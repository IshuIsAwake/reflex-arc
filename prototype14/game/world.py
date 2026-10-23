"""The world: the arena and its fog, the rover, the day's clock and the battery, and the
work. No pygame here.

Objectives are mission control's, placed on ground the rover has mapped. Interests are
the arena's own, hidden until the rover sees them; examining one says what it is."""

import random

import config
import hazards
import notes
import settings

# Each objective's marker, freed when the work is done.
GLYPHS = "123456789"
INTEREST = "*"
SOLID = set("#H") | set(GLYPHS) | {INTEREST}  # everything the rover can't drive through
THINGS = SOLID - set("#")  # ...and just the things. Rock is not a destination

# Work is solid, so the rover stops beside it rather than driving onto it.

# What a tile is called, on screen and in the view.
LABELS = {"H": "base pad", INTEREST: "point of interest"}


class Objective:
    """Mission control's work: where, its priority, and its cost. `auto` marks one placed by the auto mode."""

    kind = "objective"

    def __init__(self, cell, glyph, priority, cost, auto=False):
        self.cell = cell
        self.glyph = glyph
        self.priority = priority
        self.cost = cost
        self.auto = auto
        self.done = False

    def __repr__(self):
        return (f"Objective({self.cell}, {self.priority}, {self.cost} steps"
                f"{', done' if self.done else ''})")


class Interest:
    """Something the arena hides. `found` once the rover has seen it; `text` is what examining it says."""

    kind = "interest"
    glyph = INTEREST

    def __init__(self, cell, text, cost, found=False):
        self.cell = cell
        self.text = text
        self.cost = cost
        self.found = found
        self.done = False

    def __repr__(self):
        return (f"Interest({self.cell}, {self.cost} steps"
                f"{', found' if self.found else ''}{', done' if self.done else ''})")


def components(w, h, member):
    """The four-connected groups of cells `member(x, y)` accepts, biggest first. Used for
    both rock and fog."""
    seen, out = set(), []
    for sy in range(h):
        for sx in range(w):
            if (sx, sy) in seen or not member(sx, sy):
                continue
            group, stack = set(), [(sx, sy)]
            seen.add((sx, sy))
            while stack:
                x, y = stack.pop()
                group.add((x, y))
                for n in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
                    if (0 <= n[0] < w and 0 <= n[1] < h and n not in seen
                            and member(*n)):
                        seen.add(n)
                        stack.append(n)
            out.append(group)
    out.sort(key=len, reverse=True)
    return out


def centre_of(cells):
    """The cell of `cells` nearest their middle, so the middle of a C-shape is still one of its cells."""
    cx = sum(x for x, _ in cells) / len(cells)
    cy = sum(y for _, y in cells) / len(cells)
    return min(cells, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))


class Survey:
    """Names the rock formations as they come out of the fog. Seen rock only ever grows, so
    a formation keeps its id; when two turn out to be one, the lower id wins and the merge is
    reported. Fog only shrinks and splits, so it gets no ids."""

    def __init__(self):
        self.owner = {}  # cell -> formation id
        self.size = {}  # id -> cells known last time she asked
        self.merges = []  # ids absorbed since the last report, as (gone, kept)
        self._next = 1

    def rock(self, area):
        """Seen rock as (id, cells), with ids assigned and merges recorded."""
        groups = components(area.w, area.h,
                            lambda x, y: (x, y) in area.seen and area.at(x, y) == "#")
        out = []
        for cells in groups:
            known = sorted({self.owner[c] for c in cells if c in self.owner})
            if known:
                # Lowest id wins; the others are reported, since she may have used them.
                fid = known[0]
                for gone in known[1:]:
                    self.merges.append((gone, fid))
                    self.size.pop(gone, None)
            else:
                fid, self._next = self._next, self._next + 1
            for c in cells:
                self.owner[c] = fid
            out.append((fid, cells))
        return out

    def fog(self, area):
        """Unseen regions. No ids."""
        return components(area.w, area.h, lambda x, y: (x, y) not in area.seen)

    def since_last(self, fid, now):
        """Cells revealed since she last asked about formation `fid`; asking updates the count."""
        was = self.size.get(fid)
        self.size[fid] = now
        return None if was is None else now - was

    def take_merges(self):
        out, self.merges = self.merges, []
        return out


def label_for(world, ch):
    """What to call a tile, on screen and in the view. An objective is named by its priority."""
    if ch in GLYPHS:
        o = next((o for o in world.here.objectives.values() if o.glyph == ch), None)
        return f"{o.priority}-priority objective" if o else None
    return LABELS.get(ch)


