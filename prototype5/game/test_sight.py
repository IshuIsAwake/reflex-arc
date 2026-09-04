r"""What gemma is told, and what it must not be told.

    ..\.venv\Scripts\python.exe game\test_sight.py

Two of these are load-bearing. `test_the_grid_has_one_door_onto_the_world` reads the
source, because `Area.at` returns ground truth at every fog setting and one missing
`visible()` check hands over the whole arena with nothing ever looking wrong.
`test_decoration_never_reaches_the_view` is its twin for the other direction: the
pebbles `render.py` scatters are texture, and they stop being harmless the instant
anything reads them.
"""

import pathlib
import re
import sys

import nav
import settings as S
import sight
from world import World


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def rows(w):
    """The grid without its ruler row or its row labels."""
    return [r[5:] for r in sight.grid(w).splitlines()[1:]]


def surveyed():
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    return w


def test_the_view_is_fogged():
    print("fog")
    w = World()
    g = rows(w)
    ok = check("fifty rows", len(g) == 50, str(len(g)))
    ok &= check("fifty columns", all(len(r) == 50 for r in g))
    ok &= check("the far corner is unseen", g[2][2] == sight.FOG)
    ok &= check("the rover is drawn", g[25][25] == sight.YOU)
    ok &= check("the pad is not", g[26][25] == "H")
    ok &= check("most of it is still fog",
                sum(r.count(sight.FOG) for r in g) > 2000,
                f"{sum(r.count(sight.FOG) for r in g)} of 2500")

    g2 = rows(surveyed())
    ok &= check("surveyed, nothing is fog", not any(sight.FOG in r for r in g2))
    rock = sum(r.count("#") for r in g2)
    ok &= check("...and the rock is all there",
                rock == sum(r.count("#") for r in __import__("config").ARENA),
                f"{rock} cells")
    return ok


def test_the_list_agrees_with_the_grid():
    print("the named list")
    w = surveyed()
    named = sight.things(w)
    ok = check("one entry, not six", len(named) == 1, str(named))
    entry = named[0]
    ok &= check("it is the pad", entry.startswith("base pad, 6 cells"), entry)
    for cell in re.findall(r"\((\d+),(\d+)\)", entry):
        x, y = int(cell[0]), int(cell[1])
        ok &= check(f"({x},{y}) really is the pad", nav.known(w.here, x, y) == "H")
    return ok


def test_the_four_cells_you_could_step_into():
    print("neighbours")
    w = World()
    lines = sight.neighbours(w)
    ok = check("four of them", len(lines) == 4, str(len(lines)))
    south = next(li for li in lines if li.strip().startswith("south"))
    ok &= check("the pad is named and called solid",
                "base pad" in south and "solid" in south, south)

    # The sightline offers the last drivable cell, never the thing that stops you.
    # Gemma read the wall coordinate off the old wording and called goto on it twice.
    north = next(li for li in lines if li.strip().startswith("north"))
    ok &= check("north says how far it can go", "you can drive" in north, north)
    far = re.search(r"to \((\d+),(\d+)\)", north)
    ok &= check("and that cell is drivable",
                bool(far) and nav.known(w.here, int(far[1]), int(far[2])) == ".",
                north)

    w2 = surveyed()
    w2.pos = (32, 29)
    east = next(li for li in sight.neighbours(w2) if li.strip().startswith("east"))
    ok &= check("rock is named as rock and refused",
                "ROCK" in east and "cannot go" in east, east)
    return ok


def test_the_legend_hides_what_has_not_been_found():
    print("legend")
    w = World()
    leg = sight.legend(w)
    ok = check("fog is listed while there is fog", "? never seen" in leg, leg)
    ok &= check("the pad is listed, having been landed on", "H base pad" in leg, leg)

    g = surveyed()
    ok &= check("surveyed, fog drops out", "never seen" not in sight.legend(g))
    return ok


SPAN = re.compile(r"x(\d+)(?:-(\d+))? ([a-z][a-z ()]*[a-z)])")


def rle_rows(w):
    """`sight.rle` expanded back to one word a cell, so it can be laid on the grid."""
    out = []
    for line in sight.rle(w).splitlines():
        cells = []
        for a, b, word in SPAN.findall(line.split(": ", 1)[1]):
            a = int(a)
            b = int(b) if b else a
            cells += [word] * (b - a + 1)
        out.append(cells)
    return out


