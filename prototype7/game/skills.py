"""The skill interface: what gemma may ask for, and what it gets back.

The seam. `chat.py` knows nothing about `nav`, `nav` knows nothing about the model, and
this is the file the rover implementation swaps while both sides stay put.

    goto(x, y, why, avoid=...)       drive there. Costs a step a tile
    distance(x, y, why, avoid=...)   what it would cost. Costs nothing
    scout(x, y, why)                 the flyer's window. Costs steps, moves nothing
    execute(why)                     the work at the objective you are beside

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
from world import centre_of

NIL = {"<nil>", "nil", "none", "null", "undefined", ""}

# How many step-spending calls `_stuck` weighs together. 4 so that a single deliberate
# repositioning is never a first-offence scold; half or more of the window's steps
# buying nothing is what it fires on.
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
    {"type": "function", "function": {
        "name": "execute",
        "description": (
            "Do the work at the objective the rover is standing next to. Drive to the "
            "objective first -- goto puts you alongside it, which is arriving -- then "
            "call this. It costs that objective's own number of steps, listed with it "
            "in your view, and the objective is finished and gone once it is paid. "
            "Standing anywhere else this does nothing and costs nothing."),
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
        "name": "end",
        "description": (
            "Hand the conversation back. Until you call this you are the only one "
            "talking, so you can drive as long as you like -- one call at a time, "
            "reading the map each time. Call it when you have finished what you were "
            "asked, or when you want to check something with the crew. It ends your "
            "turn, not the sol: the day runs until the steps do."),
        "parameters": {"type": "object", "properties": {
            "why": {"type": "string", "description":
                    "optional: one line on where you have got to"},
        }, "required": []}}},
]

NAMES = [t["function"]["name"] for t in TOOLS]


def tools_for(names=None):
    """The schemas for `names`, in TOOLS order. `None` is all of them.

    A skill the turn can no longer afford is left out of the request rather than
    refused after the fact. A refusal is one line arriving into a prompt whose other
    6,700 tokens are a map that has not changed since the last one, and it loses:
    watched 2026-09-04, the 31B re-sent the identical `goto` three times after being
    told it had no drives left, then had the turn ended for it. What is not offered
    cannot be asked for, so the cap stops being something to argue with.
    """
    if names is None:
        return TOOLS
    keep = set(names)
    return [t for t in TOOLS if t["function"]["name"] in keep]


# A call the model wrote out instead of making. Built from NAMES so a skill added later
# cannot be forgotten. At Ollama's default temperature 3 of 12 turns came back with the
# call sitting in the reply text and no tool_calls at all -- nothing runs, nothing moves,
# and the pane shows a confident sentence. `MODEL_TEMP` is the fix; this is the backstop.
# The digit requirement keeps it off prose like "goto is the right tool here".
#
# Braces as well as parens, and `:` as well as `=`, because on 2026-09-04 `gemma4:31b-cloud`
# stopped populating `tool_calls` at all and began writing every call into the content as
# `call:goto{x:49,y:0,why:...}`. Verified against a one-line prompt with the stock schema:
# the local `gemma4:e4b` answers the same request with a real tool call and empty content,
# so it is that model behind that endpoint, not the schema and not the view.
#
# What each skill actually needs, read off its own schema rather than assumed. `count`
# and `end` require nothing, so a recovery path demanding x and y could never return
# either -- which with a model narrating *every* call means she can never count and
# never hand back a turn.
REQUIRED = {t["function"]["name"]: set(t["function"]["parameters"].get("required", ()))
            for t in TOOLS}

# A skill that needs arguments is recognised by having one with a digit in it. A skill
# that needs none cannot be, so it has to look like a call some other way: empty
# brackets, or something with a `:` or `=` in them. Otherwise "at the end (of the sweep)"
# reads as a call to `end` and quietly gives the turn away.
_needy = [n for n in NAMES if REQUIRED[n]]
_free = [n for n in NAMES if not REQUIRED[n]]
CALL_SHAPED = re.compile("|".join(
    ([r"\b(?:" + "|".join(_needy) + r")\s*[({]\s*[^)}]*\d"] if _needy else [])
    + ([r"\b(?:" + "|".join(_free) + r")\s*[({]\s*(?:[)}]|[^)}]*[:=])"] if _free else [])))


def looks_like_a_call(text):
    """Did the model write a call out in words rather than make one?"""
    return bool(CALL_SHAPED.search(text or ""))


# The same thing again, but parsed rather than merely detected.
WRITTEN = re.compile(r"\b(" + "|".join(NAMES) + r")\s*[({]([^(){}]*)[)}]")


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

    Complete means whatever that skill's own schema calls required -- `x` and `y` for a
    `goto`, nothing at all for `count` or `end`. A written `goto(25, 15)` is as complete
    as a tool call carrying the same two, and the recovery path must not be stricter than
    the real one.

    Accepts `goto(35, 25, "why")`, `goto(x=35, y=25, why="...")`, and the brace dialect
    `call:goto{x:35,y:25,why:...}` that `gemma4:31b-cloud` switched to on 2026-09-04.
    """
    for m in WRITTEN.finditer(text or ""):
        args, positional = {}, []
        # Blank fields dropped, so `end()` parses to no arguments rather than to one
        # empty positional that then lands in `x`.
        for field in (f for f in _fields(m.group(2)) if f.strip()):
            key, eq, val = field.partition("=")
            if not eq:
                # `x:49` is the brace dialect. `isidentifier` below is what stops a
                # positional string with a colon in it being read as a keyword.
                key, eq, val = field.partition(":")
            if eq and key.strip().isidentifier():
                args[key.strip()] = _unquote(val)
            else:
                positional.append(_unquote(field))
        for key, val in zip(("x", "y", "why"), positional):
            args.setdefault(key, val)
        # A skill that takes no required argument has no positional form either, so
        # bracketed prose -- "at the end (of the sweep)" -- is text and not a call.
        if not REQUIRED[m.group(1)] and positional:
            continue
        if REQUIRED[m.group(1)] <= set(args):
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

    **The second rule is a rate over a window, not a streak.** It used to need three
    *consecutive* gainless calls. Watched: two retreats after a BLOCKED, 19 and 24
    steps, both revealing nothing, 24% of the sol between them -- and each sat between
    two calls that gained plenty, so the streak never formed and nothing was said.
    Waste that alternates with usefulness is invisible to a streak by construction.

    WINDOW is 4 rather than 2 or 3 deliberately. **This must never be a first-offence
    scold**: driving home to the pad is a gainless drive on purpose, and so is any
    deliberate repositioning.

    **`distance` is exempt, and dropping that exemption would punish the one habit
    worth encouraging.** Pricing four routes before committing to any of them is four
    calls that reveal no map -- and it is exactly the comparison the skill exists for,
    and which gemma did not make once in twenty-seven calls. It spends no steps, so it
    never enters the window either way. Asking for the *same* price over and over is
    still caught by the first rule, which is where it belongs.
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


