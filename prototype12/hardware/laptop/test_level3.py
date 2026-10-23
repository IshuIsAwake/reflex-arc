"""Checks Level 3's hook against 10d's real planner. No window, no model, no Pi.

    python test_level3.py

10d's `goto` drives a goal far enough off to need several legs; a stand-in rover
records what it was sent. The load-bearing check is that the rover gets exactly the
legs 10d wrote to its route file, in order, each one while 10d is still paused on it.
"""

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(HERE, "..", "..", "game"))   # prototype16/game, the copy
sys.path.insert(0, GAME)
sys.path.insert(0, HERE)

import config as C10   # noqa: E402  10d's config, not the rover's
import level3          # noqa: E402
import nav             # noqa: E402
import settings as S   # noqa: E402
from world import World  # noqa: E402

S.STORM_ON = False


class StandIn:
    def __init__(self):
        self.legs = []

    def drive(self, dirs, on_step=None, check=False):
        on_disk = open(nav.plan_file(), encoding="utf-8").read().split()
        assert on_disk == dirs, ("rover sent something other than the file", on_disk, dirs)
        self.legs.append(dirs)
        return {"x": 0, "y": 0, "heading": "N"}


def test_every_leg_reaches_the_rover_while_10d_waits():
    keep = (nav.publish, nav._await_rover, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    rover, done = StandIn(), threading.Event()
    handed = []

    def wait(world, dirs):              # stands in for 10d's SPACE pause
        handed.append(list(dirs))
        assert done.wait(5), "the rover never finished the leg"
        done.clear()

    try:
        level3.install(nav, rover, done.set)
        nav._await_rover = wait
        C10.use("50")
        w = World(recorder=lambda *a, **k: None)
        nav.goto(w, 40, 40)
        assert handed, "10d handed the rover nothing"
        assert rover.legs == handed, (rover.legs, handed)
        assert open(nav.plan_file()).read() == "", "file not wiped after the last leg"
    finally:
        nav.publish, nav._await_rover, S.PLAN_FILE = keep
        C10.use(C10.DEFAULT_ARENA)
        p = os.path.join(HERE, "runs", "test_plan.txt")
        os.path.exists(p) and os.remove(p)
    print(f"  {len(handed)} legs, {sum(map(len, handed))} moves handed over")


def test_a_hand_released_pause_still_drives_every_leg_in_order():
    """The 22 Oct run: SPACE pressed by hand let 10d run ahead, and the rover refused the
    next legs as BUSY. Now they queue, and no SPACE is sent into a pause it does not own."""
    import time
    keep = (nav.publish, nav._await_rover, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    busy, driven, released = threading.Lock(), [], []

    class Slow:
        def drive(self, dirs, on_step=None, check=False):
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


class Measuring:
    """A stand-in rover that keeps its own cell, like the real one, and whose LiDAR says
    each leg ended one cell short of where it was sent -- a slip the simulation cannot
    see. `misreport` replaces the measured cell outright."""

    STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}

    def __init__(self, misreport=None):
        self.cell, self.told, self.misreport = (0, 0), [], misreport

    def drive(self, dirs, on_step=None, check=False):
        for d in dirs[:-1]:                          # the last step is lost to slip
            self.cell = (self.cell[0] + self.STEP[d][0], self.cell[1] + self.STEP[d][1])
        x, y = self.misreport or self.cell
        return {"x": x, "y": y, "heading": dirs[-1]}

    def set_pose(self, x, y, h):
        self.told.append((x, y, h))
        self.cell = (x, y)
        return {"ok": True, "pose": {"x": x, "y": y, "heading": h}}


def _run_level4(rover, goal_dx):
    """Drive one goto through level3 with correction on; returns (world, result, events)."""
    keep = (nav.publish, nav._await_rover, nav.goto, S.PLAN_FILE)
    S.PLAN_FILE = os.path.join(HERE, "runs", "test_plan.txt")
    done, events = threading.Event(), []

    def wait(world, dirs):
        world.awaiting_rover = list(dirs)
        try:
            assert done.wait(5), "the rover never finished the leg"
            done.clear()
        finally:
            world.awaiting_rover = None

    try:
        C10.use("50")
        w = World(recorder=lambda kind, **f: events.append((kind, f)))
        w.awaiting_rover = None
        level3.install(nav, rover, done.set, check=True, correct=True,
                       still_waiting=lambda world, dirs: world.awaiting_rover == dirs)
        nav._await_rover = wait
        start = w.pos
        r = nav.goto(w, start[0] + goal_dx, start[1])
        return w, start, r, events
    finally:
        nav.publish, nav._await_rover, nav.goto, S.PLAN_FILE = keep
        C10.use(C10.DEFAULT_ARENA)
        p = os.path.join(HERE, "runs", "test_plan.txt")
        os.path.exists(p) and os.remove(p)


def test_level4_moves_the_simulation_to_where_the_lidar_says():
    w, start, r, events = _run_level4(Measuring(), goal_dx=3)
    # one leg of three cells east; the rover measured itself one short
    assert w.pos == (start[0] + 2, start[1]), f"simulation's rover at {w.pos}"
    assert r.at == w.pos, f"the model is told {r.at}, the map says {w.pos}"
    assert "LiDAR measured it" in r.advice and "plan from there" in r.advice, r.advice
    fixes = [f for k, f in events if k == "lidar_fix"]
    assert fixes and tuple(fixes[-1]["measured"]) == w.pos, events[-3:]
    assert w.pos in w.here.visited, "moved there without arriving: fog and visits skipped"


def test_level4_does_not_move_the_simulation_into_nothing():
    w, start, r, _ = _run_level4(Measuring(misreport=(-200, 0)), goal_dx=3)
    assert w.pos == (start[0] + 3, start[1]), "moved off the map"
    assert "LiDAR" not in (r.advice or ""), "told the model about a move that did not happen"


def test_after_an_unsure_stop_the_rover_is_told_where_the_person_put_it():
    import correct
    told = []
    fix = correct.Corrector(type("Nav", (), {"goto": lambda *a: None, "Result": object})(),
                            send_pose=lambda x, y, h: told.append((x, y, h)))
    world = type("W", (), {"pos": (15, 15)})()
    fix.leg_handed(world, ["E", "E"])            # sim drove (13,15) -> (15,15)
    fix.leg_unsure({"x": 1, "y": 0, "heading": "E"})
    fix.after_pause(world)                        # the person put it on (15,15)'s spot
    assert told == [(2, 0, "E")], told


def test_a_refused_correction_is_not_mistaken_for_a_jump():
    """23 Oct: a measured cell off the simulation's map was refused, and the next leg
    took the disagreement for the simulation teleporting -- and told the rover a cell its
    LiDAR had just measured it was not in."""
    import correct
    told = []
    fix = correct.Corrector(type("Nav", (), {"goto": lambda *a: None, "Result": object})(),
                            send_pose=lambda x, y, h: told.append((x, y, h)))
    W = type("W", (), {})
    world = W()
    world.pos, world.here = (29, 15), type("A", (), {"w": 30, "h": 30})()
    fix.leg_handed(world, ["E", "E"])            # (27,15) -> (29,15): offset (27,15)
    fix.leg_driven({"x": 3, "y": 0, "heading": "E"})   # measured one further: (30,15)
    fix.after_pause(world)                        # off the map: refused, sim stays (29,15)
    assert world.pos == (29, 15)
    world.pos = (29, 17)                          # the simulation drives on from there
    fix.leg_handed(world, ["S", "S"])
    assert told == [], f"the rover was told a cell its LiDAR contradicts: {told}"
    world.pos = (10, 10)                          # a real jump, with no leg
    fix.after_pause(world)
    world.pos = (12, 5)
    fix.leg_handed(world, ["E", "E"])             # starts at (10,5), not where it was left
    assert told and told[-1][:2] == (10 - 27, 5 - 15), told


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
    test_every_leg_reaches_the_rover_while_10d_waits()
    test_a_hand_released_pause_still_drives_every_leg_in_order()
    test_level4_moves_the_simulation_to_where_the_lidar_says()
    test_level4_does_not_move_the_simulation_into_nothing()
    test_after_an_unsure_stop_the_rover_is_told_where_the_person_put_it()
    test_a_refused_correction_is_not_mistaken_for_a_jump()
    print("all level3 checks passed")
