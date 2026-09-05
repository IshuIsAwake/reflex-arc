"""Checks the planner plans over what the rover knows and nothing more.

    .venv/bin/python game/test_nav.py

The load-bearing ones are `test_the_planner_is_not_omniscient`,
`test_only_one_door_onto_the_grid` and
`test_a_known_rock_is_not_somewhere_you_can_arrive`. If any of them goes green for the
wrong reason the arena stops being a test of anything and nothing looks broken.
"""

import os
import tempfile
from collections import deque

import config as C
import console
import nav
import plan_txt
import settings as S
from nav import DIRS
from world import SOLID, THINGS, World

# Clear skies unless a suite asks otherwise. The weather is real and shipped on,
# but it is a scenario, not terrain -- letting one drift across an arena would make
# every route assertion here depend on STORM_RADIUS. `test_hazards.py` turns it on.
S.STORM_ON = False


NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _roomy():
    """A world on the 50, with a recorder, for the route-file tests.

    They need a goal far enough off to force replans, and (40,40) does not exist on
    the 30. `C.use` is put back by the runner at the bottom of the file.
    """
    C.use("50")
    return World(recorder=lambda *a, **k: None)


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
    for start, goal in (((15, 15), (3, 3)), ((1, 1), (27, 27)), ((15, 15), (15, 29))):
        path = nav.plan(w.here, start, goal)
        assert path, (start, goal)
        assert path[0] == start and len(path) == len(set(path)), path
        for cell in path:
            assert C.ARENA[cell[1]][cell[0]] not in SOLID, (cell, path)
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)


def test_a_surveyed_arena_agrees_with_bfs():
    w = surveyed()
    pairs = [((15, 15), (3, 3)), ((15, 15), (27, 27)), ((1, 1), (27, 18)),
             ((0, 29), (15, 0)), ((15, 15), (15, 16))]   # the last is the pad
    for start, goal in pairs:
        path = nav.plan(w.here, start, goal)
        want = reference_bfs(C.ARENA, start, goal)
        assert path is not None and want is not None, (start, goal)
        assert len(path) - 1 == want, (start, goal, len(path) - 1, want)


def test_the_planner_is_not_omniscient():
    """`Area.at()` returns ground truth whether or not the cell is fogged. A plan made
    through fog must therefore be a fantasy that drives straight into rock it has never
    met -- that is what makes a blocked goto informative and exploring worth doing."""
    # West across the mouth of the C: the fogged plan goes straight through the spine,
    # which it has never met, so it comes out shorter than the truth. A target where the
    # two happen to tie would pass this by luck, hence the margin. **The truth is
    # computed, not written down** -- it was hardcoded as 36 until 2026-08-30, which is a
    # number about one particular arena and not about the planner.
    #
    # The old note here said there was no slack left in the 4, that isolated convex
    # squares are cheap to walk around, and that if a future arena kept them convex and
    # separated this is the test that would fail first -- and that the fix would be
    # concave rock rather than a smaller margin. That is exactly what happened when the
    # 30 was rebuilt for prototype 10, and the C is the fix it called for.
    truth = reference_bfs(C.ARENA, C.SPAWN, (2, 14))
    assert truth is not None, "(2,14) has to be reachable at all"

    w = World()                      # only the landing site is seen
    path = nav.plan(w.here, w.pos, (2, 14))
    assert path, "fog has to be plannable through, or exploring is impossible"
    assert len(path) - 1 <= truth - 4, \
        (len(path) - 1, truth, "the fogged plan should be too good, by a real margin")
    assert any(C.ARENA[y][x] == "#" for x, y in path), \
        "a plan through fog that dodges unseen rock means the planner can see it"

    w2 = surveyed()
    real = nav.plan(w2.here, w2.pos, (2, 14))
    assert not any(C.ARENA[y][x] == "#" for x, y in real)
    assert len(real) - 1 == truth, (len(real) - 1, truth)


