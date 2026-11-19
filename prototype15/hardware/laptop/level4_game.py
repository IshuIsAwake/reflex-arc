"""Level 4: Level 3 with the LiDAR checking every straight run and every turn.

    python level4_game.py --rover nith.local --sols 1

Start both servers on the Pi first: server.py (the motors) and lidar_server.py. Put the
rover on its home spot, facing north, with nothing moving near it: the LiDAR records the
room from there, and every check is measured against it.

With no LiDAR it says why and runs as Level 3 does. With one, each leg goes through
checked_legs.py: the rover is checked after every piece, and when it ends up in another
cell the game's rover is moved there and plans again. The game's own options go on the
end, as for level3_game.py."""

import argparse
import os
import sys

import launch
import level3_game  # also puts ../../game on the path, for nav and main below
import lidar_link
import nav
from checked_legs import CheckedLegs
from link import RoverLink


def main():
    ap = argparse.ArgumentParser(description="Level 4: Level 3, checked by the LiDAR")
    ap.add_argument("--rover", required=True, help="the Pi's address, e.g. nith.local")
    ours, theirs = ap.parse_known_args()

    lidar, note = lidar_link.connect(ours.rover)
    if lidar is None:
        print(f"No LiDAR: {note}")
        print("Running Level 3 as before.")
        level3_game.main()
        return
    print(f"LiDAR found: {note}")

    rover = RoverLink(ours.rover, timeout=300)
    try:
        hi = rover.hello()
        start = rover.reset("N")["pose"]
    except OSError as e:
        sys.exit(f"cannot reach the rover at {ours.rover}:5005 ({e}). Is server.py running?")
    print(f"rover connected ({'fake' if hi['fake'] else 'REAL'} motors).")
    print("recording the room from home...")
    print(f"home: {lidar.home()['points']} points")

    # From the prototype's folder, so `--replay runs/<stamp>` means what it means for the game.
    os.chdir(level3_game.PROTOTYPE)
    import pygame
    import main as game

    def press_space():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0,
                                             unicode=" ", scancode=0, rover=True))

    legs = CheckedLegs(rover, lidar, press_space, start, hi["cell_m"], hi["turn_s"])
    nav.leg_started = legs.leg_started
    nav.leg_finished = legs.leg_finished
    nav.rover_driving = legs.is_driving

    if "--pause" not in theirs:
        theirs += ["--pause", "key"]
    if "--arena" not in theirs:
        theirs += ["--arena", "30"]  # 3 m of floor at 0.1 m a cell
    sys.argv = ["game/main.py"] + theirs
    try:
        game.main()
    finally:
        rover.stop(wait=False)
        rover.close()
        lidar.close()


if __name__ == "__main__":
    launch.run(main)
