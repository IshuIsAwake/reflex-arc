"""Watching the drive, and the one rule that makes it safe.

    .venv/bin/python game/test_anim.py

**The playback is a display of something that already happened.** The world jumps the
moment `goto` is called, `nav` writes down what it did, and `anim.Reel` draws that
afterwards. So the load-bearing test here is `test_the_reel_never_changes_the_world`:
if the animation could alter anything, the model would be reasoning about a world that
depends on how long somebody watched it, which is not a world at all.
"""

import sys

import anim
import config as C
import flyer
import nav
import settings as S
from world import SOLID, World

# Clear skies unless a suite asks otherwise. The weather is real and shipped on,
# but it is a scenario, not terrain -- letting one drift across an arena would make
# every route assertion here depend on STORM_RADIUS. `test_hazards.py` turns it on.
S.STORM_ON = False


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def play(reel, seconds=60.0, dt=1 / 60):
    """Run the reel to the end, the way main.py's loop does. Returns frames drawn."""
    n = 0
    while reel.busy and n * dt < seconds:
        reel.tick(dt)
        n += 1
    reel.tick(dt)
    return n


def kinds(timeline):
    return [k for k, _ in timeline]


def test_a_drive_is_recorded_as_it_happens():
    print("what nav writes down")
    # Pinned above the shipped 5. A surprise reveals one cell here, not a radius-3 disc,
    # so the rover feels its way round an outcrop instead of seeing it -- this diagonal
    # needs seven replans where prototype 7 arrived inside five. The shipped value is
    # left alone deliberately; this test is about what the reel records, not about the
    # knob, and pinning it is how the two stop being one measurement.
    keep = S.NAV_REPLANS
    S.NAV_REPLANS = 10
    try:
        return _a_drive_is_recorded()
    finally:
        S.NAV_REPLANS = keep


def _a_drive_is_recorded():
    w = World()
    r = nav.goto(w, 29, 2)         # the long north-east diagonal, three boulders deep
    ok = check("it gets there", r.code == "DONE", str(r))
    ok &= check("one reel queued", len(w.reel) == 1, str(len(w.reel)))

    tl = w.reel[0]
    ok &= check("it starts where the rover did", tl[0] == ("start", C.SPAWN), str(tl[0]))
    ks = kinds(tl)
    ok &= check("it plans before it moves", ks[1] == "plan")
    ok &= check("it was surprised", ks.count("block") > 1, f"{ks.count('block')} blocks")
    # A fresh plan after every surprise, and that is the thing worth watching: each one
    # ran through an outcrop nobody had seen.
    ok &= check("and laid a fresh plan after each",
                ks.count("plan") == ks.count("block") + 1,
                f"{ks.count('plan')} plans, {ks.count('block')} blocks")

    steps = [d for k, d in tl if k == "step"]
    ok &= check("a step per tile actually driven", len(steps) == r.steps,
                f"{len(steps)} steps vs {r.steps}")
    ok &= check("and none of them is rock",
                all(C.ARENA[c[1]][c[0]] not in SOLID for c, _ in steps))
    ok &= check("the last step is where it ended up", steps[-1][0] == w.pos)
    ok &= check("every block really is rock",
                all(C.ARENA[c[1]][c[0]] == "#" for k, c in tl if k == "block"))

    first_plan = next(d for k, d in tl if k == "plan")
    ok &= check("the first plan drove through rock it had not seen",
                any(C.ARENA[y][x] == "#" for x, y in first_plan))

    # The one case that legitimately has a single plan: the target itself turns out to
    # be rock, so there is nowhere else to re-route to and nav stops rather than
    # inventing a destination.
    w2 = World()
    r2 = nav.goto(w2, 15, 7)       # the south face of the boulder due north
    ok &= check("blocked *on* the target lays no second plan",
                r2.code == "BLOCKED" and kinds(w2.reel[0]).count("plan") == 1, str(r2))
    return ok


def test_pricing_a_trip_is_blue_and_moves_nothing():
    print("distance")
    w = World()
    before = w.pos, w.steps
    nav.distance(w, 15, 0)
    ok = check("one reel queued", len(w.reel) == 1)
    ks = kinds(w.reel[0])
    ok &= check("a probe, not a drive", ks == ["start", "probe"], str(ks))
    ok &= check("nothing moved and nothing was spent", (w.pos, w.steps) == before)

    # An unreachable price has no route to draw, so it queues nothing rather than an
    # empty reel that would flash for a frame and mean nothing.
    w2 = World()
    w2.here.seen = {(x, y) for y in range(w2.here.h) for x in range(w2.here.w)}
    w2.pos = (32, 29)
    nav.distance(w2, 33, 29)         # straight into a known outcrop
    ok &= check("an unreachable price draws nothing", not w2.reel)
    return ok


