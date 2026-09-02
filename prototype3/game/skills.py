"""The skill interface: what gemma is allowed to ask for, and what it gets back.

The blocking artifact of the whole project, in miniature. Schemas, argument coercion,
dispatch, and the one string that comes back. `chat.py` knows nothing about `nav` and
`nav` knows nothing about the model; this is the seam, and it is the file the rover
implementation swaps while everything either side of it stays put.

Two skills this slice, and the system prompt promises exactly these two:

    goto(x, y, why, avoid=...)       drive there. Costs a step a tile
    distance(x, y, why, avoid=...)   what it would cost. Costs nothing

Copied from prototype 1 essentially unchanged. Every sentence in `TOOLS` below was
paid for by a live run; the edits here are the nouns, not the rules.

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
    """One line if it is offered, and None if it is not.

    Settled in FINDINGS and unchanged: a rationale recorded *before* the outcome is a
    prediction; one offered afterwards is a story. The world never reads it and it
    changes nothing -- its whole job is to be on the tape with a timestamp earlier than
    the result, and it still does that whenever it arrives.

    **It stopped being required on 2026-09-01, because requiring it broke the turn.**
    A5 took `why` out of the assistant turns that re-enter history (`chat.without_why`),
    which was right for its own reasons -- but it also removed every example gemma had
    of a call that carried one. She stopped sending the field: **0 of 79 calls missing
    it before A5, 22 of 52 after, and 16 of 21 in `runs/20260901-000753/`**, six times
    in a row on one turn, with the error text failing to recover her every time. Each
    refusal also cost a hop (`chat.py:652` counts before the call runs), so the turn
    died to the cap without the rover moving.

    The requirement was never what made the field useful; the tape was. So the field
    stays, the record stays, and omission stops being punished. What the requirement
    actually bought is now measurable as the rate at which she supplies it unasked.
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
]

NAMES = [t["function"]["name"] for t in TOOLS]

