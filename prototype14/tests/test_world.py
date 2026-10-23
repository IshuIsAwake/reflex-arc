"""The arena itself, and the shape of a sol.


**Run this after editing the map in config.py.** The flood-fill is the reason it
exists: a sealed pocket of ground is invisible until somebody has wasted a whole sol
driving toward it, and prototype 1's version of this test caught two of them.
"""

from collections import Counter, deque

import config
import settings
from world import SOLID, World



def arena_rock():
    """Every rock cell of the loaded arena, seen or not."""
    rock = set()
    for y, row in enumerate(config.ARENA):
        for x, ch in enumerate(row):
            if ch == "#":
                rock.add((x, y))
    return rock

def flood(start):
    """Every cell reachable from `start` over the true grid."""
    rows = config.ARENA
    h, w = len(rows), len(rows[0])

    def ch(x, y):
        return "." if rows[y][x] == "@" else rows[y][x]

    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen:
                continue
            if ch(nx, ny) in SOLID:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def test_the_map_is_the_shape_it_claims():
    rows = config.ARENA
    assert len(rows) == 30, f"{len(rows)} rows"
    for y, r in enumerate(rows):
        assert len(r) == 30, f"row {y} is {len(r)} wide"
        assert set(r) <= set("#.H@"), f"row {y} has an undeclared tile: {set(r) - set('#.H@')}"
    assert sum(r.count("@") for r in rows) == 1, "exactly one landing point"
    assert rows[config.SPAWN[1]][config.SPAWN[0]] == "@", "SPAWN and the @ must agree"


def test_the_whole_arena_is_one_region():
    """No sealed pockets. Cheap to check, and the failure it prevents costs a sol.

    It also lets the prompt promise that every non-rock cell is reachable, which is
    otherwise a claim nobody is holding to.
    """
    rows = config.ARENA
    h, w = len(rows), len(rows[0])
    ground = {(x, y) for y in range(h) for x in range(w) if rows[y][x] in ".@"}
    reached = flood(config.SPAWN)
    stranded = ground - reached
    assert not stranded, f"{len(stranded)} cells sealed off, e.g. {sorted(stranded)[:5]}"
    assert len(ground) > 700, f"only {len(ground)} drivable cells -- the arena got dense"
    # The other direction, added 2026-08-29 when the map went from 517 rock to 241. A
    # one-sided bound only ever caught the arena filling up, and the failure available
    # now is the opposite one: a plain empty enough that no route costs more than its
    # straight line and `distance` is never wrong about anything.
    assert len(ground) < 830, f"{len(ground)} drivable cells -- the arena got empty"


# The thirteen boulders, as one cell of each and the size the finder must recover. Written
# down rather than computed, because a test that recomputes the thing it is checking
# agrees with any map at all.
# Two medium classes now, not one. The 30 used to be twelve nines and a sixteen; it is
# sixes and eights under a single twelve, which is the C.
MEDIUM, LARGE = (6, 8), 12
BOULDERS = [(12, (3, 11)),
            (6, (2, 22)), (6, (9, 3)), (6, (13, 7)), (6, (17, 20)), (6, (21, 26)),
            (6, (24, 10)),
            (8, (10, 24)), (8, (20, 2)), (8, (25, 17))]


# What each arena is made of, written down rather than computed, for the reason above.
# `(a cell in the largest formation, the whole size histogram)`.
#
# **Both arenas are guarded, and that is the point of this table.** Only the default one
# used to be, so the 50x50 sat at twenty tied sixteens with no largest formation at all
# and "which is the biggest rock" was put to a model four times before anyone checked.
GEOLOGY = {"30": ((3, 11), {6: 6, 8: 3, 12: 1}),
           "50": ((30, 15), {9: 10, 16: 20, 30: 1})}


def test_every_arena_has_one_largest_formation():
    """The question "which is the biggest" must have exactly one answer, on every map.

    A tie is not a harder question, it is an unanswerable one, and a model asked it will
    invent a ranking rather than say so -- measured 2026-09-04, the 31B produced a tidy
    descending list of nine sizes where the truth was twenty ties.
    """
    from world import components
    was = config.ARENA
    try:
        for name, (cell, sizes) in GEOLOGY.items():
            config.use(name)
            h, w = len(config.ARENA), len(config.ARENA[0])
            rock = components(w, h, arena_rock())
            got = Counter(len(c) for c in rock)
            assert got == sizes, f"{name}x{name}: sizes are {dict(got)}, not {sizes}"

            biggest = max(sizes)
            assert got[biggest] == 1, \
                f"{name}x{name}: {got[biggest]} formations tie at {biggest} cells"
            holding = [c for c in rock if cell in c]
            assert holding, f"{name}x{name}: no rock at {cell}"
            assert len(holding[0]) == biggest, \
                f"{name}x{name}: the formation at {cell} is {len(holding[0])}, not {biggest}"
    finally:
        config.ARENA = was
        config.use(config.DEFAULT_ARENA)


