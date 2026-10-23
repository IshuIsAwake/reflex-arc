"""The link, end to end: the real hardware/pi/server.py with fake motors, and the laptop's
RoverLink talking to it over TCP, as LINK.md describes."""
import os
import socket
import subprocess
import sys

import pytest

from link import RoverLink

PI = os.path.join(os.path.dirname(__file__), "..", "hardware", "pi")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def rover():
    """A fake rover server on a free port, and a link to it."""
    port = free_port()
    # Its own process: the Pi's config.py and settings.py share names with the game's.
    server = subprocess.Popen([sys.executable, "-u", "server.py", "--fake", "--fast",
                               "--port", str(port)], cwd=PI, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
    server.stdout.readline()  # "rover listening on port ..."
    link = RoverLink("127.0.0.1", port, timeout=5)
    yield link
    link.close()
    server.kill()
    server.wait()


def test_hello_says_where_the_rover_is(rover):
    hi = rover.hello()
    assert hi["ok"] and hi["fake"]
    assert hi["pose"] == {"x": 0, "y": 0, "heading": "N"}


def test_a_drive_reports_each_command_then_where_it_ended(rover):
    steps = []
    end = rover.drive(["N", "N", "E"], on_step=steps.append)
    assert [s["i"] for s in steps] == [1, 2, 3]
    assert [s["cmd"] for s in steps] == ["N", "N", "E"]
    assert end == {"x": 1, "y": -2, "heading": "E"}


def test_reset_and_set_pose_say_where_it_is_now(rover):
    rover.drive(["F"])
    assert rover.reset("E")["pose"] == {"x": 0, "y": 0, "heading": "E"}
    assert rover.set_pose(3, -2, "S")["pose"] == {"x": 3, "y": -2, "heading": "S"}


def test_a_stop_then_a_reset_gets_the_reset_answer(rover):
    rover.hello()
    rover.stop()
    assert rover.reset("N")["pose"] == {"x": 0, "y": 0, "heading": "N"}


def test_a_bad_message_is_answered_and_the_connection_stays(rover):
    answer = rover.ask({"op": "reset", "heading": "Q"})
    assert answer["ok"] is False and "note" in answer
    answer = rover.ask({"op": "set_pose", "y": 2, "heading": "N"})
    assert answer["ok"] is False
    assert rover.hello()["ok"], "the same connection still answers"
