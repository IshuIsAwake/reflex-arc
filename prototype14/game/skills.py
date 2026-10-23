"""The skills: what the model may ask for, and what it gets back. chat.py knows nothing
about nav, and nav knows nothing about the model; this file sits between them.

Arguments are accepted generously and refused loudly: an argument that quietly became
"nothing" would do something she never asked for. A refused call (BAD_ARGS) costs nothing.
The model can't use avoid="auto": she has no way to mark cells. The terminal can."""

import re

import nav
import settings
from world import INTEREST, centre_of

NIL = {"<nil>", "nil", "none", "null", "undefined", ""}

# How many step-spending calls `_stuck` weighs together, so one deliberate drive home is never scolded.
WINDOW = 4


class BadArgs(Exception):
    """Caught in `call` and handed back as BAD_ARGS(...)."""


def _int(name, v):
    """Accept 7, "7", " 7 " and 7.0. Refuse anything else by name."""
    if isinstance(v, bool):
        raise BadArgs(f"{name} must be a whole number, got {v!r}")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v != int(v):
            raise BadArgs(f"{name} must be a whole number, got {v!r}")
        return int(v)
    if isinstance(v, str):
        t = v.strip()
        if t.lstrip("-").isdigit():
            return int(t)
    raise BadArgs(f"{name} must be a whole number, got {v!r}")


def _why(v):
    """One line if offered, None if not. Optional: it only goes on the tape, before the result."""
    if not isinstance(v, str) or v.strip().lower() in NIL:
        return None
    return " ".join(v.split())[:200]


def _text(name, v, limit):
    """Her words, or a loud refusal. Too long is refused, not cut, since the end is usually what she just changed."""
    if not isinstance(v, str) or v.strip().lower() in NIL:
        raise BadArgs(f"{name} needs some words, got {v!r}")
    t = " ".join(v.split())
    if len(t) > limit:
        raise BadArgs(f"{name} is {len(t)} characters and the limit is {limit} -- "
                      f"nothing was written and what you had is unchanged. Shorten it "
                      f"and send the whole thing again")
    return t


def _avoid(v):
    """None, or a frozenset of cells. "(3,4),(5,6)", "3,4 5,6" and [[3,4],[5,6]] all work;
    an odd number of coordinates or no numbers at all is refused."""
    if v is None:
        return None
    if isinstance(v, str):
        t = v.strip()
        if t.lower() in NIL:
            return None  # meant to leave it out: the only silent empty
        if t.lower().startswith("auto"):
            raise BadArgs("avoid=auto is not available yet -- you cannot mark cells. "
                          "Pass the cells themselves, like (3,4),(5,6)")
        n = [int(m) for m in re.findall(r"-?\d+", t)]
        if not n:
            raise BadArgs(f"avoid needs cells like (3,4),(5,6), got {v!r}")
        if len(n) % 2:
            raise BadArgs(f"avoid has an odd number of coordinates: {v!r}")
        return frozenset(zip(n[::2], n[1::2]))
    if isinstance(v, (list, tuple)):
        if not v:
            return None
        try:
            return frozenset((_int("avoid x", c[0]), _int("avoid y", c[1])) for c in v)
        except (TypeError, IndexError, KeyError):
            raise BadArgs(f"avoid must be a list of (x, y) pairs, got {v!r}")
    raise BadArgs(f"avoid must be cells like (3,4),(5,6), got {v!r}")


