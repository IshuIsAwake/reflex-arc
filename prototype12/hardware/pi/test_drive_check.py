"""Checks the LiDAR-checked drive loop on a pretend rover with known errors. No hardware.

    python test_drive_check.py

server.Rover drives fake_world's rover exactly as it drives the real one; only the
motors and the LiDAR are pretend. Each test gives the rover a fault the open-loop
timings cannot see -- short turns, wheel slip, wheels spinning in place -- and checks
the LiDAR check catches it and does what ARCHITECTURE.md asks: heading corrected,
position reported, stop when lost.
"""

import math

import config as C
import reference
from fake_world import FakeWorld
from server import Rover

# Fast, but a quarter turn stays long next to the OS's sleep granularity (~15 ms on
# Windows): compressed to 0.06 s, a small fix was a 7 ms pulse that ran twice as long.
C.FORWARD_S_PER_CELL, C.TURN_S_PER_90, C.SETTLE_S = 0.06, 0.6, 0.0
C.CELL_M, C.FIX_MIN_S = 0.2, 0.0
C.LIDAR_MOUNT_CHECKED = True


def rover_in(world):
    r = Rover(world.motors(), world.lidar())
    r.ref, _ = reference.record_home(r.lidar, turns=3)
    return r


def drive(r, cmds, check=True, did=[0]):
    did[0] += 1
    sent = []
    r.drive({"id": did[0], "cmds": cmds, "check": check}, sent.append)
    return sent[-1], [m["check"] for m in sent if "check" in m]


def heading_off_deg(world, h):
    return abs((math.degrees(world.pose[2]) + 90 * h + 180) % 360 - 180)


def test_a_short_turn_is_caught_and_fixed():
    world = FakeWorld(turn_gain=0.8)                 # every turn 18 deg short
    r = rover_in(world)
    done, checks = drive(r, ["E", "E", "N"])
    assert done["result"] == "DONE", done
    assert any(c["fixes"] >= 1 for c in checks), "a short turn went unfixed"
    assert heading_off_deg(world, 0) < 6, f"really facing {math.degrees(world.pose[2]):.1f} deg"
    # where it really is: two cells east (map -y) and one north (map +x)
    x, y, _ = world.pose
    assert math.hypot(x - 0.2, y + 0.4) < 0.1, world.pose


def test_an_overshooting_turn_is_caught_and_fixed():
    world = FakeWorld(turn_gain=1.25)                # every turn, fixes included, 25 % too far
    r = rover_in(world)
    done, checks = drive(r, ["E", "S"])
    assert done["result"] == "DONE", done
    assert heading_off_deg(world, 2) < 6, f"really facing {math.degrees(world.pose[2]):.1f} deg"


def test_a_fix_too_small_to_make_is_reported_not_forced():
    world = FakeWorld(turn_gain=0.9)                 # 9 deg short: over tolerance, a tiny pulse
    r = rover_in(world)
    keep = C.FIX_MIN_S
    C.FIX_MIN_S = 1.0                                # pretend the chassis cannot do short pulses
    try:
        done, checks = drive(r, ["E"])
    finally:
        C.FIX_MIN_S = keep
    c = checks[0]
    assert c["fixes"] == 0 and "smallest turn" in c["heading_note"], c
    assert heading_off_deg(world, 1) < 12, "it turned anyway, and overshot"


def test_the_same_turns_unchecked_drift():
    world = FakeWorld(turn_gain=0.8)
    r = rover_in(world)
    drive(r, ["E", "E", "S"], check=False)            # two right turns: the errors add up
    # nothing corrected: ~36 deg off by the end. This is Level 3 on a real floor.
    assert heading_off_deg(world, 2) > 25


def test_slip_is_reported_not_driven_back():
    world = FakeWorld(fwd_gain=0.55)                 # wheels slip: 0.55 of each cell
    r = rover_in(world)
    done, checks = drive(r, ["N", "N", "E", "E"])    # two 2-cell runs, each ~1 cell short
    off = [c for c in checks if c["result"] == "OFF"]
    assert off, f"slip not reported: {checks}"
    assert off[0]["manhattan"] == 1 and off[0]["chebyshev"] == 1
    # reported, then carried on from the measured cell -- never driven back
    assert done["result"] == "DONE", done
    assert done["pose"] != {"x": 2, "y": -2, "heading": "E"}, "the plan's cell, not the real one"


def test_a_run_two_cells_short_is_lost_and_knows_where_it_is():
    world = FakeWorld(fwd_gain=0.55)
    r = rover_in(world)
    done, checks = drive(r, ["N", "N", "N", "N"])    # one 4-cell run ends ~2 cells short
    assert done["result"] == "LOST" and len(checks) == 1, (done, checks)
    # LOST, not UNSURE: it found itself, so the measured cell is real
    assert abs(done["pose"]["y"] - round(-world.pose[0] / C.CELL_M)) == 0, (done, world.pose)


def test_a_big_slip_beyond_the_first_look_is_still_found():
    world = FakeWorld(fwd_gain=0.55)                 # 5 cells = 1 m asked, 0.55 m driven
    r = rover_in(world)
    done, checks = drive(r, ["N"] * 5)
    assert done["result"] == "LOST", (done, checks)   # 0.45 m short: past the 0.3 m first look
    assert abs(checks[0]["x"] - world.pose[0]) < 0.05, (checks[0], world.pose)


def test_wheels_spinning_in_place_stops_the_drive():
    world = FakeWorld(fwd_gain=0.0)                  # stuck: nothing moves
    r = rover_in(world)
    done, checks = drive(r, ["N"] * 6)
    assert done["result"] in ("LOST", "UNSURE"), done
    assert len(checks) <= 2, "kept driving after it knew it was stuck"


def test_no_check_without_the_mount_checked():
    world = FakeWorld()
    r = rover_in(world)
    C.LIDAR_MOUNT_CHECKED = False
    try:
        done, _ = drive(r, ["N"])
        assert done["result"] == "REFUSED" and "lidar_check.py --mount" in done["note"], done
    finally:
        C.LIDAR_MOUNT_CHECKED = True


def test_a_pretend_room_is_never_saved_as_the_real_one():
    """23 Oct: a fake-world 'record home' wrote reference.npz on the laptop, and copying
    the code to the Pi carried the pretend room onto the real rover."""
    import os
    import server
    world = FakeWorld()
    r = Rover(world.motors(), world.lidar())
    r.ref, r.ref_file = None, None                   # as server.py --fake-world sets it
    before = os.path.getmtime(reference.FILE) if os.path.exists(reference.FILE) else None
    assert server.lidar_op(r, "ref_home")["ok"]
    after = os.path.getmtime(reference.FILE) if os.path.exists(reference.FILE) else None
    assert before == after, "the pretend room was written to reference.npz"


def test_a_good_rover_passes_every_check():
    world = FakeWorld()
    r = rover_in(world)
    done, checks = drive(r, ["E", "E", "S", "W"])
    assert done["result"] == "DONE"
    assert checks and all(c["result"] == "DONE" for c in checks), checks


if __name__ == "__main__":
    import time
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            t = time.perf_counter()
            fn()
            print(f"  {name}  {time.perf_counter() - t:.1f} s")
    print("all drive-check checks passed")
