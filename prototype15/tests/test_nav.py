"""The planner plans over what the rover knows and nothing more. If the planner could
see through fog, nothing would look broken, so these tests check it can't."""

import os
import tempfile
from collections import deque

import config
import console
import nav
import settings
from nav import DIRS
from world import SOLID, THINGS, World


NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _roomy():
    """A world on the 50, with a recorder, for the route-file tests: they need a goal far enough off to force replans."""
    config.use("50")
    return World(recorder=lambda *a, **k: None)


def reference_bfs(rows, start, goal):
    """Plain BFS over the true grid with the planner's rules. On a fully seen arena A* must
    agree with it exactly: longer means the heuristic overestimates, shorter means it cheats."""
    def ch(cell):
        x, y = cell
        if not (0 <= x < len(rows[0]) and 0 <= y < len(rows)):
            return "#"
        return "." if rows[y][x] == "@" else rows[y][x]

    # Only a thing (the pad) gets the stop-beside-it rule. Rock doesn't.
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
    """A world with the whole arena already seen. A test shortcut: nothing in the game can do this."""
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
            assert config.ARENA[cell[1]][cell[0]] not in SOLID, (cell, path)
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)


def test_a_surveyed_arena_agrees_with_bfs():
    w = surveyed()
    pairs = [((15, 15), (3, 3)), ((15, 15), (27, 27)), ((1, 1), (27, 18)),
             ((0, 29), (15, 0)), ((15, 15), (15, 16))]  # the last is the pad
    for start, goal in pairs:
        path = nav.plan(w.here, start, goal)
        want = reference_bfs(config.ARENA, start, goal)
        assert path is not None and want is not None, (start, goal)
        assert len(path) - 1 == want, (start, goal, len(path) - 1, want)


def test_the_planner_is_not_omniscient():
    """A plan made through fog must drive straight into rock it has never met: that is what
    makes a blocked goto informative."""
    # West across the mouth of the C: the fogged plan goes through the spine it has never
    # met, so it comes out shorter than the truth. The truth is computed, not written down.
    truth = reference_bfs(config.ARENA, config.SPAWN, (2, 14))
    assert truth is not None, "(2,14) has to be reachable at all"

    w = World()  # only the landing site is seen
    path = nav.plan(w.here, w.pos, (2, 14))
    assert path, "fog has to be plannable through, or exploring is impossible"
    assert len(path) - 1 <= truth - 4, \
        (len(path) - 1, truth, "the fogged plan should be too good, by a real margin")
    assert any(config.ARENA[y][x] == "#" for x, y in path), \
        "a plan through fog that dodges unseen rock means the planner can see it"

    w2 = surveyed()
    real = nav.plan(w2.here, w2.pos, (2, 14))
    assert not any(config.ARENA[y][x] == "#" for x, y in real)
    assert len(real) - 1 == truth, (len(real) - 1, truth)


def test_only_one_door_onto_the_grid():
    """nav.known() is the single fog-gated read. A second `.at(` in that file is how
    the planner goes quietly omniscient, so fail loudly if one appears."""
    src = open(nav.__file__).read()
    assert src.count(".at(") == 1, "nav.py must reach the grid only through known()"


def test_distance_is_optimistic():
    """West across the C's mouth: 14 cells if the spine is assumed drivable, 18 once it is
    known. Every other crossing is a straight line the fog can't flatter."""
    w = World()
    guess = nav.price(w, 2, 14)
    truth = reference_bfs(config.ARENA, w.pos, (2, 14))
    assert guess is not None and guess < truth, (guess, truth)
    assert w.steps == 0, "distance must not cost a step"

    w2 = surveyed()
    assert nav.price(w2, 2, 14) == truth, "surveyed, it should be exact"


def test_the_arena_has_no_rim_wall():
    """The arena has no wall round it: the outer rows and columns are ordinary ground, as the
    prompt says."""
    w = surveyed()
    n = len(config.ARENA)
    edge = ([(x, 0) for x in range(n)] + [(x, n - 1) for x in range(n)] +
            [(0, y) for y in range(n)] + [(n - 1, y) for y in range(n)])
    open_edge = [c for c in edge if config.ARENA[c[1]][c[0]] == "."]
    assert len(open_edge) > len(edge) * 0.7, \
        f"only {len(open_edge)} of {len(edge)} edge cells are drivable"
    cx, cy = config.SPAWN
    for goal in ((cx, 0), (cx, n - 1), (0, cy), (0, n - 1)):
        assert nav.plan(w.here, config.SPAWN, goal), f"cannot reach the edge at {goal}"


# --- the drive --------------------------------------------------------------

