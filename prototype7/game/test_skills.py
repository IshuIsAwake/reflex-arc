"""The skill interface: tolerant in, loud out.

    .venv/bin/python game/test_skills.py

The whole file is about one failure. An `avoid` list that quietly parses to "avoid
nothing" drives gemma through the exact cell it asked to dodge, says nothing, and the
notes file takes the blame for a parser bug. Every rejection here has to be audible,
and none of them may cost a step -- a malformed call is a mistake, not an action.

Gemma emits the literal string '<nil>' for an argument it means to omit. That is not
hypothetical; it was watched on 2026-08-26.
"""

import re
import sys

import settings as S
import skills
from world import World

PAD = {"x": 15, "y": 16}    # solid, one cell south of where the rover lands


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def test_a_plain_goto_drives():
    print("goto")
    w = World()
    w.pos = (15, 12)
    c = skills.call(w, "goto", {**PAD, "why": "back to the pad"})
    ok = check("arrives", c.result.startswith("DONE"), c.result)
    # The pad is solid, so this lands beside it. Without `beside=` in the answer,
    # DONE(at=(15,15)) for a goto(15,16) reads as failure and gets reissued.
    ok &= check("and says it stopped beside a solid target", "beside=" in c.result)
    # ...and the field alone was not enough. Watched 2026-08-26: gemma read the beside=
    # form as failure and spent the rest of the run trying to drive into a counter.
    # Arrival has to be stated, not encoded.
    ok &= check("in words as well as a field", "IS arriving" in c.result, c.result)

    already = skills.call(w, "goto", {"x": w.pos[0], "y": w.pos[1], "why": "again"})
    # A free no-op is how a confused model bounces between two cells forever.
    ok &= check("a goto to where you stand says so", "already standing" in already.result,
                already.result)
    ok &= check("and costs nothing", already.steps == 0)
    ok &= check("the why is kept", c.why == "back to the pad")
    ok &= check("steps were charged", c.steps > 0, f"{c.steps}")
    return ok


def _repeat(w, args, n=3, name="goto"):
    history = []
    for _ in range(n):
        history.append(skills.call(w, name, args, history=history))
    return history


