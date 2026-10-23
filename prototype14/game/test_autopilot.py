"""The sol's four phases and the desk's place in each: dawn, a day on the wall clock,
dusk, night -- with the one urgent message, the radio line, and replay.

    .venv/bin/python game/test_autopilot.py

The model is a script and threads run inline, as in `test_chat.py`. `fly` stands in for
`main.py`'s loop -- pump, tick the clock, roll the night over when it says so -- with
one frame a second of pretend time, so the day's clock and the desk's waits are counted
rather than slept through. Nobody is at the desk unless a test says so.
"""

import json
import sys
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

S.STORM_ON = False
S.COMMS = False


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


class Inline:
    def __init__(self, target, args=(), daemon=False):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


chat.threading = types.SimpleNamespace(Thread=Inline)


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
    print("dawn, day, dusk, night")
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
    ok = check("three turns from the clock: dawn, the day, dusk", len(opened) == 3,
               str([o[:30] for o in opened]))
    ok &= check("dawn says the day has not begun", opened[0].startswith("Dawn of sol 1")
                and "not begun" in opened[0])
    ok &= check("the day says its clock starts now", "The clock runs from now" in opened[1])
    ok &= check("dusk asks for her memory before her report",
                opened[2].index("memory") < opened[2].index("report"))
    ok &= check("the phases went in order",
                [r["phase"] for r in rows if r["kind"] == "phase"] == ["day", "dusk", "night"])
    ok &= check("she closed the day", [r["why"] for r in rows if r["kind"] == "sol_closed"]
                == ["she called end"])
    ok &= check("her memory was written at dusk", w.notes.memory == {"plan": "east first on sol 2"})
    ok &= check("and her last words are kept as her report",
                w.reports == [{"sol": 1, "text": REPORT[0]}], str(w.reports))
    ok &= check("then the night fell, once", nights == 1)
    return ok


def test_the_mission_stands_whatever_the_board_says():
    """14 Oct: once any order was posted the day's opening said only "carry out your
    orders", the orders were conditions, and she went home with half her battery."""
    print("orders and the mission")
    w = World()
    ok = check("with no orders, the day says to explore", "explore" in autopilot.begin(w))
    w.notes.order("return at about 100 battery")
    text = autopilot.begin(w)
    ok &= check("with orders, it says to carry them out and explore with what they leave",
                "orders" in text and "explore" in text and "whatever battery" in text, text)
    ok &= check("dawn says what works now and what waits for the day",
                "goto and execute are refused until the day begins" in autopilot.dawn(w))
    ok &= check("and the prompt says unspent charge is never used",
                "is never used" in prompts.SYSTEM)
    return ok


def test_dawn_drives_nothing_and_costs_no_time():
    print("dawn")
    w = World()
    model = Model([("", [call("goto", x=15, y=10)]), READY, END, REPORT])
    S.MISSION_SOLS = 1
    try:
        convs, rows, _ = fly(w, model)
    finally:
        S.MISSION_SOLS = 0
    c = convs[0]
    ok = check("a drive at dawn was refused, and nothing moved",
               not [x for x in c.calls if x.name == "goto"] and w.pos == (15, 15))
    ok &= check("the day began with its whole clock",
                f"{S.DAY_SECONDS} seconds" in said_by(c, "auto")[1])
    return ok


def test_the_day_runs_on_the_wall_clock_and_ends_when_it_runs_out():
    print("the clock")
    keep = S.DAY_SECONDS
    S.DAY_SECONDS = 20
    try:
        w = World()
        model = Model([READY] + [("Thinking it over.", [])] * 60 + [REPORT])
        convs, rows, _ = fly(w, model, frames=60)
    finally:
        S.DAY_SECONDS = keep
    closed = [r for r in rows if r["kind"] == "sol_closed"]
    ok = check("a planner that never ends is ended by the clock",
               closed and closed[0]["why"] == "the clock ran out", str(closed))
    ok &= check("which reads nought", w.time_left == 0 or w.day > 1)
    ok &= check("every reply with no call in it was a new turn, with what is left",
                sum("both allowances back" in t for t in said_by(convs[0], "auto")) > 5)
    return ok


