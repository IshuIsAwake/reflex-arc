"""Run a command sequence and check every step. Runs on the Pi, over SSH.

    python3 run.py "forward right left forward forward"
    python3 run.py "F R L F F" --fake
    python3 run.py --plan plan.txt          a route file from the simulation, N/E/S/W a line

After each command the rover stops and the expected pose is compared with the
measured one (grid.check: Manhattan and Chebyshev). Where the measured pose comes
from is the `--measure` option, and it is the part that grows with the levels:

  ask     a person looks at the floor and types the real cell -- Level 1's sensor.
          Enter means "where it should be".
  trust   the measured pose *is* the expected one. Every check passes, so this
          proves nothing about the floor; it is for dry runs with --fake.
  (lidar) Level 4. Same check, the pose read from the LD19 instead of a person.

What happens on a miss follows ARCHITECTURE.md:
  * position: reported, never driven back. The rover carries on from where it
    really is, and every later relative command is from there.
  * heading: corrected. A wrong heading makes every later move wrong, so the
    rover turns to the heading it should have before the next command.
  * LOST (Chebyshev >= --lost-at): stop and say so.

Each run writes a line per command to runs/<time>.jsonl, for comparing runs.
"""

import argparse
import json
import os
import time

import config as C
import grid
import moves
from motors import open_motors

HERE = os.path.dirname(os.path.abspath(__file__))


def ask_pose(expected):
    """Read 'x y H' from the person watching. Enter = as expected, 'q' = stop."""
    while True:
        raw = input(f"    where is it? x y heading  [enter = {expected}]: ").strip()
        if not raw:
            return expected
        if raw.lower() == "q":
            return None
        parts = raw.replace(",", " ").split()
        try:
            x, y = int(parts[0]), int(parts[1])
            h = grid.HEADING_NAMES.index(parts[2].upper()) if len(parts) > 2 \
                else expected.heading
            return grid.Pose(x, y, h)
        except (ValueError, IndexError):
            print("    e.g. '1 0 E', or '1 0' if the heading is right")


def drive(motors, prims):
    for p in prims:
        moves.do(motors, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("commands", nargs="?", default="", help='e.g. "F R L F F"')
    ap.add_argument("--plan", help="a 10d plan.txt: one N/E/S/W per line")
    ap.add_argument("--start", default="0 0 N", help='start pose "x y H" (default "0 0 N")')
    ap.add_argument("--measure", choices=("ask", "trust"), default="ask")
    ap.add_argument("--lost-at", type=int, default=2, help="Chebyshev cells that count as lost")
    ap.add_argument("--fake", action="store_true", help="print instead of driving")
    args = ap.parse_args()

    text = args.commands
    if args.plan:
        with open(args.plan, encoding="utf-8") as fh:
            text += " " + fh.read()
    cmds = grid.parse(text)
    if not cmds:
        ap.error("no commands")
    sx, sy, sh = args.start.split()
    pose = grid.Pose(int(sx), int(sy), grid.HEADING_NAMES.index(sh.upper()))

    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    log_path = os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + ".jsonl")
    motors = open_motors(args.fake)
    tally = {"DONE": 0, "OFF": 0, "LOST": 0}
    print(f"{len(cmds)} commands from {pose}: {' '.join(cmds)}   measure={args.measure}\n")

    try:
        with open(log_path, "w", encoding="utf-8") as log:
            for i, cmd in enumerate(cmds, 1):
                prims = grid.primitives(cmd, pose.heading)
                expected = grid.apply(pose, cmd)
                print(f"[{i}/{len(cmds)}] {cmd}  ->  {''.join(prims)}   expect {expected}")
                drive(motors, prims)

                measured = expected if args.measure == "trust" else ask_pose(expected)
                if measured is None:
                    print("stopped by the operator.")
                    break
                c = grid.check(expected, measured, args.lost_at)
                tally[c.result] += 1
                print("   ", c)
                log.write(json.dumps({
                    "i": i, "cmd": cmd, "prims": prims,
                    "expected": [expected.x, expected.y, expected.heading],
                    "measured": [measured.x, measured.y, measured.heading],
                    "manhattan": c.manhattan, "chebyshev": c.chebyshev,
                    "heading_off": c.heading_off, "result": c.result,
                    "forward_s": C.FORWARD_S_PER_CELL, "turn_s": C.TURN_S_PER_90}) + "\n")

                if c.result == "LOST":
                    print("LOST -- stopping. Put it back on a known cell and start again.")
                    break
                pose = measured
                if c.heading_off:
                    fix = ["R"] * c.heading_off + ["L"] * -c.heading_off
                    print(f"    heading fix: {''.join(fix)}")
                    drive(motors, fix)
                    pose = grid.Pose(pose.x, pose.y, expected.heading)
    except KeyboardInterrupt:
        print("\ninterrupted.")
    finally:
        motors.close()

    print(f"\n{tally['DONE']} done, {tally['OFF']} off, {tally['LOST']} lost.  "
          f"ended at {pose}   log: {os.path.relpath(log_path)}")


if __name__ == "__main__":
    main()
