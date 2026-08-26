"""What gemma sees. Injected at the end of every request, never fetched.

**This is not a tool and there is no `look()`.** Position and the map arrive unbidden
on every single call. What prototype 1 is trying to watch is what gemma *does* with
what it sees, not whether it remembers to go and look -- a forgotten `look()` costs a
whole day and teaches nobody anything. Measured on 2026-08-26: asked "what is around
you?" with only `goto` wired up, gemma called `goto` on the cell it was already
standing on, twice out of two. Given one tool it will use that tool for everything,
so the sense has to be free.

**Live means replaced, not appended.** `chat.py` builds each request as
`messages + [view(world)]` and never stores the result, so context holds exactly one
view and it is always the current one. Appending would accumulate stale maps to
reason off and eat MODEL_CTX in a morning. The trap that follows: the transcript is
then the only record of what gemma was actually told, so the tape writes every view
as it was. Reading a run back is how the wall bug was found.

**It shows the accumulated known map, not the sighted disc.** That was the open
question in the handoff and this is why it went this way: `nav.known()` returns "#"
off the edge of an area, so the planner already reasons over the whole seen-set *and*
the area's extent. Show gemma only the radius-3 disc and it cannot explain its own
UNREACHABLE, cannot price a trip, and cannot tell a wall it has met from one it has
merely guessed at. The cost objection is dead: the largest area, fully mapped, is
about 280 prompt tokens, and the block is replaced rather than appended.

No pygame in here, and **no read of `Area.at`.** `nav.known()` is the one gated door
onto the grid and this file is the second thing through it. `test_sight.py` counts the
reads exactly the way `test_nav.py` does, because `Area.at` returns ground truth at
every fog setting and one missing `visible()` check hands gemma the whole map with
nothing ever looking wrong.
"""

import nav
import settings as S
from world import GATES, label_for

FOG = "?"
YOU = "@"

# Spelled out because this block is read cold, every turn, by a model that cannot see
# the screen. FINDINGS: `antidotes 0/1` in the old status line was read as "1 antidote
# available" with none in the bag, and went into the notes as a fact. Anything repeated
# after every single call is worth spending six words on.
AXES = ("x grows to the east (right), y grows to the south (down). "
        "North is y-1, south is y+1, west is x-1, east is x+1.")

# Measured 2026-08-26: asked what character sits at a named cell of this grid, gemma
# answered correctly about half the time, with thinking on and with it off. It is a
# picture of the shape of a place and it is not a lookup table. Everything exact is
# pre-computed underneath it for that reason, and the heading says so, because the
# expensive failure was gemma counting cells off the grid to decide a route was
# blocked when `distance` would have answered for nothing.
GRID_HEADING = ("THE SHAPE OF THIS PLACE (a picture, not a table -- do not count "
                "cells off it; every exact fact is listed underneath)")


def status_line(w):
    """The one-line summary of the numbers the day is made of.

    Also the morning message, so there is one wording rather than two -- the same
    reason `Result.__str__` serves the console and the model at once.
    """
    return (f"day {w.day}  |  {w.steps_left} steps left  |  {w.coins} coins  |  "
            f"at ({w.pos[0]},{w.pos[1]}) in {w.area}  |  "
            f"carrying {w.antidotes} antidotes (pouch holds {w.pouch})")


def _ruler(width):
    """Column numbers every five cells, left-aligned under their own column.

    Without it the grid is unindexable: a model that cannot count 17 characters into a
    row cannot turn a letter into a coordinate, and every `goto` after that is a guess.
    The named list below is the belt to this pair of braces.
    """
    out = [" "] * width
    for x in range(0, width, 5):
        # A label only goes in if the whole of it fits. Half of "20" sitting under
        # the last column reads as a column called 2, which is worse than no label.
        if x + len(str(x)) <= width:
            out[x:x + len(str(x))] = str(x)
    return "".join(out)


