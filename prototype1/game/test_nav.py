"""Checks the planner plans over what gemma knows and nothing more.

    .venv/bin/python game/test_nav.py

The load-bearing ones are `test_the_planner_is_not_omniscient` and
`test_an_unmarked_pit_is_still_walked_into`. If either goes green for the wrong
reason the world stops being a test of anything and nothing looks broken.
"""

import os
from collections import deque

import config as C
import console
import nav
import settings as S
from world import GATES, SOLID, World

NEIGHBOURS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def reference_bfs(rows, start, goal):
    """Plain BFS over the true grid with the planner's own rules about what is
    walkable. On a fully-mapped area A* must agree with this exactly -- if it ever
    comes out longer the heuristic is overestimating, and if shorter it is cheating.
    """
    def ch(cell):
        x, y = cell
        if not (0 <= x < len(rows[0]) and 0 <= y < len(rows)):
            return "#"
        return {"^": ".", "@": "."}.get(rows[y][x], rows[y][x])

    targets = {goal}
    if ch(goal) in SOLID:
        targets = {n for n in _around(goal) if ch(n) not in SOLID and ch(n) not in GATES}

    dist, q = {start: 0}, deque([start])
    while q:
        cur = q.popleft()
        if cur in targets:
            return dist[cur]
        for n in _around(cur):
            c = ch(n)
            if n in dist or c in SOLID or (c in GATES and n not in targets):
                continue
            dist[n] = dist[cur] + 1
            q.append(n)
    return None


