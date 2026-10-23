"""The sol's four phases and the desk's place in each: dawn, a day on the wall clock,
dusk, night -- with the one urgent message, the radio line, and replay.


The model is a script and threads run inline, as in `test_chat.py`. `fly` stands in for
`main.py`'s loop -- pump, tick the clock, roll the night over when it says so -- with
one frame a second of pretend time, so the day's clock and the desk's waits are counted
rather than slept through. Nobody is at the desk unless a test says so.
"""

import pytest
import json
import tempfile
import time
import types
from pathlib import Path

import autopilot
import chat
import prompts
import replay
import settings as S
import skills
from world import World

pytestmark = pytest.mark.usefixtures("inline_threads")


@pytest.fixture(autouse=True)
def nobody_at_the_desk():
    S.COMMS = False


def call(skill, **args):
    return {"name": skill, "arguments": args}


END = ("Done for today.", [call("end")])
READY = ("Ready for the day.", [])
REPORT = ("Today I drove north. Nothing found yet; the east is still unseen.", [])


class Model:
    """Replies in order, shared across every sol's conversation. Past the end it ends.

    A reply that is the string "down" is a request that never reached the model.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def talk(self, conv):
        def stream(messages, allowed=None):
            self.sent.append(messages)
            reply = self.replies.pop(0) if self.replies else END
            if reply == "down":
                conv.q.put(("error", "URLError: connection refused"))
                return
            text, calls = reply
            if text:
                conv.q.put(("say", text))
            conv.q.put(("done", ({"prompt_eval_count": 100, "eval_count": 5}, calls)))
        conv._stream = stream
        return conv


def fly(w, model, frames=400, link=None):
    """`main.py`'s loop with the pygame taken out, nobody at the window. Returns
    (convs, rows, nights)."""
    rows = []
    w.recorder = lambda kind, **f: rows.append({"kind": kind, **f})
    convs = [model.talk(chat.Conversation(w, link=link))]
    convs[0].open_day(w)
    pilot, nights = autopilot.Autopilot(), 0
    for t in range(frames):
        convs[-1].pump()
        if pilot.tick(convs[-1], w, now=float(t)) == "night":
            nights += 1
            if S.MISSION_SOLS and w.day >= S.MISSION_SOLS:
                break
            w.next_day()
            convs.append(model.talk(chat.Conversation(w, link=link)))
            convs[-1].open_day(w)
            pilot = autopilot.Autopilot(words=pilot.words)
    return convs, rows, nights


def said_by(conv, who):
    return [text for w, text in conv.lines if w == who]


class Desk:
    """Someone at the desk -- or not -- for the length of a `with`, and `MISSION_SOLS`."""

    def __init__(self, on=True, sols=0):
        self.on, self.sols = on, sols

    def __enter__(self):
        self.keep = S.COMMS, S.MISSION_SOLS
        S.COMMS, S.MISSION_SOLS = self.on, self.sols
        prompts.use(prompts.DEFAULT)

    def __exit__(self, *exc):
        S.COMMS, S.MISSION_SOLS = self.keep
        prompts.use(prompts.DEFAULT)


def sol(w, model, rover=None, attended=True):
    """One sol's conversation and clock, as `main.py` holds them with a window open.
    `rover`, a one-item list, says whether the rover has finished its leg -- False holds
    the next request."""
    rows = []
    w.recorder = lambda kind, **f: rows.append({"kind": kind, **f})
    c = model.talk(chat.Conversation(w))
    if rover is not None:
        c.ready = lambda: rover[0]
    c.open_day(w)
    return c, autopilot.Autopilot(attended=attended), rows


def until(c, pilot, w, test, start=0, frames=300):
    """Frames until `test(result)` holds. Returns (frame, result), or (None, None)."""
    for t in range(start, start + frames):
        c.pump()
        got = pilot.tick(c, w, now=float(t))
        if test(got):
            return t, got
    return None, None


WAIT = int(S.COMMS_WAIT)


# --- the phases, with nobody at the desk ---------------------------------------
def test_a_sol_runs_its_four_phases_by_itself():
    w = World()
    model = Model([READY, ("", [call("count", kind="rock")]), END,
                   ("", [call("remember", name="plan", text="east first on sol 2")]),
                   REPORT])
    S.MISSION_SOLS = 1
    try:
        convs, rows, nights = fly(w, model)
    finally:
        S.MISSION_SOLS = 0
    c = convs[0]
    opened = said_by(c, "auto")
    assert len(opened) == 3, "three turns from the clock: dawn, the day, dusk"
    assert (opened[0].startswith("Dawn of sol 1")
                and "not begun" in opened[0]), "dawn says the day has not begun"
    assert "The clock runs from now" in opened[1], "the day says its clock starts now"
    assert opened[2].index("memory") < opened[2].index("report"), "dusk asks for her memory before her report"
    assert [r["phase"] for r in rows if r["kind"] == "phase"] == ["day", "dusk", "night"], "the phases went in order"
    assert ([r["why"] for r in rows if r["kind"] == "sol_closed"]
                == ["she called end"]), "she closed the day"
    assert w.notes.memory == {"plan": "east first on sol 2"}, "her memory was written at dusk"
    assert w.reports == [{"sol": 1, "text": REPORT[0]}], "and her last words are kept as her report"
    assert nights == 1, "then the night fell, once"


def test_the_mission_stands_whatever_the_board_says():
    """14 Oct: once any order was posted the day's opening said only "carry out your
    orders", the orders were conditions, and she went home with half her battery."""
    w = World()
    assert "explore" in autopilot.begin(w), "with no orders, the day says to explore"
    w.notes.order("return at about 100 battery")
    text = autopilot.begin(w)
    assert "orders" in text and "explore" in text and "whatever battery" in text, "with orders, it says to carry them out and explore with what they leave"
    assert "goto and execute are refused until the day begins" in autopilot.dawn(w), "dawn says what works now and what waits for the day"
    assert "is never used" in prompts.SYSTEM, "and the prompt says unspent charge is never used"