def test_only_one_door_onto_the_grid():
    """nav.known() is the single fog-gated read. A second `.at(` in that file is how
    the planner goes quietly omniscient, so fail loudly if one appears."""
    src = open(os.path.join(os.path.dirname(__file__), "nav.py")).read()
    assert src.count(".at(") == 1, "nav.py must reach the grid only through known()"


def test_distance_is_optimistic():
    """West across the C's mouth, which is the one route on this arena where fog hides
    a detour worth measuring: 14 cells if the spine is assumed drivable, 18 once it is
    known. Every other crossing is a straight line the fog cannot flatter."""
    w = World()
    guess = nav.distance(w, 2, 14)
    truth = reference_bfs(C.ARENA, w.pos, (2, 14))
    assert guess is not None and guess < truth, (guess, truth)
    assert w.steps == 0, "distance must not cost a step"

    w2 = surveyed()
    assert nav.distance(w2, 2, 14) == truth, "surveyed, it should be exact"


def test_the_arena_has_no_rim_wall():
    """Prototype 1 walled every area and 22% of gemma's calls were wasted on it: the
    prompt says aim far, the far thing was the border, and a known wall is deliberately
    UNREACHABLE. Here the outer rows and columns are ordinary ground and the system
    prompt says so, which only stays true while this passes."""
    w = surveyed()
    n = len(C.ARENA)
    edge = ([(x, 0) for x in range(n)] + [(x, n - 1) for x in range(n)] +
            [(0, y) for y in range(n)] + [(n - 1, y) for y in range(n)])
    open_edge = [c for c in edge if C.ARENA[c[1]][c[0]] == "."]
    assert len(open_edge) > len(edge) * 0.7, \
        f"only {len(open_edge)} of {len(edge)} edge cells are drivable"
    cx, cy = C.SPAWN
    for goal in ((cx, 0), (cx, n - 1), (0, cy), (0, n - 1)):
        assert nav.plan(w.here, C.SPAWN, goal), f"cannot reach the edge at {goal}"


# --- the drive --------------------------------------------------------------

def test_steps_charged_equal_tiles_driven():
    w = surveyed()
    before = w.steps
    r = nav.goto(w, 15, 16)          # the pad: solid, so land beside it
    assert r.code == "DONE", str(r)
    assert w.steps - before == r.steps == 0, (w.steps - before, r.steps)

    r = nav.goto(w, 15, 10)
    assert r.code == "DONE" and w.steps == r.steps == 5, (str(r), w.steps)


def test_a_solid_target_lands_you_next_to_it():
    """And the answer has to say so. `DONE(at=(15,15))` for a `goto(15,16)` reads as
    not having arrived, and gemma asked for the same cell three times running on
    2026-08-25. `beside` is only safe because known rock is refused before this can
    fire -- see test_a_known_rock_is_not_somewhere_you_can_arrive, the other half of
    the same rule."""
    w = surveyed()
    w.pos = (12, 20)
    r = nav.goto(w, 15, 16)          # the base pad
    assert r.code == "DONE", str(r)
    assert w.pos in _around((15, 16)), w.pos
    assert r.beside == (15, 16) and "beside=(15,16)" in str(r), str(r)
    assert "IS arriving" in r.advice, r.advice

    # An ordinary cell says nothing, or every answer carries the noise.
    r = nav.goto(w, 13, 21)
    assert r.code == "DONE" and r.beside is None, str(r)

    # Rock never gets one, because it never gets a DONE to hang it on.
    w.pos = (16, 20)
    assert nav.goto(w, 17, 20).beside is None, "rock is UNREACHABLE, not beside"