def test_the_geology_is_exactly_what_was_authored():
    """Nine medium formations, exactly one large, and nothing else at all.

    Formation identity is not written on the map -- there is no tile character for it.
    It is recovered by flood-filling the rock and reading sizes, so the map has to be
    authored such that the answer is unambiguous.

    **No size bands.** An older arena mixed boulders with ridges and had to classify by
    a size *range*, where a ridge segment landing in it became a boulder nobody placed.
    Every component here is six, eight or twelve, so a merge (14) or a split fails
    outright rather than being absorbed as a legal size.

    **Exactly one large one** is the other half. Twenty tied sixteens made "the biggest
    formation" a question with no answer, and it was asked twice before anyone noticed.

    Checked by the size of the component *containing a named cell*, not just the
    histogram, because two formations merging while a third splits leaves the count
    right.
    """
    from world import components
    h, w = len(config.ARENA), len(config.ARENA[0])
    rock = components(w, h, arena_rock())

    assert sum(1 for c in rock if len(c) == LARGE) == 1, \
        "there must be exactly one largest formation, or the question has no answer"

    assert len(rock) == len(BOULDERS), \
        f"{len(rock)} components, not {len(BOULDERS)}: {sorted(len(c) for c in rock)}"
    odd = sorted(len(c) for c in rock if len(c) not in (*MEDIUM, LARGE))
    assert not odd, f"components that are neither medium nor large: {odd}"
    assert sorted(len(c) for c in rock) == sorted(n for n, _ in BOULDERS), \
        f"class counts are wrong: {sorted(len(c) for c in rock)}"

    by_cell = {cell: c for c in rock for cell in c}
    for size, cell in BOULDERS:
        assert cell in by_cell, f"no rock at {cell} -- a boulder went missing"
        got = len(by_cell[cell])
        assert got == size, f"the boulder at {cell} is {got} cells, not {size}"

    # **Two clear cells between any two of them**, in Chebyshev. The flood fill separates
    # them at one, but on screen a run of near-touching lumps reads as a single mass, and
    # being recognisable as separate boulders is what the arena is for.
    for a in rock:
        near = {(x + dx, y + dy) for (x, y) in a
                for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)} - a
        for b in rock:
            if b is not a:
                assert not (near & b), f"two boulders within two cells, near {min(a)}"


def test_the_pad_is_behind_the_landing_point():
    rows = config.ARENA
    pad = {(x, y) for y in range(len(rows)) for x in range(len(rows[0]))
           if rows[y][x] == "H"}
    assert pad, "there is no base pad"
    sx, sy = config.SPAWN
    assert (sx, sy + 1) in pad, "the pad should sit directly behind where the rover lands"
    assert all(abs(x - sx) <= 2 and 0 < y - sy <= 3 for x, y in pad), \
        f"the pad has drifted away from the landing point: {sorted(pad)}"

    w = World()
    assert w.base == min(pad), (w.base, min(pad))
    assert w.here.blocked(*w.base), "the pad is solid -- you stop beside it"


def test_the_landing_site_is_visible_on_arrival():
    """Sol one should open on ground, not on a screen of '?'. Everything past the
    landing site is still earned by driving."""
    w = World()
    seen = len(w.here.seen)
    assert seen > 80, f"only {seen} cells visible at the pad"
    assert seen < 400, f"{seen} cells is not a landing site, it is a free map"
    assert not w.here.visible(2, 2), "the far corner must still be fog"


def test_a_move_into_rock_costs_nothing():
    """The exact test, because `nav` detects a refused drive by the step not being
    charged rather than by the position not changing."""
    w = World()
    w.pos = (16, 20)  # just west of the formation at (17,20)
    assert config.ARENA[20][17] == "#"
    before = w.steps
    w.move(1, 0)
    assert w.pos == (16, 20) and w.steps == before, (w.pos, w.steps)

    w.move(0, -1)
    assert w.pos == (16, 19) and w.steps == before + 1


def test_driving_opens_fog_and_still_remembers_where_it_went():
    """Driving west across the landing plain. The route is not assumed to be clear --
    it stops where the ground does, and the assertions are about whatever it reached.

    The rover can see again, so this is prototype 8's assertion back the right way up.
    Seen and stood-on stay two different sets, and it is the *other* direction that
    matters now: everything driven over has been seen, and a great deal more besides.
    """
    w = World()
    start = w.pos
    seen_before = set(w.here.seen)
    while True:
        before = w.pos
        w.move(-1, 0)
        if w.pos == before:
            break
    assert w.pos[0] < start[0] - 8, f"only got to {w.pos}, expected an open plain west"

    assert w.here.seen > seen_before, "driving has to lift fog"
    assert w.here.visible(*w.pos), "starting with the cell it is standing on"
    assert w.pos in w.here.visited, \
        "stood-on is tracked separately, because avoid=auto depends on it"
    assert w.here.visited <= w.here.seen, \
        "it cannot have stood somewhere it never saw"
    assert w.here.seen - w.here.visited, \
        "...and it has seen a good deal it never stood on, which is what the disc buys"