def test_dawn_drives_nothing_and_costs_no_time():
    w = World()
    model = Model([("", [call("goto", x=15, y=10)]), READY, END, REPORT])
    S.MISSION_SOLS = 1
    try:
        convs, rows, _ = fly(w, model)
    finally:
        S.MISSION_SOLS = 0
    c = convs[0]
    assert not [x for x in c.calls if x.name == "goto"] and w.pos == (15, 15), "a drive at dawn was refused, and nothing moved"
    assert f"{S.DAY_SECONDS} seconds" in said_by(c, "auto")[1], "the day began with its whole clock"


def test_the_day_runs_on_the_wall_clock_and_ends_when_it_runs_out():
    keep = S.DAY_SECONDS
    S.DAY_SECONDS = 20
    try:
        w = World()
        model = Model([READY] + [("Thinking it over.", [])] * 60 + [REPORT])
        convs, rows, _ = fly(w, model, frames=60)
    finally:
        S.DAY_SECONDS = keep
    closed = [r for r in rows if r["kind"] == "sol_closed"]
    assert closed and closed[0]["why"] == "the clock ran out", "a planner that never ends is ended by the clock"
    assert w.time_left == 0 or w.day > 1, "which reads nought"
    assert sum("both allowances back" in t for t in said_by(convs[0], "auto")) > 5, "every reply with no call in it was a new turn, with what is left"


