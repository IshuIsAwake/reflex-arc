"""Everything about the conversation that does not need Ollama up.


The model call is a thread and a socket, so both are replaced here: `_stream` becomes a
list of canned turns, and threads run inline. That is not a trick -- `pump()` is the
only place display state changes and the only place the world changes, so driving the
queue by hand drives the whole loop exactly as a frame of the game would.

The load-bearing pair is `test_the_view_is_replaced_not_appended` and
`test_the_prompt_promises_exactly_what_exists`. If a view ever lands in `messages`,
gemma spends the sol reasoning over a pile of stale maps, the context fills, Ollama
drops the morning without a word, and the model reads as forgetful rather than starved.
Nothing about that looks wrong from the outside.
"""

import pytest
import json
import types

import chat
import prompts
import settings
import sight
import skills
import world

pytestmark = pytest.mark.usefixtures("inline_threads")


class World(world.World):
    """These suites drive the rover, which happens by day. Dawn's own rules are in
    `test_what_each_phase_allows`."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.phase = "day"


PAD = {"x": 15, "y": 16, "why": "back to the pad"}


def rig(w, replies=(), defiant=False):
    """A Conversation whose model is a script. Returns it and the payloads it sent.

    Each reply is (what it says, what it asks to call). Anything past the end of the
    script is a plain "ok." with no calls, so a tool chain always terminates.

    `defiant=True` asks for skills the request did not carry the schema for. That is not
    a strawman: on the second live run the cap fired eight times in one turn with `tools`
    left out, so the loop must hold against a model that ignores what it was offered.
    The default is the honest client, which asks only for what it was given.
    """
    conv = chat.Conversation(w)
    sent, script = [], list(replies)

    def fake_stream(messages, allowed=None):
        sent.append(messages)
        text, calls = script.pop(0) if script else ("ok.", [])
        if allowed is not None and not defiant:
            calls = [c for c in calls if c.get("name") in allowed]
        if text:
            conv.q.put(("say", text))
        conv.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, calls)))

    conv._stream = fake_stream
    return conv, sent


def test_sol_opens_with_the_numbers():
    w = World()
    c = chat.Conversation(w)
    c.open_day(w)
    assert c.messages[0]["role"] == "system", "system prompt first"
    assert len(c.messages) == 2 and c.messages[1]["role"] == "user", "then one user message"
    assert c.messages[1]["content"] == sight.status_line(w), "which is the status line"
    # The map is not in the morning message. It arrives with the request, the same way
    # it will with every request after it, so there is one path and not two.
    assert sight.GRID_HEADING not in c.messages[1]["content"], "the map is not in it"


# Facts every prompt has to state, and the wordings that count as stating one. Three
# prompts say the same things in different voices, so asserting one phrasing would only
# check which prompt is loaded. The alternatives are per fact, not per prompt: a new
# prompt is free to invent its own wording and must then add it here, which is the point
# at which someone notices they dropped the promise instead of rephrasing it.
PROMISED = {
    # The two facts that decide whether a vague instruction lands on the right cell.
    "says coordinates are absolute": ("ABSOLUTE",),
    # No facing exists, so rather than say so the prompt points at the block that names
    # the compass directions for it. `sight.neighbours` is what has to keep doing that.
    "points at the compass block instead of a facing": ("compass direction",),
    # Watched 2026-08-26: gemma ended a turn on "I will use distance first to confirm
    # the cost", having made two of its eight calls. A reply with no call ends the turn,
    # and it had never been told -- so it forfeited the turn by narrating it.
    "says a wordless turn is a spent one": ("ends your turn",),
    # One goto came back having driven 35 cells and found six outcrops. Aiming far is the
    # highest-yield thing it can do and it defaults to one cell at a time.
    "says goto reaches any distance": ("no range limit", "Aim far",
                                       "long shot into the unknown"),
    "and says not to be timid with it": ("conservative", "inching forward"),
    # Prototype 1 walled its areas and 22% of calls were spent on the border. This arena
    # has no rim, and the prompt has to say so or the habit comes along.
    # `test_world.test_the_whole_arena_is_one_region` is what keeps this claim true.
    "says the far edges are real destinations": ("is not rock can be reached",
                                                 "no wall around it"),
}

# Skills and mechanics that do not exist. Naming one invents a world the model reasons
# about and cannot reach, which is the same failure as a success code for a move that
# never happened.
# `dust storm` came off this list when the weather landed, and `quake` stays on it:
# `hazards.py` has the class and one object in it, and a prompt describing the second
# kind would be inventing it. `read_notes`/`write_notes` came off it when the write path
# landed as `todo`/`strike`/`remember`; `mark(` stays, which is why `avoid="auto"` is
# still refused. `battery` came off it when the step budget became one.
UNBUILT = ("look(", "interact(", "play(", "buy(", "mark(",
           "end_day(", "fly(", "photograph(", "Ingenuity",
           "sandstorm", "quake", "sample", "before dark", "nightfall the rover")


def test_the_prompt_promises_exactly_what_exists():
    p = prompts.sighted()
    # Read off `skills.NAMES` rather than listed here, so a skill added later cannot
    # be wired up and left out of the prompt -- which is a skill she never calls.
    for skill in skills.NAMES:
        assert f"{skill}(" in p, f"names {skill}"
    for absent in UNBUILT:
        assert absent.lower() not in p.lower(), f"says nothing about {absent}"
        # `avoid="auto"` is parsed and refused, so promising it would be promising a
        # refusal. Checked as a bare word because that is how the prompt would say it.
        assert "auto" not in p, f"{name}: does not offer avoid=auto"
        for fact, wordings in PROMISED.items():
            assert any(x in p for x in wordings), f"{name}: {fact}"


def test_the_view_is_replaced_not_appended():
    w = World()
    c, sent = rig(w, [("hello", [])])
    c.open_day(w)
    c.send("what is around you?")
    c.pump()

    assert sight.GRID_HEADING in sent[0][-1]["content"], "the request carried a view"
    assert sent[0][-1]["role"] == "user", "and it was last"
    assert not any(sight.GRID_HEADING in m.get("content", "") for m in c.messages), "but it is not in the history"

    before = len(c.messages)
    c.send("and now?")
    c.pump()
    assert sight.GRID_HEADING in sent[1][-1]["content"], "a second turn sends a fresh view"
    assert sum(sight.GRID_HEADING in m.get("content", "") for m in sent[1]) == 1, "exactly one view per request"
    assert len(c.messages) == before + 2, "history grew by the turn only, not the view"


def test_a_tool_call_round_trips():
    w = World()
    w.pos = (15, 12)
    call = {"name": "goto", "arguments": dict(PAD)}
    c, sent = rig(w, [("", [call]), ("I am beside the pad.", [])])
    c.open_day(w)
    c.send("go back to base")
    c.pump()

    assert w.pos != (15, 12), "the rover moved"
    assert len(c.calls) == 1 and c.calls[0].name == "goto", "the call is on the record"
    assert any(m.get("tool_calls") for m in c.messages), "the assistant turn kept its tool_calls"
    tool = [m for m in c.messages if m["role"] == "tool"]
    assert len(tool) == 1 and "DONE" in tool[0]["content"], "a tool result went back"
    assert c.messages[-1] == {"role": "assistant", "content": "I am beside the pad."}, "gemma got a second turn to speak"
    # The whole reason the view is rebuilt per request rather than per human turn: by
    # the second call the rover has moved, and the old position is a lie.
    assert f"at ({w.pos[0]},{w.pos[1]})" in sent[1][-1]["content"], "the second request re-sent the view from the new position"
    assert (any(who == "call" for who, _ in c.lines)
                and any(who == "result" for who, _ in c.lines)), "the pane shows the call and the result"


def test_a_bad_call_is_counted_and_costs_nothing():
    w = World()
    before = w.steps
    # This was `{"x": 25, "y": 26}` -- a missing `why` -- until 2026-09-01, when that
    # stopped being an error and the counter needed a real one to count. A destination
    # with no y is the honest example: nothing can run and nothing may be guessed.
    call = {"name": "goto", "arguments": {"x": 25}}
    c, _ = rig(w, [("", [call]), ("Sorry -- I left out the y.", [])])
    c.open_day(w)
    c.send("go back to base")
    c.pump()
    assert "BAD_ARGS" in c.calls[0].result, "refused"
    assert w.steps == before, "spent nothing"
    assert c.bad_args == 1, "and it is counted"

    # The case this counter was built for is now the case it must *not* fire on.
    # (15,10), not the pad: the rover lands beside the pad, so arriving there costs
    # nothing and a zero-step drive cannot tell "it ran" from "it was refused".
    w2 = World()
    c2, _ = rig(w2, [("", [{"name": "goto", "arguments": {"x": 15, "y": 10}}]),
                     ("Driven.", [])])
    c2.open_day(w2)
    c2.send("head north")
    c2.pump()
    assert c2.bad_args == 0, "a why-less call is not bad args"
    assert w2.steps > 0, "...and it drove"


def _ran(conv):
    """Tool results that are outcomes rather than refusals."""
    return [m for m in conv.messages
            if m["role"] == "tool" and not m["content"].startswith("REFUSED")]


def test_only_one_call_of_a_batch_ever_runs():
    # Watched 2026-09-04: the 31B asked for six drives in one reply. They ran back to
    # back against a live world, but every target after the first had been chosen off a
    # map several drives out of date -- one view per batch, not one per drive.
    w = World()
    batch = [{"name": "goto", "arguments": {"x": 15, "y": 10 + i}} for i in range(6)]
    c, sent = rig(w, [("", batch), ("Done.", [])])
    c.open_day(w)
    c.send("explore")
    c.pump()
    assert len(_ran(c)) == 1, "exactly one of the six ran"
    assert (sum(1 for m in c.messages
                    if m["role"] == "tool" and "one call at a time" in m["content"]) == 5), "and the other five were refused"
    # `_settle` has already appended the assistant turn carrying all six tool_calls, so
    # a call with no answer dangles off a message nothing responded to.
    asked = sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
    answered = sum(1 for m in c.messages if m["role"] == "tool")
    assert asked == answered, "every call asked for still has an answer"
    assert len(sent) == 2, "and the turn carried on afterwards"

    # Writes are the exception: four todos at dawn lost the fourth, twice, on 14 Oct.
    w = World()
    todo = [{"name": "todo", "arguments": {"text": f"item {i}"}} for i in range(4)]
    drive = [{"name": "goto", "arguments": {"x": 15, "y": 10 + i}} for i in range(2)]
    c, sent = rig(w, [("", todo + drive), ("Done.", [])])
    c.open_day(w)
    c.send("plan, then go")
    c.pump()
    ran = [x.name for x in c.calls]
    assert ran == ["todo"] * 4 + ["goto"], "a run of writes goes through, with the one call after it"
    assert [t for t, _ in w.notes.todos] == [f"item {i}" for i in range(4)], "in order"
    assert (sum(
        1 for m in c.messages if m["role"] == "tool" and "one call at a time" in m["content"])
        == 1), "and the call after that is still refused"
    assert (sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
                == sum(1 for m in c.messages if m["role"] == "tool")), "every call still has an answer"
    w = World()
    c, _ = rig(w, [("", [drive[0], todo[0]]), ("Done.", [])])
    c.open_day(w)
    c.send("go, then plan")
    c.pump()
    assert [x.name for x in c.calls] == ["goto"] and not w.notes.todos, "a write chosen after a drive waits for the drive's outcome"


def test_a_turn_runs_until_she_ends_it():
    w = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    # Words with a call in them do not end the turn; `end` does.
    c, sent = rig(w, [("", [drive]), ("", [drive]), ("Still going.", [drive]),
                      ("", [{"name": "end", "arguments": {"why": "done"}}])])
    c.open_day(w)
    c.send("explore")
    c.pump()
    assert len(_ran(c)) == 4, "she drove three times, then ended"
    assert c.ended, "and the turn is over once she said so"
    assert any(who == "error" and "she called end" in t for who, t in c.lines), "...which the pane says"
    assert len(sent) == 4, "nothing was asked for after it"

    d, sent = rig(World(), [("", [drive]), ("I will look east next.", [])])
    d.open_day(w)
    d.send("explore")
    d.pump()
    assert len(_ran(d)) == 1 and d.ended is False and not d.busy and len(sent) == 2, "a reply with no call in it ends the turn too"


def test_looking_is_paid_for_with_driving():
    w = World()
    # `distance` and `count` cost no steps, so the battery is no backstop: a model
    # looping on one loops forever. The allowance resets on every drive, and reaching it
    # ends the turn -- by day the clock opens another, with both back.
    look = {"name": "distance", "arguments": {"x": 2, "y": 2, "why": "again"}}
    c, _ = rig(w, [("", [look])] * 40, defiant=True)
    c.open_day(w)
    c.send("how far is (2,2)?")
    c.pump()
    assert len(_ran(c)) == settings.FREE_HOPS, "looking stopped at the allowance"
    assert (c.ended and not any(
        m["content"].startswith("REFUSED") for m in c.messages if m["role"] == "tool")), "and the turn ended by itself, with nothing refused"
    assert any(who == "error" and "looks without a drive" in t for who, t in c.lines), "...and says why"

    # A drive buys the looking back.
    w2 = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    script = ([("", [look])] * (settings.FREE_HOPS - 1) + [("", [drive])]
              + [("", [look])] * (settings.FREE_HOPS - 1)
              + [("", [{"name": "end", "arguments": {}}])])
    d, _ = rig(w2, script)
    d.open_day(w2)
    d.send("look around")
    d.pump()
    assert len(_ran(d)) == (settings.FREE_HOPS - 1) * 2 + 2, "driving gives the looking allowance back"


def test_driving_is_capped_and_the_turn_ends_itself():
    w = World()
    far = [{"name": "goto", "arguments": {"x": 15, "y": 10 + (i % 5)}} for i in range(40)]
    c, _ = rig(w, [("", [f]) for f in far], defiant=True)
    c.open_day(w)
    c.send("explore")
    c.pump()
    assert len(_ran(c)) == settings.MOVE_HOPS, "driving stopped at the cap"
    assert (c.ended and not any(
        m["content"].startswith("REFUSED") for m in c.messages if m["role"] == "tool")), "and the turn ended itself, with nothing refused"
    assert (sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
                == sum(1 for m in c.messages if m["role"] == "tool")), "every call asked for has an answer"
    c.send("carry on")
    assert (c.moves == 0 and c.frees == 0
                and "20 drives left" in c._left().replace(str(settings.MOVE_HOPS), "20")), "the next turn has both back"


def test_what_each_phase_allows():
    free = {"distance", "count", "count_cells", "todo", "strike", "remember", "forget"}
    w = World()
    c, _ = rig(w, [])
    assert (set(c._allowed()) == free | {"goto", "execute",
                                                                  "end", "radio"}), "by day, everything"
    keep = settings.COMMS
    settings.COMMS = False
    try:
        assert "radio" not in c._allowed(), "...but no radio with nobody at the desk"
    finally:
        settings.COMMS = keep
    for phase in ("dawn", "dusk", "night"):
        w.phase = phase
        assert set(c._allowed()) == free, f"at {phase}, looking and writing only"
    w.phase, w.day_over = "day", True
    assert not {"goto", "end"} & set(c._allowed()), "a day already over drives nothing and ends nothing"

    # A model that asks anyway is refused, nothing moves, and it counts as a look.
    w = World()
    w.phase = "dawn"
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    d, _ = rig(w, [("", [drive]), ("", [{"name": "end", "arguments": {}}]),
                   ("Ready.", [])], defiant=True)
    d.open_day(w)
    d.send("dawn")
    d.pump()
    refused = [m["content"] for m in d.messages if m["role"] == "tool"]
    assert w.pos == (15, 15) and refused and "only does that by day" in refused[0], "a drive at dawn is refused, and nothing moved"
    assert len(refused) > 1 and "end closes the day" in refused[1], "...and end at dawn too, since end is the day"
    assert d.frees == 2, "both counted as looks"


def test_words_on_an_open_line_cost_battery():
    w = World()
    radio = {"name": "radio", "arguments": {"text": "found a vein; want it sampled?"}}
    c, _ = rig(w, [("", [radio])])
    c.open_day(w)
    c.send("work")
    c.pump()
    assert c.ended, "a radio call ends her turn"
    assert w.battery == settings.BATTERY - settings.RADIO_STEPS and w.steps == 0, "...and costs its battery, from anywhere"
    d, _ = rig(w, [("Yes, sampling it now.", [{"name": "count", "arguments": {}}]),
                   ("", [{"name": "count", "arguments": {}}]), ("Done.", [])])
    d.on_line = True
    d.open_day(w)
    d.send("go ahead")
    d.pump()
    assert w.battery == settings.BATTERY - 3 * settings.RADIO_STEPS, "every reply she speaks on the line costs the same, and silent calls do not"
    w.phase = "night"
    e, _ = rig(w, [("Good night.", [])])
    e.on_line = True
    e.open_day(w)
    e.send("night")
    e.pump()
    assert w.battery == settings.BATTERY - 3 * settings.RADIO_STEPS, "at night words are free"


def test_a_call_written_as_text_is_read_and_run():
    # Measured 2026-08-29 across five prompts at two temperatures: about 7 turns in 10
    # emit a real tool call and the rest type it out, and neither the prompt nor the
    # sampler moves that. Refusing costs a round trip and often gets the same reply
    # back, so a complete call is read out of the text and run.
    w = World()
    typed = 'I will drive north to explore.\ngoto(15, 10, "Driving north")'
    c, _ = rig(w, [(typed, []), ("Drove north and stopped against rock.", [])])
    c.open_day(w)
    c.send("explore the region")
    c.pump()

    assert c.recovered == 1, "it is recovered"
    assert any(who == "error" and "typed out" in t for who, t in c.lines), "and said out loud, not slipped through"
    assert len(c.calls) == 1 and c.calls[0].name == "goto", "the call actually ran"
    assert w.pos == (15, 10), "so the rover moved"
    # The assistant turn has to carry the call, or the tool result that follows answers
    # a question no message ever asked -- the dangling history `_refuse` guards against.
    assert any(m.get("tool_calls") for m in c.messages), "the assistant turn carries the recovered call"
    asked = sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
    answered = sum(1 for m in c.messages if m["role"] == "tool")
    assert asked == answered == 1, "and every call has an answer"

    # Both shapes the model actually uses.
    import skills
    for text in ('goto(35, 25, "east")', 'goto(x=35, y=25, why="east")',
                 "distance(35, 25, 'is it worth it')"):
        got = skills.written_call(text)
        assert bool(got) and got[1]["x"] in (35, "35") and got[1]["why"], f"read {text[:34]!r}"
    # And the shape that only became complete when `why` did. A written call must not
    # be held to a stricter schema than a real one -- see `skills.written_call`.
    for text in ("goto(35, 25)", "distance(x=35, y=25)"):
        got = skills.written_call(text)
        assert bool(got) and got[1]["x"] in (35, "35") and "why" not in got[1], f"read {text!r} without a why"


def test_a_run_of_typed_writes_all_runs():
    """Writes made together all run, and typed ones are no different. The 14 Oct team
    run typed four `todo`s into her first reply of the mission and none of them ran."""
    w = World()
    typed = ("Here is my plan.\n"
             'todo("Explore north of the pad", "Initial mapping")\n'
             'todo("Explore east of the pad", "Initial mapping")\n'
             'remember("plan", "north, then east")')
    c, _ = rig(w, [(typed, []), ("Planned.", [])])
    c.open_day(w)
    c.send("plan your day")
    c.pump()
    assert [x.name for x in c.calls] == ["todo", "todo", "remember"], "all three ran"
    assert (w.notes.todos == [["Explore north of the pad", False],
                                  ["Explore east of the pad", False]]), "onto the list, in order"
    assert w.notes.memory.get("plan") == "north, then east", "and into her memory"
    assert c.recovered == 3, "each one counted"
    assert any(who == "error" and "3 calls were typed out" in t for who, t in c.lines), "and said out loud"
    asked = sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
    answered = sum(1 for m in c.messages if m["role"] == "tool")
    assert asked == answered == 3, "every call has its answer"


def test_an_incomplete_call_is_refused_rather_than_guessed_at():
    import skills
    # A missing coordinate is the incompleteness that still counts. `why` used to be
    # on this list and came off on 2026-09-01 with the requirement itself; a destination
    # with no y is the case where reading it would mean inventing where it meant to go.
    assert skills.written_call("goto(25)") is None, "no y, no recovery"
    assert skills.looks_like_a_call("goto(25)"), "but it is still call-shaped"

    w = World()
    c, _ = rig(w, [("goto(25)", [])] * 6)
    c.open_day(w)
    c.send("explore the region")
    c.pump()
    assert c.narrated == 1, "so it gets a nudge instead"
    assert not c.calls and w.pos == (15, 15), "nothing ran"
    # A backstop that re-asks forever is the cap-that-asks-nicely mistake again.
    assert c.narrated == 1, "one nudge, not six"
    c.send("try again")
    c.pump()
    assert c.narrated == 2, "a fresh turn gets its own"


def test_ordinary_prose_is_left_alone():
    w = World()
    for text in ("I stopped beside the pad and there is rock to the east.",
                 "goto is the right tool here, but I want to know the plan first.",
                 "Nothing to report."):
        c, _ = rig(w, [(text, [])])
        c.open_day(w)
        c.send("what now?")
        c.pump()
        assert c.narrated == 0 and c.recovered == 0 and not c.calls, f"left alone: {text[:44]!r}"
    import skills
    assert not skills.looks_like_a_call("use goto next"), "a bare mention is not a call"
    assert skills.written_call("use goto next") is None, "...nor is it recoverable"


def test_a_fabricated_view_never_reaches_the_context():
    # `runs/20260829-134215/`: one sentence, a typed-out call, then four thousand
    # characters of invented view -- a grid, `399 steps left`, a position it had never
    # occupied. All of it became an assistant message, so from the next turn on the
    # model was reasoning over a map it made up.
    w = World()
    faked = ('I will drive east.\ngoto(25, 15, "east")\n\n'
             'WHAT YOU CAN SEE RIGHT NOW\n'
             'day 1  |  399 steps left  |  at (21,15) on the Jezero flats\n'
             + "?" * 3000)
    c, _ = rig(w, [(faked, []), ("Arrived.", [])])
    c.open_day(w)
    c.send("explore")
    c.pump()

    assert c.faked == 1, "it is counted"
    assert any(who == "error" and "wrote for itself" in t for who, t in c.lines), "and said out loud"
    said = [t for who, t in c.lines if who == "gemma"]
    assert bool(said) and "399 steps" not in said[0], "the pane shows only the real part"
    assert not any("399 steps" in m.get("content", "") for m in c.messages), "and the context holds none of it"
    # The real call in front of the fabrication still counts.
    assert c.recovered == 1 and w.pos == (25, 15), "the call before it was still recovered and run"

    # A reply that merely mentions the heading mid-sentence keeps all of itself.
    kept, dropped = chat.cut_fabrication(
        "the WHAT YOU CAN SEE RIGHT NOW block says there is rock east")
    assert dropped == 0, "a mention mid-line is not a fabrication"


def test_the_request_pins_the_temperature():
    # Measured 2026-08-29: unset, 9 of 12 turns emitted a real call; at 0, 12 of 12.
    # The prompt was never the problem. This test builds the actual payload rather than
    # trusting the setting, because the setting existing is not the same as it shipping.
    import urllib.request
    w = World()
    c = chat.Conversation(w)
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return iter([b'{"done":true,"message":{"content":"ok"}}'])

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen.update(json.loads(req.data))
        return FakeResponse()

    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        c._stream([{"role": "user", "content": "hi"}])
    finally:
        urllib.request.urlopen = real

    assert "temperature" in seen.get("options", {}), "temperature is sent"
    assert seen["options"]["temperature"] == settings.MODEL_TEMP, "and it is the setting, not a literal"
    assert seen["options"].get("num_ctx") == settings.MODEL_CTX, "num_ctx is still set too, and explicitly"
    assert ([t["function"]["name"] for t in seen.get("tools", [])]
                == skills.NAMES), "the tools went with it"


def test_human_turns_are_marked():
    w = World()
    c, _ = rig(w)
    c.open_day(w)
    c.send("what do you want to know?")
    assert ("you", "what do you want to know?") in c.lines, "the human turn is labelled"
    assert {"role": "user", "content": "what do you want to know?"} in c.messages, "and reaches the model as a user turn"
    assert c.busy, "busy until it answers"
    assert c.send("and another") is False, "a second turn cannot jump the queue"


def test_stream_settles():
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    for chunk in ("I am ", "beside ", "the pad."):
        c.q.put(("say", chunk))
    c.q.put(("think", "The pad is one cell south."))
    c.q.put(("done", ({"prompt_eval_count": 120, "eval_count": 8}, [])))
    c.pump()

    assert c.say_buf == "" and c.think_buf == "", "buffers cleared"
    assert not c.busy, "no longer busy"
    assert ("gemma", "I am beside the pad.") in c.lines, "what it said is in the pane"
    assert c.messages[-1] == {"role": "assistant", "content": "I am beside the pad."}, "and in the context"
    # The reasoning is the largest thing it produces, and what has to survive the night
    # is the part it chose to say out loud.
    assert (("think", "The pad is one cell south.") in c.lines
                and not any("one cell south" in m["content"] for m in c.messages)), "thinking shows but is not sent back"
    assert c.last == (c.last[0], 120, 8), "timings recorded"


def test_hiding_the_reasoning_is_a_display_choice_only():
    import render
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    c.q.put(("think", "Weighing up the north-east quadrant."))
    c.q.put(("say", "Going north-east."))
    c.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, [])))
    c.pump()

    shown = " ".join(t for t, _, _ in render._blocks(c, 80, show_thinking=True))
    hidden = " ".join(t for t, _, _ in render._blocks(c, 80, show_thinking=False))
    assert "Weighing up" in shown, "shown when on"
    assert "Weighing up" not in hidden, "gone when off"
    assert "Going north-east." in shown and "Going north-east." in hidden, "what it said survives either way"
    # The tape is written in `write`, which hiding never touches -- so turning the
    # display off can never cost a run its record.
    assert ("think", "Weighing up the north-east quadrant.") in c.lines, "and the line is still on the record"


def test_template_tokens_never_reach_the_context():
    w = World()
    c, _ = rig(w)
    c.busy = True
    c.q.put(("say", "I am beside the pad.<channel|>"))
    c.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, [])))
    c.pump()
    # Found by reading a tape, not by testing: eight of eight gemma turns ended
    # `<channel|>`, and the reply becomes an assistant message, so the token went back
    # into context every turn and into the transcript. It looks like nothing.
    assert ("gemma", "I am beside the pad.") in c.lines, "stripped from what it said"
    assert not any("channel" in m.get("content", "") for m in c.messages), "and from the context"
    assert c.junk == 1, "and counted, so a new one shows up"
    # Explicit list, not a catch-all: eating anything in angle brackets would one day
    # eat real content and never say so.
    assert chat.clean("use <b>bold</b> and 3 < 4")[0] == "use <b>bold</b> and 3 < 4", "real angle brackets survive"


def test_full_context_is_shouted():
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    c.q.put(("say", "fine"))
    c.q.put(("done", ({"prompt_eval_count": int(settings.MODEL_CTX * 0.95),
                       "eval_count": 2}, [])))
    c.pump()
    # Ollama drops the oldest messages without a word, so the model reads as forgetful
    # rather than starved. The pane has to say it or nobody finds out.
    assert any(who == "error" and "context" in text for who, text in c.lines), "says so in the pane"


def test_error_does_not_wedge():
    w = World()
    c, _ = rig(w)
    c.busy = True
    c.q.put(("error", "URLError: connection refused"))
    c.pump()
    assert any(who == "error" for who, _ in c.lines), "shown"
    assert not c.busy and c.send("still there?"), "and it can be talked to again"


def test_an_error_in_the_stream_is_an_error():
    """A cloud model with the cloud down comes back from local Ollama as an `error`
    line, not a failed status. Read as nothing, the turn waited for a `done` for ever."""
    import urllib.request
    for lines, why in (([b'{"error":"model unavailable"}'], "an error line"),
                       ([b'{"message":{"content":"half"}}'], "a stream with no done")):
        c = chat.Conversation(World())

        class FakeResponse:
            def __enter__(self):
                return iter(lines)

            def __exit__(self, *a):
                return False

        real = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse()
        try:
            c._stream([{"role": "user", "content": "hi"}])
        finally:
            urllib.request.urlopen = real
        got = []
        while not c.q.empty():
            got.append(c.q.get()[0])
        assert got and got[-1] == "error", f"{why} ends in an error, not a wait"


def test_the_tape_keeps_the_view_the_pane_drops():
    w = World()
    written = []
    c, _ = rig(w)
    c.tape = types.SimpleNamespace(write=written.append)
    c.open_day(w)
    c.send("hello")
    c.pump()
    views = [r for r in written if r["who"] == "view"]
    assert len(views) == 1, "a view was recorded"
    # Context holds only the newest view, so unless every one is written down as it was,
    # a finished run cannot be read back -- and reading one back, not testing, is how
    # the rock bug was found.
    assert sight.GRID_HEADING in views[0]["text"], "in full, not summarised"
    assert all("\n" not in text for who, text in c.lines if who == "view"), "while the pane got one line"


def test_the_tape_says_what_each_response_cost():
    """Ollama's own count of what the request we really sent really cost.

    Every other figure here is a count of characters, so nothing can be compared across
    a change until this row exists.

    Fields rather than a sentence, because a script reads the row back. `tools` is one of
    them: a capped turn goes out with no schemas, so its prompt is cheaper for a reason
    that has nothing to do with the map, and a row that did not
    say so would look like the view got smaller.
    """
    w = World()
    written = []
    c, _ = rig(w)
    c.tape = types.SimpleNamespace(write=written.append)
    c.open_day(w)
    c.send("hello")
    c.pump()
    rows = [r for r in written if r["who"] == "cost"]
    assert len(rows) == 1, "one row per response"
    row = rows[0]
    assert row["tokens_in"] == 100 and row["tokens_out"] == 5, "carrying Ollama's numbers, not a re-parse of the text"
    assert row["hops"] == 0 and row["tools"] == skills.NAMES, "and where in the turn it was asked, and what it carried"
    assert row["day"] == w.day and isinstance(row["t"], float), "the day and the clock come along, like every other row"
    # The footer already draws this live from `conv.last`. A copy per response in the
    # transcript would push the conversation off its own pane.
    assert not any(who == "cost" for who, _ in c.lines), "and it stays off the pane"
