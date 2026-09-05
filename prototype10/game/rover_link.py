r"""Ventral Root: the path from the planner to the motors, for prototype 10's seam.

Named for the motor root of a spinal nerve -- it carries commands out and nothing back,
and the deciding happened somewhere else.

    .venv\Scripts\python.exe game\rover_link.py --pi http://10.7.20.227:5000

Watches the live route file and drives whatever appears in it on the real rover,
then goes back to waiting. One leg per write:

    1. `nav.publish` writes the prefix the simulation has already driven
    2. this sees the file change and drives it, one pulse a line
    3. the operator presses SPACE in the game
    4. the file is wiped and the next leg is written -- back to 1

The rover is therefore always a leg behind the simulation and never ahead of it.
Nothing here is ever handed a move the sim has not already proved against the map,
which is the whole point of writing the plan after the drive rather than before
(`prototype10/DESIGN.md`, "The seam").

**The file is absolute headings, not rover moves.** One of N, E, S, W a line and
nothing else. Turning is this side's business: the sim never measured a heading and
does not want to, so this process carries one and works out how to get the nose round.
That is why `--heading` exists and why it is remembered between legs -- the file says
where to end up, never how to face.

**The rover can only drive forward and pivot anticlockwise.** One motor's DIR line is
faulted (2026-09-05) and spins forward whatever it is told. `Rover.drive` mixes
`left = throttle + turn`, so `turn = -1` asks that motor to reverse -- and a
stuck-forward motor answers by driving both wheels forward, which is a straight line
on the floor and looks like a pivot on the wire. It was observed doing exactly that.
`turn = +1` asks the *healthy* motor to reverse instead, so it is the only pivot that
works. A right turn is three lefts; 270 degrees anticlockwise ends on the same heading
as 90 degrees clockwise.

No policy in the loop yet: every move is one open-loop pulse of a fixed duration.
ARCHITECTURE.md's "learned policy" layer is what eventually replaces the fixed pulse,
and the file format does not change when it does.
"""

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

import nav

# --- what the rover can actually do -----------------------------------------

# (throttle, turn) per pulse. turn = -1 is deliberately absent, not forgotten:
# see the module docstring. Only these two pairs are ever sent.
FORWARD = (1.0, 0.0)
LEFT = (0.0, 1.0)          # anticlockwise, the one pivot the fault leaves working

FORWARD_SECONDS = 1.0      # one grid cell. Uncalibrated -- measure it.
TURN_SECONDS = 1.0         # 90 degrees anticlockwise. Uncalibrated -- measure it.

# The Pi stops the motors after 500ms without a command (WATCHDOG_TIMEOUT_S in
# motor_control.py), so a pulse longer than that has to keep re-stating itself
# or it dies halfway through.
KEEPALIVE_SECONDS = 0.2

HEADINGS = nav.HEADING_NAMES   # ("N", "E", "S", "W"), clockwise


# The link to the Pi is routed wifi, not a cable, and it drops for a second or
# two at a time -- one such drop killed a run mid-leg. Retrying is safe: a gap in
# commands is self-protecting, because the Pi stops the motors after 500ms of
# silence, so re-stating a pulse can never resume a rover that ran on unwatched.
POST_TRIES = 3
POST_TIMEOUT = 3