def test_a_flat_battery_ends_the_day():
    print("flat")
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
    ok = check("the drive stopped flat", drive.result.startswith("BATTERY_FLAT"),
               drive.result[:60])
    ok &= check("and the day closed on it",
                [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["the battery is flat"])
    ok &= check("flat out on the plain, dusk says the rover is lost",
                "the rover is lost" in said_by(convs[0], "auto")[-1])
    return ok


def test_a_cap_is_a_new_turn_and_her_end_is_the_day():
    print("caps and end")
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
    ok = check("three drives ran", [x.name for x in c.calls].count("goto") == 3)
    ok &= check("the cap opened a new turn with both allowances back",
                any("both allowances back" in t for t in opened))
    ok &= check("and she was never asked to call end for it",
                not any("call end and the clock" in str(m.get("content", ""))
                        for m in c.messages))
    ok &= check("her own end closed the day",
                [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["she called end"])
    return ok


def test_three_sols_with_no_key_pressed():
    print("--sols 3, nobody there")
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
    ok = check("three sols, three nights", nights == 3 and len(convs) == 3)
    ok &= check("every sol opened at dawn",
                all(said_by(c, "auto")[0].startswith("Dawn of sol") for c in convs))
    ok &= check("and her memory carried", w.notes.memory == {"note": "sol 3"})
    return ok


# --- the desk ----------------------------------------------------------------------
def test_each_phase_waits_for_the_desk():
    print("the desk's phases")
    with Desk():
        w = World()
        model = Model([READY, END, ("", [call("remember", name="n", text="x")]), REPORT])
        c, pilot, rows = sol(w, model)
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "dawn")
        ok = check("after her dawn turn, dawn waits", opened is not None)
        early, _ = until(c, pilot, w, lambda got: pilot.wait != "dawn", start=opened + 1,
                         frames=WAIT - 2)
        ok &= check("for COMMS_WAIT, with nothing typed", early is None)
        pilot.tick(c, w, now=float(opened + WAIT - 1), typing=True)
        late, _ = until(c, pilot, w, lambda got: pilot.wait != "dawn",
                        start=opened + WAIT, frames=WAIT + 5)
        ok &= check("typing holds it: the wait counts from the last keystroke",
                    late is not None and late >= opened + 2 * WAIT - 2, str(late))
        ok &= check("then the day began", w.phase == "day")
        t, _ = until(c, pilot, w, lambda got: pilot.wait == "dusk", start=late + 1)
        ok &= check("after her report, dusk waits", t is not None and w.reports)
        pilot.next()
        t2, _ = until(c, pilot, w, lambda got: pilot.wait == "night", start=t + 1, frames=3)
        ok &= check("/next moves it to night at once", t2 is not None)
        pilot.next()
        t3, got = until(c, pilot, w, lambda got: got == "night", start=t2 + 1, frames=3)
        ok &= check("and /next at night ends the sol", got == "night")
    return ok


def test_with_comms_off_every_phase_moves_on_by_itself():
    print("comms off: nobody there")
    with Desk(on=False):
        w = World()
        c, pilot, _ = sol(w, Model([READY, END, REPORT]))
        t, got = until(c, pilot, w, lambda got: got == "night", frames=20)
        ok = check("dawn to night with no wait at all", got == "night" and t < 10, str(t))
        ok &= check("and she was told nobody is at the desk",
                    "Nobody is at mission control's desk" in said_by(c, "auto")[0])
    return ok


def test_the_desk_talks_at_dawn_and_night_and_not_at_dusk():
    print("when words reach her")
    with Desk():
        w = World()
        model = Model([READY, ("Understood: east first.", [call("todo", text="east")]),
                       END, ("", [call("remember", name="n", text="x")]), REPORT,
                       ("Sleep well.", [])])
        c, pilot, _ = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        ok = check("at dawn the desk's words go", pilot.say(c, w, "go east first") is None
                   and c.turn_by == "you")
        until(c, pilot, w, lambda got: not c.busy, frames=3)
        ok &= check("and she can plan on them, with no drive", w.notes.todos == [["east", False]])
        pilot.next()
        until(c, pilot, w, lambda got: pilot.wait == "dusk")
        ok &= check("at dusk they do not", "dusk is hers" in (pilot.say(c, w, "hi") or ""))
        pilot.next()
        until(c, pilot, w, lambda got: pilot.wait == "night", frames=3)
        ok &= check("at night they go again", pilot.say(c, w, "well done") is None)
    with Desk(on=False):
        ok &= check("with comms off nothing goes", "comms are off" in
                    (autopilot.Autopilot(attended=True).why_not() or ""))
    return ok


def test_next_carries_words_to_whatever_comes_next():
    print("/next WORDS")
    with Desk():
        w = World()
        model = Model([READY, END, REPORT])
        c, pilot, _ = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next("survey the north today")
        until(c, pilot, w, lambda got: w.phase == "day", frames=5)
        until(c, pilot, w, lambda got: len(said_by(c, "auto")) >= 2, frames=5)
        ok = check("dawn's words arrive with the day's opening",
                   "Mission control: survey the north today" in said_by(c, "auto")[1])
        until(c, pilot, w, lambda got: pilot.wait == "night")
        pilot.next("rest well")
        _, got = until(c, pilot, w, lambda got: got == "night", frames=3)
        ok &= check("night's words are carried to the next sol", got == "night"
                    and pilot.words == "rest well")
        w.next_day()
        ok &= check("and arrive with its dawn", "Mission control: rest well" in
                    autopilot.dawn(w, pilot.words))
        ok &= check("by day /next is refused: the day ends by itself",
                    "Q ends it" in _day_next())
    return ok


def _day_next():
    p = autopilot.Autopilot(attended=True)
    p.phase = "day"
    return p.next() or ""


def test_an_urgent_message_ends_her_turn_not_her_day():
    print("urgent")
    with Desk():
        w = World()
        model = Model([READY, ("", [call("goto", x=15, y=12)]),
                       ("", [call("goto", x=18, y=12)])])   # what she would do next
        rover = [True]
        c, pilot, rows = sol(w, model, rover)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        ok = check("refused at dawn: just talk to her",
                   "not day" in (pilot.send_urgent(c, w, "come home") or ""))
        pilot.next()
        until(c, pilot, w, lambda got: w.phase == "day", frames=3)
        pilot.tick(c, w, now=500.0)              # the day's first turn goes out
        rover[0] = False                         # ...and the rover drives its leg
        c.pump()
        ok &= check("one drive ran, the next request is held for the rover",
                    len(c.calls) == 1 and c.waiting)
        ok &= check("an urgent message gets through, from anywhere",
                    pilot.send_urgent(c, w, "return to the pad now") is None)
        ok &= check("one at a time", "one urgent message at a time" in
                    (pilot.send_urgent(c, w, "and hurry") or ""))
        rover[0] = True
        c.pump()
        ok &= check("she stopped after the call in hand: nothing more was asked",
                    len(model.sent) == 2 and len(c.calls) == 1, f"{len(model.sent)} sent")
        model.replies = [("Heading home.", [call("goto", x=15, y=15)]), END,
                         ("", [call("remember", name="n", text="x")]), REPORT]
        until(c, pilot, w, lambda got: w.day_over, start=501, frames=10)
        ok &= check("it arrived marked urgent, and is on the tape",
                    any(str(m.get("content", "")).startswith("URGENT from mission control")
                        for m in c.messages) and any(r["kind"] == "urgent" for r in rows))
        ok &= check("her turn ended, not her day: she drove home after it",
                    [x.name for x in c.calls] == ["goto", "goto", "end"])
        ok &= check("and her own end closed the day",
                    [r["why"] for r in rows if r["kind"] == "sol_closed"] == ["she called end"])
    with Desk(on=False):
        w = World()
        c, pilot, _ = sol(w, Model([END]))
        pilot.phase = "day"
        ok &= check("comms off: refused", "comms are off" in
                    (pilot.send_urgent(c, w, "x") or ""))
    return ok


def test_a_radio_call_opens_a_line_the_clock_runs_through():
    print("the radio")
    with Desk():
        w = World()
        w.pos = (15, 5)                           # radio works away from the pad
        model = Model([READY, ("", [call("radio", text="is the C worth a sol?")])])
        c, pilot, rows = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "radio", start=1)
        ok = check("her radio opens the line, from anywhere", opened is not None
                   and any(r["kind"] == "radio" for r in rows) and c.on_line)
        ok &= check("and cost its battery", w.battery == S.BATTERY - S.RADIO_STEPS)
        model.replies = [("Understood, I will skip it.", [])]
        ok &= check("the desk answers on it", pilot.say(c, w, "no, leave the C") is None)
        until(c, pilot, w, lambda got: not c.busy, start=opened + 1, frames=3)
        ok &= check("her reply went over the radio, at the same cost",
                    w.battery == S.BATTERY - 2 * S.RADIO_STEPS, str(w.battery))
        before = w.time_left
        t, _ = until(c, pilot, w, lambda got: pilot.wait is None, start=opened + 2)
        ok &= check("nobody says more: after COMMS_WAIT it closes",
                    t is not None and t - opened >= WAIT, str(t))
        ok &= check("and the day's clock ran the whole time",
                    abs((before - w.time_left) - (t - opened - 2)) <= 2.0,
                    f"{before - w.time_left:.0f}s over {t - opened} frames")
        model.replies = [END, ("", [call("remember", name="n", text="x")]), REPORT]
        until(c, pilot, w, lambda got: w.day_over, start=t + 1, frames=5)
        ok &= check("she carries on, told the line is closed",
                    any("line to mission control is closed" in x for x in said_by(c, "auto")))
    with Desk():
        w = World()
        model = Model([READY, ("", [call("radio", text="anyone?")]), END, REPORT])
        c, pilot, rows = sol(w, model)
        until(c, pilot, w, lambda got: pilot.wait == "dawn")
        pilot.next()
        opened, _ = until(c, pilot, w, lambda got: pilot.wait == "radio", start=1)
        pilot.next("back to work")
        until(c, pilot, w, lambda got: w.day_over, start=opened + 1, frames=5)
        ok &= check("/next with words closes the line and hands them over",
                    any("line to mission control is closed" in x and
                        "Mission control: back to work" in x for x in said_by(c, "auto")))
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
        ok &= check("her end on the line closes the line and the day", t is not None
                    and [r["why"] for r in rows if r["kind"] == "sol_closed"]
                    == ["she called end"])
    with Desk(sols=1):
        w = World()
        convs, _, _ = fly(w, Model([READY, ("", [call("radio", text="anyone?")]), END,
                                    REPORT]))
        ok &= check("with nobody at the window, nobody answers",
                    any("Nobody answered the radio" in x for x in said_by(convs[0], "auto")))
    return ok


