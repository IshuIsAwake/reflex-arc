"""The operator's terminal (T). goto, distance and execute print exactly what the model
would get back; comms, sols and place run the mission and come in from main.py as `desk`."""

import re

import nav
import skills

HELP = [
    "comms on|off                 someone at the desk, or nobody (C does the same)",
    "sols N                       N more sols in the mission",
    "place X Y PRIORITY COST      an objective on mapped ground: high|medium|low, steps",
    "place X Y interest COST TEXT hide an interest; TEXT is what examining it finds",
    "goto X Y                     drive there over the map you have",
    "goto X Y avoid=auto          ...dodging every X you marked. Visited only",
    "goto X Y avoid=(3,4),(5,6)   ...dodging these cells, this trip only",
    "distance X Y [avoid=...]     length floor and a reveal guess, costs no steps",
    "execute                      do the work you are beside",
]


def _cells(text):
    """Every pair of numbers in a string: `15 10`, `15,10` and `(15,10)` all work."""
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


def run(world, text, desk=None):
    """One typed line in; the lines to print out, as (text, tone) pairs."""
    echo = [(f"> {text.strip()}", "plain")]
    text = text.strip().lstrip("/")
    verb, cells, avoid = _parse(text)

    if verb in ("", "help", "?"):
        return echo + [(line, "plain") for line in HELP]
    if desk and verb in desk:
        rest = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
        bad, said = desk[verb](rest)
        return echo + [(bad, "bad")] if bad else echo + [(said, "good")]
    if verb not in ("goto", "distance", "dist", "execute"):
        return echo + [(f"no such command: {verb}   (try help)", "bad")]

    if verb == "execute":
        c = skills.call(world, "execute", {})
        tone = "good" if c.result.startswith(("EXECUTED", "EXAMINED")) else "bad"
        world.say(c.result.split(" -- ")[0], tone)
        return echo + [(c.result, tone)]

    if not cells:
        return echo + [("needs an X and a Y -- try  goto 19 13", "bad")]

    x, y = cells[0]
    if verb == "goto":
        result = nav.goto(world, x, y, avoid)
        world.say(str(result), result.tone)  # so the HUD carries it too
        # The advice on its own line, since the console cuts lines at 88 characters.
        out = [(str(result), result.tone)]
        if result.advice:
            out.append((f"   {result.advice}", result.tone))
        return echo + out

    steps = nav.price(world, x, y, avoid)
    if steps is None:
        return echo + [("UNREACHABLE", "bad")]
    return echo + [(f"distance to ({x},{y}) >= {steps} steps", "plain")]
