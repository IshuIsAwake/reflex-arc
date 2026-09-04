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
import os
import tempfile
import time

import settings as S
from world import DIRS, SOLID, THINGS

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))
# Indexed by world.DIRS / world.heading: 0=N 1=E 2=S 3=W.
HEADING_NAMES = ("N", "E", "S", "W")
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


# The prototype directory, so a relative S.PLAN_FILE means the same thing whether
# main.py was started from prototype5/ or from prototype5/game/.
PLAN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOVES = ("FORWARD", "BACKWARD", "LEFT", "RIGHT")


def route_actions(path, heading=0):
    """A cell path from `plan` rewritten as the rover's own actions, plus the heading
    it finishes on. Returns `(actions, heading)`.

    `plan` speaks in world coordinates -- north is north whatever the rover is doing.
    The rover has a facing, so north is only FORWARD when it is already pointing
    north; six wheels and a differential drive make turning in place the primitive.

    BACKWARD is a real move, not two turns. The rover reverses as readily as it
    drives, so backing into the cell behind it costs one action and leaves the heading
    alone -- where a U-turn costs two turns and injects two turns' worth of heading
    error (ARCHITECTURE.md: rotation is the one error we bother to correct).

    These names are NOT `rl_drive.NAMES`. That list is the DQN's action space, indexed
    by the order its trained weights were built against, and it has no reverse at all.
    Anything feeding this file to that policy has to expand BACKWARD into two turns and
    a FORWARD first. Said here because the two alphabets look interchangeable and are
    not.

    `heading` follows the `world.DIRS` convention: 0=N 1=E 2=S 3=W. A repeated or
    diagonal step raises -- `plan` never emits one, and quietly accepting it would
    write a file that drives somewhere else.

    Pure. Plans nothing, moves nothing, reads no grid.
    """
    out = []
    for a, b in zip(path, path[1:]):
        step = (b[0] - a[0], b[1] - a[1])
        if step not in DIRS:
            raise ValueError(f"not a single orthogonal step: {_c(a)} -> {_c(b)}")
        want = DIRS.index(step)
        turn = (want - heading) % 4
        if turn == 2:
            # Straight back, heading untouched -- the rover has moved and is still
            # facing the way it was. Every turn is where heading error gets injected,
            # so the cheapest turn is the one not taken.
            out.append("BACKWARD")
            continue
        if turn:
            out.append("RIGHT" if turn == 1 else "LEFT")
        out.append("FORWARD")
        heading = want
    return out, heading


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

    GOOD = {"DONE", "MOVED", "PRESSED", "PLANNED"}

    def __init__(self, code, steps=0, at=None, stopped=None, beside=None, walls=(),
                 new=None, pressed=False, planned=None, extent=None):
        self.code = code
        self.steps = steps
        self.at = at
        self.stopped = stopped
        self.beside = beside
        self.walls = list(walls)
        self.new = new
        self.pressed = pressed   # the policy executor pressed the button here
        self.planned = planned   # route length for a PLANNED call, which spends none
        self.extent = extent     # arena size, set only when the target was off it

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
        # A planned route costs nothing, so `steps=0` is true and useless on its own.
        # The length is the only number the call produced.
        if self.planned is not None:
            bits.append(f"planned={self.planned}")
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
        """
        if self.extent:
            # Watched 2026-09-04: gemma asked for goto(50,15) on a 50-wide arena
            # twenty-eight times running. Every answer was UNREACHABLE, which is also
            # what a walled-in cell returns, so there was nothing to tell it the cell
            # did not exist -- and being told the same true thing repeatedly is not
            # information. The coordinates are the whole of the fix.
            w, h = self.extent
            return (f"that cell is not on the map. x is 0 to {w - 1} and y is 0 to "
                    f"{h - 1}. Asking again with the same numbers gets the same "
                    f"answer.")
        if self.beside:
            return (f"{_c(self.beside)} is solid, so stopping beside it IS "
                    f"arriving. Do not ask again.")
        if self.code == "DONE" and self.pressed:
            return f"Pressed the button at {_c(self.at)}."
        if self.code == "PRESSED":
            return f"Pressed the button at {_c(self.at)}."
        if self.code == "BUMPED":
            return (f"{_c(self.at)} is solid, so there is no arriving there. "
                    f"Plan around it.")
        if self.code == "NOTHING_TO_PRESS":
            return ("There is no button here. Buttons are listed under "
                    "WHAT YOU KNOW IS HERE -- check the view first.")
        if self.code == "PLANNED":
            return (f"the route was written to the plan file. Nothing moved and "
                    f"nothing was spent, so the map has not changed either -- "
                    f"planning again from here gives the same answer.")
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
    syncing the folder, an editor with the file up, a reader tailing it. Measured here:
    the second `goto` of a run died on it while the first went through.

    Half a second of retries, then raise. A route file that cannot be rewritten is a
    fault worth stopping for, not one to swallow: whatever reads it would otherwise go
    on driving the plan the planner has already replaced.
    """
    for n in range(tries):
        try:
            os.replace(tmp, out)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(wait)


