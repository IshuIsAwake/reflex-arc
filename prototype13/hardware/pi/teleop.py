"""Level 1 -- drive the rover from the keyboard. Runs on the Pi, over SSH.

    python3 teleop.py            real motors
    python3 teleop.py --fake     prints instead, for trying it on a laptop

Two ways to drive, on the same keys as PI_5's drive.py where they overlap:

  free    w a s d   go and keep going; any key or LATCH_MAX_S of silence stops it
          x SPACE   stop
  grid    i         forward one cell      k   back one cell
          j         left 90               l   right 90
          These are the timed primitives `run.py` uses, so this is where you see
          whether the calibration holds before handing it a whole sequence.

          q         quit (stops first)

Grid moves keep a dead-reckoned pose and print it. It is only what the timings
claim -- nothing has measured it. `run.py` is where it gets checked.
"""

import argparse
import time

import config as C
import grid
import moves
from keys import Keys
from motors import open_motors

FREE = {"w": moves.POWER["F"], "s": moves.POWER["B"],
        "a": moves.POWER["L"], "d": moves.POWER["R"]}
GRID = {"i": "F", "k": "B", "j": "L", "l": "R"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fake", action="store_true", help="print instead of driving")
    args = ap.parse_args()

    motors = open_motors(args.fake)
    pose = grid.Pose(0, 0, 0)
    print(__doc__.split("Two ways")[1].split("Grid moves")[0])
    print(f"duty band {C.MIN_DUTY:.3f}..{C.MAX_DUTY:.3f}   "
          f"{C.FORWARD_S_PER_CELL:.2f} s/cell   {C.TURN_S_PER_90:.2f} s/90")
    print("Lift the wheels for the first try.\n")

    moving_since = None
    try:
        with Keys() as keys:
            while True:
                ch = keys.read(0.05)
                if moving_since and time.monotonic() - moving_since > C.LATCH_MAX_S:
                    motors.stop()
                    moving_since = None
                    print("  stopped: no key for", C.LATCH_MAX_S, "s")
                if ch is None:
                    continue
                ch = ch.lower()
                if ch == "q":
                    break
                if ch in FREE:
                    left, right = FREE[ch]
                    motors.set(left * C.DRIVE_POWER, right * C.DRIVE_POWER)
                    moving_since = time.monotonic()
                elif ch in GRID:
                    motors.stop()
                    moving_since = None
                    prim = GRID[ch]
                    ran = moves.do(motors, prim, stop_check=lambda: keys.read(0) is not None)
                    pose = grid.apply(pose, prim)
                    print(f"  {prim}  {ran:.2f} s   dead-reckoned {pose}")
                else:   # x, space, anything else: stop
                    motors.stop()
                    moving_since = None
    except KeyboardInterrupt:
        pass
    finally:
        motors.close()
        print("\nstopped.")


if __name__ == "__main__":
    main()
