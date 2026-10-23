"""World state. No pygame in here -- this is the part the planner drives.

An arena, fog, a rover, a day on a clock and a battery. Result strings are the failure codes
prototype 1 arrived at, and the human sees the same strings the model does.

Two kinds of work. **Objectives** are mission control's: placed on ground the rover has
mapped, so she sees each one the moment it exists, with a priority and a cost. **Interests**
are the arena's: nobody knows where they are, and one shows on her map only once the rover
has seen it since it was placed. Examining one is what says what it is.
"""

import random

import config as C
import hazards
import notes
import settings as S

# The objectives' markers, one each, freed when the work is done.
GLYPHS = "123456789"
INTEREST = "*"
SOLID = set("#H") | set(GLYPHS) | {INTEREST}   # everything you cannot drive through
THINGS = SOLID - set("#")   # ...and just the things. A rock is not a destination

# Work is solid so that `nav._targets` puts the rover *beside* it rather than on top of
# it -- which is what working alongside an instrument means, and which the base pad
# already got for free. Making it drivable would complete it by running it over.

# What each tile is called out loud. Lives here rather than in render.py because the
# renderer imports pygame and the model loop cannot: gemma reads these same words.
# One wording for the screen and the view, the way Result.__str__ is one wording for
# the console and the model.
# No commas in a label: `sight.rle` joins a row's runs with ", ", so one here splits a
# single run into two and the map quietly stops parsing.
LABELS = {"H": "base pad", INTEREST: "point of interest"}


class Objective:
    """Mission control's work: where it is, its priority and what it costs to do.

    `priority` and `cost` are both facts the mission hands over. Which to do first is
    not one of them. `auto` marks one the auto mode placed, so it knows when a set is done.
    """

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
    """Something the arena hides. `found` once the rover has seen its cell since it was
    placed; `text` is what examining it turns up, and nothing shows it before then."""

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
    """The connected groups of cells `member(x, y)` accepts. Four-connected.

    One flood fill, two questions: which rock cells hang together, and -- with a
    different predicate -- which unexplored ones do. `fog()` is the second caller.
    Writing it twice is how the two answers drift apart.

    Returns a list of sets, biggest first.

    Four-connected on purpose: eight would join boulders that merely touch at a corner,
    and the rover drives in four directions.
    """
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
    """The member cell nearest the middle of `cells`.

    The *middle* of a concave formation is often not in it -- the C on the 50x50 has
    its centroid sitting in open ground inside the bay. A centre that is not a member
    is a coordinate `count_cells` cannot look anything up by, so it is snapped onto the
    nearest cell that is one. Ties break north then west, so the same set always names
    the same cell.
    """
    cx = sum(x for x, _ in cells) / len(cells)
    cy = sum(y for _, y in cells) / len(cells)
    return min(cells, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cy) ** 2, c[1], c[0]))


class Survey:
    """Names the rock formations as they come out of the fog, and remembers the names.

    Only revealed cells count. A formation half in fog is reported at the size she has
    actually seen, and the fogged half reads as fog -- a number that silently meant
    "or more" would be the lying success code again, in a field.

    **Rock ids are stable because revealed rock only ever grows.** A cell never stops
    being rock, so a formation can gain cells and two formations can turn out to be one,
    but nothing ever splits. That makes an id worth carrying: the only event to report
    is a merge, and the lowest id survives it.

    Fog gets no ids, and this is not an oversight. Fog does the opposite -- it only ever
    shrinks, and one region becomes three as she drives through the middle of it. There
    is no persistent thing there to name.
    """

    def __init__(self):
        self.owner = {}      # cell -> formation id
        self.size = {}       # id -> cells known last time she asked
        self.merges = []     # ids absorbed since the last report, as (gone, kept)
        self._next = 1

    def rock(self, area):
        """Revealed rock, as `(id, cells)`, ids assigned and merges recorded."""
        groups = components(area.w, area.h,
                            lambda x, y: (x, y) in area.seen and area.at(x, y) == "#")
        out = []
        for cells in groups:
            known = sorted({self.owner[c] for c in cells if c in self.owner})
            if known:
                # Lowest wins. She may have referred to any of the others, so the ones
                # that lose are reported rather than left to vanish mid-conversation.
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
        """Unrevealed regions. No ids, for the reason in the class docstring."""
        return components(area.w, area.h, lambda x, y: (x, y) not in area.seen)

    def since_last(self, fid, now):
        """Cells revealed since she last asked, and the count is updated by asking."""
        was = self.size.get(fid)
        self.size[fid] = now
        return None if was is None else now - was

    def take_merges(self):
        out, self.merges = self.merges, []
        return out


