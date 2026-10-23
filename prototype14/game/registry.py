"""The settings a person can change while the app runs (the O screen), and when each
change lands: "now", at the next "sol", or on "relaunch". Only values that differ from the
defaults in settings.py and config.py are saved, in user_settings.json."""

import json
import pathlib

import config as C
import settings as S

USER_FILE = pathlib.Path(__file__).resolve().parent.parent / "user_settings.json"
TIERS = ("now", "sol", "relaunch")
TIER_NAMES = {"now": "applies now", "sol": "applies at the next sol",
              "relaunch": "applies after a restart"}


class Setting:
    """One setting. `replayed` says whether a replay takes the kept run's value: true for
    the ones that change the world, false for pace and window size."""

    def __init__(self, name, kind, tier, desc, lo=None, hi=None, step=1, choices=None,
                 mod=S, replayed=True):
        self.name, self.kind, self.tier, self.desc = name, kind, tier, desc
        self.lo, self.hi, self.step, self.choices = lo, hi, step, choices
        self.mod, self.replayed = mod, replayed
        self.default = getattr(mod, name)

    @property
    def value(self):
        return getattr(self.mod, self.name)

    def coerce(self, v):
        """`v` as this setting's type, or ValueError saying why not. Takes typed text too."""
        if isinstance(v, str) and self.kind != "str" and v not in (self.choices or ()):
            v = _parse(v)
        if self.kind == "bool":
            if not isinstance(v, bool):
                raise ValueError("on or off")
            return v
        if self.kind == "choice":
            for c in self.choices:
                # 0 matches 0.0, but True must not match 1, and None matches only None.
                if c == v and isinstance(c, bool) == isinstance(v, bool):
                    return c
            raise ValueError("one of " + ", ".join(show(c) for c in self.choices))
        if self.kind == "str":
            v = str(v).strip()
            if not v:
                raise ValueError("cannot be empty")
            return v
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"a number from {show(self.lo)} to {show(self.hi)}")
        if self.kind == "int":
            if v != int(v):
                raise ValueError("a whole number")
            v = int(v)
        else:
            v = float(v)
        if not self.lo <= v <= self.hi:
            raise ValueError(f"from {show(self.lo)} to {show(self.hi)}")
        return v

    def nudge(self, v, d):
        """The next value one step in direction `d` (+1 or -1) from `v`."""
        if self.kind == "bool":
            return not v
        if self.kind in ("choice", "str"):
            opts = list(self.choices or [v])
            if v not in opts:
                opts.insert(0, v)
            return opts[(opts.index(v) + d) % len(opts)]
        v = v + d * self.step
        v = max(self.lo, min(self.hi, v))
        return round(v, 3) if self.kind == "float" else int(v)


def _parse(text):
    t = text.strip().lower()
    if t == "none":
        return None
    if t in ("on", "true", "yes"):
        return True
    if t in ("off", "false", "no"):
        return False
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return text.strip()


def show(v):
    """A value as the settings screen and the error messages show it."""
    if v is None:
        return "model's own"
    if isinstance(v, bool):
        return "on" if v else "off"
    return str(v)


