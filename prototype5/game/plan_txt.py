r"""Plan a route and write it out, without driving it.

    .venv\Scripts\python.exe game\plan_txt.py --to 12 4

A* and nothing else: no window, no policy, no torch, and the rover does not move.
`nav.plan` is a pure function over the map and this only asks it a question.

The format and the writing both live in `nav.py` -- `write_plan` is the same function
a live `goto` calls on every replan, so a file made here and a file made mid-run cannot
drift into two dialects. This is the offline door to it.

By default the route is planned over the map the rover *knows*, which on a fresh
landing is the landing disc and a great deal of fog. Fog is assumed drivable
(`nav.py`), so such a plan is a hypothesis -- the same one `goto` drives and replans
when it turns out wrong. `--survey` plans over the whole arena instead, for the route
you would get if nothing were hidden. The two differ, and that gap is what the fog is
for.
"""

import argparse
import os
import sys

import config as C
import nav
from world import World

HEADINGS = {"n": 0, "e": 1, "s": 2, "w": 3}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--to", nargs=2, type=int, metavar=("X", "Y"), required=True)
    p.add_argument("--from", dest="start", nargs=2, type=int, metavar=("X", "Y"),
                   default=list(C.SPAWN))
    p.add_argument("--heading", choices=tuple(HEADINGS), default="n",
                   help="which way the rover is pointing to begin with")
    p.add_argument("--survey", action="store_true",
                   help="plan over the whole arena instead of the fogged map")
    p.add_argument("--out", default=nav.plan_file() or "runs/plan.txt",
                   help="default is the live route file the game writes")
    args = p.parse_args(argv)

    world = World()
    world.pos = start = tuple(args.start)
    if world.here.blocked(*start):
        p.error(f"({start[0]},{start[1]}) is solid -- the rover cannot start there")
    if args.survey:
        world.here.reveal_all()
    else:
        world.here.reveal(*start)   # --from can put the rover anywhere; it sees where

    goal = tuple(args.to)
    world.heading = HEADINGS[args.heading]
    cells = nav.plan(world.here, start, goal)
    if cells is None:
        # The file is emptied rather than left alone, for the same reason `goto` empties
        # it: a stale route outlives the plan that made it and gets driven.
        nav.write_plan(args.out, [], goal)
        print(f"UNREACHABLE ({goal[0]},{goal[1]}) -- no route even assuming every "
              f"fogged cell is drivable. {args.out} emptied.", file=sys.stderr)
        return 1

    actions, _ = nav.route_actions(cells, world.heading)
    out = nav.write_plan(args.out, [(cells, start, world.heading, None)], goal)
    print(f"{len(cells) - 1} steps, {len(actions)} actions -> {out}")
    if cells[-1] != goal:
        print(f"note: ({goal[0]},{goal[1]}) is solid, so the plan stops beside it at "
              f"({cells[-1][0]},{cells[-1][1]}). That IS arriving.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