def test_the_runs_say_what_the_picture_says():
    print("run-length encoding")
    keep = S.MAP_FORMAT
    S.MAP_FORMAT = "rle"
    try:
        # The glyph each word has to agree with. Two renderers compared against each
        # other, not both against `nav.known`, which is the layer they share.
        word = {sight.FOG: "unseen", "#": "rock", ".": "open",
                sight.YOU: "the rover (you)", "H": "base pad"}
        ok = True
        for name, w in (("fogged", World()), ("surveyed", surveyed())):
            spans, pic = rle_rows(w), rows(w)
            ok &= check(f"{name}: fifty rows of fifty cells",
                        len(spans) == 50 and all(len(r) == 50 for r in spans),
                        f"{len(spans)} rows, widths {sorted({len(r) for r in spans})}")
            bad = [(x, y, pic[y][x], spans[y][x]) for y in range(50) for x in range(50)
                   if word[pic[y][x]] != spans[y][x]]
            ok &= check(f"{name}: every cell agrees with the grid", not bad,
                        f"{len(bad)} disagree, e.g. {bad[:3]}")
            # An unmerged run is still correct cell by cell, and costs double.
            unmerged = []
            for y, line in enumerate(sight.rle(w).splitlines()):
                said = [s[2] for s in SPAN.findall(line.split(": ", 1)[1])]
                unmerged += [(y, a) for a, b in zip(said, said[1:]) if a == b]
            ok &= check(f"{name}: neighbouring runs never share a word", not unmerged,
                        str(unmerged[:3]))

        ok &= check("fog is named, not left out",
                    "unseen" in sight.rle(World()).splitlines()[0])
        ok &= check("the heading tells her how to read a run",
                    sight.RLE_HEADING in sight.view(World())
                    and sight.GRID_HEADING not in sight.view(World()))

        # Not flat like the grid: filling the map in is what fragments the runs. The cap
        # is the affordability question, and it is the whole argument against this format.
        day_one, worst = len(sight.view(World())), len(sight.view(surveyed()))
        ok &= check("a surveyed arena still fits the budget", worst < 9000,
                    f"sol 1 {day_one} chars, surveyed {worst}")

        S.MAP_FORMAT = "nonsense"
        try:
            sight.view(World())
            ok &= check("an unknown MAP_FORMAT is refused", False)
        except ValueError:
            ok &= check("an unknown MAP_FORMAT is refused", True)
        return ok
    finally:
        S.MAP_FORMAT = keep


def test_the_grid_has_one_door_onto_the_world():
    print("the gated door")
    src = (pathlib.Path(__file__).parent / "sight.py").read_text()
    # Prose cannot read a grid. Strip docstrings and comments, then the check is about
    # code only -- otherwise the file cannot even name what it must not touch.
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    ok = check("no read of Area.at", ".at(" not in src)
    ok &= check("no read of Area.seen", ".seen" not in src)
    ok &= check("nav.known is used", "nav.known(" in src)
    return ok


def test_decoration_never_reaches_the_view():
    print("texture is not terrain")
    src = (pathlib.Path(__file__).parent / "sight.py").read_text()
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    ok = check("sight.py does not import render", "import render" not in src)
    ok &= check("no read of the grit scatter", "_grit" not in src)
    ok &= check("no read of the rock shading", "_rock_shade" not in src)

    # And the other direction: the decoration must be a pure function of the cell, or
    # it is state, and state that only the human can see is a second world.
    import render
    ok &= check("grit is deterministic", render._grit(7, 11) == render._grit(7, 11))
    ok &= check("...and differs by cell",
                len({tuple(render._grit(x, 3)) for x in range(40)}) > 3)
    return ok


def test_the_status_line_survived_the_move():
    print("the morning line")
    w = World()
    line = sight.status_line(w)
    ok = check("has the four facts", all(bit in line for bit in
               ("day 1", "steps left", "at (25,25)", "base pad at")), line)
    ok &= check("one line", "\n" not in line)
    ok &= check("and the view carries it", line in sight.view(w))
    ok &= check("it says steps, because steps are what a sol is made of",
                "steps left" in line, line)
    return ok


def test_the_view_stays_affordable():
    print("size")
    day_one = len(sight.view(World()))
    worst = len(sight.view(surveyed()))
    # Replaced rather than appended, so this is a flat tail cost per request and not a
    # growing one.
    ok = check("a fully surveyed arena fits a sane budget", worst < 7000,
               f"{worst} chars")

    # The intuition is wrong: a sol-one view is not smaller than a surveyed one, since
    # the grid is one character per cell whatever it holds. In *characters* the view is
    # flat from the first request. Tokens are another story this test cannot see -- a run
    # of fifty '?' merges into far fewer tokens than a mixed row.
    ok &= check("the character cost is flat, not growing",
                abs(worst - day_one) < worst * 0.05,
                f"sol 1 {day_one} chars, surveyed {worst} -- the grid is one char a "
                f"cell either way")
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_the_view_is_fogged(), test_the_list_agrees_with_the_grid(),
               test_the_four_cells_you_could_step_into(),
               test_the_legend_hides_what_has_not_been_found(),
               test_the_runs_say_what_the_picture_says(),
               test_the_grid_has_one_door_onto_the_world(),
               test_decoration_never_reaches_the_view(),
               test_the_status_line_survived_the_move(),
               test_the_view_stays_affordable()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
