"""The work: interests she has to find, and objectives the desk gives her. Nothing may
say where unfound work is, or what an interest was, except examining it. Work is solid, so
driving over it does nothing."""


import config
import nav
import settings
import sight
import skills
from world import World


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
    w = World()
    i = w.interests[0]
    assert w.here.blocked(*i.cell), "an interest is solid, so a route cannot pass through it"
    r = nav.goto(w, *i.cell)
    assert r.code == "DONE" and w.pos != i.cell, "goto stops beside it rather than on it"
    assert not i.done and i.cell in w.here.interests, "arriving did not do the work"
    assert w.steps == r.steps, "...and cost nothing beyond the drive"


def test_an_interest_is_hidden_until_seen():
    w = World()
    assert not any(i.found for i in w.interests), "none is seen from the landing site"
    view = sight.view(w)
    assert not sight.interests(w) and "shows as * only once" in view, "the view lists none, and says they show once seen"
    assert (not any(i.text in view or f"({i.cell[0]},{i.cell[1]})" in view
                        for i in w.interests)), "no interest's text or cell is anywhere in the view"

    # Placed on ground already mapped, it is still hidden: the map reads open ground.
    cell = _mapped_open(w)
    hidden, why = w.place_interest(cell, "a glint of something metallic", 25)
    assert hidden is not None, "an interest can be placed on mapped ground"
    assert nav.known(w.here, *cell) == "." and "*" not in sight.grid(w), "...and the map she reads still says open ground there"

    c = skills.call(w, "goto", {"x": cell[0], "y": cell[1] + settings.VISION_RADIUS})
    assert hidden.found, "driving within sight finds it"
    assert f"({cell[0]},{cell[1]})" in c.result and "closer look" in c.result, "...the drive's result says so, with where"
    assert nav.known(w.here, *cell) == "*" and len(sight.interests(w)) == 1, "...and now it is on the map and listed"
    assert hidden.text not in sight.view(w), "...still without what it is"


def test_what_an_interest_is_lives_only_in_the_result():
    w = World()
    i = w.interests[0]
    _beside(w, i.cell)
    c = skills.call(w, "execute", {})
    assert (c.result.startswith("EXAMINED")
               and i.text in c.result), "examining it says what it was"
    assert c.steps == i.cost, "...and charges exactly its cost"
    assert i.cell not in w.here.interests, "it is off the map"
    assert w.finished[-1]["kind"] == "interest" and w.finished[-1]["text"] == i.text, "the record keeps the text, for the report"
    view = sight.view(w)
    assert (f"({i.cell[0]},{i.cell[1]}) -- examined"
                in view), "the view lists it as examined"
    assert i.text not in view, "...and never says what it was"


def test_refusing_names_only_the_work_she_knows():
    w = World()
    c = skills.call(w, "execute", {"why": "from the pad"})
    assert c.result.startswith("NOT_BESIDE_ONE"), "nowhere near any, it refuses"
    assert c.steps == 0, "...spends nothing"
    assert not any(f"({i.cell[0]},{i.cell[1]})" in c.result for i in w.interests), "...and names no interest she has not found"
    o, _ = w.place_objective(_mapped_open(w), "high", 30)
    c = skills.call(w, "execute", {})
    assert f"({o.cell[0]},{o.cell[1]})" in c.result and "high priority" in c.result, "an objective is hers to know, so it is named"


def test_objectives_go_on_mapped_ground_and_are_seen_at_once():
    w = World()
    o, why = w.place_objective((2, 2), "high", 30)
    assert o is None and "fog" in why, "under the fog it is refused"
    cell = _mapped_open(w)
    o, why = w.place_objective(cell, "medium", 25)
    assert o is not None, "on mapped ground it is placed"
    lines = sight.objectives(w)
    assert (len(lines) == 1 and all(s in lines[0] for s in
                                        (f"({cell[0]},{cell[1]})", "medium", "25"))), "...and listed at once, with priority and cost"
    assert "OBJECTIVES FROM MISSION CONTROL" in sight.view(w), "...under its heading"
    _beside(w, cell)
    c = skills.call(w, "execute", {})
    assert (c.result.startswith("EXECUTED")
                and "priority=medium" in c.result), "doing it says so, with its priority"
    assert not w.objectives, "...and it is gone"
    for bad, word in (((15, 16), "pad"), (w.pos, "rover")):
        o, why = w.place_objective(bad, "low", 10)
        assert o is None, f"not on the {word}"


def test_the_environment_does_not_rank_them():
    w = World()
    w.here.reveal(15, 8, r=6)
    for cell, pr in (((10, 8), "low"), ((20, 8), "high"), ((15, 4), "medium")):
        w.place_objective(cell, pr, 20)
    lines = sight.objectives(w)
    assert [l.split()[0] for l in lines] == ["low", "high", "medium"], "listed in the order placed, not by priority or cost"
    blob = " ".join(lines) + skills.call(w, "execute", {}).result
    for word in ("best", "nearest", "should", "recommend", "first"):
        assert word not in blob.lower(), f"nothing says {word!r}"


