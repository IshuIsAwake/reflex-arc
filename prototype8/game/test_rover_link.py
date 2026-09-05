"""Checks the plan-file parsing, especially the two expansions -- BACKWARD and
LEFT -- that stand in for moves this rover cannot make directly. Nothing here
touches the network; `drive`/`watch` are not covered, the same way `nav`'s tests
never open a socket either.

    .venv\\Scripts\\python.exe game\\test_rover_link.py
"""

import os
import tempfile

import rover_link as RL


def _write(lines):
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def test_comments_and_metadata_are_skipped():
    path = _write([
        "# reflex-arc live route -- one objective, every leg of it.",
        "# goal (2,2), executor=teleport",
        "# cells: (0,0) (1,0) (2,0)",
        "FORWARD",
        "FORWARD",
        "# note: the simulation does not turn, so facing is assumed.",
    ])
    try:
        assert RL.actions_from_file(path) == ["FORWARD", "FORWARD"]
    finally:
        os.remove(path)


def test_a_finished_leg_stays_commented_out():
    # `nav.write_plan` prefixes every action of a non-live leg with `#`, so it
    # must not resurface here -- only the live leg's two FORWARDs should.
    path = _write([
        "# leg 1/2  BLOCKED  ...",
        "# FORWARD",
        "# RIGHT",
        "# leg 2/2  LIVE  ...",
        "FORWARD",
        "FORWARD",
    ])
    try:
        assert RL.actions_from_file(path) == ["FORWARD", "FORWARD"]
    finally:
        os.remove(path)


def test_backward_expands_to_two_turns_a_forward_and_two_turns_back():
    path = _write(["FORWARD", "BACKWARD", "RIGHT"])
    try:
        assert RL.actions_from_file(path) == [
            "FORWARD", "RIGHT", "RIGHT", "FORWARD", "RIGHT", "RIGHT", "RIGHT"]
    finally:
        os.remove(path)


def _drive(actions):
    """Where a pulse list actually leaves the rover, as (cell, heading), starting at
    (0,0) facing north. Turns are exactly 90 degrees here -- the point is the plan's
    geometry, not the chassis's calibration."""
    dirs = ((0, -1), (1, 0), (0, 1), (-1, 0))       # nav.DIRS, clockwise from north
    (x, y), h = (0, 0), 0
    for a in actions:
        if a == "RIGHT":
            h = (h + 1) % 4
        elif a == "FORWARD":
            x, y = x + dirs[h][0], y + dirs[h][1]
    return (x, y), h


def test_a_route_with_a_backward_still_ends_where_the_plan_says():
    """The regression that matters: BACKWARD leaves the plan's heading alone, so an
    expansion that ends 180 degrees out drives every later action mirrored. Before the
    turn-back this route finished at (1,1) facing north instead of (-1,1) facing west
    -- right about the reverse, wrong about everything after it."""
    path = _write(["BACKWARD", "LEFT", "FORWARD"])
    try:
        # Plan: reverse one cell to (0,1) still facing north, turn to face west, and
        # step to (-1,1). Only FORWARD and RIGHT are ever sent.
        assert _drive(RL.actions_from_file(path)) == ((-1, 1), 3)
    finally:
        os.remove(path)


def test_every_expansion_leaves_the_heading_the_plan_expects():
    # `route_actions`: LEFT ends facing west, RIGHT east, BACKWARD and FORWARD north.
    for line, heading in (("LEFT", 3), ("BACKWARD", 0), ("RIGHT", 1), ("FORWARD", 0)):
        path = _write([line])
        try:
            assert _drive(RL.actions_from_file(path))[1] == heading, line
        finally:
            os.remove(path)


def test_left_expands_to_three_right_turns():
    # The hardware fact this guards: the left motor cannot reverse, so a LEFT
    # pivot cannot be driven directly at all. Three RIGHT turns (270 degrees)
    # land on the same heading as one LEFT turn (90 degrees) and never touch
    # the broken pivot.
    path = _write(["FORWARD", "LEFT", "FORWARD"])
    try:
        assert RL.actions_from_file(path) == ["FORWARD", "RIGHT", "RIGHT", "RIGHT", "FORWARD"]
    finally:
        os.remove(path)


def test_empty_file_yields_no_actions():
    path = _write(["# nothing to drive", "# NO ROUTE -- the planner has none."])
    try:
        assert RL.actions_from_file(path) == []
    finally:
        os.remove(path)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all rover_link checks passed")