def test_a_flat_battery_ends_the_day():
    keep = S.BATTERY
    S.BATTERY = 8
    try:
        w = World()
        model = Model([READY, ("", [call("goto", x=15, y=0)]), ("Out of charge.", []),
                       REPORT])
        S.MISSION_SOLS = 1
        convs, rows, _ = fly(w, model)
    finally:
        S.BATTERY, S.MISSION_SOLS = keep, 0
    drive = [x for x in convs[0].calls if x.name == "goto"][0]
    assert drive.result.startswith("BATTERY_FLAT"), "the drive stopped flat"
    assert [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["the battery is flat"], "and the day closed on it"
    assert "the rover is lost" in said_by(convs[0], "auto")[-1], "flat out on the plain, dusk says the rover is lost"


def test_a_cap_is_a_new_turn_and_her_end_is_the_day():
    keep = S.MOVE_HOPS
    S.MOVE_HOPS = 2
    try:
        w = World()
        model = Model([READY, ("", [call("goto", x=18, y=15)]),
                       ("", [call("goto", x=15, y=18)]),        # the cap ends the turn
                       ("", [call("goto", x=15, y=15)]), END, REPORT])
        S.MISSION_SOLS = 1
        convs, rows, _ = fly(w, model)
    finally:
        S.MOVE_HOPS, S.MISSION_SOLS = keep, 0
    c = convs[0]
    opened = said_by(c, "auto")
    assert [x.name for x in c.calls].count("goto") == 3, "three drives ran"
    assert any("both allowances back" in t for t in opened), "the cap opened a new turn with both allowances back"
    assert (not any("call end and the clock" in str(m.get("content", ""))
                        for m in c.messages)), "and she was never asked to call end for it"
    assert [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["she called end"], "her own end closed the day"


def test_three_sols_with_no_key_pressed():
    w = World()
    replies = []
    for n in (1, 2, 3):
        replies += [READY, ("", [call("count", kind="rock")]), END,
                    ("", [call("remember", name="note", text=f"sol {n}")]), REPORT]
    S.MISSION_SOLS = 3
    try:
        convs, rows, nights = fly(w, Model(replies))
    finally:
        S.MISSION_SOLS = 0
    assert nights == 3 and len(convs) == 3, "three sols, three nights"
    assert all(said_by(c, "auto")[0].startswith("Dawn of sol") for c in convs), "every sol opened at dawn"
    assert w.notes.memory == {"note": "sol 3"}, "and her memory carried"


# --- the desk ----------------------------------------------------------------------
def test_each_phase_waits_for_the_desk():
    with Desk():
        w = World()
        model = Model([READY, END, ("", [call("remember", name="n", text="x")]), REPORT])
        c, pilot, rows = sol(w, model)
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "dawn")
        assert opened is not None, "after her dawn turn, dawn waits"
        early, _ = until(c, pilot, w, lambda got: pilot.wait != "dawn", start=opened + 1,
                         frames=WAIT - 2)
        assert early is None, "for COMMS_WAIT, with nothing typed"
        pilot.tick(c, w, now=float(opened + WAIT - 1), typing=True)
        late, _ = until(c, pilot, w, lambda got: pilot.wait != "dawn",
                        start=opened + WAIT, frames=WAIT + 5)
        assert late is not None and late >= opened + 2 * WAIT - 2, "typing holds it: the wait counts from the last keystroke"
        assert w.phase == "day", "then the day began"
        t, _ = until(c, pilot, w, lambda got: pilot.wait == "dusk", start=late + 1)
        assert t is not None and w.reports, "after her report, dusk waits"
        pilot.next()
        t2, _ = until(c, pilot, w, lambda got: pilot.wait == "night", start=t + 1, frames=3)
        assert t2 is not None, "/next moves it to night at once"
        pilot.next()
        t3, got = until(c, pilot, w, lambda got: got == "night", start=t2 + 1, frames=3)
        assert got == "night", "and /next at night ends the sol"


def test_with_comms_off_every_phase_moves_on_by_itself():
    with Desk(on=False):
        w = World()
        c, pilot, _ = sol(w, Model([READY, END, REPORT]))
        t, got = until(c, pilot, w, lambda got: got == "night", frames=20)
        assert got == "night" and t < 10, "dawn to night with no wait at all"
        assert "Nobody is at mission control's desk" in said_by(c, "auto")[0], "and she was told nobody is at the desk"


def test_the_desk_talks_at_dawn_and_night_and_not_at_dusk():
    with Desk():
        w = World()
        model = Model([READY, ("Understood: east first.", [call("todo", text="east")]),
                       END, ("", [call("remember", name="n", text="x")]), REPORT,
                       ("Sleep well.", [])])
        c, pilot, _ = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        assert (pilot.say(c, w, "go east first") is None
                   and c.turn_by == "you"), "at dawn the desk's words go"
        until(c, pilot, w, lambda got: not c.busy, frames=3)
        assert w.notes.todos == [["east", False]], "and she can plan on them, with no drive"
        pilot.next()
        until(c, pilot, w, lambda got: pilot.wait == "dusk")
        assert "dusk is hers" in (pilot.say(c, w, "hi") or ""), "at dusk they do not"
        pilot.next()
        until(c, pilot, w, lambda got: pilot.wait == "night", frames=3)
        assert pilot.say(c, w, "well done") is None, "at night they go again"
    with Desk(on=False):
        assert ("comms are off" in
                    (autopilot.Autopilot(attended=True).why_not() or "")), "with comms off nothing goes"


def test_next_carries_words_to_whatever_comes_next():
    with Desk():
        w = World()
        model = Model([READY, END, REPORT])
        c, pilot, _ = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next("survey the north today")
        until(c, pilot, w, lambda got: w.phase == "day", frames=5)
        until(c, pilot, w, lambda got: len(said_by(c, "auto")) >= 2, frames=5)
        assert "Mission control: survey the north today" in said_by(c, "auto")[1], "dawn's words arrive with the day's opening"
        until(c, pilot, w, lambda got: pilot.wait == "night")
        pilot.next("rest well")
        _, got = until(c, pilot, w, lambda got: got == "night", frames=3)
        assert (got == "night"
                    and pilot.words == "rest well"), "night's words are carried to the next sol"
        w.next_day()
        assert ("Mission control: rest well" in
                    autopilot.dawn(w, pilot.words)), "and arrive with its dawn"
        assert "Q ends it" in _day_next(), "by day /next is refused: the day ends by itself"


def _day_next():
    p = autopilot.Autopilot(attended=True)
    p.phase = "day"
    return p.next() or ""


def test_an_urgent_message_ends_her_turn_not_her_day():
    with Desk():
        w = World()
        model = Model([READY, ("", [call("goto", x=15, y=12)]),
                       ("", [call("goto", x=18, y=12)])])   # what she would do next
        rover = [True]
        c, pilot, rows = sol(w, model, rover)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        assert "not day" in (pilot.send_urgent(c, w, "come home") or ""), "refused at dawn: just talk to her"
        pilot.next()
        until(c, pilot, w, lambda got: w.phase == "day", frames=3)
        pilot.tick(c, w, now=500.0)              # the day's first turn goes out
        rover[0] = False                         # ...and the rover drives its leg
        c.pump()
        assert len(c.calls) == 1 and c.waiting, "one drive ran, the next request is held for the rover"
        assert pilot.send_urgent(c, w, "return to the pad now") is None, "an urgent message gets through, from anywhere"
        assert ("one urgent message at a time" in
                    (pilot.send_urgent(c, w, "and hurry") or "")), "one at a time"
        rover[0] = True
        c.pump()
        assert len(model.sent) == 2 and len(c.calls) == 1, "she stopped after the call in hand: nothing more was asked"
        model.replies = [("Heading home.", [call("goto", x=15, y=15)]), END,
                         ("", [call("remember", name="n", text="x")]), REPORT]
        until(c, pilot, w, lambda got: w.day_over, start=501, frames=10)
        assert (any(str(m.get("content", "")).startswith("URGENT from mission control")
                        for m in c.messages) and any(r["kind"] == "urgent" for r in rows)), "it arrived marked urgent, and is on the tape"
        assert [x.name for x in c.calls] == ["goto", "goto", "end"], "her turn ended, not her day: she drove home after it"
        assert [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["she called end"], "and her own end closed the day"
    with Desk(on=False):
        w = World()
        c, pilot, _ = sol(w, Model([END]))
        pilot.phase = "day"
        assert ("comms are off" in
                    (pilot.send_urgent(c, w, "x") or "")), "comms off: refused"


def test_a_radio_call_opens_a_line_the_clock_runs_through():
    with Desk():
        w = World()
        w.pos = (15, 5)                           # radio works away from the pad
        model = Model([READY, ("", [call("radio", text="is the C worth a sol?")])])
        c, pilot, rows = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "radio", start=1)
        assert (opened is not None
                   and any(r["kind"] == "radio" for r in rows) and c.on_line), "her radio opens the line, from anywhere"
        assert w.battery == S.BATTERY - S.RADIO_STEPS, "and cost its battery"
        model.replies = [("Understood, I will skip it.", [])]
        assert pilot.say(c, w, "no, leave the C") is None, "the desk answers on it"
        until(c, pilot, w, lambda got: not c.busy, start=opened + 1, frames=3)
        assert w.battery == S.BATTERY - 2 * S.RADIO_STEPS, "her reply went over the radio, at the same cost"
        before = w.time_left
        t, _ = until(c, pilot, w, lambda got: pilot.wait is None, start=opened + 2)
        assert t is not None and t - opened >= WAIT, "nobody says more: after COMMS_WAIT it closes"
        assert abs((before - w.time_left) - (t - opened - 2)) <= 2.0, "and the day's clock ran the whole time"
        model.replies = [END, ("", [call("remember", name="n", text="x")]), REPORT]
        until(c, pilot, w, lambda got: w.day_over, start=t + 1, frames=5)
        assert any("line to mission control is closed" in x for x in said_by(c, "auto")), "she carries on, told the line is closed"
    with Desk():
        w = World()
        model = Model([READY, ("", [call("radio", text="anyone?")]), END, REPORT])
        c, pilot, rows = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "radio", start=1)
        pilot.next("back to work")
        until(c, pilot, w, lambda got: w.day_over, start=opened + 1, frames=5)
        assert (any("line to mission control is closed" in x and
                        "Mission control: back to work" in x for x in said_by(c, "auto"))), "/next with words closes the line and hands them over"
    with Desk():
        w = World()
        model = Model([READY, ("", [call("radio", text="done here")]),
                       ("Going home now.", [call("end")]),
                       ("", [call("remember", name="n", text="x")]), REPORT])
        c, pilot, rows = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        until(c, pilot, w, lambda got: pilot.wait == "radio", start=1)
        pilot.say(c, w, "fine, call it a day")
        t, _ = until(c, pilot, w, lambda got: w.phase == "dusk", frames=5)
        assert (t is not None
                    and [r["why"] for r in rows if r["kind"] == "sol_closed"]
                    == ["she called end"]), "her end on the line closes the line and the day"
    with Desk(sols=1):
        w = World()
        convs, _, _ = fly(w, Model([READY, ("", [call("radio", text="anyone?")]), END,
                                    REPORT]))
        assert any("Nobody answered the radio" in x for x in said_by(convs[0], "auto")), "with nobody at the window, nobody answers"


