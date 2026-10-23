"""The weather: where it lands, what it blocks, and that two runs get the same one.


This is the one suite that runs with the sky switched on. Every other file pins
`S.STORM_ON = False`, because a storm drifting across an arena would make their route
assertions depend on STORM_RADIUS rather than on the thing they are about.

The load-bearing one is `test_the_same_sol_gets_the_same_storm`. An unseeded storm makes
every tape a different world, two runs of one prompt stop being comparable, and nothing
about that is visible from a transcript -- the run just reads as the model behaving
differently for no reason.

`test_a_storm_never_walls_the_rover_in` is the other. A sol nobody can drive out of
looks exactly like a sol the model failed.
"""

import pytest

import config as C
import hazards
import nav
import settings as S
import sight
import skills
from world import World


@pytest.fixture(autouse=True)
def storm_on():
    S.STORM_ON = True


def _stormy(day=1):
    """A world whose storm is guaranteed, with the map open so routing is the subject."""
    w = World()
    while not w.here.storm and w.day < day + 20:
        w.next_day()
    w.here.reveal_all()
    return w


def test_the_same_sol_gets_the_same_storm():
    a, b = World(), World()
    assert (a.here.storm is None) == (b.here.storm is None), "two worlds, one sol, one storm"
    if a.here.storm:
        assert a.here.storm.cells == b.here.storm.cells, "...in the same place"
        assert len(a.here.storm) == len(b.here.storm), "...and the same size"

    # Different sols must differ, or "seeded" has quietly become "fixed" and the
    # weather stops being weather.
    seen = []
    w = World()
    for _ in range(6):
        seen.append(w.here.storm.cells if w.here.storm else None)
        w.next_day()
    assert len(set(seen)) > 1, "different sols get different weather"

    # The two arenas are separate worlds and must not share a forecast.
    C.use("50")
    fifty = World().here.storm
    C.use("30")
    thirty = World().here.storm
    if fifty and thirty:
        assert fifty.cells != thirty.cells, "the arenas do not share a storm"


def test_a_storm_never_walls_the_rover_in():
    """A hard sol and a broken one read identically in a transcript -- the model reports
    STORM_BLOCKED either way and nothing says which it was. These are the two properties
    that keep the difference real.

    The second one is the one that actually bit. On the rebuilt 30, sol 1 put the storm
    squarely on objective 2 and it was unreachable all day, while the share-of-the-arena
    check sailed through at 97%. The objectives were not in `keep_clear` at all.
    """
    for name in ("30", "50"):
        C.use(name)
        w = World()
        for _ in range(30):
            s = w.here.storm
            if s:
                assert C.SPAWN not in s.cells, f"{name} sol {w.day}: not on the landing site"
                open_now = hazards._reach(w.here, C.SPAWN, s.cells)
                open_clear = hazards._reach(w.here, C.SPAWN, frozenset())
                share = len(open_now) / len(open_clear)
                # Written here rather than read from settings: the knob this compared
                # against went with the rejection loop in `hazards.py`, once a radius of
                # 2 made it reject nothing. The property was worth keeping even so.
                assert share >= 0.75, f"{name} sol {w.day}: most of the arena is still reachable"
                # ...and the part a share of the arena can never see. An interest is
                # solid, so what it needs is one open neighbour still reachable.
                for cell in sorted(C.INTERESTS):
                    x, y = cell
                    ring = {(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)}
                    assert bool(ring & open_now), (f"{name} sol {w.day}: interest at {cell} can still be "
                                f"reached")
            w.next_day()
    C.use(C.DEFAULT_ARENA)