def test_going_nowhere_twice_is_said_out_loud():
    print("the same call, again")
    w = World()
    args = {**PAD, "why": "the pad"}
    skills.call(w, "goto", args)                       # already beside it
    history = _repeat(w, args)
    # Watched 2026-08-26: seven identical calls, seven DONE(steps=0), and gemma kept
    # asking because a costless success gave it nothing to correct.
    ok = check("the first repeat is answered plainly",
               "asked for this" not in history[0].result)
    ok &= check("the third says it is going nowhere",
                "nothing has changed" in history[-1].result, history[-1].result[-95:])
    ok &= check("still honest about arriving", history[-1].result.startswith("DONE"))
    ok &= check("and still free", all(h.steps == 0 for h in history))

    # The hole this had until 2026-08-26: the check read the code instead of the fact,
    # so a live run looped five times on UNREACHABLE and was never told. The rule is now
    # the invariant -- no steps spent means nothing changed means same answer.
    w2 = World()
    w2.here.seen = {(x, y) for y in range(w2.here.h) for x in range(w2.here.w)}
    w2.pos = (18, 11)
    rock = {"x": 19, "y": 11, "why": "into the outcrop"}
    far = _repeat(w2, rock)
    ok &= check("an UNREACHABLE loop is caught too",
                far[-1].result.startswith("UNREACHABLE")
                and "nothing has changed" in far[-1].result, far[-1].result[:60])
    priced = _repeat(w2, {"x": 5, "y": 5, "why": "how far"}, name="distance")
    ok &= check("so is pricing the same trip over and over",
                "nothing has changed" in priced[-1].result)

    # A call that actually did something ends the run, however often it is repeated.
    w3 = World()
    moved = [skills.call(w3, "goto", {"x": 25, "y": 22, "why": "north"}),
             skills.call(w3, "goto", {"x": 25, "y": 20, "why": "further"})]
    again = skills.call(w3, "goto", {"x": 25, "y": 22, "why": "north"}, history=moved)
    ok &= check("a call that moved is left alone",
                "nothing has changed" not in again.result)
    # ...and it has to be a *consecutive* run: something else in between resets it.
    w4 = World()
    mixed = [skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"}),
             skills.call(w4, "distance", {"x": 23, "y": 23, "why": "b"}),
             skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"})]
    last = skills.call(w4, "distance", {"x": 22, "y": 22, "why": "a"}, history=mixed)
    ok &= check("a broken run is not counted", "nothing has changed" not in last.result)
    return ok


def test_drives_that_buy_no_map_are_said_out_loud_even_when_they_differ():
    """The loop of 2026-08-29, which the previous rule could not see at all.

    Gemma drove (0,49) to (0,10) and back, six times, then (0,49) to (45,49) three
    times: 439 steps, 358 of them revealing nothing. Every call spent forty-nine steps,
    so "spent nothing" never fired -- and every call had a *different* target from the
    one before, so no test of repetition would have fired either. What the two have in
    common is the only thing worth saying: none of it bought any map.

    Rewritten when the rule became a rate over a window rather than a streak. Two
    separate things are now said and this test keeps them apart, because conflating them
    is how the old version passed while a quarter of a sol went on backtracking:

      "revealed nothing new"        -- `Result.advice`, on every gainless drive, at once
      "bought no new map at all"    -- `_stuck`, only once there is a pattern
    """
    print("drives that buy nothing")
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}  # nothing left

    hist = []
    for x, y in ((15, 10), (15, 20), (15, 10), (15, 20)):
        hist.append(skills.call(w, "goto", {"x": x, "y": y, "why": "casting about"},
                                history=hist))
    ok = check("every drive really did spend steps",
               all(h.steps > 0 for h in hist), str([h.steps for h in hist]))
    ok &= check("...and really did learn nothing",
                all(h.gained == 0 for h in hist))
    # The fact, immediately and every time. A drive that spends the day and buys no map
    # must not read as an unqualified success.
    ok &= check("each gainless drive says so on its own",
                all("revealed nothing new" in h.result for h in hist))
    # The pattern, only once there is one. Driving home to the pad is a gainless drive
    # on purpose, so this must never be a first-offence scold.
    ok &= check("the first three are not accused of a habit",
                not any("bought no new map" in h.result for h in hist[:3]))
    ok &= check("the fourth is", "bought no new map" in hist[3].result,
                hist[3].result[-110:])
    ok &= check("and names what it cost", "steps," in hist[3].result)
    # Alternating targets, so the identical-call rule is not what caught it.
    ok &= check("the targets were never the same twice running",
                str(hist[2]) != str(hist[1]))

    # Three calls is under the window on purpose: a there-and-back is a manoeuvre, and
    # the day it starts reading as a habit is the day this stops being usable.
    w2 = World()
    run = []
    for x, y in ((15, 10), (15, 15), (15, 10)):
        run.append(skills.call(w2, "goto", {"x": x, "y": y, "why": "there and back"},
                               history=run))
    ok &= check("one drive home is not called a habit",
                "bought no new map" not in run[-1].result, run[-1].result[-80:])

    # Pricing routes is the habit the arena wants more of, not less. Four price checks
    # in a row reveal no map by construction and must not read as being stuck.
    w3 = World()
    prices = []
    for x, y in ((2, 2), (27, 27), (15, 0), (0, 29)):
        prices.append(skills.call(w3, "distance", {"x": x, "y": y, "why": "which"},
                                  history=prices))
    ok &= check("comparing four routes is not being stuck",
                all("nothing" not in p.result.split("--")[-1] for p in prices),
                prices[-1].result[-70:])
    return ok


def test_distance_spends_nothing():
    print("distance")
    w = World()
    before = w.steps
    c = skills.call(w, "distance", {"x": 5, "y": 5, "why": "is it worth the drive"})
    ok = check("prices it", c.result.startswith("DISTANCE"), c.result)
    ok &= check("costs no steps", c.steps == 0 and w.steps == before)
    ok &= check("and says what is left", "steps left today" in c.result)
    return ok


