"""Level 3 -- prototype 10d's mission, with every leg it drives sent to the real rover.

    python level3.py --rover 10.7.12.41
    python level3.py --rover 127.0.0.1 --arena 50 --sols 3      anything after --rover goes to 10d

The simulation is prototype16's own copy of 10d, in `prototype16/game/` (see
`prototype16/COPIED_FROM.md`), and its files are not changed. This imports it and wraps, in
memory, `nav.publish` -- where 10d hands a driven leg to the robot as N/E/S/W lines --
and `pygame.event.get`, for the SPACE guard below. When a leg comes
through, it goes to the rover over the link, and 10d is held at its rover pause
(`--pause key`, forced on here) until the rover reports the leg finished. Then this
presses SPACE for you. If the link fails, nothing is pressed: the HUD keeps waiting,
you put the rover where the screen says it should be, and press SPACE yourself.

With no LiDAR the simulation is the truth: the map, the fog and the battery all come
from 10d, and the rover replays what 10d already drove. Where the floor disagrees
with the screen is the error Level 4 measures.

`--check` is Level 4: the rover checks every move with its LiDAR, and correct.py moves
the simulation's rover to the measured cell after every leg (`--no-correct` to only
report).

Before starting: rover on the cell that stands for 10d's landing cell, facing grid
north (up on 10d's screen).
"""

import argparse
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "game"))   # prototype16/game, the copy
sys.path.insert(0, HERE)

from link import LinkError, RoverLink, RoverStopped  # noqa: E402


class Guard:
    """While the rover is driving, a SPACE from the keyboard is dropped, so 10d's pause
    ends when the rover says so and not when a thumb does. 10d's HUD still reads "SPACE
    when it has stopped" -- that is its own text, written for a person standing in for
    the robot. Our SPACE carries `rover=True` and always gets through. After a FAILED
    leg the guard is off, so a person can put the rover right and release 10d by hand.
    """

    def __init__(self):
        self.driving = 0              # legs queued or being driven

    def filter(self, events):
        if not self.driving:
            return events
        keep = []
        for e in events:
            if e.type == KEYDOWN and e.key == K_SPACE and not getattr(e, "rover", False):
                print("[rover] (SPACE ignored -- the rover is still driving)")
                continue
            keep.append(e)
        return keep


KEYDOWN, K_SPACE = 768, 32           # pygame's values; set properly once pygame is imported


def show(m):
    """One line per step from the rover; with the LiDAR check, what it found."""
    line = (f"[rover]   {m['cmd']} -> {m['pose']}" if "cmd" in m
            else f"[rover]   (part-way) -> {m['pose']}")
    c = m.get("check")
    if c:
        line += f"   lidar {c['result']}"
        if c.get("manhattan"):
            line += f" (manhattan {c['manhattan']}, chebyshev {c['chebyshev']})"
        if c.get("fixes"):
            line += f", heading {c['heading_err_was']:+.0f} deg fixed in {c['fixes']} turn(s)"
        if c.get("heading_note"):
            line += f", heading not fixed: {c['heading_note']}"
    print(line)