def test_a_known_rock_is_not_somewhere_you_can_arrive():
    """"Get next to it" is for things you interact with. Rock already on the map is a
    mistake, and answering DONE says you arrived somewhere you never went -- which
    leaves the caller nothing to correct. It cost four days on 2026-08-26."""
    w = surveyed()
    w.pos = (16, 20)
    assert C.ARENA[20][17] == "#", "this test is about rock"

    r = nav.goto(w, 17, 20)
    assert r.code == "UNREACHABLE", str(r)
    assert w.steps == 0, "and it does not pretend to drive"

    # ...but rock it has *not* seen stays a hypothesis worth driving into, which is the
    # whole design. Only known rock is refused. A far boulder, because BASE_REVEAL lights
    # up six cells and the one above is inside that.
    fresh = World()
    assert C.ARENA[2][20] == "#"
    assert not fresh.here.visible(20, 2), "needs to still be fogged"
    assert nav.plan(fresh.here, fresh.pos, (20, 2)) is not None, \
        "fogged rock must still be plannable, or exploring is impossible"


def test_rock_it_could_not_have_known_about_stops_the_drive():
    w = World()                      # everything past the landing site is fog
    # Driven *at* a formation it cannot see. On a sparse arena of rectangles that is the
    # way to earn a BLOCKED: with NAV_REPLANS at 5, a drive merely *passing* one walks
    # around it and still reports DONE, listing the rock it met in `walls`. The C is the
    # other way, and `test_distance_is_optimistic` drives across its mouth.
    r = nav.goto(w, 14, 9)
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
    r = nav.goto(w, 10, 0)           # 20 through fog, 26 in fact: it must be surprised
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

    nav.distance(w, 15, 0)
    assert w.last_walk[1] == [], "pricing a trip drives nothing and should show nothing"


def test_a_drive_buys_no_map_at_all():
    """`steps` says what it cost; `new` is the map it bought, and it is always zero
    unless the rover ran into something.

    This is prototype 7's assertion inverted. There, a drive that revealed nothing was
    the failure worth catching. Here it is every drive, by construction, and the only
    non-zero `new` a drive can produce is the cell it collided with.
    """
    w = World()
    first = nav.goto(w, 15, 10)
    assert first.code == "DONE" and first.new == 0, str(first)
    assert "new=" in str(first), str(first)
    assert first.steps > 0, ("it really did drive there", str(first))

    again = nav.goto(w, 15, 10)
    assert again.new == 0, ("standing still buys nothing either", str(again))

    back = nav.goto(w, 15, 15)
    assert back.steps > 0, str(back)
    assert back.new == 0, str(back)

    # A refused drive went nowhere and revealed nothing, and both are true, so the
    # field is 0 rather than absent.
    seen_rock = surveyed()
    refused = nav.goto(seen_rock, 17, 20)     # rock it can already see, so UNREACHABLE
    assert refused.code.startswith("UNREACHABLE"), str(refused)
    assert refused.new == 0, str(refused)

    # `distance` builds a Result only to log it. Claiming it revealed nothing would be
    # a statement about a trip nobody took, so the field stays off.
    assert nav.Result("DISTANCE").new is None
    assert "new=" not in str(nav.Result("DISTANCE"))

    # And it reaches the game log, which is where the map a sol bought gets computed
    # from without reading a transcript by hand.
    w2 = World()
    logged = nav.goto(w2, 15, 10)
    assert w2.nav_log[-1]["new"] == logged.new, w2.nav_log[-1]


def test_running_into_rock_is_the_only_thing_driving_reveals():
    """Contact reveals the cell hit, and nothing else. This is what stops the replan
    loop deadlocking.

    `_passable` treats fog as clear, so a rock the rover cannot see is a rock the
    planner routes straight back into. With no reveal on contact the replan returns the
    identical path, the rover bumps the same cell until NAV_REPLANS runs out, and every
    drive into unmapped ground dies at the first obstacle. The proof that it does not is
    a drive that hits *several distinct* walls and still arrives.
    """
    C.use("50")
    try:
        w = World()
        before = set(w.here.seen)
        walls = set()
        for _ in range(12):
            r = nav.goto(w, 0, 0)
            assert r.new == len(r.walls), ("a drive reveals its walls and nothing "
                                           "else", str(r))
            walls |= set(r.walls)
            if r.code == "DONE":
                break
        else:
            raise AssertionError("twelve calls and it never arrived -- each one is "
                                 "bumping rock the next one still cannot see")

        assert len(walls) > 1, "the route through fog has to have hit something"
        assert w.here.seen - before == walls, \
            ("exactly the walls, and not one cell of the route it drove",
             sorted(w.here.seen - before))
        for cell in walls:
            assert w.here.visible(*cell), f"{cell} was hit and is still fogged"
            assert cell not in w.here.visited, "hit, not stood on"
    finally:
        C.use(C.DEFAULT_ARENA)


