"""Checks the planner plans over what the rover knows and nothing more.

    .venv/bin/python game/test_nav.py

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
from world import SOLID, THINGS, World

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
    pairs = [((15, 15), (3, 3)), ((15, 15), (27, 27)), ((1, 1), (26, 18)),
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
    # Due north of the pad, behind the boulder at (14,5): the fogged plan drives straight
    # up through rock it has never met, so it comes out shorter than the truth. A target
    # where the two happen to tie would pass this by luck, hence the margin. **The truth
    # is computed, not written down** -- it was hardcoded as 36 until 2026-08-30, which is
    # a number about one particular arena and not about the planner.
    #
    # There is no slack left in that 4. Isolated convex squares are cheap to walk around,
    # so this arena's most misleading route is misleading by exactly four cells; the old
    # one managed twelve. If a future arena keeps the boulders convex and separated, this
    # is the test that fails first, and the fix is concave rock, not a smaller margin.
    truth = reference_bfs(C.ARENA, C.SPAWN, (15, 0))
    assert truth is not None, "(15,0) has to be reachable at all"

    w = World()                      # only the landing site is seen
    path = nav.plan(w.here, w.pos, (15, 0))
    assert path, "fog has to be plannable through, or exploring is impossible"
    assert len(path) - 1 <= truth - 4, \
        (len(path) - 1, truth, "the fogged plan should be too good, by a real margin")
    assert any(C.ARENA[y][x] == "#" for x, y in path), \
        "a plan through fog that dodges unseen rock means the planner can see it"

    w2 = surveyed()
    real = nav.plan(w2.here, w2.pos, (15, 0))
    assert not any(C.ARENA[y][x] == "#" for x, y in real)
    assert len(real) - 1 == truth, (len(real) - 1, truth)


def test_only_one_door_onto_the_grid():
    """nav.known() is the single fog-gated read. A second `.at(` in that file is how
    the planner goes quietly omniscient, so fail loudly if one appears."""
    src = open(os.path.join(os.path.dirname(__file__), "nav.py")).read()
    assert src.count(".at(") == 1, "nav.py must reach the grid only through known()"


def test_distance_is_optimistic():
    w = World()
    guess = nav.distance(w, 15, 0)
    truth = reference_bfs(C.ARENA, w.pos, (15, 0))
    assert guess is not None and guess < truth, (guess, truth)
    assert w.steps == 0, "distance must not cost a step"

    w2 = surveyed()
    assert nav.distance(w2, 15, 0) == truth, "surveyed, it should be exact"


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
    w.pos = (18, 11)
    assert nav.goto(w, 19, 11).beside is None, "rock is UNREACHABLE, not beside"


def test_a_known_rock_is_not_somewhere_you_can_arrive():
    """"Get next to it" is for things you interact with. Rock already on the map is a
    mistake, and answering DONE says you arrived somewhere you never went -- which
    leaves the caller nothing to correct. It cost four days on 2026-08-26."""
    w = surveyed()
    w.pos = (18, 11)
    assert C.ARENA[11][19] == "#", "this test is about rock"

    r = nav.goto(w, 19, 11)
    assert r.code == "UNREACHABLE", str(r)
    assert w.steps == 0, "and it does not pretend to drive"

    # ...but rock it has *not* seen stays a hypothesis worth driving into, which is the
    # whole design. Only known rock is refused. A far boulder, because BASE_REVEAL lights
    # up six cells and the one above is inside that.
    fresh = World()
    assert C.ARENA[9][26] == "#"
    assert not fresh.here.visible(26, 9), "needs to still be fogged"
    assert nav.plan(fresh.here, fresh.pos, (26, 9)) is not None, \
        "fogged rock must still be plannable, or exploring is impossible"


def test_rock_it_could_not_have_known_about_stops_the_drive():
    w = World()                      # everything past the landing site is fog
    # Driven *at* a boulder it cannot see. Since the arena went sparse and convex, that
    # is the only way to earn a BLOCKED: with NAV_REPLANS at 5, a drive merely *passing*
    # a 3x3 walks around it and still reports DONE, listing the rock it met in `walls`.
    r = nav.goto(w, 26, 9)
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
    r = nav.goto(w, 15, 0)           # 15 through fog, 19 in fact: it must be surprised
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


def test_a_drive_says_how_much_map_it_bought():
    """`steps` says what it cost; `new` says what it was worth.

    The failure this exists for: on 2026-08-29 gemma spent 439 steps, 358 of them
    revealing nothing, bouncing between corners it had already mapped. Every answer
    read `DONE(at=..., steps=49)` -- indistinguishable from the fourteen drives that
    had actually opened the arena up. A success code that cannot tell a useful call
    from a wasted one leaves the caller nothing to correct.
    """
    w = World()
    first = nav.goto(w, 15, 10)
    assert first.code == "DONE" and first.new > 0, str(first)
    assert "new=" in str(first), str(first)

    again = nav.goto(w, 15, 10)
    assert again.new == 0, ("standing still buys nothing", str(again))

    # ...and driving back down ground already surveyed buys nothing either, which is
    # the case that matters: it spends real steps and reads as a success.
    back = nav.goto(w, 15, 15)
    assert back.steps > 0, str(back)
    assert back.new == 0, ("a repeat down a mapped corridor", str(back))

    # A refused drive went nowhere and revealed nothing, and both are true, so the
    # field is 0 rather than absent.
    seen_rock = surveyed()
    refused = nav.goto(seen_rock, 19, 11)     # rock it can already see, so UNREACHABLE
    assert refused.code.startswith("UNREACHABLE"), str(refused)
    assert refused.new == 0, str(refused)

    # `distance` builds a Result only to log it. Claiming it revealed nothing would be
    # a statement about a trip nobody took, so the field stays off.
    assert nav.Result("DISTANCE").new is None
    assert "new=" not in str(nav.Result("DISTANCE"))

    # And it reaches the game log, which is where "358 of 439 steps bought nothing"
    # gets computed from without reading a transcript by hand.
    w2 = World()
    logged = nav.goto(w2, 15, 10)
    assert w2.nav_log[-1]["new"] == logged.new, w2.nav_log[-1]


def test_pricing_a_trip_says_what_it_might_buy():
    """`steps` is what it costs; `reveals` is why you would bother.

    Ordering journeys by length answers the wrong question on an exploration mission --
    "thirty against fifty" says which is shorter and nothing about which is worth
    taking. Gemma called `distance` zero times in twenty-seven calls on 2026-08-29, and
    a skill that only prices is a plausible reason why.
    """
    w = World()
    steps, reveals = nav.price(w, 15, 27)
    assert steps and reveals > 0, (steps, reveals)

    # Down a corridor it has already surveyed, the trip is worth nothing, and the
    # number has to say so rather than being quietly omitted.
    surveyed_w = surveyed()
    steps, reveals = nav.price(surveyed_w, 15, 27)
    assert steps > 0 and reveals == 0, (steps, reveals)

    # Never negative, never larger than the fog that is actually left.
    w2 = World()
    left = len(C.ARENA) * len(C.ARENA[0]) - len(w2.here.seen)
    _, big = nav.price(w2, 0, 29)
    assert 0 < big <= left, (big, left)

    # No route, no promise.
    assert nav.price(surveyed_w, 33, 30) == (None, 0)

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
    w = World()
    nav.goto(w, 15, 0)
    last = w.nav_log[-1]
    assert last["planned"] < last["steps"] or last["code"] != "DONE", last
    assert last["area"] == C.ARENA_NAME and last["to"] == (15, 0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all nav checks passed")
