"""The write path: today's list, and the note that survives the night.

    .venv/bin/python game/test_notes.py

Two claims hold this file up, and they are the two the demo is about. An id means the
same item all sol, whatever is struck in between -- a list that renumbers underneath her
retires the wrong decision silently. And `next_day` takes the list and leaves the note,
which is the entire difference between the two stores.

The rest is the house rule: rejected loudly, and never at the cost of a step. A write
that quietly did nothing is the vanishing call, which this project has now paid for
three times.
"""

import sys

import settings as S
import sight
import skills
from world import World

S.STORM_ON = False      # the weather is a scenario; `test_hazards.py` turns it on


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def test_a_list_is_written_and_crossed_off():
    print("the list")
    w = World()
    a = skills.call(w, "todo", {"text": "scout the fog north-east of R4",
                                "why": "nothing up there is mapped"})
    ok = check("an item lands", a.result.startswith("NOTED(1)"), a.result)
    ok &= check("and costs no steps", a.steps == 0)
    ok &= check("the why is kept", a.why == "nothing up there is mapped")
    ok &= check("it says how to cross it off", "strike(1)" in a.result, a.result)

    skills.call(w, "todo", {"text": "price the trip to the low-priority objective"})
    ok &= check("two items, both open", w.notes.open == 2, str(w.notes.open))

    s = skills.call(w, "strike", {"n": 1})
    ok &= check("striking works", s.result.startswith("STRUCK(1)"), s.result)
    # A bare STRUCK(1) cannot be checked against what she meant to strike, and an
    # off-by-one here retires a decision she never revisited.
    ok &= check("...and says which item, in words", "north-east of R4" in s.result,
                s.result)
    ok &= check("one left open", w.notes.open == 1, str(w.notes.open))
    ok &= check("but nothing was deleted", len(w.notes.todos) == 2)
    return ok


def test_ids_never_move_under_her():
    """The whole reason struck items stay on the list."""
    print("stable numbering")
    w = World()
    for t in ("drive to the pad", "scout west", "count the rock"):
        skills.call(w, "todo", {"text": t})
    skills.call(w, "strike", {"n": 1})
    third = skills.call(w, "strike", {"n": 3})
    ok = check("item 3 is still the third thing she wrote",
               "count the rock" in third.result, third.result)
    again = skills.call(w, "strike", {"n": 3})
    ok &= check("striking it twice says so rather than pretending",
                again.result.startswith("ALREADY_STRUCK(3)"), again.result)
    ok &= check("...and costs nothing", again.steps == 0)

    off = skills.call(w, "strike", {"n": 9})
    ok &= check("a number that is not on the list is refused",
                off.result.startswith("NO_SUCH_ITEM(9)"), off.result)
    ok &= check("...and says what the numbering actually is",
                "1 to 3" in off.result, off.result)

    empty = skills.call(World(), "strike", {"n": 1})
    ok &= check("an empty list says it is empty rather than quoting a range",
                "empty" in empty.result, empty.result)
    return ok


def test_the_same_item_is_never_written_twice():
    """The list exists so a decision is made once. Two copies of one line is the loop
    it was built to stop, wearing a different hat."""
    print("no duplicates")
    w = World()
    skills.call(w, "todo", {"text": "scout the north-east"})
    dup = skills.call(w, "todo", {"text": "  Scout   the North-East  "})
    ok = check("a repeat is refused by number",
               dup.result.startswith("ALREADY_ON_IT(1)"), dup.result)
    ok &= check("and the list did not grow", len(w.notes.todos) == 1)

    for i in range(S.TODO_MAX):
        skills.call(w, "todo", {"text": f"item number {i}"})
    full = skills.call(w, "todo", {"text": "one more"})
    ok &= check("the list has a ceiling", full.result.startswith("LIST_FULL"), full.result)
    ok &= check("...that holds", len(w.notes.todos) == S.TODO_MAX, str(len(w.notes.todos)))
    return ok


def test_the_note_replaces_rather_than_appends():
    """Append-only means she can never correct herself, and correction is the thing
    most worth watching. Settled in prototype1/DESIGN.md."""
    print("the note")
    w = World()
    first = skills.call(w, "remember", {"text": "R4 blocks the whole north-east ridge"})
    ok = check("it writes", first.result.startswith("REMEMBERED("), first.result)
    ok &= check("and costs no steps", first.steps == 0)

    second = skills.call(w, "remember", {"text": "R4 has a gap at y12 -- I was wrong"})
    ok &= check("the old note is gone, not appended to",
                w.notes.memory == "R4 has a gap at y12 -- I was wrong", w.notes.memory)
    ok &= check("and the answer says what it replaced", "replaced" in second.result,
                second.result)

    long = skills.call(w, "remember", {"text": "x" * (S.MEMORY_CHARS + 1)})
    ok &= check("an over-long note is refused", long.result.startswith("BAD_ARGS"),
                long.result)
    # Refused rather than truncated: cutting the end off a rewrite silently drops what
    # she wrote last, which is usually the part she has just changed her mind about.
    ok &= check("...and what she had is untouched",
                w.notes.memory == "R4 has a gap at y12 -- I was wrong")
    ok &= check("...and it says both numbers", str(S.MEMORY_CHARS) in long.result,
                long.result)

    for bad in (None, "", "   ", "<nil>"):
        r = skills.call(w, "remember", {"text": bad})
        ok &= check(f"{bad!r} is refused rather than erasing the note",
                    r.result.startswith("BAD_ARGS"), r.result)
    ok &= check("...and it really is still there", bool(w.notes.memory))
    return ok


