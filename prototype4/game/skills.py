"""The skill interface: what gemma may ask for, and what it gets back.

The seam. `chat.py` knows nothing about `nav`, `nav` knows nothing about the model, and
this is the file the rover implementation swaps while both sides stay put.

    goto(x, y, why, avoid=...)       drive there. Costs a step a tile
    distance(x, y, why, avoid=...)   what it would cost. Costs nothing
    scout(x, y, why)                 the flyer's window. Costs steps, moves nothing

`scout` is the one skill that changes the map without changing the position, which is
the fact about it a model gets backwards -- so the schema says so before the first call
and the answer says so again after it. `flyer.py` owns it; this file only dispatches.

`avoid="auto"` is not offered: it skips cells gemma has marked, and there is no way to
mark one until `mark()` lands. Described loosely as "optional", she volunteered it
unasked and would have got NOT_VISITED for a reason she never intended.

Arguments are coerced generously and rejected noisily. An `avoid` list that quietly
parses to "avoid nothing" walks gemma through the cell she asked to dodge and never
says why. She emits the literal `'<nil>'` for an argument she means to omit, so that
string must never reach a `frozenset()`.

`BAD_ARGS` spends no steps -- a malformed call is a mistake, not an action.
"""

import re

import flyer
import nav
import settings as S

NIL = {"<nil>", "nil", "none", "null", "undefined", ""}

# How many step-spending calls `_stuck` weighs together, and it is 4 on purpose -- see
# the docstring. Half or more of the window's steps buying nothing is what it fires on.
WINDOW = 4


class BadArgs(Exception):
    """Loud on purpose. Caught in `call` and handed back as BAD_ARGS(...)."""


def _int(name, v):
    """Accept 7, "7", " 7 " and 7.0. Refuse everything else by name."""
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
    """One line if it is offered, and None if it is not.

    A rationale recorded before the outcome is a prediction; one offered afterwards is a
    story. The world never reads it -- its job is to sit on the tape with a timestamp
    earlier than the result.

    Not required. `chat.without_why` keeps it out of history, which also removed every
    example gemma had of a call carrying one, so she stopped sending it: 0 of 79 calls
    missing before, 16 of 21 after, each refusal costing a hop. The tape was what made
    the field useful, not the requirement.
    """
    if not isinstance(v, str) or v.strip().lower() in NIL:
        return None
    return " ".join(v.split())[:200]


def _avoid(v):
    """None, or a frozenset of cells. Never a silent empty set.

    "(3,4),(5,6)", "3,4 5,6" and [[3,4],[5,6]] all mean the same thing -- gemma
    punctuates differently every time and this is not a parser exercise. But an odd
    number of coordinates, or a string with no numbers in it at all, is a typo that
    would otherwise become a trip through the very cell it named.
    """
    if v is None:
        return None
    if isinstance(v, str):
        t = v.strip()
        if t.lower() in NIL:
            return None            # meant to omit it. The only silent empty.
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


# Sent to Ollama as `tools`. Every sentence here was paid for: without "walks the whole
# way" gemma stepped one tile per call for a run, and without "absolute" it cannot turn
# "go ten north" into a coordinate.
TOOLS = [
    {"type": "function", "function": {
        "name": "goto",
        "description": (
            "Drive to a cell in the arena. Coordinates are ABSOLUTE cells on the map "
            "in your view, never offsets from where you stand -- to move ten cells "
            "south, add ten to your own y and pass that. One call drives the whole "
            "way, however far it is, one step per tile out of the day's budget. "
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
            "price a trip before committing the day's steps to it."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column"},
            "y": {"type": "integer", "description": "absolute row"},
            "why": {"type": "string", "description":
                    "optional: one line on what you are weighing up"},
            "avoid": {"type": "string", "description":
                      "cells to treat as impassable, like '(3,4),(5,6)'. Usually omit."},
        }, "required": ["x", "y"]}}},
    {"type": "function", "function": {
        "name": "scout",
        "description": (
            "Send the flyer up to look at a square of ground you have not driven "
            "through, and put whatever it sees onto your map. Coordinates are "
            "ABSOLUTE and name the CENTRE of the window. It reveals a square "
            f"{2 * S.SCOUT_BOX + 1} cells across, costs {S.SCOUT_COST} steps out of "
            f"the same day the rover drives on, and does NOT move the rover. The "
            f"centre must be within {S.SCOUT_RANGE} cells of where the rover is "
            f"standing, and after a sortie the flyer must charge on the ground for "
            f"{S.SCOUT_RECHARGE} steps of driving before it can go up again. Aim it "
            "at ? -- a window over ground you have already mapped costs the same and "
            "reveals nothing."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column of the centre"},
            "y": {"type": "integer", "description": "absolute row of the centre"},
            "why": {"type": "string", "description":
                    "optional: one line on what you expect to be under there"},
        }, "required": ["x", "y"]}}},
]

