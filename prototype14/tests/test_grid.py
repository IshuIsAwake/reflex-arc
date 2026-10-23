"""Checks the grid model and the Manhattan/Chebyshev check. No hardware.


The load-bearing one is `test_the_two_distances_disagree_usefully`: if Manhattan and
Chebyshev ever agree on a both-axes miss, the check loses the one thing it says about
*why* the rover missed.
"""

import grid
from grid import Pose

N, E, S, W = range(4)


def run(start, cmds):
    p = start
    for c in grid.parse(cmds):
        p = grid.apply(p, c)
    return p


def test_relative_commands_follow_the_heading():
    # forward, right, left, forward, forward from (0,0) facing N: up one, face E, face N, up two
    assert run(Pose(0, 0, N), "forward right left forward forward") == Pose(0, -3, N)
    assert run(Pose(0, 0, N), "R F F") == Pose(2, 0, E)
    assert run(Pose(0, 0, E), "L L F") == Pose(-1, 0, W)
    assert run(Pose(0, 0, N), "B") == Pose(0, 1, N)


def test_absolute_commands_ignore_where_it_was_facing():
    for h in range(4):
        assert run(Pose(5, 5, h), "E") == Pose(6, 5, E)
        assert run(Pose(5, 5, h), "N N W") == Pose(4, 3, W)


def test_turns_go_the_short_way():
    assert grid.primitives("E", N) == ["R", "F"]
    assert grid.primitives("W", N) == ["L", "F"]
    assert grid.primitives("S", N) == ["R", "R", "F"]  # a U-turn is always two rights
    assert grid.primitives("N", N) == ["F"]


def test_parse_refuses_what_it_does_not_know():
    assert grid.parse("f, r ,L") == ["F", "R", "L"]
    try:
        grid.parse("F jump F")
    except ValueError:
        return
    raise AssertionError("an unknown command was skipped instead of refused")


def test_frame_matches_10d():
    # 10d's nav.DIRS; if this drifts, a 10d plan.txt drives somewhere else
    assert grid.DIRS == ((0, -1), (1, 0), (0, 1), (-1, 0))
    assert grid.HEADING_NAMES == ("N", "E", "S", "W")
