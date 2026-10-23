"""Checks the room fit on made-up rooms. No LiDAR needed.

    python test_room_fit.py
"""

import room_fit as R
from fake_world import _box, cast


def scan(segments):
    return cast(segments, (0, 0, 0), rays=1000, noise=0.005)


def test_the_nearest_wall_sets_the_size():
    r = R.fit(*scan(_box(-4, -4, 4, 4)))              # 8 x 8 m, home in the middle
    assert r["status"] == "OK" and abs(r["nearest_m"] - 4.0) < 0.03
    assert abs(r["map_m"] - 2 * (4.0 - R.MARGIN_M)) < 0.1 and abs(r["cell_m"] - 0.24) < 0.01


def test_off_centre_home_uses_the_nearer_wall():
    r = R.fit(*scan(_box(-2.5, -4, 5.5, 4)))          # south wall 2.5 m, north 5.5 m
    assert abs(r["nearest_m"] - 2.5) < 0.03 and r["nearest_dir"] == "south", r


def test_too_small_says_clear_the_map_and_keeps_nothing():
    r = R.fit(*scan(_box(-4, -4, 4, 4) + _box(-0.2, -1.4, 0.2, -1.0)))   # a chair 1 m east
    assert r["status"] == "TOO_SMALL" and r["cell_m"] is None
    assert r["message"].startswith("clear the map") and "east" in r["message"], r["message"]


def test_a_box_near_the_squares_corner_counts():
    # 1.7 m north and 1.7 m west: 2.4 m away in a straight line, but inside a square of
    # half-side 2 -- so it must limit the map like a wall 1.7 m away.
    r = R.fit(*scan(_box(-5, -5, 5, 5) + _box(1.6, 1.6, 1.8, 1.8)))
    assert abs(r["nearest_m"] - 1.6) < 0.05, r


def test_a_big_room_is_capped_at_10_m():
    r = R.fit(*scan(_box(-7, -7, 7, 7)))
    assert r["status"] == "CAPPED" and abs(r["map_m"] - 10.0) < 0.01


def test_the_smallest_map_is_3_m():
    edge = R.MIN_SIDE_M / 2 + R.MARGIN_M
    ok = R.fit(*scan(_box(-edge - 0.05, -edge - 0.05, edge + 0.05, edge + 0.05)))
    tight = R.fit(*scan(_box(-edge + 0.05, -edge + 0.05, edge - 0.05, edge - 0.05)))
    assert ok["status"] == "OK" and ok["cell_m"] >= 0.1
    assert tight["status"] == "TOO_SMALL"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all room-fit checks passed")
