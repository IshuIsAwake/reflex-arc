"""Driving: A* over the map the rover knows, not the true arena. Fog is assumed to be
open ground, so a plan is a guess and driving it finds out. Every read of the grid goes
through known(), which hides what hasn't been seen (test_nav checks this).

After each leg is driven in the simulation, the cells that worked are written to the route
file as N/E/S/W, one a line. That file is what the real rover drives."""

import heapq
import os
import tempfile
import time

import settings as S
from world import SOLID, THINGS

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
# Clockwise from north, matching HEADING_NAMES. 0=N 1=E 2=S 3=W.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
HEADING_NAMES = ("N", "E", "S", "W")
# The whole alphabet of the route file.
MOVES = HEADING_NAMES
FAR = 1 << 30

# The prototype folder, so a relative PLAN_FILE means the same from anywhere.
PLAN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def known(area, x, y):
    """What the rover knows about a cell: its character if seen, None if fogged, "#" off the
    edge. An interest not yet found reads as the ground it sits on. The only grid read here."""
    if not (0 <= x < area.w and 0 <= y < area.h):
        return "#"
    if not area.visible(x, y):
        return None
    i = area.interests.get((x, y))
    return "." if i and not i.found else area.at(x, y)


def drive_seconds(steps):
    """About how long a drive of `steps` takes on the day's clock: drawn, then settled."""
    if not S.ANIMATE or not steps:
        return 0.0
    return steps * (S.ANIM_STEP + S.ANIM_PLAN) / S.ANIM_SPEED + S.SETTLE_SECONDS


def _around(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBOURS]


def _targets(area, goal, avoid):
    """Where a plan may end. A solid thing (the pad) means "get next to it". Rock already
    seen is refused; a fogged cell is a guess, and driving at it is how the map fills in."""
    ch = known(area, *goal)
    if ch is None or ch not in THINGS:
        return {goal}

    out = set()
    for n in _around(goal):
        if n in avoid:
            continue
        c = known(area, *n)
        if c is None or c not in SOLID:
            out.add(n)
    return out


def with_storm(area, avoid):
    """`avoid` plus today's storm, so the storm is avoided like any avoided cell."""
    return frozenset(avoid) | area.storm_cells


def _passable(area, cell, avoid):
    """Fogged cells are passable; `avoid` and seen solid cells are not."""
    if cell in avoid:
        return False
    ch = known(area, *cell)
    if ch is None:
        return True
    return ch not in SOLID


def plan(area, start, goal, avoid=frozenset()):
    """The shortest route over the known map, as a list of cells from `start`, or None if
    there is none even with every fogged cell open. A* with Manhattan distance as the
    estimate; ties go to the cell nearer the goal."""
    avoid = frozenset(avoid) - {start}
    targets = _targets(area, goal, avoid)
    if not targets:
        return None
    if start in targets:
        return [start]

    def h(c):
        return min(abs(c[0] - t[0]) + abs(c[1] - t[1]) for t in targets)

    heap = [(h(start), h(start), start)]
    came, best, closed = {start: None}, {start: 0}, set()

    while heap:
        _, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        if cur in targets:
            return _trace(came, cur)

        g = best[cur] + 1
        for n in _around(cur):
            if n in closed or not _passable(area, n, avoid):
                continue
            if g < best.get(n, FAR):
                best[n], came[n] = g, cur
                heapq.heappush(heap, (g + h(n), h(n), n))
    return None


def _trace(came, cur):
    out = [cur]
    while came[cur] is not None:
        cur = came[cur]
        out.append(cur)
    out.reverse()
    return out


def route_actions(path):
    """A path from `plan` as the route file's directions: one of N/E/S/W a step. The rover's
    heading plays no part; turning is the driver's job. A step that isn't one cell N/E/S/W raises."""
    out = []
    for a, b in zip(path, path[1:]):
        step = (b[0] - a[0], b[1] - a[1])
        if step not in DIRS:
            raise ValueError(f"not a single orthogonal step: {_c(a)} -> {_c(b)}")
        out.append(HEADING_NAMES[DIRS.index(step)])
    return out


def _c(cell):
    return f"({cell[0]},{cell[1]})"


