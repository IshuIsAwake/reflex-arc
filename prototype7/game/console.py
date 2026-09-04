"""The human's way into the planner: press T, type a goto.

It prints back the exact string gemma will get, so playtesting the planner and
reading a model transcript are the same activity. No pygame in here, so the tests
can drive it too.
"""

import re

import flyer
import nav
import skills

HELP = [
    "goto X Y                     drive there over the map you have",
    "goto X Y avoid=auto          ...dodging every X you marked. Visited only",
    "goto X Y avoid=(3,4),(5,6)   ...dodging these cells, this trip only",
    "distance X Y [avoid=...]     length floor and a reveal guess, costs no steps",
    "scout X Y                    fly the window there. Centre, not corner",
    "execute                      do the work at the objective you are beside",
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
    if verb not in ("goto", "distance", "dist", "scout", "execute"):
        return echo + [(f"no such command: {verb}   (try help)", "bad")]

    if verb == "execute":
        # The only verb that takes no cell: the objective is whichever one the rover
        # is already standing next to.
        c = skills.call(world, "execute", {})
        tone = "good" if c.result.startswith("EXECUTED") else "bad"
        world.say(c.result.split(" -- ")[0], tone)
        return echo + [(c.result, tone)]

    if not cells:
        return echo + [("needs an X and a Y -- try  goto 19 13", "bad")]

    x, y = cells[0]
    if verb == "scout":
        result, advice = flyer.scout(world, x, y)
        world.say(str(result), result.tone)
        out = [(str(result), result.tone)]
        if advice:
            out.append((f"   {advice}", result.tone))
        return echo + out

    if verb == "goto":
        result = nav.goto(world, x, y, avoid)
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
