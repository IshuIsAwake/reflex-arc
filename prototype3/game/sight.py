"""What gemma sees. Injected at the end of every request, never fetched.

**This is not a tool and there is no `look()`.** Position and the map arrive unbidden
on every single call. What this prototype is trying to watch is what gemma *does* with
what it sees, not whether it remembers to go and look -- a forgotten `look()` costs a
whole day and teaches nobody anything. Measured on 2026-08-26: asked "what is around
you?" with only `goto` wired up, gemma called `goto` on the cell it was already
standing on, twice out of two. Given one tool it will use that tool for everything, so
the sense has to be free.

**Live means replaced, not appended.** `chat.py` builds each request as
`messages + [view(world)]` and never stores the result, so context holds exactly one
view and it is always the current one. Appending would accumulate stale maps to reason
off and eat MODEL_CTX in a morning. The trap that follows: the transcript is then the
only record of what gemma was actually told, so the tape writes every view as it was.
Reading a run back is how the rock bug was found.

**It shows the accumulated known map, not the sighted disc.** `nav.known()` returns "#"
off the edge of the arena, so the planner already reasons over the whole seen-set *and*
the arena's extent. Show gemma only the radius-3 disc and it cannot explain its own
UNREACHABLE, cannot price a trip, and cannot tell rock it has met from rock it has
merely guessed at.

**Ingenuity is item 5 and is not here.** When it lands it reveals a patch the rover has
not driven through, which is a write into `Area.seen` -- this file needs no change for
it, and that is the point of the sense being one function.

No pygame in here, and **no read of `Area.at`.** `nav.known()` is the one gated door
onto the grid and this file is the second thing through it. `test_sight.py` counts the
reads exactly the way `test_nav.py` does, because `Area.at` returns ground truth at
every fog setting and one missing `visible()` check hands gemma the whole map with
nothing ever looking wrong.

**And no read of the decoration.** The pebbles `render.py` scatters are texture, not
tiles. If this file ever grows a reference to them, something the human can see and
gemma cannot has become something both can, and the arena has quietly changed shape.
"""

import nav
import settings as S
from world import label_for

FOG = "?"
YOU = "@"

# Spelled out because this block is read cold, every turn, by a model that cannot see
# the screen. FINDINGS: `antidotes 0/1` in an old status line was read as "1 antidote
# available" with none in the bag, and went into the notes as a fact. Anything repeated
# after every single call is worth spending six words on.
AXES = ("x grows to the east (right), y grows to the south (down). "
        "North is y-1, south is y+1, west is x-1, east is x+1.")

# Measured 2026-08-26: asked what character sits at a named cell of this grid, gemma
# answered correctly about half the time, with thinking on and with it off. The reading
# taken from that was that the grid is a picture and not a lookup table, and the heading
# said so -- *do not count cells off it* -- because the expensive failure was gemma
# deciding a route was blocked when `distance` would have answered for nothing.
#
# **That heading is now a suspect rather than a safeguard, 2026-08-31.** Asked three
# direct questions about named regions of a map she was holding, gemma got 0 of 3 and
# said she was not allowed to answer without driving there (`MAP-READING.md`). We had
# told her not to read the grid, here and in two other places she reads every turn, and
# then measured that she would not read the grid. The prohibition is withdrawn and the
# heading now says how to index the thing instead. `blocked_GRID_HEADING` is the control.
GRID_HEADING = ("THE MAP OF THIS PLACE -- read it. The number down the left is the row "
                "(y) and the ruler across the top marks every fifth column (x). Cell "
                "(x,y) is the xth character of row y. Exact answers to the questions "
                "asked most often are also written out underneath.")

blocked_GRID_HEADING = ("THE SHAPE OF THIS PLACE (a picture, not a table -- do not count "
                        "cells off it; every exact fact is listed underneath)")

# The sentence gemma quoted back as a rule about what she was *permitted to know*.
# `sight.py` meant it as a rule about what lifts fog: no orbital imagery, no radio, you
# drive or you stay ignorant. She read it as "I only reveal information by driving" and
# refused to describe a region that was fully revealed and sitting in front of her.
# Both halves are now said separately, because it was the collision of the two that did
# the damage. `blocked_REVEAL_RULE` is the control.
REVEAL_RULE = ("Driving is the only thing that lifts fog -- there is no orbital "
               "imagery and nothing else to ask. But every cell already on the map "
               "below is yours to read at any time, for free, without going anywhere.")

blocked_REVEAL_RULE = "Nothing else reveals ground."

# Lines that only ever appear in a view *we* wrote. If one of them turns up in what the
# model said, the model is writing the environment's half of the conversation.
#
# Watched 2026-08-29: asked to explore, gemma replied with a sentence, a call typed out
# as text, and then four thousand characters of invented view block -- a grid, a step
# count of 399, a position of (31,25) it had never been to. All of it became an
# assistant message. `chat.cut_fabrication` reads this list to cut it off.
HALLMARKS = ("WHAT YOU CAN SEE RIGHT NOW",
             "THE SHAPE OF THIS PLACE",
             "IMMEDIATELY AROUND YOU",
             "WHAT YOU KNOW IS HERE")


