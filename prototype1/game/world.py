"""World state. No pygame in here -- this is the part the planner will eventually drive.

Result strings are the failure codes from DESIGN.md. The human sees the same strings
the model will, which is the point of showing them in the HUD.
"""

import random

import config as C
import settings as S

SOLID = set("#BCFSNTL$*")  # walls and everything you interact with
GATES = "DEvn"
COUNTERS = {"S": "shop", "T": "tribe"}
TERMINALS = {"C": "cartpole", "F": "flappy", "N": "snake"}
NEEDS_KEY = {"F": "flappy_key", "D": "savana_key"}


class Area:
    def __init__(self, name, rows):
        self.name = name
        self.rows = [r.replace("@", ".") for r in rows]
        self.w = len(self.rows[0])
        self.h = len(self.rows)
        self.traps = {(x, y) for y, r in enumerate(self.rows) for x, c in enumerate(r) if c == "^"}
        self.has_map = False
        self.seen = set()
        self.marks = set()
        self.cleared = set()   # bags already emptied; they stop being drawn
        self.visited = set()   # cells actually stood on, as opposed to merely seen

    def at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            if (x, y) in self.cleared:
                return "."
            ch = self.rows[y][x]
            return "." if ch == "^" else ch  # traps are invisible, always
        return "#"

    def blocked(self, x, y):
        return self.at(x, y) in SOLID

    def visible(self, x, y):
        return self.has_map or (x, y) in self.seen

    def reveal(self, px, py):
        r = S.VISION_RADIUS
        for y in range(py - r, py + r + 1):
            for x in range(px - r, px + r + 1):
                if 0 <= x < self.w and 0 <= y < self.h and (x - px) ** 2 + (y - py) ** 2 <= r * r:
                    self.seen.add((x, y))


