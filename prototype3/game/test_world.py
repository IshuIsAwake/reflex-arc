"""The arena itself, and the shape of a sol.

    .venv/bin/python game/test_world.py

**Run this after editing the map in config.py.** The flood-fill is the reason it
exists: a sealed pocket of ground is invisible until somebody has wasted a whole sol
driving toward it, and prototype 1's version of this test caught two of them.
"""

from collections import deque

import config as C
import settings as S
from world import SOLID, World


def flood(start):
    """Every cell reachable from `start` over the true grid."""
    rows = C.ARENA
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
    rows = C.ARENA
    assert len(rows) == 50, f"{len(rows)} rows"
    for y, r in enumerate(rows):
        assert len(r) == 50, f"row {y} is {len(r)} wide"
        assert set(r) <= set("#.H@"), f"row {y} has an undeclared tile: {set(r) - set('#.H@')}"
    assert sum(r.count("@") for r in rows) == 1, "exactly one landing point"
    assert rows[C.SPAWN[1]][C.SPAWN[0]] == "@", "SPAWN and the @ must agree"


def test_the_whole_arena_is_one_region():
    """No sealed pockets. Cheap to check, and the failure it prevents costs a sol."""
    rows = C.ARENA
    ground = {(x, y) for y in range(50) for x in range(50) if rows[y][x] in ".@"}
    reached = flood(C.SPAWN)
    stranded = ground - reached
    assert not stranded, f"{len(stranded)} cells sealed off, e.g. {sorted(stranded)[:5]}"
    assert len(ground) > 1800, f"only {len(ground)} drivable cells -- the arena got dense"
    # The other direction, added 2026-08-29 when the map went from 517 rock to 241. A
    # one-sided bound only ever caught the arena filling up, and the failure available
    # now is the opposite one: a plain empty enough that no route costs more than its
    # straight line and `distance` is never wrong about anything.
    assert len(ground) < 2350, f"{len(ground)} drivable cells -- the arena got empty"


# The thirty boulders, as one cell of each and the size the finder must recover. Written
# down rather than computed, because a test that recomputes the thing it is checking
# agrees with any map at all.
MEDIUM, LARGE = 9, 16
BOULDERS = [(16, (3, 26)), (16, (4, 49)), (16, (9, 35)), (16, (10, 24)), (16, (12, 7)),
            (16, (12, 39)), (16, (12, 45)), (16, (13, 13)), (16, (18, 34)),
            (16, (19, 16)), (16, (21, 43)), (16, (23, 2)), (16, (24, 37)),
            (16, (27, 10)), (16, (32, 26)), (16, (39, 2)), (16, (40, 40)),
            (16, (41, 9)), (16, (42, 32)), (16, (44, 24)),
            (9, (0, 9)), (9, (0, 20)), (9, (4, 42)), (9, (7, 20)), (9, (10, 29)),
            (9, (18, 3)), (9, (32, 34)), (9, (35, 7)), (9, (46, 20)), (9, (47, 38))]


def test_the_geology_is_exactly_what_was_authored():
    """Twenty large boulders, ten medium, and nothing else at all.

    Boulder identity is not written on the map -- there is no tile character for it. It
    is recovered by flood-filling the rock and reading sizes, so the map has to be
    authored such that the answer is unambiguous.

    **Dropping the ridges made that much stronger.** The previous arena mixed twelve
    boulders with five long ridges and had to classify by a size *band*, where a ridge
    segment landing in range became a thirteenth boulder nobody placed -- and on the
    arena before that, 49 of 73 rock components sat in the band. With nothing but
    boulders there is no band and no reclassification: every component is nine or
    sixteen, so a merge (25) or a split fails outright.

    Checked by the size of the component *containing a named cell*, not just the
    histogram, because two boulders merging while a third splits leaves the count right.
    """
    from world import components
    rock = components(50, 50, lambda x, y: C.ARENA[y][x] == "#")

    assert len(rock) == len(BOULDERS), \
        f"{len(rock)} components, not {len(BOULDERS)}: {sorted(len(c) for c in rock)}"
    odd = sorted(len(c) for c in rock if len(c) not in (MEDIUM, LARGE))
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
    rows = C.ARENA
    pad = {(x, y) for y in range(50) for x in range(50) if rows[y][x] == "H"}
    assert pad, "there is no base pad"
    sx, sy = C.SPAWN
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
    w.pos = (32, 29)
    assert C.ARENA[29][33] == "#"
    before = w.steps
    w.move(1, 0)
    assert w.pos == (32, 29) and w.steps == before, (w.pos, w.steps)

    w.move(0, -1)
    assert w.pos == (32, 28) and w.steps == before + 1


def test_driving_reveals_and_remembers():
    """Driving west across the landing plain. The route is not assumed to be clear --
    it stops where the ground does, and the assertions are about whatever it reached."""
    w = World()
    start = w.pos
    while True:
        before = w.pos
        w.move(-1, 0)
        if w.pos == before:
            break
    assert w.pos[0] < start[0] - 8, f"only got to {w.pos}, expected an open plain west"

    edge = (w.pos[0] - S.VISION_RADIUS, w.pos[1])
    assert w.here.visible(*edge), "driving has to reveal what it drove past"
    assert w.pos in w.here.visited and edge not in w.here.visited, \
        "seen and stood-on are different sets, and avoid=auto depends on that"

    far_west = w.pos
    w.pos = start
    assert w.here.visible(*far_west), "and a cell stays known once seen"
    assert not w.here.visible(2, 2), "without going there, though"


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
    assert w.pos == C.SPAWN, "the rover wakes at the pad"
    assert w.elapsed == 0.0
    assert len(w.here.seen) >= seen, "the survey carries over"
    assert (10, 10) in w.here.marks, "and so do the marks"
    assert not w.log, "yesterday's messages do not"
    assert w.history[-1] == {"day": day, "steps": steps, "seconds": 12.5}


def test_gemma_mode_counts_steps():
    assert S.DAY_MODE == "gemma", "these tests run in the mode the game ships in"
    w = World()
    assert w.steps_left == S.DAY_STEPS
    w.spend(S.DAY_STEPS - 1)
    assert not w.day_over and w.steps_left == 1
    w.spend()
    assert w.day_over and w.steps_left == 0

    w.tick(9.0)
    assert w.elapsed == 9.0, "the stopwatch runs even though it charges nothing"
    assert w.time_left == float(S.DAY_SECONDS), "and the clock is not the budget"


def test_human_mode_still_counts_seconds():
    S.DAY_MODE = "human"
    try:
        w = World()
        w.tick(S.DAY_SECONDS - 1)
        assert not w.day_over and w.time_left == 1.0
        w.tick(2)
        assert w.day_over and w.time_left == 0.0
        before = w.steps
        w.spend(9999)
        assert w.steps == before + 9999, "steps are counted, they are just not the budget"
    finally:
        S.DAY_MODE = "gemma"


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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all world checks passed")
