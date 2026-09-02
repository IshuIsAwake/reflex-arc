"""goto -- A* over the map the rover has, not the map that exists.

Pure functions and one driver loop. No pygame, so the tests can import it.

Copied from prototype 1 with the gates, the snake pits and the antidotes taken out.
Three rules make this A* rather than any other A*:

  * fogged cells are assumed to be regolith, so a plan is a hypothesis and driving it
    is the experiment;
  * `avoid` is impassable, never merely expensive;
  * a rock you have already seen is not somewhere you can arrive.

`known()` below is the only place this module touches the grid. `Area.at` returns
ground truth whether or not the cell is fogged -- reading it without checking
`Area.visible` first makes the planner quietly omniscient, everything keeps working,
and nothing ever looks wrong. `test_nav.py` counts the reads in this file for that
reason, so there had better stay exactly one.
"""

import heapq

import settings as S
from world import SOLID, THINGS

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
FAR = 1 << 30


def known(area, x, y):
    """What the rover knows about a cell: the character if it can see the cell, None
    if it is fogged, "#" off the edge of the arena.

    The only read of the grid in this module. Keep it that way.
    """
    if not (0 <= x < area.w and 0 <= y < area.h):
        return "#"
    return area.at(x, y) if area.visible(x, y) else None


def _around(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBOURS]


def _targets(area, goal, avoid):
    """Where a plan is allowed to end.

    A solid *thing* -- today only the base pad -- means "get next to it", or
    `goto(25, 26)` at the pad would be UNREACHABLE taken literally.

    **A known rock is not a thing and gets none of this.** It is `THINGS`, not
    `SOLID`. Asking to drive into an outcrop you can already see is a mistake, and
    the honest answer is UNREACHABLE. Answering `DONE(beside=...)` says you arrived
    somewhere you never went, and a caller that believes it has moved has nothing to
    correct: on 2026-08-26 the model spent four days stood beside a shop re-issuing a
    move it had been told succeeded. Widening this back to `SOLID` is all it takes to
    bring that back, and two tests in `test_nav.py` are the whole of what stands in
    the way.

    A **fogged** cell that turns out to be rock is the opposite case and stays
    exactly as it was -- that one is a hypothesis, and driving into it is how the map
    fills in. Only rock already seen is refused.
    """
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


def _passable(area, cell, avoid):
    """Fogged cells are passable at cost 1, and that is the whole design. Treat fog
    as rock and the rover can never path into unexplored ground; treat it as truth
    and it is omniscient.
    """
    if cell in avoid:
        return False
    ch = known(area, *cell)
    if ch is None:
        return True
    return ch not in SOLID


def plan(area, start, goal, avoid=frozenset()):
    """Cheapest known route, as a list of cells beginning with `start`. None if no
    route exists even assuming every fogged cell is regolith.

    A*: pop the cell with the smallest f = g + h, where g is the steps already spent
    reaching it and h is the Manhattan distance still to go. Manhattan can never
    overestimate on a four-way grid of unit steps, which is what makes the answer
    provably shortest rather than merely short. Ties break on the smaller h, so the
    search runs at the goal instead of fanning out around it.
    """
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


def _c(cell):
    return f"({cell[0]},{cell[1]})"