def test_a_missing_why_never_stops_the_call():
    """Inverted on 2026-09-01. It used to assert the opposite, and that was the bug.

    Requiring the field cost 16 of 21 calls in `runs/20260901-000753/` once A5 had
    removed every example of one from history -- see `skills._why`. The field survives
    because the tape wants it; the refusal does not.
    """
    print("a missing why is not an error")
    ok = True
    # Not PAD: the rover lands next to the pad, so arriving there costs nothing and
    # would not show that the drive ran. This is a destination it has to travel to.
    away = {"x": 25, "y": 20}
    for label, args in (("absent", dict(away)),
                        ("empty", {**away, "why": "   "}),
                        ("<nil>", {**away, "why": "<nil>"})):
        w = World()
        c = skills.call(w, "goto", args)
        ok &= check(f"{label} why still drives", not c.result.startswith("BAD_ARGS"),
                    c.result[:60])
        ok &= check(f"...and records no reason for it", c.why is None, repr(c.why))
        ok &= check(f"...and actually moved", w.steps > 0, f"{w.steps} steps")

    # The point of relaxing one argument is that the others are still checked. A
    # coordinate that cannot be read is still the call that must not silently happen.
    w = World()
    before, where = w.steps, w.pos
    for label, args in (("no y", {"x": 25}), ("junk x", {"x": "east", "y": 26})):
        c = skills.call(w, "goto", args)
        ok &= check(f"{label} is still refused", c.result.startswith("BAD_ARGS"),
                    c.result[:60])
    ok &= check("and neither moved nor spent", w.steps == before and w.pos == where)

    # Supplied, it is still trimmed and still kept -- that half is untouched.
    kept = skills.call(World(), "goto", {**PAD, "why": "  back   to the pad  "})
    ok &= check("a why that is given is still recorded",
                kept.why == "back to the pad", repr(kept.why))
    return ok


def test_a_bad_avoid_never_becomes_an_empty_one():
    print("the avoid parser")
    w = World()
    ok = True
    # The silent-empty failure, in every disguise it arrives in.
    for bad in ("north", "the ridge", "(3,4),(5", "auto", "AUTO", 7, {"x": 1}):
        c = skills.call(w, "goto", {**PAD, "why": "w", "avoid": bad})
        ok &= check(f"avoid={bad!r} is refused", c.result.startswith("BAD_ARGS"),
                    c.result[:70])
    # `avoid="auto"` is refused by name rather than by falling through, because the
    # probe on 2026-08-26 showed gemma volunteering it unasked. It comes back when
    # mark() does -- which is still not built.
    c = skills.call(w, "goto", {**PAD, "why": "w", "avoid": "auto"})
    ok &= check("...and auto says why, not just no", "mark" in c.result, c.result[:80])
    return ok


def test_avoid_is_read_however_it_is_punctuated():
    print("avoid, tolerantly")
    ok = True
    for text in ("(3,4),(5,6)", "3,4 5,6", " (3, 4) (5, 6) ", [[3, 4], [5, 6]],
                 [(3, 4), (5, 6)]):
        ok &= check(f"{text!r} means two cells",
                    skills._avoid(text) == frozenset({(3, 4), (5, 6)}))
    # An omitted optional argument is the one thing allowed to become nothing, and only
    # when it says so in the ways gemma actually says it.
    for text in (None, "", "<nil>", "none", []):
        ok &= check(f"{text!r} means omitted", skills._avoid(text) is None)
    return ok


def _steps_in(result):
    """The step count out of a DISTANCE line, whatever the comparator in front of it.

    It read `steps=` literally until 2026-08-30, when the field became `steps>=` -- the
    number is a floor and now says so. That turned a wrong answer here into an
    IndexError, which is the good version of this failure, but the test was pinning the
    punctuation when what it cares about is the number moving when `avoid` is obeyed.
    """
    return int(re.search(r"steps\D*?(\d+)", result).group(1))


def test_an_avoid_that_parses_is_obeyed():
    print("avoid, obeyed")
    w = World()
    w.here.seen = {(x, y) for y in range(w.here.h) for x in range(w.here.w)}
    w.pos = (15, 12)
    c = skills.call(w, "distance", {**PAD, "why": "clear run"})
    plain = _steps_in(c.result)
    # Seal the pad's free neighbours from the north. If the parser dropped the list on
    # the floor the number would not move, which is exactly the bug that hides.
    fence = "(14,15),(15,15),(16,15)"
    c = skills.call(w, "distance", {**PAD, "why": "dodging", "avoid": fence})
    ok = check("the list changes the answer",
               c.result.startswith("UNREACHABLE") or
               _steps_in(c.result) != plain, c.result[:70])
    return ok


