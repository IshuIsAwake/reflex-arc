"""The skill interface: tolerant in, loud out.

    .venv/bin/python game/test_skills.py

The whole file is about one failure. An `avoid` list that quietly parses to "avoid
nothing" walks gemma through the exact cell it asked to dodge, says nothing, and the
notes file takes the blame for a parser bug. Every rejection here has to be audible,
and none of them may cost a step -- a malformed call is a mistake, not an action.

Gemma emits the literal string '<nil>' for an argument it means to omit. That is not
hypothetical; it was watched on 2026-08-26.
"""

import sys

import settings as S
import skills
from world import World


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def test_a_plain_goto_walks():
    print("goto")
    w = World()
    c = skills.call(w, "goto", {"x": 10, "y": 16, "why": "the shop is right there"})
    ok = check("arrives", c.result.startswith("DONE"), c.result)
    # The shop is solid, so this lands beside it. Without `beside=` in the answer,
    # DONE(at=(10,15)) for a goto(10,16) reads as failure and gets reissued.
    ok &= check("and says it stopped beside a solid target", "beside=" in c.result)
    # ...and the field alone was not enough. Watched 2026-08-26: gemma read the
    # beside= form as failure and spent the rest of the run trying to step into a
    # shop counter. Arrival has to be stated, not encoded.
    ok &= check("in words as well as a field", "IS arriving" in c.result, c.result)

    already = skills.call(w, "goto", {"x": w.pos[0], "y": w.pos[1], "why": "again"})
    # A free no-op is how a confused model bounces between two cells forever.
    ok &= check("a goto to where you stand says so", "already standing" in already.result,
                already.result)
    ok &= check("and costs nothing", already.steps == 0)
    ok &= check("the why is kept", c.why == "the shop is right there")
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
    args = {"x": 3, "y": 8, "why": "the board"}
    skills.call(w, "goto", args)                       # walks there
    history = _repeat(w, args)
    # Watched 2026-08-26: seven identical goto(3,8) calls, seven DONE(steps=0), and
    # gemma kept asking because a costless success gave it nothing to correct.
    ok = check("the first repeat is answered plainly", "asked for this" not in history[0].result)
    ok &= check("the third says it is going nowhere",
                "nothing has changed" in history[-1].result, history[-1].result[-95:])
    ok &= check("still honest about arriving", history[-1].result.startswith("DONE"))
    ok &= check("and still free", all(h.steps == 0 for h in history))

    # The hole this had until 2026-08-26: the check read the code instead of the fact,
    # so a live run looped five times on UNREACHABLE and was never told. The rule is
    # now the invariant -- no steps spent means nothing changed means same answer.
    w2 = World()
    west = {"x": 0, "y": 5, "why": "west"}
    skills.call(w2, "goto", west)      # this one walks part of the way and stops
    far = _repeat(w2, west)
    ok &= check("an UNREACHABLE loop is caught too",
                far[-1].result.startswith("UNREACHABLE")
                and "nothing has changed" in far[-1].result, far[-1].result[:60])
    priced = _repeat(w2, {"x": 10, "y": 16, "why": "how far"}, name="distance")
    ok &= check("so is pricing the same trip over and over",
                "nothing has changed" in priced[-1].result)

    # A call that actually did something ends the run, however often it is repeated.
    w3 = World()
    moved = [skills.call(w3, "goto", {"x": 10, "y": 14, "why": "back"}),
             skills.call(w3, "goto", {"x": 10, "y": 12, "why": "north"})]
    again = skills.call(w3, "goto", {"x": 10, "y": 14, "why": "back"}, history=moved)
    ok &= check("a call that moved is left alone", "nothing has changed" not in again.result)
    # ...and it has to be a *consecutive* run: something else in between resets it.
    w4 = World()
    mixed = [skills.call(w4, "distance", {"x": 1, "y": 1, "why": "a"}),
             skills.call(w4, "distance", {"x": 2, "y": 2, "why": "b"}),
             skills.call(w4, "distance", {"x": 1, "y": 1, "why": "a"})]
    last = skills.call(w4, "distance", {"x": 1, "y": 1, "why": "a"}, history=mixed)
    ok &= check("a broken run is not counted", "nothing has changed" not in last.result)
    return ok


def test_distance_spends_nothing():
    print("distance")
    w = World()
    before = w.steps
    c = skills.call(w, "distance", {"x": 10, "y": 16, "why": "is it worth the walk"})
    ok = check("prices it", c.result.startswith("DISTANCE"), c.result)
    ok &= check("costs no steps", c.steps == 0 and w.steps == before)
    ok &= check("and says what is left", "steps left today" in c.result)
    return ok


def test_a_missing_why_is_refused():
    print("the why requirement")
    w = World()
    before = w.steps
    ok = True
    for label, args in (("absent", {"x": 10, "y": 16}),
                        ("empty", {"x": 10, "y": 16, "why": "   "}),
                        ("<nil>", {"x": 10, "y": 16, "why": "<nil>"})):
        c = skills.call(w, "goto", args)
        ok &= check(f"{label} why is refused", c.result.startswith("BAD_ARGS"), c.result[:60])
    # FINDINGS settled that the rationale is required. What that costs is the calls
    # it rejects, and the count is only meaningful if none of them moved anything.
    ok &= check("and none of it moved or spent", w.steps == before and w.pos == World().pos)
    return ok


