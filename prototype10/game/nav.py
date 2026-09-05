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

It also writes the route out, and that file is the whole seam to the physical rover.
`goto` drives the leg in the simulation first and only then writes down the prefix
that actually worked, as one of N/E/S/W a line and nothing else. So the robot is only
ever handed moves the simulation has already proved, and cannot be sent into rock.
The file holds the current leg; the whole journey lives in the tape.
"""

import heapq
import os
import tempfile
import time

import settings as S
from world import SOLID, THINGS

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
# Clockwise from north, and this order is load-bearing: it indexes HEADING_NAMES, so a
# step is `HEADING_NAMES[DIRS.index(step)]`. 0=N 1=E 2=S 3=W.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
HEADING_NAMES = ("N", "E", "S", "W")
# The whole alphabet the route file speaks. Anything reading it can check against this.
MOVES = HEADING_NAMES
FAR = 1 << 30

# The prototype directory, so a relative S.PLAN_FILE means the same thing whether
# main.py was started from prototype7/ or from prototype7/game/.
PLAN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    A known rock is not a thing and gets none of this -- it is `THINGS`, not `SOLID`.
    Driving into an outcrop you can see is a mistake and UNREACHABLE is the honest
    answer; `DONE(beside=...)` would say you arrived somewhere you never went, and the
    model once spent four days re-issuing a move it had been told succeeded.

    A fogged cell that turns out to be rock is the opposite case: that one is a
    hypothesis and driving into it is how the map fills in. Only seen rock is refused.
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


def with_storm(area, avoid):
    """`avoid` plus today's weather.

    The storm is folded in here rather than taught to `_passable`, so every rule that
    already holds for an avoided cell holds for it too -- a route is planned around it,
    a goal inside it has no way in, and `_targets` will not stop the rover beside one.
    It also makes "what would this route have been without the storm" a plain second
    call to `plan`, which is how `goto` tells a storm apart from an outcrop.
    """
    return frozenset(avoid) | area.storm_cells


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


def route_actions(path):
    """A cell path from `plan` rewritten as the directions the route file speaks --
    one of N/E/S/W a step, in order.

    Absolute, in world coordinates, the same frame `plan` already thinks in. The
    rover's facing does not appear. It used to: a step became a turn plus a FORWARD,
    computed against a heading, and BACKWARD existed to spend one action where a
    U-turn would have spent three. All of it was arithmetic against a quantity the
    simulation never measured -- and with the rover stopping at every leg boundary,
    an assumed heading is exactly where the sim's belief and the robot's reality come
    apart. Absolute removes the quantity rather than correcting it.

    Turning is now the driver's business, on its own side of the file. It knows which
    way it is pointing; nothing here can.

    A repeated or diagonal step raises. `plan` never emits one, and quietly accepting
    it would write a file that drives somewhere else.

    Pure. Plans nothing, moves nothing, reads no grid.
    """
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
    """What a goto comes back with.

    `str()` is the line gemma reads and the line the console prints -- one wording, not
    two. `at` is where you ended up or the rock you hit; `stopped` appears only when
    those differ. Every result carries `steps`.

    `beside` says the target was solid and this is as close as anyone gets. Without it,
    `goto(25,26)` at the pad reads as `DONE(at=(25,25))` and the model concludes it has
    not arrived. Set for things, never for rock.

    `new` is how much map the drive bought. Without it gemma spent 439 steps, 358 of
    them revealing nothing, and every answer was the same `DONE(at=..., steps=49)` the
    useful drives got -- nothing to tell a drive that mapped three hundred cells from
    one that mapped none.

    `None` for a call that never drove, so it prints conditionally: `distance` builds a
    Result purely to log, and "revealed nothing" would be a claim about a trip nobody
    took.
    """

    GOOD = {"DONE", "SCOUTED", "PLANNED"}

    def __init__(self, code, steps=0, at=None, stopped=None, beside=None, walls=(),
                 new=None, to=None, planned=None):
        self.code = code
        self.steps = steps
        self.at = at
        self.stopped = stopped
        self.beside = beside
        self.walls = list(walls)
        self.new = new
        # Where the call was *aimed*, when that differs from where anything ended up --
        # a scout window has a centre and leaves the rover where it stands, so `at`
        # alone cannot say what was asked for.
        self.to = to
        # How long the route is, for a call that planned one and drove none of it.
        self.planned = planned

    @property
    def tone(self):
        return "good" if self.code in self.GOOD else "bad"

    def __str__(self):
        bits = []
        if self.to:
            bits.append(f"to={_c(self.to)}")
        if self.at:
            bits.append(f"at={_c(self.at)}")
        if self.beside:
            bits.append(f"beside={_c(self.beside)}")
        if self.stopped:
            bits.append(f"stopped={_c(self.stopped)}")
        if self.planned is not None:
            bits.append(f"route={self.planned}")
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

        Kept off `__str__` so the code form stays one line -- the HUD ticker does not
        wrap and the console truncates. `skills` appends it for gemma, the console
        prints it for the human. One wording, three places.

        `beside=` alone was not enough: gemma read `DONE(at=(10,15), beside=(10,16))`
        as a failure to reach (10,16) and spent the run driving into a counter. A field
        is not a sentence.

        The zero-step case is the other half -- `goto` to the cell you are standing on
        succeeds, costs nothing, and reads as though something happened.

        Prototype 7's third case -- a drive that bought no map -- is gone. No drive buys
        map here, so saying so after every one is noise rather than news.
        """
        if self.beside:
            return (f"{_c(self.beside)} is solid, so stopping beside it IS "
                    f"arriving. Do not ask again.")
        if self.code == "STORM_BLOCKED":
            return (f"the dust storm is across the only way there. It is not rock and "
                    f"it is not your doing: it blows out at the end of the sol and the "
                    f"ground under it is fine. Go somewhere else today, or wait it out.")
        if self.code == "PLANNED":
            return ("the route is in the plan file and the rover has not moved, so "
                    "nothing has changed and planning this again gives the same answer.")
        if self.code == "DONE" and not self.steps:
            return "you were already standing there. Nothing moved, nothing spent."
        return ""


