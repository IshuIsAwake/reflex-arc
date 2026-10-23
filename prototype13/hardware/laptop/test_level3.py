"""Checks Level 3's hook against the game's real planner. No window, no model, no Pi.

    python test_level3.py

The game's `goto` drives a goal far enough off to need several legs; a stand-in rover
records what it was sent. The load-bearing check is that the rover gets exactly the
legs the game wrote to its route file, in order, each one while the game is still
paused on it.
"""

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "game"))   # prototype13/game
sys.path.insert(0, GAME)
sys.path.insert(0, HERE)

import config as C10   # noqa: E402  the game's config, not the rover's
import level3          # noqa: E402
import nav             # noqa: E402
import settings as S   # noqa: E402
from world import World  # noqa: E402

S.STORM_ON = False


class StandIn:
    def __init__(self):
        self.legs = []

    def drive(self, dirs, on_step=None):
        on_disk = open(nav.plan_file(), encoding="utf-8").read().split()
        assert on_disk == dirs, ("rover sent something other than the file", on_disk, dirs)
        self.legs.append(dirs)
        return {"x": 0, "y": 0, "heading": "N"}


def test_every_leg_reaches_the_rover_while_the_game_waits():
    keep = (nav.publish, nav._await_rover, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    rover, done = StandIn(), threading.Event()
    handed = []

    def wait(world, dirs):              # stands in for the game's SPACE pause
        handed.append(list(dirs))
        assert done.wait(5), "the rover never finished the leg"
        done.clear()

    try:
        level3.install(nav, rover, done.set)
        nav._await_rover = wait
        C10.use("50")
        w = World(recorder=lambda *a, **k: None)
        nav.goto(w, 40, 40)
        assert handed, "the game handed the rover nothing"
        assert rover.legs == handed, (rover.legs, handed)
        assert open(nav.plan_file()).read() == "", "file not wiped after the last leg"
    finally:
        nav.publish, nav._await_rover, S.PLAN_FILE = keep
        C10.use(C10.DEFAULT_ARENA)
        p = os.path.join(HERE, "runs", "test_plan.txt")
        os.path.exists(p) and os.remove(p)
    print(f"  {len(handed)} legs, {sum(map(len, handed))} moves handed over")


def test_a_hand_released_pause_still_drives_every_leg_in_order():
    """The 22 Oct run: SPACE pressed by hand let the game run ahead, and the rover refused the
    next legs as BUSY. Now they queue, and no SPACE is sent into a pause it does not own."""
    import time
    keep = (nav.publish, nav._await_rover, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    busy, driven, released = threading.Lock(), [], []

    class Slow:
        def drive(self, dirs, on_step=None):
            assert busy.acquire(blocking=False), "two legs reached the rover at once"
            try:
                time.sleep(0.15)
                driven.append(dirs)
            finally:
                busy.release()
            return {"x": 0, "y": 0, "heading": "N"}

    done = threading.Event()
    first = [True]

    def wait(world, dirs):
        world.awaiting_rover = list(dirs)
        try:
            if first[0]:           # the operator's thumb: let go at once
                first[0] = False
                return
            assert done.wait(10), "a leg never finished"
            done.clear()
        finally:
            world.awaiting_rover = None

    def finished():
        released.append(1)
        done.set()

    try:
        level3.install(nav, Slow(), finished,
                       still_waiting=lambda world, dirs: world.awaiting_rover == dirs)
        nav._await_rover = wait
        C10.use("50")
        w = World(recorder=lambda *a, **k: None)
        w.awaiting_rover = None
        handed = []
        real_publish = nav.publish

        def spy(world, dirs):
            if dirs:
                handed.append(list(dirs))
            real_publish(world, dirs)
        nav.publish = spy
        nav.goto(w, 40, 40)
        deadline = time.time() + 10
        while len(driven) < len(handed) and time.time() < deadline:
            time.sleep(0.05)
        assert len(handed) > 1, "need more than one leg to test this"
        assert driven == handed, ("legs lost or out of order", driven, handed)
    finally:
        nav.publish, nav._await_rover, S.PLAN_FILE = keep
        C10.use(C10.DEFAULT_ARENA)
        p = os.path.join(HERE, "runs", "test_plan.txt")
        os.path.exists(p) and os.remove(p)
    print(f"  {len(handed)} legs, first released by hand, all driven in order")


def test_a_stopped_leg_is_handed_over_and_the_rover_told_where_it_ends():
    """A stop from the pad ends the leg: nothing is resent and no SPACE is sent. The
    screen says where the leg ends; once a person releases the game, the rover is told
    it stands there."""
    import time
    keep = (nav.publish, nav._await_rover, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    guard, handed, told, released, hints = level3.Guard(), [], [], [], []

    class Stopped:
        def drive(self, dirs, on_step=None):
            raise level3.RoverStopped({"result": "STOPPED", "pose": {"x": 0, "y": 0,
                                                                     "heading": "N"}})

        def set_pose(self, x, y, h):
            told.append((x, y, h))
            return {"ok": True, "pose": {"x": x, "y": y, "heading": h}}

    def wait(world, dirs):              # the person: waits for the rover, then presses SPACE
        handed.append(list(dirs))
        deadline = time.time() + 5
        while guard.driving and time.time() < deadline:
            time.sleep(0.01)
        assert not guard.driving, "the stopped leg was never handed back"

    try:
        level3.install(nav, Stopped(), lambda: released.append(1), guard=guard,
                       tell=hints.append)
        nav._await_rover = wait
        C10.use("50")
        w = World(recorder=lambda *a, **k: None)
        nav.goto(w, w.pos[0] + 3, w.pos[1])
        deadline = time.time() + 5
        while len(told) < len(handed) and time.time() < deadline:
            time.sleep(0.01)
    finally:
        nav.publish, nav._await_rover, S.PLAN_FILE = keep
        C10.use(C10.DEFAULT_ARENA)
        p = os.path.join(HERE, "runs", "test_plan.txt")
        os.path.exists(p) and os.remove(p)
    assert handed and not released, "SPACE was sent for a leg that never finished"
    assert told[0] == level3.leg_end({"x": 0, "y": 0, "heading": "N"}, handed[0]), told
    assert len(told) == len(handed), (told, handed)
    x, y, h = told[0]
    assert hints[:2] == [level3.DRIVING, f"STOPPED: put it {level3.from_home(x, y)}, "
                                         f"facing {h}, then SPACE"], hints
    print(f"  {len(handed)} stopped leg(s), the rover told {told[0]}")


def test_the_person_is_told_the_cell_from_home():
    assert level3.from_home(3, -2, 0.1) == "3 cells (30 cm) east and 2 cells (20 cm) north of home"
    assert level3.from_home(-1, 0) == "1 cell west of home"
    assert level3.from_home(0, 4, 0.1) == "4 cells (40 cm) south of home"
    assert level3.from_home(0, 0, 0.1) == "on home"


def test_a_hand_space_is_dropped_while_the_rover_drives():
    import pygame
    level3.KEYDOWN, level3.K_SPACE = pygame.KEYDOWN, pygame.K_SPACE
    hand = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
    ours = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", rover=True)
    other = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a")
    g = level3.Guard()
    assert g.filter([hand, other]) == [hand, other], "nothing driving: every key passes"
    g.driving = 1
    assert g.filter([hand, ours, other]) == [ours, other], "driving: only our SPACE passes"


if __name__ == "__main__":
    test_a_hand_space_is_dropped_while_the_rover_drives()
    test_every_leg_reaches_the_rover_while_the_game_waits()
    test_a_hand_released_pause_still_drives_every_leg_in_order()
    test_a_stopped_leg_is_handed_over_and_the_rover_told_where_it_ends()
    test_the_person_is_told_the_cell_from_home()
    print("all level3 checks passed")
