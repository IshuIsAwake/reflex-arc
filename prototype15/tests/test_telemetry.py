"""Display telemetry must follow playback, not the already-completed world."""
from types import SimpleNamespace

from anim import Reel

ROUTE = [("start", (2, 2)), ("plan", [(2, 2), (3, 2), (3, 3)]),
         ("step", ((3, 2), [])), ("step", ((3, 3), []))]


def make_reel():
    world = SimpleNamespace(pos=(3, 3), reel=[list(ROUTE)])
    return world, Reel(world)


def test_route_dots_remain_as_rover_passes():
    world, reel = make_reel()
    reel._load(ROUTE)
    reel._apply("at", (2, 2))
    reel._apply("plan", [(2, 2), (3, 2), (3, 3)])
    assert reel.plan == [(2, 2), (3, 2), (3, 3)]
    reel._apply("step", ((3, 2), []))
    assert reel.plan == [(2, 2), (3, 2), (3, 3)]
    reel._apply("step", ((3, 3), []))
    assert reel.plan == [(2, 2), (3, 2), (3, 3)]
    reel._apply("probe", [(3, 3), (4, 3)])
    assert reel.probe == [(3, 3), (4, 3)]


def test_arrival_follows_playback_and_survives_cleanup():
    world, reel = make_reel()
    reel.tick(0.001)
    assert reel.where(world.pos) == (2, 2)
    assert reel.destination == (3, 3)
    assert reel.destination_status == "APPROACHING"
    reel.tick(30)
    reel.tick(1)
    assert reel.destination_status == "REACHED"


def test_a_refused_cell_reads_as_blocked():
    world, reel = make_reel()
    reel._load(ROUTE)
    reel._apply("at", (3, 2))
    reel._apply("block", (3, 1))
    assert reel.destination_status == "BLOCKED / REPLANNING"


def test_skip_keeps_the_last_queued_destination():
    world, reel = make_reel()
    reel.tick(0.001)
    world.reel.append([("start", (3, 3)), ("plan", [(3, 3), (2, 3)]),
                       ("step", ((2, 3), []))])
    world.pos = (2, 3)
    reel.skip()
    assert reel.destination == (2, 3)
    assert reel.destination_status == "REACHED"


def test_price_probe_does_not_claim_a_drive_destination():
    world, reel = make_reel()
    reel._load([("start", (3, 3)), ("probe", [(3, 3), (4, 3)])])
    assert reel.destination is None