def test_a_late_urgent_message_is_said_to_be_late():
    print("too late")
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
        ok = check("an urgent message after her end does not reopen the day",
                   any("came too late" in t for t in said_by(c, "note"))
                   and not any(str(m.get("content", "")).startswith("URGENT")
                               for m in c.messages))
    return ok


def test_the_prompt_says_how_a_sol_goes_and_who_can_be_reached():
    print("the prompt")
    with Desk():
        on = prompts.SYSTEM
    with Desk(on=False):
        off = prompts.SYSTEM
    ok = check("both say a sol is dawn, day, dusk and night",
               all("dawn, day, dusk and night" in p for p in (on, off)))
    ok &= check("both say end closes the day", all("`end` closes the day" in p
                                                   for p in (on, off)))
    ok &= check("with someone there, the radio and its cost",
                "radio" in on and f"{S.RADIO_STEPS} steps of battery" in on)
    ok &= check("with nobody, no radio at all", "radio(" not in off and "Nobody is at" in off)
    ok &= check("and sos is gone", "sos" not in on and "sos" not in skills.NAMES)
    return ok


def test_flat_away_from_the_pad_ends_the_mission():
    print("lost")
    w = World()
    w.pos = (3, 3)
    w.battery = 2
    text = autopilot.dusk(w)
    return check("dusk says the rover is lost and the mission ends", "lost" in text
                 and "mission ends" in text, text)


