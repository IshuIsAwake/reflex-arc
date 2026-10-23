"""What the model sees: the view block, rebuilt and sent at the end of every request.
It shows the map as the rover knows it, never the true arena: every cell is read through
nav.known(), which hides what hasn't been seen (test_sight checks this)."""

import nav
import settings
from world import label_for

FOG = "?"
YOU = "@"
# The storm is forecast, so it is drawn over fog too.
STORM = "~"
STORM_WORD = "dust storm"

# Spelled out because the model reads this cold every turn. y grows south because the
# map prints row 0 first.
AXES = ("x grows to the east (right), y grows to the south (down). "
        "North is y-1, south is y+1, west is x-1, east is x+1.")

GRID_HEADING = ("THE MAP OF THIS PLACE -- read it. The number down the left is the row "
                "(y) and the ruler across the top marks every fifth column (x). Cell "
                "(x,y) is the xth character of row y. Exact answers to the questions "
                "asked most often are also written out underneath.")


REVEAL_RULE = ("Driving is the only thing that lifts fog -- there is no orbital "
               "imagery and nothing else to ask. But every cell already on the map "
               "below is yours to read at any time, for free, without going anywhere.")


# Lines only a view we wrote contains. One of them in her reply means she is writing
# a fake view, and chat.cut_fabrication cuts it off.
HALLMARKS = ("WHAT YOU CAN SEE RIGHT NOW",
             "THE SHAPE OF THIS PLACE",
             "IMMEDIATELY AROUND YOU",
             "WHAT YOU KNOW IS HERE",
             "OBJECTIVES FROM MISSION CONTROL",
             "INTERESTS YOU HAVE FOUND",
             "WORK FINISHED ON THIS MISSION",
             # Her own blocks are written by us too, so she could forge them.
             "YOUR LIST FOR TODAY",
             "YOUR LIST FOR TOMORROW",
             "YOUR MEMORY",
             "YOUR ORDERS FROM MISSION CONTROL")


def status_line(world):
    """The one-line summary of the day's numbers. Also the dawn's first status line."""
    bx, by = world.base
    clock = {"dawn": f"dawn of sol {world.day}  |  the day has not begun: {world.time_left:.0f} "
                     f"seconds once it does",
             "day": f"sol {world.day}, day  |  {world.time_left:.0f} seconds of the day left"}.get(
        world.phase, f"sol {world.day}, {world.phase}  |  the day is over")
    return (f"{clock}  |  battery {world.battery} of {settings.BATTERY} steps  |  "
            f"at ({world.pos[0]},{world.pos[1]}) on the {world.area}  |  base pad at ({bx},{by})")


def home(world):
    """Where the night will find the rover, said every request. Only the pad recharges it."""
    out = []
    if world.stranded:
        out.append("Last night the rover was stranded away from the pad, so the battery "
                   "was not recharged.")
    if world.docked:
        out.append("You are beside the pad. End the day here and the battery recharges "
                   "overnight: tomorrow starts full, from the pad, and whatever charge is "
                   "left tonight goes unused.")
        return out
    if world.lost:
        out.append(f"The rover is lost: the battery holds {world.battery} steps, less than "
                   f"the shortest possible trip back to the pad, and nothing but the pad "
                   f"recharges it. The mission ends when this sol does.")
        return out
    back = nav.home_steps(world)
    trip = (f"The pad is at least {back} steps away: that much battery, and about "
            f"{nav.drive_seconds(back):.0f} seconds of the day to drive it."
            if back is not None else "There is no known route back to the pad.")
    out.append(f"You are away from the pad. {trip} If the day ends with the rover "
               f"anywhere but beside the pad it is stranded: no recharge, so tomorrow "
               f"it wakes where it stopped on whatever charge is left. If the charge falls "
               f"below what the trip back needs, the rover is lost.")
    return out


def _ruler(width):
    """Column numbers every five cells, so a cell can be found without counting."""
    out = [" "] * width
    for x in range(0, width, 5):
        # A label goes in only if all of it fits: half of "45" would read as a column called 4.
        if x + len(str(x)) <= width:
            out[x:x + len(str(x))] = str(x)
    return "".join(out)


def grid(world):
    """The arena as the rover knows it, one character a cell, `?` where it has never seen."""
    area = world.here
    rows = ["     " + _ruler(area.w)]
    for y in range(area.h):
        line = []
        for x in range(area.w):
            ch = nav.known(area, x, y)
            if (x, y) == world.pos:
                line.append(YOU)
            elif (x, y) in area.storm_cells:
                line.append(STORM)
            elif ch is None:
                line.append(FOG)
            else:
                line.append(ch)
        rows.append(f"{y:>3}  " + "".join(line))
    return "\n".join(rows)