def test_the_night_takes_the_list_and_leaves_the_note():
    """The one claim the whole prototype is for."""
    print("what crosses the night")
    w = World()
    skills.call(w, "todo", {"text": "come back for the low-priority objective"})
    skills.call(w, "remember", {"text": "objective 3 is 60 steps of work -- not worth "
                                        "a sol on its own"})
    w.day_over = True
    w.next_day()

    ok = check("the list is gone", w.notes.todos == [], str(w.notes.todos))
    ok &= check("the note is not", "not worth a sol" in w.notes.memory, w.notes.memory)
    ok &= check("and the map came with it", w.day == 2)
    return ok


def test_a_write_is_a_look_and_never_costs_a_step():
    print("what it costs")
    w = World()
    before = w.steps
    for name, args in (("todo", {"text": "a thing"}), ("strike", {"n": 1}),
                       ("remember", {"text": "a note"})):
        c = skills.call(w, name, args)
        ok = check(f"{name} spends nothing", c.steps == 0, str(c.steps))
        if not ok:
            return False
    ok = check("the day is where it started", w.steps == before, str(w.steps))

    # The buzzer must not lock her out of her own notes: a `goto` that spends the last
    # step used to end the sol with the whole day unwritten.
    w.steps = S.DAY_STEPS
    w.day_over = True
    late = skills.call(w, "remember", {"text": "written after the steps ran out"})
    ok &= check("and a spent day can still be written up",
                late.result.startswith("REMEMBERED("), late.result)
    return ok


def test_a_malformed_write_is_loud_and_free():
    print("rejected loudly")
    w = World()
    for args in ({"text": None}, {"text": "<nil>"}, {}):
        c = skills.call(w, "todo", args)
        ok = check(f"todo{args} is refused", c.result.startswith("BAD_ARGS"), c.result)
        if not ok:
            return False
    ok = check("nothing landed on the list", w.notes.todos == [])
    for args in ({"n": "two"}, {"n": None}, {}):
        c = skills.call(w, "strike", args)
        ok &= check(f"strike{args} is refused", c.result.startswith("BAD_ARGS"), c.result)
    # She writes "3" as often as 3, and a strike that refuses a string is a strike she
    # cannot make from a list she is reading as text.
    skills.call(w, "todo", {"text": "something"})
    ok &= check("but a written number still strikes",
                skills.call(w, "strike", {"n": " 1 "}).result.startswith("STRUCK(1)"))
    return ok


def test_both_blocks_are_in_the_view_from_the_first_request():
    """Injected, not fetched. A forgotten `read_notes()` costs a whole day and teaches
    nobody anything -- prototype1/FINDINGS.md settled this and it is not re-argued."""
    print("in the view")
    w = World()
    v = sight.view(w)
    ok = check("the empty list is shown", "YOUR LIST FOR TODAY" in v)
    ok &= check("the empty note is shown", "WHAT YOU WROTE DOWN TO KEEP" in v)
    # An empty block carries no example of a call, and `why` collapsed to nothing the
    # moment history stopped carrying one. The invitation has to be in the words.
    ok &= check("...and the empty one names both calls",
                'todo("...")' in v and "strike(n)" in v, "")
    ok &= check("...and says which one survives", 'remember("...")' in v)

    skills.call(w, "todo", {"text": "scout the north-east"})
    skills.call(w, "todo", {"text": "price objective 3"})
    skills.call(w, "strike", {"n": 1})
    skills.call(w, "remember", {"text": "the ridge is impassable west of x20"})
    v = sight.view(w)
    ok &= check("a struck item shows as struck", "1. [x] scout the north-east" in v, "")
    ok &= check("an open one shows as open", "2. [ ] price objective 3" in v, "")
    ok &= check("the note is quoted whole", "impassable west of x20" in v)
    ok &= check("the pane one-liner counts what is open", "1 on her list" in
                sight.one_line(w), sight.one_line(w))

    # Both blocks are ours to write, so both can be forged. She once invented four
    # thousand characters of view; a forged list would read back as work she never did.
    ok &= check("both headings are hallmarks",
                "YOUR LIST FOR TODAY" in sight.HALLMARKS
                and "WHAT YOU WROTE DOWN TO KEEP" in sight.HALLMARKS)
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_list_is_written_and_crossed_off(),
               test_ids_never_move_under_her(),
               test_the_same_item_is_never_written_twice(),
               test_the_note_replaces_rather_than_appends(),
               test_the_night_takes_the_list_and_leaves_the_note(),
               test_a_write_is_a_look_and_never_costs_a_step(),
               test_a_malformed_write_is_loud_and_free(),
               test_both_blocks_are_in_the_view_from_the_first_request()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
