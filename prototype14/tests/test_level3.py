"""Level 3's hooks against the game's real planner. No window, no model, no Pi.

The game's goto drives a goal far enough off to need several legs; a stand-in rover
records what it was sent. The rover must get exactly the legs the game wrote to its route
file, in order, each one while the game is still paused on it.
"""

import threading
import time

import pygame

import config
import dashboard
import level3
import main
import nav
from world import World


def attach(legs):
    nav.leg_started = legs.leg_started
    nav.leg_finished = legs.leg_finished
    nav.rover_driving = legs.is_driving


class StandIn:
    def __init__(self):
        self.legs = []

    def drive(self, dirs, on_step=None):
        on_disk = open(nav.plan_file(), encoding="utf-8").read().split()
        assert on_disk == dirs, ("rover sent something other than the file", on_disk, dirs)
        self.legs.append(dirs)
        return {"x": 0, "y": 0, "heading": "N"}


def test_every_leg_reaches_the_rover_while_the_game_waits():
    rover = StandIn()
    done = threading.Event()
    handed = []

    def wait(world, dirs):  # stands in for the game's SPACE pause
        world.awaiting_rover = list(dirs)
        handed.append(list(dirs))
        assert done.wait(5), "the rover never finished the leg"
        done.clear()
        world.awaiting_rover = None

    attach(level3.RoverLegs(rover, done.set))
    nav.wait_for_rover = wait
    config.use("50")
    w = World(recorder=lambda *a, **k: None)
    nav.goto(w, 40, 40)
    assert handed, "the game handed the rover nothing"
    assert rover.legs == handed, (rover.legs, handed)
    assert open(nav.plan_file()).read() == "", "file not wiped after the last leg"


def test_a_hand_released_pause_still_drives_every_leg_in_order():
    """SPACE pressed by hand once let the game run ahead, and the rover refused the next
    legs as BUSY. They queue, and no SPACE is sent into a pause it does not own."""
    busy = threading.Lock()
    driven = []
    handed = []
    done = threading.Event()
    first = [True]

    class Slow:
        def drive(self, dirs, on_step=None):
            assert busy.acquire(blocking=False), "two legs reached the rover at once"
            try:
                time.sleep(0.15)
                driven.append(dirs)
            finally:
                busy.release()
            return {"x": 0, "y": 0, "heading": "N"}

    def wait(world, dirs):
        handed.append(list(dirs))
        world.awaiting_rover = list(dirs)
        try:
            if first[0]:  # the operator's thumb: let go at once
                first[0] = False
                return
            assert done.wait(10), "a leg never finished"
            done.clear()
        finally:
            world.awaiting_rover = None

    attach(level3.RoverLegs(Slow(), done.set))
    nav.wait_for_rover = wait
    config.use("50")
    w = World(recorder=lambda *a, **k: None)
    nav.goto(w, 40, 40)
    deadline = time.time() + 10
    while len(driven) < len(handed) and time.time() < deadline:
        time.sleep(0.05)
    assert len(handed) > 1, "need more than one leg to test this"
    assert driven == handed, ("legs lost or out of order", driven, handed)


def test_a_stopped_leg_is_handed_over_and_the_rover_told_where_it_ends():
    """A stop from the pad ends the leg: nothing is resent and no SPACE is sent. The screen
    says where the leg ends; once a person releases the game, the rover is told it stands
    there."""
    handed = []
    told = []
    released = []

    class Stopped:
        def drive(self, dirs, on_step=None):
            raise level3.RoverStopped({"result": "STOPPED", "pose": {"x": 0, "y": 0,
                                                                     "heading": "N"}})

        def set_pose(self, x, y, h):
            told.append((x, y, h))
            return {"ok": True, "pose": {"x": x, "y": y, "heading": h}}

    legs = level3.RoverLegs(Stopped(), lambda: released.append(1))

    def wait(world, dirs):  # the person: waits for the rover, then presses SPACE
        handed.append(list(dirs))
        deadline = time.time() + 5
        while legs.is_driving() and time.time() < deadline:
            time.sleep(0.01)
        assert not legs.is_driving(), "the stopped leg was never handed back"

    attach(legs)
    nav.wait_for_rover = wait
    config.use("50")
    w = World(recorder=lambda *a, **k: None)
    nav.goto(w, w.pos[0] + 3, w.pos[1])
    deadline = time.time() + 5
    while len(told) < len(handed) and time.time() < deadline:
        time.sleep(0.01)
    assert handed and not released, "SPACE was sent for a leg that never finished"
    assert told[0] == level3.leg_end({"x": 0, "y": 0, "heading": "N"}, handed[0]), told
    assert len(told) == len(handed), (told, handed)
    x, y, h = told[0]
    assert dashboard.ROVER_HINT == f"STOPPED: put it {level3.from_home(x, y)}, facing {h}, then SPACE"


def test_the_person_is_told_the_cell_from_home():
    assert level3.from_home(3, -2, 0.1) == "3 cells (30 cm) east and 2 cells (20 cm) north of home"
    assert level3.from_home(-1, 0) == "1 cell west of home"
    assert level3.from_home(0, 4, 0.1) == "4 cells (40 cm) south of home"
    assert level3.from_home(0, 0, 0.1) == "on home"


def test_a_hand_space_is_ignored_while_the_rover_drives():
    hand = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
    ours = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", rover=True)
    assert main.space_ends_pause(hand), "nothing driving: a hand SPACE ends the pause"
    nav.rover_driving = lambda: True
    assert not main.space_ends_pause(hand), "driving: a hand SPACE is ignored"
    assert main.space_ends_pause(ours), "driving: the rover's own SPACE ends the pause"
