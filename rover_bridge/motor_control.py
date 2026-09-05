"""
motor_control.py — driver for the rover's actual motor controller: a
SmartElex 15D board in PWM independent mode, on a Raspberry Pi 5. Takes
(throttle, turn) commands in [-1, 1] — the same action shape RoverAgent.cs
outputs in Unity — and drives the two motors accordingly.

This is a non-ROS strip-down of Nithin's tested/calibrated ROS2 node
(rover_drive_logic/l298n_node.py, pulled from his rover_ros2 Pi on
2026-09-04) — same wiring, same pins, same measured duty calibration, same
gpiozero library, just without the rclpy/ROS2 dependency this project
doesn't need. See that file's docstring for the full calibration writeup
(the duty-vs-speed sweep, why quantized levels broke things, etc.).

Wiring (Pi 5 GPIO -> SmartElex PWM/analog header, INDEPENDENT mode):
    PWM1 (S1) <- BCM 12   DIR1 <- BCM 23   -> Motor 1 (left)
    PWM2 (S2) <- BCM 13   DIR2 <- BCM 24   -> Motor 2 (right)
    Pi GND <-> driver GND (commoned), I/P LOGIC SELECT jumpers -> ON (3V3)
    Motor power: external 7-22V on VIN/GND.

Duty model (SmartElex datasheet + measured on this chassis):
    DIR high = forward, low = reverse.
    duty 8% -> 0% motor speed, 94% -> 100% motor speed, linear. 0% = stopped.
    MIN_DUTY/MAX_DUTY below are the *calibrated usable band* (not the
    hardware's raw 8-94% range) — the floor below which the drivetrain
    stalls and the ceiling that keeps it controllable. Re-measure
    (rover_drive_logic/README.md) after any change to tyres, load, battery,
    or the driver board itself.
"""

import time
import threading

try:
    from gpiozero import PWMOutputDevice, DigitalOutputDevice
except ImportError:
    # Lets you import/lint this file on a non-Pi machine without gpiozero
    # installed. Actually running Rover() will fail loudly off-Pi, which is
    # correct — motor control only makes sense on the rover. On the Pi 5
    # itself gpiozero also needs its lgpio pin factory:
    #     sudo apt update && sudo apt install -y python3-gpiozero python3-lgpio
    PWMOutputDevice = DigitalOutputDevice = None

# --- Pins (BCM numbering) -----------------------------------------------
LEFT_MOTOR = {"pwm": 12, "dir": 23}
RIGHT_MOTOR = {"pwm": 13, "dir": 24}
PWM_FREQ_HZ = 490  # matches SmartElex node; gpiozero write latency ~0.1ms at this rate

# Flip if a motor is wired/spinning backwards, instead of re-wiring.
# Left at default (no inversion) per instruction 2026-09-05 -- the
# INVERT_LEFT=True guess from on-bench observation didn't resolve the
# button-direction mismatch, so revert to defaults until the per-motor
# diagnostic (test_wheels.py) results are confirmed.
INVERT_LEFT = False
INVERT_RIGHT = False

# --- Calibrated duty band (measured on this chassis, see module docstring) ---
MIN_DUTY = 0.082  # duty at which the drivetrain actually starts moving
MAX_DUTY = 0.154  # duty ceiling — keeps the (low-grip) tyres controllable
DEADZONE = 1e-3   # ignore tiny float noise in throttle/turn

# If no drive command arrives within this many seconds, motors auto-stop.
# Prevents a runaway rover if the network link to Unity/the webapp drops.
WATCHDOG_TIMEOUT_S = 0.5
# -------------------------------------------------------------------------


def _clamp(v, lo=-1.0, hi=1.0):
    return max(lo, min(hi, v))


class Motor:
    """One motor: one PWM pin + one direction pin (SmartElex independent-mode channel)."""

    def __init__(self, pwm_pin, dir_pin, freq_hz, invert=False):
        self.pwm = PWMOutputDevice(pwm_pin, frequency=freq_hz)
        self.dir = DigitalOutputDevice(dir_pin)
        self.invert = invert
        self.pwm.value = 0.0

    def drive(self, speed: float):
        """speed in [-1, 1]: sign = direction, magnitude maps into [MIN_DUTY, MAX_DUTY]."""
        speed = _clamp(speed)
        if self.invert:
            speed = -speed
        if abs(speed) <= DEADZONE:
            self.pwm.value = 0.0
            return
        self.dir.value = 1 if speed > 0 else 0
        frac = min(abs(speed), 1.0)
        self.pwm.value = MIN_DUTY + frac * (MAX_DUTY - MIN_DUTY)

    def stop(self):
        self.pwm.value = 0.0

    def cleanup(self):
        self.pwm.close()
        self.dir.close()


class Rover:
    """
    Differential-drive rover: takes (throttle, turn) — same convention as
    RoverAgent.cs's continuous action pair — and mixes it into per-wheel
    speeds. throttle/turn are each in [-1, 1].
    """

    def __init__(self):
        if PWMOutputDevice is None:
            raise RuntimeError(
                "gpiozero not available — this must run on the Pi, not your laptop."
            )
        self.left = Motor(LEFT_MOTOR["pwm"], LEFT_MOTOR["dir"], PWM_FREQ_HZ, INVERT_LEFT)
        self.right = Motor(RIGHT_MOTOR["pwm"], RIGHT_MOTOR["dir"], PWM_FREQ_HZ, INVERT_RIGHT)

        self._lock = threading.Lock()
        self._last_command_time = 0.0
        self._stopped = True

        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def drive(self, throttle: float, turn: float):
        throttle = _clamp(throttle)
        turn = _clamp(turn)
        left_speed = _clamp(throttle + turn)
        right_speed = _clamp(throttle - turn)
        with self._lock:
            self.left.drive(left_speed)
            self.right.drive(right_speed)
            self._last_command_time = time.time()
            self._stopped = False

    def stop(self):
        with self._lock:
            self.left.stop()
            self.right.stop()
            self._stopped = True

    def _watchdog_loop(self):
        while True:
            time.sleep(0.1)
            with self._lock:
                stale = (not self._stopped) and (
                    time.time() - self._last_command_time > WATCHDOG_TIMEOUT_S
                )
            if stale:
                self.stop()

    def cleanup(self):
        self.stop()
        self.left.cleanup()
        self.right.cleanup()


if __name__ == "__main__":
    # Quick standalone smoke test: forward, then turn, then stop.
    # Run directly on the Pi with `python3 motor_control.py` to confirm
    # wiring/direction before touching the webapp or Unity at all.
    r = Rover()
    try:
        print("Forward (throttle=0.5) for 1s...")
        r.drive(0.5, 0.0)
        time.sleep(1)

        print("Turn right in place (turn=0.5) for 1s...")
        r.drive(0.0, 0.5)
        time.sleep(1)

        print("Stopping.")
        r.stop()
    finally:
        r.cleanup()