class Result:
    """What a goto comes back with. str() is the line the model reads and the console prints.
    `at` is where it ended or the rock it hit; `stopped` appears only when those differ;
    `beside` means the target was solid and this is as close as it gets; `new` is how many
    cells the drive revealed, None for a call that never drove."""

    GOOD = {"DONE"}

    def __init__(self, code, steps=0, at=None, stopped=None, beside=None, walls=(),
                 new=None, planned=None, closed=False):
        self.code = code
        self.steps = steps
        self.at = at
        self.stopped = stopped
        self.beside = beside
        self.walls = list(walls)
        self.new = new
        # The route's length, for a call that planned one.
        self.planned = planned
        # OUT_OF_TIME because the sol was closed with time left, not because it ran out.
        self.closed = closed

    @property
    def tone(self):
        return "good" if self.code in self.GOOD else "bad"

    def __str__(self):
        bits = []
        if self.at:
            bits.append(f"at={_c(self.at)}")
        if self.beside:
            bits.append(f"beside={_c(self.beside)}")
        if self.stopped:
            bits.append(f"stopped={_c(self.stopped)}")
        if self.planned is not None:
            bits.append(f"route={self.planned}")
        bits.append(f"steps={self.steps}")
        # Printed even when 0: a drive that revealed nothing is worth saying.
        if self.new is not None:
            bits.append(f"new={self.new}")
        if self.walls:
            bits.append("rock=[" + ", ".join(_c(w) for w in self.walls) + "]")
        return f"{self.code}({', '.join(bits)})"

    @property
    def advice(self):
        """The answers the model reads backwards, said again in words: arriving beside a solid
        target, a zero-step goto, and a drive that revealed nothing."""
        if self.beside:
            return (f"{_c(self.beside)} is solid, so stopping beside it IS "
                    f"arriving. Do not ask again.")
        if self.code == "OUT_OF_TIME" and self.closed:
            return ("the sol is already over, so the rover did not move. Unless it is "
                    "beside the pad, it is stranded tonight.")
        if self.code == "OUT_OF_TIME":
            return ("the sol ran out on the way, so the rover stopped where it stands. "
                    "Unless that is beside the pad, it is stranded tonight.")
        if self.code == "BATTERY_FLAT":
            return ("the battery is flat, so the rover stopped where it stands and the "
                    "day is over. Only the pad recharges it, and only if the rover is "
                    "beside it.")
        if self.code == "STORM_BLOCKED":
            return (f"the dust storm is across the only way there. It is not rock and "
                    f"it is not your doing: it blows out at the end of the sol and the "
                    f"ground under it is fine. Go somewhere else today, or wait it out.")
        if self.code == "DONE" and not self.steps:
            return "you were already standing there. Nothing moved, nothing spent."
        if self.steps and self.new == 0:
            return (f"those {self.steps} steps were spent over ground already on your "
                    f"map and revealed nothing new. Aim at cells showing ?.")
        return ""


def plan_file():
    """Absolute path of the live route file, or None when it is switched off."""
    if not S.PLAN_FILE:
        return None
    if os.path.isabs(S.PLAN_FILE):
        return S.PLAN_FILE
    return os.path.join(PLAN_ROOT, S.PLAN_FILE)


def _replace(tmp, out, tries=10, wait=0.05):
    """os.replace, retried for half a second: on Windows it is refused while anything else
    has the file open (OneDrive, an editor)."""
    for n in range(tries):
        try:
            os.replace(tmp, out)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(wait)


def write_plan(out, dirs):
    """Write one driven leg, one of N/E/S/W a line, nothing else. Written to a temp file and
    renamed over the target, so a reader never sees half a file. Empty `dirs` empties it."""
    # No newline on an empty file, or a reader would get one blank move.
    body = "".join(f"{d}\n" for d in dirs)

    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(out), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        _replace(tmp, out)
    except BaseException:
        os.path.exists(tmp) and os.remove(tmp)
        raise
    return out


def clear_plan(world):
    """Empty the route file. Done at the start of a run and after every leg."""
    publish(world, [])


def live_file(world):
    """The route file this run writes, or None. Only a live run writes one (world.recorder
    is None in tests), and None also means there is no rover to wait for."""
    out = plan_file()
    return out if out and world.recorder else None


def publish(world, dirs):
    """Write one leg's directions to the live route file, if there is one."""
    out = live_file(world)
    if out:
        write_plan(out, dirs)


def _await_rover(world, dirs):
    """Wait until the rover has driven `dirs`. Does nothing here: main.py replaces it with
    the SPACE pause, and the tests with a stand-in."""
    return


def _log(world, area_name, start, goal, planned, result):
    """Record what the plan promised against what the drive cost."""
    world.nav_log.append({"day": world.day, "area": area_name, "from": start,
                          "to": goal, "planned": planned, "steps": result.steps,
                          "code": result.code, "new": result.new})
    world.record("nav", area=area_name, start=start, goal=goal, planned=planned,
                 steps=result.steps, code=result.code, new=result.new)
    return result