def test_auto_objectives_come_in_sets():
    keep = settings.OBJECTIVES
    settings.OBJECTIVES = "auto"
    try:
        w = World()
        assert not w.auto_objectives(), "none on sol 1"
        w.here.reveal(15, 15, r=10)
        w.next_day()
        placed = w.auto_objectives()
        assert sorted(o.priority for o in placed) == ["high", "low", "medium"], "three on sol 2, one of each priority"
        assert all(w.here.visible(*o.cell) for o in placed), "...all on mapped open ground"
        assert (all(settings.OBJECTIVE_COST[0] <= o.cost <= settings.OBJECTIVE_COST[1]
                        and o.cost % 5 == 0 for o in placed)), "...with work in fives between the bounds"
        assert [o.cell for o in placed] == [o.cell for o in _again(w)], "...and the same three for the same sol"
        w.next_day()
        assert not w.auto_objectives(), "no new set while one is open"
        for o in list(w.objectives):
            _beside(w, o.cell)
            skills.call(w, "execute", {})
        w.pos = config.SPAWN
        w.next_day()
        assert len(w.auto_objectives()) == 3, "a new set once the last is finished"
        settings.OBJECTIVES = "manual"
        w.next_day()
        assert not w.auto_objectives(), "manual places none"
    finally:
        settings.OBJECTIVES = keep


def _again(w):
    """The set the same world places again, once the first is taken away."""
    for o in list(w.objectives):
        del w.here.objectives[o.cell]
    return w.auto_objectives()


def test_a_battery_that_runs_flat_mid_task_still_pays_for_what_it_used():
    w = World()
    i = w.interests[0]
    _beside(w, i.cell)
    w.battery = 5  # five steps of charge left, a 40-step job
    c = skills.call(w, "execute", {})
    assert not i.done and i.cell in w.here.interests, "it does not finish"
    assert (c.result.startswith("UNFINISHED")
                and "battery ran flat" in c.result), "...says the battery ran flat"
    assert w.battery == 0 and c.steps == 5 and w.day_over, "...the charge is gone, and with it the day"
    over = skills.call(w, "execute", {})
    assert over.result.startswith("BATTERY_FLAT"), "flat, it refuses outright, and says why"
    assert over.steps == 0, "...and spends nothing"


def test_the_arena_survives_them_being_solid():
    for name in ("30", "50"):
        config.use(name)
        w = World()
        w.here.reveal_all()
        for i in w.interests:
            i.found = True
        for i in w.interests:
            path = nav.plan(w.here, config.SPAWN, i.cell)
            assert path is not None and path[-1] != i.cell, f"{name}: the interest at {i.cell} can be reached"
    config.use(config.DEFAULT_ARENA)


def test_interests_cannot_be_placed_where_work_cannot_happen():
    w = World()
    for cell, word in (((15, 16), "pad"), ((19, 20), "rock")):
        i, why = w.place_interest(cell, "nothing", 10)
        assert i is None, f"not on the {word}"
    i, why = w.place_interest((3, 3), "under the fog", 10)
    assert i is not None, "under the fog is fine"
    i, why = w.place_interest((3, 3), "twice", 10)
    assert i is None, "not on top of other work"


def test_done_is_not_the_end_of_the_day():
    """By day, "nothing left to do" goes on to say what the day still holds."""
    w = World()
    w.phase = "day"
    a = w.here
    c = skills.call(w, "execute", {})
    assert "No work you know of is waiting, and the day is not over" in c.result, "with nothing known, the refusal says the day is not over"
    skills.call(w, "todo", {"text": "look north"})
    c = skills.call(w, "strike", {"n": 1})
    left = (f"the day is not over: {w.battery} steps of battery and "
            f"{w.time_left:.0f} seconds are left, and {a.w * a.h - len(a.seen)} of the "
            f"{a.w * a.h} cells are still unseen.")
    assert c.result.endswith("Nothing is left open on your list, and " + left), "an emptied list says so, with the numbers"
    i = w.interests[0]
    _beside(w, i.cell)
    others = [p for p in w.interests if p.found and p is not i] + w.objectives
    c = skills.call(w, "execute", {})
    assert (others or "No other work you know of is waiting, and the day is not "
                "over" in c.result), "examining the last known work says so too"

    w2 = World()
    skills.call(w2, "todo", {"text": "plan"})
    c = skills.call(w2, "strike", {"n": 1})
    assert c.result.endswith("Nothing is left open on your list."), "at dawn the day has not begun, and there are no numbers"
    w2.phase = "day"
    w2.run_clock(w2.time_left)
    c = skills.call(w2, "execute", {})
    assert c.result.endswith("is waiting."), "nor once the day is over"