# Sent to Ollama as `tools`. The wording matters: "one call drives the whole way" and "ABSOLUTE" each fixed a real mistake.
TOOLS = [
    {"type": "function", "function": {
        "name": "goto",
        "description": (
            "Drive to a cell in the arena. Coordinates are ABSOLUTE cells on the map "
            "in your view, never offsets from where you stand -- to move ten cells "
            "south, add ten to your own y and pass that. One call drives the whole "
            "way, however far it is: each tile is one step off the battery, and the "
            "day's clock runs while the rover drives. "
            "It plans over the map you have seen and assumes unseen ground is clear, "
            "so rock you have never met will stop you: that is not a bug, it is how "
            "the map fills in, and the rock you hit comes back in the answer. Aiming "
            "at something solid such as the base pad puts you next to it, which "
            "counts as arriving."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column, 0 is the west edge"},
            "y": {"type": "integer", "description": "absolute row, 0 is the north edge"},
            "why": {"type": "string", "description":
                    "optional: one line on what you expect from this, written before "
                    "you find out. The drive runs either way."},
            "avoid": {"type": "string", "description":
                      "cells to treat as impassable for this trip only, like '(3,4),(5,6)'. "
                      "Omit it entirely unless you have a specific cell in mind."},
        }, "required": ["x", "y"]}}},
    {"type": "function", "function": {
        "name": "distance",
        "description": (
            "How many steps a goto to this cell would cost, without walking it and "
            "without spending anything. Optimistic: it assumes every unseen cell is "
            "clear, so the real walk can only come out the same or longer. Use it to "
            "price a trip before committing battery and time to it."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column"},
            "y": {"type": "integer", "description": "absolute row"},
            "why": {"type": "string", "description":
                    "optional: one line on what you are weighing up"},
            "avoid": {"type": "string", "description":
                      "cells to treat as impassable, like '(3,4),(5,6)'. Usually omit."},
        }, "required": ["x", "y"]}}},
    {"type": "function", "function": {
        "name": "execute",
        "description": (
            "Do the work at the objective or interest the rover is standing next to. "
            "Drive to it first -- goto puts you alongside it, which is arriving -- then "
            "call this. It costs that work's own number of steps, listed with it in "
            "your view: that much battery, and the day's time to do them one by one. "
            "The work is finished and gone once it is paid. An interest "
            "tells you what it is when you examine it, and only then. Standing anywhere "
            "else this does nothing and costs nothing."),
        "parameters": {"type": "object", "properties": {
            "why": {"type": "string", "description":
                    "optional: one line on why this one now"},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "count",
        "description": (
            "Every rock formation and every patch of fog you have revealed so far, "
            "each with how many cells it covers and one coordinate at its middle. "
            "Rock formations keep the same id for the whole expedition, so R4 is the "
            "same rock tomorrow. Counting cells off the map by eye is the one thing "
            "you are reliably wrong about -- ask for the numbers instead of adding "
            "them up. It costs no steps. Rock still under fog is not counted as rock, "
            "because you have not seen it yet."),
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "description":
                     "'rock', 'fog', or omit for both"},
            "why": {"type": "string", "description":
                    "optional: one line on what you are weighing up"},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "count_cells",
        "description": (
            "The exact cells one formation occupies. Give it any coordinate that "
            "belongs to the thing -- the middle coordinate `count` gave you is always "
            "one. Use it when you need the shape rather than the size, such as working "
            "out which way round something you cannot drive through. Costs no steps."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column"},
            "y": {"type": "integer", "description": "absolute row"},
            "why": {"type": "string", "description":
                    "optional: one line on what you are weighing up"},
        }, "required": ["x", "y"]}}},
    {"type": "function", "function": {
        "name": "todo",
        "description": (
            "Put one thing you mean to do on your list, so you do not decide it "
            "twice. The list is in your view, numbered, and it is yours -- it is not "
            "the mission's work, which is listed separately and crosses itself off "
            "when the work is paid for. Costs no steps. The whole list is cleared when "
            "dusk ends, so what you put on it at night is waiting for you at dawn."),
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description":
                     "the item, in one line -- 'drive the fog north-east of R4'"},
            "why": {"type": "string", "description":
                    "optional: one line on what put this on the list"},
        }, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "strike",
        "description": (
            "Cross an item off today's list once it is done or once it stops being "
            "worth doing. Give the number the list shows against it. It stays visible "
            "as [x] so the numbering never shifts under you. Costs no steps."),
        "parameters": {"type": "object", "properties": {
            "n": {"type": "integer", "description":
                  "the number of the item, as your list shows it"},
            "why": {"type": "string", "description":
                    "optional: one line on how it went, or why you are dropping it"},
        }, "required": ["n"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": (
            "Write one entry of your memory, by name -- what you carry forward. This "
            "conversation and your reasoning are gone by morning and today's list is "
            "cleared when dusk ends; the map, the finished work and mission control's "
            "orders carry themselves, so do not copy those -- but what an interest "
            "turned out to be is kept nowhere else. An entry holds one subject: what "
            "you found, what you judged not worth the trip, a constraint you are "
            "keeping, what to do next. A name you already have REPLACES that entry, so "
            "send all of it; a new name adds one, up to the cap. Write sols as numbers -- "
            "'until the end of sol 3', never 'for two more sols'. Costs no steps."),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description":
                     "a short name for the subject, e.g. 'constraints' or 'the C'"},
            "text": {"type": "string", "description":
                     f"the whole entry, at most {settings.MEMORY_CHARS} characters; bullets are fine"},
            "why": {"type": "string", "description":
                    "optional: one line on what changed your mind"},
        }, "required": ["name", "text"]}}},
    {"type": "function", "function": {
        "name": "forget",
        "description": (
            "Drop one entry of your memory, by name, once it is no longer true or no "
            "longer needed. At the cap this is how you make room. Costs no steps."),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "the entry's name"},
            "why": {"type": "string", "description": "optional: one line on why it goes"},
        }, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "radio",
        "description": (
            "Call mission control by day, from anywhere: an answer to an urgent "
            "message, a question only they can answer, or news that changes the plan. "
            "It costs battery, as the system prompt says. It ends your turn, and their "
            "answer is your next message; while the line is open everything you say "
            "goes over it at the same cost. If nobody answers within a minute the line "
            "closes and the day is yours again. At dawn and night just talk."),
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description":
                     f"what you say to them, at most {settings.RADIO_CHARS} characters"},
            "why": {"type": "string", "description":
                    "optional: one line on why it cannot wait for the night"},
        }, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "end",
        "description": (
            "End the day. Call it beside the pad once the battery is down to what the "
            "trip back needed, or the clock is nearly out -- not because your list or "
            "the work you know of is done, since charge left tonight is wasted. The day "
            "is over the moment you do, and dusk follows. Until then you can drive as "
            "long as you like, one call at a time, reading the map each time."),
        "parameters": {"type": "object", "properties": {
            "why": {"type": "string", "description":
                    "optional: one line on where you have got to"},
        }, "required": []}}},
]