def test_pricing_a_trip_says_what_it_costs_and_nothing_else():
    """Prototype 7 returned `(steps, reveals)`. Driving reveals nothing here, so the
    second number was always zero and is gone rather than shipped as a constant --
    a field that can only ever hold one value teaches the caller a false rule.
    """
    w = World()
    steps = nav.price(w, 15, 27)
    assert isinstance(steps, int) and steps > 0, steps

    # A floor, not a quote: the route is planned over fog assumed clear, so the drive
    # itself can only come out longer.
    driven = nav.goto(w, 15, 27)
    assert driven.steps >= steps, (steps, str(driven))

    # No route, no number -- and a bare None, not a pair.
    surveyed_w = surveyed()
    assert nav.price(surveyed_w, 33, 30) is None

    # `distance` still hands back the bare integer four other call sites rely on.
    d = nav.distance(World(), 15, 27)
    assert isinstance(d, int) and d > 0, d


def test_unreachable_says_whether_the_avoid_list_caused_it():
    w = surveyed()
    w.pos = (15, 15)
    # A ring around the rover and the pad it is standing on, so nothing can get out.
    fence = [(15, 14), (14, 15), (16, 15), (13, 16), (13, 17), (17, 16), (17, 17),
             (14, 18), (15, 18), (16, 18)]
    r = nav.goto(w, 10, 20, avoid=fence)
    assert r.code == "UNREACHABLE(avoid)", str(r)
    assert w.steps == 0, "a refused plan costs nothing"

    assert nav.goto(w, 10, 20).code == "DONE", "and without the fence it is fine"


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
    nav.goto(w, 15, 10)
    assert w.pos == (15, 10)
    w.toggle_mark((15, 12))
    r = nav.goto(w, 15, 15, avoid="auto")
    assert r.code == "DONE" and w.pos == (15, 15), str(r)
    assert (15, 12) not in w.last_walk[1], "it drove through the cell it was told to dodge"


# --- the console ------------------------------------------------------------

def test_the_console_parses_what_a_human_would_type():
    assert console._parse("goto 15 10") == ("goto", [(15, 10)], None)
    assert console._parse("goto (15,10)") == ("goto", [(15, 10)], None)
    assert console._parse("goto 15 10 avoid=auto")[2] == "auto"
    assert console._parse("goto 15 10 avoid=(3,4),(5,6)")[2] == frozenset({(3, 4), (5, 6)})

    w = surveyed()
    w.pos = (12, 20)
    # Two lines: the code form, then the clause that says landing beside a solid target
    # is arriving. The human is shown the same words gemma is, laid out for a console
    # that truncates -- so check both, not just the last.
    pad = console.run(w, "goto 15 16")
    assert "DONE" in pad[1][0], pad
    assert "IS arriving" in pad[-1][0], pad
    assert all(len(text) < 88 for text, _ in pad), "a truncated explanation is worse"
    before = w.steps
    assert console.run(w, "distance 5 5")[-1][0].startswith("distance to")
    assert w.steps == before, "distance must not have cost anything"
    assert console.run(w, "fly 1 2")[-1][1] == "bad"
    assert len(console.run(w, "help")) == len(console.HELP) + 1