def test_a_bad_avoid_never_becomes_an_empty_one():
    print("the avoid parser")
    w = World()
    ok = True
    # The silent-empty failure, in every disguise it arrives in.
    for bad in ("north", "the pits", "(3,4),(5", "auto", "AUTO", 7, {"x": 1}):
        c = skills.call(w, "goto", {"x": 10, "y": 16, "why": "w", "avoid": bad})
        ok &= check(f"avoid={bad!r} is refused", c.result.startswith("BAD_ARGS"),
                    c.result[:70])
    # `avoid="auto"` is refused by name rather than by falling through, because the
    # probe on 2026-08-26 showed gemma volunteering it unasked. It comes back when
    # mark() does.
    c = skills.call(w, "goto", {"x": 10, "y": 16, "why": "w", "avoid": "auto"})
    ok &= check("...and auto says why, not just no", "mark" in c.result, c.result[:80])
    return ok


def test_avoid_is_read_however_it_is_punctuated():
    print("avoid, tolerantly")
    ok = True
    for text in ("(3,4),(5,6)", "3,4 5,6", " (3, 4) (5, 6) ", [[3, 4], [5, 6]],
                 [(3, 4), (5, 6)]):
        ok &= check(f"{text!r} means two cells",
                    skills._avoid(text) == frozenset({(3, 4), (5, 6)}))
    # An omitted optional argument is the one thing allowed to become nothing, and
    # only when it says so in the ways gemma actually says it.
    for text in (None, "", "<nil>", "none", []):
        ok &= check(f"{text!r} means omitted", skills._avoid(text) is None)
    return ok


def test_an_avoid_that_parses_is_obeyed():
    print("avoid, obeyed")
    w = World()
    w.here.has_map = True
    c = skills.call(w, "distance", {"x": 10, "y": 16, "why": "clear run"})
    plain = int(c.result.split("steps=")[1].split(",")[0])
    # Seal the shop's only free neighbour. If the parser dropped the list on the
    # floor the number would not move, which is exactly the bug that hides.
    c = skills.call(w, "distance", {"x": 10, "y": 16, "why": "dodging",
                                    "avoid": "(10,15)"})
    ok = check("the list changes the answer",
               c.result.startswith("UNREACHABLE") or
               int(c.result.split("steps=")[1].split(",")[0]) != plain, c.result[:60])
    return ok


def test_coordinates_are_taken_generously():
    print("x and y")
    w = World()
    ok = check('"10" is 10', skills._int("x", "10") == 10)
    ok &= check("10.0 is 10", skills._int("x", 10.0) == 10)
    for bad in ("<nil>", "ten", None, 10.5, True, [10]):
        try:
            skills._int("x", bad)
            ok &= check(f"{bad!r} is refused", False)
        except skills.BadArgs:
            ok &= check(f"{bad!r} is refused", True)
    c = skills.call(w, "goto", {"x": "10", "y": "16", "why": "strings are fine"})
    ok &= check("and a call with string coordinates works", c.result.startswith("DONE"))
    return ok


def test_an_unknown_skill_says_what_there_is():
    print("no such skill")
    w = World()
    # Gemma will reach for skills that do not exist yet. The answer has to name the
    # ones that do, or it will keep guessing at the same absent verb.
    c = skills.call(w, "look", {"why": "having a look"})
    ok = check("refused", c.result.startswith("NO_SUCH_SKILL"), c.result)
    ok &= check("and lists what exists", "goto" in c.result and "distance" in c.result)
    ok &= check("costing nothing", c.steps == 0)
    return ok


def test_the_schema_matches_what_is_wired_up():
    print("the schema is honest")
    names = {t["function"]["name"] for t in skills.TOOLS}
    ok = check("exactly two skills", names == {"goto", "distance"}, str(names))
    blob = str(skills.TOOLS)
    ok &= check("why is required on both",
                all("why" in t["function"]["parameters"]["required"] for t in skills.TOOLS))
    # Never advertised on 2026-08-26, so gemma stepped one tile per call for a whole
    # run. Free to fix; it changes the shape of everything after it.
    ok &= check("goto says it walks the whole way", "whole way" in blob)
    ok &= check("and that coordinates are absolute", "ABSOLUTE" in blob)
    # avoid="auto" has no mark() behind it yet, so it must not be offered.
    ok &= check("auto is not offered", "auto'" not in blob and '"auto"' not in blob)
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_plain_goto_walks(), test_going_nowhere_twice_is_said_out_loud(),
               test_distance_spends_nothing(),
               test_a_missing_why_is_refused(),
               test_a_bad_avoid_never_becomes_an_empty_one(),
               test_avoid_is_read_however_it_is_punctuated(),
               test_an_avoid_that_parses_is_obeyed(),
               test_coordinates_are_taken_generously(),
               test_an_unknown_skill_says_what_there_is(),
               test_the_schema_matches_what_is_wired_up()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
