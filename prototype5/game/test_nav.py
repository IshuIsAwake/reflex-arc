r"""Checks the planner plans over what the rover knows and nothing more.

    ..\.venv\Scripts\python.exe game\test_nav.py

The load-bearing ones are `test_the_planner_is_not_omniscient`,
`test_only_one_door_onto_the_grid` and
`test_a_known_rock_is_not_somewhere_you_can_arrive`. If any of them goes green for the
wrong reason the arena stops being a test of anything and nothing looks broken.
"""

import os
from collections import deque

import config as C
import console
import nav
import plan_txt
import settings as S
import tempfile
from world import DIRS, SOLID, THINGS, World

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def reference_bfs(rows, start, goal):
    """Plain BFS over the true grid with the planner's own rules about what is
    drivable. On a fully-surveyed arena A* must agree with this exactly -- if it ever
    comes out longer the heuristic is overestimating, and if shorter it is cheating.
    """
    def ch(cell):
        x, y = cell
        if not (0 <= x < len(rows[0]) and 0 <= y < len(rows)):
            return "#"
        return "." if rows[y][x] == "@" else rows[y][x]

    # Only a *thing* gets the "stop beside it" rule. Rock does not -- widen this to
    # SOLID and the reference quietly starts agreeing with the bug nav is written to
    # avoid, which is the one way a test like this can go green for nothing.
    targets = {goal}
    if ch(goal) in THINGS:
        targets = {n for n in _around(goal) if ch(n) not in SOLID}

    dist, q = {start: 0}, deque([start])
    while q:
        cur = q.popleft()
        if cur in targets:
            return dist[cur]
        for n in _around(cur):
            if n in dist or ch(n) in SOLID:
                continue
            dist[n] = dist[cur] + 1
            q.append(n)
    return None


def _around(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBOURS]


def surveyed():
    """A world with the whole arena already seen, so there is no fog to reason about.

    There is no map to buy in prototype 2 -- ground is earned by driving over it -- so
    the tests reach into `Area.seen` directly. That is a test shortcut and the only
    one; nothing in the game can do this.
    """
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    return w


# --- the planner ------------------------------------------------------------

def test_never_routes_through_known_rock():
    w = surveyed()
    for start, goal in (((25, 25), (5, 5)), ((2, 2), (45, 45)), ((25, 25), (25, 49))):
        path = nav.plan(w.here, start, goal)
        assert path, (start, goal)
        assert path[0] == start and len(path) == len(set(path)), path
        for cell in path:
            assert C.ARENA[cell[1]][cell[0]] not in SOLID, (cell, path)
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)


def test_a_surveyed_arena_agrees_with_bfs():
    w = surveyed()
    pairs = [((25, 25), (5, 5)), ((25, 25), (45, 45)), ((2, 2), (44, 30)),
             ((0, 49), (25, 0)), ((25, 25), (25, 26))]   # the last is the pad
    for start, goal in pairs:
        path = nav.plan(w.here, start, goal)
        want = reference_bfs(C.ARENA, start, goal)
        assert path is not None and want is not None, (start, goal)
        assert len(path) - 1 == want, (start, goal, len(path) - 1, want)


def test_the_planner_is_not_omniscient():
    """`Area.at()` returns ground truth whether or not the cell is fogged. A plan made
    through fog must therefore be a fantasy that drives straight into rock it has never
    met -- that is what makes a blocked goto informative and exploring worth doing."""
    # (25,49) is 24 cells away as the crow flies and a good deal more by any real route,
    # so a plan that comes out shorter than the truth is one that has driven through rock
    # on paper. A target where the two happen to tie would pass this by luck, hence the
    # margin. **The truth is computed, not written down** -- it was hardcoded as 36 until
    # 2026-08-30, which is a number about one particular arena and not about the planner.
    truth = reference_bfs(C.ARENA, C.SPAWN, (25, 49))
    assert truth is not None, "(25,49) has to be reachable at all"

    w = World()                      # only the landing site is seen
    path = nav.plan(w.here, w.pos, (25, 49))
    assert path, "fog has to be plannable through, or exploring is impossible"
    assert len(path) - 1 <= truth - 4, \
        (len(path) - 1, truth, "the fogged plan should be too good, by a real margin")
    assert any(C.ARENA[y][x] == "#" for x, y in path), \
        "a plan through fog that dodges unseen rock means the planner can see it"

    w2 = surveyed()
    real = nav.plan(w2.here, w2.pos, (25, 49))
    assert not any(C.ARENA[y][x] == "#" for x, y in real)
    assert len(real) - 1 == truth, (len(real) - 1, truth)


