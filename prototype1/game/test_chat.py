"""Everything about the conversation that does not need Ollama up.

    .venv/bin/python game/test_chat.py

The model call is a thread and a socket, so both are replaced here: `_stream` becomes
a list of canned turns, and threads run inline. That is not a trick -- `pump()` is the
only place display state changes and the only place the world changes, so driving the
queue by hand drives the whole loop exactly as a frame of the game would.

The load-bearing group is `test_the_view_is_replaced_not_appended`. If a view ever
lands in `messages`, gemma spends the day reasoning over a pile of stale maps, the
context fills, Ollama drops the morning without a word, and the model reads as
forgetful rather than starved. Nothing about that looks wrong from the outside.
"""

import sys
import types

import chat
import settings as S
import sight
from world import World


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

    `defiant=True` keeps asking for tools even when the request carried no schemas.
    That is not a strawman: on the second live run the cap fired eight times in one
    turn with `tools` left out, so the loop must hold against a model that ignores it.
    """
    conv = chat.Conversation(w)
    sent, script = [], list(replies)

    def fake_stream(messages, use_tools=True):
        sent.append(messages)
        text, calls = script.pop(0) if script else ("ok.", [])
        if not use_tools and not defiant:
            calls = []
        if text:
            conv.q.put(("say", text))
        conv.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, calls)))

    conv._stream = fake_stream
    return conv, sent


def test_day_opens_with_the_numbers():
    print("the morning")
    w = World()
    c = chat.Conversation(w)
    c.open_day(w)
    ok = check("system prompt first", c.messages[0]["role"] == "system")
    ok &= check("then one user message", len(c.messages) == 2 and c.messages[1]["role"] == "user")
    ok &= check("which is the status line", c.messages[1]["content"] == sight.status_line(w))
    # The map is not in the morning message. It arrives with the request, the same
    # way it will with every request after it, so there is one path and not two.
    ok &= check("the map is not in it", sight.GRID_HEADING not in c.messages[1]["content"])
    return ok


def test_the_prompt_promises_exactly_what_exists():
    print("an honest prompt")
    # This test used to assert the prompt promised *nothing*. It now asserts it
    # promises the two skills that are wired up and no others. A prompt describing a
    # skill that does not exist is the same failure as a success code for a move that
    # never happened: it invents a world the model reasons about and cannot reach.
    ok = check("names goto", "goto(" in chat.SYSTEM)
    ok &= check("names distance", "distance(" in chat.SYSTEM)
    for absent in ("look(", "interact(", "play(", "buy(", "read_notes", "write_notes",
                   "mark(", "end_day("):
        ok &= check(f"does not promise {absent}", absent not in chat.SYSTEM)
    ok &= check("does not offer avoid=auto", "auto" not in chat.SYSTEM)
    # The two facts that decide whether a vague instruction lands on the right cell.
    ok &= check("says coordinates are absolute", "ABSOLUTE" in chat.SYSTEM)
    ok &= check("and that nothing has a facing", "facing" in chat.SYSTEM)
    return ok


def test_the_view_is_replaced_not_appended():
    print("live means replaced")
    w = World()
    S.DAY_MODE = "gemma"
    c, sent = rig(w, [("hello", [])])
    c.open_day(w)
    c.send("what is around you?")
    c.pump()

    ok = check("the request carried a view", sight.GRID_HEADING in sent[0][-1]["content"])
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
    S.DAY_MODE = "gemma"
    call = {"name": "goto", "arguments": {"x": 10, "y": 16, "why": "the shop"}}
    c, sent = rig(w, [("", [call]), ("I am beside the shop.", [])])
    c.open_day(w)
    c.send("go to the shop")
    c.pump()

    ok = check("the world moved", w.pos != (10, 14), str(w.pos))
    ok &= check("the call is on the record", len(c.calls) == 1 and c.calls[0].name == "goto")
    ok &= check("the assistant turn kept its tool_calls",
                any(m.get("tool_calls") for m in c.messages))
    tool = [m for m in c.messages if m["role"] == "tool"]
    ok &= check("a tool result went back", len(tool) == 1 and "DONE" in tool[0]["content"])
    ok &= check("gemma got a second turn to speak",
                c.messages[-1] == {"role": "assistant", "content": "I am beside the shop."})
    # The whole reason the view is rebuilt per request rather than per human turn:
    # by the second call gemma has moved, and the old position is a lie.
    ok &= check("the second request re-sent the view from the new position",
                f"at ({w.pos[0]},{w.pos[1]})" in sent[1][-1]["content"])
    ok &= check("the pane shows the call and the result",
                any(who == "call" for who, _ in c.lines)
                and any(who == "result" for who, _ in c.lines))
    return ok


def test_a_bad_call_is_counted_and_costs_nothing():
    print("BAD_ARGS")
    w = World()
    S.DAY_MODE = "gemma"
    before = w.steps
    call = {"name": "goto", "arguments": {"x": 10, "y": 16}}      # no why
    c, _ = rig(w, [("", [call]), ("Sorry -- I left out the why.", [])])
    c.open_day(w)
    c.send("go to the shop")
    c.pump()
    ok = check("refused", "BAD_ARGS" in c.calls[0].result, c.calls[0].result[:50])
    ok &= check("spent nothing", w.steps == before)
    # FINDINGS asked what the `why` requirement costs. This is the counter that says.
    ok &= check("and it is counted", c.bad_args == 1)
    return ok


def test_the_hop_cap_stops_a_loop():
    print("the hop cap")
    w = World()
    S.DAY_MODE = "gemma"
    # distance costs no steps, so the day's budget is no backstop against this.
    spin = {"name": "distance", "arguments": {"x": 1, "y": 1, "why": "again"}}
    c, _ = rig(w, [("", [spin])] * (S.MODEL_MAX_HOPS + 5))
    c.open_day(w)
    c.send("how far is (1,1)?")
    c.pump()
    ok = check("it was stopped", c.hops <= S.MODEL_MAX_HOPS, f"{c.hops} hops")
    ok &= check("and told why", any(who == "error" and "hop cap" in text
                                    for who, text in c.lines))
    ok &= check("in words gemma can read too",
                any("without saying anything" in m.get("content", "") for m in c.messages))
    # The cap fired four times in one turn on 2026-08-26 because it asked rather than
    # enforced. Once is the whole point: after it, the tools are gone.
    ok &= check("and it fires exactly once",
                sum(1 for who, text in c.lines if who == "error" and "hop cap" in text) == 1)
    ok &= check("not one call ran past the cap",
                sum(1 for m in c.messages if m["role"] == "tool") == S.MODEL_MAX_HOPS,
                f"{sum(1 for m in c.messages if m['role'] == 'tool')} results")
    ok &= check("and the turn is over", not c.busy)

    # Withholding the schemas is a request, not an enforcement. Live, the model kept
    # calling anyway. The cap has to hold against that or it is decoration.
    w2 = World()
    d, _ = rig(w2, [("", [spin])] * 40, defiant=True)
    d.open_day(w2)
    d.send("how far is (1,1)?")
    d.pump()
    ok &= check("a model that ignores tools-off is capped once anyway",
                sum(1 for who, t in d.lines if who == "error" and "hop cap" in t) == 1)
    ok &= check("and its later calls are dropped, not run",
                sum(1 for m in d.messages if m["role"] == "tool") == S.MODEL_MAX_HOPS)
    ok &= check("with the drop said out loud",
                any("dropped" in t for who, t in d.lines if who == "error"))
    return ok


def test_human_turns_are_marked():
    print("who said what")
    w = World()
    c, _ = rig(w)
    c.open_day(w)
    c.send("what do you want to know?")
    ok = check("the human turn is labelled", ("you", "what do you want to know?") in c.lines)
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
    for chunk in ("I am ", "beside ", "the shop."):
        c.q.put(("say", chunk))
    c.q.put(("think", "The shop is two cells south."))
    c.q.put(("done", ({"prompt_eval_count": 120, "eval_count": 8}, [])))
    c.pump()

    ok = check("buffers cleared", c.say_buf == "" and c.think_buf == "")
    ok &= check("no longer busy", not c.busy)
    ok &= check("what it said is in the pane", ("gemma", "I am beside the shop.") in c.lines)
    ok &= check("and in the context",
                c.messages[-1] == {"role": "assistant", "content": "I am beside the shop."})
    # The reasoning is the largest thing it produces, and what has to survive the
    # night is the part it chose to say out loud.
    ok &= check("thinking shows but is not sent back",
                ("think", "The shop is two cells south.") in c.lines
                and not any("two cells south" in m["content"] for m in c.messages))
    ok &= check("timings recorded", c.last == (c.last[0], 120, 8))
    return ok


def test_full_context_is_shouted():
    print("the 4096 trap")
    w = World()
    c = chat.Conversation(w)
    c.busy = True
    c.q.put(("say", "fine"))
    c.q.put(("done", ({"prompt_eval_count": int(S.MODEL_CTX * 0.95), "eval_count": 2}, [])))
    c.pump()
    # Ollama drops the oldest messages without a word, so the model reads as
    # forgetful rather than starved. The pane has to say it or nobody finds out.
    return check("says so in the pane", any(who == "error" and "context" in text
                                            for who, text in c.lines))


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
    S.DAY_MODE = "gemma"
    written = []
    c, _ = rig(w)
    c.tape = types.SimpleNamespace(write=written.append)
    c.open_day(w)
    c.send("hello")
    c.pump()
    views = [r for r in written if r["who"] == "view"]
    ok = check("a view was recorded", len(views) == 1)
    # Context holds only the newest view, so unless every one is written down as it
    # was, a finished run cannot be read back -- and reading one back, not testing,
    # is how the wall bug was found.
    ok &= check("in full, not summarised", sight.GRID_HEADING in views[0]["text"])
    ok &= check("while the pane got one line",
                all("\n" not in text for who, text in c.lines if who == "view"))
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_day_opens_with_the_numbers(),
               test_the_prompt_promises_exactly_what_exists(),
               test_the_view_is_replaced_not_appended(),
               test_a_tool_call_round_trips(),
               test_a_bad_call_is_counted_and_costs_nothing(),
               test_the_hop_cap_stops_a_loop(),
               test_human_turns_are_marked(), test_stream_settles(),
               test_full_context_is_shouted(), test_error_does_not_wedge(),
               test_the_tape_keeps_the_view_the_pane_drops()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