def goto(world, x, y, avoid=None):
    """Drive to (x, y) over the known map. Returns a Result.

    `avoid=None` dodges only known rock; a list of cells dodges those too, this trip only;
    "auto" dodges every marked cell (visited destinations only).

    The drive stops at the first refused step, reveals that rock, and replans, up to
    NAV_REPLANS times. Each leg driven is handed to the rover before any replan."""
    area, area_name, goal, start = world.here, world.area, (x, y), world.pos

    # Every cell actually driven over. The world holds it by reference, so it grows as the drive does.
    walk = [start]
    world.last_walk = (area_name, walk)

    # What the drive did, in order, for anim.py to draw afterwards.
    reel = [("start", start)]

    if avoid == "auto":
        if goal not in area.visited:
            world.last_path = (area_name, [])
            return _log(world, area_name, start, goal, None,
                        Result("NOT_VISITED", at=start, new=0))
        avoid = frozenset(area.marks)
    else:
        avoid = frozenset(avoid or ())
    asked, avoid = avoid, with_storm(area, avoid)

    path = plan(area, start, goal, avoid)
    if path is None:
        # No route: say whether the storm or the avoid list is what sealed it.
        code = "UNREACHABLE"
        if area.storm and plan(area, start, goal, asked):
            code = "STORM_BLOCKED"
        elif asked and plan(area, start, goal, frozenset()):
            code = "UNREACHABLE(avoid)"
        world.last_path = (area_name, [])
        return _log(world, area_name, start, goal, None, Result(code, at=start, new=0))

    planned = len(path) - 1
    world.last_path = (area_name, list(path))
    reel.append(("plan", list(path)))

    walls, steps, replans = [], 0, S.NAV_REPLANS
    # What the drive revealed. world.revealed holds one move's worth, so it is gathered as we go.
    gained = set()
    # Where in `walk` the current leg started. The rover is handed one leg at a time.
    leg_start = 0

    def hand_over():
        """Hand the leg just driven to the rover and wait, then empty the file. Skipped for a leg
        that didn't move, and when there is no route file."""
        cells = walk[leg_start:]
        if len(cells) < 2 or not live_file(world):
            return
        dirs = route_actions(cells)
        publish(world, dirs)
        _await_rover(world, dirs)
        publish(world, [])

    def done(code, **kw):
        kw.setdefault("at", world.pos)
        kw.setdefault("new", len(gained))
        if code == "DONE" and world.pos != goal:
            # The target was solid, so this is as close as it gets. Say so.
            kw["beside"] = goal
        world.play(reel)
        hand_over()
        return _log(world, area_name, start, goal, planned,
                    Result(code, steps=steps, walls=walls, **kw))

    while True:
        wall = None
        leg_start = len(walk) - 1
        for cell in path[1:]:
            # Checked before the move: world.move refuses a flat battery the same way it refuses
            # rock, and the check below would log it as rock.
            if world.battery <= 0:
                return done("BATTERY_FLAT")
            if world.day_over:
                return done("OUT_OF_TIME", closed=world.time_left > 0)

            was_pos, was_steps = world.pos, world.steps
            world.move(cell[0] - was_pos[0], cell[1] - was_pos[1])

            # A refused move is one that wasn't charged a step.
            if world.steps == was_steps:
                wall = cell
                # Bumping into rock reveals it, or the replan would return the same path.
                gained |= area.reveal_cells({cell})
                # An interest found a step ago stops the plan too, and it is not rock.
                if cell not in walls and known(area, *cell) == "#":
                    walls.append(cell)
                reel.append(("block", cell))
                break

            steps += 1
            walk.append(cell)
            # Handed to the reel, so the fog opens in step with the drawn rover.
            gained |= world.revealed
            reel.append(("step", (cell, sorted(world.revealed))))
        else:
            return done("DONE")

        # The leg ended on rock. The rover drives what worked before anything is replanned.
        hand_over()

        if replans <= 0:
            break
        replans -= 1
        path = plan(area, world.pos, goal, avoid)
        if path is None:
            break  # the model calls goto again from wherever it is
        world.last_path = (area_name, list(path))
        reel.append(("plan", list(path)))

    # `done` hands over too, and this leg has already gone, so make the next slice empty.
    leg_start = len(walk) - 1
    return done("BLOCKED", at=wall, stopped=world.pos)


def price(world, x, y, avoid=None):
    """What a trip would cost in steps, or None if there is no route. A floor: rock under
    the fog can make the real drive longer. Moves nothing."""
    area = world.here
    avoid = frozenset(area.marks) if avoid == "auto" else frozenset(avoid or ())
    # The same storm the drive would meet.
    avoid = with_storm(area, avoid)
    path = plan(area, world.pos, (x, y), avoid)
    world.last_path = (world.area, list(path) if path else [])
    world.last_walk = (world.area, [])  # priced, not driven
    # The priced route is drawn in blue, never in a drive's yellow.
    if path:
        world.play([("start", world.pos), ("probe", list(path))])

    steps = None if path is None else len(path) - 1
    # Logged even though it moves nothing.
    _log(world, world.area, world.pos, (x, y), steps,
         Result("UNREACHABLE" if steps is None else "DISTANCE"))
    return steps


def home_steps(world, storm=True):
    """Steps back to beside the pad over the known map: 0 when already there, None if no
    route. Breadth-first. `storm=False` leaves today's storm out, to ask whether the rover can
    ever get home."""
    if world.docked:
        return 0
    area, pad = world.here, world.pad
    avoid = with_storm(area, ()) if storm else frozenset()
    seen, frontier, steps = {world.pos}, [world.pos], 0
    while frontier:
        steps += 1
        nxt = []
        for cell in frontier:
            for n in _around(cell):
                if n in seen or not _passable(area, n, avoid):
                    continue
                if set(_around(n)) & pad:
                    return steps
                seen.add(n)
                nxt.append(n)
        frontier = nxt
    return None


