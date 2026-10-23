"""Watching the drive, and the one rule that makes it safe.


**The playback is a display of something that already happened.** The world jumps the
moment `goto` is called, `nav` writes down what it did, and `anim.Reel` draws that
afterwards. So the load-bearing test here is `test_the_reel_never_changes_the_world`:
if the animation could alter anything, the model would be reasoning about a world that
depends on how long somebody watched it, which is not a world at all.
"""


import anim
import config
import nav
import settings
from world import SOLID, World


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
    # Pinned above the shipped 5, so the drive has room to be surprised as often as this
    # route surprises it. The shipped value is left alone deliberately: this test is
    # about what the reel records, not about the knob, and pinning it is how the two
    # stop being one measurement.
    keep = settings.NAV_REPLANS
    settings.NAV_REPLANS = 10
    try:
        return _a_drive_is_recorded()
    finally:
        settings.NAV_REPLANS = keep


def _a_drive_is_recorded():
    w = World()
    # The long run west across the C and out to the far edge, three surprises deep. With
    # the rover seeing again a short route mostly walks around what it meets, so the
    # drive worth recording is a long one into ground the landing disc never lit. Open
    # ground rather than an objective, because an objective is solid without being rock
    # and the last block would not be an outcrop at all.
    r = nav.goto(w, 0, 10)
    assert r.code == "DONE", "it gets there"
    assert len(w.reel) == 1, "one reel queued"

    tl = w.reel[0]
    assert tl[0] == ("start", config.SPAWN), "it starts where the rover did"
    ks = kinds(tl)
    assert ks[1] == "plan", "it plans before it moves"
    assert ks.count("block") > 1, "it was surprised"
    # A fresh plan after every surprise, and that is the thing worth watching: each one
    # ran through an outcrop nobody had seen.
    assert ks.count("plan") == ks.count("block") + 1, "and laid a fresh plan after each"

    steps = [d for k, d in tl if k == "step"]
    assert len(steps) == r.steps, "a step per tile actually driven"
    assert all(config.ARENA[c[1]][c[0]] not in SOLID for c, _ in steps), "and none of them is rock"
    assert steps[-1][0] == w.pos, "the last step is where it ended up"
    assert all(config.ARENA[c[1]][c[0]] == "#" for k, c in tl if k == "block"), "every block really is rock"

    first_plan = next(d for k, d in tl if k == "plan")
    assert any(config.ARENA[y][x] == "#" for x, y in first_plan), "the first plan drove through rock it had not seen"

    # The one case that legitimately has a single plan: the target itself turns out to
    # be rock, so there is nowhere else to re-route to and nav stops rather than
    # inventing a destination.
    w2 = World()
    r2 = nav.goto(w2, 14, 9)       # the south face of the formation due north
    assert r2.code == "BLOCKED" and kinds(w2.reel[0]).count("plan") == 1, "blocked *on* the target lays no second plan"


def test_pricing_a_trip_is_blue_and_moves_nothing():
    w = World()
    before = w.pos, w.steps
    nav.price(w, 15, 0)
    assert len(w.reel) == 1, "one reel queued"
    ks = kinds(w.reel[0])
    assert ks == ["start", "probe"], "a probe, not a drive"
    assert (w.pos, w.steps) == before, "nothing moved and nothing was spent"

    # An unreachable price has no route to draw, so it queues nothing rather than an
    # empty reel that would flash for a frame and mean nothing.
    w2 = World()
    w2.here.seen = {(x, y) for y in range(w2.here.h) for x in range(w2.here.w)}
    w2.pos = (16, 20)
    nav.price(w2, 17, 20)         # straight into a known outcrop
    assert not w2.reel, "an unreachable price draws nothing"


def test_the_fog_opens_in_time_with_the_drive():
    """The reel holds revealed ground shut until the step that revealed it is drawn.

    The world jumps and the screen lags it on purpose: `goto` returns with the whole
    route driven and every disc along it already open in `seen`. If the reel showed that
    straight away, the map would peel back before the rover had been drawn moving, and
    the drive would explain nothing. So what the world has seen stays veiled until the
    step that bought it plays.

    Prototype 7 tested exactly this and prototype 8 could not -- a blind rover has no
    fog to hold back. It is the drive's assertion again.
    """
    w = World()
    nav.goto(w, 15, 0)
    far = w.pos
    assert w.here.visible(*far), "the world has already seen where it ended up"

    reel = anim.Reel(w)
    reel.tick(0.001)
    assert reel.veiled(far), "but the reel holds it back until the rover is drawn there"
    assert reel.where(w.pos) == config.SPAWN, "and it is drawn back at the pad"

    play(reel)
    assert not reel.veiled(far), "by the end nothing is veiled"
    assert reel.where(w.pos) == w.pos, "and the rover has arrived"