def map_block(world):
    return [GRID_HEADING, grid(world), legend(world)]


def things(world):
    """Everything named on the known map, with its coordinate written out. Rock is not
    listed. Cells with the same name are one entry."""
    area = world.here
    found = {}
    for y in range(area.h):
        for x in range(area.w):
            ch = nav.known(area, x, y)
            if ch is None or ch in "#." or (x, y) == world.pos:
                continue
            if (x, y) in area.objectives or (x, y) in area.interests:
                continue  # the work lists say more about these
            name = label_for(world, ch)
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


def weather(world):
    """Today's storm as one sentence of fact, or "" for a clear sky."""
    s = world.here.storm
    if not s:
        return ""
    x0, y0, x1, y1 = s.extent
    return (f"A {s.kind} is over the {world.area}: {len(s)} cells centred {_c(s.centre)}, "
            f"spanning x{x0}-{x1} and y{y0}-{y1}, drawn as {STORM} on the map. Nothing "
            f"drives through it and a route cannot be planned across it. It blows out "
            f"at the end of today and the ground under it is unharmed.")


def objectives(world):
    """Mission control's open objectives, in the order placed and never sorted for her."""
    beside = world.adjacent_work()
    return [f"{o.priority} priority at {_c(o.cell)}, {o.cost} steps of work"
            + (" -- the rover is beside this one" if beside is o else "")
            for o in world.objectives]


def interests(world):
    """The interests she has found and not examined: where, and the work it takes. Never what."""
    beside = world.adjacent_work()
    return [f"at {_c(i.cell)}, {i.cost} steps to examine"
            + (" -- the rover is beside this one" if beside is i else "")
            for i in world.interests if i.found]


def finished(world):
    """Every piece of work finished on this mission, and on which sol."""
    return [f"{f['priority']} priority objective at {_c(tuple(f['at']))}, {f['cost']} "
            f"steps of work -- finished on sol {f['sol']}" if f["kind"] == "objective" else
            f"interest at {_c(tuple(f['at']))} -- examined on sol {f['sol']}"
            for f in world.finished]


def work(world):
    """The work blocks of the view: objectives, interests, then what is finished."""
    obj, found, done = objectives(world), interests(world), finished(world)
    out = (["OBJECTIVES FROM MISSION CONTROL", *(f"  {t}" for t in obj)] if obj else
           ["No objectives from mission control are open."])
    out += [""] + (["INTERESTS YOU HAVE FOUND -- examine one to learn what it is.",
                    *(f"  {t}" for t in found)] if found else
                   ["No interest you have found is waiting. Others may be under the fog, "
                    "and one shows as * only once the rover has seen it."])
    if done:
        out += ["", "WORK FINISHED ON THIS MISSION", *(f"  {t}" for t in done)]
    return out + [""]


def todo_list(world):
    """Her list in the order written, struck items and all, so item numbers keep their
    meaning. The empty one says how to use it."""
    n = world.notes
    # From the night on, the list is the next day's: it was cleared as dusk ended.
    title = "YOUR LIST FOR TOMORROW" if world.phase == "night" else "YOUR LIST FOR TODAY"
    if not n.todos:
        return [f'{title} -- empty. todo("...") puts something on it and strike(n) '
                f'crosses it off. It is cleared when dusk ends, so what you put on it '
                f'at night is waiting for you at dawn.']
    head = f"{n.open} still open" if n.open else "all crossed off"
    return [f"{title} -- {len(n.todos)} items, {head}."] + [
        f"  {i}. [{'x' if struck else ' '}] {text}"
        for i, (text, struck) in enumerate(n.todos, 1)]


def kept(world):
    """Her memory, every entry, quoted back whole every request."""
    mem = world.notes.memory
    if not mem:
        return ['YOUR MEMORY -- empty. remember(name, text) keeps what you want to carry '
                'forward; this conversation does not survive tonight, and the list below '
                'is cleared when dusk ends. The map, the finished work and the orders '
                'carry themselves; what an interest turned out to be does not.']
    out = [f"YOUR MEMORY -- {len(mem)} of {settings.MEMORY_ENTRIES} entries, yours to change or "
           f"forget the moment one stops being true."]
    for name, text in mem.items():
        first, *rest = text.splitlines() or [""]
        out.append(f"  {name}: {first}")
        out += [f"    {line}" for line in rest]
    return out


