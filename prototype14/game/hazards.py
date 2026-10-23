"""Weather: one dust storm a sol, lasting the sol. The rover can't drive through it,
so nav plans around it. Seeded from the arena and the sol, so a replay gets the same storm."""

import random

import settings as S


class Storm:
    """Cells nothing can drive through, and what to call them."""

    def __init__(self, cells, centre, kind="dust storm"):
        self.cells = frozenset(cells)
        self.centre = centre
        self.kind = kind

    def __len__(self):
        return len(self.cells)

    @property
    def extent(self):
        """Bounding box as (x0, y0, x1, y1), both ends included."""
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
    """The storm for `day`, or None. It never covers `start` (where the rover wakes), and
    every cell in `keep_clear` (the pad and the work) keeps an open neighbour the rover can reach."""
    if not S.STORM_ON:
        return None

    keep = set(keep_clear) | {start}
    rng = random.Random(f"{area.name}:{area.w}x{area.h}:sol{day}")
    before = _reach(area, start, frozenset())
    if not before:
        return None  # nowhere to drive from anyway

    for _ in range(20):
        cx, cy = rng.randrange(area.w), rng.randrange(area.h)
        cells = _disc(cx, cy, S.STORM_RADIUS, area.w, area.h)
        if not cells or cells & keep:
            continue
        if not _all_approachable(area, start, frozenset(cells), keep_clear):
            continue
        return Storm(cells, (cx, cy))
    return None


def _all_approachable(area, start, blocked, targets):
    """Every target still has an open neighbour reachable from `start`."""
    reach = _reach(area, start, blocked)
    for tx, ty in targets:
        ring = {(tx, ty - 1), (tx, ty + 1), (tx - 1, ty), (tx + 1, ty)}
        if not ring & reach:
            return False
    return True


def _reach(area, start, blocked):
    """Open cells reachable from `start` on the true grid, treating `blocked` as rock."""
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