NAMES = [t["function"]["name"] for t in TOOLS]

# A call the model wrote out instead of making. Built from NAMES so a skill added later
# cannot be forgotten. At Ollama's default temperature 3 of 12 turns came back with the
# call sitting in the reply text and no tool_calls at all -- nothing runs, nothing moves,
# and the pane shows a confident sentence. `MODEL_TEMP` is the fix; this is the backstop.
# The digit requirement keeps it off prose like "goto is the right tool here".
CALL_SHAPED = re.compile(r"\b(" + "|".join(NAMES) + r")\s*\(\s*[^)]*\d")


def looks_like_a_call(text):
    """Did the model write a call out in words rather than make one?"""
    return bool(CALL_SHAPED.search(text or ""))


# The same thing again, but parsed rather than merely detected.
WRITTEN = re.compile(r"\b(" + "|".join(NAMES) + r")\s*\(([^()]*)\)")


def _fields(inside):
    """Split `35, 25, "why, with a comma"` on the commas that separate arguments."""
    out, cur, quote = [], "", ""
    for ch in inside:
        if quote:
            cur += ch
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote, cur = ch, cur + ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [f.strip() for f in out if f.strip()]


def _unquote(v):
    v = v.strip()
    return v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'" else v


def written_call(text):
    """A complete call the model typed instead of making. Returns (name, args) or None.

    This runs it rather than refusing it. About 7 turns in 10 emit a real tool call and
    the rest type it out, and neither the prompt nor the sampler moves that number.
    There is nothing to invent: a written call names the skill and its arguments, so it
    is a decision the model made and Ollama failed to encode.

    `skills.call` still validates it, so a malformed recovery comes back BAD_ARGS like
    any other, and everything recovered this way is counted on the tape.

    Complete means x and y. A written `goto(25, 15)` is as complete as a tool call
    carrying the same two, and the recovery path must not be stricter than the real one.

    Accepts `goto(35, 25, "why")` and `goto(x=35, y=25, why="...")`.
    """
    for m in WRITTEN.finditer(text or ""):
        args, positional = {}, []
        for field in _fields(m.group(2)):
            key, eq, val = field.partition("=")
            if eq and key.strip().isidentifier():
                args[key.strip()] = _unquote(val)
            else:
                positional.append(_unquote(field))
        for key, val in zip(("x", "y", "why"), positional):
            args.setdefault(key, val)
        if {"x", "y"} <= set(args):
            return m.group(1), args
    return None


class Call:
    """One skill invocation, start to finish. What the tape records.

    `why` is captured before dispatch and `result` after, so the file preserves the
    order in which they were true. That ordering is the entire point of the field.
    """

    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.why = None
        self.result = None
        self.steps = 0
        self.gained = 0       # cells of map this call bought. See `_stuck`.

    def __str__(self):
        shown = {k: v for k, v in self.args.items() if k != "why"}
        bits = ", ".join(f"{k}={v}" for k, v in shown.items())
        return f"{self.name}({bits})"