def test_a_dropped_connection_is_asked_again_not_counted():
    print("ollama down")
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
    ok = check("both failures were noticed", c.failures == 2)
    ok &= check("and said so", sum("did not answer" in t for t in said_by(c, "auto")) == 2)
    ok &= check("the retry carried on the same turn rather than opening one",
                sum(t.startswith("Sol 1 has begun") for t in said_by(c, "auto")) == 1
                and not any("both allowances back" in t for t in said_by(c, "auto")))
    ok &= check("the sol still finished", nights == 1)
    return ok


def test_the_cloud_drops_for_a_sol_and_comes_back():
    """`--outage 2`, end to end but for the socket."""
    print("--outage 2")
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
    ok = check("sol 1 on the cloud", by_sol[1] == {S.MODEL}, str(by_sol))
    ok &= check("sol 2 on the fallback", by_sol[2] == {S.MODEL_FALLBACK}, str(by_sol))
    ok &= check("sol 3 back on the cloud from its dawn", by_sol[3] == {S.MODEL},
                str(by_sol))
    ok &= check("the drop was not a failure", all(c.failures == 0 for c in convs)
                and nights == 3)
    return ok


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
    print("replay: dawn, a capped day, the radio, dusk, auto objectives")
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
    ok = check("live: dawn, day and dusk calls all ran",
               [x.name for x in live].count("goto") == 5 and "radio" in [x.name for x in live],
               str([x.name for x in live]))
    ok &= check("sol 2 got its auto objectives", len(w.objectives) == 3
                or any(f["kind"] == "objective" for f in w.finished), str(w.objectives))
    ok &= check("the replay never diverged", not diverged, str(diverged))
    ok &= check("and ran the same calls to the same results",
                [(x.name, x.result) for x in again if x.name != "end"]
                == [(x.name, x.result) for x in live if x.name != "end"])
    ok &= check("ending where the live rover did, on the same battery",
                (w2.pos, w2.battery) == (w.pos, w.battery),
                f"{(w2.pos, w2.battery)} {(w.pos, w.battery)}")
    ok &= check("with the same objectives on the map",
                sorted(o.cell for o in w2.objectives) == sorted(o.cell for o in w.objectives))
    return ok


