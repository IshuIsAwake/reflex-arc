"""goto -- A* over the map gemma has, not the map that exists.

Pure functions and one driver loop. No pygame, so the tests can import it.

Three rules make this A* rather than any other A*:

  * fogged cells are assumed to be floor, so a plan is a hypothesis and walking it
    is the experiment;
  * snake pits are invisible here by construction, not by special case;
  * `avoid` is impassable, never merely expensive.

`known()` below is the only place this module touches the grid. `Area.at` returns
ground truth whether or not the cell is fogged -- reading it without checking
`Area.visible` first makes the planner quietly omniscient, everything keeps working,
and nothing ever looks wrong. `test_nav.py` counts the reads in this file for that
reason, so there had better stay exactly one.

Spec and the decisions behind it: NAVIGATION.md.
"""

import heapq

import settings as S
from world import GATES, SOLID, THINGS

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
FAR = 1 << 30


def known(area, x, y):
    """What gemma knows about a cell: the character if it can see the cell, None if
    it is fogged, "#" off the edge of the area.

    The only read of the grid in this module. Keep it that way.
    """
    if not (0 <= x < area.w and 0 <= y < area.h):
        return "#"
    return area.at(x, y) if area.visible(x, y) else None


def _around(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBOURS]


def _targets(area, goal, avoid, opened):
    """Where a plan is allowed to end.

    A solid *thing* -- a terminal, a counter, a bag, the board -- means "get next to
    it", or `goto(30, 16)` at the tribe would be UNREACHABLE taken literally. A gate
    that has not been opened yet counts the same way: you stop beside it and press
    E, because gates never open by being walked into.

    **A known wall is not a thing and gets none of this.** It is `THINGS`, not
    `SOLID`. Asking to walk into a wall you can already see is a mistake, and the
    honest answer is UNREACHABLE. Answering `DONE(beside=...)` says you arrived
    somewhere you never went, and a caller that believes it has moved has nothing to
    correct: on 2026-08-26 the model spent four days stood beside the shop at nought
    coins re-issuing a move it had been told succeeded. Widening this back to `SOLID`
    is all it takes to bring that back, and two tests in `test_nav.py` are the whole
    of what stands in the way.

    A **fogged** cell that turns out to be a wall is the opposite case and stays
    exactly as it was -- that one is a hypothesis, and walking into it is how the
    map fills in. Only walls already seen are refused.
    """
    ch = known(area, *goal)
    if ch is None or not (ch in THINGS or (ch == "D" and goal not in opened)):
        return {goal}

    out = set()
    for n in _around(goal):
        if n in avoid:
            continue
        c = known(area, *n)
        if c is None or (c not in SOLID and c not in GATES):
            out.add(n)
    return out


def _passable(area, cell, avoid, targets):
    """Fogged cells are passable at cost 1, and that is the whole design. Treat fog
    as wall and gemma can never path into unexplored ground; treat it as truth and
    it is omniscient.
    """
    if cell in avoid:
        return False
    ch = known(area, *cell)
    if ch is None:
        return True
    if ch in SOLID:
        return False
    if ch in GATES:
        return cell in targets   # aimed at, never routed through
    return True


def plan(area, start, goal, avoid=frozenset(), opened=frozenset()):
    """Cheapest known route, as a list of cells beginning with `start`. None if no
    route exists even assuming every fogged cell is floor.

    A*: pop the cell with the smallest f = g + h, where g is the steps already spent
    reaching it and h is the Manhattan distance still to go. Manhattan can never
    overestimate on a four-way grid of unit steps, which is what makes the answer
    provably shortest rather than merely short. Ties break on the smaller h, so the
    search runs at the goal instead of fanning out around it.
    """
    avoid = frozenset(avoid) - {start}
    targets = _targets(area, goal, avoid, opened)
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
            if n in closed or not _passable(area, n, avoid, targets):
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


def _c(cell):
    return f"({cell[0]},{cell[1]})"


class Result:
    """What a goto comes back with.

    `str()` is exactly the line gemma reads and exactly the line the console prints,
    so there is one wording rather than two. `at` is what the call is about -- where
    you ended up, or the wall you hit. `stopped` appears only when those differ.
    Every result carries `steps`, because in gemma mode the day is made of them.

    `beside` says the target was solid and this is as close as anyone gets. Without
    it, arriving at the shop reads as `DONE(at=(10,15))` for a `goto(10,16)`, and a
    model reasonably concludes it has not arrived and asks again -- watched gemma do
    exactly that three times on 2026-08-25. It is set for things, never for walls,
    and `_targets` is what guarantees that.
    """

    GOOD = {"DONE", "LEFT_AREA"}

    def __init__(self, code, steps=0, at=None, stopped=None, area=None,
                 beside=None, walls=(), antidotes=()):
        self.code = code
        self.steps = steps
        self.at = at
        self.stopped = stopped
        self.area = area
        self.beside = beside
        self.walls = list(walls)
        self.antidotes = list(antidotes)

    @property
    def tone(self):
        return "good" if self.code in self.GOOD else "bad"

    def __str__(self):
        bits = []
        if self.area:
            bits.append(self.area)
        if self.at:
            bits.append(f"at={_c(self.at)}")
        if self.beside:
            bits.append(f"beside={_c(self.beside)}")
        if self.stopped:
            bits.append(f"stopped={_c(self.stopped)}")
        bits.append(f"steps={self.steps}")
        if self.walls:
            bits.append("walls=[" + ", ".join(_c(w) for w in self.walls) + "]")
        if self.antidotes:
            bits.append("antidotes=[" + ", ".join(_c(a) for a in self.antidotes) + "]")
        return f"{self.code}({', '.join(bits)})"


