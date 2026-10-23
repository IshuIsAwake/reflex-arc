"""What gemma is told, and what it must not be told.


Two of these are load-bearing. `test_the_grid_has_one_door_onto_the_world` reads the
source, because `Area.at` returns ground truth at every fog setting and one missing
`visible()` check hands over the whole arena with nothing ever looking wrong.
`test_decoration_never_reaches_the_view` is its twin for the other direction: the
pebbles `render.py` scatters are texture, and they stop being harmless the instant
anything reads them.
"""

import pathlib
import re

import nav
import settings as S
import sight
import world
from world import World


def rows(w):
    """The grid without its ruler row or its row labels."""
    return [r[5:] for r in sight.grid(w).splitlines()[1:]]


def surveyed():
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    return w


def test_the_view_is_fogged():
    w = World()
    g = rows(w)
    assert len(g) == 30, "thirty rows"
    assert all(len(r) == 30 for r in g), "thirty columns"
    assert g[2][2] == sight.FOG, "the far corner is unseen"
    assert g[15][15] == sight.YOU, "the rover is drawn"
    assert g[16][15] == "H", "the pad is not"
    assert sum(r.count(sight.FOG) for r in g) > 700, "most of it is still fog"

    g2 = rows(surveyed())
    assert not any(sight.FOG in r for r in g2), "surveyed, nothing is fog"
    rock = sum(r.count("#") for r in g2)
    assert rock == sum(r.count("#") for r in __import__("config").ARENA), "...and the rock is all there"


def test_the_list_agrees_with_the_grid():
    w = surveyed()
    named = sight.things(w)
    assert len(named) == 1, "one entry, not six"
    entry = named[0]
    assert entry.startswith("base pad, 6 cells"), "it is the pad"
    for cell in re.findall(r"\((\d+),(\d+)\)", entry):
        x, y = int(cell[0]), int(cell[1])
        assert nav.known(w.here, x, y) == "H", f"({x},{y}) really is the pad"


def test_the_four_cells_you_could_step_into():
    w = World()
    lines = sight.neighbours(w)
    assert len(lines) == 4, "four of them"
    south = next(li for li in lines if li.strip().startswith("south"))
    assert "base pad" in south and "solid" in south, "the pad is named and called solid"

    # The sightline offers the last drivable cell, never the thing that stops you.
    # Gemma read the wall coordinate off the old wording and called goto on it twice.
    north = next(li for li in lines if li.strip().startswith("north"))
    assert "you can drive" in north, "north says how far it can go"
    far = re.search(r"to \((\d+),(\d+)\)", north)
    assert bool(far) and nav.known(w.here, int(far[1]), int(far[2])) == ".", "and that cell is drivable"

    w2 = surveyed()
    w2.pos = (32, 29)
    east = next(li for li in sight.neighbours(w2) if li.strip().startswith("east"))
    assert "ROCK" in east and "cannot go" in east, "rock is named as rock and refused"


def test_the_legend_hides_what_has_not_been_found():
    w = World()
    leg = sight.legend(w)
    assert "? never seen" in leg, "fog is listed while there is fog"
    assert "H base pad" in leg, "the pad is listed, having been landed on"

    g = surveyed()
    assert "never seen" not in sight.legend(g), "surveyed, fog drops out"


def test_the_grid_has_one_door_onto_the_world():
    src = pathlib.Path(sight.__file__).read_text()
    # Prose cannot read a grid. Strip docstrings and comments, then the check is about
    # code only -- otherwise the file cannot even name what it must not touch.
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    assert ".at(" not in src, "no read of Area.at"
    assert ".seen" not in src, "no read of Area.seen"
    assert "nav.known(" in src, "nav.known is used"


def test_decoration_never_reaches_the_view():
    src = pathlib.Path(sight.__file__).read_text()
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    assert "import render" not in src, "sight.py does not import render"
    assert "_grit" not in src, "no read of the grit scatter"
    assert "_rock_shade" not in src, "no read of the rock shading"

    # And the other direction: the decoration must be a pure function of the cell, or
    # it is state, and state that only the human can see is a second world.
    import render
    assert render._grit(7, 11) == render._grit(7, 11), "grit is deterministic"
    assert len({tuple(render._grit(x, 3)) for x in range(40)}) > 3, "...and differs by cell"


def test_the_status_line_survived_the_move():
    w = World()
    line = sight.status_line(w)
    assert (all(bit in line for bit in ("dawn of sol 1", "has not begun", "battery",
                                           "at (15,15)", "base pad at"))), "at dawn it says the day has not begun"
    assert "\n" not in line, "one line"
    assert line in sight.view(w), "and the view carries it"
    assert f"{S.DAY_SECONDS} seconds" in line, "it says seconds, because a day is made of time"
    w.phase = "day"
    w.run_clock(100)
    assert f"{S.DAY_SECONDS - 100} seconds of the day left" in sight.status_line(w), "by day it counts down"
    w.phase = "dusk"
    assert ("sol 1, dusk  |  the day is over" in
                sight.status_line(w)), "at dusk the day is over"


def test_the_view_says_how_far_home_is():
    w = World()
    assert "You are beside the pad" in sight.view(w), "at the landing site it says the rover is home"
    assert "goes unused" in sight.view(w), "and that charge left tonight goes unused"
    w.pos = (15, 10)
    v = sight.view(w)
    assert "The pad is at least 5 steps away" in v, "five rows north, it says the pad is at least five steps off"
    assert "stranded" in v, "and what being caught out there costs"
    w.next_day()
    assert "was not recharged" in sight.view(w), "after a night out there it says there was no recharge"


def test_finished_work_stays_in_view():
    """Two reports said no objective had ever been found, after all three were done:
    a finished objective left the map, and with it every trace that it had been done."""
    w = World()
    w.here.reveal(15, 11, r=3)
    o, _ = w.place_objective((15, 11), "high", 20)
    w.pos = (15, 12)
    w.execute(o)
    i = w.interests[1]
    w.pos = (i.cell[0], i.cell[1] - 1)
    w._arrive()
    w.execute(i)
    w.next_day()
    v = sight.view(w)
    assert ("WORK FINISHED ON THIS MISSION" in v
               and "high priority objective at (15,11), 20 steps of work -- finished on "
                   "sol 1" in v), "the next sol's view lists the objective, with the sol it was done on"
    assert (f"interest at ({i.cell[0]},{i.cell[1]}) -- examined on sol 1" in v
                and i.text not in v), "...and the interest, without what it was"


def test_the_view_stays_affordable():
    day_one = len(sight.view(World()))
    worst = len(sight.view(surveyed()))
    # Replaced rather than appended, so this is a flat tail cost per request and not a
    # growing one.
    assert worst < 7000, "a fully surveyed arena fits a sane budget"

    # The intuition is wrong: a sol-one view is not smaller than a surveyed one, since
    # the grid is one character per cell whatever it holds. In *characters* the view is
    # flat from the first request. Tokens are another story this test cannot see -- a run
    # of fifty '?' merges into far fewer tokens than a mixed row.
    assert abs(worst - day_one) < worst * 0.05, "the character cost is flat, not growing"