def _post(pi, path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    last = None
    for attempt in range(POST_TRIES):
        req = urllib.request.Request(f"{pi}{path}", data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=POST_TIMEOUT) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as e:
            last = e
            if attempt + 1 < POST_TRIES:
                print(f"         {path} did not answer ({e}) -- retrying")
                time.sleep(0.3)
    raise last


def headings_from_file(path):
    """The headings in a written plan file, or [] if there is nothing to drive.

    A missing file, an empty one, or one caught mid-atomic-replace (`nav._replace`)
    all come back empty rather than raising -- the wipe between legs is the normal
    case, not an error. Anything that is not a heading is refused rather than
    skipped: a plan file with a stray line in it is a plan nobody wrote, and
    driving the rest of it would be acting on a file we do not understand.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().upper()
        if not line:
            continue
        if line not in HEADINGS:
            raise ValueError(f"{path}:{n}: {raw.strip()!r} is not one of {'/'.join(HEADINGS)}")
        out.append(line)
    return out


def expand(headings, facing):
    """Absolute headings to pulses, and the heading they leave the rover on.

    A left turn is one step anticlockwise, so facing `to` from `facing` costs
    `(facing - to) mod 4` lefts -- N to W is one, N to E is three the long way
    round. Then one forward. Checked against all sixteen from/to pairs.
    """
    moves = []
    for to in headings:
        lefts = (HEADINGS.index(facing) - HEADINGS.index(to)) % 4
        moves += ["LEFT"] * lefts
        facing = to
        moves.append("FORWARD")
    return moves, facing


def pulse(pi, action, seconds):
    """Hold one action for `seconds`, then stop.

    Re-stated every KEEPALIVE_SECONDS because the Pi's watchdog would otherwise
    cut the motors mid-pulse and the move would come up short with nothing said.
    """
    throttle, turn = action
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _post(pi, "/drive", {"throttle": throttle, "turn": turn})
        time.sleep(min(KEEPALIVE_SECONDS, max(0.0, deadline - time.monotonic())))
    _post(pi, "/stop")


def drive(pi, moves, dry_run=False):
    """Send one pulse a move, in order. Stops the motors on any failure."""
    for i, move in enumerate(moves, 1):
        action = FORWARD if move == "FORWARD" else LEFT
        seconds = FORWARD_SECONDS if move == "FORWARD" else TURN_SECONDS
        print(f"    {i:>3}/{len(moves)}  {move}")
        if dry_run:
            continue
        try:
            pulse(pi, action, seconds)
        except (urllib.error.URLError, OSError) as e:
            try:
                _post(pi, "/stop")
            except Exception:
                pass
            raise RuntimeError(f"lost the bridge at move {i}/{len(moves)}: {e}") from e


def watch(pi, path, facing="N", interval=0.25, dry_run=False):
    """Drive each leg as it appears, and keep the heading between them.

    Fires on *content*, not on mtime: the wipe between legs rewrites the file and
    an mtime watcher would treat the empty result as a new plan. Never drives the
    same bytes twice, so a rewrite that happens to repeat a leg still only runs it
    once -- the sim asks for a leg by changing the file, and an unchanged file is
    not an ask.
    """
    print(f"Watching {path}")
    print(f"  bridge  {pi}{'  (DRY RUN -- nothing is sent)' if dry_run else ''}")
    print(f"  facing  {facing}")
    print(f"  pulses  forward {FORWARD_SECONDS}s, left {TURN_SECONDS}s  (uncalibrated)")
    print("Ctrl+C to stop.\n")

    # Whatever is in the file at startup has already been driven, or was never
    # ours: the game writes a leg and waits, so a file with content in it when
    # this begins is the *last* leg, not the next one. Remembering it before the
    # loop starts is what makes it safe to start this before the game -- without
    # it, a leftover file drives the moment the process opens, against a rover
    # nobody is watching yet.
    last = _digest(path)
    stale = headings_from_file(path) if last else []
    if stale:
        print(f"  ignoring the leg already in the file: {' '.join(stale)}")
        print("  (already driven, or from an earlier run -- waiting for the next write)\n")

    while True:
        # The digest is taken *before* the parse, so a file we have already
        # answered for is dropped whether it was drivable or not. Checking
        # afterwards let a bad file re-raise on every poll and say so every
        # time, which buries the run in one repeated line.
        seen = _digest(path)
        if seen == last:
            time.sleep(interval)
            continue
        last = seen

        try:
            headings = headings_from_file(path)
        except ValueError as e:
            print(f"  REFUSED: {e}")
            print("  Nothing sent. Waiting for the file to change.")
            time.sleep(interval)
            continue

        if not headings:
            time.sleep(interval)
            continue

        moves, ends = expand(headings, facing)
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] leg: {' '.join(headings)}")
        print(f"           {len(moves)} pulse(s), {facing} -> {ends}")
        try:
            drive(pi, moves, dry_run)
        except RuntimeError as e:
            print(f"  FAILED: {e}")
            print(f"  Heading is no longer trustworthy -- restart with --heading once "
                  f"you have looked at the rover.")
            return
        facing = ends
        print(f"           done. facing {facing}. waiting for the next leg.\n")


def _digest(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pi", default="http://10.7.20.227:5000",
                   help="rover bridge base URL (default: %(default)s)")
    p.add_argument("--plan-file", default=None,
                   help="default: the live route file from settings.PLAN_FILE")
    p.add_argument("--heading", default="N", choices=list(HEADINGS),
                   help="which way the rover is pointing right now (default: %(default)s)")
    p.add_argument("--interval", type=float, default=0.25,
                   help="poll interval in seconds (default: %(default)s)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the pulses and send nothing -- the rover does not move")
    args = p.parse_args(argv)

    path = args.plan_file or nav.plan_file()
    if not path:
        p.error("no plan file configured (settings.PLAN_FILE is unset) and "
                "--plan-file not given")
    try:
        watch(args.pi, path, args.heading, args.interval, args.dry_run)
    except KeyboardInterrupt:
        print("\nstopping.")
        if not args.dry_run:
            try:
                _post(args.pi, "/stop")
                print("motors stopped.")
            except Exception:
                print("could not reach the bridge to send a final stop -- check the rover.")


if __name__ == "__main__":
    main()
