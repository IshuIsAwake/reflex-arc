"""The work, both kinds: interests she has to find, objectives the desk gives her.

    .venv/bin/python game/test_work.py

The load-bearing ones are the two about what she is told. `test_an_interest_is_hidden_until_seen`
and `test_what_an_interest_is_lives_only_in_the_result`: 10c's `execute` named every
objective on the arena, fog or not, and the 31B drove straight to both high-priority ones
on that list. Anything that says where unfound work is, or what an interest was after the
fact, breaks the thing being measured.

`test_work_is_not_done_by_driving_over_it` is the other: make work drivable and every
piece gets done for free on the way past, and nothing looks broken.
"""

import sys

import config as C
import nav
import settings as S
import sight
import skills
from world import World

# Clear skies: the weather is a scenario, not terrain. `test_hazards.py` turns it on.
S.STORM_ON = False


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def _beside(w, cell):
    """Put the rover beside `cell` without spending the day getting there."""
    x, y = cell
    for c in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
        if not w.here.blocked(*c):
            w.pos = c
            w._arrive()
            return c
    raise AssertionError(f"{cell} has no open cell beside it")


def _mapped_open(w, near=(15, 11)):
    """An open, mapped cell a few rows north of the pad, for placing on."""
    w.here.reveal(*near, r=3)
    return near


def test_work_is_not_done_by_driving_over_it():
    print("you have to stop and do the work")
    w = World()
    i = w.interests[0]
    ok = check("an interest is solid, so a route cannot pass through it",
               w.here.blocked(*i.cell))
    r = nav.goto(w, *i.cell)
    ok &= check("goto stops beside it rather than on it",
                r.code == "DONE" and w.pos != i.cell, f"{r} pos={w.pos}")
    ok &= check("arriving did not do the work", not i.done and i.cell in w.here.interests)
    ok &= check("...and cost nothing beyond the drive", w.steps == r.steps)
    return ok


def test_an_interest_is_hidden_until_seen():
    print("interests are found, never given")
    w = World()
    ok = check("none is seen from the landing site", not any(i.found for i in w.interests))
    view = sight.view(w)
    ok &= check("the view lists none, and says they show once seen",
                not sight.interests(w) and "shows as * only once" in view)
    ok &= check("no interest's text or cell is anywhere in the view",
                not any(i.text in view or f"({i.cell[0]},{i.cell[1]})" in view
                        for i in w.interests))

    # Placed on ground already mapped, it is still hidden: the map reads open ground.
    cell = _mapped_open(w)
    hidden, why = w.place_interest(cell, "a glint of something metallic", 25)
    ok &= check("an interest can be placed on mapped ground", hidden is not None, str(why))
    ok &= check("...and the map she reads still says open ground there",
                nav.known(w.here, *cell) == "." and "*" not in sight.grid(w))

    c = skills.call(w, "goto", {"x": cell[0], "y": cell[1] + S.VISION_RADIUS})
    ok &= check("driving within sight finds it", hidden.found, c.result[:80])
    ok &= check("...the drive's result says so, with where",
                f"({cell[0]},{cell[1]})" in c.result and "closer look" in c.result,
                c.result[-160:])
    ok &= check("...and now it is on the map and listed",
                nav.known(w.here, *cell) == "*" and len(sight.interests(w)) == 1)
    ok &= check("...still without what it is", hidden.text not in sight.view(w))
    return ok


def test_what_an_interest_is_lives_only_in_the_result():
    print("examining is the only way to learn what it is")
    w = World()
    i = w.interests[0]
    _beside(w, i.cell)
    c = skills.call(w, "execute", {})
    ok = check("examining it says what it was", c.result.startswith("EXAMINED")
               and i.text in c.result, c.result[:120])
    ok &= check("...and charges exactly its cost", c.steps == i.cost)
    ok &= check("it is off the map", i.cell not in w.here.interests)
    ok &= check("the record keeps the text, for the report",
                w.finished[-1]["kind"] == "interest" and w.finished[-1]["text"] == i.text)
    view = sight.view(w)
    ok &= check("the view lists it as examined", f"({i.cell[0]},{i.cell[1]}) -- examined"
                in view)
    ok &= check("...and never says what it was", i.text not in view)
    return ok


def test_refusing_names_only_the_work_she_knows():
    print("refusals carry the map she has, and no more")
    w = World()
    c = skills.call(w, "execute", {"why": "from the pad"})
    ok = check("nowhere near any, it refuses", c.result.startswith("NOT_BESIDE_ONE"))
    ok &= check("...spends nothing", c.steps == 0)
    ok &= check("...and names no interest she has not found",
                not any(f"({i.cell[0]},{i.cell[1]})" in c.result for i in w.interests),
                c.result)
    o, _ = w.place_objective(_mapped_open(w), "high", 30)
    c = skills.call(w, "execute", {})
    ok &= check("an objective is hers to know, so it is named",
                f"({o.cell[0]},{o.cell[1]})" in c.result and "high priority" in c.result,
                c.result)
    return ok