def write_plan(out, legs, goal, executor="teleport"):
    """The whole journey to one objective, rewritten from scratch on every change.

    `legs` is every plan made toward `goal`, oldest first, each a
    `(cells, start, heading, status)`. A leg carries a status once it is over --
    superseded by a replan, or the end of the drive. The last leg with no status is
    the live one.

    Which gives the file two jobs at once and only one of them is dangerous:

      * every leg is written out, so the file is the story of getting there --
        the first hypothesis, each wall that broke it, and what was tried instead;
      * only the live leg's moves are left runnable. Finished legs keep theirs
        behind `#`, so a reader that strips comments and drives the rest gets at
        most one route, always the current one, however many times the plan changed.

    A new objective starts a new file. Nothing from the last one survives, because a
    route to somewhere the rover is no longer going is the worst kind of stale: it is
    perfectly well-formed.

    Written to a temporary file and renamed over the target -- atomic on Windows as
    well as POSIX, so a reader arriving mid-write gets the previous file rather than
    half of this one. A rover executing half a plan drives into something.
    """
    live = len(legs) - 1 if legs and legs[-1][3] is None else -1
    out_lines = [
        "# reflex-arc live route -- one objective, every leg of it.",
        f"# goal {_c(goal)}, executor={executor}",
        f"# {len(legs)} leg(s). Only an uncommented move is one to drive.",
    ]
    if not legs:
        out_lines.append("# NO ROUTE -- the planner has none. Do not drive the last one.")

    for i, (cells, at, heading, status) in enumerate(legs):
        actions, ends = route_actions(cells, heading)
        state = status or "LIVE"
        out_lines += [
            "#",
            f"# leg {i + 1}/{len(legs)}  {state}  from {_c(at)} facing "
            f"{HEADING_NAMES[heading]}, {len(cells) - 1} moves, {len(actions)} "
            f"actions, ends facing {HEADING_NAMES[ends]}",
            "# cells: " + " ".join(_c(c) for c in cells),
        ]
        out_lines += actions if i == live else [f"# {a}" for a in actions]

    if executor != "policy":
        out_lines.append("# note: teleport executor does not turn, so facing is assumed.")

    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(out), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out_lines) + "\n")
        _replace(tmp, out)
    except BaseException:
        os.path.exists(tmp) and os.remove(tmp)
        raise
    return out


def _close_leg(legs, status):
    """Mark the live leg finished. A leg with a status keeps its moves commented out,
    so at most one runnable route is ever in the file."""
    if legs and legs[-1][3] is None:
        cells, at, heading, _ = legs[-1]
        legs[-1] = (cells, at, heading, status)


def clear_plan(world):
    """Empty the route file for a new session.

    Whatever reads this file has no way to know how old it is. Left alone, the first
    thing a fresh run offers is the last plan of the previous one -- a route from a
    position the rover is no longer in, which is the worst kind of wrong because it is
    perfectly well-formed.
    """
    world.plan_goal, world.plan_legs = None, []
    publish(world, [], world.pos)


