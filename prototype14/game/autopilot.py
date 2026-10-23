"""The sol, in four phases, and where the desk fits in each.

    .venv/bin/python game/main.py --sols 3

    dawn   the sol has not begun: no clock, and nothing drives. She reads her memory,
           the board and the work, and sets up today's list. The desk may talk freely.
    day    DAY_SECONDS of wall clock, which nothing pauses. She works alone. The desk can
           break in with one urgent message -- words, or a change to the board -- and she
           can call the desk with `radio`, from anywhere, at a cost in battery.
    dusk   the day is over. She brings her memory up to date, and her last words are her
           report. The desk reads it.
    night  her list is cleared as it begins, so what she puts on it now is tomorrow's.
           The desk may talk freely. Then the next sol's dawn.

**Every phase but the day ends the same way.** With someone at the desk (`COMMS`, and a
window on the app) it waits COMMS_WAIT after the last thing typed or said, or for /next.
With nobody there it moves on as soon as she is quiet. `/next <words>` moves on and hands
her the words with whatever she is sent next. The day ends when she calls `end`, the clock
runs out or the battery runs flat -- or the desk presses Q.

**`end` is the day, and only hers.** A turn also ends when a cap is reached, an urgent
message cuts it, she radios, or she replies with no call in it; by day the clock then opens
the next turn. A radio line is a window inside the day: the clock keeps running, and every
reply she speaks on it costs battery (`Conversation.on_line`).

Its lines are `auto` on the tape, never `you`, so a sol nobody coached can never be
mistaken for one somebody did. **A replay holds no windows and runs no clock**: the tape
sets the clock and the phase at every call, and while it holds calls for today the clock
keeps opening turns.

No pygame in here, so the tests can drive the whole thing.
"""

import time

import settings as S
import skills

PHASES = ("dawn", "day", "dusk", "night")


def _desk_line(text):
    return f"\n\nMission control: {text}" if text else ""


def dawn(world, words="", placed=()):
    """The turn that opens the sol. Nothing drives yet and no time passes."""
    stuck = (f" The rover spent the night stranded, so the battery was not recharged: "
             f"{world.battery} of {S.BATTERY}." if world.stranded else "")
    new = (f" Mission control has posted {len(placed)} new objectives; they are in your "
           f"view." if placed else "")
    desk = (" Mission control is at the desk and may talk with you before the day begins."
            if S.COMMS else " Nobody is at mission control's desk.")
    kept = " It holds what you put on it last night." if world.notes.todos else ""
    return (f"Dawn of sol {world.day}. The day has not begun: no time passes and the rover "
            f"does not move until it does.{stuck}{new} Read your memory, the board and the "
            f"work in your view, and set up today's list.{kept} Your list, your memory, "
            f"distance and count all work now; goto and execute are refused until the day "
            f"begins.{desk}" + _desk_line(words))


EXPLORE = ("explore: drive into ground you have not seen, examine the interests you find, "
           "do the objectives worth the steps, and work out which rock formation is the "
           "largest.")


def begin(world, words=""):
    """The turn that opens the day, and starts its clock. The mission stands whatever
    the board says: the 14 Oct run's orders were conditions, not a job, and replacing the
    mission with them left her nothing to do once the objectives were done."""
    job = (f"Carry out your orders from mission control, and with whatever battery and time "
           f"they leave, {EXPLORE}" if world.notes.orders else
           f"You have no orders, so {EXPLORE}")
    return (f"Sol {world.day} has begun. The clock runs from now: {world.time_left:.0f} "
            f"seconds, and nothing stops it. {job} Be back beside the pad before you call "
            f"end; end closes the day." + _desk_line(words))


def carry_on(world, after_line=False, words=""):
    """A day's turn ended without the day ending: a cap, a reply with no call in it, an
    urgent message handled, or a radio line closed -- `after_line`, or "unanswered"."""
    back = {True: "The line to mission control is closed. ",
            "unanswered": "Nobody answered the radio. "}.get(after_line, "")
    return (f"{back}The day goes on with a new turn and both allowances back: "
            f"{world.time_left:.0f} seconds and {world.battery} steps of battery are "
            f"left. Carry on until the battery is down to the trip home or the clock is "
            f"nearly out; end closes the day." + _desk_line(words))


