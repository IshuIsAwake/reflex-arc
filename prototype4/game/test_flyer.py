"""The flyer: what it reveals, and the three doors that stop it revealing everything.

    .venv/bin/python game/test_flyer.py

Most of this file is about the loopholes rather than the capability. Revealing a box is
four lines and cannot really go wrong; a capability that can be spammed, or that can be
aimed anywhere, deletes the exploration this prototype exists to watch -- and it does so
quietly, because everything still works and nothing ever looks broken. Same shape as the
omniscient-planner trap `test_nav.py` guards.

The load-bearing one is `test_it_cannot_be_spammed_from_one_spot`. If it ever goes green
by accident -- somebody raises SCOUT_RANGE, or drops the recharge -- the rover can sit on
the pad and buy the map, and the first symptom is a run where nothing ever drives
anywhere and it looks like a very good day.
"""

import sys

import flyer
import settings as S
import skills
from world import World


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def _fresh():
    """A world with the flyer ready and plenty of day left."""
    return World()


def test_a_sortie_reveals_a_window_and_moves_nothing():
    print("scout")
    w = _fresh()
    where = w.pos
    before_seen, before_steps = len(w.here.seen), w.steps
    target = (w.pos[0], w.pos[1] - S.SCOUT_RANGE)     # north, into fog

    r, advice = flyer.scout(w, *target)
    ok = check("succeeds", r.code == "SCOUTED", str(r))
    ok &= check("reveals ground", len(w.here.seen) > before_seen,
                f"{before_seen} -> {len(w.here.seen)}")
    ok &= check("...and says how much", r.new == len(w.here.seen) - before_seen,
                f"new={r.new}")
    # The rover not moving is the thing most likely to read as a skill that misfired,
    # so the answer has to say it rather than leave it to be inferred from `at`.
    ok &= check("the rover has not moved", w.pos == where)
    ok &= check("...and the answer says so", "not moved" in advice, advice)
    ok &= check("it costs the day", w.steps - before_steps == S.SCOUT_COST,
                f"{w.steps - before_steps}")

    # The window is a square of known size, so this is checkable rather than trusted.
    side = 2 * S.SCOUT_BOX + 1
    ok &= check("the window is the size the schema promises",
                len(w.here.box(*target, S.SCOUT_BOX)) == side * side)
    return ok


def test_the_window_reveals_rock_as_well_as_regolith():
    print("what a window is allowed to see")
    # Deliberate, and it has a price: a goto through scouted ground can no longer come
    # back BLOCKED, which is the best thing on the screen. It is here as a test so that
    # if anybody changes it, they change it on purpose.
    w = _fresh()
    a = w.here
    rock = [(x, y) for y in range(a.h) for x in range(a.w)
            if a.at(x, y) == "#" and not a.visible(x, y)
            and max(abs(x - w.pos[0]), abs(y - w.pos[1])) <= S.SCOUT_RANGE]
    if not rock:
        return check("no unseen rock in range to test with", False)
    flyer.scout(w, *rock[0])
    return check("rock under the window becomes known", a.visible(*rock[0]))


def test_it_cannot_be_aimed_across_the_map():
    print("range")
    w = _fresh()
    far = (w.pos[0] + S.SCOUT_RANGE + 1, w.pos[1])
    before = w.steps
    r, advice = flyer.scout(w, *far)
    ok = check("out of range is refused", r.code == "OUT_OF_RANGE", str(r))
    ok &= check("and costs nothing", w.steps == before)
    # A refusal that does not say what to do instead gets reissued. Watched three
    # separate times in FINDINGS, each time with a different code on it.
    ok &= check("and says to drive closer", "Drive closer" in advice, advice)

    edge = (w.pos[0] + S.SCOUT_RANGE, w.pos[1])
    ok &= check("exactly at the limit is allowed", flyer.scout(w, *edge)[0].code == "SCOUTED")

    w2 = _fresh()
    off, _ = flyer.scout(w2, 999, 999)
    ok &= check("off the arena is its own answer", off.code == "OFF_MAP", str(off))
    return ok