# A call the model *wrote out* instead of making. Built from NAMES so a skill added
# later cannot be forgotten here.
#
# Measured 2026-08-29: with `temperature` left to Ollama's default, 3 of 12 turns came
# back with `goto(25, 15, "Driving north...")` sitting in the reply text and no
# tool_calls at all. Nothing runs, nothing moves, and the pane shows a confident
# sentence -- which is **the vanishing call again**, the shape FINDINGS keeps recording:
# an answer with no outcome leaves the caller nothing to correct.
#
# `MODEL_TEMP` is the actual fix and this is the backstop. It is deliberately a
# *detector*, not a parser: executing a call the model only narrated would be inventing
# intent, and a tolerant-but-silent path is the exact failure this file exists to avoid.
# Telling it the call did not run costs one turn and is honest.
#
# The digit requirement keeps it off ordinary prose -- "goto is the right tool here" is
# a sentence about a skill, not a call.
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

    **This runs it rather than refusing it, and that is a deliberate reversal.** The
    first version detected a written call and told the model off, on the grounds that
    executing one would be inventing intent. Measured 2026-08-29 across five prompts at
    two temperatures: about **7 turns in 10** emit a real tool call and the rest type it
    out, and neither the prompt nor the sampler moves that number. Refusing costs a
    whole round trip and, measured, often produces the same reply again.

    There is nothing to invent. `goto(35, 25, "to explore the terrain east")` names the
    skill and every required argument; it is a decision the model made and Ollama failed
    to encode. Reading it is not guessing. **Only a complete call qualifies**, and
    `skills.call` still validates every one of them, so a malformed recovery comes back
    BAD_ARGS like any other. Everything recovered this way is counted and labelled in
    the pane and on the tape, because a call that arrived by an unusual road is exactly
    the kind of thing a later run needs to be able to see.

    **Complete now means x and y**, following `_why` on 2026-09-01. It used to mean all
    three, on the reasoning that a call with no stated reason is not a decision anybody
    can act on -- but that was the schema's rule leaking into the reader. A written
    `goto(25, 15)` is exactly as complete as a tool call carrying the same two
    arguments, and refusing one while running the other would make the recovery path
    stricter than the real one.

    Accepts both shapes the model uses: `goto(35, 25, "why")` and
    `goto(x=35, y=25, why="...")`.
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

    **The rule is an invariant, and this is the third time it has had to be widened.**
    Each version was written around the failure in front of it and missed the next one:

    1. Fired only on `DONE`, because `DONE(beside=(3,8), steps=0)` seven times running
       was the loop being watched. A live tape then showed the same loop wearing a
       different code -- five `goto(0,5)`, five `UNREACHABLE(at=(13,5), steps=0)`, no
       nudge -- because it was checking the label instead of the fact.
    2. So it became *spent no steps*: a call that costs nothing cannot have changed the
       world, so an identical call after it is guaranteed the identical answer. That
       covered arriving beside something solid, an unreachable target and pricing the
       same trip twice, all at once.
    3. And it could not fire at all on 2026-08-29, when gemma spent 439 steps learning
       nothing. **Every one of those drives spent forty-nine.** Costing something is
       not the same as achieving something, and "spent no steps" was the label a second
       time over.

    So the invariant is now *this call told you nothing you did not already know* --
    `gained` is nought -- which subsumes "spent nothing", since a call that never moved
    can never have revealed anything.

    **And it no longer requires the calls to be identical**, which is the other half of
    what made version 3 blind. The loop measured was (0,49) to (0,10) and back, six
    times: alternating, so a run of *identical* calls never forms, and no test of what
    each call gained would have helped. What the caller needs telling is that the last
    few calls between them bought nothing -- the targets being different is exactly the
    point, because it means casting about at random is not working either.

    Only a consecutive run counts, and any call that gained something ends it. That
    matters more than it looks: driving home to the pad is a gainless drive on purpose,
    and so is any deliberate repositioning, so this must never be a first-offence
    scold.

    **`distance` is exempt from the second rule, and dropping that exemption would
    punish the one habit worth encouraging.** Pricing four routes before committing to
    any of them is four calls that reveal no map -- and it is exactly the comparison
    the skill exists for, and which gemma did not make once in twenty-seven calls. So a
    price check neither extends a run of gainless drives nor breaks one: it changes
    nothing about the map, in either direction. Asking for the *same* price over and
    over is still caught, by the first rule, which is where it belongs.
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

    if c.name == "goto" and not c.gained:
        drives = [c]
        for p in reversed(history):
            if p.name != "goto":
                continue                     # a price check is neither way
            if p.gained:
                break
            drives.append(p)
        if len(drives) >= 3:
            spent = sum(p.steps for p in drives)
            return (f" That is {len(drives)} drives in a row that revealed nothing new, "
                    f"between them costing {spent} steps. You are covering ground you "
                    f"have already mapped. Somewhere on this arena is still unexplored "
                    f"-- go there, or say what you are trying to achieve.")
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

    if name == "goto":
        r = nav.goto(world, x, y, avoid)
        c.gained = r.new or 0
        # `beside=` was meant to carry this on its own and did not. Watched
        # 2026-08-26: gemma read DONE(at=(10,15), beside=(10,16)) as a failure to
        # reach (10,16) and spent the rest of the run trying to step into a shop
        # counter. A field is not a sentence.
        c.result = f"{r} -- {r.advice}" if r.advice else str(r)
    else:
        # What it would cost *and* what it might be worth. Ordering journeys by length
        # answers the wrong question on an exploration mission, which is the likeliest
        # reason this skill went unused for a whole sol.
        #
        # **The two numbers are not the same kind of number, and one word covering both
        # was a lie.** `optimistic` used to sit here claiming the drive could only come
        # out longer and the reveal only smaller. The first half holds; the second was
        # false nine times in thirty-eight measured trips, because replanning round rock
        # sweeps ground the straight route never passed. See `nav.price`. So say which is
        # a floor and which is a guess, in words, because a field is not a sentence.
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