def plan_file():
    """Absolute path of the live route file, or None when it is switched off."""
    if not S.PLAN_FILE:
        return None
    if os.path.isabs(S.PLAN_FILE):
        return S.PLAN_FILE
    return os.path.join(PLAN_ROOT, S.PLAN_FILE)


def _replace(tmp, out, tries=10, wait=0.05):
    """`os.replace`, retried. It is atomic and it is also refused with WinError 5 the
    moment anything else has the target open for a fraction of a second -- OneDrive
    syncing the folder, an editor with the file up, a reader tailing it.

    Half a second of retries, then raise. A route file that cannot be rewritten is a
    fault worth stopping for: whatever reads it would otherwise go on driving the plan
    the planner has already replaced.
    """
    for n in range(tries):
        try:
            os.replace(tmp, out)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(wait)


def write_plan(out, dirs):
    """One leg, already driven, as one of N/E/S/W a line. Nothing else in the file.

    No header, no comments, no coordinates, no leg structure. Everything a reader
    used to have to skip is gone, so there is no parser on the other side worth the
    name -- read the lines, drive them. An empty `dirs` writes an empty file, which
    is how the file says the rover has nothing to do.

    `dirs` is the prefix that *worked*, not a plan: `goto` drives the leg in the
    simulation and calls this afterwards with the cells it actually got over. The
    robot is therefore never handed a move the simulation has not already proved,
    and cannot be driven into rock. That is the whole reason the write comes last.

    Written to a temporary file and renamed over the target -- atomic on Windows as
    well as POSIX, so a reader arriving mid-write gets the previous file rather than
    half of this one. A rover executing half a plan drives into something.
    """
    # No trailing newline on an empty file. "\n".join([]) + "\n" is a blank line, and
    # a reader splitting on newlines would get one empty move out of it.
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
    """Empty the route file, and forget the journey it belonged to.

    Whatever reads this file has no way to know how old it is. Left alone, the first
    thing a fresh run offers is the last leg of the previous one -- a route from a
    position the rover is no longer in, which is the worst kind of wrong because it is
    perfectly well-formed.

    Also the wipe at the end of every leg. Once the robot has replayed a leg the file
    has said everything it has to say, and an empty file is the only honest thing to
    leave lying there while the planner thinks.
    """
    publish(world, [])