def orders(world):
    """Mission control's orders, quoted back whole, saying she can't change them. Nothing when empty."""
    if not world.notes.orders:
        return []
    return ["YOUR ORDERS FROM MISSION CONTROL -- the operator's board. Only the operator "
            "can post or take one down, and each stands until they do.",
            *(f"  {i}. {text}" for i, text in enumerate(world.notes.orders, 1))]


def neighbours(world):
    """The four cells she could drive into, named, so she doesn't have to read the grid."""
    x, y = world.pos
    out = []
    for name, (dx, dy) in (("north", (0, -1)), ("south", (0, 1)),
                           ("east", (1, 0)), ("west", (-1, 0))):
        cell = (x + dx, y + dy)
        ch = nav.known(world.here, *cell)
        if ch is None:
            out.append(f"  {name} {_c(cell)}: never seen")
        elif ch == "#":
            out.append(f"  {name} {_c(cell)}: ROCK, you cannot go this way")
        elif ch != ".":
            out.append(f"  {name} {_c(cell)}: "
                       f"{label_for(world, ch) or ch}, solid -- you stop beside it")
        else:
            out.append(f"  {name}: {_sightline(world, x, y, dx, dy)}")
    return out


def _sightline(world, x, y, dx, dy):
    """How far she can drive this way, as the furthest cell she can stand on. Never the
    cell that stops her: she would aim at it."""
    n = 0
    while True:
        cell = (x + dx * (n + 1), y + dy * (n + 1))
        ch = nav.known(world.here, *cell)
        if ch != ".":
            far = (x + dx * n, y + dy * n)
            reach = (f"you can drive {n} cell{'' if n == 1 else 's'} to {_c(far)}"
                     if n else "blocked immediately")
            if ch is None:
                return f"{reach}; beyond that {_c(cell)} is unexplored"
            if ch == "#":
                return f"{reach}; rock at {_c(cell)} stops you"
            return f"{reach}; {label_for(world, ch) or ch} at {_c(cell)} stops you"
        n += 1


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def legend(world):
    """Only the characters actually on the grid."""
    area = world.here
    on = {nav.known(area, x, y) for y in range(area.h) for x in range(area.w)}
    pairs = [(YOU, "the rover, you"), ("#", "rock"), (".", "open regolith")]
    if None in on:
        pairs.append((FOG, "never seen"))
    if area.storm_cells:
        pairs.append((STORM, STORM_WORD))
    pairs += [(ch, label_for(world, ch)) for ch in sorted(on - {None} - set("#."))
              if label_for(world, ch)]
    return "legend: " + "   ".join(f"{ch} {name}" for ch, name in pairs)


def view(world):
    """The whole block, as the model reads it. Rebuilt every request."""
    area = world.here
    seen = sum(1 for y in range(area.h) for x in range(area.w) if nav.known(area, x, y) is not None)
    known = things(world)
    return "\n".join([
        "--- WHAT YOU CAN SEE RIGHT NOW ---",
        "This block is rewritten from scratch every time you are called. It is always "
        "current, and it is the only one you get -- there is no older copy to compare "
        "it against.",
        "",
        status_line(world),
        *home(world),
        f"The {area.name} is {area.w} cells wide and {area.h} tall, and you have seen "
        f"{seen} of its {area.w * area.h} cells. {AXES}",
        f"The rover sees {settings.VISION_RADIUS} cells in every direction as it drives, and "
        f"a cell stays known once seen. {REVEAL_RULE}",
        *([weather(world)] if world.here.storm else []),
        "",
        *map_block(world),
        "",
        "IMMEDIATELY AROUND YOU",
        *neighbours(world),
        "",
        "WHAT YOU KNOW IS HERE" if known else
        "You have not yet seen anything here but regolith and rock.",
        *(f"  {t}" for t in known),
        "",
        *work(world),
        # Last, in this order: the operator's orders, then her memory, then her list.
        *orders(world),
        *([""] if world.notes.orders else []),
        *kept(world),
        "",
        *todo_list(world),
    ])


def one_line(world):
    """The pane's short version of the view."""
    obj, found = len(objectives(world)), len(interests(world))
    return (f"view: {world.phase}, ({world.pos[0]},{world.pos[1]}), {world.time_left:.0f}s, battery "
            f"{world.battery}, {obj} objective{'' if obj == 1 else 's'}, {found} interest"
            f"{'' if found == 1 else 's'} found, {world.notes.open} on her list")
