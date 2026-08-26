"""The skill interface: what gemma is allowed to ask for, and what it gets back.

The blocking artifact of the whole project, in miniature. Schemas, argument coercion,
dispatch, and the one string that comes back. `chat.py` knows nothing about `nav` and
`nav` knows nothing about the model; this is the seam, and it is the file the rover
implementation swaps while everything either side of it stays put.

Two skills this slice, and the system prompt promises exactly these two:

    goto(x, y, why, avoid=...)       walk there. Costs a step a tile
    distance(x, y, why, avoid=...)   what it would cost. Costs nothing

`avoid="auto"` is deliberately **not** offered yet. It skips every cell gemma has
marked, and gemma has no way to mark a cell until `mark()` lands -- so advertising it
would describe a capability whose other half does not exist, which is the same failure
as a success code for a move that never happened. Measured 2026-08-26: with `avoid`
described loosely as "optional", gemma volunteered `avoid="auto"` unasked, which would
have come back NOT_VISITED for a reason it never intended. The description below earns
its length.

## Tolerant, and still loud

Every argument is coerced generously and rejected noisily. The failure this guards
against is specific: an `avoid` list that quietly parses to "avoid nothing" walks gemma
through the exact cell it asked to dodge, never says why, and the notes file takes the
blame for a parser bug. Gemma emits the literal string `'<nil>'` for an argument it
means to omit, so that string in particular must never reach a `frozenset()`.

`BAD_ARGS` spends no steps. A malformed call is a mistake, not an action, and charging
the day for it would make the parser part of the difficulty.
"""

import re

import nav
import settings as S

NIL = {"<nil>", "nil", "none", "null", "undefined", ""}


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
    """One line, and it is required.

    Settled in FINDINGS: a rationale recorded *before* the outcome is a prediction; one
    offered afterwards is a story. The world never reads it and it changes nothing --
    its whole job is to be on the tape with a timestamp earlier than the result. Calls
    that fail for want of one are counted, and that count is what the requirement costs.
    """
    if not isinstance(v, str) or v.strip().lower() in NIL:
        raise BadArgs("why is required -- one line, before you know how it turns out")
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


# Sent to Ollama as `tools`. Every sentence here was paid for.
#
# "walks the whole way" is in the description because it was in neither prompt nor
# schema on 2026-08-26 and gemma stepped one tile per call for a whole run -- free to
# fix, and it changes the shape of everything after it.
#
# "absolute" is there because the only way "go ten blocks north" works is if gemma
# does the arithmetic itself and passes the answer. Six for six on the probe.
TOOLS = [
    {"type": "function", "function": {
        "name": "goto",
        "description": (
            "Walk to a cell in the area you are in. Coordinates are ABSOLUTE cells on "
            "the map in your view, never offsets from where you stand -- to move ten "
            "cells south, add ten to your own y and pass that. One call walks the "
            "whole way, however far it is, one step per tile out of the day's budget. "
            "It plans over the map you have seen and assumes unseen ground is clear, "
            "so a wall you have never met will stop you: that is not a bug, it is how "
            "the map fills in, and the walls you hit come back in the answer. Aiming "
            "at something solid such as a shop or a terminal puts you next to it, "
            "which counts as arriving."),
        "parameters": {"type": "object", "properties": {
            "x": {"type": "integer", "description": "absolute column, 0 is the west edge"},
            "y": {"type": "integer", "description": "absolute row, 0 is the north edge"},
            "why": {"type": "string", "description":
                    "one line on what you expect from this, written before you find out"},
            "avoid": {"type": "string", "description":
                      "cells to treat as walls for this trip only, like '(3,4),(5,6)'. "
                      "Omit it entirely unless you have a specific cell in mind."},
        }, "required": ["x", "y", "why"]}}},
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
                    "one line on what you are weighing up"},
            "avoid": {"type": "string", "description":
                      "cells to treat as walls, like '(3,4),(5,6)'. Usually omit."},
        }, "required": ["x", "y", "why"]}}},
]

NAMES = [t["function"]["name"] for t in TOOLS]


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

    def __str__(self):
        shown = {k: v for k, v in self.args.items() if k != "why"}
        bits = ", ".join(f"{k}={v}" for k, v in shown.items())
        return f"{self.name}({bits})"


def _stuck(c, history):
    """Say so when the same call is repeated with nothing happening in between.

    **The rule is an invariant, not a list of codes.** A call that spends no steps
    cannot have changed the world, so an identical call after it is guaranteed the
    identical answer. That covers every way of going nowhere at once: arriving beside
    something solid, an UNREACHABLE, or pricing the same trip twice.

    It was written narrower and the narrowness showed. The first version only fired on
    `DONE`, because that was the case being watched -- gemma asked for `goto(3,8)`
    seven times and was told `DONE(beside=(3,8), steps=0)` every time. Reading a live
    tape on 2026-08-26 turned up the same loop wearing a different code: five
    consecutive `goto(0,5)` calls, five `UNREACHABLE(at=(13,5), steps=0)`, and no
    nudge, because the detector was checking the label instead of the fact.

    Only a *consecutive* run counts, and any call that spent a step ends it -- once
    the world has moved, the same question may honestly have a different answer.

    None of this fixes the cause. Gemma repeats because it wants to *use* what it has
    reached and `interact` does not exist; this only stops the world agreeing
    pleasantly with a question already answered.
    """
    if c.steps:
        return ""
    same = 0
    for p in reversed(history):
        if p.steps or str(p) != str(c):
            break
        same += 1
    if same < 2:
        return ""
    return (f" You have asked for this {same + 1} times in a row and spent no steps "
            f"doing it, so nothing has changed and the answer cannot change either. "
            f"Do something different, or say what you are trying to achieve.")


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

    if name == "goto":
        r = nav.goto(world, x, y, avoid)
        # `beside=` was meant to carry this on its own and did not. Watched
        # 2026-08-26: gemma read DONE(at=(10,15), beside=(10,16)) as a failure to
        # reach (10,16) and spent the rest of the run trying to step into a shop
        # counter. A field is not a sentence.
        c.result = f"{r} -- {r.advice}" if r.advice else str(r)
    else:
        steps = nav.distance(world, x, y, avoid)
        c.result = (f"UNREACHABLE(to=({x},{y})) -- no route even assuming every "
                    f"unseen cell is clear" if steps is None else
                    f"DISTANCE(to=({x},{y}), steps={steps}, optimistic) -- "
                    f"you have {world.steps_left} steps left today")

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