def test_coordinates_are_taken_generously():
    print("x and y")
    w = World()
    w.pos = (15, 12)
    ok = check('"25" is 25', skills._int("x", "25") == 25)
    ok &= check("25.0 is 25", skills._int("x", 25.0) == 25)
    for bad in ("<nil>", "ten", None, 10.5, True, [10]):
        try:
            skills._int("x", bad)
            ok &= check(f"{bad!r} is refused", False)
        except skills.BadArgs:
            ok &= check(f"{bad!r} is refused", True)
    c = skills.call(w, "goto", {"x": "25", "y": "26", "why": "strings are fine"})
    ok &= check("and a call with string coordinates works", c.result.startswith("DONE"))
    return ok


def test_an_unknown_skill_says_what_there_is():
    print("no such skill")
    w = World()
    # Gemma will reach for skills that do not exist yet -- and in this prototype most
    # of the ones it will imagine (interact, fly, sample) genuinely do not. The answer
    # has to name the ones that do, or it keeps guessing at the same absent verb.
    for absent in ("look", "interact", "fly"):
        c = skills.call(w, absent, {"why": "trying it on"})
        ok = check(f"{absent} refused", c.result.startswith("NO_SUCH_SKILL"), c.result)
        ok &= check("and lists what exists",
                    "goto" in c.result and "distance" in c.result)
        ok &= check("costing nothing", c.steps == 0)
    return ok


def _surveyed():
    """A world with the whole arena revealed, so counting is not about fog."""
    w = World()
    w.here.reveal(*w.pos, r=max(w.here.w, w.here.h))
    return w


def test_counting_is_exact_where_reading_the_map_is_not():
    print("count")
    # The failure this exists for, measured 2026-09-04 on the 50x50: nine bounding boxes
    # named, nine of them real formations, one of nine sizes correct. It knows where the
    # rocks are and cannot say how many cells they have. So the sizes must be exact.
    import config as C
    was = C.ARENA
    try:
        C.use("50")
        w = _surveyed()
        r = skills.call(w, "count", {"kind": "rock"})
        ok = check("it costs no steps", r.steps == 0)
        ok &= check("every formation is listed", r.result.count("cells,") == 31,
                    f"{r.result.count('cells,')} listed")
        ok &= check("including the one that is 30", "30 cells" in r.result)
        # Twenty sixteens tie. Listing by size would put the answer at the top and do
        # the deciding; map order leaves the weighing where it belongs.
        middles = [int(m) for m in re.findall(r"middle \((\d+),", r.result)]
        sizes = [int(m) for m in re.findall(r"R\d+: (\d+) cells", r.result)]
        ok &= check("and it is not handed over pre-ranked",
                    sizes != sorted(sizes, reverse=True))
        ok &= check("...but in map order", len(middles) == len(sizes))

        # A middle that is not in its own formation is a coordinate `count_cells` cannot
        # resolve. The C on this arena has its centroid in open ground inside the bay.
        big = re.search(r"R(\d+): 30 cells, middle \((\d+),(\d+)\)", r.result)
        ok &= check("the middle of the concave one is a cell of it", bool(big))
        if big:
            x, y = int(big.group(2)), int(big.group(3))
            ok &= check("...and it really is rock", C.ARENA[y][x] == "#", f"({x},{y})")
            cells = skills.call(w, "count_cells", {"x": x, "y": y})
            ok &= check("count_cells resolves it", "30 cells" in cells.result,
                        cells.result[:60])
            ok &= check("...as runs, not a wall of coordinates",
                        "y15: x30-39" in cells.result, cells.result[:80])
            ok &= check("...costing nothing", cells.steps == 0)
    finally:
        C.ARENA = was
        C.use(C.DEFAULT_ARENA)
    return ok