def test_the_sol_rolls_over():
    w = World()
    w.pos = (10, 10)
    w.spend(37)
    w.elapsed = 12.5
    day, steps = w.day, w.steps
    seen = len(w.here.seen)
    w.toggle_mark((10, 10))

    w.next_day()
    assert w.day == day + 1 and w.steps == 0 and not w.day_over
    assert w.pos == (10, 10), "away from the pad at nightfall, it wakes where it stopped"
    assert w.stranded and w.battery == settings.BATTERY - 37, "on what it had left: no recharge"
    assert w.time_left == float(settings.DAY_SECONDS), "but the clock is a new sol's"
    assert w.elapsed == 0.0
    assert len(w.here.seen) >= seen, "the survey carries over"
    assert (10, 10) in w.here.marks, "and so do the marks"
    assert not w.log, "yesterday's messages do not"
    assert w.history[-1] == {"day": day, "steps": steps, "seconds": 12.5, "at": [10, 10],
                             "docked": False, "battery": settings.BATTERY - 37}, \
        "and how the sol ended is the world's record, not anyone's account of it"


def test_home_by_nightfall():
    w = World()
    assert w.docked, "the rover lands beside the pad"
    w.pos = (15, 18)  # south of the pad, not where it landed
    assert w.docked, "any side of the pad is home"
    w.spend(40)
    w.next_day()
    assert not w.stranded and w.pos == config.SPAWN, "woken at the pad"
    assert w.battery == settings.BATTERY, "recharged"

    w.pos = (3, 3)
    w.spend(30)
    w.next_day()
    w.spend(20)
    w.next_day()
    assert w.stranded and w.pos == (3, 3), "stranded twice, still where it stopped"
    assert w.battery == settings.BATTERY - 50, "and nothing came back either night"


def test_flat_away_from_the_pad_is_lost():
    w = World()
    w.pos = (3, 3)
    w.spend(w.battery)
    assert w.battery == 0 and w.lost, "flat, and out on the plain"
    before = w.pos
    w.move(1, 0)
    assert w.pos == before and w.steps == settings.BATTERY, "a flat rover does not move"
    w.next_day()
    assert w.battery == 0 and w.lost, "and no morning brings it back"

    w = World()
    w.pos = (3, 3)
    w.battery = 2
    assert w.lost, "two charge and the pad twenty-odd steps off is lost, though not flat"
    w.battery = 40
    assert not w.lost, "enough for the trip back is only stranded"

    w = World()
    w.spend(w.battery)
    assert not w.lost, "flat beside the pad is not lost"
    w.next_day()
    assert w.battery == settings.BATTERY, "the pad charges it"


def test_the_day_runs_on_the_wall_clock():
    w = World()
    assert w.phase == "dawn" and w.time_left == float(settings.DAY_SECONDS)
    w.spend(10)
    assert w.battery == settings.BATTERY - 10, "steps drain the battery"
    assert w.time_left == float(settings.DAY_SECONDS), "and take no time of their own"

    w.tick(9.0)
    assert w.elapsed == 9.0, "the stopwatch runs"
    assert w.time_left == float(settings.DAY_SECONDS), "and the frame rate is not the day's clock"

    w.run_clock(settings.DAY_SECONDS - 1)
    assert not w.day_over and w.time_left == 1.0
    w.run_clock(2)
    assert w.day_over and w.time_left == 0.0, "the clock ends the day"
    assert w.battery > 0, "with charge to spare"

    w = World()
    w.spend(w.battery)
    assert w.battery == 0 and w.day_over, "a flat battery ends the day"
    w = World()
    w.drain(settings.BATTERY)
    assert w.day_over and w.steps == 0, "so does one drained by the radio, with no step taken"


def test_the_recorder_hears_everything_and_is_optional():
    """`world.py` does no I/O. The log gets written because `logs.Run.record` is
    handed in, and everything else -- every test above -- runs with no recorder at
    all."""
    assert World().recorder is None

    seen = []
    w = World(recorder=lambda kind, **f: seen.append((kind, f)))
    assert seen[0][0] == "day_open" and seen[0][1]["day"] == 1
    w.say("BLOCKED(at=(1,1))", "bad")
    w.next_day()
    kinds = [k for k, _ in seen]
    assert kinds == ["day_open", "say", "day_close", "day_open"], kinds
    assert seen[1][1]["tone"] == "bad"
    assert seen[2][1]["day"] == 1 and seen[3][1]["day"] == 2
