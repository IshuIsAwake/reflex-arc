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


def test_backward_expands_to_two_turns_and_a_forward():
    path = _write(["FORWARD", "BACKWARD", "RIGHT"])
    try:
        assert RL.actions_from_file(path) == ["FORWARD", "RIGHT", "RIGHT", "FORWARD", "RIGHT"]
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