def test_counting_only_ever_counts_what_she_has_seen():
    print("count under fog")
    # Rock still under fog is fog. A size that silently meant "or more" would be the
    # lying success code again, wearing a number.
    w = World()          # fresh: only the landing site is revealed
    r = skills.call(w, "count", {})
    seen_rock = sum(1 for (x, y) in w.here.seen if w.here.at(x, y) == "#")
    listed = sum(int(n) for n in re.findall(r"R\d+: (\d+) cells", r.result))
    ok = check("it counts revealed rock and no more", listed == seen_rock,
               f"{listed} counted, {seen_rock} revealed")
    ok &= check("and fog is reported as fog", "FOG" in r.result)
    # Open ground is neither, and saying so beats guessing which she meant.
    here = skills.call(w, "count_cells", {"x": w.pos[0], "y": w.pos[1]})
    ok &= check("a cell that is neither is refused by name",
                here.result.startswith("NOT_A_FEATURE"), here.result[:50])
    return ok


def test_a_formation_keeps_its_name_as_it_comes_out_of_the_fog():
    print("formation ids")
    # Revealed rock only ever grows, so an id is worth carrying: the one event is a
    # merge, and she may have said the losing name out loud.
    import config as C
    was = C.ARENA
    try:
        C.use("50")
        w = World()
        w.here.reveal(31, 16, r=3)          # part of the C
        first = skills.call(w, "count", {"kind": "rock"}).result
        got = re.search(r"R(\d+): (\d+) cells", first)
        ok = check("it is named on sight", bool(got), first[:80])
        w.here.reveal(35, 21, r=6)          # more of the same formation
        second = skills.call(w, "count", {"kind": "rock"}).result
        ok &= check("the same rock keeps its id",
                    f"R{got.group(1)}:" in second, second[:120])
        ok &= check("and the newly revealed cells are called out",
                    "new since you last asked" in second, second[:200])
    finally:
        C.ARENA = was
        C.use(C.DEFAULT_ARENA)
    return ok


def test_every_dialect_of_a_written_call_is_recovered():
    """The backstop has to speak whatever the model happens to serialise into.

    On 2026-09-04 `gemma4:31b-cloud` stopped populating `tool_calls` and began writing
    every call into the content as `call:goto{x:49,y:0,why:...}`. Three runs died on
    turn one, 0 steps in 108 seconds, because the recovery only knew `name(a, b)`.
    Verified against a one-line prompt with the stock schema: `gemma4:e4b` answers with
    a real tool call, so this is the model, not the request.

    `count` and `end` matter as much as `goto` here. Recovery used to demand x and y,
    so with every call narrated she could not have counted or handed a turn back.
    """
    print("a call by any punctuation")
    ok = True
    for text, want in [
        # The brace dialect, both argument orders it has been seen in.
        ("call:goto{why:Mapping the north-east quadrant.,x:49,y:0}",
         ("goto", {"x": "49", "y": "0", "why": "Mapping the north-east quadrant."})),
        ("call:goto{x:49,y:0,why:go}", ("goto", {"x": "49", "y": "0", "why": "go"})),
        # The two older ones, which must not have regressed.
        ('goto(15, 10, "Driving north")',
         ("goto", {"x": "15", "y": "10", "why": "Driving north"})),
        ('goto(x=35, y=25, why="east")',
         ("goto", {"x": "35", "y": "25", "why": "east"})),
        # The skills that require nothing, which were unrecoverable before.
        ("count{kind:rock}", ("count", {"kind": "rock"})),
        ("count(kind=rock)", ("count", {"kind": "rock"})),
        ("end{}", ("end", {})),
        ("end()", ("end", {})),
        ("call:end{why:done for now}", ("end", {"why": "done for now"})),
        ("count_cells{x:31,y:18}", ("count_cells", {"x": "31", "y": "18"})),
    ]:
        ok &= check(f"recovered: {text[:38]}", skills.written_call(text) == want,
                    str(skills.written_call(text)))
        ok &= check(f"...and seen as one: {text[:30]}", skills.looks_like_a_call(text))

    # Loosening the shape is what makes prose dangerous: `end` gives the turn away, so
    # a bracket in a sentence must never read as a call to it.
    for text in ("goto is the right tool here", "at the end (of the sweep) I will stop",
                 "I will count (rocks) later", "the end (of the day)",
                 "no calls here at all"):
        ok &= check(f"prose left alone: {text[:34]}",
                    not skills.looks_like_a_call(text) and not skills.written_call(text),
                    str(skills.written_call(text)))

    # Read off the schema, not restated here -- the two drifting apart is the bug.
    ok &= check("what a recovery must carry comes from the schema itself",
                skills.REQUIRED == {t["function"]["name"]:
                                    set(t["function"]["parameters"]["required"])
                                    for t in skills.TOOLS})
    return ok


