"""The weather: where it lands, what it blocks, and that two runs get the same one.

    .venv/bin/python game/test_hazards.py

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

import sys

import config as C
import hazards
import nav
import settings as S
import sight
import skills
from world import World

S.STORM_ON = True       # the one file that wants weather


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def _stormy(day=1):
    """A world whose storm is guaranteed, with the map open so routing is the subject."""
    w = World()
    while not w.here.storm and w.day < day + 20:
        w.next_day()
    w.here.reveal_all()
    return w


def test_the_same_sol_gets_the_same_storm():
    print("seeded, or nothing is comparable")
    a, b = World(), World()
    ok = check("two worlds, one sol, one storm",
               (a.here.storm is None) == (b.here.storm is None))
    if a.here.storm:
        ok &= check("...in the same place", a.here.storm.cells == b.here.storm.cells)
        ok &= check("...and the same size", len(a.here.storm) == len(b.here.storm))

    # Different sols must differ, or "seeded" has quietly become "fixed" and the
    # weather stops being weather.
    seen = []
    w = World()
    for _ in range(6):
        seen.append(w.here.storm.cells if w.here.storm else None)
        w.next_day()
    ok &= check("different sols get different weather", len(set(seen)) > 1,
                f"{len(set(seen))} distinct over 6 sols")

    # The two arenas are separate worlds and must not share a forecast.
    C.use("50")
    fifty = World().here.storm
    C.use("30")
    thirty = World().here.storm
    if fifty and thirty:
        ok &= check("the arenas do not share a storm", fifty.cells != thirty.cells)
    return ok


def test_a_storm_never_walls_the_rover_in():
    print("the sol stays playable")
    ok = True
    for name in ("30", "50"):
        C.use(name)
        w = World()
        for _ in range(12):
            s = w.here.storm
            if s:
                ok &= check(f"{name} sol {w.day}: not on the landing site",
                            C.SPAWN not in s.cells)
                open_now = hazards._reach(w.here, C.SPAWN, s.cells)
                open_clear = hazards._reach(w.here, C.SPAWN, frozenset())
                share = len(open_now) / len(open_clear)
                ok &= check(f"{name} sol {w.day}: most of the arena is still reachable",
                            share >= S.STORM_MAX_CUTOFF, f"{share:.0%} left")
            w.next_day()
    C.use(C.DEFAULT_ARENA)
    return ok


def test_a_route_goes_around_it_rather_than_through():
    print("the planner respects the weather")
    w = _stormy()
    s = w.here.storm
    ok = check("there is a storm to test with", s is not None)
    if not ok:
        return ok

    # Somewhere on the far side of it, reachable when the sky is clear.
    target = None
    for cell in sorted(hazards._reach(w.here, C.SPAWN, frozenset())):
        if 6 < abs(cell[0] - s.centre[0]) + abs(cell[1] - s.centre[1]) < 14:
            target = cell
            break
    ok &= check("...and somewhere past it to aim at", target is not None)
    if target is None:
        return ok

    path = nav.plan(w.here, w.pos, target, nav.with_storm(w.here, frozenset()))
    if path:
        ok &= check("the route does not cross the storm",
                    not (set(path) & s.cells), str(set(path) & s.cells))
    # And the drive itself, not just the plan: `world.move` must refuse a storm cell
    # even when something hands it one directly.
    inside = next(iter(s.cells))
    w.pos = (inside[0], inside[1] - 1) if (inside[0], inside[1] - 1) not in s.cells \
        else (inside[0], inside[1] + 1)
    if not w.here.blocked(*w.pos):
        before = w.steps
        w.move(inside[0] - w.pos[0], inside[1] - w.pos[1])
        ok &= check("driving into it is refused and charges nothing",
                    w.pos != inside and w.steps == before)
    return ok


def test_a_goal_behind_the_storm_says_it_is_the_storm():
    print("STORM_BLOCKED, not UNREACHABLE")
    w = _stormy()
    s = w.here.storm
    # A cell inside the storm has no way in at all, which is the cleanest case.
    inside = sorted(s.cells)[len(s.cells) // 2]
    r = nav.goto(w, *inside)
    ok = check("a goal inside it is refused", r.code == "STORM_BLOCKED", str(r))
    ok &= check("...and nothing was driven", r.steps == 0)
    # A code with no sentence behind it gets reissued. It also has to say the thing a
    # model would otherwise get wrong: this is not rock, and it is gone tomorrow.
    ok &= check("...and it says the storm is what did it", "dust storm" in r.advice)
    ok &= check("...that it is not terrain", "not rock" in r.advice, r.advice)
    ok &= check("...and that it clears", "blows out" in r.advice, r.advice)

    c = skills.call(w, "goto", {"x": inside[0], "y": inside[1], "why": "into it"})
    ok &= check("the skill hands the whole thing over",
                "STORM_BLOCKED" in c.result and "dust storm" in c.result)
    ok &= check("...and spends nothing", c.steps == 0)
    return ok


def test_pricing_a_trip_meets_the_same_weather():
    print("distance does not quote a trip nobody can take")
    w = _stormy()
    inside = sorted(w.here.storm.cells)[len(w.here.storm.cells) // 2]
    steps, _ = nav.price(w, *inside)
    ok = check("a priced route into the storm has no answer", steps is None, str(steps))
    c = skills.call(w, "distance", {"x": inside[0], "y": inside[1], "why": "how far"})
    ok &= check("...and the skill says unreachable rather than a number",
                c.result.startswith("UNREACHABLE"), c.result[:60])
    return ok


def test_the_storm_is_visible_because_it_is_forecast():
    print("forecast, so drawn even over fog")
    w = World()
    while not w.here.storm and w.day < 20:
        w.next_day()
    s = w.here.storm
    ok = check("there is a storm", s is not None)
    if not s:
        return ok

    grid = sight.grid(w).splitlines()
    x, y = sorted(s.cells)[0]
    ok &= check("a storm cell is drawn on the map",
                sight.STORM in grid[y + 1], grid[y + 1][:60])
    # Forecast means orbital, so it is known before the ground under it is. What it must
    # not do is reveal that ground.
    ok &= check("...even where the rover has never been", not w.here.visible(x, y))
    ok &= check("...without lifting the fog under it", (x, y) not in w.here.seen)
    ok &= check("the legend explains the glyph", sight.STORM_WORD in sight.legend(w))

    line = sight.weather(w)
    ok &= check("the view states where it is", f"({s.centre[0]},{s.centre[1]})" in line)
    ok &= check("...and how big", str(len(s)) in line)
    ok &= check("...and that it clears tonight", "blows out" in line)
    ok &= check("it is in the block the model reads", line in sight.view(w))
    return ok


def test_the_weather_turns_over_with_the_sol():
    print("one storm a sol, lasting the sol")
    w = World()
    first = w.here.storm
    steps_in = []
    for _ in range(40):
        w.spend(10)
        steps_in.append(w.here.storm)
    ok = check("it does not move or clear during the sol",
               all(s is first for s in steps_in))
    w.day_over = False
    w.next_day()
    ok &= check("a new sol gets its own weather", w.here.storm is not first)
    return ok


def test_the_storm_is_weather_and_not_terrain():
    print("the ground underneath is untouched")
    w = _stormy()
    s = w.here.storm
    cell = sorted(s.cells)[len(s.cells) // 2]
    ok = check("the map still reports the ground under it",
               w.here.at(*cell) in ".#H123", w.here.at(*cell))
    # `Survey` counts rock by character, so a storm must not turn up as a formation.
    rock = [cells for _, cells in w.survey.rock(w.here)]
    ok &= check("it is not counted as rock",
                not any(cell in group for group in rock if w.here.at(*cell) != "#"))
    c = skills.call(w, "count", {"kind": "rock"})
    ok &= check("...and `count` never mentions it", "storm" not in c.result.lower())
    return ok


if __name__ == "__main__":
    results = [test_the_same_sol_gets_the_same_storm(),
               test_a_storm_never_walls_the_rover_in(),
               test_a_route_goes_around_it_rather_than_through(),
               test_a_goal_behind_the_storm_says_it_is_the_storm(),
               test_pricing_a_trip_meets_the_same_weather(),
               test_the_storm_is_visible_because_it_is_forecast(),
               test_the_weather_turns_over_with_the_sol(),
               test_the_storm_is_weather_and_not_terrain()]
    C.use(C.DEFAULT_ARENA)
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