NAMES = [t["function"]["name"] for t in TOOLS]

def got_through(c):
    """Whether `c` was a radio call that reached the desk."""
    return c.name == "radio" and (c.result or "").startswith("RADIOED")


def tools_for(names=None):
    """The schemas for `names`, in TOOLS order; None is all. A skill the turn can't afford isn't offered at all."""
    if names is None:
        return TOOLS
    keep = set(names)
    return [t for t in TOOLS if t["function"]["name"] in keep]


# Read off each skill's schema: what it requires, its arguments in order, and their types.
REQUIRED = {}
ORDER = {}
TYPES = {}
for tool in TOOLS:
    skill = tool["function"]["name"]
    params = tool["function"]["parameters"]
    REQUIRED[skill] = set(params.get("required", ()))
    ORDER[skill] = list(params["properties"])
    TYPES[skill] = {}
    for arg, spec in params["properties"].items():
        TYPES[skill][arg] = spec["type"]

# A call the model typed into its reply instead of making it. It writes them as
# `goto(35, 25)` or as `call:goto{x:35,y:25}`, so both brackets and both `:` and `=` count.
# A skill that needs arguments looks like a call when one has a digit in it, or starts
# with a quote. One that needs none must have empty brackets or a `:` or `=` in them, so
# "at the end (of the sweep)" isn't read as `end`.
NEEDY = [n for n in NAMES if REQUIRED[n]]
FREE = [n for n in NAMES if not REQUIRED[n]]
NEEDY_CALL = r"\b(?:" + "|".join(NEEDY) + r")\s*[({]\s*(?:[^)}]*\d|[\"'])"
FREE_CALL = r"\b(?:" + "|".join(FREE) + r")\s*[({]\s*(?:[)}]|[^)}]*[:=])"
CALL_SHAPED = re.compile(NEEDY_CALL + "|" + FREE_CALL)