def publish(world, legs, goal, executor="teleport"):
    """Rewrite the live route file, if there is one. Called wherever `goto` commits to
    a route -- the first plan and every replan -- so the file holds one plan, the
    current one, instead of a pile of them nobody can tell apart.

    Written only for a live run, and `world.recorder` is what marks one -- `logs.py`
    sets it and it is None in every test, which is the same seam `world.py` uses to
    keep itself free of I/O. A suite that plans thousands of routes has no business
    touching the disk, and a plan file a test left behind is a route the next reader
    believes. `S.PLAN_FILE = None` switches it off for a live run too.
    """
    out = plan_file()
    if out and world.recorder:
        write_plan(out, legs, goal, executor)


def _log(world, area_name, start, goal, planned, result,
         cells=None, walked=None, why=None, heading=None):
    """The gap between what the plan promised and what the drive cost is a direct
    read on what unmapped ground is costing. Free to record, so record it.

    `world.nav_log` stays the short in-memory summary the map view and the tests read.
    The recorder gets the whole decision, because that is what a training set is made
    of and there is no second chance to collect it:

        why      the model's own reason, as it gave it
        cells    the route A* planned, in full
        walked   the cells actually driven, which differ the moment anything replans
        heading  which way the rover was pointing, so the actions can be recomputed

    Actions are deliberately *not* stored. `route_actions(cells, heading)` derives them
    exactly, and a second copy is a second thing to keep in step.
    """
    world.nav_log.append({"day": world.day, "area": area_name, "from": start,
                          "to": goal, "planned": planned, "steps": result.steps,
                          "code": result.code, "new": result.new})
    world.record("nav", area=area_name, start=start, goal=goal, planned=planned,
                 steps=result.steps, code=result.code, new=result.new,
                 why=why, heading=heading,
                 cells=list(cells) if cells else None,
                 walked=list(walked) if walked else None)
    return result