def _log(world, area_name, start, goal, planned, result):
    """The gap between what the plan promised and what the walk cost is a direct
    read on what an unmapped area is costing -- the same currency economy.py prints
    per step. Free to record, so record it.
    """
    world.nav_log.append({"day": world.day, "area": area_name, "from": start,
                          "to": goal, "planned": planned, "steps": result.steps,
                          "code": result.code})
    return result


def goto(world, x, y, avoid=None):
    """Walk to (x, y) over the map gemma has. Returns a Result.

    `avoid=None`      dodge only the walls it already knows about
    `avoid=[(a, b)]`  ...and these cells, this trip only
    `avoid="auto"`    ...and every cell it has marked. Visited destinations only.

    The walk stops the moment a step is refused -- face to face with the wall, which
    is where the most map has been revealed -- records it, and replans up to
    NAV_REPLANS times. An antidote absorbing a pit does not end the trip; falling
    into one without an antidote does, because it puts gemma in another area.
    """
    area, area_name, goal, start = world.here, world.area, (x, y), world.pos

    # Every cell actually stepped on, as against the cells that were planned for.
    # Handed to the world by reference so it grows as the walk does -- a watcher
    # redrawing per move needs no second channel. It can never contain a wall,
    # which is exactly what makes it worth drawing beside a plan that can.
    walk = [start]
    world.last_walk = (area_name, walk)

    if avoid == "auto":
        if goal not in area.visited:
            world.last_path = (area_name, [])
            return _log(world, area_name, start, goal, None,
                        Result("NOT_VISITED", at=start))
        avoid = frozenset(area.marks)
    else:
        avoid = frozenset(avoid or ())
    opened = frozenset(c for a, c in world.unlocked if a == area_name)

    path = plan(area, start, goal, avoid, opened)
    if path is None:
        # One more hypothesis, and only from the get-go: did the avoid list seal the
        # route, or is there genuinely no way through? Those are different facts and
        # gemma cannot tell them apart otherwise.
        code = "UNREACHABLE"
        if avoid and plan(area, start, goal, frozenset(), opened):
            code = "UNREACHABLE(avoid)"
        world.last_path = (area_name, [])
        return _log(world, area_name, start, goal, None, Result(code, at=start))

    planned = len(path) - 1
    world.last_path = (area_name, list(path))
    walls, burned, steps, replans = [], [], 0, S.NAV_REPLANS

    def done(code, **kw):
        kw.setdefault("at", world.pos)
        if code == "DONE" and world.pos != goal:
            # The target was solid, so this is as close as it gets. Say so, or
            # arriving reads as not having arrived.
            kw["beside"] = goal
        return _log(world, area_name, start, goal, planned,
                    Result(code, steps=steps, walls=walls, antidotes=burned, **kw))

    while True:
        wall = None
        for cell in path[1:]:
            if world.day_over:
                return done("OUT_OF_STEPS")

            was_area, was_pos, was_anti = world.area, world.pos, world.antidotes
            was_steps = world.steps
            world.move(cell[0] - was_pos[0], cell[1] - was_pos[1])

            # A refused move is detected by the step not being charged, never by
            # the position being unchanged. `world.move` charges a step only when
            # it actually moved, so this is exact -- and it does not read
            # `Area.traps`, so there is still nothing to leak.
            #
            # Position is not enough: a pit teleports you to the Plaza spawn, and
            # if you stepped into one *from* the spawn you land back where you
            # started. That reads as a refused move, so the pit gets reported as a
            # wall, the coins go missing with no TRAPPED to explain them, and the
            # notes end up with a wall recorded where a pit is.
            if world.steps == was_steps:
                wall = cell           # a wall, or a gate that will not open
                if cell not in walls:
                    walls.append(cell)
                break

            steps += 1
            walk.append(cell)
            if world.area != was_area:
                if (known(area, *cell) or ".") in GATES:
                    return done("LEFT_AREA", area=world.area)
                return done("TRAPPED", at=cell)      # a pit sent us home
            if world.pos != cell:
                return done("TRAPPED", at=cell)      # ...from inside this area
            if world.antidotes < was_anti:
                burned.append(cell)                  # absorbed; the walk carries on
        else:
            return done("DONE")

        if replans <= 0:
            break
        replans -= 1
        path = plan(area, world.pos, goal, avoid, opened)
        if path is None:
            break                     # gemma calls goto again from wherever it is
        world.last_path = (area_name, list(path))

    return done("BLOCKED", at=wall, stopped=world.pos)


def distance(world, x, y, avoid=None):
    """Planned length in steps. Costs nothing and moves nothing. None if no route.

    Optimistic, so it is a lower bound -- fog is assumed clear and the walk can only
    come out longer. `avoid="auto"` is accepted here even for somewhere gemma has
    never stood: the visited rule is about committing steps, and this commits none.
    """
    area = world.here
    avoid = frozenset(area.marks) if avoid == "auto" else frozenset(avoid or ())
    opened = frozenset(c for a, c in world.unlocked if a == world.area)
    path = plan(area, world.pos, (x, y), avoid, opened)
    world.last_path = (world.area, list(path) if path else [])
    world.last_walk = (world.area, [])   # priced, not walked -- say so on the map

    steps = None if path is None else len(path) - 1
    # Logged even though it moves nothing: whether gemma prices a trip before
    # committing to it is one of the behaviours prototype 1 exists to watch.
    _log(world, world.area, world.pos, (x, y), steps,
         Result("UNREACHABLE" if steps is None else "DISTANCE"))
    return steps