def test_only_one_door_onto_the_grid():
    """nav.known() is the single fog-gated read. A second `.at(` in that file is how
    the planner goes quietly omniscient, so fail loudly if one appears."""
    src = open(os.path.join(os.path.dirname(__file__), "nav.py")).read()
    assert src.count(".at(") == 1, "nav.py must reach the grid only through known()"


def test_distance_is_optimistic():
    w = World()
    guess = nav.distance(w, 25, 49)
    truth = reference_bfs(C.ARENA, w.pos, (25, 49))
    assert guess is not None and guess < truth, (guess, truth)
    assert w.steps == 0, "distance must not cost a step"

    w2 = surveyed()
    assert nav.distance(w2, 25, 49) == truth, "surveyed, it should be exact"


def test_the_arena_has_no_rim_wall():
    """Prototype 1 walled every area and 22% of gemma's calls were wasted on it: the
    prompt says aim far, the far thing was the border, and a known wall is deliberately
    UNREACHABLE. Here the outer rows and columns are ordinary ground and the system
    prompt says so, which only stays true while this passes."""
    w = surveyed()
    edge = ([(x, 0) for x in range(50)] + [(x, 49) for x in range(50)] +
            [(0, y) for y in range(50)] + [(49, y) for y in range(50)])
    open_edge = [c for c in edge if C.ARENA[c[1]][c[0]] == "."]
    assert len(open_edge) > len(edge) * 0.7, \
        f"only {len(open_edge)} of {len(edge)} edge cells are drivable"
    for goal in ((25, 0), (25, 49), (0, 25), (0, 49)):
        assert nav.plan(w.here, (25, 25), goal), f"cannot reach the edge at {goal}"


# --- the drive --------------------------------------------------------------

def test_steps_charged_equal_tiles_driven():
    w = surveyed()
    before = w.steps
    r = nav.goto(w, 25, 26)          # the pad: solid, so land beside it
    assert r.code == "DONE", str(r)
    assert w.steps - before == r.steps == 0, (w.steps - before, r.steps)

    r = nav.goto(w, 25, 20)
    assert r.code == "DONE" and w.steps == r.steps == 5, (str(r), w.steps)


def test_a_solid_target_lands_you_next_to_it():
    """And the answer has to say so. `DONE(at=(25,25))` for a `goto(25,26)` reads as
    not having arrived, and gemma asked for the same cell three times running on
    2026-08-25. `beside` is only safe because known rock is refused before this can
    fire -- see test_a_known_rock_is_not_somewhere_you_can_arrive, the other half of
    the same rule."""
    w = surveyed()
    w.pos = (20, 20)
    r = nav.goto(w, 25, 26)          # the base pad
    assert r.code == "DONE", str(r)
    assert w.pos in _around((25, 26)), w.pos
    assert r.beside == (25, 26) and "beside=(25,26)" in str(r), str(r)
    assert "IS arriving" in r.advice, r.advice

    # An ordinary cell says nothing, or every answer carries the noise.
    r = nav.goto(w, 22, 22)
    assert r.code == "DONE" and r.beside is None, str(r)

    # Rock never gets one, because it never gets a DONE to hang it on.
    w.pos = (32, 29)
    assert nav.goto(w, 33, 29).beside is None, "rock is UNREACHABLE, not beside"


def test_a_known_rock_is_not_somewhere_you_can_arrive():
    """"Get next to it" is for things you interact with. Rock already on the map is a
    mistake, and answering DONE says you arrived somewhere you never went -- which
    leaves the caller nothing to correct. It cost four days on 2026-08-26."""
    w = surveyed()
    w.pos = (32, 29)
    assert C.ARENA[29][33] == "#", "this test is about rock"

    r = nav.goto(w, 33, 29)
    assert r.code == "UNREACHABLE", str(r)
    assert w.steps == 0, "and it does not pretend to drive"

    # ...but rock it has *not* seen stays a hypothesis worth driving into, which is the
    # whole design. Only known rock is refused.
    fresh = World()
    assert not fresh.here.visible(33, 29), "needs to still be fogged"
    assert nav.plan(fresh.here, fresh.pos, (33, 29)) is not None, \
        "fogged rock must still be plannable, or exploring is impossible"