def test_steps_charged_equal_tiles_driven():
    w = surveyed()
    before = w.steps
    r = nav.goto(w, 15, 16)  # the pad: solid, so land beside it
    assert r.code == "DONE", str(r)
    assert w.steps - before == r.steps == 0, (w.steps - before, r.steps)

    r = nav.goto(w, 15, 10)
    assert r.code == "DONE" and w.steps == r.steps == 5, (str(r), w.steps)


def test_a_solid_target_lands_you_next_to_it():
    """And the answer has to say so: DONE(at=(15,15)) for goto(15,16) reads as not having
    arrived. `beside` is only safe because known rock is refused first."""
    w = surveyed()
    w.pos = (12, 20)
    r = nav.goto(w, 15, 16)  # the base pad
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
    """"Get next to it" is for things you work on. Driving at rock already on the map is a
    mistake, and DONE would say she arrived somewhere she never went."""
    w = surveyed()
    w.pos = (16, 20)
    assert config.ARENA[20][17] == "#", "this test is about rock"

    r = nav.goto(w, 17, 20)
    assert r.code == "UNREACHABLE", str(r)
    assert w.steps == 0, "and it does not pretend to drive"

    # ...but rock she has not seen is still worth driving at; only known rock is refused. A
    # far boulder, since the landing site's reveal lights the near one.
    fresh = World()
    assert config.ARENA[2][20] == "#"
    assert not fresh.here.visible(20, 2), "needs to still be fogged"
    assert nav.plan(fresh.here, fresh.pos, (20, 2)) is not None, \
        "fogged rock must still be plannable, or exploring is impossible"


def test_rock_it_could_not_have_known_about_stops_the_drive():
    w = World()  # everything past the landing site is fog
    # Driven at a formation it can't see. A drive merely passing one walks around it and
    # reports DONE, listing the rock it met.
    r = nav.goto(w, 14, 9)
    assert r.code == "BLOCKED", str(r)
    assert r.walls, "every outcrop found on the way is reported"
    assert w.here.at(*r.at) == "#", r.at
    assert abs(r.stopped[0] - r.at[0]) + abs(r.stopped[1] - r.at[1]) == 1, \
        "it stops face to face with the rock, where the most map has been revealed"
    assert w.pos == r.stopped