def test_a_late_urgent_message_is_said_to_be_late():
    with Desk():
        w = World()
        model = Model([READY, END])
        rover = [True]
        c, pilot, rows = sol(w, model, rover)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        until(c, pilot, w, lambda got: w.phase == "day", frames=3)
        rover[0] = False
        pilot.tick(c, w, now=500.0)
        pilot.send_urgent(c, w, "one more thing")
        rover[0] = True
        until(c, pilot, w, lambda got: w.phase == "dusk", start=501, frames=5)
        assert (any("came too late" in t for t in said_by(c, "note"))
                   and not any(str(m.get("content", "")).startswith("URGENT")
                               for m in c.messages)), "an urgent message after her end does not reopen the day"


def test_the_prompt_says_how_a_sol_goes_and_who_can_be_reached():
    with Desk():
        on = prompts.SYSTEM
    with Desk(on=False):
        off = prompts.SYSTEM
    assert all("dawn, day, dusk and night" in p for p in (on, off)), "both say a sol is dawn, day, dusk and night"
    assert (all("`end` closes the day" in p
                                                   for p in (on, off))), "both say end closes the day"
    assert "radio" in on and f"{S.RADIO_STEPS} steps of battery" in on, "with someone there, the radio and its cost"
    assert "radio(" not in off and "Nobody is at" in off, "with nobody, no radio at all"
    assert "sos" not in on and "sos" not in skills.NAMES, "and sos is gone"