def test_it_cannot_be_spammed_from_one_spot():
    """The load-bearing one. Without the recharge, range does not save you: a rover
    parked on the pad can scout the whole reachable square in a handful of calls, never
    drive anywhere, and the run looks like a triumph."""
    print("recharge")
    w = _fresh()
    r1, _ = flyer.scout(w, w.pos[0], w.pos[1] - 5)
    ok = check("the first sortie flies", r1.code == "SCOUTED")

    before = w.steps
    r2, advice = flyer.scout(w, w.pos[0] + 5, w.pos[1])
    ok &= check("the second is refused", r2.code == "RECHARGING", str(r2))
    ok &= check("and costs nothing", w.steps == before)
    ok &= check("and says how much driving it owes", "more steps of driving" in advice,
                advice)
    ok &= check("the status line agrees", w.scout_ready_in > 0, f"{w.scout_ready_in}")

    # Driving is what pays it off, and it has to actually be driving -- a recharge that
    # thinking or talking could clear would be no constraint at all, which is why it is
    # counted in steps like everything else. Note the loop: a move into rock is refused
    # and charges nothing, so the debt is paid in cells actually crossed. That is the
    # right behaviour and the first version of this test got it wrong.
    guard = 0
    while w.scout_ready_in and guard < 500:
        guard += 1
        for d in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            was = w.steps
            w.move(*d)
            if w.steps != was:
                break
    ok &= check("driving it off makes it ready again", w.scout_ready_in == 0,
                f"{w.scout_ready_in}")
    ok &= check("and it flies", flyer.scout(w, *w.pos)[0].code == "SCOUTED")
    return ok


def test_a_sortie_over_known_ground_says_so():
    print("a window that bought nothing")
    w = _fresh()
    # Everything known, so the window cannot buy anything whatever the knobs are set
    # to. An earlier version aimed at the landing site and passed only while the window
    # happened to be smaller than BASE_REVEAL -- a test that green depends on tuning is
    # not testing what it says it is.
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    r, advice = flyer.scout(w, *w.pos)
    ok = check("it still succeeds", r.code == "SCOUTED", str(r))
    ok &= check("revealing nothing", r.new == 0, f"new={r.new}")
    # A costless-looking success is the failure FINDINGS records three times: it
    # succeeded, so there is nothing to correct, so the same call comes back.
    ok &= check("and says the window was wasted", "nothing changed" in advice, advice)
    ok &= check("but it was still paid for", r.steps == S.SCOUT_COST, f"{r.steps}")
    return ok


def test_the_day_can_run_out_mid_sortie():
    print("the end of the day")
    w = _fresh()
    w.steps = S.DAY_STEPS - (S.SCOUT_COST - 1)     # not quite enough left
    r, advice = flyer.scout(w, w.pos[0], w.pos[1] - 5)
    ok = check("a sortie it cannot afford is refused",
               r.code == "NOT_ENOUGH_CHARGE", str(r))
    ok &= check("and says what it costs", str(S.SCOUT_COST) in advice, advice)
    ok &= check("and nothing was revealed", r.new == 0)
    return ok


def test_going_nowhere_by_air_is_caught_too():
    print("the stuck detector reaches the flyer")
    # `_stuck` fires on the fact -- a call that revealed nothing -- not on the name of
    # the skill. A new skill that spends steps and buys no map must land inside it
    # automatically, or the detector goes back to being a list of the cases somebody
    # happened to think of.
    w = _fresh()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    history = []
    for _ in range(3):
        w.scout_ready_at = 0            # the recharge is not what is under test here
        history.append(skills.call(w, "scout", {"x": w.pos[0], "y": w.pos[1]},
                                   history=history))
    return check("three sorties that revealed nothing are called out",
                 "nothing has changed" in history[-1].result
                 or "revealed nothing new" in history[-1].result,
                 history[-1].result[-110:])


def test_the_view_admits_the_flyer_exists():
    print("the sense agrees with the skills")
    import sight
    w = _fresh()
    ok = check("the status line says the flyer is ready", "flyer ready" in sight.status_line(w))
    flyer.scout(w, w.pos[0], w.pos[1] - 5)
    ok &= check("...and that it is charging, in words not a ratio",
                "charging" in sight.status_line(w), sight.status_line(w))
    # The prompt and the view may only promise what is wired up. This sentence was a
    # lie for exactly as long as it took to notice.
    ok &= check("nothing still claims driving is the only thing that lifts fog",
                "only thing that lifts fog" not in sight.REVEAL_RULE)
    return ok


if __name__ == "__main__":
    results = [test_a_sortie_reveals_a_window_and_moves_nothing(),
               test_the_window_reveals_rock_as_well_as_regolith(),
               test_it_cannot_be_aimed_across_the_map(),
               test_it_cannot_be_spammed_from_one_spot(),
               test_a_sortie_over_known_ground_says_so(),
               test_the_day_can_run_out_mid_sortie(),
               test_going_nowhere_by_air_is_caught_too(),
               test_the_view_admits_the_flyer_exists()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
