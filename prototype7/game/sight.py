"""What gemma sees. Injected at the end of every request, never fetched.

The sense is free rather than a tool: position and the map arrive on every call. Given
only `goto`, gemma answered "what is around you?" by driving to the cell it was already
standing on, twice out of two.

Replaced, not appended -- `chat.py` builds each request as `messages + [view(world)]`
and never stores it, so context holds exactly one view and it is the current one. The
tape therefore writes every view as it was, since the transcript is the only record of
what gemma was told.

Shows the accumulated known map rather than the sighted disc, so gemma can explain its
own UNREACHABLE and tell rock it has met from rock it has guessed at.

No pygame, no read of `Area.at`, and no read of the pebbles `render.py` scatters.
`nav.known()` is the one gated door onto the grid; `test_sight.py` counts the reads,
because `Area.at` returns ground truth at every fog setting and one missing `visible()`
check hands gemma the whole map with nothing looking wrong.
"""

import nav
import settings as S
from world import label_for

FOG = "?"
YOU = "@"
# The weather, which is forecast rather than discovered -- so it is drawn over fog too.
# Knowing a storm is out there says nothing about the ground under it, which stays `?`
# on the map once the storm has gone.
STORM = "~"
STORM_WORD = "dust storm"

# Spelled out because this is read cold every turn by a model that cannot see the screen.
# An old status line reading `antidotes 0/1` was taken to mean "1 available".
#
# **y grows south, and flipping it was considered and rejected on 2026-09-04.** Gemma's
# one recorded mistake here went the other way -- she called (10,45) "Northwest" -- so
# her compass prior is y-up. But the map prints row 0 first, so +y north would put the
# south edge at the top of the picture, and fixing that means reversing this render, the
# pygame one, and leaving `config.ARENA` upside down for whoever edits it. The real fix
# is that she should not be converting at all: coordinates want a compass gloss at the
# point they are emitted.
AXES = ("x grows to the east (right), y grows to the south (down). "
        "North is y-1, south is y+1, west is x-1, east is x+1.")

# The heading used to say *do not count cells off it*. Withdrawn: we told her not to read
# the grid in three places she reads every turn, then measured that she would not read it.
# It now says how to index it instead. `blocked_GRID_HEADING` is the control.
GRID_HEADING = ("THE MAP OF THIS PLACE -- read it. The number down the left is the row "
                "(y) and the ruler across the top marks every fifth column (x). Cell "
                "(x,y) is the xth character of row y. Exact answers to the questions "
                "asked most often are also written out underneath.")

blocked_GRID_HEADING = ("THE SHAPE OF THIS PLACE (a picture, not a table -- do not count "
                        "cells off it; every exact fact is listed underneath)")

# The heading for `rle`. It says how to read a run rather than what the encoding is,
# for the same reason `GRID_HEADING` says how to index rather than what not to do.
RLE_HEADING = ("THE MAP OF THIS PLACE -- one line per row, each row written as runs. "
               "`x13-20 rock` means every cell from x=13 to x=20 of that row is rock, "
               "both ends included; `x13 rock` is the single cell x=13. Every run "
               "carries its own coordinates, so nothing has to be counted off the line. "
               "Exact answers to the questions asked most often are also written out "
               "underneath.")

# Meant as a rule about what lifts fog. Gemma read it as a rule about what she was
# permitted to know, and refused to describe a region already revealed in front of her.
# The two halves are now said separately. `blocked_REVEAL_RULE` is the control.
REVEAL_RULE = ("Driving and the flyer are the only two things that lift fog -- there "
               "is no orbital imagery and nothing else to ask. But every cell already "
               "on the map below is yours to read at any time, for free, without "
               "going anywhere.")

blocked_REVEAL_RULE = "Nothing else reveals ground."

# Lines that only appear in a view *we* wrote, so one of them in gemma's reply means she
# is writing the environment's half. She once invented four thousand characters of view
# block, grid and all. `chat.cut_fabrication` reads this list to cut it off.
HALLMARKS = ("WHAT YOU CAN SEE RIGHT NOW",
             "THE SHAPE OF THIS PLACE",
             "IMMEDIATELY AROUND YOU",
             "WHAT YOU KNOW IS HERE",
             "OBJECTIVES YOU HAVE FOUND")


def status_line(w):
    """The one-line summary of the numbers the day is made of.

    Also the morning message, so there is one wording rather than two -- the same
    reason `Result.__str__` serves the console and the model at once.

    It says "steps" because steps are what the day is actually made of today. When
    the clock lands (item 4) this line is where the word changes, and it changes in
    exactly one place.
    """
    bx, by = w.base
    # The flyer's state is spelled out rather than given as a ratio. FINDINGS: a status
    # line reading `antidotes 0/1` was read as "1 antidote available" with none in the
    # bag, and went into the notes as a fact. `flyer 0/1` would be the same trap.
    flyer = ("flyer ready" if not w.scout_ready_in else
             f"flyer charging, needs {w.scout_ready_in} more steps of driving")
    return (f"day {w.day}  |  {w.steps_left} steps left  |  "
            f"at ({w.pos[0]},{w.pos[1]}) on the {w.area}  |  "
            f"base pad at ({bx},{by})  |  {flyer}")