def test_objectives_go_on_mapped_ground_and_are_seen_at_once():
    print("the desk's objectives")
    w = World()
    o, why = w.place_objective((2, 2), "high", 30)
    ok = check("under the fog it is refused", o is None and "fog" in why, str(why))
    cell = _mapped_open(w)
    o, why = w.place_objective(cell, "medium", 25)
    ok &= check("on mapped ground it is placed", o is not None, str(why))
    lines = sight.objectives(w)
    ok &= check("...and listed at once, with priority and cost",
                len(lines) == 1 and all(s in lines[0] for s in
                                        (f"({cell[0]},{cell[1]})", "medium", "25")),
                str(lines))
    ok &= check("...under its heading", "OBJECTIVES FROM MISSION CONTROL" in sight.view(w))
    _beside(w, cell)
    c = skills.call(w, "execute", {})
    ok &= check("doing it says so, with its priority", c.result.startswith("EXECUTED")
                and "priority=medium" in c.result, c.result[:80])
    ok &= check("...and it is gone", not w.objectives)
    for bad, word in (((15, 16), "pad"), (w.pos, "rover")):
        o, why = w.place_objective(bad, "low", 10)
        ok &= check(f"not on the {word}", o is None, str(why))
    return ok


def test_the_environment_does_not_rank_them():
    print("the ranking stays with the model")
    w = World()
    w.here.reveal(15, 8, r=6)
    for cell, pr in (((10, 8), "low"), ((20, 8), "high"), ((15, 4), "medium")):
        w.place_objective(cell, pr, 20)
    lines = sight.objectives(w)
    ok = check("listed in the order placed, not by priority or cost",
               [l.split()[0] for l in lines] == ["low", "high", "medium"], str(lines))
    blob = " ".join(lines) + skills.call(w, "execute", {}).result
    for word in ("best", "nearest", "should", "recommend", "first"):
        ok &= check(f"nothing says {word!r}", word not in blob.lower())
    return ok


def test_auto_objectives_come_in_sets():
    print("auto objectives")
    keep = S.OBJECTIVES
    S.OBJECTIVES = "auto"
    try:
        w = World()
        ok = check("none on sol 1", not w.auto_objectives())
        w.here.reveal(15, 15, r=10)
        w.next_day()
        placed = w.auto_objectives()
        ok &= check("three on sol 2, one of each priority",
                    sorted(o.priority for o in placed) == ["high", "low", "medium"],
                    str(placed))
        ok &= check("...all on mapped open ground",
                    all(w.here.visible(*o.cell) for o in placed))
        ok &= check("...with work in fives between the bounds",
                    all(S.OBJECTIVE_COST[0] <= o.cost <= S.OBJECTIVE_COST[1]
                        and o.cost % 5 == 0 for o in placed), str([o.cost for o in placed]))
        ok &= check("...and the same three for the same sol",
                    [o.cell for o in placed] == [o.cell for o in _again(w)])
        w.next_day()
        ok &= check("no new set while one is open", not w.auto_objectives())
        for o in list(w.objectives):
            _beside(w, o.cell)
            skills.call(w, "execute", {})
        w.pos = C.SPAWN
        w.next_day()
        ok &= check("a new set once the last is finished", len(w.auto_objectives()) == 3)
        S.OBJECTIVES = "manual"
        w.next_day()
        ok &= check("manual places none", not w.auto_objectives())
    finally:
        S.OBJECTIVES = keep
    return ok


def _again(w):
    """The set the same world places again, once the first is taken away."""
    for o in list(w.objectives):
        del w.here.objectives[o.cell]
    return w.auto_objectives()


def test_a_battery_that_runs_flat_mid_task_still_pays_for_what_it_used():
    print("running flat is not a refund")
    w = World()
    i = w.interests[0]
    _beside(w, i.cell)
    w.battery = 5                      # five steps of charge left, a 40-step job
    c = skills.call(w, "execute", {})
    ok = check("it does not finish", not i.done and i.cell in w.here.interests)
    ok &= check("...says the battery ran flat", c.result.startswith("UNFINISHED")
                and "battery ran flat" in c.result, c.result[:90])
    ok &= check("...the charge is gone, and with it the day",
                w.battery == 0 and c.steps == 5 and w.day_over)
    over = skills.call(w, "execute", {})
    ok &= check("flat, it refuses outright, and says why",
                over.result.startswith("BATTERY_FLAT"), over.result[:60])
    ok &= check("...and spends nothing", over.steps == 0)
    return ok


def test_the_arena_survives_them_being_solid():
    print("no interest seals a corridor")
    ok = True
    for name in ("30", "50"):
        C.use(name)
        w = World()
        w.here.reveal_all()
        for i in w.interests:
            i.found = True
        for i in w.interests:
            path = nav.plan(w.here, C.SPAWN, i.cell)
            ok &= check(f"{name}: the interest at {i.cell} can be reached",
                        path is not None and path[-1] != i.cell, str(path and path[-1]))
    C.use(C.DEFAULT_ARENA)
    return ok


def test_interests_cannot_be_placed_where_work_cannot_happen():
    print("placing an interest")
    w = World()
    ok = True
    for cell, word in (((15, 16), "pad"), ((19, 20), "rock")):
        i, why = w.place_interest(cell, "nothing", 10)
        ok &= check(f"not on the {word}", i is None, str(why))
    i, why = w.place_interest((3, 3), "under the fog", 10)
    ok &= check("under the fog is fine", i is not None, str(why))
    i, why = w.place_interest((3, 3), "twice", 10)
    ok &= check("not on top of other work", i is None, str(why))
    return ok


if __name__ == "__main__":
    results = [test_work_is_not_done_by_driving_over_it(),
               test_an_interest_is_hidden_until_seen(),
               test_what_an_interest_is_lives_only_in_the_result(),
               test_refusing_names_only_the_work_she_knows(),
               test_objectives_go_on_mapped_ground_and_are_seen_at_once(),
               test_the_environment_does_not_rank_them(),
               test_auto_objectives_come_in_sets(),
               test_a_battery_that_runs_flat_mid_task_still_pays_for_what_it_used(),
               test_the_arena_survives_them_being_solid(),
               test_interests_cannot_be_placed_where_work_cannot_happen()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