class Area:
    def __init__(self, name, rows, interests=None):
        self.name = name
        self.rows = [r.replace("@", ".") for r in rows]
        self.w = len(self.rows[0])
        self.h = len(self.rows)
        self.seen = set()
        self.marks = set()
        self.visited = set()  # cells actually driven over, as opposed to merely seen
        # Work lies over the rows rather than in them, so finishing it is a deletion.
        self.objectives = {}
        self.interests = {cell: Interest(cell, text, cost)
                          for cell, (text, cost) in (interests or {}).items()}
        self.storm = None  # today's weather (hazards.py), turned over by next_day

    def at(self, x, y):
        """Ground truth, hidden interests included. What the rover knows is nav.known."""
        if 0 <= x < self.w and 0 <= y < self.h:
            if (x, y) in self.objectives:
                return self.objectives[(x, y)].glyph
            if (x, y) in self.interests:
                return INTEREST
            return self.rows[y][x]
        return "#"

    def work(self):
        """Every unfinished piece of work, objectives first."""
        return list(self.objectives.values()) + list(self.interests.values())

    @property
    def storm_cells(self):
        """Today's storm as a set, empty when the sky is clear."""
        return self.storm.cells if self.storm else frozenset()

    def blocked(self, x, y):
        # The storm sits over the ground rather than being a tile, so `at` still sees the ground.
        if (x, y) in self.storm_cells:
            return True
        return self.at(x, y) in SOLID

    def visible(self, x, y):
        return (x, y) in self.seen

    def reachable(self, start=None):
        """Every cell the rover could drive to from `start` on the true grid, ignoring the storm.
        Used to refuse work the rover could never reach."""
        start = start or config.SPAWN
        seen, edge = {start}, [start]
        while edge:
            x, y = edge.pop()
            for cell in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
                cx, cy = cell
                if (cell in seen or not (0 <= cx < self.w and 0 <= cy < self.h)
                        or self.at(cx, cy) in SOLID):
                    continue
                seen.add(cell)
                edge.append(cell)
        return seen

    def disc(self, px, py, r=None):
        """Every in-bounds cell the rover would see standing at (px, py)."""
        r = settings.VISION_RADIUS if r is None else r
        return {(x, y)
                for y in range(max(0, py - r), min(self.h, py + r + 1))
                for x in range(max(0, px - r), min(self.w, px + r + 1))
                if (x - px) ** 2 + (y - py) ** 2 <= r * r}


    def reveal_all(self):
        """Lift the whole fog. The game never does this; the tests use it."""
        self.seen |= {(x, y) for y in range(self.h) for x in range(self.w)}

    def reveal_cells(self, cells):
        """Open the fog over `cells`. Returns the ones that were new. The only write into `seen`."""
        new = cells - self.seen
        self.seen |= new
        return new

    def reveal(self, px, py, r=None):
        """Open a disc of fog around a cell. Returns what was new."""
        return self.reveal_cells(self.disc(px, py, r))


