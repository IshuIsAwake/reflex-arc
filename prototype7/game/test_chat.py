"""Everything about the conversation that does not need Ollama up.

    .venv/bin/python game/test_chat.py

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

import json
import sys
import types

import chat
import prompts
import settings as S
import sight
import skills
from world import World

# Clear skies unless a suite asks otherwise. The weather is real and shipped on,
# but it is a scenario, not terrain -- letting one drift across an arena would make
# every route assertion here depend on STORM_RADIUS. `test_hazards.py` turns it on.
S.STORM_ON = False


PAD = {"x": 15, "y": 16, "why": "back to the pad"}


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


class Inline:
    """A 'thread' that runs where it stands, so one send() drives a whole exchange."""

    def __init__(self, target, args=(), daemon=False):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


chat.threading = types.SimpleNamespace(Thread=Inline)


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
    print("the morning")
    w = World()
    c = chat.Conversation(w)
    c.open_day(w)
    ok = check("system prompt first", c.messages[0]["role"] == "system")
    ok &= check("then one user message",
                len(c.messages) == 2 and c.messages[1]["role"] == "user")
    ok &= check("which is the status line",
                c.messages[1]["content"] == sight.status_line(w))
    # The map is not in the morning message. It arrives with the request, the same way
    # it will with every request after it, so there is one path and not two.
    ok &= check("the map is not in it",
                sight.GRID_HEADING not in c.messages[1]["content"])
    return ok


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
# kind would be inventing it.
UNBUILT = ("look(", "interact(", "play(", "buy(", "read_notes", "write_notes", "mark(",
           "end_day(", "fly(", "photograph(", "Ingenuity",
           "sandstorm", "quake", "battery", "sample", "before dark", "nightfall the rover")


def test_every_prompt_promises_exactly_what_exists():
    """Run over all of `prompts.PROMPTS`, not just the live one.

    A prompt kept around to be re-measured against is still a prompt someone can select
    with a flag, so it has to stay honest. Checking only the default would let a shelved
    one rot into promising a skill that has since been deleted.
    """
    print("honest prompts")
    ok = True
    for name in prompts.PROMPTS:
        p = prompts.PROMPTS[name]()
        # Read off `skills.NAMES` rather than listed here, so a skill added later cannot
        # be wired up and left out of the prompt -- which is a skill she never calls.
        for skill in skills.NAMES:
            ok &= check(f"{name}: names {skill}", f"{skill}(" in p)
        for absent in UNBUILT:
            ok &= check(f"{name}: says nothing about {absent}", absent.lower() not in p.lower())
        # `avoid="auto"` is parsed and refused, so promising it would be promising a
        # refusal. Checked as a bare word because that is how the prompt would say it.
        ok &= check(f"{name}: does not offer avoid=auto", "auto" not in p)
        for fact, wordings in PROMISED.items():
            ok &= check(f"{name}: {fact}", any(x in p for x in wordings))
    return ok


def test_the_live_prompt_matches_the_map_it_ships_with():
    """The 2026-09-04 loss: two runs read under a prompt describing the grid's ruler
    while `--map rle` was running. The map paragraph is built from `MAP_FORMAT`, so the
    two cannot disagree -- this is what proves the wiring, in both directions."""
    print("the prompt describes the map actually being sent")
    import settings as S
    keep = S.MAP_FORMAT
    ok = True
    try:
        S.MAP_FORMAT = "grid"
        p = prompts.use("old")
        ok &= check("grid: describes the ruler", "ruler across the top" in p)
        ok &= check("grid: says nothing about runs", "x7-9 rock" not in p)
        S.MAP_FORMAT = "rle"
        p = prompts.use("old")
        ok &= check("rle: describes the runs", "x7-9 rock" in p)
        ok &= check("rle: says nothing about the ruler", "ruler across the top" not in p)
    finally:
        S.MAP_FORMAT = keep
        prompts.use(prompts.DEFAULT)
    return ok


def test_the_view_is_replaced_not_appended():
    print("live means replaced")
    w = World()
    c, sent = rig(w, [("hello", [])])
    c.open_day(w)
    c.send("what is around you?")
    c.pump()

    ok = check("the request carried a view",
               sight.GRID_HEADING in sent[0][-1]["content"])
    ok &= check("and it was last", sent[0][-1]["role"] == "user")
    ok &= check("but it is not in the history",
                not any(sight.GRID_HEADING in m.get("content", "") for m in c.messages))

    before = len(c.messages)
    c.send("and now?")
    c.pump()
    ok &= check("a second turn sends a fresh view",
                sight.GRID_HEADING in sent[1][-1]["content"])
    ok &= check("exactly one view per request",
                sum(sight.GRID_HEADING in m.get("content", "") for m in sent[1]) == 1)
    ok &= check("history grew by the turn only, not the view",
                len(c.messages) == before + 2, f"{before} -> {len(c.messages)}")
    return ok


def test_a_tool_call_round_trips():
    print("goto, end to end")
    w = World()
    w.pos = (15, 12)
    call = {"name": "goto", "arguments": dict(PAD)}
    c, sent = rig(w, [("", [call]), ("I am beside the pad.", [])])
    c.open_day(w)
    c.send("go back to base")
    c.pump()

    ok = check("the rover moved", w.pos != (15, 12), str(w.pos))
    ok &= check("the call is on the record",
                len(c.calls) == 1 and c.calls[0].name == "goto")
    ok &= check("the assistant turn kept its tool_calls",
                any(m.get("tool_calls") for m in c.messages))
    tool = [m for m in c.messages if m["role"] == "tool"]
    ok &= check("a tool result went back",
                len(tool) == 1 and "DONE" in tool[0]["content"])
    ok &= check("gemma got a second turn to speak",
                c.messages[-1] == {"role": "assistant", "content": "I am beside the pad."})
    # The whole reason the view is rebuilt per request rather than per human turn: by
    # the second call the rover has moved, and the old position is a lie.
    ok &= check("the second request re-sent the view from the new position",
                f"at ({w.pos[0]},{w.pos[1]})" in sent[1][-1]["content"])
    ok &= check("the pane shows the call and the result",
                any(who == "call" for who, _ in c.lines)
                and any(who == "result" for who, _ in c.lines))
    return ok


def test_a_bad_call_is_counted_and_costs_nothing():
    print("BAD_ARGS")
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
    ok = check("refused", "BAD_ARGS" in c.calls[0].result, c.calls[0].result[:50])
    ok &= check("spent nothing", w.steps == before)
    ok &= check("and it is counted", c.bad_args == 1)

    # The case this counter was built for is now the case it must *not* fire on.
    # (15,10), not the pad: the rover lands beside the pad, so arriving there costs
    # nothing and a zero-step drive cannot tell "it ran" from "it was refused".
    w2 = World()
    c2, _ = rig(w2, [("", [{"name": "goto", "arguments": {"x": 15, "y": 10}}]),
                     ("Driven.", [])])
    c2.open_day(w2)
    c2.send("head north")
    c2.pump()
    ok &= check("a why-less call is not bad args", c2.bad_args == 0,
                c2.calls[0].result[:60])
    ok &= check("...and it drove", w2.steps > 0, f"{w2.steps} steps")
    return ok


def _ran(conv):
    """Tool results that are outcomes rather than refusals."""
    return [m for m in conv.messages
            if m["role"] == "tool" and not m["content"].startswith("REFUSED")]


def test_only_one_call_of_a_batch_ever_runs():
    print("one call at a time")
    # Watched 2026-09-04: the 31B asked for six drives in one reply. They ran back to
    # back against a live world, but every target after the first had been chosen off a
    # map several drives out of date -- one view per batch, not one per drive.
    w = World()
    batch = [{"name": "goto", "arguments": {"x": 15, "y": 10 + i}} for i in range(6)]
    c, sent = rig(w, [("", batch), ("Done.", [])])
    c.open_day(w)
    c.send("explore")
    c.pump()
    ok = check("exactly one of the six ran", len(_ran(c)) == 1, f"{len(_ran(c))} ran")
    ok &= check("and the other five were refused",
                sum(1 for m in c.messages
                    if m["role"] == "tool" and "one call at a time" in m["content"]) == 5)
    # `_settle` has already appended the assistant turn carrying all six tool_calls, so
    # a call with no answer dangles off a message nothing responded to.
    asked = sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
    answered = sum(1 for m in c.messages if m["role"] == "tool")
    ok &= check("every call asked for still has an answer", asked == answered,
                f"{asked} asked, {answered} answered")
    ok &= check("and the turn carried on afterwards", len(sent) == 2, f"{len(sent)} sent")
    return ok


def test_a_turn_runs_until_she_ends_it():
    print("end, not silence")
    w = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    # Words alone no longer hand back: only `end` does. Three drives, a sentence with no
    # call in it, then `end`.
    c, sent = rig(w, [("", [drive]), ("", [drive]), ("Still going.", [drive]),
                      ("", [{"name": "end", "arguments": {"why": "done"}}])])
    c.open_day(w)
    c.send("explore")
    c.pump()
    ok = check("she drove three times", len(_ran(c)) == 4, f"{len(_ran(c))} calls ran")
    ok &= check("and the turn is over only once she said so", c.ended)
    ok &= check("...which the pane says",
                any(who == "error" and "she called end" in t for who, t in c.lines))
    ok &= check("nothing was asked for after it", len(sent) == 4, f"{len(sent)} sent")
    ok &= check("and the sol is untouched -- end ends a turn, not a day",
                not w.day_over and w.steps_left > 0)
    return ok


def test_looking_is_paid_for_with_driving():
    print("the two allowances")
    w = World()
    # `distance` and `count` cost no steps, so the day's budget is no backstop: a model
    # looping on one loops forever. The allowance resets on every drive, so more looking
    # has to be bought with moving -- and moving is capped, so the turn terminates.
    look = {"name": "distance", "arguments": {"x": 2, "y": 2, "why": "again"}}
    c, _ = rig(w, [("", [look])] * 40, defiant=True)
    c.open_day(w)
    c.send("how far is (2,2)?")
    c.pump()
    ok = check("looking stopped at the allowance", len(_ran(c)) == S.FREE_HOPS,
               f"{len(_ran(c))} ran")
    ok &= check("and the turn was ended for her", c.ended)
    ok &= check("after exactly FREE_GRACE refusals",
                sum(1 for m in c.messages
                    if m["role"] == "tool" and m["content"].startswith("REFUSED"))
                == S.FREE_GRACE)
    ok &= check("with gemma told, not just the pane",
                any("REFUSED" in m.get("content", "") for m in c.messages))

    # A drive buys the looking back. Five looks, one drive, five more looks: eleven
    # calls run where the flat allowance would have stopped at five.
    w2 = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    script = ([("", [look])] * S.FREE_HOPS + [("", [drive])]
              + [("", [look])] * S.FREE_HOPS
              + [("", [{"name": "end", "arguments": {}}])])
    d, _ = rig(w2, script)
    d.open_day(w2)
    d.send("look around")
    d.pump()
    ok &= check("driving gives the looking allowance back",
                len(_ran(d)) == S.FREE_HOPS * 2 + 2, f"{len(_ran(d))} ran")
    ok &= check("...and it really was reset, not merely raised", d.frees <= S.FREE_HOPS)
    return ok


def test_driving_is_capped_and_the_turn_ends_itself():
    print("the drive cap")
    w = World()
    # A model that never calls `end` still has to stop. Refusing forever is its own
    # failure -- a whole turn spent being told no -- so the grace is what ends it.
    far = [{"name": "goto", "arguments": {"x": 15, "y": 10 + (i % 5)}} for i in range(40)]
    c, _ = rig(w, [("", [f]) for f in far], defiant=True)
    c.open_day(w)
    c.send("explore")
    c.pump()
    ok = check("driving stopped at the cap", len(_ran(c)) == S.MOVE_HOPS,
               f"{len(_ran(c))} ran")
    ok &= check("and the turn ended itself", c.ended)
    ok &= check("after exactly MOVE_GRACE refusals",
                sum(1 for m in c.messages
                    if m["role"] == "tool" and m["content"].startswith("REFUSED"))
                == S.MOVE_GRACE)
    ok &= check("every call asked for has an answer",
                sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
                == sum(1 for m in c.messages if m["role"] == "tool"))
    return ok


def test_ending_is_never_refused():
    print("the way out is always open")
    # If `end` were budgeted, a turn that had run out of everything else could not do
    # the one thing that gets it out. Spend the drive allowance, then end.
    #
    # `defiant`, because the schema for `goto` is withdrawn once the drives are gone --
    # so a model that respects the request cannot reach the refusal path at all. This
    # asserts the backstop under the model that ignores it.
    w = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    script = ([("", [drive])] * (S.MOVE_HOPS + 1)
              + [("", [{"name": "end", "arguments": {}}])])
    c, _ = rig(w, script, defiant=True)
    c.open_day(w)
    c.send("explore")
    c.pump()
    ok = check("the drive past the cap was refused",
               any(m["content"].startswith("REFUSED")
                   for m in c.messages if m["role"] == "tool"))
    ok &= check("but end still ran", any(m["role"] == "tool" and m["content"]
                                         .startswith("END") for m in c.messages))
    ok &= check("and it ended the turn", c.ended)
    return ok


def test_a_spent_allowance_withdraws_the_schema():
    """The cap stops being an argument and becomes an absence.

    Watched 2026-09-04 on `runs/20260904-224619`: with the drives gone, the 31B re-sent
    the identical `goto` three times and had the turn ended for it, four turns out of
    five. The refusal was reaching it -- ~57 tokens landing into a ~6,700-token prompt
    whose bulk was a map that had not changed, and it lost every time. So the skill it
    cannot afford is left out of the request instead.
    """
    print("what is not offered cannot be asked for")
    w = World()
    drive = {"name": "goto", "arguments": {"x": 15, "y": 12}}
    look = {"name": "distance", "arguments": {"x": 2, "y": 2}}
    c, sent = rig(w, [("", [drive])] * S.MOVE_HOPS + [("", [look]), ("", [look])])
    c.open_day(w)
    c.send("explore")
    c.pump()

    ok = check("every drive of the allowance ran", c.moves == S.MOVE_HOPS, str(c.moves))
    ok &= check("and then goto was withdrawn", "goto" not in c._allowed(),
                str(c._allowed()))
    ok &= check("but end never is", "end" in c._allowed())
    ok &= check("and the free skills stay while they are affordable",
                "count" in c._allowed())
    # The refusal path is a backstop for a model that ignores the schema, so an honest
    # one must never reach it: no refusal, and the turn ends by running out of script.
    ok &= check("so nothing was refused", c.move_denied == 0, str(c.move_denied))

    # Spend the looks too. With both gone the request carries one way out and no others.
    # Driven through the script rather than set by hand: `send` resets the counters, so
    # a turn posed as already-spent is not one.
    d, _ = rig(World(), [("", [drive])] * S.MOVE_HOPS + [("", [look])] * S.FREE_HOPS)
    d.open_day(w)
    d.send("explore, then look around")
    d.pump()
    ok &= check("a turn with nothing left is offered end alone",
                d._allowed() == ("end",), str(d._allowed()))
    ok &= check("and the schemas really are filtered, not just the names",
                [t["function"]["name"] for t in skills.tools_for(d._allowed())] == ["end"])
    # `_left` is what it reads on the way there, and it used to promise a drive back.
    ok &= check("the allowance note does not promise a drive it cannot make",
                "before you have to drive again" not in d._left(), d._left())
    ok &= check("...and names the way out instead", "end" in d._left(), d._left())
    return ok


def test_a_call_written_as_text_is_read_and_run():
    print("typed out, not made")
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

    ok = check("it is recovered", c.recovered == 1, f"recovered={c.recovered}")
    ok &= check("and said out loud, not slipped through",
                any(who == "error" and "typed out" in t for who, t in c.lines))
    ok &= check("the call actually ran", len(c.calls) == 1 and c.calls[0].name == "goto")
    ok &= check("so the rover moved", w.pos == (15, 10), str(w.pos))
    # The assistant turn has to carry the call, or the tool result that follows answers
    # a question no message ever asked -- the dangling history `_refuse` guards against.
    ok &= check("the assistant turn carries the recovered call",
                any(m.get("tool_calls") for m in c.messages))
    asked = sum(len(m["tool_calls"]) for m in c.messages if m.get("tool_calls"))
    answered = sum(1 for m in c.messages if m["role"] == "tool")
    ok &= check("and every call has an answer", asked == answered == 1,
                f"{asked} asked, {answered} answered")

    # Both shapes the model actually uses.
    import skills
    for text in ('goto(35, 25, "east")', 'goto(x=35, y=25, why="east")',
                 "distance(35, 25, 'is it worth it')"):
        got = skills.written_call(text)
        ok &= check(f"read {text[:34]!r}",
                    bool(got) and got[1]["x"] in (35, "35") and got[1]["why"], str(got))
    # And the shape that only became complete when `why` did. A written call must not
    # be held to a stricter schema than a real one -- see `skills.written_call`.
    for text in ("goto(35, 25)", "distance(x=35, y=25)"):
        got = skills.written_call(text)
        ok &= check(f"read {text!r} without a why",
                    bool(got) and got[1]["x"] in (35, "35") and "why" not in got[1],
                    str(got))
    return ok


def test_an_incomplete_call_is_refused_rather_than_guessed_at():
    print("...but only a complete one")
    import skills
    # A missing coordinate is the incompleteness that still counts. `why` used to be
    # on this list and came off on 2026-09-01 with the requirement itself; a destination
    # with no y is the case where reading it would mean inventing where it meant to go.
    ok = check("no y, no recovery", skills.written_call("goto(25)") is None)
    ok &= check("but it is still call-shaped",
                skills.looks_like_a_call("goto(25)"))

    w = World()
    c, _ = rig(w, [("goto(25)", [])] * 6)
    c.open_day(w)
    c.send("explore the region")
    c.pump()
    ok &= check("so it gets a nudge instead", c.narrated == 1, f"{c.narrated}")
    ok &= check("nothing ran", not c.calls and w.pos == (15, 15))
    # A backstop that re-asks forever is the cap-that-asks-nicely mistake again.
    ok &= check("one nudge, not six", c.narrated == 1)
    c.send("try again")
    c.pump()
    ok &= check("a fresh turn gets its own", c.narrated == 2, f"{c.narrated}")
    return ok


def test_ordinary_prose_is_left_alone():
    print("not everything with 'goto' in it")
    w = World()
    for text in ("I stopped beside the pad and there is rock to the east.",
                 "goto is the right tool here, but I want to know the plan first.",
                 "Nothing to report."):
        c, _ = rig(w, [(text, [])])
        c.open_day(w)
        c.send("what now?")
        c.pump()
        ok = check(f"left alone: {text[:44]!r}",
                   c.narrated == 0 and c.recovered == 0 and not c.calls)
        if not ok:
            return False
    import skills
    ok = check("a bare mention is not a call", not skills.looks_like_a_call("use goto next"))
    ok &= check("...nor is it recoverable", skills.written_call("use goto next") is None)
    return ok


def test_a_fabricated_view_never_reaches_the_context():
    print("it wrote our half of the conversation")
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

    ok = check("it is counted", c.faked == 1, f"faked={c.faked}")
    ok &= check("and said out loud",
                any(who == "error" and "wrote for itself" in t for who, t in c.lines))
    said = [t for who, t in c.lines if who == "gemma"]
    ok &= check("the pane shows only the real part",
                bool(said) and "399 steps" not in said[0], str(said[:1])[:70])
    ok &= check("and the context holds none of it",
                not any("399 steps" in m.get("content", "") for m in c.messages))
    # The real call in front of the fabrication still counts.
    ok &= check("the call before it was still recovered and run",
                c.recovered == 1 and w.pos == (25, 15), str(w.pos))

    # A reply that merely mentions the heading mid-sentence keeps all of itself.
    kept, dropped = chat.cut_fabrication(
        "the WHAT YOU CAN SEE RIGHT NOW block says there is rock east")
    ok &= check("a mention mid-line is not a fabrication", dropped == 0, kept)
    return ok


def test_the_request_pins_the_temperature():
    print("the sampler is not left to chance")
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

    ok = check("temperature is sent", "temperature" in seen.get("options", {}),
               str(seen.get("options")))
    ok &= check("and it is the setting, not a literal",
                seen["options"]["temperature"] == S.MODEL_TEMP)
    ok &= check("num_ctx is still set too, and explicitly",
                seen["options"].get("num_ctx") == S.MODEL_CTX)
    ok &= check("the tools went with it",
                [t["function"]["name"] for t in seen.get("tools", [])]
                == skills.NAMES)
    return ok


def test_human_turns_are_marked():
    print("who said what")
    w = World()
    c, _ = rig(w)
    c.open_day(w)
    c.send("what do you want to know?")
    ok = check("the human turn is labelled",
               ("you", "what do you want to know?") in c.lines)
    ok &= check("and reaches the model as a user turn",
                {"role": "user", "content": "what do you want to know?"} in c.messages)
    ok &= check("busy until it answers", c.busy)
    ok &= check("a second turn cannot jump the queue", c.send("and another") is False)
    return ok


def test_stream_settles():
    print("a streamed reply")
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    for chunk in ("I am ", "beside ", "the pad."):
        c.q.put(("say", chunk))
    c.q.put(("think", "The pad is one cell south."))
    c.q.put(("done", ({"prompt_eval_count": 120, "eval_count": 8}, [])))
    c.pump()

    ok = check("buffers cleared", c.say_buf == "" and c.think_buf == "")
    ok &= check("no longer busy", not c.busy)
    ok &= check("what it said is in the pane",
                ("gemma", "I am beside the pad.") in c.lines)
    ok &= check("and in the context",
                c.messages[-1] == {"role": "assistant", "content": "I am beside the pad."})
    # The reasoning is the largest thing it produces, and what has to survive the night
    # is the part it chose to say out loud.
    ok &= check("thinking shows but is not sent back",
                ("think", "The pad is one cell south.") in c.lines
                and not any("one cell south" in m["content"] for m in c.messages))
    ok &= check("timings recorded", c.last == (c.last[0], 120, 8))
    return ok


def test_hiding_the_reasoning_is_a_display_choice_only():
    print("H hides, it does not delete")
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
    ok = check("shown when on", "Weighing up" in shown)
    ok &= check("gone when off", "Weighing up" not in hidden)
    ok &= check("what it said survives either way",
                "Going north-east." in shown and "Going north-east." in hidden)
    # The tape is written in `write`, which hiding never touches -- so turning the
    # display off can never cost a run its record.
    ok &= check("and the line is still on the record",
                ("think", "Weighing up the north-east quadrant.") in c.lines)
    return ok


def test_template_tokens_never_reach_the_context():
    print("scaffolding")
    w = World()
    c, _ = rig(w)
    c.busy = True
    c.q.put(("say", "I am beside the pad.<channel|>"))
    c.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, [])))
    c.pump()
    # Found by reading a tape, not by testing: eight of eight gemma turns ended
    # `<channel|>`, and the reply becomes an assistant message, so the token went back
    # into context every turn and into the transcript. It looks like nothing.
    ok = check("stripped from what it said",
               ("gemma", "I am beside the pad.") in c.lines)
    ok &= check("and from the context",
                not any("channel" in m.get("content", "") for m in c.messages))
    ok &= check("and counted, so a new one shows up", c.junk == 1)
    # Explicit list, not a catch-all: eating anything in angle brackets would one day
    # eat real content and never say so.
    ok &= check("real angle brackets survive",
                chat.clean("use <b>bold</b> and 3 < 4")[0] == "use <b>bold</b> and 3 < 4")
    return ok


def test_full_context_is_shouted():
    print("the 4096 trap")
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    c.q.put(("say", "fine"))
    c.q.put(("done", ({"prompt_eval_count": int(S.MODEL_CTX * 0.95),
                       "eval_count": 2}, [])))
    c.pump()
    # Ollama drops the oldest messages without a word, so the model reads as forgetful
    # rather than starved. The pane has to say it or nobody finds out.
    return check("says so in the pane",
                 any(who == "error" and "context" in text for who, text in c.lines))


def test_error_does_not_wedge():
    print("ollama down")
    w = World()
    c, _ = rig(w)
    c.busy = True
    c.q.put(("error", "URLError: connection refused"))
    c.pump()
    ok = check("shown", any(who == "error" for who, _ in c.lines))
    ok &= check("and it can be talked to again", not c.busy and c.send("still there?"))
    return ok


def test_the_tape_keeps_the_view_the_pane_drops():
    print("the tape")
    w = World()
    written = []
    c, _ = rig(w)
    c.tape = types.SimpleNamespace(write=written.append)
    c.open_day(w)
    c.send("hello")
    c.pump()
    views = [r for r in written if r["who"] == "view"]
    ok = check("a view was recorded", len(views) == 1)
    # Context holds only the newest view, so unless every one is written down as it was,
    # a finished run cannot be read back -- and reading one back, not testing, is how
    # the rock bug was found.
    ok &= check("in full, not summarised", sight.GRID_HEADING in views[0]["text"])
    ok &= check("while the pane got one line",
                all("\n" not in text for who, text in c.lines if who == "view"))
    return ok


def test_the_tape_says_what_each_response_cost():
    """Ollama's own count of what the request we really sent really cost.

    Every other figure here is a count of characters, so nothing can be compared across
    a change until this row exists.

    Fields rather than a sentence, because a script reads the row back. `tools` is one of
    them: a capped turn goes out with no schemas, so its prompt is cheaper for a reason
    that has nothing to do with the map, and a row that did not
    say so would look like the view got smaller.
    """
    print("cost")
    w = World()
    written = []
    c, _ = rig(w)
    c.tape = types.SimpleNamespace(write=written.append)
    c.open_day(w)
    c.send("hello")
    c.pump()
    rows = [r for r in written if r["who"] == "cost"]
    ok = check("one row per response", len(rows) == 1, f"{len(rows)} rows")
    if not ok:
        return ok
    row = rows[0]
    ok &= check("carrying Ollama's numbers, not a re-parse of the text",
                row["tokens_in"] == 100 and row["tokens_out"] == 5, str(row))
    ok &= check("and where in the turn it was asked, and what it carried",
                row["hops"] == 0 and row["tools"] == skills.NAMES, str(row))
    ok &= check("the day and the clock come along, like every other row",
                row["day"] == w.day and isinstance(row["t"], float))
    # The footer already draws this live from `conv.last`. A copy per response in the
    # transcript would push the conversation off its own pane.
    ok &= check("and it stays off the pane",
                not any(who == "cost" for who, _ in c.lines))
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_sol_opens_with_the_numbers(),
               test_every_prompt_promises_exactly_what_exists(),
               test_the_view_is_replaced_not_appended(),
               test_a_tool_call_round_trips(),
               test_a_bad_call_is_counted_and_costs_nothing(),
               test_only_one_call_of_a_batch_ever_runs(),
               test_a_turn_runs_until_she_ends_it(),
               test_looking_is_paid_for_with_driving(),
               test_driving_is_capped_and_the_turn_ends_itself(),
               test_ending_is_never_refused(),
               test_a_spent_allowance_withdraws_the_schema(),
               test_a_call_written_as_text_is_read_and_run(),
               test_an_incomplete_call_is_refused_rather_than_guessed_at(),
               test_ordinary_prose_is_left_alone(),
               test_a_fabricated_view_never_reaches_the_context(),
               test_the_request_pins_the_temperature(),
               test_human_turns_are_marked(), test_stream_settles(),
               test_hiding_the_reasoning_is_a_display_choice_only(),
               test_template_tokens_never_reach_the_context(),
               test_full_context_is_shouted(), test_error_does_not_wedge(),
               test_the_tape_keeps_the_view_the_pane_drops(),
               test_the_tape_says_what_each_response_cost()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