SETTINGS = [
    # Now
    Setting("ANIM_SPEED", "float", "now", "how fast drives are drawn; 1 is the design "
            "pace, 0.5 the recording's. The day's clock runs while they are",
            0.25, 4.0, 0.25, replayed=False),
    Setting("ANIMATE", "bool", "now", "draw each drive cell by cell; off and the rover "
            "jumps", replayed=False),
    Setting("SETTLE_SECONDS", "float", "now", "the pause after a drive before the "
            "planner may think again", 0.0, 10.0, 0.5, replayed=False),
    Setting("SHOW_THINKING", "bool", "now", "show the model's reasoning in the pane; the "
            "tape keeps it either way", replayed=False),
    Setting("TIME_SCALE", "float", "now", "how fast the day's clock runs",
            0.25, 8.0, 0.25, replayed=False),
    # On a replay these stay the viewer's.
    Setting("COMMS", "bool", "now", "someone is at the desk: each phase waits for "
            "them, and they can talk at dawn and night. Off, every phase moves on by "
            "itself. C in the app switches it for this run only", replayed=False),
    Setting("COMMS_WAIT", "float", "now", "seconds a phase waits after the last thing "
            "typed or said before it moves on by itself", 10.0, 600.0, 10.0,
            replayed=False),
    Setting("MAP_LABELS", "bool", "now", "labels on the map: the rover's cell, and "
            "where a drive is headed and whether it got there", replayed=False),
    Setting("ROVER_PAUSE", "choice", "now", "key: press SPACE when the rover has driven "
            "each leg. none: do not wait", choices=("key", "none"), replayed=False),
    # At the next sol
    Setting("MODEL", "str", "sol", "the planner: any model Ollama has, cloud ones "
            "through this machine's Ollama sign-in", replayed=False),
    Setting("MODEL_FALLBACK", "str", "now", "answers when the planner's model cannot, "
            "until it is back; the same model as the planner turns it off",
            replayed=False),
    Setting("MODEL_THINK", "bool", "sol", "a reasoning trace before each answer; slower",
            replayed=False),
    Setting("MODEL_TEMP", "choice", "sol", "sampling temperature",
            choices=(0.0, 0.3, 0.7, 1.0, None), replayed=False),
    Setting("MODEL_SEED", "choice", "sol", "the sampler's seed",
            choices=(0, 1, 2, 3, None), replayed=False),
    Setting("MODEL_CTX", "choice", "sol", "context window in tokens; Ollama truncates "
            "silently past it", choices=(8192, 16384, 32768, 65536), replayed=False),
    Setting("OLLAMA_HOST", "str", "sol", "where the chat endpoint is", replayed=False),
    Setting("MISSION_SOLS", "int", "sol", "sols in the mission; after the last, the "
            "window waits for N, 1-9 or ESC, and a headless run ends. 0 is no limit",
            0, 100),
    Setting("DAY_SECONDS", "int", "sol", "seconds of wall clock in the day, from the "
            "moment it begins; nothing pauses it", 30, 3600, 10),
    Setting("RADIO_STEPS", "int", "sol", "battery one radio message costs her: the call, "
            "and each reply while the line is open", 0, 50),
    Setting("OBJECTIVES", "choice", "sol", "manual: the desk places objectives. auto: "
            "three, one of each priority, from sol 2, a new set once the last is done",
            choices=("manual", "auto")),
    Setting("BATTERY", "int", "sol", "the battery, in steps: one per tile driven, plus "
            "the work. Only the pad recharges it", 30, 2000, 10),
    Setting("MOVE_HOPS", "int", "sol", "drives the model may make in one turn", 1, 50),
    Setting("FREE_HOPS", "int", "sol", "looks it may make between drives", 1, 30),
    Setting("VISION_RADIUS", "int", "sol", "how far the rover sees as it drives", 1, 6),
    Setting("STORM_ON", "bool", "sol", "one dust storm a sol"),
    Setting("STORM_RADIUS", "int", "sol", "how big the storm is", 1, 5),
    Setting("NAV_REPLANS", "int", "sol", "replans in one goto before it returns BLOCKED",
            0, 10),
    Setting("TODO_MAX", "int", "sol", "items on the model's list in a sol", 1, 40),
    Setting("TODO_CHARS", "int", "sol", "characters in one list item", 40, 1000, 20),
    Setting("MEMORY_ENTRIES", "int", "sol", "entries her memory holds; at the cap she "
            "forgets one before she adds", 1, 30),
    Setting("MEMORY_CHARS", "int", "sol", "characters in one entry of her memory",
            50, 1000, 25),
    Setting("ORDERS_CHARS", "int", "sol", "characters in one order on the board",
            50, 1000, 25),
    # After a restart
    Setting("APP_ARENA", "choice", "relaunch", "the arena: 30x30 or 50x50",
            choices=tuple(C.ARENAS), mod=C),
    Setting("HUD_H", "int", "relaunch", "height of the strip under the arena",
            96, 250, 2, mod=C, replayed=False),
]
BY_NAME = {s.name: s for s in SETTINGS}

# The recording's values are today's defaults; the design set is what the work costs were balanced for.
PRESETS = {
    "29 Sept recording": {"BATTERY": 500, "DAY_SECONDS": 600, "MOVE_HOPS": 20,
                          "FREE_HOPS": 10, "ANIM_SPEED": 0.5},
    "design": {"BATTERY": 150, "DAY_SECONDS": 200, "MOVE_HOPS": 10, "FREE_HOPS": 5,
               "ANIM_SPEED": 1.0},
}


def snapshot():
    """Every setting's value now, for the run log."""
    return {s.name: s.value for s in SETTINGS}


def apply(values, only=None):
    """Put `values` in force, skipping unknown names. Returns the names whose values were
    refused. `only` picks which settings to take (replay takes the world's)."""
    bad = []
    for name, v in values.items():
        s = BY_NAME.get(name)
        if not s or (only and not only(s)):
            continue
        try:
            setattr(s.mod, name, s.coerce(v))
        except ValueError:
            bad.append(name)
    return bad


class Prefs:
    """One person's settings: what they saved, and what waits for nightfall."""

    def __init__(self, path=None):
        self.path = path = path or USER_FILE
        self.user = {}
        self.pending = {}
        self.warnings = []
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as e:
                raw = {}
                self.warnings.append(f"{path.name} is not valid JSON ({e}); ignored")
            for name, v in raw.items():
                s = BY_NAME.get(name)
                try:
                    self.user[name] = s.coerce(v)
                except (AttributeError, ValueError):
                    self.warnings.append(f"{path.name}: {name}={v!r} ignored")

    def apply_all(self):
        """At start-up every tier applies at once."""
        apply(self.user)

    def shown(self, s):
        """What the screen shows: the waiting change if there is one."""
        if s.name in self.pending:
            return self.pending[s.name]
        if s.tier == "relaunch":
            return self.user.get(s.name, s.default)
        return s.value

    def set(self, name, v):
        """Check, save, and apply as the tier allows. Raises ValueError."""
        s = BY_NAME[name]
        v = s.coerce(v)
        if v == s.default and type(v) is type(s.default):
            self.user.pop(name, None)
        else:
            self.user[name] = v
        self.save()
        if s.tier == "now":
            setattr(s.mod, name, v)
        elif s.tier == "sol":
            if v == s.value and type(v) is type(s.value):
                self.pending.pop(name, None)
            else:
                self.pending[name] = v
        return v


    def preset(self, label):
        for name, v in PRESETS[label].items():
            self.set(name, v)

    def nightfall(self):
        """Put the waiting changes in force. Returns them."""
        done, self.pending = self.pending, {}
        apply(done)
        return done

    def save(self):
        self.path.write_text(json.dumps(self.user, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")


def from_log(game_rows):
    """The settings a kept run was played under, by sol."""
    out = {}
    for r in game_rows:
        if r.get("kind") == "settings":
            out[r.get("sol", 1)] = r.get("values", {})
    return out