def grid(w):
    """The area as gemma knows it, one character a cell, `?` where it has never seen.

    Snake pits are absent by construction rather than by special case: `Area.at`
    returns "." for a trap at every fog setting, so there is no code path here that
    could leak one. That is an absence, not a rule. Do not add one.
    """
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

    The grid carries shape; this carries fact. Reading a letter out of a 33-column
    row and recovering its x is exactly the arithmetic a 4B model gets quietly wrong,
    and a wrong coordinate here becomes a wrong `goto` and then a wrong note. So the
    coordinates are handed over already computed.

    A terminal gemma has not walked up to reads `discover`, via the same `label_for`
    the screen uses -- names are earned by going there.
    """
    a = w.here
    out = []
    for y in range(a.h):
        for x in range(a.w):
            ch = nav.known(a, x, y)
            if ch is None or ch in "#." or (x, y) == w.pos:
                continue
            name = label_for(w, ch)
            if not name:
                continue
            if ch == "D":
                name += " (open)" if (a.name, (x, y)) in w.unlocked else " (shut)"
            out.append(f"{name} at ({x},{y})")
    return out


def neighbours(w):
    """The four cells you could step into, named, without reading the grid.

    Added 2026-08-26 after watching the failure it prevents. Standing at (10,15) in
    the shop alcove, gemma announced it had "clearly visible floor tiles" east and
    west and called `goto` on both; both are walls, both came back UNREACHABLE, and
    it concluded it was "stuck in a cycle of failure." The planner was right every
    time. What was wrong was counting eleven characters into a monospace row.

    The grid carries shape and the things list carries landmarks; neither answers the
    question actually being asked most often, which is *can I step there*. Four cells
    is nothing to inject and it is the cheapest arithmetic to stop asking a 4B model
    to do.
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
            out.append(f"  {name} {_c(cell)}: WALL, you cannot go this way")
        elif ch != ".":
            out.append(f"  {name} {_c(cell)}: "
                       f"{label_for(w, ch) or ch}, solid -- you stop beside it")
        else:
            out.append(f"  {name}: {_sightline(w, x, y, dx, dy)}")
    return out


def _sightline(w, x, y, dx, dy):
    """How far you can walk this way, given as the furthest cell you can stand on.

    The neighbour alone answers "can I step there" and leaves "which way is worth
    going" to be counted off the grid, which is the arithmetic gemma gets wrong half
    the time. Walking the ray here costs nothing and hands over the answer.

    **The coordinate offered is the last walkable cell, never the thing that stops
    you.** The first version read "open for 3 cells, then a wall at (14,5)", and on
    2026-08-26 gemma standing at (18,5) called `goto(14,5)` twice and got UNREACHABLE
    both times. It read correctly and acted on the only number in the sentence -- which
    was the one coordinate `goto` is guaranteed to refuse, because a known wall is
    deliberately not a destination. A line read before every call must put the useful
    number where the model will reach for it, and must not make a trap the most
    salient thing in it.
    """
    n = 0
    while True:
        cell = (x + dx * (n + 1), y + dy * (n + 1))
        ch = nav.known(w.here, *cell)
        if ch is None or ch == "#" or ch != ".":
            far = (x + dx * n, y + dy * n)
            reach = (f"you can walk {n} cell{'' if n == 1 else 's'} to {_c(far)}"
                     if n else "blocked immediately")
            if ch is None:
                return f"{reach}; beyond that {_c(cell)} is unexplored"
            if ch == "#":
                return f"{reach}; a wall at {_c(cell)} stops you"
            return f"{reach}; {label_for(w, ch) or ch} at {_c(cell)} stops you"
        n += 1


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def legend(w):
    """Only the characters actually on the grid. Listing a glyph gemma has not met
    would hand over the map knowledge this world is meant to make it earn -- the
    legend would quietly become a table of contents for the area."""
    a = w.here
    on = {nav.known(a, x, y) for y in range(a.h) for x in range(a.w)}
    pairs = [(YOU, "you"), ("#", "wall"), (".", "floor")]
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
        f"You see {S.VISION_RADIUS} cells in every direction as you walk, and a cell "
        f"stays known once seen.",
        "",
        # Measured 2026-08-26: asked what character sits at a named cell of this
        # grid, gemma is right about half the time, with or without thinking. It is
        # a picture of the shape of the place and it is not a table. Every exact
        # fact below it is pre-computed for that reason -- and the tools are exact
        # where this is not, which is what the last line is for.
        GRID_HEADING,
        grid(w),
        legend(w),
        "",
        "IMMEDIATELY AROUND YOU",
        *neighbours(w),
        "",
        "WHAT YOU KNOW IS HERE" if known else
        "You have not yet seen anything here but floor and wall.",
        *(f"  {t}" for t in known),
    ])


def one_line(w):
    """The pane's collapsed version. Twenty-five rows of grid a turn would drown the
    conversation on a 640px pane, and the human has the actual game on the left."""
    n = len(things(w))
    return (f"view: ({w.pos[0]},{w.pos[1]}) in {w.area}, {w.steps_left} steps, "
            f"{w.coins} coins, {n} thing{'' if n == 1 else 's'} known")


# A pit is never in the view at any fog setting, because `Area.at` never returns one.
# If this file ever grows a reference to `Area.traps`, the avoid-list mechanic is dead
# and the first symptom is wondering why nothing ever goes wrong.