def test_a_list_made_at_night_wakes_with_her_and_replays():
    """Dusk's end clears the day's list, and what she writes at night is the next
    day's. A replay re-issues the whole sol before it walks the phases, so it clears
    the list from the tape's row for the night beginning instead."""
    print("a plan made at night, live and on replay")
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
            ok = check("at dusk the day's list is still there",
                       w.notes.todos == [["explore south", False]], str(w.notes.todos))
            pilot.next()
            t, _ = until(c, pilot, w, lambda got: pilot.wait == "night", start=t + 1)
            ok &= check("dusk over, it is gone", w.notes.todos == [], str(w.notes.todos))
            pilot.say(c, w, "take the north tomorrow")
            t, _ = until(c, pilot, w, lambda got: w.notes.todos and not c.busy,
                         start=t + 1)
            pilot.next()
            t, got = until(c, pilot, w, lambda got: got == "night", start=t + 1)
            w.next_day()
        tape.close()
        ok &= check("what she wrote at night is her list at dawn",
                    w.notes.todos == [["explore north", False]], str(w.notes.todos))
        ok &= check("and the dawn says so",
                    "It holds what you put on it last night." in autopilot.dawn(w))

        script = replay.Script(Path(d))
        w2 = World()
        r = replay.Replay(w2, script)
        r.open_day(w2)
        until(r, autopilot.Autopilot(live=False), w2,
              lambda got: got == "night" or r.diverged, frames=80)
        script.operator(w2, w2.day)
        w2.next_day()
    ok &= check("the replay never diverged", not r.diverged, str(r.diverged))
    ok &= check("and woke with the same list", w2.notes.todos == w.notes.todos,
                str(w2.notes.todos))
    return ok


