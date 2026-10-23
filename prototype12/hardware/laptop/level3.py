"""Level 3 -- prototype 10d's mission, with every leg it drives sent to the real rover.

    python level3.py --rover 10.7.12.41
    python level3.py --rover 127.0.0.1 --arena 50 --sols 3      anything after --rover goes to 10d

The simulation is prototype12's own copy of 10d, in `prototype12/game/` (see
`prototype12/COPIED_FROM.md`), and its files are not changed. This imports it and wraps, in
memory, `nav.publish` -- where 10d hands a driven leg to the robot as N/E/S/W lines --
and `pygame.event.get`, for the SPACE guard below. When a leg comes
through, it goes to the rover over the link, and 10d is held at its rover pause
(`--pause key`, forced on here) until the rover reports the leg finished. Then this
presses SPACE for you. If the link fails, nothing is pressed: the HUD keeps waiting,
you put the rover where the screen says it should be, and press SPACE yourself.

With no LiDAR the simulation is the truth: the map, the fog and the battery all come
from 10d, and the rover replays what 10d already drove. Nothing measures where the
floor disagrees with the screen; that is Level 4, deferred.

A stop from the control pad ends the leg there and hands the rover to you, the same as
a failed link: put it where the screen shows it, facing the way the leg ended, and
press SPACE. The rover is then told it is there.

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
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "game"))   # prototype12/game, the copy
sys.path.insert(0, HERE)

from link import LinkError, RoverLink, RoverStopped  # noqa: E402

STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}   # 10d's frame and the rover's


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
    """One line per step from the rover."""
    print(f"[rover]   {m['cmd']} -> {m['pose']}")


def leg_end(pose, dirs):
    """Where a leg leaves the rover, from the pose it started in: the cell, facing the
    way its last move went."""
    x, y = pose["x"], pose["y"]
    for d in dirs:
        x, y = x + STEP[d][0], y + STEP[d][1]
    return x, y, dirs[-1]


def install(nav, rover, finished, still_waiting=lambda world, dirs: True, guard=None,
            start=None):
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

    A leg that does not finish -- stopped, or the link failed -- leaves the rover to a
    person. When they release 10d's pause, the rover is told it stands where that leg
    ends (`start` is the rover's pose before the first leg). Returns a function that
    undoes the wrap.
    """
    original = nav.publish
    legs = queue.Queue()
    guard = guard or Guard()
    at = [start or {"x": 0, "y": 0, "heading": "N"}]   # the rover's pose before the next leg
    owed = [None]                 # the pose to tell it once a person has put it right

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
                    at[0] = rover.set_pose(*item)["pose"]
                    print(f"[rover] told it is on cell {at[0]}")
                except (LinkError, OSError) as e:
                    print(f"[rover] could not tell the rover its cell: {e}")
                continue
            world, dirs = item
            ok = False
            print(f"[rover] leg: {' '.join(dirs)}"
                  + (f"   ({legs.qsize()} more queued -- the sim is ahead)" if legs.qsize() else ""))
            try:
                at[0] = rover.drive(dirs, on_step=show)
                print(f"[rover] leg done, rover believes {at[0]}")
                ok = True
                guard.driving -= 1
                release(world, dirs)
            except RoverStopped as e:
                print(f"[rover] STOPPED: {e}")
            except (LinkError, OSError) as e:
                print(f"[rover] FAILED: {e}")
            except Exception as e:        # a bug here must say so, not kill the leg thread quietly
                print(f"[rover] FAILED (a bug in level3.py): {e!r}")
            finally:
                if not ok:
                    owed[0] = leg_end(at[0], dirs)
                    print(f"[rover] the rover is yours: put it where the screen shows it, facing "
                          f"{dirs[-1]}, then press SPACE in the game")
                    guard.driving = 0     # hand control back to the person

    threading.Thread(target=worker, daemon=True).start()

    def publish(world, dirs):
        original(world, dirs)
        if not nav.live_file(world):
            return
        if dirs:
            guard.driving += 1            # before 10d's pause starts reading keys
            legs.put(("leg", (world, list(dirs))))
        elif owed[0]:
            # The pause is over and a person put the rover right; it goes through the same
            # queue as the legs, so it can never reach the rover in the middle of one.
            legs.put(("pose", owed[0]))
            owed[0] = None

    nav.publish = publish

    def restore():
        nav.publish = original
    return restore


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True, help="the Pi's address, or 127.0.0.1 for a fake")
    ap.add_argument("--no-reset", action="store_true",
                    help="keep the rover's heading from last time instead of 'facing north now'")
    ours, theirs = ap.parse_known_args()

    rover = RoverLink(ours.rover, timeout=300)
    try:
        hi = rover.hello()
        start = hi["pose"] if ours.no_reset else rover.reset("N")["pose"]
    except OSError as e:
        sys.exit(f"cannot reach the rover at {ours.rover}:5005 ({e}). Is server.py running?")
    print(f"rover connected ({'fake' if hi['fake'] else 'REAL'} motors).")

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
            guard=guard, start=start)
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