def _stuck(c, history):
    """Say so when a run of calls has told the caller nothing it did not already know.

    The invariant is `gained == 0`, and it has been widened three times -- each earlier
    version checked a label rather than the fact. Firing only on `DONE` missed the same
    loop wearing `UNREACHABLE`; "spent no steps" missed 439 steps that revealed nothing.

    It does not require the calls to be identical. The loop measured was (0,49) to
    (0,10) and back, six times, so a run of identical calls never forms. That the
    targets differ is the point: casting about at random is not working either.

    **The second rule is a rate over a window, not a streak, since 2026-09-04.** It used
    to need three *consecutive* gainless calls, and that is the fourth time a detector
    here has been written around the case in front of it. Watched: two retreats after a
    BLOCKED, 19 and 24 steps, both revealing nothing, 24% of the sol between them -- and
    each sat between two calls that gained plenty, so the streak never formed and
    nothing was ever said. Waste that alternates with usefulness is invisible to a
    streak by construction.

    So: across the last WINDOW calls that spent steps, how many of those steps bought no
    map at all. Half or more and it says so. A rate is also why this does not need a
    floor on cells-per-step -- late in a sol a thin yield is honest, and punishing it
    would scold the model for the arena running out of fog rather than for going in
    circles.

    WINDOW is 4 rather than 2 or 3 deliberately. **This must never be a first-offence
    scold**: driving home to the pad is a gainless drive on purpose, and so is any
    deliberate repositioning. On the sol that prompted this, 4 fires once, on the second
    retreat, which is the point at which it stops being a manoeuvre and becomes a habit.

    **`distance` is exempt, and dropping that exemption would punish the one habit worth
    encouraging.** Pricing four routes before committing to any of them is four calls
    that reveal no map -- and it is exactly the comparison the skill exists for, and
    which gemma did not make once in twenty-seven calls. It spends no steps, so it never
    enters the window in either direction. Asking for the *same* price over and over is
    still caught, by the first rule, which is where it belongs.
    """
    if not c.gained:
        # The same question, asked again, having learned nothing in between. Covers
        # arriving beside something solid, an unreachable target, and pricing one trip
        # repeatedly -- three codes, one fact.
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

    # The window is over calls that actually spent steps -- `scout` counts beside `goto`
    # because both buy map with the day, and a call that spent nothing cannot have
    # wasted anything, so it is neither evidence nor an alibi.
    if not c.steps or c.name == "distance":
        return ""
    window = [p for p in list(history) + [c] if p.steps and p.name != "distance"][-WINDOW:]
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


def call(world, name, args, history=()):
    """Run one skill. Returns a finished `Call` -- never raises, never lies.

    A BAD_ARGS costs nothing. `world.steps` is read either side rather than trusted to
    the skill, so what the tape says a call spent is what the day actually lost.

    `history` is the calls already made, newest last, and is only read to notice a
    repeat that is going nowhere.
    """
    c = Call(name, dict(args or {}))
    before = world.steps

    if name not in NAMES:
        c.result = f"NO_SUCH_SKILL({name}) -- you have {' and '.join(NAMES)}"
        return c

    try:
        c.why = _why(c.args.get("why"))
        x = _int("x", c.args.get("x"))
        y = _int("y", c.args.get("y"))
        avoid = _avoid(c.args.get("avoid"))
    except BadArgs as e:
        c.result = f"BAD_ARGS({e}). Nothing happened and nothing was spent."
        return c

    if name == "scout":
        r, advice = flyer.scout(world, x, y)
        # Counted as gain the same way a drive is, so `_stuck` catches a run of
        # sorties over ground already mapped without needing to know what a sortie is.
        c.gained = r.new or 0
        c.result = f"{r} -- {advice}" if advice else str(r)
    elif name == "goto":
        r = nav.goto(world, x, y, avoid)
        c.gained = r.new or 0
        # `beside=` was meant to carry this on its own and did not. Watched
        # 2026-08-26: gemma read DONE(at=(10,15), beside=(10,16)) as a failure to
        # reach (10,16) and spent the rest of the run trying to step into a shop
        # counter. A field is not a sentence.
        c.result = f"{r} -- {r.advice}" if r.advice else str(r)
    else:
        # What it would cost and what it might be worth -- ordering journeys by length
        # answers the wrong question on an exploration mission. The two numbers are not
        # the same kind: steps is a floor, reveals is a guess that was low 9 times in 38
        # measured trips, because replanning round rock sweeps ground the straight route
        # never passed. Say which is which in words; a field is not a sentence.
        steps, reveals = nav.price(world, x, y, avoid)
        c.result = (f"UNREACHABLE(to=({x},{y})) -- no route even assuming every "
                    f"unseen cell is clear" if steps is None else
                    f"DISTANCE(to=({x},{y}), steps>={steps}, reveals~{reveals}) -- "
                    f"planned as though the fog were clear, so the drive takes at least "
                    f"that many steps, and may reveal rather more or rather less than "
                    f"that. You have {world.steps_left} steps left today")

    c.steps = world.steps - before
    c.result += _stuck(c, list(history))
    return c


def budget_note(world):
    """Handed back with a result when the day is spent, because OUT_OF_STEPS on its own
    reads as a failure of the call rather than the end of the day."""
    if world.day_over:
        return (" The day is over -- you have no steps left. Anything that costs "
                "steps will refuse from here.")
    if world.steps_left < S.DAY_STEPS // 10:
        return f" Only {world.steps_left} steps left today."
    return ""
