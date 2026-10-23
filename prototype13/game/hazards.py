"""Weather. One dust storm a sol, and the sol is how long it lasts.

A class first and one object in it, because the second kind is a matter of filling in
`cells` and a name -- everything downstream reads `Area.storm.cells` and cares about
nothing else. Earthquakes are deferred, not designed out.

**The storm is impassable, not lethal.** Driving into one would end the rover, but
`nav` folds its cells into `avoid`, so a route is planned around it or refused -- which
means the rover can never actually touch one and a respawn penalty would be code that
cannot run. The decision the storm creates is the detour or the wait, and that is the
one worth watching first. If the rover is ever allowed in deliberately, this is where
the damage goes.

It is visible the moment it exists. Forecasting it a few sols ahead would make the
decision temporal -- can I get there and back before it lands -- which is richer and is
not this version.

**Seeded from the arena and the day**, so two runs of the same sol get the same weather
and can be compared. An unseeded storm makes every tape a different world, which is the
thing the measurement rules on this project exist to stop.
"""

import random

import settings as S


class Storm:
    """A blot of cells nothing can drive through, and what to call it."""

    def __init__(self, cells, centre, day, kind="dust storm"):
        self.cells = frozenset(cells)
        self.centre = centre
        self.day = day
        self.kind = kind

    def __contains__(self, cell):
        return cell in self.cells

    def __len__(self):
        return len(self.cells)

    @property
    def extent(self):
        """Bounding box as `(x0, y0, x1, y1)`, both ends included."""
        xs = [c[0] for c in self.cells]
        ys = [c[1] for c in self.cells]
        return min(xs), min(ys), max(xs), max(ys)

    def __repr__(self):
        return f"Storm({self.kind}, {len(self.cells)} cells, centre {self.centre})"


def _disc(cx, cy, r, w, h):
    return {(x, y)
            for y in range(max(0, cy - r), min(h, cy + r + 1))
            for x in range(max(0, cx - r), min(w, cx + r + 1))
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r}


def spawn_for_day(area, day, start, keep_clear=()):
    """The storm for `day`, or None if the weather is off or nowhere will take one.

    `start` is where the rover wakes, and is both the cell the storm may never cover
    and the one connectivity is measured from. It has to be open ground: measuring
    from the pad would measure from inside a wall and quietly accept every placement.

    `keep_clear` is everything the storm must neither sit on nor cut off -- the pad and
    every objective. An objective is solid, so what it needs is one open neighbour the
    rover can still reach; sitting next to it is fair weather, sealing all four sides is
    not.

    Placement is rejected rather than adjusted. A sol whose objective cannot be reached
    is not a harder sol, it is a broken one, and the two are indistinguishable from a
    transcript -- the model reports STORM_BLOCKED either way and nothing says which.
    """
    if not S.STORM_ON:
        return None

    keep = set(keep_clear) | {start}
    rng = random.Random(f"{area.name}:{area.w}x{area.h}:sol{day}")
    before = _reach(area, start, frozenset())
    if not before:
        return None                     # nowhere to drive from anyway

    # Twenty draws, which is far more than enough for a disc of thirteen cells, and a
    # local number rather than a setting because nobody tunes it.
    #
    # `STORM_TRIES` and `STORM_MAX_CUTOFF` used to live in settings and drove a coarser
    # version of this: reject anything sealing off more than a quarter of the arena.
    # Measured over 500 sols on the 30, that rejected nothing at all -- the worst
    # placement left 97.4% reachable -- while sol 1 quietly buried objective 2 and made
    # it STORM_BLOCKED all day. A share of the arena was never the thing worth measuring.
    # What matters is whether the places the rover has to get to are still gettable.
    for _ in range(20):
        cx, cy = rng.randrange(area.w), rng.randrange(area.h)
        cells = _disc(cx, cy, S.STORM_RADIUS, area.w, area.h)
        if not cells or cells & keep:
            continue
        if not _all_approachable(area, start, frozenset(cells), keep_clear):
            continue
        return Storm(cells, (cx, cy), day)
    return None


def _all_approachable(area, start, blocked, targets):
    """Every target still has an open neighbour reachable from `start`.

    Targets are solid -- the pad and the objectives -- so reachability is asked about the
    ring around them rather than the cell itself, which is never reachable at all.
    """
    reach = _reach(area, start, blocked)
    for tx, ty in targets:
        ring = {(tx, ty - 1), (tx, ty + 1), (tx - 1, ty), (tx + 1, ty)}
        if not ring & reach:
            return False
    return True


def _reach(area, start, blocked):
    """Open cells reachable from `start` over the true grid, treating `blocked` as wall.

    The true grid on purpose: this is the environment deciding whether a sol is
    playable, not the rover deciding where to go. It has nothing to do with fog.
    """
    if area.at(*start) in "#H" or start in blocked:
        return set()
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        for n in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if n in seen or n in blocked:
                continue
            if not (0 <= n[0] < area.w and 0 <= n[1] < area.h):
                continue
            if area.at(*n) in "#H":
                continue
            seen.add(n)
            stack.append(n)
    return seen
