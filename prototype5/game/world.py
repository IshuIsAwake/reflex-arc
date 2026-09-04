"""World state. No pygame in here -- this is the part the planner drives.

An arena, fog, a rover, a day and a step budget. Result strings are the failure codes
prototype 1 arrived at, and the human sees the same strings the model does.
"""

import random

import config as C
import settings as S

SOLID = set("#H")   # everything you cannot drive through
THINGS = SOLID - set("#")   # ...and just the things. A rock is not a destination

# Headings for the learned-policy buttons: 0=N(-y) 1=E(+x) 2=S(+y) 3=W(-x).
# This order must not change -- rl_cell.DVEC and the trained weights assume it.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))

# What each tile is called out loud. Lives here rather than in render.py because the
# renderer imports pygame and the model loop cannot: gemma reads these same words.
# One wording for the screen and the view, the way Result.__str__ is one wording for
# the console and the model.
LABELS = {"H": "base pad"}


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


def label_for(w, ch):
    """What to call a tile, out loud, on screen and in the view.

    A pass-through today -- prototype 1 used it to make terminal names something you
    had to walk up to and earn. Kept because `interact` brings that rule straight
    back, and because it is the one place a name is decided.
    """
    return LABELS.get(ch)


def _pick_buttons(area, spawn, n=1):
    """Button cells on clear ground near spawn, deterministic for a fixed ARENA.

    Buttons are not tiles -- the ARENA strings stay untouched, so nothing that
    reads the grid (nav.known, sight, the flood-fill test) sees them. The ring
    search keeps the first button inside the landing-site reveal, so listing it
    in the view never hands over unearned map.
    """
    sx, sy = spawn
    out = []
    for r in range(2, 10):
        for y in range(sy - r, sy + r + 1):
            for x in range(sx - r, sx + r + 1):
                if max(abs(x - sx), abs(y - sy)) != r:
                    continue
                if area.at(x, y) == "." and (x, y) != spawn and (x, y) not in out:
                    out.append((x, y))
                    if len(out) >= n:
                        return set(out)
    return set(out)


class Area:
    def __init__(self, name, rows):
        self.name = name
        self.rows = [r.replace("@", ".") for r in rows]
        self.w = len(self.rows[0])
        self.h = len(self.rows)
        self.seen = set()
        self.marks = set()
        self.visited = set()   # cells actually driven over, as opposed to merely seen

    def at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.rows[y][x]
        return "#"

    def blocked(self, x, y):
        return self.at(x, y) in SOLID

    def visible(self, x, y):
        return (x, y) in self.seen

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
        """Lift the whole fog. Never used by the game -- driving is the only thing
        that opens the map there. This is for training sets and for `--no-fog`, where
        seeing everything is the deliberate point rather than a bug."""
        self.seen |= {(x, y) for y in range(self.h) for x in range(self.w)}

    def reveal(self, px, py, r=None):
        """Open the fog around a cell. Returns the cells that were new.

        The return value is what lets the drive be watched. `nav` finishes instantly,
        so by the time anything is drawn the fog has already lifted along the whole
        route -- and a rover trundling down an already-open corridor is the least
        interesting version of this. Recording which step revealed what lets
        `anim.Reel` hold the fog shut and peel it back in time with the rover.
        """
        new = self.disc(px, py, r) - self.seen
        self.seen |= new
        return new


