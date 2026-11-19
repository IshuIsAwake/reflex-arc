"""Level 4 in the game's planner. When the LiDAR finds the real rover in another cell, or
something in its way, leg_finished returns (the cell it is on, the cells with something in
them). The game's rover is moved there, those cells become rock, and goto plans again.
No window, no model, no Pi: the hooks stand in for the rover."""

import config
import nav
import settings
from world import World, neighbours


def open_world():
    config.use("50")
    w = World(recorder=lambda *a, **k: None)
    w.here.reveal_all()  # no rock in the fog, so the only replans are the LiDAR's
    return w


def goal_for(w):
    """A free cell 6 to 12 steps away."""
    for cell in w.here.cells():
        if w.here.blocked(*cell):
            continue
        path = nav.plan(w.here, w.pos, cell)
        if path and 6 <= len(path) - 1 <= 12:
            return cell


def leg_start(end, dirs):
    x, y = end
    for d in dirs:
        step = nav.DIRS[nav.HEADING_NAMES.index(d)]
        x -= step[0]
        y -= step[1]
    return x, y


def record_legs(legs):
    nav.leg_started = lambda world, dirs: legs.append((world.pos, list(dirs)))


def miss_once(goal, moved):
    """The first leg ends one cell off where the game drove it."""
    def finished(world):
        if moved:
            return None
        for cell in neighbours(world.pos):
            if not world.here.blocked(*cell) and cell != goal:
                moved.append(cell)
                return cell, []

    nav.leg_finished = finished


def test_a_miss_moves_the_rover_and_the_game_plans_again_from_there():
    w = open_world()
    goal = goal_for(w)
    legs = []
    moved = []
    record_legs(legs)
    miss_once(goal, moved)

    result = nav.goto(w, *goal)

    assert result.code == "DONE", str(result)
    assert w.pos == goal
    assert len(legs) == 2, legs
    # the second leg starts on the cell the LiDAR measured
    assert leg_start(*legs[1]) == moved[0]
    # the move to the measured cell is not a step
    assert result.steps == len(legs[0][1]) + len(legs[1][1])
    assert result.beside is None


def test_with_no_replans_left_it_stops_where_the_rover_is_and_says_so():
    settings.NAV_REPLANS = 0
    w = open_world()
    goal = goal_for(w)
    legs = []
    moved = []
    record_legs(legs)
    miss_once(goal, moved)

    result = nav.goto(w, *goal)

    assert len(legs) == 1
    assert w.pos == moved[0]
    assert result.at == moved[0]
    # not "beside": the target isn't solid, the rover just isn't there yet
    assert result.beside is None
    assert result.steps == len(legs[0][1])


def test_something_in_the_way_becomes_rock_and_the_route_goes_round_it():
    w = open_world()
    goal = goal_for(w)
    route = nav.plan(w.here, w.pos, goal)
    stop = route[2]  # the real rover stopped two cells in...
    block = route[3]  # ...because the LiDAR saw something in the next cell
    legs = []
    told = []
    record_legs(legs)

    def finished(world):
        if told:
            return None
        told.append(True)
        return stop, [block]

    nav.leg_finished = finished
    result = nav.goto(w, *goal)

    assert w.here.at(*block) == "#"
    assert result.code == "DONE", str(result)
    assert w.pos == goal
    assert leg_start(*legs[1]) == stop
    # the second leg never goes through the new rock
    x, y = stop
    for d in legs[1][1]:
        step = nav.DIRS[nav.HEADING_NAMES.index(d)]
        x += step[0]
        y += step[1]
        assert (x, y) != block


def test_no_miss_is_the_game_as_before():
    w = open_world()
    goal = goal_for(w)
    legs = []
    nav.leg_started = lambda world, dirs: legs.append(list(dirs))
    nav.leg_finished = lambda world: None

    result = nav.goto(w, *goal)

    assert result.code == "DONE"
    assert w.pos == goal
    assert len(legs) == 1
    assert result.steps == len(legs[0])
