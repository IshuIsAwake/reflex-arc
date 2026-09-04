r"""The skill interface: tolerant in, loud out.

    ..\.venv\Scripts\python.exe game\test_skills.py

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

PAD = {"x": 25, "y": 26}    # solid, one cell south of where the rover lands


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def test_a_plain_goto_drives():
    print("goto")
    w = World()
    w.pos = (25, 22)
    c = skills.call(w, "goto", {**PAD, "why": "back to the pad"})
    ok = check("arrives", c.result.startswith("DONE"), c.result)
    # The pad is solid, so this lands beside it. Without `beside=` in the answer,
    # DONE(at=(25,25)) for a goto(25,26) reads as failure and gets reissued.
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
    w2.here.seen = {(x, y) for y in range(50) for x in range(50)}
    w2.pos = (32, 29)
    rock = {"x": 33, "y": 29, "why": "into the outcrop"}
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
    """
    print("drives that buy nothing")
    w = World()
    w.here.seen = {(x, y) for y in range(50) for x in range(50)}   # nothing left to find

    hist = []
    for x, y in ((25, 20), (25, 30), (25, 20), (25, 30)):
        hist.append(skills.call(w, "goto", {"x": x, "y": y, "why": "casting about"},
                                history=hist))
    ok = check("every drive really did spend steps",
               all(h.steps > 0 for h in hist), str([h.steps for h in hist]))
    ok &= check("...and really did learn nothing",
                all(h.gained == 0 for h in hist))
    ok &= check("the first two are answered plainly",
                "revealed nothing new" not in hist[1].result)
    ok &= check("the third says so", "3 drives in a row" in hist[2].result,
                hist[2].result[-100:])
    ok &= check("and names what it cost", "costing" in hist[3].result)
    # Alternating targets, so the old identical-call rule is not what caught it.
    ok &= check("the targets were never the same twice running",
                str(hist[2]) != str(hist[1]))

    # A drive that opens new ground ends the run, or returning to base would be scolded.
    w2 = World()
    run = []
    for x, y in ((25, 20), (25, 25), (25, 20)):
        run.append(skills.call(w2, "goto", {"x": x, "y": y, "why": "there and back"},
                               history=run))
    ok &= check("a run is not started by driving home",
                "revealed nothing new" not in run[-1].result, run[-1].result[-80:])

    # Pricing routes is the habit the arena wants more of, not less. Four price checks
    # in a row reveal no map by construction and must not read as being stuck.
    w3 = World()
    prices = []
    for x, y in ((2, 2), (45, 45), (25, 0), (0, 49)):
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
    w.here.seen = {(x, y) for y in range(50) for x in range(50)}
    w.pos = (25, 22)
    c = skills.call(w, "distance", {**PAD, "why": "clear run"})
    plain = _steps_in(c.result)
    # Seal the pad's free neighbours from the north. If the parser dropped the list on
    # the floor the number would not move, which is exactly the bug that hides.
    fence = "(24,25),(25,25),(26,25)"
    c = skills.call(w, "distance", {**PAD, "why": "dodging", "avoid": fence})
    ok = check("the list changes the answer",
               c.result.startswith("UNREACHABLE") or
               _steps_in(c.result) != plain, c.result[:70])
    return ok


def test_coordinates_are_taken_generously():
    print("x and y")
    w = World()
    w.pos = (25, 22)
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


def test_the_schema_matches_what_is_wired_up():
    print("the schema is honest")
    names = {t["function"]["name"] for t in skills.TOOLS}
    ok = check("four skills", names == {"goto", "distance", "step", "press"},
               str(names))
    blob = str(skills.TOOLS)
    # Optional since 2026-09-01, and the schema has to say so or the model infers the
    # requirement from the shape and goes back to failing calls it never had to fail.
    ok &= check("why is offered on all",
                all("why" in t["function"]["parameters"]["properties"]
                    for t in skills.TOOLS))
    ok &= check("...and required on none",
                not any("why" in t["function"]["parameters"]["required"]
                        for t in skills.TOOLS))
    by_name = {t["function"]["name"]: t["function"] for t in skills.TOOLS}
    ok &= check("...and x and y still are on goto and distance",
                all({"x", "y"} <= set(by_name[n]["parameters"]["required"])
                    for n in ("goto", "distance")))
    ok &= check("...and direction is on step",
                "direction" in by_name["step"]["parameters"]["required"])
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
               test_the_schema_matches_what_is_wired_up()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