def test_a_route_goes_around_it_rather_than_through():
    w = _stormy()
    s = w.here.storm
    assert s is not None, "there is a storm to test with"

    # Somewhere on the far side of it, reachable when the sky is clear.
    target = None
    for cell in sorted(hazards._reach(w.here, C.SPAWN, frozenset())):
        if 6 < abs(cell[0] - s.centre[0]) + abs(cell[1] - s.centre[1]) < 14:
            target = cell
            break
    assert target is not None, "...and somewhere past it to aim at"

    path = nav.plan(w.here, w.pos, target, nav.with_storm(w.here, frozenset()))
    if path:
        assert not (set(path) & s.cells), "the route does not cross the storm"
    # And the drive itself, not just the plan: `world.move` must refuse a storm cell
    # even when something hands it one directly.
    inside = next(iter(s.cells))
    w.pos = (inside[0], inside[1] - 1) if (inside[0], inside[1] - 1) not in s.cells \
        else (inside[0], inside[1] + 1)
    if not w.here.blocked(*w.pos):
        before = w.steps
        w.move(inside[0] - w.pos[0], inside[1] - w.pos[1])
        assert w.pos != inside and w.steps == before, "driving into it is refused and charges nothing"


def test_a_goal_behind_the_storm_says_it_is_the_storm():
    w = _stormy()
    s = w.here.storm
    # A cell inside the storm has no way in at all, which is the cleanest case.
    inside = sorted(s.cells)[len(s.cells) // 2]
    r = nav.goto(w, *inside)
    assert r.code == "STORM_BLOCKED", "a goal inside it is refused"
    assert r.steps == 0, "...and nothing was driven"
    # A code with no sentence behind it gets reissued. It also has to say the thing a
    # model would otherwise get wrong: this is not rock, and it is gone tomorrow.
    assert "dust storm" in r.advice, "...and it says the storm is what did it"
    assert "not rock" in r.advice, "...that it is not terrain"
    assert "blows out" in r.advice, "...and that it clears"

    c = skills.call(w, "goto", {"x": inside[0], "y": inside[1], "why": "into it"})
    assert "STORM_BLOCKED" in c.result and "dust storm" in c.result, "the skill hands the whole thing over"
    assert c.steps == 0, "...and spends nothing"


def test_pricing_a_trip_meets_the_same_weather():
    w = _stormy()
    inside = sorted(w.here.storm.cells)[len(w.here.storm.cells) // 2]
    steps = nav.price(w, *inside)
    assert steps is None, "a priced route into the storm has no answer"
    c = skills.call(w, "distance", {"x": inside[0], "y": inside[1], "why": "how far"})
    assert c.result.startswith("UNREACHABLE"), "...and the skill says unreachable rather than a number"


def test_the_storm_is_visible_because_it_is_forecast():
    w = World()
    while not w.here.storm and w.day < 20:
        w.next_day()
    s = w.here.storm
    assert s is not None, "there is a storm"

    grid = sight.grid(w).splitlines()
    x, y = sorted(s.cells)[0]
    assert sight.STORM in grid[y + 1], "a storm cell is drawn on the map"
    # Forecast means orbital, so it is known before the ground under it is. What it must
    # not do is reveal that ground.
    assert not w.here.visible(x, y), "...even where the rover has never been"
    assert (x, y) not in w.here.seen, "...without lifting the fog under it"
    assert sight.STORM_WORD in sight.legend(w), "the legend explains the glyph"

    line = sight.weather(w)
    assert f"({s.centre[0]},{s.centre[1]})" in line, "the view states where it is"
    assert str(len(s)) in line, "...and how big"
    assert "blows out" in line, "...and that it clears tonight"
    assert line in sight.view(w), "it is in the block the model reads"


def test_the_weather_turns_over_with_the_sol():
    w = World()
    first = w.here.storm
    steps_in = []
    for _ in range(40):
        w.spend(10)
        steps_in.append(w.here.storm)
    assert all(s is first for s in steps_in), "it does not move or clear during the sol"
    w.day_over = False
    w.next_day()
    assert w.here.storm is not first, "a new sol gets its own weather"


def test_the_storm_is_weather_and_not_terrain():
    w = _stormy()
    s = w.here.storm
    cell = sorted(s.cells)[len(s.cells) // 2]
    assert w.here.at(*cell) in ".#H123", "the map still reports the ground under it"
    # `Survey` counts rock by character, so a storm must not turn up as a formation.
    rock = [cells for _, cells in w.survey.rock(w.here)]
    assert not any(cell in group for group in rock if w.here.at(*cell) != "#"), "it is not counted as rock"
    c = skills.call(w, "count", {"kind": "rock"})
    assert "storm" not in c.result.lower(), "...and `count` never mentions it"
