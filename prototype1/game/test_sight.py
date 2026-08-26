"""What gemma is allowed to see.

    .venv/bin/python game/test_sight.py

Most of this is ordinary: fog reads `?`, the grid and the list agree, a legend only
lists what is on the map. Two are load-bearing and are the reason the file exists:

  * **the pit test.** If a snake pit ever appears in a view, the avoid-list mechanic
    is dead and the first symptom is wondering why nothing ever goes wrong.
  * **the read count.** `Area.at` returns ground truth at every fog setting.
    `nav.known()` is the one gated door, and this file is the second thing through
    it. One dropped `visible()` check hands gemma the whole map with nothing looking
    wrong anywhere, so the door is counted rather than trusted.
"""

import pathlib
import re
import sys

import settings as S
import sight
from world import World


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def rows(w):
    """The grid's cell rows, without the ruler and without the row labels."""
    return [line[5:] for line in sight.grid(w).splitlines()[1:]]


def test_the_view_is_fogged():
    print("fog")
    w = World()
    a = w.here
    body = rows(w)
    unseen = [(x, y) for y in range(a.h) for x in range(a.w) if (x, y) not in a.seen]
    ok = check("day one is nearly all unknown", len(unseen) > a.w * a.h * 0.8,
               f"{len(unseen)} of {a.w * a.h}")
    ok &= check("and every unseen cell reads ?",
                all(body[y][x] == sight.FOG for x, y in unseen))
    ok &= check("where you stand is @", body[w.pos[1]][w.pos[0]] == sight.YOU)
    # The extent is disclosed deliberately: nav.known() returns "#" off the edge, so
    # the planner already knows how big the area is. Hiding it from gemma would leave
    # it unable to reason about its own UNREACHABLE.
    ok &= check("the grid is the whole area", len(body) == a.h and len(body[0]) == a.w)
    ok &= check("extent is stated in words", f"{a.w} cells wide and {a.h} tall" in sight.view(w))
    return ok


def test_a_pit_is_never_shown():
    print("snake pits")
    w = World()
    a = w.areas["savana2"]
    w.area, w.pos = "savana2", (1, 1)
    a.has_map = True                       # the most revealing setting there is
    ok = check("the area has pits to hide", len(a.traps) > 0, f"{len(a.traps)} of them")
    body = rows(w)
    # Not "no ^ in the output" -- that would pass if pits were drawn as something
    # else. Every trap cell must read as ordinary floor.
    ok &= check("every one of them reads as plain floor",
                all(body[y][x] == "." for x, y in a.traps if (x, y) != w.pos))
    ok &= check("and none is named in the list",
                not any(str(cell) in " ".join(sight.things(w)) for cell in a.traps))
    return ok


def test_names_are_earned():
    print("discover")
    w = World()
    w.here.has_map = True
    named = " ".join(sight.things(w))
    ok = check("an unvisited terminal reads discover", "discover at" in named, named[:70])
    ok &= check("and is not called cartpole", "cartpole" not in named)
    w.discovered["cartpole"] = "plaza"
    ok &= check("...until you have walked up to it", "cartpole at" in " ".join(sight.things(w)))
    return ok


def test_the_list_agrees_with_the_grid():
    print("things")
    w = World()
    w.here.has_map = True
    body = rows(w)
    ok = True
    for entry in sight.things(w):
        x, y = (int(n) for n in re.findall(r"-?\d+", entry.split(" at ")[-1]))
        ok &= check(f"{entry} is not floor on the grid", body[y][x] not in "#." + sight.FOG)
    # A coordinate that disagrees with the grid becomes a wrong goto and then a wrong
    # note, and the parser gets the blame. Cheap to pin, so pin it.
    ok &= check("the shop is where the world puts it", "shop at (10,16)" in sight.things(w))
    return ok