def looks_like_a_call(text):
    """Did the model write a call out in words rather than make one?"""
    return bool(CALL_SHAPED.search(text or "")) or bool(written_calls(text))


# Where each typed call opens. Where it closes is `_closes`'s job.
OPENS = re.compile(r"\b(" + "|".join(NAMES) + r")\s*[({]")


def _quote_opens(text, i):
    """Whether the quote at `i` starts a value, rather than being an apostrophe inside a word."""
    before = text[:i].rstrip()
    return not before or before[-1] in "({,=:"


def _closes(text, start):
    """Where the bracket just before `start` closes, skipping quoted and nested brackets. None if never."""
    depth, quote = 0, ""
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'" and _quote_opens(text, i):
            quote = ch
        elif ch in "({":
            depth += 1
        elif ch in ")}":
            if not depth:
                return i
            depth -= 1
    return None


def _fields(inside):
    """Split `35, 25, "why, with a comma"` on the commas that separate arguments."""
    out, cur, quote, depth = [], "", "", 0
    for i, ch in enumerate(inside):
        if quote:
            cur += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'" and _quote_opens(inside, i):
            quote = ch
            cur += ch
        elif ch == "," and not depth:
            out.append(cur)
            cur = ""
        else:
            if ch in "({":
                depth += 1
            elif ch in ")}":
                depth -= 1
            cur += ch
    out.append(cur)
    return [f.strip() for f in out if f.strip()]


def _unquote(v):
    v = v.strip()
    if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def written_call(text):
    """The first complete call the model typed instead of making: (name, args), or None."""
    calls = written_calls(text)
    return calls[0] if calls else None


def written_calls(text):
    """Every complete call the model typed instead of making, in order, as (name, args).
    They are run, not refused: about 3 turns in 10 type the call out, and a typed call is
    still her decision. skills.call still checks it. Complete means the skill's own
    required arguments are there."""
    out = []
    text = text or ""
    at = 0
    while True:
        m = OPENS.search(text, at)
        if m is None:
            break
        end = _closes(text, m.end())
        if end is None:
            at = m.end()
            continue
        name = m.group(1)
        inside = text[m.end():end]
        # Carry on past it, so a skill named inside quoted text isn't read as a call too.
        at = end + 1
        args = {}
        positional = []  # (value, whether it was quoted)
        for field in _fields(inside):
            key, eq, val = field.partition("=")
            if not eq:
                # `x:49` is the brace dialect; isidentifier stops a positional string with a colon being read as a keyword.
                key, eq, val = field.partition(":")
            if eq and key.strip().isidentifier():
                args[key.strip()] = _unquote(val)
            else:
                positional.append((_unquote(field), field[:1] in "\"'"))
        # A skill with no required argument has no positional form, so bracketed prose isn't a call.
        if not REQUIRED[name] and positional:
            continue
        free = [k for k in ORDER[name] if k not in args]
        # Words must be in quotes: "I will radio (if needed)" is a sentence, not a call.
        if (positional and free and TYPES[name][free[0]] == "string"
                and not positional[0][1]):
            continue
        for key, field in zip(free, positional):
            args[key] = field[0]
        if REQUIRED[name] <= set(args):
            out.append((name, args))
    return out


class Call:
    """One skill call, start to finish: what the tape records."""

    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.why = None
        self.result = None
        self.steps = 0
        self.gained = 0  # cells of map this call revealed (see _stuck)

    def __str__(self):
        shown = {k: v for k, v in self.args.items() if k != "why"}
        bits = ", ".join(f"{k}={v}" for k, v in shown.items())
        return f"{self.name}({bits})"