class World:
    def __init__(self):
        self.areas = {name: Area(name, rows) for name, rows in C.AREAS.items()}
        self.area = "plaza"
        self.pos = C.PLAZA_SPAWN
        self.coins = S.START_COINS
        self.items = set()
        self.antidotes = 0
        self.taken = set()      # (area, x, y) pickups already collected
        self.unlocked = set()   # (area, x, y) doors already opened
        self.cooldown = {}      # game -> seconds remaining
        self.played = set()     # games tried at least once
        self.discovered = {}    # game -> area, for terminals you have walked up to
        self.day = 1
        self.day_over = False
        self.day_start_coins = self.coins
        self.time_left = float(S.DAY_SECONDS)
        self.steps = 0
        self.elapsed = 0.0      # stopwatch, so a gemma run can be timed and logged
        self.history = []       # one record per finished day
        self.nav_log = []       # one record per goto/distance -- planned vs walked
        self.last_path = ("", [])  # (area, cells) of the last plan, for the map view
        self.log = []
        self._arrive()

    @property
    def here(self):
        return self.areas[self.area]

    def _arrive(self):
        """Standing somewhere is stronger than seeing it. `avoid="auto"` is meant to
        be legal only for somewhere gemma has actually been, so track it separately."""
        self.here.reveal(*self.pos)
        self.here.visited.add(self.pos)

    @property
    def pouch(self):
        return S.POUCH_UPGRADED if "tool_pouch" in self.items else S.POUCH

    def say(self, msg, tone="plain"):
        self.log.append((msg, tone))
        del self.log[:-6]

    # --- time ------------------------------------------------------------
    def tick(self, dt):
        """Wall clock. In human mode it runs the day down. In gemma mode it only
        watches, so we can log how long the model actually took without charging it
        for thinking."""
        dt *= S.TIME_SCALE
        self.elapsed += dt
        if S.DAY_MODE != "human":
            return
        self.time_left -= dt
        self._cool(dt)
        if self.time_left <= 0:
            self.time_left = 0.0
            self.day_over = True

    def spend(self, n=1):
        """One world-changing action. In gemma mode the day is made of these."""
        self.steps += n
        if S.DAY_MODE == "human":
            return
        self._cool(n)
        if self.steps >= S.DAY_STEPS:
            self.day_over = True

    def _cool(self, amount):
        for g in list(self.cooldown):
            self.cooldown[g] -= amount
            if self.cooldown[g] <= 0:
                del self.cooldown[g]

    @property
    def steps_left(self):
        return max(0, S.DAY_STEPS - self.steps)

    def earned_today(self):
        return self.coins - self.day_start_coins

    def next_day(self):
        """Coins, items, maps, marks and everything learned carry over. The log does
        not -- yesterday's messages are noise once the day is closed."""
        self.history.append({"day": self.day, "steps": self.steps,
                             "seconds": round(self.elapsed, 1),
                             "earned": self.earned_today(), "coins": self.coins})
        self.day += 1
        self.day_over = False
        self.time_left = float(S.DAY_SECONDS)
        self.steps = 0
        self.elapsed = 0.0
        self.cooldown.clear()
        self.log.clear()
        self.last_path = ("", [])
        self.day_start_coins = self.coins
        self.area, self.pos = "plaza", C.PLAZA_SPAWN
        self._arrive()

    # --- movement --------------------------------------------------------
    def move(self, dx, dy):
        x, y = self.pos[0] + dx, self.pos[1] + dy
        ch = self.here.at(x, y)

        # Doors open by interacting, never by walking into them, so that opening one
        # stays a visible decision rather than a side effect of moving.
        if ch == "D" and (self.area, (x, y)) not in self.unlocked:
            if NEEDS_KEY["D"] in self.items:
                self.say("The east gate is shut. Press E to open it.")
            else:
                self.say(f"LOCKED(needs: {NEEDS_KEY['D']})", "bad")
            return
        if self.here.blocked(x, y):
            return

        self.pos = (x, y)
        self._arrive()
        self.spend()            # only a move that happened costs anything

        if (x, y) in self.here.traps:
            # One antidote absorbs one pit. You stay where you are, which is the
            # whole value of it -- no coins lost and no walk back.
            if self.antidotes:
                self.antidotes -= 1
                self.say(f"TRAPPED({x}, {y}) -- an antidote burns up. {self.antidotes} left.",
                         "good")
                return
            self.coins = max(0, self.coins - S.TRAP_PENALTY)
            self.say(f"TRAPPED({x}, {y}) -- snake pit. -{S.TRAP_PENALTY} coins.", "bad")
            self.area, self.pos = "plaza", C.PLAZA_SPAWN
            self._arrive()
            return

        link = C.LINKS.get((self.area, (x, y)))
        if link:
            self.area, self.pos = link[0], link[1]
            self._arrive()
            self.say(f"Entered the {C.DISPLAY_NAMES[self.area]}.")

    # --- interaction -----------------------------------------------------
    def facing(self):
        """Every adjacent cell that has something worth pressing E at."""
        x, y = self.pos
        out = []
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            ch = self.here.at(x + dx, y + dy)
            if ch not in "#.":
                out.append((ch, (x + dx, y + dy)))
        return out

    def interact(self):
        # Pressing E next to nothing does nothing at all -- no message. The planner
        # will still get NOT_HERE back from its own interact(); this is only the
        # human's keyboard being forgiving.
        for ch, cell in self.facing():
            if self._use(ch, cell):
                if ch not in COUNTERS:
                    self.spend()   # a counter costs nothing to lean on; buying does
                return

    def _use(self, ch, cell):
        key = (self.area, cell)

        if ch == "B":
            if self.here.has_map:
                self.say("ALREADY_DONE -- you already have the Plaza map.", "bad")
            else:
                self.here.has_map = True
                self.say("Plaza map acquired. Press M.", "good")
            return True

        if ch == "L":
            self.taken.add(key)
            self.here.cleared.add(cell)
            self.here.has_map = True
            extra = S.LOST_BAG_ITEMS.get(key)
            if extra == "antidote":
                self.antidotes = min(self.pouch, self.antidotes + 1)
                self.say(f"A lost bag: the {C.DISPLAY_NAMES[self.area]} map and a free antidote.",
                         "good")
            elif extra:
                self.items.add(extra)
                self.say(f"A lost bag: the {C.DISPLAY_NAMES[self.area]} map and a free {extra}.",
                         "good")
            else:
                self.say(f"A lost bag. The {C.DISPLAY_NAMES[self.area]} map was inside. Press M.",
                         "good")
            return True

        if ch in "$*":
            self.taken.add(key)
            self.here.cleared.add(cell)
            amount = S.BAGS.get(key, 0)
            self.coins += amount
            what = "The vault" if ch == "*" else "A coin bag"
            self.say(f"{what}. +{amount} coins.", "good")
            return True

        if ch in COUNTERS:
            return True  # the counter's panel is opened by the caller

        if ch in TERMINALS:
            game = TERMINALS[ch]
            if game not in self.discovered:
                self.discovered[game] = self.area
                self.say(f"A {game} terminal.", "good")
            self.play(game, ch)
            return True

        if ch == "D":
            if key in self.unlocked:
                self.say("ALREADY_DONE -- the gate is already open.")
            elif NEEDS_KEY["D"] in self.items:
                self.unlocked.add(key)
                self.say("The east gate swings open.", "good")
            else:
                self.say(f"LOCKED(needs: {NEEDS_KEY['D']})", "bad")
            return True

        return False

    def at_counter(self):
        """Which shop counter you are standing next to, if any."""
        for ch, _ in self.facing():
            if ch in COUNTERS:
                return COUNTERS[ch]
        return None

    # --- games and shop --------------------------------------------------
    def play(self, game, ch):
        need = NEEDS_KEY.get(ch)
        if need and need not in self.items:
            self.say(f"LOCKED(needs: {need})", "bad")
            return
        if game in self.cooldown:
            self.say(f"ON_COOLDOWN({self.cooldown[game]:.0f}s)", "bad")
            return

        cd, pay, chance = S.GAMES[game]
        self.cooldown[game] = float(cd)
        self.played.add(game)
        if random.random() < chance:
            self.coins += pay
            self.say(f"WON({pay}) at {game}.", "good")
        else:
            self.say(f"LOST at {game}.", "bad")

    def buy(self, item, counter=None):
        counter = counter or self.at_counter()
        stock = S.SHOPS.get(counter, {})
        if item not in stock:
            self.say("NOT_STOCKED", "bad")
            return
        if item == "antidote":
            if self.antidotes >= self.pouch:
                self.say(f"NOT_STOCKED -- your pouch holds {self.pouch}.", "bad")
                return
        elif item in self.items:
            self.say("NOT_STOCKED -- you own it.", "bad")
            return

        price = stock[item]
        if self.coins < price:
            self.say(f"INSUFFICIENT_COINS -- {item} costs {price}.", "bad")
            return
        self.coins -= price
        self.spend()
        if item == "antidote":
            self.antidotes += 1
        else:
            self.items.add(item)
        self.say(f"Bought {item} for {price}.", "good")

    def cooldown_lines(self):
        """Only terminals you have walked up to *and* can actually use. A locked one
        has no cooldown to report, and listing one you have never found would hand
        over map knowledge this world is meant to make you earn."""
        out = []
        for game, (cd, _, _) in S.GAMES.items():
            need = next((k for c, k in NEEDS_KEY.items() if TERMINALS.get(c) == game), None)
            if game not in self.discovered or (need and need not in self.items):
                continue
            where = C.DISPLAY_NAMES[self.discovered[game]]
            if game in self.cooldown:
                out.append((game, where, f"{self.cooldown[game]:.0f}s", "bad"))
            else:
                out.append((game, where, f"ready  ({cd}s cooldown)", "good"))
        return out

    def toggle_mark(self, cell=None):
        a = self.here
        cell = cell or self.pos
        if cell in a.marks:
            a.marks.discard(cell)
            self.say(f"Mark cleared at {cell}.")
        else:
            a.marks.add(cell)
            self.say(f"Marked {cell} with an X.")