def test_the_log_records_what_the_plan_promised():
    """Northwest, past the formation at (9,3), so the drive costs more than the plan
    promised and both numbers are on the line. Due north is a clean 15 either way, and
    a log that only ever agreed with itself would not be recording anything."""
    w = World()
    nav.goto(w, 10, 0)
    last = w.nav_log[-1]
    assert last["planned"] < last["steps"] or last["code"] != "DONE", last
    assert last["area"] == C.ARENA_NAME and last["to"] == (10, 0)


def test_the_directions_replay_to_the_planned_path():
    """The one that matters. `route_actions` turns cells into the directions the file
    speaks, and getting the DIRS order wrong lands the rover somewhere else while the
    file still looks perfectly reasonable. So drive it back and compare.
    """
    w = World()
    path = nav.plan(w.here, w.pos, (25, 5))
    assert path and len(path) > 3, path
    dirs = nav.route_actions(path)

    pos, walked = path[0], [path[0]]
    for d in dirs:
        step = DIRS[nav.HEADING_NAMES.index(d)]
        pos = (pos[0] + step[0], pos[1] + step[1])
        walked.append(pos)
    assert walked == path, (walked, path)
    # One direction a cell, and no turns anywhere -- that is the whole point of going
    # absolute. A file longer than the path means turn arithmetic crept back in.
    assert len(dirs) == len(path) - 1


def test_a_direction_is_the_step_and_nothing_else():
    """Absolute, so each of the four steps is one letter regardless of what the rover
    was doing before. The old encoding spent a turn plus a FORWARD on three of these
    and had a BACKWARD for the fourth; all of it was arithmetic against a heading
    nobody measured."""
    assert nav.route_actions([(5, 5), (5, 4)]) == ["N"]
    assert nav.route_actions([(5, 5), (6, 5)]) == ["E"]
    assert nav.route_actions([(5, 5), (5, 6)]) == ["S"]
    assert nav.route_actions([(5, 5), (4, 5)]) == ["W"]
    assert nav.route_actions([(5, 5)]) == []
    # Same two cells, same answer, however the rover got there. There is no heading
    # to pass in any more -- an extra argument would not even be accepted.
    assert set(nav.route_actions([(5, 5), (5, 4)])) <= set(nav.MOVES)


def test_writing_a_plan_drives_nothing():
    """`plan_txt` exists to produce a file and no motion. A regression here is
    silent: the file still gets written, and the rover has spent the day."""
    out = os.path.join(tempfile.gettempdir(), "reflex_plan_check.txt")
    w = World()
    before = (w.pos, w.steps, len(w.here.seen))
    try:
        assert plan_txt.main(["--to", "25", "5", "--out", out]) == 0
        lines = open(out, encoding="utf-8").read().splitlines()
    finally:
        if os.path.exists(out):
            os.remove(out)
    assert lines and set(lines) <= set(nav.MOVES), lines
    # Nothing to skip. No header, no comments, no coordinates -- a reader that drives
    # every line it finds is a correct reader, and that is the whole format.
    assert not [l for l in lines if l.startswith("#")], lines
    # plan_txt builds its own throwaway World; this one must be untouched.
    assert (w.pos, w.steps, len(w.here.seen)) == before


def test_planning_offline_never_writes_the_file_the_rover_drives():
    """`plan_txt` writes a route nobody has driven, and the live file is defined as
    ground the simulation has already been over. Same format, opposite guarantee, so
    the default must not be the live file -- it used to be."""
    keep = S.PLAN_FILE
    S.PLAN_FILE = os.path.join(tempfile.gettempdir(), "reflex_live_must_not_move.txt")
    try:
        if os.path.exists(S.PLAN_FILE):
            os.remove(S.PLAN_FILE)
        out = os.path.join(tempfile.gettempdir(), "reflex_preview.txt")
        assert plan_txt.main(["--to", "25", "5", "--out", out]) == 0
        assert not os.path.exists(S.PLAN_FILE), "offline planning wrote the live file"
    finally:
        S.PLAN_FILE = keep
        for f in (out, ):
            if os.path.exists(f):
                os.remove(f)