def _stuck(c, history):
    """Say so when calls have stopped telling her anything new. Two rules: the same call asked
    three times running without learning anything, or half or more of the steps of the last
    WINDOW step-spending calls revealing nothing. `distance` spends no steps, so it is only
    caught by the first rule."""
    if not c.gained:
        # The same question asked again, having learned nothing in between.
        same = 0
        for p in reversed(history):
            if p.gained or str(p) != str(c):
                break
            same += 1
        if same >= 2:
            return (f" You have asked for this {same + 1} times in a row and learned "
                    f"nothing new any of those times, so nothing has changed and the "
                    f"answer cannot change either. Do something different, or say what "
                    f"you are trying to achieve.")

    # A call that spent nothing wasted nothing, so it doesn't count either way.
    if not c.steps or c.name == "distance":
        return ""
    window = []
    for p in list(history) + [c]:
        if p.steps and p.name != "distance":
            window.append(p)
    window = window[-WINDOW:]
    if len(window) < WINDOW:
        return ""
    spent = sum(p.steps for p in window)
    wasted = sum(p.steps for p in window if not p.gained)
    if spent and wasted * 2 >= spent:
        return (f" Of your last {spent} steps, {wasted} bought no new map at all -- you "
                f"are going back over ground you have already covered. Somewhere on this "
                f"arena is still unexplored: aim at the ? and say what you are trying to "
                f"achieve.")
    return ""


def _runs(cells):
    """A set of cells as one line of runs a row, the way the map is written: `y15: x30-39`."""
    rows = {}
    for x, y in sorted(cells, key=lambda c: (c[1], c[0])):
        rows.setdefault(y, []).append(x)
    out = []
    for y, xs in rows.items():
        spans, lo, prev = [], xs[0], xs[0]
        for x in xs[1:] + [None]:
            if x != prev + 1:
                spans.append(f"x{lo}" if lo == prev else f"x{lo}-{prev}")
                lo = x
            prev = x
        out.append(f"y{y}: {', '.join(spans)}")
    return " | ".join(out)


def _count(world, kind):
    """Sizes and middles for everything revealed, in map order, never sorted by size."""
    area, s = world.here, world.survey
    want = (kind or "").strip().lower() or "both"
    if want not in ("rock", "fog", "both"):
        return (f"BAD_ARGS(kind must be 'rock', 'fog' or omitted, got {kind!r}). "
                f"Nothing happened.")
    lines = []
    if want in ("rock", "both"):
        found = s.rock(area)
        found.sort(key=lambda f: (centre_of(f[1])[1], centre_of(f[1])[0]))
        for fid, cells in found:
            mx, my = centre_of(cells)
            grew = s.since_last(fid, len(cells))
            more = f", {grew} of them new since you last asked" if grew else ""
            lines.append(f"  R{fid}: {len(cells)} cells, middle ({mx},{my}){more}")
        lines.insert(0, f"ROCK -- {len(found)} formations you have seen:")
    if want in ("fog", "both"):
        blobs = s.fog(area)
        blobs.sort(key=lambda c: (centre_of(c)[1], centre_of(c)[0]))
        if blobs:
            lines.append(f"FOG -- {len(blobs)} patches still unseen:")
        else:
            lines.append("FOG -- none left, you have seen the whole arena.")
        for c in blobs:
            lines.append(f"  {len(c)} cells, middle {centre_of(c)}")
    # A formation she may have named must not simply vanish.
    for gone, kept in s.take_merges():
        lines.append(f"  NOTE: R{gone} and R{kept} turned out to be one formation. "
                     f"It is all R{kept} now.")
    return "COUNT --\n" + "\n".join(lines)


def _count_cells(world, x, y):
    """Every cell of the one feature at (x, y), written as runs."""
    area, s = world.here, world.survey
    if not (0 <= x < area.w and 0 <= y < area.h):
        return f"BAD_ARGS(({x},{y}) is off the arena). Nothing happened."
    if (x, y) not in area.seen:
        for c in s.fog(area):
            if (x, y) in c:
                return (f"CELLS(fog, {len(c)} cells) -- {_runs(c)}. You have not been "
                        f"here, so what is under it is unknown.")
    if area.at(x, y) != "#":
        return (f"NOT_A_FEATURE(({x},{y})) -- that is open ground you have already "
                f"seen, not rock and not fog. Give a cell that belongs to the thing "
                f"you mean; the middle coordinate `count` gives you always does.")
    for fid, cells in s.rock(area):
        if (x, y) in cells:
            return f"CELLS(R{fid}, {len(cells)} cells) -- {_runs(cells)}"
    return f"NOT_A_FEATURE(({x},{y})) -- nothing revealed there."