class World:
    """One expedition. Days roll over; the arena and everything learned carry on.
    `recorder` writes the game log (logs.py); it is None in tests, so this file does no I/O."""

    def __init__(self, recorder=None, carried=None):
        """`carried` is a carry() from an earlier run: the world wakes on the sol after it."""
        self.here = Area(config.ARENA_NAME, config.ARENA, config.INTERESTS)
        self.pos = config.SPAWN
        self.day = 1
        # dawn, day, dusk or night. autopilot moves it on
        self.phase = "dawn"
        self.day_over = False
        self.time_left = float(settings.DAY_SECONDS)  # the day's wall clock, run by autopilot
        self.battery = settings.BATTERY  # in steps. Only the pad recharges it
        self.steps = 0  # taken today, for the record
        self.elapsed = 0.0  # stopwatch
        self.history = []  # one record per finished day
        self.nav_log = []  # one record per goto or distance: planned against driven
        # The last goto, for the map: what it planned and what it actually covered.
        self.last_path = ("", [])
        self.last_walk = ("", [])
        # The leg the real rover is driving right now, as directions, or None. For the screen.
        self.awaiting_rover = None
        self.log = []
        self.recorder = recorder
        self.revealed = set()  # what the last move opened up, for the playback
        self.reel = []  # finished drives waiting to be drawn (anim.py)
        self.survey = Survey()  # formation ids, kept for the whole expedition
        # Every piece of work finished, with its sol. Finished work leaves the map, so this is
        # how she and the report still know it happened.
        self.finished = []
        # Interests the rover came within sight of on the latest call, for its result.
        self.just_found = []
        # Her own words at each dusk, for the report: [{"sol", "text"}].
        self.reports = []
        # Her list, her memory and the orders (notes.py).
        self.notes = notes.Notes()
        # Whether last night caught the rover away from the pad: no recharge, and it wakes where it stopped.
        self.stranded = False
        if carried:
            self._restore(carried)
            self._morning()
            return
        self._weather()
        # The landing site is visible on arrival.
        self.here.reveal(*self.pos, r=settings.BASE_REVEAL)
        self._arrive()
        self.record("day_open", at=self.pos, battery=self.battery, clock=self.time_left)

    @property
    def area(self):
        return self.here.name

    @property
    def pad(self):
        """Every pad cell."""
        area = self.here
        return {(x, y) for y in range(area.h) for x in range(area.w) if area.at(x, y) == "H"}

    @property
    def docked(self):
        """Beside any side of any pad cell, which is where it recharges overnight."""
        x, y = self.pos
        return bool({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} & self.pad)

    @property
    def base(self):
        """Where the pad is, read off the map."""
        area = self.here
        cells = [(x, y) for y in range(area.h) for x in range(area.w) if area.at(x, y) == "H"]
        return min(cells) if cells else config.SPAWN

    def record(self, kind, **fields):
        """One line of the game log, if anything is listening."""
        if self.recorder:
            self.recorder(kind, day=self.day, **fields)

    def _arrive(self):
        """Arriving at a cell opens the fog out to VISION_RADIUS. `revealed` holds just this
        move's cells; `visited` is where the rover has actually stood."""
        self.revealed = self.here.reveal(*self.pos)
        self.here.visited.add(self.pos)
        # An interest is found by sight: one placed on ground already mapped stays hidden until the rover comes back near it.
        sight = self.here.disc(*self.pos)
        for i in self.here.interests.values():
            if not i.found and i.cell in sight:
                i.found = True
                self.just_found.append(i.cell)
                self.record("interest_found", at=i.cell)

    def play(self, timeline):
        """Hand a finished drive to the screen, if anything is drawing. Capped, since a headless run draws nothing."""
        if not settings.ANIMATE or not timeline:
            return
        self.reel.append(timeline)
        del self.reel[:-settings.REEL_MAX]

    def say(self, msg, tone="plain"):
        self.log.append((msg, tone))
        del self.log[:-6]
        self.record("say", text=msg, tone=tone)

    def tick(self, dt):
        """The stopwatch, every frame. The day's clock is run_clock's."""
        self.elapsed += dt * settings.TIME_SCALE

    def run_clock(self, dt):
        """The day's wall clock, run down by autopilot while the day is on. Rounded so the tape and the world agree."""
        if dt <= 0 or self.day_over:
            return
        self.time_left = max(0.0, round(self.time_left - dt * settings.TIME_SCALE, 3))
        if self.time_left <= 0:
            self.day_over = True

    def spend(self, n=1):
        """`n` steps of driving or work. A flat battery ends the day."""
        self.steps += n
        self.drain(n)

    def drain(self, n):
        """Battery spent on something that is not a step: a radio message."""
        self.battery = max(0, self.battery - n)
        if self.battery <= 0:
            self.day_over = True

    def set_clock(self, seconds):
        """Replay sets the clock as the tape says it stood. It can end the sol but never reopen one."""
        self.time_left = seconds
        if seconds <= 0:
            self.day_over = True

    @property
    def lost(self):
        """Away from the pad with less charge than the shortest possible trip back (fog counted
        as clear, the storm left out), so the rover can never get home."""
        if self.docked:
            return False
        import nav  # nav imports world, so this import waits until it is needed
        back = nav.home_steps(self, storm=False)
        return back is None or self.battery < back

    def evening(self):
        """Dusk is over: today's list goes. autopilot calls it as the night begins."""
        self.notes.clear_list()

    def next_day(self):
        """The night: the map carries over and the message log doesn't. Beside the pad, the
        battery recharges and the rover wakes there; anywhere else it is stranded."""
        if self.phase != "night":
            self.evening()
        self.history.append(self._sol_record())
        self.stranded = not self.docked
        self.record("day_close", steps=self.steps, seconds=round(self.elapsed, 1),
                    at=self.pos, stranded=self.stranded, battery=self.battery,
                    clock=self.time_left)
        self.day += 1
        self._morning()

    def _morning(self):
        """Everything the night resets. Shared with a resumed expedition, so the two wake the same."""
        self.phase = "dawn"
        self.day_over = False
        self.time_left = float(settings.DAY_SECONDS)
        self.steps = 0
        self.elapsed = 0.0
        self.log.clear()
        self.last_path = ("", [])
        self.last_walk = ("", [])
        self.reel.clear()  # nobody wants to watch yesterday's drive
        if not self.stranded:
            self.pos = config.SPAWN  # woken at the pad
            self.battery = settings.BATTERY
        self._weather()  # yesterday's storm has blown out; today gets its own
        self._arrive()
        self.record("day_open", at=self.pos, battery=self.battery,
                    clock=self.time_left, stranded=self.stranded)

    def _sol_record(self):
        """How a sol ended, for `history` and the report."""
        return {"day": self.day, "steps": self.steps, "seconds": round(self.elapsed, 1),
                "at": list(self.pos), "docked": self.docked, "battery": self.battery}

    def carry(self):
        """What the night keeps, as JSON, so a new session can wake on the next sol. Quitting
        mid-sol counts the sol as played."""
        area, sv = self.here, self.survey
        cells = lambda cs: sorted([x, y] for x, y in cs)
        return {"version": 2, "arena": str(area.w), "day": self.day,
                "seen": cells(area.seen), "visited": cells(area.visited), "marks": cells(area.marks),
                "objectives": [[*o.cell, o.glyph, o.priority, o.cost, o.auto]
                               for o in area.objectives.values()],
                "interests": [[*i.cell, i.text, i.cost, i.found]
                              for i in area.interests.values()],
                "reports": self.reports,
                "survey": {"owner": sorted([x, y, f] for (x, y), f in sv.owner.items()),
                           "size": sorted([f, n] for f, n in sv.size.items()),
                           "merges": [list(m) for m in sv.merges], "next": sv._next},
                "memory": [[k, v] for k, v in self.notes.memory.items()],
                "orders": list(self.notes.orders),
                "todos": ([[t, struck] for t, struck in self.notes.todos]
                          if self.phase == "night" else []),
                "pos": list(self.pos), "stranded": not self.docked,
                "battery": self.battery, "finished": self.finished,
                "history": self.history + [self._sol_record()]}

    def _restore(self, c):
        """The inverse of carry(): the world at the night after `c["day"]`."""
        area, sv = self.here, self.survey
        if c.get("version") != 2:
            raise ValueError("saved by an earlier prototype, whose work was all objectives")
        if c.get("arena") != str(area.w):
            raise ValueError(f"saved on the {c.get('arena')}, and the {area.w} is loaded")
        area.seen = {tuple(p) for p in c["seen"]}
        area.visited = {tuple(p) for p in c["visited"]}
        area.marks = {tuple(p) for p in c["marks"]}
        area.objectives = {(x, y): Objective((x, y), g, pr, cost, auto)
                        for x, y, g, pr, cost, auto in c["objectives"]}
        area.interests = {(x, y): Interest((x, y), text, cost, found)
                       for x, y, text, cost, found in c["interests"]}
        self.reports = list(c["reports"])
        sv.owner = {(x, y): f for x, y, f in c["survey"]["owner"]}
        sv.size = {f: n for f, n in c["survey"]["size"]}
        sv.merges = [tuple(m) for m in c["survey"]["merges"]]
        sv._next = c["survey"]["next"]
        self.notes.load(c["memory"], c["orders"], c.get("todos", ()))
        self.pos = tuple(c["pos"])
        self.stranded = c["stranded"]
        self.battery = c["battery"]
        self.finished = list(c["finished"])
        self.history = list(c["history"])
        self.day = c["day"] + 1

    def _weather(self):
        """Today's storm, never over the pad, the rover or any work, and never cutting off the work."""
        self.here.storm = hazards.spawn_for_day(
            self.here, self.day, self.pos,
            keep_clear=(self.base, *self.here.objectives, *self.here.interests))
        if self.here.storm:
            s = self.here.storm
            self.record("storm", weather=s.kind, at=s.centre, cells=len(s),
                        extent=s.extent)

    @property
    def objectives(self):
        """Every unfinished objective, in the order placed."""
        return list(self.here.objectives.values())

    @property
    def interests(self):
        """Every unexamined interest, found or not."""
        return list(self.here.interests.values())

    def _placeable(self, cell, what):
        """Why `cell` can't take a piece of work, or None. Work is done from a neighbour, so at
        least one of its four neighbours must be reachable on the true grid."""
        area = self.here
        x, y = cell
        if not (0 <= x < area.w and 0 <= y < area.h):
            return f"({x},{y}) is off the {area.name}, which is {area.w} by {area.h}."
        if cell in area.objectives or cell in area.interests:
            return f"({x},{y}) already carries work."
        if area.at(x, y) == "H":
            return f"({x},{y}) is the base pad."
        if area.at(x, y) == "#":
            return (f"({x},{y}) is rock. {what} sits on drivable ground -- the rover "
                    f"stops beside it, not on it.")
        if cell == self.pos:
            return f"({x},{y}) is where the rover is standing."
        if cell in area.storm_cells:
            return f"({x},{y}) is under today's dust storm."
        reach = area.reachable()
        if not any(c in reach for c in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y))):
            return (f"({x},{y}) has no approach the rover can reach -- every cell beside "
                    f"it is rock, off the arena, or walled off.")
        return None

    def place_objective(self, cell, priority, cost, auto=False):
        """Mission control puts work on mapped ground. Returns (Objective, None) or (None, why)."""
        why = self._placeable(cell, "An objective")
        if why:
            return None, why
        if not self.here.visible(*cell):
            return None, (f"({cell[0]},{cell[1]}) is still under the fog. Objectives go "
                          f"on ground the rover has mapped.")
        free = [g for g in GLYPHS if not any(o.glyph == g for o in self.objectives)]
        if not free:
            return None, f"all {len(GLYPHS)} objective markers are in use."
        o = Objective(cell, free[0], priority, cost, auto)
        self.here.objectives[cell] = o
        self.record("placed", at=cell, glyph=o.glyph, priority=priority, cost=cost,
                    auto=auto)
        return o, None

    def place_interest(self, cell, text, cost):
        """Hide an interest anywhere drivable. Returns (Interest, None) or (None, why)."""
        why = self._placeable(cell, "An interest")
        if why:
            return None, why
        i = Interest(cell, text, cost)
        self.here.interests[cell] = i
        self.record("placed_interest", at=cell, text=text, cost=cost)
        return i, None

    def auto_objectives(self):
        """The auto mode's dawn: three objectives, one of each priority, from sol 2, and a new set
        only once the last is done. On mapped open ground, away from the pad, the rover and other
        work. Seeded by arena and sol. Returns what it placed."""
        if settings.OBJECTIVES != "auto" or self.day < 2 or any(o.auto for o in self.objectives):
            return []
        area = self.here
        rng = random.Random(f"{area.name}:{area.w}x{area.h}:objectives:sol{self.day}")
        near = lambda c, d, r: abs(c[0] - d[0]) <= r and abs(c[1] - d[1]) <= r
        taken = set(area.objectives) | set(area.interests)
        cells = [c for c in sorted(area.seen) if area.at(*c) == "."
                 and not any(near(c, p, 2) for p in self.pad) and not near(c, self.pos, 2)
                 and not any(near(c, t, 1) for t in taken)]
        rng.shuffle(cells)
        placed = []
        for priority in ("high", "medium", "low"):
            for c in cells:
                if any(near(c, o.cell, 1) for o in placed):
                    continue
                o, _ = self.place_objective(c, priority,
                                            rng.randrange(settings.OBJECTIVE_COST[0],
                                                          settings.OBJECTIVE_COST[1] + 1, 5),
                                            auto=True)
                if o:
                    placed.append(o)
                    break
        return placed

    def adjacent_work(self):
        """The unfinished work the rover is beside (N/E/S/W), if any: an objective, or a found interest."""
        x, y = self.pos
        for cell in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            o = self.here.objectives.get(cell)
            if o and not o.done:
                return o
            i = self.here.interests.get(cell)
            if i and i.found and not i.done:
                return i
        return None

    def execute(self, o):
        """Do the work at `o`, charging its cost first, so a battery that runs out mid-task still
        pays. Returns the steps spent."""
        spent = min(o.cost, self.battery)
        self.spend(spent)
        self.play([("work", (o.cell, spent))])
        if spent < o.cost:
            return spent  # ran out of battery; the work isn't finished
        o.done = True
        area = self.here
        del (area.objectives if o.kind == "objective" else area.interests)[o.cell]
        what = ({"priority": o.priority} if o.kind == "objective" else {"text": o.text})
        self.finished.append({"sol": self.day, "at": list(o.cell), "kind": o.kind,
                              "cost": o.cost, **what})
        # No `day=` here: record() adds it.
        self.record(o.kind, at=o.cell, cost=o.cost, **what)
        return spent

    def move(self, dx, dy):
        x, y = self.pos[0] + dx, self.pos[1] + dy
        if self.here.blocked(x, y) or self.battery <= 0:
            return
        self.pos = (x, y)
        self._arrive()
        self.spend()  # only a move that happened costs anything

    def toggle_mark(self, cell=None):
        area = self.here
        cell = cell or self.pos
        if cell in area.marks:
            area.marks.discard(cell)
            self.say(f"Mark cleared at {cell}.")
        else:
            area.marks.add(cell)
            self.say(f"Marked {cell} with an X.")
