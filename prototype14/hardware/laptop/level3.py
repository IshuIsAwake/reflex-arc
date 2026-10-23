"""Level 3: the simulation's mission, with every leg it drives sent to the real rover.

    python level3.py --rover 10.7.12.41
    python level3.py --rover 127.0.0.1 --arena 50 --sols 3   anything after --rover goes to the game

The game in ../../game runs as usual, with the rover pause on (--pause key). Each leg it
drives goes to the rover over the link, and the game waits at the pause until the rover
reports the leg done; then this presses SPACE for you. With no LiDAR the simulation is the
truth, and the rover replays what the game already drove.

If a leg is stopped from the pad, or the link fails, nothing is pressed: the screen says
where to put the rover (counted from home), and you press SPACE once it is there.

Before starting: the rover on the home spot (the landing cell), facing north.
"""

import argparse
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROTOTYPE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(PROTOTYPE, "game"))  # the game's modules

import dashboard  # noqa: E402
import nav  # noqa: E402
from link import LinkError, RoverLink, RoverStopped  # noqa: E402

STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}  # the game's frame and the rover's
DRIVING = "the rover says when it has stopped"  # the pause's hint while a leg drives


def show(m):
    """One line per step from the rover."""
    print(f"[rover]   {m['cmd']} -> {m['pose']}")


def leg_end(pose, dirs):
    """Where a leg leaves the rover, from the pose it started in: the cell, facing the way
    its last move went."""
    x = pose["x"]
    y = pose["y"]
    for d in dirs:
        x += STEP[d][0]
        y += STEP[d][1]
    return x, y, dirs[-1]


def from_home(x, y, cell_m=None):
    """A rover cell as a person finds it on the floor: how far east or west, and north or
    south, of the home spot."""
    parts = []
    for n, ahead, back in ((x, "east", "west"), (-y, "north", "south")):
        if not n:
            continue
        far = f"{abs(n)} cell"
        if abs(n) != 1:
            far += "s"
        if cell_m:
            far += f" ({abs(n) * cell_m * 100:.0f} cm)"
        if n > 0:
            parts.append(f"{far} {ahead}")
        else:
            parts.append(f"{far} {back}")
    if not parts:
        return "on home"
    return " and ".join(parts) + " of home"


class RoverLegs:
    """Sends each leg the game drives to the rover, in order, from one worker thread, so a
    leg never reaches a rover that is still driving the last one. The game calls
    leg_started, leg_finished and is_driving through nav's hooks."""

    def __init__(self, rover, press_space, start=None, cell_m=None):
        self.rover = rover
        self.press_space = press_space  # ends the game's pause
        self.cell_m = cell_m
        self.pose = start or {"x": 0, "y": 0, "heading": "N"}  # the rover's pose before the next leg
        self.owed = None  # where a person was told to put the rover, sent once they have
        self.driving = 0  # legs queued or being driven
        self.jobs = queue.Queue()
        threading.Thread(target=self.work, daemon=True).start()

    def leg_started(self, world, dirs):
        self.driving += 1  # before the game's pause starts reading keys
        dashboard.ROVER_HINT = DRIVING
        self.jobs.put(("leg", world, list(dirs)))

    def leg_finished(self, world):
        # The pause is over, so a person has put the rover right. The pose goes through
        # the same queue as the legs, so it never reaches the rover in the middle of one.
        if self.owed:
            self.jobs.put(("pose", world, self.owed))
            self.owed = None

    def is_driving(self):
        return self.driving > 0

    def work(self):
        while True:
            kind, world, item = self.jobs.get()
            if kind == "pose":
                self.tell_pose(item)
            else:
                self.drive(world, item)

    def tell_pose(self, pose):
        try:
            self.pose = self.rover.set_pose(*pose)["pose"]
            print(f"[rover] told it is on cell {self.pose}")
        except (LinkError, OSError) as e:
            print(f"[rover] could not tell the rover its cell: {e}")

    def drive(self, world, dirs):
        line = f"[rover] leg: {' '.join(dirs)}"
        if self.jobs.qsize():
            line += f"   ({self.jobs.qsize()} more queued -- the sim is ahead)"
        print(line)
        try:
            self.pose = self.rover.drive(dirs, on_step=show)
        except RoverStopped as e:
            print(f"[rover] STOPPED: {e}")
            self.hand_back(dirs)
            return
        except (LinkError, OSError) as e:
            print(f"[rover] FAILED: {e}")
            self.hand_back(dirs)
            return
        print(f"[rover] leg done, rover believes {self.pose}")
        self.driving -= 1
        self.release(world, dirs)

    def release(self, world, dirs):
        """Press SPACE, but only while the game is still waiting on this leg: one pressed
        after the game moved on would land in the next pause, or in the chat. The game
        marks its pause just after the leg starts, so a short leg can beat it."""
        for _ in range(20):
            if world.awaiting_rover == dirs:
                self.press_space()
                return
            time.sleep(0.05)
        print("[rover] (the game had already moved on -- no SPACE sent)")

    def hand_back(self, dirs):
        """The leg did not finish: the rover is a person's to put right, where the leg ends."""
        self.owed = leg_end(self.pose, dirs)
        x, y, heading = self.owed
        where = f"put it {from_home(x, y, self.cell_m)}, facing {heading}"
        print(f"[rover] the rover is yours: {where}, then press SPACE in the game")
        dashboard.ROVER_HINT = f"STOPPED: {where}, then SPACE"
        self.driving = 0


def main():
    ap = argparse.ArgumentParser(description="Level 3: the simulation drives the real rover")
    ap.add_argument("--rover", required=True, help="the Pi's address, or 127.0.0.1 for a fake")
    ap.add_argument("--no-reset", action="store_true",
                    help="keep the rover's heading from last time instead of 'facing north now'")
    ours, theirs = ap.parse_known_args()

    rover = RoverLink(ours.rover, timeout=300)
    try:
        hi = rover.hello()
        if ours.no_reset:
            start = hi["pose"]
        else:
            start = rover.reset("N")["pose"]
    except OSError as e:
        sys.exit(f"cannot reach the rover at {ours.rover}:5005 ({e}). Is server.py running?")
    print(f"rover connected ({'fake' if hi['fake'] else 'REAL'} motors).")

    # From the prototype's folder, so `--replay runs/<stamp>` means what it means for the game.
    os.chdir(PROTOTYPE)
    import pygame
    import main as game

    def press_space():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0,
                                             unicode=" ", scancode=0, rover=True))

    legs = RoverLegs(rover, press_space, start, hi.get("cell_m"))
    nav.leg_started = legs.leg_started
    nav.leg_finished = legs.leg_finished
    nav.rover_driving = legs.is_driving

    if "--pause" not in theirs:
        theirs += ["--pause", "key"]
    if "--arena" not in theirs:
        theirs += ["--arena", "30"]  # 3 m of floor; the game alone opens on the 50
    sys.argv = ["game/main.py"] + theirs
    try:
        game.main()
    finally:
        rover.stop()
        rover.close()


if __name__ == "__main__":
    main()