def _work_line(o, short=False):
    """One piece of work as she reads it. An interest's text is never in it."""
    at = f"({o.cell[0]},{o.cell[1]})"
    if o.kind == "objective" and short:
        return f"{o.priority} priority at {at}, {o.cost} steps"
    if o.kind == "objective":
        return f"{o.priority} priority at {at}, {o.cost} steps of work"
    return f"an interest at {at}, {o.cost} steps to examine"


def _nothing_waiting(world, what):
    """Her known work, or her list, is all done. By day it goes on to say what the day still
    holds, so she doesn't take it as "you are finished"."""
    if world.phase != "day" or world.day_over:
        return f"{what}."
    area = world.here
    return (f"{what}, and the day is not over: {world.battery} steps of battery and "
            f"{world.time_left:.0f} seconds are left, and {area.w * area.h - len(area.seen)} of "
            f"the {area.w * area.h} cells are still unseen.")


def _execute(world):
    """Do the work the rover is beside and say what it cost, and for an interest what it was:
    the only place she is ever told. Every refusal says where her known work is."""
    left = world.objectives + [i for i in world.interests if i.found]
    o = world.adjacent_work()
    if o is None:
        if not left:
            return ("NOT_BESIDE_ONE -- the rover is not next to any work, so nothing "
                    "happened and nothing was spent. "
                    + _nothing_waiting(world, "No work you know of is waiting"))
        near = ", ".join(_work_line(p) for p in left)
        return (f"NOT_BESIDE_ONE -- the rover is not next to any work, so nothing "
                f"happened and nothing was spent. Still to do: {near}. Drive to one; "
                f"goto stops you alongside it, which is arriving.")

    at = f"({o.cell[0]},{o.cell[1]})"
    if world.battery <= 0:
        return (f"BATTERY_FLAT -- the work at {at} needs {o.cost} steps and the battery "
                f"is flat. Nothing was spent.")
    if world.day_over:
        return (f"OUT_OF_TIME -- the work at {at} needs {o.cost} steps and the day is "
                f"over. Nothing was spent. It will still be there tomorrow.")

    spent = world.execute(o)
    if not o.done:
        return (f"UNFINISHED(at={at}, steps={spent}) -- the work needs {o.cost} steps and "
                f"the battery ran flat after {spent}. It is not done and those steps are "
                f"gone. Start it with more in hand.")
    rest = [p for p in left if p is not o]
    if rest:
        tail = " Still to do: " + ", ".join(_work_line(p, short=True) for p in rest) + "."
    else:
        tail = " " + _nothing_waiting(world, "No other work you know of is waiting")
    if o.kind == "objective":
        return (f"EXECUTED(at={at}, priority={o.priority}, steps={spent}) -- the work is "
                f"done and the objective is off the map." + tail)
    return (f"EXAMINED(at={at}, steps={spent}) -- you found {o.text}. Your view keeps "
            f"where it was and nothing of what it was." + tail)


def _todo(world, text):
    """One item onto today's list. A duplicate is refused by name."""
    n = world.notes
    for i, (t, struck) in enumerate(n.todos, 1):
        if t.lower() == text.lower():
            crossed = ""
            if struck:
                crossed = " and already crossed off"
            return (f'ALREADY_ON_IT({i}) -- "{t}" is item {i} on your list{crossed}, so '
                    f'nothing was added and nothing was spent.')
    if len(n.todos) >= settings.TODO_MAX:
        return (f"LIST_FULL -- your list already holds {settings.TODO_MAX} items today and "
                f"this one was not added. {n.open} of them are still open: do one of "
                f"those, or say what you are trying to achieve.")
    i = n.add(text)
    world.record("todo", n=i, text=text)
    return (f'NOTED({i}) -- "{text}" is item {i} on your list, {n.open} still open. '
            f'Cross it off with strike({i}) when it is done.')