def _around(cell):
    return [(cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBOURS]


def mapped():
    """A world with every map bought, so there is no fog to reason about."""
    w = World()
    for a in w.areas.values():
        a.has_map = True
    return w


# --- the planner ------------------------------------------------------------

def test_never_routes_through_a_known_wall():
    w = mapped()
    for start, goal in (((10, 14), (18, 1)), ((1, 7), (19, 3)), ((2, 8), (10, 15))):
        path = nav.plan(w.areas["plaza"], start, goal)
        assert path, (start, goal)
        assert path[0] == start and len(path) == len(set(path)), path
        for cell in path:
            assert C.PLAZA[cell[1]][cell[0]] not in SOLID, (cell, path)
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, (a, b)


def test_a_mapped_area_agrees_with_bfs():
    w = mapped()
    pairs = [("plaza", (10, 14), (18, 1)), ("plaza", (1, 1), (10, 16)),
             ("savana", (1, 16), (30, 16)), ("savana", (1, 16), (27, 5)),
             ("savana2", (15, 1), (1, 1)), ("savana2", (15, 1), (30, 20))]
    for name, start, goal in pairs:
        path = nav.plan(w.areas[name], start, goal)
        want = reference_bfs(C.AREAS[name], start, goal)
        assert path is not None and want is not None, (name, start, goal)
        assert len(path) - 1 == want, (name, start, goal, len(path) - 1, want)


def test_the_planner_is_not_omniscient():
    """`Area.at()` returns ground truth whether or not the cell is fogged. A plan
    made through fog must therefore be a fantasy that walks straight into walls it
    has never met -- that is what makes a blocked goto informative and a map worth
    buying."""
    w = World()                      # plaza, no map yet, sees a radius of 3
    path = nav.plan(w.here, w.pos, (19, 1))
    assert path, "fog has to be plannable through, or exploring is impossible"
    assert any(C.PLAZA[y][x] == "#" for x, y in path), \
        "a plan through fog that dodges unseen walls means the planner can see them"

    w.here.has_map = True
    assert not any(C.PLAZA[y][x] == "#" for x, y in nav.plan(w.here, w.pos, (19, 1)))


def test_only_one_door_onto_the_grid():
    """nav.known() is the single fog-gated read. A second `.at(` in that file is how
    the planner goes quietly omniscient, so fail loudly if one appears."""
    src = open(os.path.join(os.path.dirname(__file__), "nav.py")).read()
    assert src.count(".at(") == 1, "nav.py must reach the grid only through known()"


def test_distance_is_optimistic():
    w = World()
    guess = nav.distance(w, 19, 1)
    truth = reference_bfs(C.PLAZA, w.pos, (19, 1))
    assert guess is not None and guess < truth, (guess, truth)
    assert w.steps == 0, "distance must not cost a step"

    w.here.has_map = True
    assert nav.distance(w, 19, 1) == truth, "with the map it should be exact"


def test_gates_are_aimed_at_never_routed_through():
    w = mapped()
    for name in C.AREAS:
        a = w.areas[name]
        gates = [c for (ar, c) in C.LINKS if ar == name]
        for start, goal in (((1, 1), (a.w - 2, a.h - 2)), ((a.w - 2, 1), (1, a.h - 2))):
            if a.blocked(*start) or a.blocked(*goal):
                continue
            path = nav.plan(a, start, goal) or []
            assert not (set(path) & set(gates)), (name, path)


# --- the walk ---------------------------------------------------------------

def test_steps_charged_equal_tiles_walked():
    w = mapped()
    before = w.steps
    r = nav.goto(w, 10, 16)          # the shop counter: solid, so land beside it
    assert r.code == "DONE", str(r)
    assert w.steps - before == r.steps == 1, (w.steps - before, r.steps)


def test_a_solid_target_lands_you_next_to_it():
    w = World()
    r = nav.goto(w, 3, 8)            # the notice board
    assert r.code == "DONE", str(r)
    assert w.pos in _around((3, 8)), w.pos
    w.interact()
    assert w.here.has_map, "goto then interact should just work"


def test_a_known_wall_is_not_somewhere_you_can_arrive():
    """"Get next to it" is for things you interact with. A wall already on the map
    is a mistake, and answering DONE says you arrived somewhere you never went --
    which leaves the caller nothing to correct. It cost four days on 2026-08-26."""
    w = mapped()
    w.pos = (10, 15)
    assert C.PLAZA[15][9] == "#", "this test is about a wall"

    r = nav.goto(w, 9, 15)
    assert r.code == "UNREACHABLE", str(r)
    assert w.steps == 0, "and it does not pretend to walk"

    # ...but a wall it has *not* seen stays a hypothesis worth walking into, which
    # is the whole design. Only known walls are refused.
    fresh = World()
    fresh.pos = (10, 15)
    assert not fresh.here.visible(9, 6), "needs to still be fogged"
    assert nav.plan(fresh.here, fresh.pos, (9, 6)) is not None, \
        "a fogged wall must still be plannable, or exploring is impossible"


def test_a_shut_gate_stops_you_beside_it_and_an_open_one_lets_you_through():
    w = mapped()
    r = nav.goto(w, 20, 13)          # the east gate, still locked
    assert r.code == "DONE" and w.pos == (19, 13), (str(r), w.pos)

    w.items.add("savana_key")
    w.interact()
    assert ("plaza", (20, 13)) in w.unlocked

    r = nav.goto(w, 20, 13)
    assert r.code == "LEFT_AREA" and r.area == "savana", str(r)
    assert (w.area, w.pos) == ("savana", (1, 16)), (w.area, w.pos)


def test_a_wall_it_could_not_have_known_about_stops_the_walk():
    w = World()                      # no plaza map: the north maze is all fog
    r = nav.goto(w, 10, 0)
    assert r.code in ("BLOCKED", "DONE"), str(r)
    assert r.code == "BLOCKED", "a straight line north runs into the maze"
    assert r.walls, "every wall found on the way is reported"
    assert w.here.at(*r.at) == "#", r.at
    assert abs(r.stopped[0] - r.at[0]) + abs(r.stopped[1] - r.at[1]) == 1, \
        "it stops face to face with the wall, where the most map has been revealed"
    assert w.pos == r.stopped


def test_unreachable_says_whether_the_avoid_list_caused_it():
    w = mapped()
    assert nav.goto(w, 0, 0).code == "UNREACHABLE", "inside the outer wall"

    fence = [(9, 15), (11, 15), (10, 14)]     # seal the shop alcove off
    w.pos = (10, 15)
    r = nav.goto(w, 10, 16, avoid=fence)
    assert r.code == "DONE", str(r)            # already adjacent, nothing to walk

    w.pos = (10, 13)
    r = nav.goto(w, 10, 16, avoid=fence)
    assert r.code == "UNREACHABLE(avoid)", str(r)
    assert w.steps == 0, "a refused plan costs nothing"


# --- pits, antidotes and avoid ---------------------------------------------

def test_an_antidote_absorbs_a_pit_and_the_walk_carries_on():
    """Antidotes come before traps: one pit with an antidote in the bag is a note to
    write down, not a reason to hand control back. The second one, with the pouch
    empty, ends the trip because it puts gemma in another room."""
    w = mapped()
    w.here.traps.update({(12, 14), (14, 14)})
    w.antidotes = 1

    r = nav.goto(w, 16, 14)
    assert r.code == "TRAPPED", str(r)
    assert r.at == (14, 14), r.at
    assert r.antidotes == [(12, 14)], r.antidotes
    assert r.steps == 4, r.steps
    assert w.pos == C.PLAZA_SPAWN and w.antidotes == 0


def test_an_unmarked_pit_is_still_walked_into():
    """The one that has to stay red. If falling in ever marks the cell for you, the
    notes file stops being the thing under test and the avoid mechanic is dead."""
    w = mapped()
    r = nav.goto(w, 16, 14)
    assert r.code == "DONE" and (16, 14) in w.here.visited

    w.here.traps.add((13, 14))
    nav.goto(w, 10, 14)
    r = nav.goto(w, 16, 14, avoid="auto")
    assert r.code == "TRAPPED" and r.at == (13, 14), str(r)
    assert (13, 14) not in w.here.marks, "the world must never mark a pit for gemma"

    w.toggle_mark((13, 14))          # now gemma has written it down
    r = nav.goto(w, 16, 14, avoid="auto")
    assert r.code == "DONE" and w.pos == (16, 14), str(r)


def test_auto_is_only_legal_somewhere_it_has_stood():
    w = mapped()
    assert (27, 5) not in w.areas["savana"].visited
    w.area, w.pos = "savana", (1, 16)
    assert nav.goto(w, 27, 5, avoid="auto").code == "NOT_VISITED"
    assert w.steps == 0
    assert nav.goto(w, 27, 5).code in ("DONE", "TRAPPED"), "naming it by hand is fine"


def test_the_planner_never_sees_a_pit():
    w = mapped()
    for a in w.areas.values():
        for x, y in a.traps:
            assert nav.known(a, x, y) == ".", (a.name, x, y)


# --- the console ------------------------------------------------------------

def test_the_console_parses_what_a_human_would_type():
    assert console._parse("goto 15 10") == ("goto", [(15, 10)], None)
    assert console._parse("goto (15,10)") == ("goto", [(15, 10)], None)
    assert console._parse("goto 15 10 avoid=auto")[2] == "auto"
    assert console._parse("goto 15 10 avoid=(3,4),(5,6)")[2] == frozenset({(3, 4), (5, 6)})

    w = mapped()
    assert "DONE" in console.run(w, "goto 10 16")[-1][0]
    assert console.run(w, "distance 19 13")[-1][0].startswith("distance to")
    assert w.steps == 1, "distance must not have cost anything"
    assert console.run(w, "fly 1 2")[-1][1] == "bad"
    assert len(console.run(w, "help")) == len(console.HELP) + 1


def test_the_log_records_what_the_plan_promised():
    w = World()
    nav.goto(w, 10, 0)
    last = w.nav_log[-1]
    assert last["planned"] < last["steps"] or last["code"] != "DONE", last
    assert last["area"] == "plaza" and last["to"] == (10, 0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all nav checks passed")
