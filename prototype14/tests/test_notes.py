"""The write path: today's list, and the memory that survives the night.


Two claims hold this file up, and they are the two the demo is about. An id means the
same item all sol, whatever is struck in between -- a list that renumbers underneath her
retires the wrong decision silently. And `next_day` takes the list and leaves the memory,
which is the entire difference between the two stores.

The rest is the house rule: rejected loudly, and never at the cost of a step. A write
that quietly did nothing is the vanishing call, which this project has now paid for
three times.
"""


import settings
import sight
import skills
from world import World


def test_a_list_is_written_and_crossed_off():
    w = World()
    a = skills.call(w, "todo", {"text": "scout the fog north-east of R4",
                                "why": "nothing up there is mapped"})
    assert a.result.startswith("NOTED(1)"), "an item lands"
    assert a.steps == 0, "and costs no steps"
    assert a.why == "nothing up there is mapped", "the why is kept"
    assert "strike(1)" in a.result, "it says how to cross it off"

    skills.call(w, "todo", {"text": "price the trip to the low-priority objective"})
    assert w.notes.open == 2, "two items, both open"

    s = skills.call(w, "strike", {"n": 1})
    assert s.result.startswith("STRUCK(1)"), "striking works"
    # A bare STRUCK(1) cannot be checked against what she meant to strike, and an
    # off-by-one here retires a decision she never revisited.
    assert "north-east of R4" in s.result, "...and says which item, in words"
    assert w.notes.open == 1, "one left open"
    assert len(w.notes.todos) == 2, "but nothing was deleted"


def test_ids_never_move_under_her():
    """The whole reason struck items stay on the list."""
    w = World()
    for t in ("drive to the pad", "scout west", "count the rock"):
        skills.call(w, "todo", {"text": t})
    skills.call(w, "strike", {"n": 1})
    third = skills.call(w, "strike", {"n": 3})
    assert "count the rock" in third.result, "item 3 is still the third thing she wrote"
    again = skills.call(w, "strike", {"n": 3})
    assert again.result.startswith("ALREADY_STRUCK(3)"), "striking it twice says so rather than pretending"
    assert again.steps == 0, "...and costs nothing"

    off = skills.call(w, "strike", {"n": 9})
    assert off.result.startswith("NO_SUCH_ITEM(9)"), "a number that is not on the list is refused"
    assert "1 to 3" in off.result, "...and says what the numbering actually is"

    empty = skills.call(World(), "strike", {"n": 1})
    assert "empty" in empty.result, "an empty list says it is empty rather than quoting a range"


def test_the_same_item_is_never_written_twice():
    """The list exists so a decision is made once. Two copies of one line is the loop
    it was built to stop, wearing a different hat."""
    w = World()
    skills.call(w, "todo", {"text": "scout the north-east"})
    dup = skills.call(w, "todo", {"text": "  Scout   the North-East  "})
    assert dup.result.startswith("ALREADY_ON_IT(1)"), "a repeat is refused by number"
    assert len(w.notes.todos) == 1, "and the list did not grow"

    for i in range(settings.TODO_MAX):
        skills.call(w, "todo", {"text": f"item number {i}"})
    full = skills.call(w, "todo", {"text": "one more"})
    assert full.result.startswith("LIST_FULL"), "the list has a ceiling"
    assert len(w.notes.todos) == settings.TODO_MAX, "...that holds"


def test_an_entry_replaces_rather_than_appends():
    """Append-only means she can never correct herself, and correction is the thing
    most worth watching. Settled in prototype 1, docs/findings.md -- now per entry."""
    w = World()
    first = skills.call(w, "remember", {"name": "ridge",
                                        "text": "R4 blocks the whole north-east ridge"})
    assert first.result.startswith("REMEMBERED(ridge"), "it writes"
    assert first.steps == 0, "and costs no steps"

    second = skills.call(w, "remember", {"name": "Ridge",
                                         "text": "R4 has a gap at y12 -- I was wrong"})
    assert w.notes.memory == {"ridge": "R4 has a gap at y12 -- I was wrong"}, "the same name, whatever its case, replaces it rather than appending"
    assert "replaced" in second.result, "and the answer says what it replaced"

    long = skills.call(w, "remember", {"name": "ridge", "text": "x" * (settings.MEMORY_CHARS + 1)})
    assert long.result.startswith("BAD_ARGS"), "an over-long entry is refused"
    # Refused rather than truncated: cutting the end off a rewrite silently drops what
    # she wrote last, which is usually the part she has just changed her mind about.
    assert w.notes.memory["ridge"] == "R4 has a gap at y12 -- I was wrong", "...and what she had is untouched"
    assert str(settings.MEMORY_CHARS) in long.result, "...and it says both numbers"

    for bad in (None, "", "   ", "<nil>"):
        r = skills.call(w, "remember", {"name": "ridge", "text": bad})
        assert r.result.startswith("BAD_ARGS"), f"{bad!r} is refused rather than erasing the entry"
        r = skills.call(w, "remember", {"name": bad, "text": "something"})
        assert r.result.startswith("BAD_ARGS"), f"a name of {bad!r} is refused"
    assert "ridge" in w.notes.memory, "...and it really is still there"


