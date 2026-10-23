"""moves -- one grid primitive, F B L R, driven open-loop by time.

This is the whole of the rover's skill until the LiDAR is in: power on, wait the
calibrated time, power off, let it settle. Nothing here knows whether it worked.
That is `grid.check`'s job, with a pose from somewhere other than these timings --
a person at Level 1, the LiDAR from Level 4.

Expect turns to be the weak part. PI_5's calib_omega.py measured two identical
turn pulses landing 34 % apart (4 of the 6 tyres are taped), so a timed 90 is a
guess with a wide spread. Forward is steadier.
"""

import time

import config as C

# left, right power for each primitive. L turns anticlockwise seen from above.
POWER = {"F": (1, 1), "B": (-1, -1), "L": (-1, 1), "R": (1, -1)}


def seconds(prim):
    return C.FORWARD_S_PER_CELL if prim in "FB" else C.TURN_S_PER_90


def do(motors, prim, stop_check=None, n=1, secs=None):
    """Drive one primitive `n` times over, in one go, and stop. `stop_check()`
    returning True cuts it short. Returns the seconds the motors were actually on.

    `n` > 1 is for runs of the same move: three cells forward as one pulse stops and
    starts once instead of three times, and every stop is a coast nobody measured.
    `secs` drives for exactly that long instead -- the LiDAR's fix-up turns.
    """
    left, right = POWER[prim]
    p = C.DRIVE_POWER if prim in "FB" else C.TURN_POWER
    want = secs if secs is not None else seconds(prim) * n
    t0 = time.monotonic()
    try:
        motors.set(left * p, right * p)
        while True:
            remaining = want - (time.monotonic() - t0)
            if remaining <= 0 or (stop_check and stop_check()):
                break
            time.sleep(min(0.01, remaining))     # end on time, not up to 10 ms late
    finally:
        motors.stop()
    ran = time.monotonic() - t0
    time.sleep(C.SETTLE_S)
    return ran
