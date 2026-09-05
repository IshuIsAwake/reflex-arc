#!/usr/bin/env python3
"""
l298n_node  --  cmd_vel -> SmartElex 15D motor driver over PWM (independent mode).
Filename kept as l298n_node.py so /root/stack.sh and the launch line
(python3 /root/l298n_node.py) need ZERO changes. ROS node name is 'smart_elex_15d'.

*** MODE: PWM LINEAR INDEPENDENT (DIP = Mode 3: SW1=OFF SW2=OFF SW3=ON SW4=ON) ***
Retired the TTL-serial mode (the SmartElex's ~2.0 s per-write floor that made
teleop/nav crawl). PWM is continuous: a new duty cycle applies within one PWM
period (~2 ms @ 490 Hz), measured write latency ~0.1 ms on the Pi 5.

Wiring (Pi 5 GPIO -> SmartElex PWM/analog header, INDEPENDENT mode):
    PWM1 (S1) <- m1_pwm_pin (def 12)   DIR1 <- m1_dir_pin (def 23)   -> Motor 1
    PWM2 (S2) <- m2_pwm_pin (def 13)   DIR2 <- m2_dir_pin (def 24)   -> Motor 2
    Pi GND  <->  driver GND  (MUST be commoned)
    I/P LOGIC SELECT jumpers -> ON (3V3; Pi GPIO is 3.3 V)
    Motor power: external 7-22 V on VIN/GND (USB no longer used for control).

SmartElex INDEPENDENT PWM duty map (from the datasheet):
    DIR HIGH = clockwise (forward), LOW = counterclockwise (reverse)
    duty  8 % -> 0 % motor speed,  94 % -> 100 % motor speed (linear)
    duty  0 % -> STOPPED  (safe default: low/floating pin = motors off)
We reproduce the OLD serial speed levels: serial SPD N (0..9) == N/9 of full
motor speed, so level_to_duty(N) = 0.08 + (N/9)*0.86 for N>=1, 0 for N==0.
=> identical behaviour to the serial node, just ~0.1 ms latency instead of ~2 s.

Kinematics / direction (UNCHANGED from the serial node -- verified motion):
    vL = v - w*track_width/2 ;  vR = v + w*track_width/2
    left_is_a=True  -> ch1=M1=left(vL) , ch2=M2=right(vR)
    left_is_a=False -> ch1=M1=right(vR), ch2=M2=left(vL)   (this build)
    DIR HIGH when wheel speed > 0 (forward); LOW when < 0 (reverse).
    invert_left / invert_right flip a channel's direction if a motor is wired reversed.

Speed model (UNCHANGED):
    max_speed<=0 : any nonzero wheel cmd = full power (level 9).  (legacy)
    max_speed >0 : level = round(|v|/max_speed*9), floored at min_level,
                   capped at max_level.  (proportional, quantized to 9 levels)
    `rover speed N` sets min_level=max_level=N -> every motion runs at level N
    (same bang-bang power level as before in BOTH teleop and nav).

WATCHDOG (deadman): if no /cmd_vel for `deadman` seconds (default 2.0), force
STOP. Set deadman:=0 to disable (legacy: last command persists -- stack.sh
uses 0.0 for latched teleop and relies on stop_cmd.py / Nav2 smoother timeout).

NOTE on libraries: uses gpiozero (validated on this Pi 5 at ~0.1 ms). gpiozero
needs its lgpio pin factory on the Pi 5, so wherever this node runs (host or the
--privileged container with /dev bind-mounted) you need gpiozero + lgpio
installed. No writer thread: PWM/DIR writes are non-blocking, so the control
loop sets the pins directly.
"""
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

try:
    from gpiozero import PWMOutputDevice, DigitalOutputDevice
except ImportError:
    raise SystemExit(
        "gpiozero is not installed -- install it (and lgpio for Pi 5):\n"
        "    sudo apt update && sudo apt install -y python3-gpiozero python3-lgpio")

DZ = 1e-3               # deadzone (ignore tiny float noise on cmd_vel)
PWM_MIN = 0.08          # SmartElex: 8 % duty  -> 0 % motor
PWM_MAX = 0.94          # SmartElex: 94 % duty -> 100 % motor