def test_rock_it_could_not_have_known_about_stops_the_drive():
    w = World()                      # everything past the landing site is fog
    r = nav.goto(w, 25, 5)
    assert r.code == "BLOCKED", str(r)
    assert r.walls, "every outcrop found on the way is reported"
    assert w.here.at(*r.at) == "#", r.at
    assert abs(r.stopped[0] - r.at[0]) + abs(r.stopped[1] - r.at[1]) == 1, \
        "it stops face to face with the rock, where the most map has been revealed"
    assert w.pos == r.stopped


def test_the_map_keeps_the_drive_as_well_as_the_plan():
    """The plan is thrown away on every replan, so after a blocked goto the drawing
    explains neither the rock reported nor where the rover ended up standing. The drive
    is the record that survives, and unlike the plan it can never cross rock -- which
    is what makes the two worth drawing together."""
    w = World()
    r = nav.goto(w, 25, 49)          # 24 through fog, 36 in fact: it must be surprised
    assert r.code in ("BLOCKED", "DONE"), str(r)

    area, walk = w.last_walk
    assert area == w.area and walk[0] == C.SPAWN and walk[-1] == w.pos
    assert len(walk) - 1 == r.steps, (len(walk) - 1, r.steps)
    for a, b in zip(walk, walk[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)
    for x, y in walk:
        assert C.ARENA[y][x] not in SOLID, ("the drive never crosses rock", x, y)

    # ...while a plan, made through fog, is still allowed to be wrong.
    #
    # Ask the reel, not `last_path`: that field holds only the newest hypothesis, so a
    # drive that replans through to DONE leaves behind the one plan that turned out
    # right. Every plan the drive actually laid is in the reel.
    plans = [cells for kind, cells in w.reel[-1] if kind == "plan"]
    assert plans, "a drive lays at least one plan"
    assert any(C.ARENA[y][x] == "#" for cells in plans for x, y in cells), \
        "some plan ran through rock nobody had seen -- that is what fog costs"

    nav.distance(w, 25, 49)
    assert w.last_walk[1] == [], "pricing a trip drives nothing and should show nothing"


def test_a_drive_says_how_much_map_it_bought():
    """`steps` says what it cost; `new` says what it was worth.

    The failure this exists for: on 2026-08-29 gemma spent 439 steps, 358 of them
    revealing nothing, bouncing between corners it had already mapped. Every answer
    read `DONE(at=..., steps=49)` -- indistinguishable from the fourteen drives that
    had actually opened the arena up. A success code that cannot tell a useful call
    from a wasted one leaves the caller nothing to correct.
    """
    w = World()
    first = nav.goto(w, 25, 20)
    assert first.code == "DONE" and first.new > 0, str(first)
    assert "new=" in str(first), str(first)

    again = nav.goto(w, 25, 20)
    assert again.new == 0, ("standing still buys nothing", str(again))

    # ...and driving back down ground already surveyed buys nothing either, which is
    # the case that matters: it spends real steps and reads as a success.
    back = nav.goto(w, 25, 25)
    assert back.steps > 0, str(back)
    assert back.new == 0, ("a repeat down a mapped corridor", str(back))

    # A refused drive went nowhere and revealed nothing, and both are true, so the
    # field is 0 rather than absent.
    seen_rock = surveyed()
    refused = nav.goto(seen_rock, 33, 29)     # rock it can already see, so UNREACHABLE
    assert refused.code.startswith("UNREACHABLE"), str(refused)
    assert refused.new == 0, str(refused)

    # `distance` builds a Result only to log it. Claiming it revealed nothing would be
    # a statement about a trip nobody took, so the field stays off.
    assert nav.Result("DISTANCE").new is None
    assert "new=" not in str(nav.Result("DISTANCE"))

    # And it reaches the game log, which is where "358 of 439 steps bought nothing"
    # gets computed from without reading a transcript by hand.
    w2 = World()
    logged = nav.goto(w2, 25, 20)
    assert w2.nav_log[-1]["new"] == logged.new, w2.nav_log[-1]


def test_pricing_a_trip_says_what_it_might_buy():
    """`steps` is what it costs; `reveals` is why you would bother.

    Ordering journeys by length answers the wrong question on an exploration mission --
    "thirty against fifty" says which is shorter and nothing about which is worth
    taking. Gemma called `distance` zero times in twenty-seven calls on 2026-08-29, and
    a skill that only prices is a plausible reason why.
    """
    w = World()
    steps, reveals = nav.price(w, 25, 45)
    assert steps and reveals > 0, (steps, reveals)

    # Down a corridor it has already surveyed, the trip is worth nothing, and the
    # number has to say so rather than being quietly omitted.
    surveyed_w = surveyed()
    steps, reveals = nav.price(surveyed_w, 25, 45)
    assert steps > 0 and reveals == 0, (steps, reveals)

    # Never negative, never larger than the fog that is actually left.
    w2 = World()
    left = 2500 - len(w2.here.seen)
    _, big = nav.price(w2, 0, 49)
    assert 0 < big <= left, (big, left)

    # No route, no promise.
    assert nav.price(surveyed_w, 33, 30) == (None, 0)

    # `distance` still hands back the bare integer four other call sites rely on.
    d = nav.distance(World(), 25, 45)
    assert isinstance(d, int) and d > 0, d


def test_unreachable_says_whether_the_avoid_list_caused_it():
    w = surveyed()
    w.pos = (25, 25)
    fence = [(24, 25), (26, 25), (25, 24), (25, 28), (24, 28), (26, 28),
             (23, 26), (23, 27), (27, 26), (27, 27)]
    r = nav.goto(w, 20, 20, avoid=fence)
    assert r.code == "UNREACHABLE(avoid)", str(r)
    assert w.steps == 0, "a refused plan costs nothing"

    assert nav.goto(w, 20, 20).code == "DONE", "and without the fence it is fine"


def test_auto_is_only_legal_somewhere_it_has_stood():
    w = surveyed()
    assert (5, 5) not in w.here.visited
    assert nav.goto(w, 5, 5, avoid="auto").code == "NOT_VISITED"
    assert w.steps == 0
    assert nav.goto(w, 5, 5).code == "DONE", "naming it by hand is fine"


def test_a_marked_cell_is_driven_around():
    """`avoid="auto"` is the human's X list. Gemma cannot mark a cell yet -- `mark()`
    is not built -- which is exactly why `skills` refuses `avoid=auto` by name."""
    w = surveyed()
    nav.goto(w, 25, 20)
    assert w.pos == (25, 20)
    w.toggle_mark((25, 22))
    r = nav.goto(w, 25, 25, avoid="auto")
    assert r.code == "DONE" and w.pos == (25, 25), str(r)
    assert (25, 22) not in w.last_walk[1], "it drove through the cell it was told to dodge"


# --- the console ------------------------------------------------------------

def test_the_console_parses_what_a_human_would_type():
    assert console._parse("goto 15 10") == ("goto", [(15, 10)], None)
    assert console._parse("goto (15,10)") == ("goto", [(15, 10)], None)
    assert console._parse("goto 15 10 avoid=auto")[2] == "auto"
    assert console._parse("goto 15 10 avoid=(3,4),(5,6)")[2] == frozenset({(3, 4), (5, 6)})

    w = surveyed()
    w.pos = (20, 20)
    # Two lines: the code form, then the clause that says landing beside a solid target
    # is arriving. The human is shown the same words gemma is, laid out for a console
    # that truncates -- so check both, not just the last.
    pad = console.run(w, "goto 25 26")
    assert "DONE" in pad[1][0], pad
    assert "IS arriving" in pad[-1][0], pad
    assert all(len(text) < 88 for text, _ in pad), "a truncated explanation is worse"
    before = w.steps
    assert console.run(w, "distance 5 5")[-1][0].startswith("distance to")
    assert w.steps == before, "distance must not have cost anything"
    assert console.run(w, "fly 1 2")[-1][1] == "bad"
    assert len(console.run(w, "help")) == len(console.HELP) + 1


def test_the_log_records_what_the_plan_promised():
    w = World()
    nav.goto(w, 25, 5)
    last = w.nav_log[-1]
    assert last["planned"] < last["steps"] or last["code"] != "DONE", last
    assert last["area"] == C.ARENA_NAME and last["to"] == (25, 5)


def test_the_actions_replay_to_the_planned_path():
    """The one that matters. `route_actions` turns absolute cells into turns and a
    facing, and every way of getting that wrong -- sign of the turn, order of DIRS,
    forgetting to carry the heading -- lands the rover somewhere else while the file
    still looks perfectly reasonable. So drive the file back and compare.
    """
    w = World()
    path = nav.plan(w.here, w.pos, (25, 5))
    assert path and len(path) > 3, path
    actions, end = nav.route_actions(path, 0)

    pos, h, walked = path[0], 0, [path[0]]
    for a in actions:
        if a == "LEFT":
            h = (h - 1) % 4
        elif a == "RIGHT":
            h = (h + 1) % 4
        else:
            sign = -1 if a == "BACKWARD" else 1
            pos = (pos[0] + sign * DIRS[h][0], pos[1] + sign * DIRS[h][1])
            walked.append(pos)
    assert walked == path, (walked, path)
    assert h == end, (h, end)
    assert sum(a in ("FORWARD", "BACKWARD") for a in actions) == len(path) - 1


def test_going_backwards_costs_one_move_and_no_turn():
    """The (want - heading) % 4 == 2 case, which a random arena route may never hit.

    Reversing must not become a U-turn: that is two turns' worth of heading error
    spent to reach a cell one move away, and it fails by being merely wasteful rather
    than by being wrong. The heading staying put is the half that is easy to lose --
    the rover moved, it did not turn.
    """
    facing_north = 0
    assert nav.route_actions([(5, 5), (5, 6)], facing_north) == (["BACKWARD"], 0)
    assert nav.route_actions([(5, 5), (4, 5)], 0) == (["LEFT", "FORWARD"], 3)
    assert nav.route_actions([(5, 5), (6, 5)], 0) == (["RIGHT", "FORWARD"], 1)
    assert nav.route_actions([(5, 5), (5, 4)], 0) == (["FORWARD"], 0)
    assert nav.route_actions([(5, 5)], 2) == ([], 2)


def test_writing_a_plan_drives_nothing():
    """`plan_txt` exists to produce a file and no motion. A regression here is
    silent: the file still gets written, and the rover has spent the day."""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_plan_check.txt")
    w = World()
    before = (w.pos, w.steps, w.heading, len(w.here.seen))
    try:
        assert plan_txt.main(["--to", "25", "5", "--out", out]) == 0
        lines = open(out, encoding="utf-8").read().splitlines()
    finally:
        if os.path.exists(out):
            os.remove(out)
    body = [l for l in lines if not l.startswith("#")]
    assert body and set(body) <= set(nav.MOVES), body
    assert lines[0].startswith("# reflex-arc live route"), lines[0]
    # plan_txt builds its own throwaway World; this one must be untouched.
    assert (w.pos, w.steps, w.heading, len(w.here.seen)) == before


def test_an_unreachable_target_empties_the_file_rather_than_leaving_it():
    """The dangerous failure is not a missing file, it is the last good route still
    sitting there after the planner has given up -- somebody drives it."""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_nope.txt")
    rock = [(x, y) for y in range(len(C.ARENA))
            for x in range(len(C.ARENA[0])) if C.ARENA[y][x] == "#"]
    assert rock, "the arena has no wall to aim at"
    try:
        assert plan_txt.main(["--to", "5", "5", "--survey", "--out", out]) == 0
        assert "FORWARD" in open(out, encoding="utf-8").read()
        assert plan_txt.main(["--to", str(rock[0][0]), str(rock[0][1]),
                              "--survey", "--out", out]) == 1
        left = open(out, encoding="utf-8").read()
    finally:
        if os.path.exists(out):
            os.remove(out)
    assert "NO ROUTE" in left and "FORWARD" not in left, left


def test_the_live_file_is_rewritten_in_place_and_only_for_a_real_run():
    """Two halves, both of which fail silently if they break.

    A test world has no recorder, so it must leave nothing on disk -- otherwise every
    suite drops a route where the next reader will find it and believe it.

    A real run rewrites the one file instead of adding another, so what is on disk is
    the current plan and never a backlog somebody has to work out the order of.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_live_plan.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        if os.path.exists(out):
            os.remove(out)
        nav.goto(World(), 25, 5)
        assert not os.path.exists(out), "a test with no recorder wrote a plan file"

        w = World(recorder=lambda *a, **k: None)
        nav.goto(w, 25, 5)
        first = open(out, encoding="utf-8").read()
        assert "# goal (25,5)" in first, first[:200]

        nav.goto(w, 5, 25)
        second = open(out, encoding="utf-8").read()
        assert second.count("# reflex-arc live route") == 1, "the file accumulated"
        assert "# goal (5,25)" in second and "# goal (25,5)" not in second

        # The safety property, and the reason the file exists in this shape: the RL
        # reads it and drives what it finds. A finished route still executable is a
        # rover that does the trip twice. Strip the comments and nothing may remain.
        # Strip the comments and nothing may remain -- the RL reads this file and a
        # finished route left executable is a rover that drives the trip twice.
        assert not [l for l in second.splitlines() if not l.startswith("#")], second
        # ...but the moves must still be legible, or the file is useless to watch.
        assert any(l.startswith("# FORWARD") for l in second.splitlines()), second
    finally:
        S.PLAN_FILE = keep
        if os.path.exists(out):
            os.remove(out)


def test_planning_only_writes_the_route_and_moves_nothing():
    """`executor="plan"` has exactly one job and one way to fail badly.

    The job: a route file with drivable actions still in it, unlike a finished drive
    which strips them. The failure that matters is silent -- a plan call that charges
    a step or lifts a cell of fog is a rover that moved when it was told not to, and
    nothing on screen would say so.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_plan_only.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        w = World(recorder=lambda *a, **k: None)
        before = (w.pos, w.steps, w.heading, len(w.here.seen), len(w.here.visited))
        r = nav.goto(w, 12, 4, executor="plan")
        after = (w.pos, w.steps, w.heading, len(w.here.seen), len(w.here.visited))
        body = [l for l in open(out, encoding="utf-8").read().splitlines()
                if not l.startswith("#")]
    finally:
        S.PLAN_FILE = keep
        if os.path.exists(out):
            os.remove(out)

    assert after == before, (before, after)
    assert r.code == "PLANNED" and r.steps == 0, str(r)
    moves = sum(b in ("FORWARD", "BACKWARD") for b in body)
    assert r.planned == moves, (r.planned, moves)
    assert set(body) <= set(nav.MOVES) and body, body
    assert "plan file" in r.advice, r.advice

def test_every_decision_is_logged_whole_and_consistent():
    """One row per decision, with enough in it to train on and nothing in it that
    contradicts the rest of the row.

    The failure this catches is quiet and poisons a dataset rather than crashing:
    `path` is rebound by every replan, so logging it at the end files the last
    hypothesis under the `planned` length of the first. Every row still parses, and
    the routes no longer match the numbers beside them.
    """
    rows = []
    w = World(recorder=lambda kind, **f: rows.append(dict(kind=kind, **f)))
    r = nav.goto(w, 12, 4, why="drive it")
    row = [x for x in rows if x["kind"] == "nav"][-1]

    assert row["planned"] == len(row["cells"]) - 1, (row["planned"], len(row["cells"]))
    assert row["cells"][0] == (25, 25), "cells must start where the rover did"
    assert row["walked"][0] == (25, 25) and row["walked"][-1] == w.pos
    assert len(row["walked"]) - 1 == r.steps == row["steps"]
    assert row["why"] == "drive it" and row["heading"] == 0
    # The actions are not stored, so they must still be derivable from what is.
    actions, _ = nav.route_actions(row["cells"], row["heading"])
    assert sum(a in ("FORWARD", "BACKWARD") for a in actions) == row["planned"]

def test_a_cell_off_the_map_says_so_rather_than_just_unreachable():
    """Measured on a live run 2026-09-04: gemma asked for goto(50,15) on a 50-wide
    arena twenty-eight times in a row, 14 minutes of model time, and never moved.

    Bare `UNREACHABLE` is also what a walled-in cell returns, so nothing in the answer
    could tell it the cell did not exist. The failure mode is a loop, not an error --
    every reply was true, and none of them was news.
    """
    w = World()
    off = nav.goto(w, w.here.w, 15)
    assert off.code == "UNREACHABLE(off_map)", off.code
    assert "not on the map" in off.advice
    assert f"0 to {w.here.w - 1}" in off.advice, off.advice
    assert w.pos == C.SPAWN and w.steps == 0, "an off-map ask must cost nothing"

    # A cell that exists and cannot be reached is still the plain code -- widen the
    # bounds check by accident and this is what stops saying the right thing.
    walled = nav.goto(w, 0, 0)
    assert walled.code in ("UNREACHABLE", "DONE", "BLOCKED"), walled.code
    assert "not on the map" not in walled.advice

def test_the_file_keeps_every_leg_of_one_objective_and_only_one_is_runnable():
    """A drive that replans is several routes, not one, and the file is the story of
    all of them -- the first hypothesis, each wall that broke it, what was tried next.

    The dangerous half is the other one. However many legs pile up, at most a single
    leg may be left uncommented: whatever reads this file strips `#` and drives the
    rest, and two runnable legs is a rover driving one route and then an older one it
    had already abandoned.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_legs.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        w = World(recorder=lambda *a, **k: None)
        # (40,40) is rock, so this replans its way across the arena and ends BLOCKED.
        r = nav.goto(w, 40, 40)
        text = open(out, encoding="utf-8").read()

        # Same objective throughout, and more than one leg to show for it.
        legs = [l for l in text.splitlines() if l.startswith("# leg ")]
        assert len(legs) > 1, text
        assert text.count("# goal ") == 1 and "# goal (40,40)" in text
        assert r.code == "BLOCKED", str(r)

        # A finished drive leaves nothing to run; every move is behind a `#`.
        assert not [l for l in text.splitlines() if not l.startswith("#")], text
        assert sum(l[2:] in nav.MOVES for l in text.splitlines()) > 1

        # A live plan leaves exactly one leg runnable.
        nav.goto(w, 5, 5, executor="plan")
        live = open(out, encoding="utf-8").read().splitlines()
        assert [l for l in live if l.startswith("# leg ")][-1].count("LIVE") == 1
        assert all(l in nav.MOVES for l in live if not l.startswith("#"))
        assert "# goal (40,40)" not in "\n".join(live), "a new objective starts fresh"
    finally:
        S.PLAN_FILE = keep
        if os.path.exists(out):
            os.remove(out)

def test_the_journey_survives_calls_until_the_objective_is_reached():
    """Being blocked and trying again is one journey, not several.

    `goto` returning BLOCKED does not mean the rover gave up on the goal -- gemma
    calls again from wherever it stopped. If the file reset on each of those, it would
    show the last leg of a five-call struggle and nothing of the four that produced it,
    which is exactly the history worth keeping.

    Arriving is what ends it. Without that the list grows for the rest of the run.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_journey.txt")
    keep_file, keep_replans = S.PLAN_FILE, S.NAV_REPLANS
    S.PLAN_FILE, S.NAV_REPLANS = out, 0     # stop at the first wall, so it takes several
    try:
        w = World(recorder=lambda *a, **k: None)
        nav.clear_plan(w)

        def legs():
            return [l for l in open(out, encoding="utf-8").read().splitlines()
                    if l.startswith("# leg ")]

        seen = []
        for _ in range(4):
            r = nav.goto(w, 2, 2)
            seen.append(len(legs()))
            if r.code == "DONE":
                break
        assert seen == sorted(seen) and seen[-1] > 1, seen
        assert seen[-1] == len(seen), "one call that did not arrive, one leg kept"

        # Each attempt starts where the last one stopped -- that is what makes the
        # legs one journey rather than four unrelated routes.
        text = open(out, encoding="utf-8").read()
        assert text.count("# goal ") == 1 and "# goal (2,2)" in text

        # Arriving ends it: the next call is a new journey even at the same cell.
        while nav.goto(w, 2, 2).code != "DONE":
            pass
        nav.goto(w, 2, 2)
        assert len(legs()) == 1, legs()
    finally:
        S.PLAN_FILE, S.NAV_REPLANS = keep_file, keep_replans
        if os.path.exists(out):
            os.remove(out)

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all nav checks passed")