def _strike(world, i):
    """Cross one off, saying which in words so a wrong number is noticed."""
    n = world.notes
    if not n.holds(i):
        if not n.todos:
            return (f"NO_SUCH_ITEM({i}) -- your list is empty, nothing has been written "
                    f"on it today, and nothing happened.")
        return (f"NO_SUCH_ITEM({i}) -- your list is numbered 1 to {len(n.todos)}. "
                f"Nothing happened.")
    if n.struck(i):
        return (f'ALREADY_STRUCK({i}) -- "{n.text(i)}" was crossed off already, so '
                f'nothing happened.')
    n.strike(i)
    world.record("strike", n=i, text=n.text(i))
    if n.open:
        left = f"{n.open} still open on your list."
    else:
        left = _nothing_waiting(world, "Nothing is left open on your list")
    return f'STRUCK({i}) -- "{n.text(i)}" is crossed off. ' + left


def _remember(world, name, text):
    """One entry, written or replaced whole. The old length is quoted back, so a big cut shows."""
    n = world.notes
    if n.entry(name) is None and len(n.memory) >= settings.MEMORY_ENTRIES:
        return (f"MEMORY_FULL -- you already hold {settings.MEMORY_ENTRIES} entries, so nothing was "
                f"written. Forget one that is no longer true, or fold this into an entry "
                f"that covers it: {', '.join(n.memory)}.")
    had = n.remember(name, text)
    world.record("remember", name=name, chars=len(text), text=text)
    if had is None:
        what = f"a new entry: {len(n.memory)} of {settings.MEMORY_ENTRIES}. "
    else:
        what = f"this replaced the {had} characters that were there. "
    return (f"REMEMBERED({name}, {len(text)} characters) -- " + what
            + "It will still be in your memory tomorrow morning.")


def _forget(world, name):
    n = world.notes
    if not n.forget(name):
        held = ", ".join(n.memory) or "none"
        return (f"NOT_REMEMBERED({name}) -- there is no entry by that name, so nothing "
                f"changed. Your entries: {held}.")
    world.record("forget", name=name)
    return f"FORGOT({name}) -- {len(n.memory)} of {settings.MEMORY_ENTRIES} entries left."


def call(world, name, args, history=()):
    """Run one skill. Returns a finished Call; never raises. The steps are read off the world
    either side, so the tape's cost is what the day actually lost. `history` is the calls
    already made, used to notice a repeat that is going nowhere."""
    c = Call(name, dict(args or {}))
    before = world.steps

    if name not in NAMES:
        c.result = f"NO_SUCH_SKILL({name}) -- you have {' and '.join(NAMES)}"
        return c

    try:
        c.why = _why(c.args.get("why"))
        if name in ("goto", "distance", "count_cells"):
            x = _int("x", c.args.get("x"))
            y = _int("y", c.args.get("y"))
        if name in ("goto", "distance"):
            avoid = _avoid(c.args.get("avoid"))
        if name == "strike":
            n = _int("n", c.args.get("n"))
        if name == "todo":
            text = _text("text", c.args.get("text"), settings.TODO_CHARS)
        if name == "remember":
            text = _text("text", c.args.get("text"), settings.MEMORY_CHARS)
        if name == "radio":
            text = _text("text", c.args.get("text"), settings.RADIO_CHARS)
        if name in ("remember", "forget"):
            entry = _text("name", c.args.get("name"), 40)
    except BadArgs as e:
        c.result = f"BAD_ARGS({e}). Nothing happened and nothing was spent."
        return c

    if name == "end":
        # chat ends the turn; here `end` is a call like any other, so it lands on the tape in
        # order. The result is the same whoever is at the desk, since replay compares results.
        c.result = "END -- your turn is over."
        return c

    if name == "radio":
        c.result = _radio(world, text)
        return c

    if name == "count":
        c.result = _count(world, c.args.get("kind"))
        return c

    if name == "count_cells":
        c.result = _count_cells(world, x, y)
        return c

    if name == "execute":
        left = len(world.here.work())
        c.result = _execute(world)
        # Doing the work counts as gain, though it reveals nothing.
        if len(world.here.work()) < left:
            c.gained = 1
    elif name == "goto":
        c.result, c.gained = _goto(world, x, y, avoid)
    elif name == "todo":
        c.result = _todo(world, text)
    elif name == "strike":
        c.result = _strike(world, n)
    elif name == "remember":
        c.result = _remember(world, entry, text)
    elif name == "forget":
        c.result = _forget(world, entry)
    else:
        c.result = _distance(world, x, y, avoid)

    c.steps = world.steps - before
    c.result += _stuck(c, list(history))
    return c