def test_flat_away_from_the_pad_ends_the_mission():
    w = World()
    w.pos = (3, 3)
    w.battery = 2
    text = autopilot.dusk(w)
    assert ("lost" in text
                 and "mission ends" in text), "dusk says the rover is lost and the mission ends"


def test_a_dropped_connection_is_asked_again_not_counted():
    w = World()
    model = Model([READY, "down", "down", ("", [call("count", kind="rock")]), END, REPORT])
    keep, keep_fb = S.AUTO_RETRY_SECONDS, S.MODEL_FALLBACK
    S.AUTO_RETRY_SECONDS, S.MODEL_FALLBACK = 10, S.MODEL
    S.MISSION_SOLS = 1
    try:
        convs, rows, nights = fly(w, model, frames=60)
    finally:
        S.AUTO_RETRY_SECONDS, S.MODEL_FALLBACK, S.MISSION_SOLS = keep, keep_fb, 0
    c = convs[0]
    assert c.failures == 2, "both failures were noticed"
    assert sum("did not answer" in t for t in said_by(c, "auto")) == 2, "and said so"
    assert (sum(t.startswith("Sol 1 has begun") for t in said_by(c, "auto")) == 1
                and not any("both allowances back" in t for t in said_by(c, "auto"))), "the retry carried on the same turn rather than opening one"
    assert nights == 1, "the sol still finished"