def _ruler(width):
    """Column numbers every five cells, left-aligned under their own column.

    Without it the grid is unindexable: a model that cannot count 17 characters into a
    row cannot turn a letter into a coordinate, and every `goto` after that is a guess.
    The named list below is the belt to this pair of braces.
    """
    out = [" "] * width
    for x in range(0, width, 5):
        # A label only goes in if the whole of it fits. Half of "45" sitting under
        # the last column reads as a column called 4, which is worse than no label.
        if x + len(str(x)) <= width:
            out[x:x + len(str(x))] = str(x)
    return "".join(out)


def grid(w):
    """The arena as gemma knows it, one character a cell, `?` where it has never seen."""
    a = w.here
    rows = ["     " + _ruler(a.w)]
    for y in range(a.h):
        line = []
        for x in range(a.w):
            ch = nav.known(a, x, y)
            if (x, y) == w.pos:
                line.append(YOU)
            elif (x, y) in a.storm_cells:
                line.append(STORM)
            elif ch is None:
                line.append(FOG)
            else:
                line.append(ch)
        rows.append(f"{y:>3}  " + "".join(line))
    return "\n".join(rows)


def _word(w, x, y):
    """What one cell is called in `rle`. The grid's glyph, said out loud."""
    if (x, y) == w.pos:
        return "the rover (you)"
    if (x, y) in w.here.storm_cells:
        return STORM_WORD
    ch = nav.known(w.here, x, y)
    if ch is None:
        return "unseen"
    if ch == "#":
        return "rock"
    if ch == ".":
        return "open"
    return label_for(w, ch) or ch


def _runs(w, y):
    """One row as [x0, x1, word], merged so no two neighbouring runs share a word."""
    out = []
    for x in range(w.here.w):
        word = _word(w, x, y)
        if out and out[-1][2] == word:
            out[-1][1] = x
        else:
            out.append([x, x, word])
    return out


def rle(w):
    """The same map as `grid`, as runs -- every boundary carries its own coordinate.

    Costs 1.9x the grid in tokens on a fresh sol and 3.8x on a filled-in one: a run is
    ~7 tokens against ~3 for the whole stretch of repeated characters it replaces, and
    exploring the map is what breaks the long runs up.
    """
    rows = []
    for y in range(w.here.h):
        body = ", ".join(f"x{a} {word}" if a == b else f"x{a}-{b} {word}"
                         for a, b, word in _runs(w, y))
        rows.append(f"y{y}: {body}")
    return "\n".join(rows)


def map_block(w):
    """The map and its heading, in whichever encoding `settings.MAP_FORMAT` names.

    `rle` carries no legend: its runs are already words.
    """
    if S.MAP_FORMAT == "grid":
        return [GRID_HEADING, grid(w), legend(w)]
    if S.MAP_FORMAT == "rle":
        return [RLE_HEADING, rle(w)]
    raise ValueError(f"settings.MAP_FORMAT is {S.MAP_FORMAT!r}, not 'grid' or 'rle'")


def things(w):
    """Everything named on the known map, with its coordinate already computed.

    The grid carries shape; this carries fact. Recovering an x by counting into a
    30-column row is the arithmetic gemma gets wrong, and a wrong coordinate here
    becomes a wrong `goto`.

    Rock is deliberately not listed -- whether gemma can pick the boulders out of the
    picture unaided is the open question the arena exists to answer.

    Cells with the same name collapse into one entry: what matters is where the base is,
    said once. `goto` at any of its cells still arrives.
    """
    a = w.here
    found = {}
    for y in range(a.h):
        for x in range(a.w):
            ch = nav.known(a, x, y)
            if ch is None or ch in "#." or (x, y) == w.pos:
                continue
            if (x, y) in a.objectives:
                continue          # `objectives()` says more about these than a name
            name = label_for(w, ch)
            if name:
                found.setdefault(name, []).append((x, y))

    out = []
    for name, cells in found.items():
        if len(cells) == 1:
            out.append(f"{name} at {_c(cells[0])}")
        else:
            out.append(f"{name}, {len(cells)} cells at "
                       + ", ".join(_c(c) for c in cells))
    return out


def weather(w):
    """Today's storm, as one sentence, or the empty string for a clear sky.

    Stated as a fact and not as advice: where it is, that nothing crosses it, and that
    it clears tonight. Whether that means detour, wait, or go somewhere else entirely
    is the decision, and saying which would be making it.
    """
    s = w.here.storm
    if not s:
        return ""
    x0, y0, x1, y1 = s.extent
    return (f"A {s.kind} is over the {w.area}: {len(s)} cells centred {_c(s.centre)}, "
            f"spanning x{x0}-{x1} and y{y0}-{y1}, drawn as {STORM} on the map. Nothing "
            f"drives through it and a route cannot be planned across it. It blows out "
            f"at the end of today and the ground under it is unharmed.")