def test_the_plan_is_torn_up_when_it_is_wrong():
    w = World()
    # West across the C's mouth. The plan is drawn straight through the spine, which is
    # fog until it is driven at, so the yellow really does cross rock and really is torn
    # up. A route that merely passes a rectangle walks around it with nothing to see.
    nav.goto(w, 2, 14)
    reel = anim.Reel(w)

    saw_plan_over_rock = saw_retracting = saw_pruned_to_rover = False
    lengths = []
    while reel.busy:
        reel.tick(1 / 60)
        if any(config.ARENA[y][x] == "#" for x, y in reel.plan):
            saw_plan_over_rock = True
        if reel.bump:
            lengths.append(len(reel.plan))
            # Retracted rather than blinked out: it ends where the rover is standing.
            if reel.plan and reel.plan[-1] == reel.at:
                saw_pruned_to_rover = True
    if len(lengths) > 2:
        saw_retracting = any(b < a for a, b in zip(lengths, lengths[1:]))

    assert saw_plan_over_rock, "the plan was drawn straight through an outcrop"
    assert saw_retracting, "and withdrew a cell at a time when one refused"
    assert saw_pruned_to_rover, "back to the cell the rover was standing on"


def test_the_reel_never_changes_the_world():
    w = World()
    nav.goto(w, 15, 0)
    after = (w.pos, w.steps, w.day, len(w.here.seen), len(w.here.visited),
             len(w.nav_log), w.last_walk[1][:], w.last_path[1][:])

    reel = anim.Reel(w)
    play(reel)
    now = (w.pos, w.steps, w.day, len(w.here.seen), len(w.here.visited),
           len(w.nav_log), w.last_walk[1][:], w.last_path[1][:])
    assert after == now, "nothing about the world moved"

    # And the same holds if nobody ever draws it, which is how every other test runs.
    w2 = World()
    nav.goto(w2, 15, 0)
    assert w2.pos == w.pos, "an undrawn reel changes nothing either"


def test_skipping_lands_exactly_where_the_world_already_is():
    w = World()
    nav.goto(w, 15, 0)
    nav.goto(w, 12, 0)
    reel = anim.Reel(w)
    for _ in range(30):
        reel.tick(1 / 60)
    assert reel.where(w.pos) != w.pos, "mid-drive, the drawing is behind"

    reel.skip()
    assert not reel.busy and not w.reel, "skipping empties the queue"
    assert reel.where(w.pos) == w.pos, "and shows the rover where it really is"
    assert not reel.veiled((15, 0)), "with nothing left veiled"


def test_a_long_stall_catches_up_rather_than_crawling():
    w = World()
    nav.goto(w, 15, 0)
    reel = anim.Reel(w)
    reel.tick(0.001)
    reel.tick(30.0)              # the model held the loop for thirty seconds
    assert not reel.busy, "it does not then play out in slow motion"
    assert reel.where(w.pos) == w.pos, "and it is caught up"


def test_turning_it_off_records_nothing():
    settings.ANIMATE = False
    try:
        w = World()
        nav.goto(w, 15, 0)
        nav.price(w, 5, 5)
        assert not w.reel, "no reels are kept"
        assert w.pos == (15, 0), "but the drive still happened"
        assert not anim.Reel(w).busy, "and a reel over an empty queue is never busy"
    finally:
        settings.ANIMATE = True


def test_work_takes_time_on_screen_like_driving():
    """The day's clock is the wall clock, so work is drawn a step at a time: that is
    what makes `execute` cost the day as well as the battery."""
    w = World()
    i = w.interests[0]
    w.pos = (i.cell[0], i.cell[1] + 1)
    w.execute(i)
    assert (len(w.reel) == 1
               and kinds(w.reel[0]) == ["work"]), "examining queues a reel of its own"
    frames = anim.frames(w.reel[0])
    assert (len(frames) == i.cost
                and frames[-1][1] == (i.cell, i.cost, i.cost)), "one frame a step of work"
    reel = anim.Reel(w)
    reel.tick(1 / 60)
    assert reel.busy and reel.work and reel.work[0] == i.cell, "while it plays, the reel is busy and shows the progress"
    drawn = play(reel) / 60
    step = settings.ANIM_STEP / settings.ANIM_SPEED
    assert abs(drawn - i.cost * step) <= step + 0.05, "and it takes a driving step's time per step of work, to within one"
    assert not reel.busy and reel.work is None, "then it clears"


def test_the_queue_cannot_grow_forever():
    w = World()
    for i in range(settings.REEL_MAX * 3):
        w.pos = config.SPAWN
        nav.price(w, 15, 0)
    assert len(w.reel) == settings.REEL_MAX, "capped"