def desk(on):
    """What she is told, with her next turn, when someone sits down at the desk or
    leaves it."""
    if on:
        return ("Mission control is at the desk now: they talk with you at dawn and at "
                "night, and by day you can radio them.")
    return ("Mission control has left the desk. Nobody will talk to you, answer you or "
            "call: work from your orders, your memory and your own judgement.")


KEEP = ("First bring your memory up to date: remember what tomorrow needs -- what you "
        "found, what you left and why, what to do first, any constraint still standing -- "
        "carry over from today's list whatever still matters, since the list is cleared "
        "when dusk ends, and forget what is no longer true. What was finished and what "
        "was mapped carry themselves; what an interest turned out to be does not.")

REPORT = ("Then, as your last words, report your day to mission control in a few lines: "
          "what you did, what you found, and what is still worth doing and why. No call "
          "is needed after it.")


def dusk(world):
    """The day is over. Her memory first and her report last: a report sent first once
    ended her turn before the memory was written."""
    if world.lost:
        return (f"Sol {world.day} is over, and the rover is lost: the battery holds less "
                f"than the trip back to the pad needs, and nothing else recharges it. The "
                f"mission ends tonight. {REPORT}")
    out = ("" if world.docked else
           f" The rover is not beside the pad, so it is stranded tonight: no recharge, and "
           f"tomorrow it wakes where it stands on {world.battery} steps of battery.")
    last = (" It was the last sol of the mission." if S.MISSION_SOLS and
            world.day >= S.MISSION_SOLS else "")
    return f"Sol {world.day} is over.{out}{last} {KEEP} {REPORT}"


# The pane's line when a window opens.
OPENED = {"dawn": "dawn -- talk to her, post orders, or /next to begin the day",
          "radio": "she is on the radio -- answer, or /next to close the line; the "
                   "clock runs, and each reply she speaks costs her battery",
          "dusk": "dusk -- her report; /next for the night",
          "night": "night -- talk to her, or /next for the next sol"}


