"""
test_wheels.py — diagnostic only. Drives each motor channel individually,
RAW (no throttle/turn mixing, no INVERT_LEFT/INVERT_RIGHT applied), at a
low, safe duty, so a human watching the rover can report exactly what each
physical wheel does. Run on the Pi: `python3 test_wheels.py`. Not used by
server.py / RoverBridgeClient — delete once wiring is confirmed.
"""
import time
from gpiozero import PWMOutputDevice, DigitalOutputDevice
from motor_control import LEFT_MOTOR, RIGHT_MOTOR, PWM_FREQ_HZ, MIN_DUTY, MAX_DUTY

DUTY = (MIN_DUTY + MAX_DUTY) / 2  # gentle, clearly-visible speed
RUN_S = 3
PAUSE_S = 2


def phase(label, pwm_pin, dir_pin, dir_high):
    print(f"\n=== {label} === (watch the rover now)")
    pwm = PWMOutputDevice(pwm_pin, frequency=PWM_FREQ_HZ)
    d = DigitalOutputDevice(dir_pin)
    d.value = 1 if dir_high else 0
    pwm.value = DUTY
    time.sleep(RUN_S)
    pwm.value = 0.0
    pwm.close()
    d.close()
    print(f"=== {label} done ===")
    time.sleep(PAUSE_S)


if __name__ == "__main__":
    print(f"Duty used for this test: {DUTY:.3f}")
    phase("M1 (pwm{}/dir{}) DIR=HIGH".format(LEFT_MOTOR['pwm'], LEFT_MOTOR['dir']),
          LEFT_MOTOR["pwm"], LEFT_MOTOR["dir"], True)
    phase("M1 (pwm{}/dir{}) DIR=LOW".format(LEFT_MOTOR['pwm'], LEFT_MOTOR['dir']),
          LEFT_MOTOR["pwm"], LEFT_MOTOR["dir"], False)
    phase("M2 (pwm{}/dir{}) DIR=HIGH".format(RIGHT_MOTOR['pwm'], RIGHT_MOTOR['dir']),
          RIGHT_MOTOR["pwm"], RIGHT_MOTOR["dir"], True)
    phase("M2 (pwm{}/dir{}) DIR=LOW".format(RIGHT_MOTOR['pwm'], RIGHT_MOTOR['dir']),
          RIGHT_MOTOR["pwm"], RIGHT_MOTOR["dir"], False)
    print("\nAll phases done.")