def install(nav, rover, finished, still_waiting=lambda world, dirs: True, guard=None,
            check=False, correct=False):
    """Wrap `nav.publish` so every leg 10d hands over is also driven by `rover`, and
    `finished()` is called once the rover has done it. 10d calls `publish` with the
    leg, then waits at its rover pause, then calls it again with [] -- so the wait is
    the window the rover drives in.

    Legs go through one queue and one worker, in order. If 10d is let go early -- a
    SPACE typed by hand ends its pause too -- the next leg waits its turn instead of
    reaching a rover that is still driving and being refused, so every direction is
    still driven. `finished()` only fires while 10d is still waiting on that same leg
    (`still_waiting`); a SPACE posted after a hand-released pause would otherwise
    land in the next one, or in the chat.

    `correct=True` (Level 4, needs `check`) moves the simulation's rover to the cell
    the LiDAR measured after every leg -- correct.py. Returns a function that undoes
    every wrap.
    """
    original = nav.publish
    legs = queue.Queue()
    guard = guard or Guard()
    # Telling the rover its cell goes through the same queue as the legs, so it can never
    # reach the rover in the middle of one.
    fix = None
    if correct:
        from correct import Corrector
        fix = Corrector(nav, send_pose=lambda x, y, h: legs.put(("pose", (x, y, h))))

    def release(world, dirs):
        # 10d marks its pause just after `publish` returns; a short leg can beat it.
        for _ in range(20):
            if still_waiting(world, dirs):
                finished()
                return
            time.sleep(0.05)
        print("[rover] (10d had already moved on -- no SPACE sent)")

    def worker():
        while True:
            kind, item = legs.get()
            if kind == "pose":
                try:
                    print(f"[rover] told it is on cell {rover.set_pose(*item)['pose']}")
                except (LinkError, OSError) as e:
                    print(f"[rover] could not tell the rover its cell: {e}")
                continue
            world, dirs = item
            ok = False
            print(f"[rover] leg: {' '.join(dirs)}"
                  + (f"   ({legs.qsize()} more queued -- the sim is ahead)" if legs.qsize() else ""))
            try:
                pose = rover.drive(dirs, on_step=show, check=check)
                print(f"[rover] leg done, rover {'measured' if check else 'believes'} {pose}")
                if fix:
                    fix.leg_driven(pose)
                ok = True
                guard.driving -= 1
                release(world, dirs)
            except RoverStopped as e:
                if fix and e.result == "LOST":
                    # It knows where it is, just not where it was sent: the simulation is moved
                    # there and the model replans. Nobody needs to touch it.
                    print(f"[rover] STOPPED, 2+ cells from the plan: {e}\n"
                          f"[rover] the simulation is moved to where it really is")
                    fix.leg_driven(e.pose)
                    ok = True
                    guard.driving -= 1
                    release(world, dirs)
                    continue
                if fix:
                    fix.leg_unsure(e.pose)
                print(f"[rover] STOPPED BY ITS LIDAR CHECK: {e}\n"
                      f"[rover] put the rover where the screen shows it, then press SPACE in the game")
            except (LinkError, OSError) as e:
                print(f"[rover] FAILED: {e}\n"
                      f"[rover] put the rover where the screen shows it, then press SPACE in the game")
            except Exception as e:        # a bug here must say so, not kill the leg thread quietly
                print(f"[rover] FAILED (a bug in level3.py): {e!r}\n"
                      f"[rover] put the rover where the screen shows it, then press SPACE in the game")
            finally:
                if not ok:
                    guard.driving = 0     # hand control back to the person

    threading.Thread(target=worker, daemon=True).start()

    def publish(world, dirs):
        original(world, dirs)
        if not nav.live_file(world):
            return
        if dirs:
            if fix:
                fix.leg_handed(world, dirs)
            guard.driving += 1            # before 10d's pause starts reading keys
            legs.put(("leg", (world, list(dirs))))
        elif fix:
            fix.after_pause(world)        # the pause is over; 10d plans next, from here

    nav.publish = publish

    def restore():
        nav.publish = original
        if fix:
            fix.restore()
    return restore


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True, help="the Pi's address, or 127.0.0.1 for a fake")
    ap.add_argument("--no-reset", action="store_true",
                    help="keep the rover's heading from last time instead of 'facing north now'")
    ap.add_argument("--check", action="store_true",
                    help="Level 4: the rover checks every move with its LiDAR")
    ap.add_argument("--no-correct", action="store_true",
                    help="with --check: report what the LiDAR measured, but leave the "
                         "simulation's rover where the plan put it")
    ours, theirs = ap.parse_known_args()

    rover = RoverLink(ours.rover, timeout=300)
    try:
        hi = rover.hello()
        if ours.check and hi.get("can_check") != "yes":
            sys.exit(f"the rover cannot check with its LiDAR: {hi.get('can_check', 'old server')}")
        if not ours.no_reset:
            rover.reset("N")
    except OSError as e:
        sys.exit(f"cannot reach the rover at {ours.rover}:5005 ({e}). Is server.py running?")
    correct = ours.check and not ours.no_correct
    print(f"rover connected ({'fake' if hi['fake'] else 'REAL'} motors"
          f"{', LiDAR checks on' if ours.check else ''}"
          f"{', the simulation follows the LiDAR' if correct else ''}).")

    sys.path.insert(0, GAME)
    os.chdir(os.path.dirname(GAME))           # 10d's own working directory
    import pygame
    import nav
    import main as game

    global KEYDOWN, K_SPACE
    KEYDOWN, K_SPACE = pygame.KEYDOWN, pygame.K_SPACE

    def press_space():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0,
                                             unicode=" ", scancode=0, rover=True))

    # Every pygame.event.get() 10d makes -- its main loop and its rover pause -- goes
    # through the guard. 10d's code is not touched; the function it calls is wrapped.
    guard = Guard()
    real_get = pygame.event.get
    pygame.event.get = lambda *a, **k: guard.filter(real_get(*a, **k))

    # 10d sets `world.awaiting_rover` to the leg for exactly as long as it holds on it.
    install(nav, rover, press_space,
            still_waiting=lambda world, dirs: getattr(world, "awaiting_rover", None) == dirs,
            guard=guard, check=ours.check, correct=correct)
    if "--pause" not in theirs:
        theirs += ["--pause", "key"]
    sys.argv = ["game/main.py"] + theirs
    try:
        game.main()
    finally:
        rover.stop()
        rover.close()


if __name__ == "__main__":
    main()