def status_line(w):
    """The one-line summary of the numbers the day is made of.

    Also the morning message, so there is one wording rather than two -- the same
    reason `Result.__str__` serves the console and the model at once.

    It says "steps" because steps are what the day is actually made of today. When
    the clock lands (item 4) this line is where the word changes, and it changes in
    exactly one place.
    """
    bx, by = w.base
    return (f"day {w.day}  |  {w.steps_left} steps left  |  "
            f"at ({w.pos[0]},{w.pos[1]}) on the {w.area}  |  "
            f"base pad at ({bx},{by})")


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
            elif ch is None:
                line.append(FOG)
            else:
                line.append(ch)
        rows.append(f"{y:>3}  " + "".join(line))
    return "\n".join(rows)


def things(w):
    """Everything named on the known map, with its coordinate.

    The grid carries shape; this carries fact. Reading a letter out of a 50-column row
    and recovering its x is exactly the arithmetic a 4B model gets quietly wrong, and a
    wrong coordinate here becomes a wrong `goto` and then a wrong note. So the
    coordinates are handed over already computed.

    **Rock is not listed, and since 2026-08-29 that is an experiment rather than an
    economy.** The old reason was cost: 450 scattered outcrops, and naming each would
    bury the one thing that matters in a wall of coordinates, which FINDINGS measured
    as the most expensive way there is to describe a map (972 tokens against 196 for
    the picture). The arena now holds thirty boulders and nothing else, and naming them
    would be affordable -- a line each is a few hundred characters.

    It is still not done, because what the rebuilt arena is *for* is finding out
    whether gemma can pick the boulders out of the picture on its own. FINDINGS
    measured it failing to **index** a grid -- naming the cell at a given coordinate,
    five times in ten. Counting compact lumps and saying roughly where they are is a
    different skill and has never been measured here. If it cannot, the names come back
    and this docstring gets rewritten again; if it can, the picture was carrying more
    than anybody credited. Either answer is worth more than the line it would save.

    **Cells with the same name are collapsed into one entry.** The pad is six tiles,
    and six consecutive lines all reading `base pad at ...` is the wall-of-coordinates
    failure in miniature: the thing that matters is *where the base is*, said once.
    Every cell is still named, because `goto` at any of them arrives.
    """
    a = w.here
    found = {}
    for y in range(a.h):
        for x in range(a.w):
            ch = nav.known(a, x, y)
            if ch is None or ch in "#." or (x, y) == w.pos:
                continue
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


def neighbours(w):
    """The four cells you could drive into, named, without reading the grid.

    Added 2026-08-26 after watching the failure it prevents. Gemma announced it had
    "clearly visible floor tiles" east and west and called `goto` on both; both were
    walls, both came back UNREACHABLE, and it concluded it was "stuck in a cycle of
    failure." The planner was right every time. What was wrong was counting eleven
    characters into a monospace row.

    Four cells is nothing to inject and it is the cheapest arithmetic to stop asking a
    4B model to do.
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

    The neighbour alone answers "can I go there" and leaves "which way is worth going"
    to be counted off the grid, which is the arithmetic gemma gets wrong half the time.
    Walking the ray here costs nothing and hands over the answer.

    **The coordinate offered is the last drivable cell, never the thing that stops
    you.** The first version read "open for 3 cells, then a wall at (14,5)", and on
    2026-08-26 gemma standing at (18,5) called `goto(14,5)` twice and got UNREACHABLE
    both times. It read correctly and acted on the only number in the sentence -- which
    was the one coordinate `goto` is guaranteed to refuse, because known rock is
    deliberately not a destination. A line read before every call must put the useful
    number where the model will reach for it, and must not make a trap the most
    salient thing in it.
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
    pairs += [(ch, label_for(w, ch)) for ch in sorted(on - {None} - set("#."))
              if label_for(w, ch)]
    return "legend: " + "   ".join(f"{ch} {name}" for ch, name in pairs)


def view(w):
    """The whole block, as gemma reads it. One string, rebuilt every request."""
    a = w.here
    seen = sum(1 for y in range(a.h) for x in range(a.w) if nav.known(a, x, y) is not None)
    known = things(w)
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
        "",
        GRID_HEADING,
        grid(w),
        legend(w),
        "",
        "IMMEDIATELY AROUND YOU",
        *neighbours(w),
        "",
        "WHAT YOU KNOW IS HERE" if known else
        "You have not yet seen anything here but regolith and rock.",
        *(f"  {t}" for t in known),
    ])


def one_line(w):
    """The pane's collapsed version. Fifty rows of grid a turn would drown the
    conversation, and the human has the actual arena on the left."""
    n = len(things(w))
    return (f"view: ({w.pos[0]},{w.pos[1]}), {w.steps_left} steps, "
            f"{n} landmark{'' if n == 1 else 's'} known")