def goto(world, x, y, avoid=None, executor="teleport", act=None, why=None):
    """Drive to (x, y) over the map the rover has. Returns a Result.

    `avoid=None`      dodge only the rock it already knows about
    `avoid=[(a, b)]`  ...and these cells, this trip only
    `avoid="auto"`    ...and every cell it has marked. Visited destinations only.

    `why` is the model's stated reason. Nothing here reads it -- it goes straight to
    the log, where it is the label beside the route and the only part of a decision
    that cannot be recovered afterwards.

    `executor="teleport"` (the default) steps cell to cell via world.move.
    `executor="policy"` drives each leg with the trained one-cell DQN
    (rl_drive.py) via world.step_action, and PRESSes the button if the goal
    is one. `act` is an action function for tests; None loads rl_policy.pt,
    which raises RuntimeError with the fix when weights or torch are missing.

    The drive stops the moment a step is refused -- face to face with the outcrop,
    which is where the most map has been revealed -- records it, and replans up to
    NAV_REPLANS times.
    """
    area, area_name, goal, start = world.here, world.area, (x, y), world.pos
    heading0 = world.heading      # recorded, so the actions can be rebuilt from cells

    # Every plan made toward this objective, oldest first, as
    # (cells, from, heading, status). Replans append -- and so does a fresh `goto` at a
    # goal the rover has not reached yet, because being blocked and trying again is one
    # journey and the file has to read like one. Only a change of objective, or having
    # arrived at the last one, starts the list over.
    if world.plan_goal != goal:
        world.plan_goal, world.plan_legs = goal, []
    legs = world.plan_legs

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
            publish(world, legs, goal, executor)
            return _log(world, area_name, start, goal, None,
                        Result("NOT_VISITED", at=start, new=0),
                        why=why, heading=heading0)
        avoid = frozenset(area.marks)
    else:
        avoid = frozenset(avoid or ())

    policy_act = None
    if executor == "policy":
        # Lazy so the teleport path (and every test of it) never imports numpy
        # or torch. A scripted `act` keeps this branch testable without weights.
        from rl_drive import drive_leg, load_policy, press_here
        policy_act = act if act is not None else load_policy()

    path = plan(area, start, goal, avoid)
    if path is None:
        # One more hypothesis, and only from the get-go: did the avoid list seal the
        # route, or is there genuinely no way through? Those are different facts and
        # gemma cannot tell them apart otherwise.
        code, extent = "UNREACHABLE", None
        if not (0 <= x < area.w and 0 <= y < area.h):
            # Off the edge of the arena, which is a different mistake from a cell
            # that exists and cannot be got to. Qualified rather than given its own
            # code, the way `UNREACHABLE(avoid)` already is.
            code, extent = "UNREACHABLE(off_map)", (area.w, area.h)
        elif avoid and plan(area, start, goal, frozenset()):
            code = "UNREACHABLE(avoid)"
        world.last_path = (area_name, [])
        publish(world, legs, goal, executor)
        return _log(world, area_name, start, goal, None,
                    Result(code, at=start, new=0, extent=extent),
                    why=why, heading=heading0)

    planned = len(path) - 1
    # The route as first planned. `path` is rebound by every replan, so logging it at
    # the end would file the last hypothesis under a `planned` length belonging to the
    # first -- a row that looks consistent and is not.
    first = list(path)
    world.last_path = (area_name, list(path))
    legs.append((list(path), start, heading0, None))
    publish(world, legs, goal, executor)
    reel.append(("plan", list(path)))

    if executor == "plan":
        # Plan and stop. The route file is the whole output: it keeps its actions,
        # because unlike a finished drive this one has not been carried out and the
        # actions are exactly what somebody is meant to read.
        #
        # Nothing moves, so no fog lifts, so the next plan from here is the same plan.
        # That is not a bug to route around -- it is what planning without driving
        # means, and `advice` says so rather than letting the model rediscover it.
        world.play(reel)
        return _log(world, area_name, start, goal, planned,
                    Result("PLANNED", at=start, planned=planned, new=0),
                    cells=first, why=why, heading=heading0)
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
        # The drive is over. Closing the last leg is what takes the file out of
        # "drive this" and into "here is what happened" -- leave it open and whatever
        # reads it goes on offering a route the rover has already finished.
        _close_leg(legs, code)
        publish(world, legs, goal, executor)
        if code in Result.GOOD:
            # Objective met. What comes next is a new journey even if it names the same
            # cell, so the accumulation stops here instead of growing without end.
            world.plan_goal = None
        return _log(world, area_name, start, goal, planned,
                    Result(code, steps=steps, walls=walls, **kw),
                    cells=first, walked=walk, why=why, heading=heading0)

    while True:
        wall = None
        for cell in path[1:]:
            if world.day_over:
                return done("OUT_OF_STEPS")

            if executor == "policy":
                leg = drive_leg(world, cell[0], cell[1], policy_act)
                steps += leg["charged"]
                for moved, revealed in leg["trail"]:
                    walk.append(moved)
                    gained |= set(revealed)
                    reel.append(("step", (moved, revealed)))
                if world.pos == cell:
                    continue
                # Not where A* sent it. A real wall gets the wall treatment;
                # wandering onto open ground just replans from where it is.
                if world.here.blocked(*cell):
                    wall = cell
                    if cell not in walls:
                        walls.append(cell)
                    reel.append(("block", cell))
                break

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
            pressed = False
            if executor == "policy" and world.pos in world.buttons:
                was_steps = world.steps
                pressed, _ = press_here(world, policy_act)
                steps += world.steps - was_steps
            return done("DONE", pressed=pressed)

        if replans <= 0:
            break
        replans -= 1
        path = plan(area, world.pos, goal, avoid)
        if path is None:
            _close_leg(legs, "BLOCKED")
            publish(world, legs, goal, executor)
            break                     # gemma calls goto again from wherever it is
        world.last_path = (area_name, list(path))
        _close_leg(legs, "SUPERSEDED")
        legs.append((list(path), world.pos, world.heading, None))
        publish(world, legs, goal, executor)
        reel.append(("plan", list(path)))

    return done("BLOCKED", at=wall, stopped=world.pos)


def price(world, x, y, avoid=None):
    """What a trip would cost and what it might buy: `(steps, reveals)`.

    `steps` alone answers the wrong question on an exploration mission -- which journey
    is shorter says nothing about which is worth taking. `reveals` walks the planned
    route, unions what the rover would see from each cell, and subtracts what it knows.

    The two numbers do not point the same way. `steps` is a floor for a trip that
    arrives, since the route is planned over fog assumed clear. `reveals` is not bounded
    at all: replanning round rock sweeps ground the straight route never passed, and in
    38 priced-then-driven trips nine revealed *more* than promised, worst 68 against an
    actual 112. So the result string says which is a floor and which is a guess.

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