def _runs(cells):
    """A set of cells as one line of coordinate runs a row, the way the map is written.

    Thirty coordinates in a row is a wall she has to parse; `y15: x30-39` is the same
    fact in the notation she is already reading the map in.
    """
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
    """Sizes and middles for everything revealed. Facts only -- deliberately unranked.

    Listed in map order, north to south, not by size. She is the one weighing which
    formation matters; a list already sorted by the answer would be doing that for her.
    """
    a, s = world.here, world.survey
    want = (kind or "").strip().lower() or "both"
    if want not in ("rock", "fog", "both"):
        return (f"BAD_ARGS(kind must be 'rock', 'fog' or omitted, got {kind!r}). "
                f"Nothing happened.")
    lines = []
    if want in ("rock", "both"):
        found = s.rock(a)
        found.sort(key=lambda f: (centre_of(f[1])[1], centre_of(f[1])[0]))
        for fid, cells in found:
            mx, my = centre_of(cells)
            grew = s.since_last(fid, len(cells))
            more = f", {grew} of them new since you last asked" if grew else ""
            lines.append(f"  R{fid}: {len(cells)} cells, middle ({mx},{my}){more}")
        lines.insert(0, f"ROCK -- {len(found)} formations you have seen:")
    if want in ("fog", "both"):
        blobs = s.fog(a)
        blobs.sort(key=lambda c: (centre_of(c)[1], centre_of(c)[0]))
        fog = [f"  {len(c)} cells, middle {centre_of(c)}" for c in blobs]
        lines.append(f"FOG -- {len(blobs)} patches still unseen:" if blobs
                     else "FOG -- none left, you have seen the whole arena.")
        lines += fog
    # A formation she may have named out loud must not simply stop existing.
    for gone, kept in s.take_merges():
        lines.append(f"  NOTE: R{gone} and R{kept} turned out to be one formation. "
                     f"It is all R{kept} now.")
    return "COUNT --\n" + "\n".join(lines)


def _count_cells(world, x, y):
    """Every cell of the one feature at (x, y), written as runs."""
    a, s = world.here, world.survey
    if not (0 <= x < a.w and 0 <= y < a.h):
        return f"BAD_ARGS(({x},{y}) is off the arena). Nothing happened."
    if (x, y) not in a.seen:
        for c in s.fog(a):
            if (x, y) in c:
                return (f"CELLS(fog, {len(c)} cells) -- {_runs(c)}. You have not been "
                        f"here, so what is under it is unknown.")
    if a.at(x, y) != "#":
        return (f"NOT_A_FEATURE(({x},{y})) -- that is open ground you have already "
                f"seen, not rock and not fog. Give a cell that belongs to the thing "
                f"you mean; the middle coordinate `count` gives you always does.")
    for fid, cells in s.rock(a):
        if (x, y) in cells:
            return f"CELLS(R{fid}, {len(cells)} cells) -- {_runs(cells)}"
    return f"NOT_A_FEATURE(({x},{y})) -- nothing revealed there."