class Result:
    """What a goto comes back with.

    `str()` is exactly the line gemma reads and exactly the line the console prints,
    so there is one wording rather than two. `at` is what the call is about -- where
    you ended up, or the rock you hit. `stopped` appears only when those differ.
    Every result carries `steps`, because the day is made of them.

    `beside` says the target was solid and this is as close as anyone gets. Without
    it, arriving at the pad reads as `DONE(at=(25,25))` for a `goto(25,26)`, and a
    model reasonably concludes it has not arrived and asks again -- watched gemma do
    exactly that three times on 2026-08-25. It is set for things, never for rock, and
    `_targets` is what guarantees that.

    **`new` is how much map the drive bought**, and the number that was missing. Read
    back the sol of 2026-08-29: gemma swept the perimeter in fourteen drives and then
    spent 439 steps, 358 of which revealed nothing at all, ping-ponging between three
    corners while a five-hundred-cell blob sat unexplored. Every one of those answers
    was `DONE(at=..., steps=49)` -- the same sentence the fourteen useful drives got.
    A caller told only that it arrived and what it spent has no way to tell a drive
    that mapped three hundred cells from one that mapped none, and so nothing to
    correct. The count already existed: `world.revealed` is set on every move and was
    read only by the fog animation.

    It is `None` for a call that never drove, which is why it prints conditionally --
    `distance` builds a Result purely to log, and "revealed nothing" would be a claim
    about a trip nobody took.
    """

    GOOD = {"DONE"}

    def __init__(self, code, steps=0, at=None, stopped=None, beside=None, walls=(),
                 new=None):
        self.code = code
        self.steps = steps
        self.at = at
        self.stopped = stopped
        self.beside = beside
        self.walls = list(walls)
        self.new = new

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
        bits.append(f"steps={self.steps}")
        # Printed even when it is nought -- especially when it is nought. A drive that
        # bought no map is the thing worth saying, and a field that appears only on
        # success is one the reader learns to stop looking for.
        if self.new is not None:
            bits.append(f"new={self.new}")
        if self.walls:
            bits.append("rock=[" + ", ".join(_c(w) for w in self.walls) + "]")
        return f"{self.code}({', '.join(bits)})"

    @property
    def advice(self):
        """The two answers a reader gets backwards, said again in words.

        Kept off `__str__` so the code form stays one line: the HUD ticker does not
        wrap and the console truncates, so folding this in would overflow one surface
        and silently cut the other. Defined once here and laid out by whoever is
        showing it -- `skills` appends it for gemma, the console prints it underneath
        for the human. One wording, three places.

        `beside=` was supposed to be enough on its own and is not. Watched on
        2026-08-26: gemma read `DONE(at=(10,15), beside=(10,16))`, decided it had
        failed to reach (10,16), and spent the rest of the run trying to drive into a
        counter -- *"moving there has no apparent effect."* **A field is not a
        sentence.** A caller that cannot tell arrival from failure has nothing to
        correct, which is the expensive kind of wrong.

        The zero-step case is the other half. `goto` to the cell you are standing on
        succeeds, costs nothing, and reads as though something happened -- so a model
        that has misread its position can bounce between two cells indefinitely and
        never be told it is going nowhere.
        """
        if self.beside:
            return (f"{_c(self.beside)} is solid, so stopping beside it IS "
                    f"arriving. Do not ask again.")
        if self.code == "DONE" and not self.steps:
            return "you were already standing there. Nothing moved, nothing spent."
        return ""


def _log(world, area_name, start, goal, planned, result):
    """The gap between what the plan promised and what the drive cost is a direct
    read on what unmapped ground is costing. Free to record, so record it.
    """
    world.nav_log.append({"day": world.day, "area": area_name, "from": start,
                          "to": goal, "planned": planned, "steps": result.steps,
                          "code": result.code, "new": result.new})
    world.record("nav", area=area_name, start=start, goal=goal, planned=planned,
                 steps=result.steps, code=result.code, new=result.new)
    return result


def goto(world, x, y, avoid=None):
    """Drive to (x, y) over the map the rover has. Returns a Result.

    `avoid=None`      dodge only the rock it already knows about
    `avoid=[(a, b)]`  ...and these cells, this trip only
    `avoid="auto"`    ...and every cell it has marked. Visited destinations only.

    The drive stops the moment a step is refused -- face to face with the outcrop,
    which is where the most map has been revealed -- records it, and replans up to
    NAV_REPLANS times.
    """
    area, area_name, goal, start = world.here, world.area, (x, y), world.pos

    # Every cell actually driven over, as against the cells that were planned for.
    # Handed to the world by reference so it grows as the drive does -- a watcher
    # redrawing per move needs no second channel. It can never contain a rock,
    # which is exactly what makes it worth drawing beside a plan that can.
    walk = [start]
    world.last_walk = (area_name, walk)

    # What the drive did, in order, so it can be watched afterwards. `anim.py` reads
    # this; nothing here waits on it. Every replan appends its own `plan`, which is the
    # part `world.last_path` cannot carry -- that field only ever holds the newest
    # hypothesis, and the interesting thing to look at is the one that was wrong.
    reel = [("start", start)]

    if avoid == "auto":
        if goal not in area.visited:
            world.last_path = (area_name, [])
            return _log(world, area_name, start, goal, None,
                        Result("NOT_VISITED", at=start, new=0))
        avoid = frozenset(area.marks)
    else:
        avoid = frozenset(avoid or ())

    path = plan(area, start, goal, avoid)
    if path is None:
        # One more hypothesis, and only from the get-go: did the avoid list seal the
        # route, or is there genuinely no way through? Those are different facts and
        # gemma cannot tell them apart otherwise.
        code = "UNREACHABLE"
        if avoid and plan(area, start, goal, frozenset()):
            code = "UNREACHABLE(avoid)"
        world.last_path = (area_name, [])
        return _log(world, area_name, start, goal, None, Result(code, at=start, new=0))

    planned = len(path) - 1
    world.last_path = (area_name, list(path))
    reel.append(("plan", list(path)))
    walls, steps, replans = [], 0, S.NAV_REPLANS
    # What the drive bought. `world.revealed` holds one move's worth and is replaced on
    # the next, so it is unioned as we go rather than read at the end.
    gained = set()

    def done(code, **kw):
        kw.setdefault("at", world.pos)
        kw.setdefault("new", len(gained))
        if code == "DONE" and world.pos != goal:
            # The target was solid, so this is as close as it gets. Say so, or
            # arriving reads as not having arrived.
            kw["beside"] = goal
        world.play(reel)
        return _log(world, area_name, start, goal, planned,
                    Result(code, steps=steps, walls=walls, **kw))

    while True:
        wall = None
        for cell in path[1:]:
            if world.day_over:
                return done("OUT_OF_STEPS")

            was_pos, was_steps = world.pos, world.steps
            world.move(cell[0] - was_pos[0], cell[1] - was_pos[1])

            # A refused move is detected by the step not being charged, never by the
            # position being unchanged. `world.move` charges a step only when it
            # actually moved, so this is exact. Prototype 1 needed this because a
            # pit could teleport you back to where you started; there are no pits
            # here yet, and item 3 brings hazards that will need it again.
            if world.steps == was_steps:
                wall = cell
                if cell not in walls:
                    walls.append(cell)
                reel.append(("block", cell))
                break

            steps += 1
            walk.append(cell)
            gained |= world.revealed
            # The cells this one step opened up, so the fog can be peeled back in time
            # with the rover rather than all at once before it sets off.
            reel.append(("step", (cell, sorted(world.revealed))))
        else:
            return done("DONE")

        if replans <= 0:
            break
        replans -= 1
        path = plan(area, world.pos, goal, avoid)
        if path is None:
            break                     # gemma calls goto again from wherever it is
        world.last_path = (area_name, list(path))
        reel.append(("plan", list(path)))

    return done("BLOCKED", at=wall, stopped=world.pos)