def test_the_map_keeps_the_drive_as_well_as_the_plan():
    """The plan is replaced on every replan, so the drive is the record that survives, and
    unlike the plan it can never cross rock."""
    w = World()
    r = nav.goto(w, 10, 0)  # 20 through fog, 26 in fact: it must be surprised
    assert r.code in ("BLOCKED", "DONE"), str(r)

    area, walk = w.last_walk
    assert area == w.area and walk[0] == config.SPAWN and walk[-1] == w.pos
    assert len(walk) - 1 == r.steps, (len(walk) - 1, r.steps)
    for a, b in zip(walk, walk[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)
    for x, y in walk:
        assert config.ARENA[y][x] not in SOLID, ("the drive never crosses rock", x, y)

    # ...while a plan, made through fog, may still be wrong. Every plan the drive laid is
    # in the reel; last_path only holds the newest.
    plans = [cells for kind, cells in w.reel[-1] if kind == "plan"]
    assert plans, "a drive lays at least one plan"
    assert any(config.ARENA[y][x] == "#" for cells in plans for x, y in cells), \
        "some plan ran through rock nobody had seen -- that is what fog costs"

    nav.price(w, 15, 0)
    assert w.last_walk[1] == [], "pricing a trip drives nothing and should show nothing"


def test_a_drive_buys_the_map_it_drove_past():
    """`steps` is what a drive cost; `new` is the map it bought. Ground already seen buys
    nothing, and _stuck reads `new` to notice calls going nowhere."""
    w = World()
    first = nav.goto(w, 15, 10)
    assert first.code == "DONE" and first.new > 0, ("driving into fog buys map",
                                                    str(first))
    assert "new=" in str(first), str(first)
    assert first.steps > 0, ("it really did drive there", str(first))

    again = nav.goto(w, 15, 10)
    assert again.new == 0, ("standing still buys nothing", str(again))

    back = nav.goto(w, 15, 15)
    assert back.steps > 0, str(back)
    assert back.new == 0, ("...and neither does driving back over seen ground", str(back))

    # A refused drive went nowhere and revealed nothing, and both are true, so the
    # field is 0 rather than absent.
    seen_rock = surveyed()
    refused = nav.goto(seen_rock, 17, 20)  # rock it can already see, so UNREACHABLE
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


def test_running_into_rock_reveals_the_cell_that_stopped_the_drive():
    """Hitting rock reveals the cell hit, or the replan would return the same path and the
    rover would bump the same cell until NAV_REPLANS ran out. A drive that hits several
    distinct walls and still arrives proves it."""
    config.use("50")
    try:
        w = World()
        walls = set()
        for _ in range(12):
            r = nav.goto(w, 0, 0)
            assert r.new >= len(r.walls), ("a drive reveals at least its walls", str(r))
            walls |= set(r.walls)
            if r.code == "DONE":
                break
        else:
            raise AssertionError("twelve calls and it never arrived -- each one is "
                                 "bumping rock the next one still cannot see")

        assert len(walls) > 1, "the route through fog has to have hit something"
        for cell in walls:
            assert w.here.visible(*cell), f"{cell} was hit and is still fogged"
            assert cell not in w.here.visited, "hit, not stood on"
    finally:
        config.use(config.DEFAULT_ARENA)


def test_pricing_a_trip_says_what_it_costs_and_nothing_else():
    """distance returns one number: the steps."""
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
    d = nav.price(World(), 15, 27)
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
    # Two lines: the result, then the clause that says landing beside a solid target is arriving.
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
    """Northwest, past the formation at (9,3), so the drive costs more than the plan promised
    and both numbers are on the line."""
    w = World()
    nav.goto(w, 10, 0)
    last = w.nav_log[-1]
    assert last["planned"] < last["steps"] or last["code"] != "DONE", last
    assert last["area"] == config.ARENA_NAME and last["to"] == (10, 0)


def test_the_directions_replay_to_the_planned_path():
    """route_actions turns cells into the file's directions. A wrong DIRS order would send
    the rover somewhere else while the file looked fine, so drive it back and compare."""
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
    """Absolute directions: each of the four steps is one letter, whatever the rover's heading."""
    assert nav.route_actions([(5, 5), (5, 4)]) == ["N"]
    assert nav.route_actions([(5, 5), (6, 5)]) == ["E"]
    assert nav.route_actions([(5, 5), (5, 6)]) == ["S"]
    assert nav.route_actions([(5, 5), (4, 5)]) == ["W"]
    assert nav.route_actions([(5, 5)]) == []
    # Same two cells, same answer, however the rover got there. There is no heading
    # to pass in any more -- an extra argument would not even be accepted.
    assert set(nav.route_actions([(5, 5), (5, 4)])) <= set(nav.MOVES)


def test_the_live_file_is_rewritten_in_place_and_only_for_a_real_run():
    """A test world has no recorder, so it leaves nothing on disk. A real run rewrites the
    one file, so it always holds the current leg."""
    out = os.path.join(tempfile.gettempdir(), "reflex_live_plan.txt")
    keep = settings.PLAN_FILE
    settings.PLAN_FILE = out
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
        settings.PLAN_FILE = keep
        config.use(config.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)


def _legs_handed_over(w, *goto_args, **kw):
    """Every leg the robot was given, in order. `wait_for_rover` runs between the write and
    the wipe, the only moment the file holds anything, so this reads what the robot would."""
    seen = []

    def spy(world, dirs):
        on_disk = open(nav.plan_file(), encoding="utf-8").read().split()
        # What the pause is handed and what is on the file must be the same.
        assert on_disk == list(dirs), (on_disk, dirs)
        seen.append(on_disk)

    nav.wait_for_rover = spy
    try:
        r = nav.goto(w, *goto_args, **kw)
    finally:
        nav.wait_for_rover = None
    return r, seen


def test_the_robot_is_only_ever_handed_ground_the_simulation_drove():
    """The safety property the route file exists for: it holds only the cells the
    simulation actually drove, so the robot can never be pointed at rock."""
    out = os.path.join(tempfile.gettempdir(), "reflex_driven_only.txt")
    keep = settings.PLAN_FILE
    settings.PLAN_FILE = out
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
        settings.PLAN_FILE = keep
        if os.path.exists(out):
            os.remove(out)


def test_a_replan_hands_over_the_leg_before_planning_the_next_one():
    """Each leg is handed to the robot and driven before the next is planned: several
    handovers for one goto, not one at the end."""
    out = os.path.join(tempfile.gettempdir(), "reflex_pause.txt")
    keep = settings.PLAN_FILE
    settings.PLAN_FILE = out
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
        settings.PLAN_FILE = keep
        config.use(config.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)


def test_a_call_that_did_not_arrive_leaves_nothing_for_the_next_one():
    """The file is the leg being driven right now. The whole journey lives in the tape, so
    a finished goto leaves the file empty, however many tries it took."""
    out = os.path.join(tempfile.gettempdir(), "reflex_journey.txt")
    keep_file, keep_replans = settings.PLAN_FILE, settings.NAV_REPLANS
    settings.PLAN_FILE, settings.NAV_REPLANS = out, 0  # stop at the first wall, so it takes several
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
        settings.PLAN_FILE, settings.NAV_REPLANS = keep_file, keep_replans
        config.use(config.DEFAULT_ARENA)
        if os.path.exists(out):
            os.remove(out)