def _execute(world):
    """Do the work at the objective the rover is beside, and say what it cost.

    Every refusal says where the nearest unfinished objective is and that nothing was
    spent. A bare code leaves a 4B model nothing to act on, which is the lesson
    `DONE(beside=...)` cost four days: a field is not a sentence.
    """
    left = [o for o in world.objectives if not o.done]
    o = world.adjacent_objective()
    if o is None:
        if not left:
            return ("NOTHING_TO_DO -- every objective on this arena is finished. "
                    "Nothing was spent.")
        near = ", ".join(f"{p.priority} priority at ({p.cell[0]},{p.cell[1]}), "
                         f"{p.cost} steps of work" for p in left)
        return (f"NOT_BESIDE_ONE -- the rover is not next to an objective, so nothing "
                f"happened and nothing was spent. Still to do: {near}. Drive to one; "
                f"goto stops you alongside it, which is arriving.")

    if world.day_over:
        return (f"OUT_OF_STEPS -- the {o.priority}-priority objective at "
                f"({o.cell[0]},{o.cell[1]}) needs {o.cost} steps and the day is over. "
                f"Nothing was spent. It will still be there tomorrow.")

    spent = world.execute(o)
    if not o.done:
        return (f"UNFINISHED(at=({o.cell[0]},{o.cell[1]}), steps={spent}) -- the work "
                f"needs {o.cost} steps and the day ran out after {spent}. The objective "
                f"is not done and the steps are gone. Start it earlier tomorrow.")
    rest = [p for p in left if p is not o]
    tail = (" Nothing else is left to do." if not rest else
            " Still to do: " + ", ".join(
                f"{p.priority} priority at ({p.cell[0]},{p.cell[1]}), {p.cost} steps"
                for p in rest) + ".")
    return (f"EXECUTED(at=({o.cell[0]},{o.cell[1]}), priority={o.priority}, "
            f"steps={spent}) -- the work is done and the objective is off the map."
            + tail)


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
        if name in ("goto", "distance", "count_cells", "scout"):
            x = _int("x", c.args.get("x"))
            y = _int("y", c.args.get("y"))
        if name in ("goto", "distance"):
            avoid = _avoid(c.args.get("avoid"))
    except BadArgs as e:
        c.result = f"BAD_ARGS({e}). Nothing happened and nothing was spent."
        return c

    if name == "end":
        # The turn is ended by `chat`, which is the only thing that knows what a turn
        # is. Here it is a call like any other so that it lands on the tape in order
        # with the rest, rather than as an event beside them.
        c.result = "END -- your turn is over and the crew can speak again."
        return c

    if name == "count":
        c.result = _count(world, c.args.get("kind"))
        return c

    if name == "count_cells":
        c.result = _count_cells(world, x, y)
        return c

    if name == "execute":
        left = len(world.here.objectives)
        c.result = _execute(world)
        # Doing the work is the point of the sol, so it counts as gain even though it
        # reveals nothing -- otherwise `_stuck` reads the whole mission as waste.
        c.gained = 1 if len(world.here.objectives) < left else 0
    elif name == "scout":
        r, advice = flyer.scout(world, x, y)
        # Counted as gain the same way a drive is, so `_stuck` catches a run of sorties
        # over ground already mapped without needing to know what a sortie is.
        c.gained = r.new or 0
        c.result = f"{r} -- {advice}" if advice else str(r)
    elif name == "goto":
        r = nav.goto(world, x, y, avoid)
        c.gained = r.new or 0
        # A drive that ends beside work still to do bought something, even over ground
        # already mapped. Without this the scold fires on the one journey the sol is
        # actually for -- going to an objective is not casting about.
        if not c.gained and world.adjacent_objective():
            c.gained = 1
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


def budget_note(world, hops=""):
    """Handed back with a result when the day is spent, because OUT_OF_STEPS on its own
    reads as a failure of the call rather than the end of the day.

    `hops` is what is left of the turn's allowance, and it rides on *every* result
    rather than only on the last one. A cap she is told about only once she has hit it
    is a cap she cannot plan around -- the 31B spent half a run discovering it by
    having calls refused.
    """
    out = hops
    if world.day_over:
        out += (" The day is over -- you have no steps left. Anything that costs "
                "steps will refuse from here.")
    elif world.steps_left < S.DAY_STEPS // 10:
        out += f" Only {world.steps_left} steps left today."
    return out
