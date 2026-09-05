r"""The last stop before the motors.

    .venv\Scripts\python.exe game\rover_link.py --pi http://10.7.20.227:5000

`nav.write_plan` already puts one FORWARD/LEFT/RIGHT/BACKWARD action a line in the
live route file (`nav.plan_file()`), rewritten atomically on every goto/replan. This
watches that file and calls the rover bridge's two oldest endpoints, /drive and
/stop, directly -- nothing in between, and nothing on the Pi has to know a plan file
exists.

No policy in the loop yet: every action is one open-loop pulse, ROVER_PULSE_SECONDS
long, then a stop. See ARCHITECTURE.md's "learned policy" layer for what eventually
replaces the fixed pulse -- the file format does not change when it does.

The rover cannot reverse (`nav.route_actions`'s own note), so BACKWARD is expanded
into two turns, a forward, and two turns back before anything is sent -- BACKWARD
leaves the plan's heading alone, so the rover has to end it facing as it started or
everything after drives mirrored. The left motor's DIR line is
hardware-faulted as of 2026-09-05 and cannot turn that way at all either, so LEFT
(a 90 degree turn that way) is driven as three RIGHT pulses instead: turning 270
degrees right lands on the same heading as 90 degrees left. Slower and never
touches the broken pivot -- only FORWARD and RIGHT are ever actually sent.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request

import nav

ROVER_PULSE_SECONDS = 0.5

# (throttle, turn) per action -- FORWARD and RIGHT match what the rover's own
# dashboard already drives safely. Nothing else is ever looked up: LEFT and
# BACKWARD are both expanded away in `actions_from_file`, before this is used.
_DRIVE = {"FORWARD": (1.0, 0.0), "RIGHT": (0.0, -1.0)}


def _post(pi, path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(f"{pi}{path}", data=data,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def actions_from_file(path):
    """The live action list out of a written plan.txt, reduced to only FORWARD and
    RIGHT -- the two moves the rover can actually make right now.

    `nav.write_plan` already comments out every finished leg, so an uncommented
    FORWARD/LEFT/RIGHT/BACKWARD line IS a move still to drive -- no leg-boundary
    bookkeeping needed here.

    BACKWARD becomes two turns, a forward, and two turns back, per
    `nav.route_actions`'s own note that this rover cannot reverse. The turn back
    is the load-bearing half: `route_actions` emits BACKWARD as a move that leaves
    the heading alone, so every action after it assumes the old facing. Stopping
    after the forward -- the same note's "two turns' worth of heading error" --
    leaves the rover 180 degrees out and drives the rest of the route mirrored.

    LEFT becomes three RIGHT turns -- 270 degrees right ends on the same heading
    as 90 degrees left -- because the left motor can't reverse either, so it can't
    pivot that way directly at all. That one is already heading-neutral.
    """
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line == "BACKWARD":
                out += ["RIGHT", "RIGHT", "FORWARD", "RIGHT", "RIGHT"]
            elif line == "LEFT":
                out += ["RIGHT", "RIGHT", "RIGHT"]
            elif line in ("FORWARD", "RIGHT"):
                out.append(line)
    return out


def drive(pi, actions):
    """Send one pulse a action, in order."""
    for action in actions:
        throttle, turn = _DRIVE[action]
        _post(pi, "/drive", {"throttle": throttle, "turn": turn})
        time.sleep(ROVER_PULSE_SECONDS)
        _post(pi, "/stop")


def watch(pi, path, interval=1.0):
    """Poll `path` for changes and drive whatever it holds, each time it does.

    A file that is not there yet, or is mid-atomic-replace (`nav._replace`),
    is skipped for this tick rather than crashing the loop. Never fires twice
    on the same content -- only an actual rewrite (a fresh goto or replan)
    triggers a drive.
    """
    last_mtime = None
    print(f"Watching {path} -> {pi} (Ctrl+C to stop)")
    while True:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            time.sleep(interval)
            continue
        if mtime != last_mtime:
            last_mtime = mtime
            actions = actions_from_file(path)
            if actions:
                print(f"[{time.strftime('%H:%M:%S')}] plan changed: {actions}")
                try:
                    drive(pi, actions)
                    print("  done")
                except urllib.error.URLError as e:
                    print(f"  FAILED: {e}")
        time.sleep(interval)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pi", default="http://10.7.20.227:5000",
                   help="rover bridge base URL (default: %(default)s)")
    p.add_argument("--plan-file", default=None,
                   help="default: the live route file from settings.PLAN_FILE")
    p.add_argument("--interval", type=float, default=1.0,
                   help="poll interval in seconds (default: %(default)s)")
    args = p.parse_args(argv)

    path = args.plan_file or nav.plan_file()
    if not path:
        p.error("no plan file configured (settings.PLAN_FILE is unset) and "
                 "--plan-file not given")
    watch(args.pi, path, args.interval)


if __name__ == "__main__":
    main()
