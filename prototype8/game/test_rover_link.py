"""Checks the plan-file parsing and the LEFT refusal -- the two things worth
getting wrong here. Nothing here touches the network; `drive`/`watch` are not
covered, the same way `nav`'s tests never open a socket either.

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


def test_left_voids_the_whole_drive():
    # The hardware fact this guards: the left motor cannot reverse, so a LEFT
    # pivot cannot be driven at all, not driven wrong. `drive` must refuse
    # before sending a single pulse rather than stop partway through.
    sent = []
    try:
        RL.drive("http://unused", ["FORWARD", "LEFT", "FORWARD"])
        assert False, "should have raised"
    except ValueError as e:
        assert "LEFT" in str(e)
    assert sent == []


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