def test_the_cloud_drops_for_a_sol_and_comes_back():
    """`--outage 2`, end to end but for the socket."""
    answered, probed = [], []

    class Cloud(Model):
        def talk(self, conv):
            def stream(messages, allowed=None):
                if conv._sent_host == S.OUTAGE_HOST:
                    conv.q.put(("error", "URLError: [Errno 111] Connection refused"))
                    return
                answered.append((conv.day, conv._sent_model))
                text, calls = self.replies.pop(0) if self.replies else END
                if text:
                    conv.q.put(("say", text))
                conv.q.put(("done", ({"prompt_eval_count": 1, "eval_count": 1}, calls)))
            conv._stream = stream
            return conv

    def probe(model, host):
        probed.append(host)
        return host != S.OUTAGE_HOST

    keep = S.OUTAGE_SOLS, S.PROBE_SECONDS, S.MISSION_SOLS
    S.OUTAGE_SOLS, S.PROBE_SECONDS, S.MISSION_SOLS = (2,), 0, 3
    try:
        replies = []
        for n in (1, 2, 3):
            replies += [READY, ("", [call("count", kind="rock")]), END, REPORT]
        convs, rows, nights = fly(World(), Cloud(replies), frames=80,
                                  link=chat.Link(probe))
    finally:
        S.OUTAGE_SOLS, S.PROBE_SECONDS, S.MISSION_SOLS = keep
    by_sol = {d: {m for dd, m in answered if dd == d} for d in (1, 2, 3)}
    assert by_sol[1] == {S.MODEL}, "sol 1 on the cloud"
    assert by_sol[2] == {S.MODEL_FALLBACK}, "sol 2 on the fallback"
    assert by_sol[3] == {S.MODEL}, "sol 3 back on the cloud from its dawn"
    assert (all(c.failures == 0 for c in convs)
                and nights == 3), "the drop was not a failure"


# --- replay ------------------------------------------------------------------------
def recorder(log):
    """`World.recorder` writing a game log a `replay.Script` can read."""
    def write(kind, **f):
        log.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **f},
                             default=str) + "\n")
        log.flush()
        if kind in replay.OPS:
            time.sleep(0.002)      # an op and the call after it never share a stamp
    return write