def live_file(world):
    """The route file this run writes, or None when nothing is driving.

    Written only for a live run, and `world.recorder` is what marks one -- `logs.py`
    sets it and it is None in every test, the same seam `world.py` uses to keep itself
    free of I/O. A suite that plans thousands of routes has no business touching the
    disk, and a plan file a test left behind is a route the next reader believes.
    `S.PLAN_FILE = None` switches it off for a live run too.

    None also means there is no robot on the other end, so nothing waits for one.
    """
    out = plan_file()
    return out if out and world.recorder else None


def publish(world, dirs):
    """Write one leg's directions to the live route file, if there is one."""
    out = live_file(world)
    if out:
        write_plan(out, dirs)


def _await_rover(world, dirs):
    """Block until the robot has driven `dirs` off the file and stopped.

    A no-op here, and replaced from outside: `main.py` swaps in a wait on the
    operator, and the tests swap in a spy. Keeping the default empty is what lets a
    suite drive thousands of legs without anything to press, and keeps pygame out of
    this file -- the same injection `main.py` already does for `Conversation.ready`.

    The operator standing in for the robot is temporary. The rover bridge reporting
    back for itself is Abhishek's, and none of the file format changes when it lands:
    this is the only function that has to know the difference.
    """
    return


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


def goto(world, x, y, avoid=None, executor=None):
    """Drive to (x, y) over the map the rover has. Returns a Result.

    `avoid=None`      dodge only the rock it already knows about
    `avoid=[(a, b)]`  ...and these cells, this trip only
    `avoid="auto"`    ...and every cell it has marked. Visited destinations only.

    One leg at a time, and the leg is the unit the physical rover sees. The simulation
    drives a plan until it arrives or hits rock, `S.PLAN_FILE` is then written with the
    prefix that *worked*, the robot replays that and stops, and the file is wiped before
    the planner is allowed to think again. So the robot is only ever handed ground the
    simulation has already been over, and a plan that turns out to run into an outcrop
    costs a replan rather than a collision.

    `executor="teleport"` (the default) steps cell to cell via `world.move`.
    `executor="plan"` plans and moves nothing, which is for watching the planner alone:
    no fog lifts, so every plan is made over the same map. Nothing is driven, so nothing
    is written -- the file is a record of a drive, and there was no drive.

    The drive stops the moment a step is refused -- face to face with the outcrop,
    which is where the most map has been revealed -- records it, and replans up to
    NAV_REPLANS times. `NAV_REPLANS = 5` therefore bounds this at six hardware
    round-trips per call, however far the rover has to go.
    """
    executor = S.EXECUTOR if executor is None else executor
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
    asked, avoid = avoid, with_storm(area, avoid)

    path = plan(area, start, goal, avoid)
    if path is None:
        # One more hypothesis, and only from the get-go: did the avoid list seal the
        # route, or is there genuinely no way through? Those are different facts and
        # gemma cannot tell them apart otherwise. The storm is a third: it is not the
        # rover's doing and it clears tonight, which is a different thing to be told.
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

    if executor == "plan":
        # Plan and stop. Nothing was driven, so nothing is written: this file says what
        # the rover *did*, and a hypothesis in it is the one thing it must never hold.
        world.play(reel)
        return _log(world, area_name, start, goal, planned,
                    Result("PLANNED", at=start, planned=planned, new=0))

    walls, steps, replans = [], 0, S.NAV_REPLANS
    # What the drive bought. `world.revealed` holds one move's worth and is replaced on
    # the next, so it is unioned as we go rather than read at the end.
    gained = set()
    # Where in `walk` the leg currently being driven started. `walk` spans the whole
    # goto; the robot is handed one leg at a time.
    leg_start = 0

    def hand_over():
        """The leg just driven, given to the robot, and the file left empty after.

        Called once a leg has stopped -- arrived, blocked, or out of steps. A leg of
        one cell is the rover not having moved, and writing an empty file and wiping
        it again says nothing, so it is skipped. So is a run with no file at all:
        there is no robot on the other end of one, and nothing to wait for.
        """
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
            # The target was solid, so this is as close as it gets. Say so, or
            # arriving reads as not having arrived.
            kw["beside"] = goal
        world.play(reel)
        hand_over()
        return _log(world, area_name, start, goal, planned,
                    Result(code, steps=steps, walls=walls, **kw))

    while True:
        wall = None
        leg_start = len(walk) - 1
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
                # Contact is the only thing driving reveals. Without this the rock stays
                # fogged, `_passable` goes on believing it clear, and the replan below
                # returns the identical path -- the rover bumps the same cell until the
                # replans run out. A rover with no cameras still knows what it hit.
                gained |= area.reveal_cells({cell})
                reel.append(("block", cell))
                break

            steps += 1
            walk.append(cell)
            # The disc this step opened. Unioned as we go because `world.revealed` holds
            # one move's worth and is replaced by the next, and handed to the reel so the
            # fog peels back in step with the rover being drawn rather than all at once
            # the moment the call returns.
            gained |= world.revealed
            reel.append(("step", (cell, sorted(world.revealed))))
        else:
            return done("DONE")

        # The leg ended on rock. The robot drives what worked before anything is
        # replanned -- it is behind the simulation until it has, and a route planned
        # from a cell it has not reached yet is a route for somebody else.
        hand_over()

        if replans <= 0:
            break
        replans -= 1
        path = plan(area, world.pos, goal, avoid)
        if path is None:
            break                     # gemma calls goto again from wherever it is
        world.last_path = (area_name, list(path))
        reel.append(("plan", list(path)))

    # `done` hands over too, and the leg it would send has already gone. Reset so the
    # slice is a single cell and the write is skipped rather than repeated.
    leg_start = len(walk) - 1
    return done("BLOCKED", at=wall, stopped=world.pos)


