"""Measure how long a cell and a quarter turn take, on this floor, today.

    python3 calibrate.py forward 3.0 --reps 3     drive 3 s; you measure the distance
    python3 calibrate.py turn 1.5 --reps 4        turn 1.5 s; you measure the angle

The mean is saved to calib.json. Check the spread first: a wide one means open-loop moves
will miss. Turns alternate direction. Re-run after any change to tyres, load or battery."""

import argparse
import statistics
import time

import config as C
from motors import open_motors

POWER = {"forward": (1, 1), "turn": (1, -1)}


def ask(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("  a number, please")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=("forward", "turn"))
    ap.add_argument("seconds", type=float)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--fake", action="store_true")
    args = ap.parse_args()
    if not 0 < args.seconds <= 10:
        ap.error("keep a pulse between 0 and 10 s")

    motors = open_motors(args.fake)
    unit = "cm" if args.what == "forward" else "degrees"
    got = []
    try:
        for r in range(args.reps):
            input(f"rep {r + 1}/{args.reps}: place the rover, Enter to go ")
            left, right = POWER[args.what]
            sign = -1 if (args.what == "turn" and r % 2) else 1
            p = C.DRIVE_POWER if args.what == "forward" else C.TURN_POWER
            motors.set(sign * left * p, sign * right * p)
            time.sleep(args.seconds)
            motors.stop()
            time.sleep(C.SETTLE_S)
            got.append(abs(ask(f"  measured, in {unit}: ")))
    finally:
        motors.close()

    rate = [g / args.seconds for g in got]
    m = statistics.mean(rate)
    spread = (max(rate) - min(rate)) / m * 100 if m else 0
    print(f"\n{unit}/s per rep: {' '.join(f'{x:.1f}' for x in rate)}   "
          f"mean {m:.2f}   spread {spread:.0f}%")
    if m <= 0:
        print("it did not move -- check power and MIN_DUTY. Nothing saved.")
        return
    if args.what == "forward":
        speed = m / 100  # cm/s -> m/s
        C.save(FORWARD_M_PER_S=round(speed, 4))
        print(f"FORWARD_M_PER_S = {speed:.3f} m/s  (saved) -> {C.FORWARD_S_PER_CELL:.2f} s "
              f"for a {C.CELL_M} m cell; a new cell size follows by itself")
    else:
        value = 90 / m
        C.save(TURN_S_PER_90=round(value, 3))
        print(f"TURN_S_PER_90 = {value:.2f} s  (saved)")
    if spread > 15:
        print("spread over 15 % -- open-loop moves will miss often.")


if __name__ == "__main__":
    main()