def price(world, x, y, avoid=None):
    """What a trip would cost and what it might buy: `(steps, reveals)`.

    **`steps` alone answers the wrong question for an exploration mission.** "Thirty
    against fifty" says which journey is shorter and nothing about which is worth
    taking, and on 2026-08-29 gemma did not call this skill once in twenty-seven calls.
    `reveals` is the other half: walk the planned route, union what the rover would see
    from each cell of it, and subtract what it has already seen.

    **The two numbers do not point the same way, and calling them both `optimistic` was
    wrong.** The route is planned over fog assumed clear, so `steps` is a floor: a drive
    that completes takes this long or longer. `reveals` was described the same way and is
    not bounded at all. The reason is the mechanism already named above -- the drive
    replans around rock the straight route assumed away, and the detour sweeps ground the
    straight route would never have passed.

    Measured 2026-08-30, thirty-eight trips priced and then driven from the same state:
    nine revealed **more** than promised, worst case 68 against an actual 112. The run in
    `runs/20260830-102123/` is the one that caught it -- priced `steps=53, reveals~299`,
    drove it and got `steps=69, new=315`. So `reveals` is an estimate either way, and the
    result string now says which number is a floor and which is a guess. **A field that
    promises a direction it does not hold is the lying success code wearing a number.**

    (Drives that stop early read shorter than priced, and all five of those in the sweep
    were `BLOCKED`. The code carries that; `steps` is a floor for a trip that arrives.)

    `(None, 0)` if there is no route at all. Costs nothing and moves nothing.
    `avoid="auto"` is accepted even for somewhere the rover has never stood: the visited
    rule is about committing steps, and this commits none.
    """
    area = world.here
    avoid = frozenset(area.marks) if avoid == "auto" else frozenset(avoid or ())
    path = plan(area, world.pos, (x, y), avoid)
    world.last_path = (world.area, list(path) if path else [])
    world.last_walk = (world.area, [])   # priced, not driven -- say so on the map
    # Pricing a trip is the one skill with nothing to see, so the route it considered
    # is drawn instead -- in blue, and never in the yellow a real drive uses, because
    # the whole point is that this one costs nothing and moves nothing.
    if path:
        world.play([("start", world.pos), ("probe", list(path))])

    steps = None if path is None else len(path) - 1
    # What the trip might buy: what the rover would see from every cell of the route,
    # less what it has seen already. Fifty cells at forty-nine each -- nothing.
    reveals = 0
    if path:
        would_see = set()
        for cell in path:
            would_see |= area.disc(*cell)
        reveals = len(would_see - area.seen)

    # Logged even though it moves nothing: whether gemma prices a trip before
    # committing to it is one of the behaviours this prototype exists to watch.
    _log(world, world.area, world.pos, (x, y), steps,
         Result("UNREACHABLE" if steps is None else "DISTANCE"))
    return steps, reveals


def distance(world, x, y, avoid=None):
    """Planned length in steps, or None. The `price` above, without the second number.

    Kept because it is what four tests and the map view ask for, and because a caller
    that only wants the cost should not have to unpack a pair to ignore half of it.
    """
    return price(world, x, y, avoid)[0]