def test_the_four_cells_you_could_step_into():
    print("immediately around you")
    w = World()
    w.area, w.pos = "plaza", (10, 15)      # the shop alcove: walls east and west
    w.here.reveal(*w.pos)
    lines = " ".join(sight.neighbours(w))
    # Watched 2026-08-26: gemma read this exact spot off the grid as "clearly visible
    # floor tiles" east and west, called goto on both, got UNREACHABLE twice, and
    # decided it was stuck. Both are walls. The planner was right; the counting was not.
    ok = check("east is called a wall", "east (11,15): WALL" in lines, lines)
    ok &= check("west is called a wall", "west (9,15): WALL" in lines)
    ok &= check("and south names the shop", "south (10,16): shop" in lines)
    # Open floor gets the whole sightline instead of just the one cell: "which way
    # is worth going" is the other question gemma was counting off the grid to answer.
    ok &= check("north reports how far it is open", "north: open for" in lines)
    ok &= check("it says you stop beside a solid thing",
                "you stop beside it" in lines)
    ok &= check("and the view carries it", "IMMEDIATELY AROUND YOU" in sight.view(w))

    w.area, w.pos = "savana2", (16, 11)    # somewhere with nothing revealed
    ok &= check("unseen neighbours say so",
                "never seen" in " ".join(sight.neighbours(w)))
    return ok


def test_the_legend_hides_what_has_not_been_found():
    print("legend")
    w = World()
    day_one = sight.legend(w)
    ok = check("fog is explained while there is fog", "never seen" in day_one)
    ok &= check("the tribe is not listed on day one", "tribe" not in day_one, day_one)
    w.here.has_map = True
    ok &= check("nor once the plaza map is bought", "tribe" not in sight.legend(w))
    w.area = "savana"
    w.areas["savana"].has_map = True
    ok &= check("...but it is once you are in its area with a map",
                "tribe" in sight.legend(w))
    return ok


def test_the_grid_has_one_door_onto_the_world():
    print("the gated door")
    src = (pathlib.Path(__file__).parent / "sight.py").read_text()
    # Prose cannot read a grid. Strip docstrings and comments, then the check is
    # about code only -- otherwise the file cannot even name what it must not touch.
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    # nav.known() is the only legal read. `Area.at` returns ground truth whether or
    # not the cell is fogged, so a single call to it here would make the view
    # omniscient, everything would keep working, and nothing would ever look wrong.
    ok = check("no read of Area.at", ".at(" not in src)
    ok &= check("no read of Area.traps", ".traps" not in src)
    ok &= check("no read of Area.seen", ".seen" not in src)
    ok &= check("nav.known is used", "nav.known(" in src)
    return ok


def test_the_status_line_survived_the_move():
    print("the morning line")
    w = World()
    line = sight.status_line(w)
    ok = check("has the five facts", all(bit in line for bit in
               ("day 1", "coins", "in plaza", "antidotes", "pouch holds")), line)
    # FINDINGS: `antidotes 0/1` was read as "1 antidote available" and written into
    # the notes with none in the bag. The count stays spelled out.
    ok &= check("no bare fraction for antidotes", f"{w.antidotes}/{w.pouch}" not in line)
    ok &= check("one line", "\n" not in line)
    ok &= check("and the view carries it", line in sight.view(w))
    return ok


def test_the_view_stays_affordable():
    print("size")
    w = World()
    worst = 0
    for name in w.areas:
        w.area, w.pos = name, (1, 1)
        w.areas[name].has_map = True
        worst = max(worst, len(sight.view(w)))
    # Replaced rather than appended, so this is a flat tail cost per request, not a
    # growing one. Measured at roughly a token to three characters on gemma4:e4b.
    return check("the largest area fits a sane budget", worst < 4000,
                 f"{worst} chars, about {worst // 3} tokens")


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_the_view_is_fogged(), test_a_pit_is_never_shown(),
               test_names_are_earned(), test_the_list_agrees_with_the_grid(),
               test_the_four_cells_you_could_step_into(),
               test_the_legend_hides_what_has_not_been_found(),
               test_the_grid_has_one_door_onto_the_world(),
               test_the_status_line_survived_the_move(),
               test_the_view_stays_affordable()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