def test_an_unreachable_target_empties_the_file_rather_than_leaving_it():
    """The dangerous failure is not a missing file, it is the last good route still
    sitting there after the planner has given up -- somebody drives it."""
    out = os.path.join(tempfile.gettempdir(), "reflex_nope.txt")
    rock = [(x, y) for y in range(len(C.ARENA))
            for x in range(len(C.ARENA[0])) if C.ARENA[y][x] == "#"]
    assert rock, "the arena has no wall to aim at"
    try:
        assert plan_txt.main(["--to", "5", "5", "--survey", "--out", out]) == 0
        assert open(out, encoding="utf-8").read().split(), "no route written"
        assert plan_txt.main(["--to", str(rock[0][0]), str(rock[0][1]),
                              "--survey", "--out", out]) == 1
        left = open(out, encoding="utf-8").read()
    finally:
        if os.path.exists(out):
            os.remove(out)
    # Empty, and empty means empty: not a blank line, which splits into one move.
    assert left == "", repr(left)
    assert [l for l in left.splitlines() if l.strip()] == []


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

        w = _roomy()
        nav.goto(w, 25, 5)
        # The wipe. The robot has replayed the last leg and stopped, so there is
        # nothing left to drive -- an old route lying here is one somebody picks up.
        assert open(out, encoding="utf-8").read() == "", "the file was left loaded"

        nav.goto(w, 5, 25)
        assert open(out, encoding="utf-8").read() == ""
        # One file, rewritten. A backlog is a reader having to work out the order.
        assert len([f for f in os.listdir(os.path.dirname(out))
                    if f.startswith("reflex_live_plan")]) == 1
    finally:
        S.PLAN_FILE = keep
        C.use(C.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)


def _legs_handed_over(w, *goto_args, **kw):
    """Every leg the robot was actually given, in order.

    `_await_rover` runs between the write and the wipe, which is the only moment the
    file holds anything -- so standing in for the robot there reads exactly what the
    robot would have read, and proves the pause sits between the two.
    """
    seen = []
    real = nav._await_rover

    def spy(world, dirs):
        on_disk = open(nav.plan_file(), encoding="utf-8").read().split()
        # What the pause is handed and what is actually on the file are two ways of
        # saying the same thing, and a demo that showed one while the robot drove the
        # other would be lying on screen.
        assert on_disk == list(dirs), (on_disk, dirs)
        seen.append(on_disk)

    nav._await_rover = spy
    try:
        r = nav.goto(w, *goto_args, **kw)
    finally:
        nav._await_rover = real
    return r, seen