def test_a_replay_of_an_urgent_message_matches():
    """An urgent message cut a turn with no `end` in it. With two drives a turn, the
    replay only agrees if it ends that turn where the live one ended."""
    print("replay: an urgent message")
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
    ok = check("live: three drives ran, across the cut", len(live) == 3, str(live))
    ok &= check("the replay ran them to the same results", not r.diverged and
                [(x.name, x.result) for x in r.calls if x.name != "end"] == live,
                str(r.diverged))
    ok &= check("and ended where the live rover did", w2.pos == w.pos)
    return ok


def test_a_replay_runs_on_the_tapes_clock():
    print("replay sets the clock")
    rows = [{"day": 1, "who": "call", "name": "distance", "args": {"x": 15, "y": 10},
             "ran": True, "clock": 42.5, "phase": "day"}]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "chat.jsonl").write_text(json.dumps(rows[0]))
        w = World()
        r = replay.Replay(w, replay.Script(Path(d)))
        r.send("go")
        r.pump()
        ok = check("the call ran on the recorded clock", w.time_left == 42.5,
                   str(w.time_left))
        ok &= check("in the recorded phase", w.phase == "day")
    w = World()
    w.set_clock(0.0)
    ok &= check("a recorded clock at nought ends the day", w.day_over)
    w.set_clock(30.0)
    ok &= check("and setting it back up never reopens one", w.day_over)
    return ok


if __name__ == "__main__":
    results = [test_a_sol_runs_its_four_phases_by_itself(),
               test_the_mission_stands_whatever_the_board_says(),
               test_dawn_drives_nothing_and_costs_no_time(),
               test_the_day_runs_on_the_wall_clock_and_ends_when_it_runs_out(),
               test_a_flat_battery_ends_the_day(),
               test_a_cap_is_a_new_turn_and_her_end_is_the_day(),
               test_three_sols_with_no_key_pressed(),
               test_each_phase_waits_for_the_desk(),
               test_with_comms_off_every_phase_moves_on_by_itself(),
               test_the_desk_talks_at_dawn_and_night_and_not_at_dusk(),
               test_next_carries_words_to_whatever_comes_next(),
               test_an_urgent_message_ends_her_turn_not_her_day(),
               test_a_radio_call_opens_a_line_the_clock_runs_through(),
               test_a_late_urgent_message_is_said_to_be_late(),
               test_the_prompt_says_how_a_sol_goes_and_who_can_be_reached(),
               test_flat_away_from_the_pad_ends_the_mission(),
               test_a_dropped_connection_is_asked_again_not_counted(),
               test_the_cloud_drops_for_a_sol_and_comes_back(),
               test_a_two_sol_run_replays_exactly(),
               test_a_replay_of_an_urgent_message_matches(),
               test_a_list_made_at_night_wakes_with_her_and_replays(),
               test_a_replay_runs_on_the_tapes_clock()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