def label_for(w, ch):
    """What to call a tile, out loud, on screen and in the view.

    An objective is named from the priority it actually carries rather than from a
    table keyed by glyph. The operator places objectives now, so the glyph no longer
    implies the priority -- `4` is whatever she said it was -- and a table would have
    to be rewritten every time she placed one.

    This is the one place a name is decided. `prototype1` used it to make terminal
    names something you had to walk up to and earn, and `interact` brings that back.
    """
    if ch in GLYPHS:
        o = next((o for o in w.here.objectives.values() if o.glyph == ch), None)
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
        self.visited = set()   # cells actually driven over, as opposed to merely seen
        # Laid over the rows rather than written into them, so the map stays one thing
        # and finishing a piece of work is a deletion rather than an edit to the terrain.
        self.objectives = {}
        self.interests = {cell: Interest(cell, text, cost)
                          for cell, (text, cost) in (interests or {}).items()}
        self.storm = None       # today's weather. `hazards.py` makes it, `next_day` turns it over

    def at(self, x, y):
        """Ground truth, hidden interests included. What the rover knows is `nav.known`."""
        if 0 <= x < self.w and 0 <= y < self.h:
            if (x, y) in self.objectives:
                return self.objectives[(x, y)].glyph
            if (x, y) in self.interests:
                return INTEREST
            return self.rows[y][x]
        return "#"

    def work(self):
        """Every unfinished piece of work on the arena, objectives first."""
        return list(self.objectives.values()) + list(self.interests.values())

    @property
    def storm_cells(self):
        """Today's storm as a set, empty when the sky is clear. One read, so nothing
        downstream has to keep checking whether there is weather at all."""
        return self.storm.cells if self.storm else frozenset()

    def blocked(self, x, y):
        # The storm is not a tile -- it sits over one. Kept out of `at` so that the
        # grid, `Survey` and the flood-fill go on seeing the ground underneath it.
        if (x, y) in self.storm_cells:
            return True
        return self.at(x, y) in SOLID

    def visible(self, x, y):
        return (x, y) in self.seen

    def reachable(self, start=None):
        """Every cell the rover could drive to from `start`, over the true grid.

        Ground truth on purpose, and the storm deliberately not consulted: this answers
        whether the arena permits a journey, not whether today does. `nav` is the one
        that plans over fog and weather. Used by `place_objective` and `place_interest`
        to refuse work the rover could never reach.
        """
        start = start or C.SPAWN
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
        """Every in-bounds cell the rover would see standing at (px, py).

        Split out of `reveal` so it can be asked hypothetically. `distance` walks a
        planned route and unions one of these per cell to say how much map the trip
        might buy, which it cannot do by driving it.
        """
        r = S.VISION_RADIUS if r is None else r
        return {(x, y)
                for y in range(max(0, py - r), min(self.h, py + r + 1))
                for x in range(max(0, px - r), min(self.w, px + r + 1))
                if (x - px) ** 2 + (y - py) ** 2 <= r * r}


    def reveal_all(self):
        """Lift the whole fog. Never used by the game, where driving and contact with
        rock open the map a disc at a time. This is for `plan_txt --survey`, where
        seeing everything is the deliberate point rather than a bug."""
        self.seen |= {(x, y) for y in range(self.h) for x in range(self.w)}

    def reveal_cells(self, cells):
        """Open the fog over a set of cells. Returns the ones that were new.

        The one write into `seen` in the whole codebase. Everything the model is shown
        reads back through `visible` -> `seen`, so a capability that reveals ground is
        a call to this and nothing else. A second writer is how the fog quietly stops
        meaning one thing.
        """
        new = cells - self.seen
        self.seen |= new
        return new

    def reveal(self, px, py, r=None):
        """Open a disc of fog around a cell. Returns what was new.

        Driving is the main caller -- `World._arrive` opens `VISION_RADIUS` around every
        cell the rover reaches -- alongside the landing site and `plan_txt --survey`.
        """
        return self.reveal_cells(self.disc(px, py, r))