def _radio(world, text):
    """A call to the desk. Whether anyone answers is autopilot's business, so the result is
    the same whoever replays it."""
    if world.phase != "day" or world.day_over:
        return ("NOT_NEEDED -- it is not day, so nothing was sent and nothing was "
                "spent. At dawn and night just say it; at dusk your last words "
                "are your report.")
    world.drain(settings.RADIO_STEPS)
    world.record("radio", text=text, at=list(world.pos), cost=settings.RADIO_STEPS)
    return (f"RADIOED -- mission control has it, and it cost {settings.RADIO_STEPS} steps "
            f"of battery. Your turn is over: their answer, if they give one, is "
            f"your next message, and while the line is open every reply you speak "
            f"costs the same. The day's clock does not stop for it.")


def _goto(world, x, y, avoid):
    """Drive there. Returns (result, gained): the cells revealed, or 1 for a drive that
    ended beside work or found an interest."""
    world.just_found = []
    r = nav.goto(world, x, y, avoid)
    gained = r.new or 0
    if not gained and world.adjacent_work():
        gained = 1
    result = str(r)
    if r.advice:
        result = f"{r} -- {r.advice}"
    if world.just_found:
        found = ", ".join(f"({cx},{cy})" for cx, cy in world.just_found)
        result += (f" On the way the rover came within sight of something worth a "
                   f"closer look at {found}, marked {INTEREST} on your map. Examine "
                   f"it to find out what it is.")
        gained = max(gained, 1)
    return result, gained


def _distance(world, x, y, avoid):
    """What the drive would cost: a floor, not a quote, said in words."""
    steps = nav.price(world, x, y, avoid)
    if steps is None:
        return (f"UNREACHABLE(to=({x},{y})) -- no route even assuming every "
                f"unseen cell is clear")
    return (f"DISTANCE(to=({x},{y}), steps>={steps}) -- planned as though the "
            f"fog were clear, so the drive takes at least that many steps and "
            f"more if there is rock in the way. {_left_today(world)}")


def _left_today(world):
    if world.phase == "day":
        clock = f"the day has {world.time_left:.0f} seconds left"
    elif world.phase == "dawn":
        clock = f"the day's {world.time_left:.0f} seconds start when it does"
    else:
        clock = "the day is over"
    return f"The battery holds {world.battery} steps and {clock}."


def budget_note(world, hops=""):
    """Added to a result when the day or the battery is nearly spent. `hops` is what the turn
    has left, sent with every result so she can plan around the cap."""
    out = hops
    if world.battery <= 0:
        out += (" The battery is flat, so the day is over. Only the pad recharges it.")
        return out
    if world.day_over:
        out += (" The day is over. Anything that drives or works will refuse from here.")
        return out
    # Warn about getting home while there's still time: within a tenth of a charge or of the day of what the trip back costs.
    back = nav.home_steps(world)
    low_b = world.battery <= (back or 0) + settings.BATTERY // 10
    low_t = (world.phase == "day" and
             world.time_left <= nav.drive_seconds(back or 0) + settings.DAY_SECONDS / 10)
    if back and (low_b or low_t):
        out += (f" {_left_today(world)} The pad is at least {back} steps away. Head "
                f"back now, or the rover is stranded tonight.")
    elif low_b or low_t:
        out += f" {_left_today(world)}"
    return out
