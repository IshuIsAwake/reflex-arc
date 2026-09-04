r"""Write a training set of (map, goal) -> route, as text.

    ..\.venv\Scripts\python.exe game\make_dataset.py --n 500 --out runs\train.txt

Fog is lifted for every sample, so the whole arena is on the map and the objective is
somewhere the rover can see. That is the point of a training set and the opposite of
how the game is played -- driving is the only thing that lifts fog there, and a planner
trained on full maps has never met the situation the game actually poses. Which is
fine, and worth knowing: this teaches routing, not exploration.

Each sample is exactly what gemma reads at play time -- `sight.grid`, the same
function, so the training text and the live prompt cannot drift into two dialects --
followed by the goal and the actions A* produced. Self-contained: the map is repeated
per sample rather than hoisted into a header, because a sample that needs a header to
be understood is a sample you can only shuffle by hand.

One arena per file. `config.ARENA` is the only map here; when there are more, one file
each, and the map inside each sample already says which.

Nothing drives. `nav.plan` is pure and `nav.route_actions` is arithmetic, so this is
fast enough to make thousands and cheap enough to throw away.
"""

import argparse
import os
import random
import sys

import nav
import settings as S
import sight
from world import DIRS, SOLID, World

HEADING_NAMES = ("N", "E", "S", "W")


def open_cells(area):
    """Every cell a rover could stand on. The base pad is solid, so it is not one."""
    return [(x, y) for y in range(area.h) for x in range(area.w)
            if area.at(x, y) not in SOLID]


def sample(world, cells, rng, min_steps):
    """One (start, heading, goal, actions) or None if the draw was no good.

    Returns None rather than retrying inside, so the caller counts attempts and a
    map with almost nothing reachable ends the run instead of spinning in here.
    """
    start, goal = rng.choice(cells), rng.choice(cells)
    if start == goal:
        return None
    world.pos = start
    path = nav.plan(world.here, start, goal)
    if path is None or len(path) - 1 < min_steps:
        return None
    heading = rng.randrange(4)
    actions, _ = nav.route_actions(path, heading)
    # Every sample is replayed before it is written. A dataset is the one artefact
    # nobody checks by eye, and a route that does not reach its own goal teaches the
    # model to miss -- so the file is correct by construction or it does not exist.
    assert _replays(start, heading, actions) == path[-1], (start, goal, actions)
    return start, heading, goal, actions


def _replays(start, heading, actions):
    """Where these actions actually leave a rover starting at `start`."""
    pos = start
    for a in actions:
        if a == "LEFT":
            heading = (heading - 1) % 4
        elif a == "RIGHT":
            heading = (heading + 1) % 4
        else:
            # BACKWARD is the same vector negated, and leaves the heading alone.
            sign = -1 if a == "BACKWARD" else 1
            pos = (pos[0] + sign * DIRS[heading][0],
                   pos[1] + sign * DIRS[heading][1])
    return pos


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=200, help="samples to write")
    p.add_argument("--out", default=os.path.join("runs", "train.txt"))
    p.add_argument("--seed", type=int, default=0, help="same seed, same file")
    p.add_argument("--min-steps", type=int, default=3,
                   help="skip routes shorter than this -- a one-step answer teaches "
                        "nothing and there are a great many of them")
    args = p.parse_args(argv)

    rng = random.Random(args.seed)
    world = World()
    area = world.here
    area.reveal_all()
    cells = open_cells(area)
    if len(cells) < 2:
        print("arena has nowhere to drive", file=sys.stderr)
        return 1

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    written = attempts = 0
    # Ten draws a sample before giving up, so a nearly-impassable arena stops rather
    # than looping forever looking for the route it does not have.
    budget = args.n * 10
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# reflex-arc plan dataset -- arena {area.name!r}, fog lifted\n"
                 f"# {args.n} samples, seed {args.seed}, min {args.min_steps} steps\n"
                 f"# each sample: MAP, then GOAL x,y, then ACTIONS, then a blank line\n"
                 f"# actions are FORWARD / BACKWARD / LEFT / RIGHT; '@' is the start\n\n")
        while written < args.n and attempts < budget:
            attempts += 1
            s = sample(world, cells, rng, args.min_steps)
            if s is None:
                continue
            start, heading, goal, actions = s
            fh.write(f"SAMPLE {written}\n"
                     f"START {start[0]},{start[1]} FACING {HEADING_NAMES[heading]}\n"
                     f"GOAL {goal[0]},{goal[1]}\n"
                     f"{sight.grid(world)}\n"
                     f"ACTIONS {' '.join(actions)}\n\n")
            written += 1

    print(f"{written} samples in {attempts} draws -> {out} "
          f"({os.path.getsize(out) / 1024:.0f} KB)")
    if written < args.n:
        print(f"short by {args.n - written}: ran out of draws. Lower --min-steps or "
              f"raise --n's budget.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