class World:
    """One expedition. Days roll over; the arena and everything learned carry on.

    `recorder` is how the run gets written down without putting a file handle in
    here. `logs.py` sets it; it is None everywhere else, including every test, so
    this file still does no I/O.
    """

    def __init__(self, recorder=None, carried=None):
        """`carried` is a `carry()` from an earlier run: the expedition wakes on the sol
        after it, exactly as `next_day` would have woken it."""
        self.here = Area(C.ARENA_NAME, C.ARENA, C.INTERESTS)
        self.pos = C.SPAWN
        self.day = 1
        # dawn, day, dusk or night. `autopilot` moves it on; the view and the screen read it.
        self.phase = "dawn"
        self.day_over = False
        self.time_left = float(S.DAY_SECONDS)   # the day's wall clock, run by `autopilot`
        self.battery = S.BATTERY                # in steps. Only the pad recharges it
        self.steps = 0          # taken today, for the record. The battery is what binds
        self.elapsed = 0.0      # stopwatch. Runs in both modes and is shown in both,
                                # because it is the measurement the clock needs
        self.history = []       # one record per finished day
        self.nav_log = []       # one record per goto/distance -- planned vs walked
        # The last goto, for the map view: what it planned and what it actually
        # covered. Written together, always. The plan is replaced on every replan
        # and the walk is not, so a drawing that mixed two calls would explain
        # neither -- which is the confusion these two exist to end.
        self.last_path = ("", [])
        self.last_walk = ("", [])
        # The leg the robot is out driving right now, as directions, or None. Only the
        # operator-stands-in-for-the-rover pause sets it, and only so the HUD can say
        # what the machine on the floor is supposed to be doing.
        self.awaiting_rover = None
        self.log = []
        self.recorder = recorder
        self.revealed = set()   # what the last move opened up, for the playback
        self.reel = []          # finished drives waiting to be drawn. See anim.py
        self.survey = Survey()  # formation ids, carried across the whole expedition
        # Every piece of work finished on this expedition, with the sol it was done on. It
        # leaves the map when it is done, so without this nothing she can see says the work
        # happened -- which is how two reports came to say no objective was ever found.
        # An interest's text is kept here for the report, and never shown to her.
        self.finished = []
        # Interests the rover came within sight of on the latest call, for its result.
        self.just_found = []
        # Her own words at each dusk, for the report: [{"sol", "text"}].
        self.reports = []
        # Her own writing. The list dies at nightfall and the memory does not, which is
        # the only difference between the two stores; `notes.py` says why.
        self.notes = notes.Notes()
        # Whether last night caught the rover away from the pad. Stranded means no
        # recharge: it wakes where it stopped, on what was left. See `next_day`.
        self.stranded = False
        if carried:
            self._restore(carried)
            self._morning()
            return
        self._weather()
        # The landing site is visible on arrival. You can see where you came down.
        self.here.reveal(*self.pos, r=S.BASE_REVEAL)
        self._arrive()
        self.record("day_open", at=self.pos, battery=self.battery, clock=self.time_left)

    @property
    def area(self):
        """One arena, so this is a constant -- but nav, sight and the logs all name
        the place they are talking about, and item 3 puts weather on top of it."""
        return self.here.name

    @property
    def pad(self):
        """Every pad cell. Solid, so the rover is home when it is beside one."""
        a = self.here
        return {(x, y) for y in range(a.h) for x in range(a.w) if a.at(x, y) == "H"}

    @property
    def docked(self):
        """Beside the pad, which is where it recharges overnight. Any side of any pad
        cell: `goto` at the pad stops beside whichever cell the route reaches first, and
        a rule stricter than where `goto` parks would strand a rover that did go home."""
        x, y = self.pos
        return bool({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} & self.pad)

    @property
    def base(self):
        """Where the pad is. Read off the map rather than written down twice, so
        moving the pad in config.py cannot leave a stale coordinate behind."""
        a = self.here
        cells = [(x, y) for y in range(a.h) for x in range(a.w) if a.at(x, y) == "H"]
        return min(cells) if cells else C.SPAWN

    def record(self, kind, **fields):
        """One line of the game log, if anything is listening."""
        if self.recorder:
            self.recorder(kind, day=self.day, **fields)

    def _arrive(self):
        """Arriving opens fog again, out to `VISION_RADIUS`.

        Prototype 8 blinded the rover on the grounds that Ingenuity was the only eye
        worth having. Take the flyer away from that and nothing can see at all, and the
        geology question -- which formation is largest -- stops being answerable by
        driving, which is the only way it was ever meant to be answered.

        `revealed` holds this move's worth and is replaced on the next, so a watcher
        redrawing per step gets the cells that just opened rather than all of them.
        `visited` is tracked separately: `avoid="auto"` is legal only for ground the
        rover has actually stood on, which is a smaller set than what it has seen.
        """
        self.revealed = self.here.reveal(*self.pos)
        self.here.visited.add(self.pos)
        # An interest is found by sight, not by fog lifting: one placed on ground already
        # mapped is still hidden until the rover comes back within sight of it.
        sight = self.here.disc(*self.pos)
        for i in self.here.interests.values():
            if not i.found and i.cell in sight:
                i.found = True
                self.just_found.append(i.cell)
                self.record("interest_found", at=i.cell)

    def play(self, timeline):
        """Hand a finished drive to whatever is drawing, if anything is.

        Pure data -- a list of (kind, payload) -- so `world.py` still knows nothing
        about pygame or about time. Capped, because a headless run has no player and
        this would otherwise be a list that only grows.
        """
        if not S.ANIMATE or not timeline:
            return
        self.reel.append(timeline)
        del self.reel[:-S.REEL_MAX]

    def say(self, msg, tone="plain"):
        self.log.append((msg, tone))
        del self.log[:-6]
        self.record("say", text=msg, tone=tone)

    # --- time ------------------------------------------------------------
    def tick(self, dt):
        """The stopwatch, every frame. The day's clock is `run_clock`'s."""
        self.elapsed += dt * S.TIME_SCALE

    def run_clock(self, dt):
        """The day's wall clock, run down by `autopilot` while the day is on and by
        nothing else. Rounded to the millisecond so the value on the tape is the value
        the world held."""
        if dt <= 0 or self.day_over:
            return
        self.time_left = max(0.0, round(self.time_left - dt * S.TIME_SCALE, 3))
        if self.time_left <= 0:
            self.day_over = True

    def spend(self, n=1):
        """`n` steps of driving or work, off the battery. A flat battery ends the day:
        nothing could drive or work again before the pad recharges it."""
        self.steps += n
        self.drain(n)

    def drain(self, n):
        """Battery spent on something that is not a step: a radio message."""
        self.battery = max(0, self.battery - n)
        if self.battery <= 0:
            self.day_over = True

    def set_clock(self, seconds):
        """Replay's door: the clock as the tape says it stood. It can end the sol and
        never reopen one -- a sol the clock in the live run had not closed may have been
        closed by her `end`, and that is the tape's to say, not the clock's."""
        self.time_left = seconds
        if seconds <= 0:
            self.day_over = True

    @property
    def lost(self):
        """Away from the pad with less charge than the shortest trip back could take.

        Not "flat": the first unattended run to strand with 2 charge 23 steps out sat
        there sensibly spending nothing, and with `lost` meaning a battery at nought the
        mission never ended -- sixteen empty sols and counting. The trip is a floor (fog
        counted as clear, the storm left out because it blows out), so short of it no
        route will ever get the rover home, and nothing but the pad recharges it.
        """
        if self.docked:
            return False
        import nav      # nav imports world; by the time anyone asks, both are loaded
        back = nav.home_steps(self, storm=False)
        return back is None or self.battery < back

    def next_day(self):
        """The night. Everything it has mapped carries over; the message log does not
        -- yesterday's messages are noise once the day is shut.

        Her list goes with them and `notes.memory` does not. That one line is what the
        write path is for: the conversation, the reasoning and the day's plan are all
        gone by morning, so the doc is the only thing she can hand herself.

        **Where the night finds the rover decides the morning.** Beside the pad, the
        battery recharges and it wakes there full. Anywhere else it is stranded: no
        recharge, so it wakes where it stopped on whatever charge it had left, and if
        that is none it is `lost`. That is item 2 -- the journey home was always free,
        and now not making it costs something.
        """
        self.history.append(self._sol_record())
        self.stranded = not self.docked
        self.record("day_close", steps=self.steps, seconds=round(self.elapsed, 1),
                    at=self.pos, stranded=self.stranded, battery=self.battery,
                    clock=self.time_left)
        self.day += 1
        self._morning()

    def _morning(self):
        """Everything the night resets. Shared by `next_day` and a resumed expedition,
        so the two cannot wake differently."""
        self.phase = "dawn"
        self.day_over = False
        self.time_left = float(S.DAY_SECONDS)
        self.steps = 0
        self.elapsed = 0.0
        self.log.clear()
        self.notes.new_day()
        self.last_path = ("", [])
        self.last_walk = ("", [])
        self.reel.clear()       # nobody wants to watch yesterday's drive
        if not self.stranded:
            self.pos = C.SPAWN  # woken at the pad
            self.battery = S.BATTERY
        self._weather()         # yesterday's storm has blown out; today gets its own
        self._arrive()
        self.record("day_open", at=self.pos, battery=self.battery,
                    clock=self.time_left, stranded=self.stranded)

    def _sol_record(self):
        """How a sol ended, for `history` and so for the report: the facts of it, kept
        by the world rather than left to anyone's account of them."""
        return {"day": self.day, "steps": self.steps, "seconds": round(self.elapsed, 1),
                "at": list(self.pos), "docked": self.docked, "battery": self.battery}

    # --- across sessions -------------------------------------------------
    def carry(self):
        """What the night keeps, as JSON: enough to wake on the next sol in a new session.

        Quitting mid-sol counts the sol as played, and where the rover stands is where
        the night finds it, so quitting away from the pad strands it. The list, the
        storm and the step count are not here because the morning resets all three. The
        battery is, because a stranded morning does not.
        """
        a, sv = self.here, self.survey
        cells = lambda cs: sorted([x, y] for x, y in cs)
        return {"version": 2, "arena": str(a.w), "day": self.day,
                "seen": cells(a.seen), "visited": cells(a.visited), "marks": cells(a.marks),
                "objectives": [[*o.cell, o.glyph, o.priority, o.cost, o.auto]
                               for o in a.objectives.values()],
                "interests": [[*i.cell, i.text, i.cost, i.found]
                              for i in a.interests.values()],
                "reports": self.reports,
                "survey": {"owner": sorted([x, y, f] for (x, y), f in sv.owner.items()),
                           "size": sorted([f, n] for f, n in sv.size.items()),
                           "merges": [list(m) for m in sv.merges], "next": sv._next},
                "memory": [[k, v] for k, v in self.notes.memory.items()],
                "orders": list(self.notes.orders),
                "pos": list(self.pos), "stranded": not self.docked,
                "battery": self.battery, "finished": self.finished,
                "history": self.history + [self._sol_record()]}

    def _restore(self, c):
        """The inverse of `carry`, leaving the world at the night after `c["day"]`."""
        a, sv = self.here, self.survey
        if c.get("version") != 2:
            raise ValueError("saved by an earlier prototype, whose work was all objectives")
        if c.get("arena") != str(a.w):
            raise ValueError(f"saved on the {c.get('arena')}, and the {a.w} is loaded")
        a.seen = {tuple(p) for p in c["seen"]}
        a.visited = {tuple(p) for p in c["visited"]}
        a.marks = {tuple(p) for p in c["marks"]}
        a.objectives = {(x, y): Objective((x, y), g, pr, cost, auto)
                        for x, y, g, pr, cost, auto in c["objectives"]}
        a.interests = {(x, y): Interest((x, y), text, cost, found)
                       for x, y, text, cost, found in c["interests"]}
        self.reports = list(c["reports"])
        sv.owner = {(x, y): f for x, y, f in c["survey"]["owner"]}
        sv.size = {f: n for f, n in c["survey"]["size"]}
        sv.merges = [tuple(m) for m in c["survey"]["merges"]]
        sv._next = c["survey"]["next"]
        self.notes.load(c["memory"], c["orders"])
        # Older nights have neither: those rovers all woke at the pad.
        self.pos = tuple(c.get("pos") or C.SPAWN)
        self.stranded = bool(c.get("stranded", False))
        # Older nights have no battery: those rovers woke on a full sol, charged or not.
        self.battery = int(c.get("battery", S.BATTERY))
        self.finished = list(c.get("finished", []))
        self.history = list(c["history"])
        self.day = c["day"] + 1

    def _weather(self):
        """Today's storm. One a sol, lasting the sol, and never over the pad, the landing
        site or any work -- a storm the rover wakes up inside is not a decision, and one
        sitting on the work is a sol that cannot be finished for a reason nothing in the
        transcript distinguishes from a hard one.

        The work goes in by cell. `hazards` keeps the storm off each piece and leaves at
        least one approach open, which is all a solid target needs."""
        # From where the rover woke, which is the pad unless last night stranded it: a
        # storm on a stranded rover would be the one the docstring above rules out.
        self.here.storm = hazards.spawn_for_day(
            self.here, self.day, self.pos,
            keep_clear=(self.base, *self.here.objectives, *self.here.interests))
        if self.here.storm:
            s = self.here.storm
            self.record("storm", weather=s.kind, at=s.centre, cells=len(s),
                        extent=s.extent)

    # --- the work --------------------------------------------------------
    @property
    def objectives(self):
        """Every unfinished objective, in the order placed."""
        return list(self.here.objectives.values())

    @property
    def interests(self):
        """Every unexamined interest, found or not, in the order `config` wrote them."""
        return list(self.here.interests.values())

    def _placeable(self, cell, what):
        """Why `cell` cannot take a piece of work, or None if it can.

        **The approach test is the point.** Work is solid, so the rover does it from a
        neighbour -- which means placeable is not "the cell is open", it is "at least one
        of its four neighbours can be driven to". A cell whose every approach is rock is a
        sol that ends in BLOCKED after a long drive, and a transcript of that is
        indistinguishable from work that was merely hard. Judged over the true grid.
        """
        a = self.here
        x, y = cell
        if not (0 <= x < a.w and 0 <= y < a.h):
            return f"({x},{y}) is off the {a.name}, which is {a.w} by {a.h}."
        if cell in a.objectives or cell in a.interests:
            return f"({x},{y}) already carries work."
        if a.at(x, y) == "H":
            return f"({x},{y}) is the base pad."
        if a.at(x, y) == "#":
            return (f"({x},{y}) is rock. {what} sits on drivable ground -- the rover "
                    f"stops beside it, not on it.")
        if cell == self.pos:
            return f"({x},{y}) is where the rover is standing."
        if cell in a.storm_cells:
            return f"({x},{y}) is under today's dust storm."
        reach = a.reachable()
        if not any(c in reach for c in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y))):
            return (f"({x},{y}) has no approach the rover can reach -- every cell beside "
                    f"it is rock, off the arena, or walled off.")
        return None

    def place_objective(self, cell, priority, cost, auto=False):
        """Mission control puts work on the map. Returns (Objective, None) or (None, why).

        **Only on ground the rover has mapped.** The desk can only point at what it has
        seen, and that is what makes an objective visible to her the moment it exists:
        nothing has to be lifted out of the fog for it.
        """
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
        """Hide something on the map. Returns (Interest, None) or (None, why).

        Anywhere drivable, mapped or not, and hidden either way: she finds it only by
        bringing the rover within sight of it again.
        """
        why = self._placeable(cell, "An interest")
        if why:
            return None, why
        i = Interest(cell, text, cost)
        self.here.interests[cell] = i
        self.record("placed_interest", at=cell, text=text, cost=cost)
        return i, None

    def auto_objectives(self):
        """The auto mode's dawn: three objectives, one of each priority, from sol 2, and a
        new set only once every auto one is finished. Returns what it placed.

        On mapped open ground, away from the pad and the rover, never beside other work,
        so a set cannot wall in the pad or itself. Seeded by arena and sol, like the storm.
        """
        if S.OBJECTIVES != "auto" or self.day < 2 or any(o.auto for o in self.objectives):
            return []
        a = self.here
        rng = random.Random(f"{a.name}:{a.w}x{a.h}:objectives:sol{self.day}")
        near = lambda c, d, r: abs(c[0] - d[0]) <= r and abs(c[1] - d[1]) <= r
        taken = set(a.objectives) | set(a.interests)
        cells = [c for c in sorted(a.seen) if a.at(*c) == "."
                 and not any(near(c, p, 2) for p in self.pad) and not near(c, self.pos, 2)
                 and not any(near(c, t, 1) for t in taken)]
        rng.shuffle(cells)
        placed = []
        for priority in ("high", "medium", "low"):
            for c in cells:
                if any(near(c, o.cell, 1) for o in placed):
                    continue
                o, _ = self.place_objective(c, priority,
                                            rng.randrange(S.OBJECTIVE_COST[0],
                                                          S.OBJECTIVE_COST[1] + 1, 5),
                                            auto=True)
                if o:
                    placed.append(o)
                    break
        return placed

    def adjacent_work(self):
        """The unfinished work the rover is standing next to, if any: an objective, or an
        interest it has found.

        Orthogonal only, and one at a time -- the same four cells `nav` can drive
        between, so "next to it" means the same thing to the planner and to the work.
        """
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
        """Do the work at `o`, charging its cost. Returns the steps actually spent.

        Charged before the work is marked done, so a battery that runs out mid-task still
        pays for what it used -- running out is not a refund. Its time on the day is the
        reel's: a step of work is drawn at a driving step's pace.
        """
        spent = min(o.cost, self.battery)
        self.spend(spent)
        self.play([("work", (o.cell, spent))])
        if spent < o.cost:
            return spent                # ran out of battery; the work is not finished
        o.done = True
        a = self.here
        del (a.objectives if o.kind == "objective" else a.interests)[o.cell]
        what = ({"priority": o.priority} if o.kind == "objective" else {"text": o.text})
        self.finished.append({"sol": self.day, "at": list(o.cell), "kind": o.kind,
                              "cost": o.cost, **what})
        # No `day=` here: `record` stamps it. Passing it again is a TypeError that only
        # fires on a live run, because every test world has `recorder=None`.
        self.record(o.kind, at=o.cell, cost=o.cost, **what)
        return spent

    # --- movement --------------------------------------------------------
    def move(self, dx, dy):
        x, y = self.pos[0] + dx, self.pos[1] + dy
        if self.here.blocked(x, y) or self.battery <= 0:
            return
        self.pos = (x, y)
        self._arrive()
        self.spend()            # only a move that happened costs anything

    def toggle_mark(self, cell=None):
        a = self.here
        cell = cell or self.pos
        if cell in a.marks:
            a.marks.discard(cell)
            self.say(f"Mark cleared at {cell}.")
        else:
            a.marks.add(cell)
            self.say(f"Marked {cell} with an X.")
