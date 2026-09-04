"""The human's way into the planner: press T, type a goto.

It prints back the exact string gemma will get, so playtesting the planner and
reading a model transcript are the same activity. No pygame in here, so the tests
can drive it too.
"""

import re

import nav
import skills

HELP = [
    "goto X Y                     drive there over the map you have",
    "goto X Y avoid=auto          ...dodging every X you marked. Visited only",
    "goto X Y avoid=(3,4),(5,6)   ...dodging these cells, this trip only",
    "goto X Y policy              ...driven by the trained RL buttons, not teleported",
    "step north|south|east|west   drive exactly one cell, like the model can",
    "press                        press the button where you stand",
    "distance X Y [avoid=...]     length floor and a reveal guess, costs no steps",
]


def _cells(text):
    """Every pair of numbers in a string, however it was punctuated. `15 10`,
    `15,10` and `(15,10)` all mean the same thing -- this is a console, not a
    parser exercise."""
    n = [int(t) for t in re.findall(r"-?\d+", text)]
    return list(zip(n[::2], n[1::2]))


def _parse(text):
    head, sep, tail = text.partition("avoid")
    avoid = None
    if sep:
        tail = tail.lstrip("= \t")
        avoid = "auto" if tail[:4].lower() == "auto" else frozenset(_cells(tail))
    words = head.split()
    return (words[0].lower() if words else ""), _cells(head), avoid


def run(world, text):
    """One typed line in, the lines to print out, as (text, tone) pairs."""
    echo = [(f"> {text.strip()}", "plain")]
    verb, cells, avoid = _parse(text)

    if verb in ("", "help", "?"):
        return echo + [(line, "plain") for line in HELP]
    if verb not in ("goto", "distance", "dist", "step", "press"):
        return echo + [(f"no such command: {verb}   (try help)", "bad")]

    if verb in ("step", "press"):
        # The model's own buttons, through the same validation it gets --
        # skills.call, not nav directly, so BAD_ARGS behaves identically.
        args = {}
        if verb == "step":
            m = re.search(r"\b(north|south|east|west|n|s|e|w)\b", text, re.I)
            args = {"direction": m.group(1)} if m else {}
        c = skills.call(world, verb, args)
        tone = "good" if c.result.startswith(("MOVED", "PRESSED")) else "bad"
        world.say(c.result, tone)   # so the HUD carries it too
        return echo + [(c.result, tone)]
    if not cells:
        return echo + [("needs an X and a Y -- try  goto 19 13", "bad")]

    x, y = cells[0]
    if verb == "goto":
        # `policy` is a console-only word, never a skill argument: it picks the
        # RL executor while gemma keeps the teleport one. "policy" holds no
        # digits so _cells never mistakes it for a coordinate.
        executor = "policy" if re.search(r"\bpolicy\b", text, re.I) else "teleport"
        try:
            result = nav.goto(world, x, y, avoid, executor=executor)
        except RuntimeError as e:
            return echo + [(str(e), "bad")]
        world.say(str(result), result.tone)   # so the HUD carries it too
        # The code form on one line, the clause on its own underneath -- the same
        # words gemma gets, laid out for a console that truncates at 88 characters.
        out = [(str(result), result.tone)]
        if result.advice:
            out.append((f"   {result.advice}", result.tone))
        return echo + out

    steps, reveals = nav.price(world, x, y, avoid)
    if steps is None:
        return echo + [("UNREACHABLE", "bad")]
    return echo + [(f"distance to ({x},{y}) >= {steps} steps, reveals~{reveals}", "plain")]
