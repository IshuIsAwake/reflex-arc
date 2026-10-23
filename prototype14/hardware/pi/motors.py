"""Left and right power (-1..1) in, PWM on the SmartElex out. FakeMotors prints instead,
so everything above this file runs on a laptop; open_motors() falls back to it without
gpiozero."""

import config as C


def duty(power):
    """Power -1..1 -> (forward?, duty). Clamped."""
    p = max(-1.0, min(1.0, power))
    if abs(p) < 1e-3:
        return True, 0.0
    return p > 0, C.MIN_DUTY + abs(p) * (C.MAX_DUTY - C.MIN_DUTY)


class Motors:
    def __init__(self):
        from gpiozero import DigitalOutputDevice, PWMOutputDevice
        self._pwm = (PWMOutputDevice(C.M1_PWM, frequency=C.PWM_HZ),
                     PWMOutputDevice(C.M2_PWM, frequency=C.PWM_HZ))
        self._dir = (DigitalOutputDevice(C.M1_DIR), DigitalOutputDevice(C.M2_DIR))
        self.stop()

    def set(self, left, right):
        if C.INVERT_LEFT:
            left = -left
        if C.INVERT_RIGHT:
            right = -right
        m1, m2 = (left, right) if C.LEFT_IS_M1 else (right, left)
        for pwm, pin, power in zip(self._pwm, self._dir, (m1, m2)):
            fwd, d = duty(power)
            pin.value = 1 if fwd else 0
            pwm.value = d

    def stop(self):
        for pwm in self._pwm:
            pwm.value = 0.0

    def close(self):
        self.stop()
        for dev in self._pwm + self._dir:
            dev.close()


class FakeMotors:
    """Prints what the real motors would have been told."""

    def __init__(self, quiet=False):
        self.quiet = quiet
        self.last = (0.0, 0.0)

    def set(self, left, right):
        self.last = (left, right)
        if not self.quiet:
            print(f"    [fake motors] left {left:+.2f}  right {right:+.2f}")

    def stop(self):
        if self.last != (0.0, 0.0) and not self.quiet:
            print("    [fake motors] stop")
        self.last = (0.0, 0.0)

    def close(self):
        self.stop()


def open_motors(fake=False):
    if fake:
        return FakeMotors()
    try:
        return Motors()
    except ImportError:
        print("gpiozero is not installed -- using fake motors. On the Pi:\n"
              "    sudo apt install -y python3-gpiozero python3-lgpio")
        return FakeMotors()