class World:
    """One expedition. Days roll over; the arena and everything learned carry on.

    `recorder` is how the run gets written down without putting a file handle in
    here. `logs.py` sets it; it is None everywhere else, including every test, so
    this file still does no I/O.
    """

    def __init__(self, recorder=None):
        self.here = Area(C.ARENA_NAME, C.ARENA)
        self.pos = C.SPAWN
        self.heading = 0      # N, CellEnv convention -- the policy executor turns it
        self.herr = 0.0       # deg off square, as the overhead camera would report
        self.buttons = _pick_buttons(self.here, self.pos)
        self.pressed = set()  # buttons pressed so far; persist like the map
        self.day = 1
        self.day_over = False
        self.time_left = float(S.DAY_SECONDS)
        self.steps = 0
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
        # The objective the route file is currently about, and every leg planned
        # toward it. `nav` owns the contents; they live here because they outlast a
        # single `goto` -- a call that came back BLOCKED and the call that carries on
        # from where it stopped are one journey, and the file has to read like one.
        self.plan_goal = None
        self.plan_legs = []
        self.log = []
        self.recorder = recorder
        self.revealed = set()   # what the last move opened up, for the playback
        self.reel = []          # finished drives waiting to be drawn. See anim.py
        # The landing site is visible on arrival. You can see where you came down.
        self.here.reveal(*self.pos, r=S.BASE_REVEAL)
        self._arrive()
        self.record("day_open", at=self.pos, steps_left=self.steps_left)

    @property
    def area(self):
        """One arena, so this is a constant -- but nav, sight and the logs all name
        the place they are talking about, and item 3 puts weather on top of it."""
        return self.here.name

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
        """Standing somewhere is stronger than seeing it. `avoid="auto"` is meant to
        be legal only for somewhere the rover has actually been, so track it
        separately."""
        self.revealed = self.here.reveal(*self.pos)
        self.here.visited.add(self.pos)

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
        """Wall clock. In human mode it runs the day down. In gemma mode it only
        watches, so we can log how long the model actually took without charging it
        for thinking -- which is the number item 4 has to be designed against."""
        dt *= S.TIME_SCALE
        self.elapsed += dt
        if S.DAY_MODE != "human":
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0.0
            self.day_over = True

    def spend(self, n=1):
        """One world-changing action. In gemma mode the day is made of these."""
        self.steps += n
        if S.DAY_MODE == "human":
            return
        if self.steps >= S.DAY_STEPS:
            self.day_over = True

    @property
    def steps_left(self):
        return max(0, S.DAY_STEPS - self.steps)

    def next_day(self):
        """The rover wakes at the pad. Everything it has mapped carries over; the
        message log does not -- yesterday's messages are noise once the day is shut.

        It returns to base for free, which is half of item 2 already standing. What
        that item adds is the *consequence* of not being here at nightfall, not the
        journey.
        """
        self.history.append({"day": self.day, "steps": self.steps,
                             "seconds": round(self.elapsed, 1)})
        self.record("day_close", steps=self.steps, seconds=round(self.elapsed, 1))
        self.day += 1
        self.day_over = False
        self.time_left = float(S.DAY_SECONDS)
        self.steps = 0
        self.elapsed = 0.0
        self.log.clear()
        self.last_path = ("", [])
        self.last_walk = ("", [])
        self.plan_goal, self.plan_legs = None, []   # yesterday's journey is over
        self.reel.clear()       # nobody wants to watch yesterday's drive
        self.pos = C.SPAWN
        self.heading = 0
        self.herr = 0.0
        self._arrive()
        self.record("day_open", at=self.pos, steps_left=self.steps_left)

    # --- movement --------------------------------------------------------
    def move(self, dx, dy):
        x, y = self.pos[0] + dx, self.pos[1] + dy
        if self.here.blocked(x, y):
            return
        self.pos = (x, y)
        self._arrive()
        self.spend()            # only a move that happened costs anything

    def _settle_heading(self, sigma):
        """The ArUco snap: a turn drags the heading off, the overhead camera
        squares it back. Same shape as CellEnv._correct_heading in rl_cell.py,
        with fixed noise -- the episode randomisation lives in training."""
        self.herr += random.gauss(0, sigma)
        self.herr = self.herr * 0.15 + random.gauss(0, 1.5)
        self.herr = max(-30.0, min(30.0, self.herr))

    def step_action(self, a):
        """One learned-policy button: 0 FWD, 1 LEFT90, 2 RIGHT90, 3 PRESS.

        The buttons the RL half of the project emits (rl_cell.py NAMES). Only
        the policy executor (nav.goto executor="policy") calls this; everything
        else drives via move(). A refused FWD charges nothing, exactly like
        move(), so bumping a wall is free but never moves.
        Returns "moved", "turned", "pressed", "noop" or "bump".
        """
        if a == 1:
            self.heading = (self.heading - 1) % 4
            self._settle_heading(10.0)
            self.spend()
            return "turned"
        if a == 2:
            self.heading = (self.heading + 1) % 4
            self._settle_heading(10.0)
            self.spend()
            return "turned"
        if a == 0:
            dx, dy = DIRS[self.heading]
            x, y = self.pos[0] + dx, self.pos[1] + dy
            if self.here.blocked(x, y):
                return "bump"
            self.pos = (x, y)
            self._arrive()
            self.herr = max(-30.0, min(30.0, self.herr + random.gauss(0, 1.0)))
            self.spend()
            return "moved"
        if a == 3:
            self.spend()
            if self.pos in self.buttons:
                self.pressed.add(self.pos)
                return "pressed"
            return "noop"
        return "noop"

    def toggle_mark(self, cell=None):
        a = self.here
        cell = cell or self.pos
        if cell in a.marks:
            a.marks.discard(cell)
            self.say(f"Mark cleared at {cell}.")
        else:
            a.marks.add(cell)
            self.say(f"Marked {cell} with an X.")
