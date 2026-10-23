"""Checks the scan matcher on made-up rooms. No LiDAR needed.

    python test_locate.py

Scans are cast from known poses into a room of line segments, with 1 cm of noise and
the LD19's ~500 rays a turn. The load-bearing test is the plain rectangle seen from its
centre: it looks the same turned 180 deg, which is what flipped AMCL in the lab. With
the search kept around the expected pose, the flip must never come back.
"""

import math

import numpy as np

import locate as L

RNG = np.random.default_rng(0)

# The room and the ray caster live in fake_world.py, which the drive tests share.
from fake_world import ROOM as _ALL, cast as _cast

ROOM, BOX = _ALL[:4], _ALL[4:]


def cast(segments, pose, rays=500, noise=0.01):
    """A scan, in the rover frame, from `pose` in the map frame."""
    return _cast(segments, pose, rays, noise, RNG)


def ref_at_home(segments):
    xs, ys = cast(segments, (0.0, 0.0, 0.0))
    return L.Reference(xs, ys)


def off(res, truth):
    x, y, yaw = res["pose"]
    dyaw = math.degrees((yaw - truth[2] + math.pi) % (2 * math.pi) - math.pi)
    return math.hypot(x - truth[0], y - truth[1]), abs(dyaw)


def test_finds_a_carried_move_and_a_turn():
    walls = ROOM + BOX
    ref = ref_at_home(walls)
    for truth in [(0.40, 0.0, 0.0), (0.0, -0.20, 0.0), (0.0, 0.0, math.radians(-90)),
                  (0.40, -0.20, math.radians(-90)), (-0.25, 0.10, math.radians(12))]:
        guess = (round(truth[0] / 0.2) * 0.2, round(truth[1] / 0.2) * 0.2,
                 round(truth[2] / (math.pi / 2)) * math.pi / 2)    # "where the grid said"
        res = L.locate(ref, *cast(walls, truth), guess)
        d, a = off(res, truth)
        assert res["status"] == "OK", (truth, res)
        assert d < 0.03 and a < 1.5, f"{truth}: off by {d:.3f} m, {a:.1f} deg"


def test_the_symmetric_room_does_not_flip():
    ref = ref_at_home(ROOM)                    # no box: same turned 180 deg about the centre
    truth = (0.30, 0.0, math.radians(5))
    res = L.locate(ref, *cast(ROOM, truth), (0.2, 0.0, 0.0))
    d, a = off(res, truth)
    assert a < 2 and d < 0.03, f"flipped or lost: {res['pose']}"


def test_a_scan_from_somewhere_else_is_poor():
    ref = ref_at_home(ROOM + BOX)
    other = [((-3, -3), (5, -3)), ((5, -3), (5, 6)), ((5, 6), (-3, 6)), ((-3, 6), (-3, -3))]
    res = L.locate(ref, *cast(other, (0, 0, 0)), (0, 0, 0))
    assert res["status"] == "POOR", res


def test_a_person_in_the_way_does_not_move_the_answer():
    walls = ROOM + BOX
    ref = ref_at_home(walls)
    truth = (0.40, 0.0, 0.0)
    person = [((0.9, -0.3), (1.1, -0.3)), ((1.1, -0.3), (1.1, -0.1)),
              ((1.1, -0.1), (0.9, -0.1)), ((0.9, -0.1), (0.9, -0.3))]
    res = L.locate(ref, *cast(walls + person, truth), (0.4, 0.0, 0.0))
    d, a = off(res, truth)
    assert d < 0.03 and a < 1.5, (d, a)


def test_cells_round_trip():
    for gx, gy, h in [(0, 0, 0), (3, -2, 1), (-1, 4, 2), (2, 2, 3)]:
        assert L.to_cell(L.from_cell(gx, gy, h, 0.2), 0.2) == (gx, gy, h)
    # north is map +x, east is map -y
    assert L.to_cell((0.2, 0.0, 0.0), 0.2) == (0, -1, 0)
    assert L.to_cell((0.0, -0.2, math.radians(-90)), 0.2) == (1, 0, 1)


if __name__ == "__main__":
    import time
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            t = time.perf_counter()
            fn()
            print(f"  {name}  {time.perf_counter() - t:.2f} s")
    print("all locate checks passed")