def test_the_memory_has_a_cap_and_forget_makes_room():
    w = World()
    keep = settings.MEMORY_ENTRIES
    settings.MEMORY_ENTRIES = 2
    try:
        skills.call(w, "remember", {"name": "a", "text": "one"})
        skills.call(w, "remember", {"name": "b", "text": "two\n- a bullet\n- another"})
        full = skills.call(w, "remember", {"name": "c", "text": "three"})
        assert (full.result.startswith(
            "MEMORY_FULL") and "c" not in w.notes.memory), "at the cap a new entry is refused"
        assert "a, b" in full.result, "...and it names what she holds"
        assert (skills.call(w, "remember", {"name": "a", "text": "one, revised"})
                    .result.startswith("REMEMBERED")), "but an entry she has can still be rewritten"
        gone = skills.call(w, "forget", {"name": "A"})
        assert (gone.result.startswith(
            "FORGOT(A)") and "a" not in w.notes.memory), "forget drops one, whatever its case"
        assert (skills.call(w, "remember", {"name": "c", "text": "three"})
                    .result.startswith("REMEMBERED")), "and then there is room"
        miss = skills.call(w, "forget", {"name": "nothing"})
        assert miss.result.startswith("NOT_REMEMBERED") and "b, c" in miss.result, "forgetting what is not there changes nothing, and says what is"
        assert "- another" in w.notes.memory["b"], "bullets survive inside an entry"
    finally:
        settings.MEMORY_ENTRIES = keep


def test_the_night_takes_the_list_and_leaves_the_memory():
    """The one claim the whole prototype is for."""
    w = World()
    skills.call(w, "todo", {"text": "come back for the low-priority objective"})
    skills.call(w, "remember", {"name": "objective 3",
                                "text": "60 steps of work -- not worth a sol on its own"})
    w.day_over = True
    w.next_day()

    assert w.notes.todos == [], "the list is gone"
    assert "not worth a sol" in w.notes.memory["objective 3"], "the memory is not"
    assert w.day == 2, "and the map came with it"


def test_a_list_made_at_night_is_the_next_days():
    """The list is cleared when dusk ends, not at dawn. In the 14 Oct team run the desk
    took an order down at night and she planned "explore north, explore east" in
    answer; by morning her list was empty and she copied the objectives instead."""
    w = World()
    skills.call(w, "todo", {"text": "explore south"})
    w.phase = "dusk"
    assert w.notes.todos == [["explore south", False]], "at dusk today's list is still there to read"
    w.phase = "night"
    w.evening()
    assert w.notes.todos == [], "dusk over, it is cleared"
    skills.call(w, "todo", {"text": "explore north"})
    assert "YOUR LIST FOR TOMORROW -- 1 items" in sight.view(w), "and the view calls it tomorrow's"
    w.next_day()
    assert w.notes.todos == [["explore north", False]], "what she wrote at night is there at dawn"
    assert "YOUR LIST FOR TODAY -- 1 items" in sight.view(w), "and the view calls it today's again"


def test_a_write_is_a_look_and_never_costs_a_step():
    w = World()
    before = w.steps
    for name, args in (("todo", {"text": "a thing"}), ("strike", {"n": 1}),
                       ("remember", {"name": "n", "text": "a note"}),
                       ("forget", {"name": "n"})):
        c = skills.call(w, name, args)
        assert c.steps == 0, f"{name} spends nothing"
    assert w.steps == before, "the day is where it started"

    # The buzzer must not lock her out of her own notes: a `goto` that spends the last
    # step used to end the sol with the whole day unwritten.
    w.run_clock(w.time_left)
    late = skills.call(w, "remember", {"name": "late",
                                       "text": "written after the steps ran out"})
    assert late.result.startswith("REMEMBERED("), "and a spent day can still be written up"


def test_a_malformed_write_is_loud_and_free():
    w = World()
    for args in ({"text": None}, {"text": "<nil>"}, {}):
        c = skills.call(w, "todo", args)
        assert c.result.startswith("BAD_ARGS"), f"todo{args} is refused"
    assert w.notes.todos == [], "nothing landed on the list"
    for args in ({"n": "two"}, {"n": None}, {}):
        c = skills.call(w, "strike", args)
        assert c.result.startswith("BAD_ARGS"), f"strike{args} is refused"
    # She writes "3" as often as 3, and a strike that refuses a string is a strike she
    # cannot make from a list she is reading as text.
    skills.call(w, "todo", {"text": "something"})
    assert skills.call(w, "strike", {"n": " 1 "}).result.startswith("STRUCK(1)"), "but a written number still strikes"


def test_both_blocks_are_in_the_view_from_the_first_request():
    """Injected, not fetched. A forgotten `read_notes()` costs a whole day and teaches
    nobody anything -- prototype 1 settled this (docs/findings.md); not re-argued."""
    w = World()
    v = sight.view(w)
    assert "YOUR LIST FOR TODAY" in v, "the empty list is shown"
    assert "YOUR MEMORY" in v, "the empty memory is shown"
    # An empty block carries no example of a call, and `why` collapsed to nothing the
    # moment history stopped carrying one. The invitation has to be in the words.
    assert 'todo("...")' in v and "strike(n)" in v, "...and the empty one names both calls"
    assert "remember(name, text)" in v, "...and says which one survives"

    skills.call(w, "todo", {"text": "scout the north-east"})
    skills.call(w, "todo", {"text": "price objective 3"})
    skills.call(w, "strike", {"n": 1})
    skills.call(w, "remember", {"name": "ridge",
                                "text": "impassable west of x20\n- try the gap at y12"})
    v = sight.view(w)
    assert "1. [x] scout the north-east" in v, "a struck item shows as struck"
    assert "2. [ ] price objective 3" in v, "an open one shows as open"
    assert "ridge: impassable west of x20" in v and "- try the gap at y12" in v, "each entry is quoted whole, by name"
    assert ("1 on her list" in
                sight.one_line(w)), "the pane one-liner counts what is open"

    # Both blocks are ours to write, so both can be forged. She once invented four
    # thousand characters of view; a forged list would read back as work she never did.
    assert ("YOUR LIST FOR TODAY" in sight.HALLMARKS
                and "YOUR MEMORY" in sight.HALLMARKS), "both headings are hallmarks"