def live_then_replay(replies, sols=1, objectives="manual"):
    """A live run with nobody at the window, kept to a tape and a game log, then replayed
    from them. Returns (live world, live calls, replay world, replays, replayed calls)."""
    keep = S.MISSION_SOLS, S.OBJECTIVES
    S.MISSION_SOLS, S.OBJECTIVES = sols, objectives

    def run(w, make, live):
        convs = [make(w)]
        convs[0].open_day(w)
        pilot = autopilot.Autopilot(live=live)
        for t in range(400):
            conv = convs[-1]
            conv.pump()
            if getattr(conv, "diverged", None):
                break
            if pilot.tick(conv, w, now=float(t)) == "night":
                if w.day >= sols:
                    break
                w.next_day()
                convs.append(make(w))
                convs[-1].open_day(w)
                pilot = autopilot.Autopilot(live=live)
        return convs

    try:
        with tempfile.TemporaryDirectory() as d:
            tape = chat.Tape(Path(d) / "chat.jsonl")
            with (Path(d) / "game.jsonl").open("w") as log:
                w = World(recorder=recorder(log))
                model = Model(replies)
                live = run(w, lambda w_: model.talk(chat.Conversation(w_, tape)), True)
            tape.close()
            script = replay.Script(Path(d))
            w2 = World()
            again = run(w2, lambda w_: replay.Replay(w_, script), False)
    finally:
        S.MISSION_SOLS, S.OBJECTIVES = keep
    return (w, [x for c in live for x in c.calls], w2, again,
            [x for c in again for x in c.calls])


def test_a_two_sol_run_replays_exactly():
    keep = S.MOVE_HOPS, S.COMMS
    S.MOVE_HOPS, S.COMMS = 2, True
    try:
        replies = [("", [call("todo", text="north first"), call("todo", text="then east"),
                         call("remember", name="plan", text="north, then east")]), READY,
                   ("", [call("goto", x=15, y=10)]), ("", [call("goto", x=20, y=10)]),
                   ("", [call("radio", text="anything I should know?")]),
                   ("", [call("distance", x=2, y=2)]),
                   ("", [call("goto", x=15, y=14)]), END,
                   ("", [call("remember", name="plan", text="east on sol 2")]), REPORT,
                   ("", [call("count", kind="rock")]), READY,
                   ("", [call("goto", x=24, y=8)]), ("", [call("goto", x=15, y=14)]),
                   END, ("", [call("forget", name="plan")]), REPORT]
        w, live, w2, runs, again = live_then_replay(replies, sols=2, objectives="auto")
    finally:
        S.MOVE_HOPS, S.COMMS = keep
    diverged = [c.diverged for c in runs if c.diverged]
    assert [x.name for x in live].count("goto") == 5 and "radio" in [x.name for x in live], "live: dawn, day and dusk calls all ran"
    assert (len(w.objectives) == 3
                or any(f["kind"] == "objective" for f in w.finished)), "sol 2 got its auto objectives"
    assert not diverged, "the replay never diverged"
    assert ([(x.name, x.result) for x in again if x.name != "end"]
                == [(x.name, x.result) for x in live if x.name != "end"]), "and ran the same calls to the same results"
    assert (w2.pos, w2.battery) == (w.pos, w.battery), "ending where the live rover did, on the same battery"
    assert sorted(o.cell for o in w2.objectives) == sorted(o.cell for o in w.objectives), "with the same objectives on the map"


