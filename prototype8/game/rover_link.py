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
into two turns and a forward before anything is sent. A LEFT pivot is refused
outright and the whole file is skipped: the left motor's DIR line is
hardware-faulted as of 2026-09-05 and cannot turn that way at all. Driving
everything up to the bad turn and stopping silently wrong is worse than not
starting.
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
# dashboard already drives safely; LEFT is refused in `drive` before this is used.
_DRIVE = {"FORWARD": (1.0, 0.0), "RIGHT": (0.0, -1.0), "LEFT": (0.0, 1.0)}


def _post(pi, path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(f"{pi}{path}", data=data,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def actions_from_file(path):
    """The live action list out of a written plan.txt.

    `nav.write_plan` already comments out every finished leg, so an uncommented
    FORWARD/LEFT/RIGHT/BACKWARD line IS a move still to drive -- no leg-boundary
    bookkeeping needed here. BACKWARD is expanded on the way out, per
    `nav.route_actions`'s note that this rover cannot reverse.
    """
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line == "BACKWARD":
                out += ["RIGHT", "RIGHT", "FORWARD"]
            elif line in ("FORWARD", "LEFT", "RIGHT"):
                out.append(line)
    return out


def drive(pi, actions):
    """Send one pulse a action, in order. Refuses up front rather than partway
    through -- see the module docstring for why a LEFT anywhere in the list
    voids the whole thing."""
    if "LEFT" in actions:
        raise ValueError("route needs a LEFT turn -- left motor can't reverse, "
                          "hardware-faulted. Nothing sent.")
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
                except (ValueError, urllib.error.URLError) as e:
                    print(f"  REFUSED/FAILED: {e}")
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