class SmartElex15D(Node):
    def __init__(self):
        super().__init__('smart_elex_15d')

        # --- pins / hw ---
        self.m1_pwm_pin = int(self.declare_parameter('m1_pwm_pin', 12).value)
        self.m1_dir_pin = int(self.declare_parameter('m1_dir_pin', 23).value)
        self.m2_pwm_pin = int(self.declare_parameter('m2_pwm_pin', 13).value)
        self.m2_dir_pin = int(self.declare_parameter('m2_dir_pin', 24).value)
        self.pwm_freq   = int(self.declare_parameter('pwm_freq', 490).value)

        # --- kinematics / direction (identical to the serial node) ---
        self.track_width  = float(self.declare_parameter('track_width', 0.15).value)
        self.left_is_a    = self.declare_parameter('left_is_a', True).value
        self.invert_left  = self.declare_parameter('invert_left', False).value
        self.invert_right = self.declare_parameter('invert_right', False).value

        # --- speed model (identical to the serial node) ---
        self.max_speed = float(self.declare_parameter('max_speed', 0.0).value)
        self.max_level = int(self.declare_parameter('max_level', 9).value)
        self.min_level = int(self.declare_parameter('min_level', 2).value)
        self.deadman   = float(self.declare_parameter('deadman', 2.0).value)  # s; 0 = off

        # --- PROPORTIONAL (continuous-duty) speed model ---
        # The 0..9 levels are a leftover from SERIAL mode, where speed really was one
        # digit in the *[D][S][D][S]# packet. In INDEPENDENT PWM mode the board takes a
        # CONTINUOUS duty: 8 % -> 0 % motor, 94 % -> 100 %, linear (manual p.13). Nothing
        # requires quantizing to 9 steps, and quantizing costs the thing Nav2 needs most.
        #
        # With `speed N` setting min_level == max_level == N, every nonzero wheel command
        # collapsed to ONE duty (level 1 = 17.6 %), so only the SIGN of /cmd_vel survived.
        # Measured on the bench: commanding wz=-0.15 and wz=-0.5 rad/s for 0.6 s produced
        # -51.9 deg and -44.4 deg respectively -- 3.3x less commanded velocity produced
        # MORE rotation. DWB was asking for gentle heading trims and getting a ~1.4 rad/s
        # lurch (~10x commanded), so it could never settle inside yaw_goal_tolerance.
        #
        # Proportional mode maps the requested fraction of max_speed into the usable duty
        # band [min_duty, max_duty]:
        #   min_duty -- the duty at which the drivetrain actually STARTS moving. Below it
        #               the motors stall and Nav2 would be commanding motion that never
        #               happens. Must be MEASURED, not assumed; it depends on this
        #               chassis, and on the tape currently on 4 of the 6 tyres.
        #   max_duty -- the ceiling, i.e. the old `speed N` knob. Keeping it low is what
        #               keeps the low-grip tyres controllable.
        # Both are runtime-settable (`ros2 param set`) so the deadband can be swept
        # without restarting the node and losing the GPIO.
        self.proportional = bool(self.declare_parameter('proportional', True).value)
        self.min_duty = float(self.declare_parameter('min_duty', PWM_MIN).value)
        max_duty_p = float(self.declare_parameter('max_duty', 0.0).value)
        self.max_duty = max_duty_p if max_duty_p > 0.0 else self._level_to_duty(self.max_level)
        self.add_on_set_parameters_callback(self._on_set_params)

        ctrl_hz = max(float(self.declare_parameter('ctrl_hz', 20.0).value), 1.0)

        # --- gpiozero devices ---
        self.m1_pwm = PWMOutputDevice(self.m1_pwm_pin, frequency=self.pwm_freq)
        self.m1_dir = DigitalOutputDevice(self.m1_dir_pin)
        self.m2_pwm = PWMOutputDevice(self.m2_pwm_pin, frequency=self.pwm_freq)
        self.m2_dir = DigitalOutputDevice(self.m2_dir_pin)
        self._stop()  # start safely: motors off

        # --- command state (single-threaded executor -> no lock needed) ---
        self.v = 0.0
        self.w = 0.0
        self._last_cmd = 0.0          # monotonic time of last /cmd_vel (0 = never)

        # remember last applied output so we only write the hardware on change
        self._last = (None, None, None, None)   # (m1_dir, m1_duty, m2_dir, m2_duty)

        self.create_subscription(Twist, '/cmd_vel', self.on_cmd, 10)
        self.create_timer(1.0 / ctrl_hz, self.tick)

        self.get_logger().info(
            f"smart_elex_15d ready (PWM independent @ {self.pwm_freq} Hz) "
            f"pins M1[pwm{self.m1_pwm_pin}/dir{self.m1_dir_pin}] "
            f"M2[pwm{self.m2_pwm_pin}/dir{self.m2_dir_pin}] "
            f"track={self.track_width:.3f} left_is_a={self.left_is_a} "
            f"invL={self.invert_left} invR={self.invert_right} "
            f"max_speed={self.max_speed} max_level={self.max_level} "
            f"min_level={self.min_level} "
            f"{'PROPORTIONAL duty %.3f..%.3f' % (self.min_duty, self.max_duty) if self.proportional else 'QUANTIZED levels'} "
            f"deadman={self.deadman} "
            f"(~0.1 ms writes, no 2 s serial floor)")

    # ---------- cmd_vel ----------
    def on_cmd(self, msg):
        self.v = msg.linear.x
        self.w = msg.angular.z
        self._last_cmd = time.monotonic()

    # ---------- control loop ----------
    def tick(self):
        now = time.monotonic()
        v, w = self.v, self.w
        stale = (self.deadman > 0.0) and \
                (self._last_cmd == 0.0 or (now - self._last_cmd > self.deadman))
        if stale:                      # watchdog -> STOP
            v, w = 0.0, 0.0
        vL = v - w * self.track_width / 2.0
        vR = v + w * self.track_width / 2.0
        if self.left_is_a:
            m1_dir, m1_duty = self._chan(vL, self.invert_left)    # M1 = left
            m2_dir, m2_duty = self._chan(vR, self.invert_right)   # M2 = right
        else:
            m1_dir, m1_duty = self._chan(vR, self.invert_right)   # M1 = right
            m2_dir, m2_duty = self._chan(vL, self.invert_left)    # M2 = left
        self._apply(m1_dir, m1_duty, m2_dir, m2_duty)

    # ---------- runtime parameter updates ----------
    def _on_set_params(self, params):
        """Allow min_duty/max_duty/proportional to be retuned live.

        Calibrating the deadband means trying a dozen duties; restarting the node for
        each one tears down and re-grabs the GPIO, which is both slow and a good way to
        leave a motor latched mid-sweep. Clamped to the board's legal 8..94 % window.
        """
        from rcl_interfaces.msg import SetParametersResult
        for p in params:
            if p.name == 'min_duty':
                self.min_duty = max(0.0, min(float(p.value), PWM_MAX))
            elif p.name == 'max_duty':
                self.max_duty = max(0.0, min(float(p.value), PWM_MAX))
            elif p.name == 'proportional':
                self.proportional = bool(p.value)
        self._last = (None, None, None, None)      # force a rewrite on the next tick
        return SetParametersResult(successful=True)

    # ---------- per-channel: (dir_high, duty) ----------
    def _chan(self, speed, invert):
        """Return (dir_high: bool, duty: float 0..PWM_MAX). Stopped -> (True, 0.0)."""
        if invert:
            speed = -speed
        if abs(speed) <= DZ:
            return True, 0.0                       # stopped: duty 0 (dir don't-care)
        dir_high = speed > 0.0
        if self.proportional and self.max_speed > 0.0:
            # continuous duty: |wheel speed| as a fraction of full scale, mapped into
            # the usable band. frac is clamped, NOT wrapped -- an over-range command
            # saturates at max_duty rather than folding back to a small duty.
            frac = min(abs(speed) / self.max_speed, 1.0)
            lo, hi = self.min_duty, max(self.max_duty, self.min_duty)
            return dir_high, lo + frac * (hi - lo)
        if self.max_speed <= 0.0:
            lvl = 9                                # legacy: full power
        else:
            lvl = int(round(min(abs(speed) / self.max_speed, 1.0) * 9.0))
            lvl = max(self.min_level, min(9, lvl)) # floor (weak cmds still move)
        lvl = min(lvl, self.max_level)             # ceiling (safe cap)
        return dir_high, self._level_to_duty(lvl)

    @staticmethod
    def _level_to_duty(lvl):
        """Serial SPD level 0..9 -> SmartElex PWM duty fraction (0..0.94).
        lvl 0 = 0 (stopped); lvl N reproduces serial SPD N = N/9 of full motor."""
        if lvl <= 0:
            return 0.0
        return PWM_MIN + (lvl / 9.0) * (PWM_MAX - PWM_MIN)

    # ---------- hardware ----------
    def _apply(self, m1_dir, m1_duty, m2_dir, m2_duty):
        state = (m1_dir, m1_duty, m2_dir, m2_duty)
        if state == self._last:                    # nothing changed -> skip the write
            return
        self.m1_dir.value = 1 if m1_dir else 0
        self.m1_pwm.value = m1_duty
        self.m2_dir.value = 1 if m2_dir else 0
        self.m2_pwm.value = m2_duty
        self._last = state

    def _stop(self):
        self.m1_pwm.value = 0.0
        self.m2_pwm.value = 0.0
        self._last = (None, None, None, None)      # force a real write on next cmd

    def destroy_node(self):
        try:
            self._stop()                           # motors off
            self.m1_pwm.close(); self.m1_dir.close()
            self.m2_pwm.close(); self.m2_dir.close()
        except Exception as e:
            self.get_logger().warn(f"shutdown error: {e}")
        return super().destroy_node()


def main():
    rclpy.init()
    node = SmartElex15D()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