def test_a_list_made_at_night_wakes_with_her_and_replays():
    """Dusk's end clears the day's list, and what she writes at night is the next
    day's. A replay re-issues the whole sol before it walks the phases, so it clears
    the list from the tape's row for the night beginning instead."""
    model = Model([READY, ("", [call("todo", text="explore south")]), END,
                   ("", [call("remember", name="n", text="south done")]), REPORT,
                   ("North first, then.", [call("todo", text="explore north")]),
                   ("Good night.", [])])
    with Desk(sols=2), tempfile.TemporaryDirectory() as d:
        tape = chat.Tape(Path(d) / "chat.jsonl")
        with (Path(d) / "game.jsonl").open("w") as log:
            w = World(recorder=recorder(log))
            c = model.talk(chat.Conversation(w, tape))
            c.open_day(w)
            pilot = autopilot.Autopilot(attended=True)
            t, _ = until(c, pilot, w, lambda got: pilot.wait == "dawn")
            pilot.next()
            t, _ = until(c, pilot, w, lambda got: pilot.wait == "dusk", start=t + 1)
            assert w.notes.todos == [["explore south", False]], "at dusk the day's list is still there"
            pilot.next()
            t, _ = until(c, pilot, w, lambda got: pilot.wait == "night", start=t + 1)
            assert w.notes.todos == [], "dusk over, it is gone"
            pilot.say(c, w, "take the north tomorrow")
            t, _ = until(c, pilot, w, lambda got: w.notes.todos and not c.busy,
                         start=t + 1)
            pilot.next()
            t, got = until(c, pilot, w, lambda got: got == "night", start=t + 1)
            w.next_day()
        tape.close()
        assert w.notes.todos == [["explore north", False]], "what she wrote at night is her list at dawn"
        assert "It holds what you put on it last night." in autopilot.dawn(w), "and the dawn says so"

        script = replay.Script(Path(d))
        w2 = World()
        r = replay.Replay(w2, script)
        r.open_day(w2)
        until(r, autopilot.Autopilot(live=False), w2,
              lambda got: got == "night" or r.diverged, frames=80)
        script.operator(w2, w2.day)
        w2.next_day()
    assert not r.diverged, "the replay never diverged"
    assert w2.notes.todos == w.notes.todos, "and woke with the same list"


def test_a_replay_of_an_urgent_message_matches():
    """An urgent message cut a turn with no `end` in it. With two drives a turn, the
    replay only agrees if it ends that turn where the live one ended."""
    keep = S.MOVE_HOPS
    S.MOVE_HOPS = 2
    try:
        with Desk(sols=1), tempfile.TemporaryDirectory() as d:
            tape = chat.Tape(Path(d) / "chat.jsonl")
            w = World()
            model = Model([READY, ("", [call("goto", x=15, y=12)]),
                           ("", [call("goto", x=18, y=12)]),
                           ("", [call("goto", x=15, y=10)]), END, REPORT])
            rover = [True]
            c = model.talk(chat.Conversation(w, tape))
            c.ready = lambda: rover[0]
            c.open_day(w)
            pilot = autopilot.Autopilot()
            until(c, pilot, w, lambda got: w.phase == "day", frames=5)
            rover[0] = False
            pilot.tick(c, w, now=10.0)
            c.pump()
            pilot.send_urgent(c, w, "two more drives, then home")
            rover[0] = True
            until(c, pilot, w, lambda got: got == "night", start=11, frames=40)
            tape.close()
            live = [(x.name, x.result) for x in c.calls if x.name != "end"]
            w2 = World()
            r = replay.Replay(w2, replay.Script(Path(d)))
            r.open_day(w2)
            until(r, autopilot.Autopilot(live=False), w2,
                  lambda got: got == "night" or r.diverged, frames=60)
    finally:
        S.MOVE_HOPS = keep
    assert len(live) == 3, "live: three drives ran, across the cut"
    assert (not r.diverged and
                [(x.name, x.result) for x in r.calls if x.name != "end"] == live), "the replay ran them to the same results"
    assert w2.pos == w.pos, "and ended where the live rover did"


def test_a_replay_runs_on_the_tapes_clock():
    rows = [{"day": 1, "who": "call", "name": "distance", "args": {"x": 15, "y": 10},
             "ran": True, "clock": 42.5, "phase": "day"}]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "chat.jsonl").write_text(json.dumps(rows[0]))
        w = World()
        r = replay.Replay(w, replay.Script(Path(d)))
        r.send("go")
        r.pump()
        assert w.time_left == 42.5, "the call ran on the recorded clock"
        assert w.phase == "day", "in the recorded phase"
    w = World()
    w.set_clock(0.0)
    assert w.day_over, "a recorded clock at nought ends the day"
    w.set_clock(30.0)
    assert w.day_over, "and setting it back up never reopens one"