def price(world, x, y, avoid=None):
    """What a trip would cost, in steps. None if there is no route at all.

    Prototype 7 returned a second number -- what the drive would reveal. Driving reveals
    nothing here, so the honest answer is always zero and the field is gone rather than
    shipped as a constant.

    `steps` is a floor, not a quote: the route is planned over fog assumed clear, so
    rock in the way makes the real drive longer. Costs nothing and moves nothing.
    `avoid="auto"` is accepted even for somewhere the rover has never stood: the visited
    rule is about committing steps, and this commits none.
    """
    area = world.here
    avoid = frozenset(area.marks) if avoid == "auto" else frozenset(avoid or ())
    # The same weather the drive would meet, or the quote is for a trip nobody can take.
    avoid = with_storm(area, avoid)
    path = plan(area, world.pos, (x, y), avoid)
    world.last_path = (world.area, list(path) if path else [])
    world.last_walk = (world.area, [])   # priced, not driven -- say so on the map
    # Pricing a trip is the one skill with nothing to see, so the route it considered
    # is drawn instead -- in blue, and never in the yellow a real drive uses, because
    # the whole point is that this one costs nothing and moves nothing.
    if path:
        world.play([("start", world.pos), ("probe", list(path))])

    steps = None if path is None else len(path) - 1
    # Logged even though it moves nothing: whether gemma prices a trip before
    # committing to it is one of the behaviours this prototype exists to watch.
    _log(world, world.area, world.pos, (x, y), steps,
         Result("UNREACHABLE" if steps is None else "DISTANCE"))
    return steps


def distance(world, x, y, avoid=None):
    """Planned length in steps, or None. An alias for `price`, kept because it is what
    four tests and the map view ask for."""
    return price(world, x, y, avoid)
