"""One grid move (F B L R), driven by time: power on, wait, power off, settle. Nothing
here knows whether it worked. Turns are the weak part: identical turn pulses have landed
34% apart on this rover."""

import time

import config as C

# Left and right power for each move. L turns anticlockwise seen from above.
POWER = {"F": (1, 1), "B": (-1, -1), "L": (-1, 1), "R": (1, -1)}


def seconds(prim):
    return C.FORWARD_S_PER_CELL if prim in "FB" else C.TURN_S_PER_90


def do(motors, prim, stop_check=None, n=1):
    """Drive one move `n` times over as one pulse, then stop. A run of three cells is one
    stop instead of three. `stop_check()` returning True cuts it short. Returns the seconds the
    motors were on."""
    left, right = POWER[prim]
    p = C.DRIVE_POWER if prim in "FB" else C.TURN_POWER
    want = seconds(prim) * n
    t0 = time.monotonic()
    try:
        motors.set(left * p, right * p)
        while True:
            remaining = want - (time.monotonic() - t0)
            if remaining <= 0 or (stop_check and stop_check()):
                break
            time.sleep(min(0.01, remaining))  # end on time, not up to 10 ms late
    finally:
        motors.stop()
    ran = time.monotonic() - t0
    time.sleep(C.SETTLE_S)
    return ran