class Autopilot:
    """One sol's phases, clock and windows. `main.py` makes a new one every dawn.

    `attended`: a window is open on the app, so someone may be at the desk and the
    phases wait for them. `live=False` is a replay, which never waits and runs no clock.
    `words`: what the desk said with /next at last night's end, for the dawn.
    """

    def __init__(self, live=True, attended=False, words=""):
        self.live = live
        self.attended = attended and live
        self.phase = "dawn"
        self.started = False    # the phase's opening has gone out
        self.mark = 0           # len(conv.calls) when the latest turn or window opened
        self.failures = 0       # conv.failures already answered for
        self.retry_at = None    # when to ask again after a request that got no answer
        self.wait = None        # the open window: a key of OPENED, or None
        self.quiet_since = None # when it last went quiet, against COMMS_WAIT
        self.skip = False       # /next: close the window once she is quiet
        self.words = words      # /next's words, for whatever she is sent next
        self.after_line = False # the next turn the clock opens says the line closed
        self.urgent = None      # an urgent message waiting for the call in hand
        self.clock_at = None    # when the day's clock last ran
        self.said_at = 0        # len(conv.lines) when the dusk turn opened
        self.over = False       # the night has ended: the roll-over is the caller's

    # --- the frame ---------------------------------------------------------
    def tick(self, conv, world, now=None, typing=False):
        """One frame. Acts on `conv` and `world` once a turn is over, and returns
        "night" when the sol is finished and the roll-over is the caller's to do.
        `typing`: the desk is writing in her chat, which holds any open window."""
        now = time.monotonic() if now is None else now
        self.run_clock(world, now)
        if self.over:                   # asked again until the caller rolls the night
            return "night"
        if typing and self.wait:
            self.quiet_since = None
        if conv.busy or conv.waiting or not conv.ready():
            self.quiet_since = None
            return None
        if self.wait:
            return self._waiting(conv, world, now)
        if conv.failures > self.failures:
            self.failures = conv.failures
            self.retry_at = now + S.AUTO_RETRY_SECONDS
            conv.write("auto", f"the model did not answer -- asking again in "
                               f"{S.AUTO_RETRY_SECONDS:g}s")
            return None
        if self.retry_at is not None:
            if now >= self.retry_at:
                self.retry_at = None
                conv.retry()
            return None
        if conv.holds_sol:
            self._open(conv, carry_on(world))
            return None
        return getattr(self, "_" + self.phase)(conv, world, now)

    def run_clock(self, world, now=None):
        """The day's wall clock: run down while the day is on, live, and never paused.
        Safe to call more than once a frame -- `main.py` also calls it while the quit
        question is up, when `tick` is not called."""
        now = time.monotonic() if now is None else now
        if self.live and self.phase == "day" and self.clock_at is not None:
            world.run_clock(now - self.clock_at)
        self.clock_at = now if self.phase == "day" else None

    # --- the phases ----------------------------------------------------------
    def _dawn(self, conv, world, now):
        if not self.started:
            self.started = True
            placed = world.auto_objectives() if self.live else []
            self._open(conv, dawn(world, self.words, placed))
            self.words = ""
            return None
        self._open_wait(conv, world, "dawn", now)
        return None

    def _day(self, conv, world, now):
        if not self.started:
            self.started = True
            self.clock_at = now
            self._open(conv, begin(world, self.words))
            self.words = ""
            return None
        why = self._over(conv, world)
        if why:
            if self.urgent is not None:
                self.urgent = None
                conv.write("note", "the urgent message came too late: the day is over. "
                                   "Say it at night.")
            world.day_over = True
            world.record("sol_closed", by="autopilot", why=why)
            self._enter(world, "dusk")
            return self._dusk(conv, world, now)
        if self.urgent is not None:
            text, self.urgent = self.urgent, None
            self.mark = len(conv.calls)
            conv.send(f"URGENT from mission control: {text}", who="urgent")
            return None
        if self._called(conv):
            if self.attended:
                self._open_wait(conv, world, "radio", now)
                conv.on_line = True
                return None
            self.after_line = "unanswered"      # nobody there to answer
        self._open(conv, carry_on(world, self.after_line, self.words))
        self.after_line, self.words = False, ""
        return None

    def _dusk(self, conv, world, now):
        if not self.started:
            self.started = True
            self.said_at = len(conv.lines)
            self._open(conv, dusk(world))
            return None
        said = [text for who, text in conv.lines[self.said_at:] if who == "gemma"]
        if said:
            world.reports.append({"sol": world.day, "text": said[-1]})
            world.record("report", text=said[-1])
        self._open_wait(conv, world, "dusk", now)
        return None

    def _night(self, conv, world, now):
        if not self.started:
            self.started = True
            if self.words and self.attended and S.COMMS:
                conv.send(self.words, who="you")
                self.words = ""
                return None
        self._open_wait(conv, world, "night", now)
        return None

    def _enter(self, world, phase):
        self.phase, world.phase, self.started = phase, phase, False
        world.record("phase", phase=phase)
        # Dusk is over, so today's list goes. A replay clears it from this row on the
        # tape instead (`replay.apply`): it re-issues a sol's calls before it walks the
        # phases, so clearing here would wipe a list it had rebuilt from the night's.
        if phase == "night" and self.live:
            world.evening()

    def _over(self, conv, world):
        """Why the day is over, or None if it is not."""
        if world.day_over:
            return ("the battery is flat" if world.battery <= 0 else
                    "the clock ran out" if world.time_left <= 0 else "the desk ended it")
        if (len(conv.calls) > self.mark and conv.calls[-1].name == "end"
                and conv.ended):
            return "she called end"
        return None

    def _called(self, conv):
        """The turn just over ended on a radio call that got through."""
        if len(conv.calls) <= self.mark or not self.live or not S.COMMS:
            return False
        return skills.got_through(conv.calls[-1])

    def _open(self, conv, text, who="auto"):
        self.mark = len(conv.calls)
        conv.send(text, who=who)

    # --- the windows ---------------------------------------------------------
    def _open_wait(self, conv, world, why, now):
        self.wait, self.quiet_since = why, None
        self.mark = len(conv.calls)
        # A request still owed a retry belongs to the turn the window has just ended.
        self.retry_at, self.failures = None, conv.failures
        world.record("window", opened=why)
        if self.attended and S.COMMS:
            conv.write("note", OPENED[why])

    def _waiting(self, conv, world, now):
        why = self.wait
        if why == "radio" and (world.day_over or not S.COMMS or self._over(conv, world)):
            return self._close(conv, world)
        if not (self.attended and S.COMMS):        # nobody at the desk: /next by itself
            return self._close(conv, world)
        if self.quiet_since is None:
            self.quiet_since = now
        if self.skip or now - self.quiet_since >= S.COMMS_WAIT:
            return self._close(conv, world)
        return None

    def _close(self, conv, world):
        why, self.wait = self.wait, None
        self.skip, self.quiet_since = False, None
        self.failures = conv.failures
        world.record("window", closed=why)
        if why == "radio":
            # `mark` stays where the line opened, so an `end` she sent on it still
            # closes the day.
            conv.on_line = False
            self.after_line = True
            conv.write("note", "the line is closed")
            return None
        self.mark = len(conv.calls)
        if why == "night":
            self.over = True
            return "night"
        self._enter(world, {"dawn": "day", "dusk": "night"}[why])
        return None

    # --- the desk ------------------------------------------------------------
    def why_not(self):
        """Why the desk's words cannot reach her right now, or None if they can."""
        if not self.live:
            return "a replay is a tape -- nobody on it can be talked to"
        if not S.COMMS:
            return "comms are off -- nobody is at the desk, and nothing reaches her"
        if self.phase == "dusk":
            return "dusk is hers: she is writing her report. Talk at night, or /next"
        if self.phase == "day" and self.wait != "radio":
            return "it is day -- what you type goes to her as one urgent message"
        if not self.wait:
            return "she is still talking -- send it when she has finished"
        return None

    def say(self, conv, world, text, who="you"):
        """Words from the desk in her chat, at dawn, at night or on a radio line. None,
        or why they did not go."""
        why = self.why_not()
        if why:
            return why
        if conv.busy:
            return "she is still talking -- send it when she has finished"
        conv.send(text, who=who)
        self.quiet_since = None
        return None

    def next(self, text=""):
        """/next, with or without words: move on to the next phase, or close the line.
        None, or why not."""
        if not self.live:
            return "a replay is a tape -- it moves on by itself"
        if self.phase == "day" and self.wait != "radio":
            return ("the day ends when she calls end, the clock runs out or the battery "
                    "is flat -- Q ends it from the desk")
        self.skip, self.words = True, text.strip()
        return None

    def urgent_why_not(self, world):
        """Why an urgent message cannot go now, or None if it can."""
        if not self.live:
            return "a replay is a tape -- nobody on it can be called"
        if not S.COMMS:
            return "comms are off -- nobody is at the desk to call her"
        if self.phase != "day" or world.day_over:
            return "it is not day -- just talk to her"
        if self.urgent is not None:
            return "one urgent message at a time -- the last has not reached her yet"
        return None

    def send_urgent(self, conv, world, text):
        """Anything the desk types by day: one message, delivered once the call in hand
        has finished. It ends her turn, not her day. None, or why not."""
        why = self.urgent_why_not(world)
        if why:
            return why
        if not text.strip():
            return "an urgent message needs words"
        self.urgent = text.strip()
        world.record("urgent", text=self.urgent)
        conv.cut()
        return None

    def wait_left(self, now=None):
        """Seconds before a quiet window closes, or None while it is not counting."""
        if not self.wait or self.quiet_since is None:
            return None
        now = time.monotonic() if now is None else now
        return max(0.0, S.COMMS_WAIT - (now - self.quiet_since))