def test_the_robot_is_only_ever_handed_ground_the_simulation_drove():
    """The safety property the whole seam exists for.

    `goto` plans over fog it assumes is drivable, so a plan routinely runs into rock
    nobody knew about. The old file held that plan. This one holds the prefix that
    worked, written *after* the drive -- so a hypothesis that turns out wrong costs a
    replan instead of a collision, and there is no arrangement of the file in which
    the robot is pointed at an outcrop.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_driven_only.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        # Fogged, so (14,9) drives into rock it cannot see -- the case the whole
        # write-after-driving order exists for. A recorder, or nothing is written.
        w = World(recorder=lambda *a, **k: None)
        r, legs = _legs_handed_over(w, 14, 9)
        assert r.code == "BLOCKED" and r.walls, str(r)
        assert legs, "the rover drove and the robot was handed nothing"

        # Replay every direction it was given and see where that lands. Every cell
        # must be one the simulation stood on -- never the wall it stopped at.
        pos = w.last_walk[1][0]
        for leg in legs:
            for d in leg:
                step = DIRS[nav.HEADING_NAMES.index(d)]
                pos = (pos[0] + step[0], pos[1] + step[1])
                assert w.here.at(*pos) != "#", f"handed a move into rock at {pos}"
        assert pos == w.pos, (pos, w.pos)
        assert pos != r.at, "the robot was driven onto the wall the sim stopped at"
    finally:
        S.PLAN_FILE = keep
        if os.path.exists(out):
            os.remove(out)


def test_a_replan_hands_over_the_leg_before_planning_the_next_one():
    """The pause, and the reason it is the demo. The robot is behind the simulation
    from the moment a leg is planned, and a route computed from a cell it has not
    reached yet belongs to somebody else. So each leg goes over and is driven before
    the next is worked out -- several handovers for one `goto`, not one at the end."""
    out = os.path.join(tempfile.gettempdir(), "reflex_pause.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        w = _roomy()
        # (40,40) is rock, so this replans its way across the arena and ends BLOCKED.
        r, legs = _legs_handed_over(w, 40, 40)
        assert r.code == "BLOCKED", str(r)
        assert len(legs) > 1, f"a replanning drive handed over once: {legs}"
        assert all(leg for leg in legs), f"an empty leg went over: {legs}"
        assert all(set(leg) <= set(nav.MOVES) for leg in legs), legs
        # Every leg together is the whole walk, in order and without repeats. A leg
        # sent twice is the rover driving a stretch it has already covered.
        assert sum(len(leg) for leg in legs) == len(w.last_walk[1]) - 1
    finally:
        S.PLAN_FILE = keep
        C.use(C.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)


def test_planning_only_moves_nothing_and_writes_nothing():
    """`executor="plan"` has exactly one job and one way to fail badly.

    It used to write its route out, which the seam no longer permits: this file says
    what the rover *did*, and a plan call drives nothing at all. Writing here would
    put the one thing the robot must never receive -- an untested hypothesis -- into
    the one file it reads. The other failure is silent, a plan call that charges a
    step or lifts a cell of fog, and nothing on screen would say so.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_plan_only.txt")
    keep = S.PLAN_FILE
    S.PLAN_FILE = out
    try:
        if os.path.exists(out):
            os.remove(out)
        w = _roomy()
        before = (w.pos, w.steps, len(w.here.seen), len(w.here.visited))
        r = nav.goto(w, 12, 4, executor="plan")
        after = (w.pos, w.steps, len(w.here.seen), len(w.here.visited))
        wrote = os.path.exists(out)
    finally:
        S.PLAN_FILE = keep
        C.use(C.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)

    assert after == before, (before, after)
    assert r.code == "PLANNED" and r.steps == 0, str(r)
    assert not wrote, "a plan nobody drove reached the file the robot reads"


def test_a_call_that_did_not_arrive_leaves_nothing_for_the_next_one():
    """Gemma calls `goto` again from wherever a BLOCKED one stopped, and prototype 9
    kept those calls in the file as one accumulating journey.

    The seam ends that. The file is the leg being driven right now, and the journey --
    every wall, every detour -- lives in the tape instead. So what a call leaves behind
    is nothing at all, however many times it took, and the file is never a backlog the
    robot has to work out the order of.
    """
    out = os.path.join(tempfile.gettempdir(), "reflex_journey.txt")
    keep_file, keep_replans = S.PLAN_FILE, S.NAV_REPLANS
    S.PLAN_FILE, S.NAV_REPLANS = out, 0     # stop at the first wall, so it takes several
    try:
        w = _roomy()
        nav.clear_plan(w)

        handed = 0
        for _ in range(4):
            r, legs = _legs_handed_over(w, 2, 2)
            handed += len(legs)
            assert open(out, encoding="utf-8").read() == "", "a route was left behind"
            if r.code == "DONE":
                break
        assert handed, "several calls and the robot was never given anything"
    finally:
        S.PLAN_FILE, S.NAV_REPLANS = keep_file, keep_replans
        C.use(C.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    C.use(C.DEFAULT_ARENA)   # `_roomy` pins the 50; leave the module as we found it
    print("all nav checks passed")