def test_the_schema_matches_what_is_wired_up():
    print("the schema is honest")
    names = {t["function"]["name"] for t in skills.TOOLS}
    ok = check("exactly six skills",
               names == {"goto", "distance", "scout", "count", "count_cells", "end"},
               str(names))
    blob = str(skills.TOOLS)
    # `scout` changes the map and not the position, which is the one thing about it a
    # model will get backwards -- the same shape as `DONE(beside=...)` reading as a
    # failure to arrive. Say it in the schema, before the first call, not only after.
    scout = next(t for t in skills.TOOLS if t["function"]["name"] == "scout")
    desc = scout["function"]["description"]
    ok &= check("scout says it does not move the rover",
                "not move the rover" in desc.lower())
    ok &= check("...and that the coordinate is the centre", "CENTRE" in desc)
    # The numbers come out of settings rather than being typed here a second time. A
    # schema promising a range the code does not enforce is the same lie as a prompt
    # promising a skill that does not exist.
    ok &= check("...and quotes the real range", str(S.SCOUT_RANGE) in desc)
    ok &= check("...and the real cost", str(S.SCOUT_COST) in desc)
    ok &= check("scout is offered no avoid list",
                "avoid" not in scout["function"]["parameters"]["properties"])
    # Optional since 2026-09-01, and the schema has to say so or the model infers the
    # requirement from the shape and goes back to failing calls it never had to fail.
    ok &= check("why is offered on all of them",
                all("why" in t["function"]["parameters"]["properties"]
                    for t in skills.TOOLS))
    ok &= check("...and required on none",
                not any("why" in t["function"]["parameters"]["required"]
                        for t in skills.TOOLS))
    # Only where a cell is what the call is *about*. `count` takes no coordinate and
    # `end` takes nothing at all, and a schema demanding x and y from them would have
    # the model inventing a pair to satisfy it.
    placed = {"goto", "distance", "count_cells", "scout"}
    ok &= check("...and x and y are required exactly where a cell is meant",
                all(({"x", "y"} <= set(t["function"]["parameters"]["required"]))
                    == (t["function"]["name"] in placed) for t in skills.TOOLS))
    # Never advertised on 2026-08-26, so gemma stepped one tile per call for a whole
    # run. Free to fix; it changes the shape of everything after it.
    ok &= check("goto says it drives the whole way", "whole way" in blob)
    ok &= check("and that coordinates are absolute", "ABSOLUTE" in blob)
    # avoid="auto" has no mark() behind it yet, so it must not be offered.
    ok &= check("auto is not offered", "auto'" not in blob and '"auto"' not in blob)
    # Nothing may be promised that is not built. These are items 2 to 7.
    for absent in ("interact", "sample", "storm", "Ingenuity", "battery"):
        ok &= check(f"{absent} is not advertised", absent.lower() not in blob.lower())
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_plain_goto_drives(), test_going_nowhere_twice_is_said_out_loud(),
               test_drives_that_buy_no_map_are_said_out_loud_even_when_they_differ(),
               test_distance_spends_nothing(),
               test_a_missing_why_never_stops_the_call(),
               test_a_bad_avoid_never_becomes_an_empty_one(),
               test_avoid_is_read_however_it_is_punctuated(),
               test_an_avoid_that_parses_is_obeyed(),
               test_coordinates_are_taken_generously(),
               test_an_unknown_skill_says_what_there_is(),
               test_counting_is_exact_where_reading_the_map_is_not(),
               test_counting_only_ever_counts_what_she_has_seen(),
               test_a_formation_keeps_its_name_as_it_comes_out_of_the_fog(),
               test_every_dialect_of_a_written_call_is_recovered(),
               test_the_schema_matches_what_is_wired_up()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