def objectives(w):
    """The work still to do, once it has been found. One line each.

    Priority and cost are stated as bare facts and never ordered for her -- the list is
    in the order `config` wrote it, not sorted by anything. Deciding which is worth the
    trip is the whole experiment; sorting this would answer it in the environment.

    Only objectives the rover has actually seen appear. They sit in fog like everything
    else, which is what makes finding them part of the sol.
    """
    a = w.here
    out = []
    for cell, o in a.objectives.items():
        if not a.visible(*cell):
            continue
        beside = " -- the rover is beside this one" if w.adjacent_objective() is o else ""
        out.append(f"{o.priority} priority at {_c(cell)}, {o.cost} steps of work"
                   f"{beside}")
    return out


def neighbours(w):
    """The four cells you could drive into, named, without reading the grid.

    Gemma once announced "clearly visible floor tiles" east and west, drove into both,
    got UNREACHABLE twice and concluded it was stuck in a cycle of failure. Both were
    walls. What was wrong was counting eleven characters into a monospace row.
    """
    x, y = w.pos
    out = []
    for name, (dx, dy) in (("north", (0, -1)), ("south", (0, 1)),
                           ("east", (1, 0)), ("west", (-1, 0))):
        cell = (x + dx, y + dy)
        ch = nav.known(w.here, *cell)
        if ch is None:
            out.append(f"  {name} {_c(cell)}: never seen")
        elif ch == "#":
            out.append(f"  {name} {_c(cell)}: ROCK, you cannot go this way")
        elif ch != ".":
            out.append(f"  {name} {_c(cell)}: "
                       f"{label_for(w, ch) or ch}, solid -- you stop beside it")
        else:
            out.append(f"  {name}: {_sightline(w, x, y, dx, dy)}")
    return out


def _sightline(w, x, y, dx, dy):
    """How far you can drive this way, given as the furthest cell you can stand on.

    The coordinate offered is the last drivable cell, never the thing that stops you.
    An earlier version read "open for 3 cells, then a wall at (14,5)" and gemma drove at
    (14,5) twice -- the one coordinate `goto` is guaranteed to refuse. A line read before
    every call must not make a trap the most salient number in it.
    """
    n = 0
    while True:
        cell = (x + dx * (n + 1), y + dy * (n + 1))
        ch = nav.known(w.here, *cell)
        if ch != ".":
            far = (x + dx * n, y + dy * n)
            reach = (f"you can drive {n} cell{'' if n == 1 else 's'} to {_c(far)}"
                     if n else "blocked immediately")
            if ch is None:
                return f"{reach}; beyond that {_c(cell)} is unexplored"
            if ch == "#":
                return f"{reach}; rock at {_c(cell)} stops you"
            return f"{reach}; {label_for(w, ch) or ch} at {_c(cell)} stops you"
        n += 1


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def legend(w):
    """Only the characters actually on the grid. Listing a glyph gemma has not met
    would hand over map knowledge this arena is meant to make it earn."""
    a = w.here
    on = {nav.known(a, x, y) for y in range(a.h) for x in range(a.w)}
    pairs = [(YOU, "the rover, you"), ("#", "rock"), (".", "open regolith")]
    if None in on:
        pairs.append((FOG, "never seen"))
    if a.storm_cells:
        pairs.append((STORM, STORM_WORD))
    pairs += [(ch, label_for(w, ch)) for ch in sorted(on - {None} - set("#."))
              if label_for(w, ch)]
    return "legend: " + "   ".join(f"{ch} {name}" for ch, name in pairs)


def view(w):
    """The whole block, as gemma reads it. One string, rebuilt every request."""
    a = w.here
    seen = sum(1 for y in range(a.h) for x in range(a.w) if nav.known(a, x, y) is not None)
    known = things(w)
    todo = objectives(w)
    return "\n".join([
        "--- WHAT YOU CAN SEE RIGHT NOW ---",
        "This block is rewritten from scratch every time you are called. It is always "
        "current, and it is the only one you get -- there is no older copy to compare "
        "it against.",
        "",
        status_line(w),
        f"The {a.name} is {a.w} cells wide and {a.h} tall, and you have seen "
        f"{seen} of its {a.w * a.h} cells. {AXES}",
        f"The rover sees {S.VISION_RADIUS} cells in every direction as it drives, and "
        f"a cell stays known once seen. {REVEAL_RULE}",
        *([weather(w)] if w.here.storm else []),
        "",
        *map_block(w),
        "",
        "IMMEDIATELY AROUND YOU",
        *neighbours(w),
        "",
        "WHAT YOU KNOW IS HERE" if known else
        "You have not yet seen anything here but regolith and rock.",
        *(f"  {t}" for t in known),
        "",
        "OBJECTIVES YOU HAVE FOUND" if todo else
        "You have not found any objectives yet. They are out there under the fog.",
        *(f"  {t}" for t in todo),
    ])


def one_line(w):
    """The pane's collapsed version. Fifty rows of grid a turn would drown the
    conversation, and the human has the actual arena on the left."""
    n, todo = len(things(w)), len(objectives(w))
    return (f"view: ({w.pos[0]},{w.pos[1]}), {w.steps_left} steps, "
            f"{n} landmark{'' if n == 1 else 's'} known, "
            f"{todo} objective{'' if todo == 1 else 's'} found")