def test_the_fog_opens_in_time_with_the_sortie():
    """The reel holds revealed ground shut until the thing that revealed it is drawn.

    In prototype 7 that thing was the drive, and this test drove. Driving reveals
    nothing here, so a drive has no fog to hold back at all -- the flyer does, and the
    window has to stay veiled until the sortie plays or it appears before Ingenuity
    does.
    """
    print("the fog is held shut")
    w = World()
    nav.goto(w, 15, 0)
    far = w.pos
    ok = check("driving revealed nothing to hold back", not w.here.visible(*far))
    reel = anim.Reel(w)
    reel.tick(0.001)
    ok &= check("so the drive veils nothing", not reel.veiled(far))
    ok &= check("and it is drawn back at the pad", reel.where(w.pos) == C.SPAWN)
    play(reel)

    # The sortie is the case that matters.
    w2 = World()
    target = (w2.pos[0], w2.pos[1] - S.SCOUT_RANGE)
    flyer.scout(w2, *target)
    ok &= check("the world has already seen the window", w2.here.visible(*target))

    reel2 = anim.Reel(w2)
    reel2.tick(0.001)
    ok &= check("but the reel holds it back until Ingenuity is drawn",
                reel2.veiled(target),
                "otherwise the map opens before the flyer has left the ground")

    play(reel2)
    ok &= check("by the end nothing is veiled", not reel2.veiled(target))
    ok &= check("and the rover never moved for it", reel2.where(w2.pos) == w2.pos)
    return ok


def test_the_plan_is_torn_up_when_it_is_wrong():
    print("yellow, then no yellow")
    w = World()
    nav.goto(w, 15, 0)
    reel = anim.Reel(w)

    saw_plan_over_rock = saw_retracting = saw_pruned_to_rover = False
    lengths = []
    while reel.busy:
        reel.tick(1 / 60)
        if any(C.ARENA[y][x] == "#" for x, y in reel.plan):
            saw_plan_over_rock = True
        if reel.bump:
            lengths.append(len(reel.plan))
            # Retracted rather than blinked out: it ends where the rover is standing.
            if reel.plan and reel.plan[-1] == reel.at:
                saw_pruned_to_rover = True
    if len(lengths) > 2:
        saw_retracting = any(b < a for a, b in zip(lengths, lengths[1:]))

    ok = check("the plan was drawn straight through an outcrop", saw_plan_over_rock)
    ok &= check("and withdrew a cell at a time when one refused", saw_retracting)
    ok &= check("back to the cell the rover was standing on", saw_pruned_to_rover)
    return ok


def test_the_reel_never_changes_the_world():
    print("a display, and only a display")
    w = World()
    nav.goto(w, 15, 0)
    after = (w.pos, w.steps, w.day, len(w.here.seen), len(w.here.visited),
             len(w.nav_log), w.last_walk[1][:], w.last_path[1][:])

    reel = anim.Reel(w)
    play(reel)
    now = (w.pos, w.steps, w.day, len(w.here.seen), len(w.here.visited),
           len(w.nav_log), w.last_walk[1][:], w.last_path[1][:])
    ok = check("nothing about the world moved", after == now)

    # And the same holds if nobody ever draws it, which is how every other test runs.
    w2 = World()
    nav.goto(w2, 15, 0)
    ok &= check("an undrawn reel changes nothing either", w2.pos == w.pos)
    return ok


def test_skipping_lands_exactly_where_the_world_already_is():
    print("SPACE")
    w = World()
    nav.goto(w, 15, 0)
    nav.goto(w, 12, 0)
    reel = anim.Reel(w)
    for _ in range(30):
        reel.tick(1 / 60)
    ok = check("mid-drive, the drawing is behind", reel.where(w.pos) != w.pos)

    reel.skip()
    ok &= check("skipping empties the queue", not reel.busy and not w.reel)
    ok &= check("and shows the rover where it really is", reel.where(w.pos) == w.pos)
    ok &= check("with nothing left veiled", not reel.veiled((15, 0)))
    return ok


def test_a_long_stall_catches_up_rather_than_crawling():
    print("one big dt")
    w = World()
    nav.goto(w, 15, 0)
    reel = anim.Reel(w)
    reel.tick(0.001)
    reel.tick(30.0)              # the model held the loop for thirty seconds
    ok = check("it does not then play out in slow motion", not reel.busy)
    ok &= check("and it is caught up", reel.where(w.pos) == w.pos)
    return ok


def test_turning_it_off_records_nothing():
    print("ANIMATE = False")
    S.ANIMATE = False
    try:
        w = World()
        nav.goto(w, 15, 0)
        nav.distance(w, 5, 5)
        ok = check("no reels are kept", not w.reel)
        ok &= check("but the drive still happened", w.pos == (15, 0), str(w.pos))
        ok &= check("and a reel over an empty queue is never busy",
                    not anim.Reel(w).busy)
    finally:
        S.ANIMATE = True
    return ok


def test_the_queue_cannot_grow_forever():
    print("headless, nobody watching")
    w = World()
    for i in range(S.REEL_MAX * 3):
        w.pos = C.SPAWN
        nav.distance(w, 15, 0)
    return check("capped", len(w.reel) == S.REEL_MAX, f"{len(w.reel)} kept")


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_drive_is_recorded_as_it_happens(),
               test_pricing_a_trip_is_blue_and_moves_nothing(),
               test_the_fog_opens_in_time_with_the_sortie(),
               test_the_plan_is_torn_up_when_it_is_wrong(),
               test_the_reel_never_changes_the_world(),
               test_skipping_lands_exactly_where_the_world_already_is(),
               test_a_long_stall_catches_up_rather_than_crawling(),
               test_turning_it_off_records_nothing(),
               test_the_queue_cannot_grow_forever()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
