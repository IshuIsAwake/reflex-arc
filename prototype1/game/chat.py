"""Gemma, in the window, with one sense and one pair of hands.

The model side. Two things live here and they are deliberately different shapes:

  * **`goto` and `distance` are tools.** Gemma asks; the world answers. `skills.py`
    owns what they accept and what comes back.
  * **The view is injected and never fetched.** `sight.view(world)` is appended to
    every request and stored nowhere, so context holds exactly one view and it is
    always the current one. There is no `look()` and there never needs to be.

**The system prompt promises exactly what is wired up.** A prompt describing skills
that do not exist is the same failure as a success code for a move that never
happened: it invents a world the model then reasons about and cannot reach. A test
holds it to the two.

**Every world change happens on the main thread, inside `pump()`.** The model call
is a socket on a background thread and produces nothing but text and requests; the
tool that moves gemma runs a frame later, where the renderer is. That keeps the
walk and the drawing off each other and keeps the whole loop drivable from a test
by pushing onto the same queue.

No pygame in here. `render.draw_chat` does the drawing and this file does the
talking, the same split `world.py` and `render.py` already have.
"""

import json
import queue
import threading
import time
import urllib.error
import urllib.request

import settings as S
import sight
import skills
from sight import status_line   # one wording for the morning and the view

# What gemma is told. Every paragraph corresponds to something that exists.
SYSTEM = """\
You have a body in a small world, and a person at the screen who can see it.

At the end of every message you are sent there is a block headed WHAT YOU CAN SEE
RIGHT NOW. It is rebuilt from scratch each time and is always current. You never
have to ask for it and there is no way to request it -- it simply arrives. It holds
where you are, the map of everything you have seen so far, and a list of the things
you have found, each with its coordinates. Only one copy exists: the newest. If
something mattered, say it out loud, because the older blocks are gone.

You have two skills and no others:

  goto(x, y, why)       walk to that cell. One call walks the whole way.
  distance(x, y, why)   what that walk would cost. Spends nothing.

Both take ABSOLUTE coordinates -- a cell on the map in your view, never an offset
from where you stand. If you are at (10,14) and want to go ten cells south, work
out that this is (10,24) and pass that. Nothing in this world has a facing, so
"forward" and "back" mean nothing on their own; if someone asks for one, pick a
compass direction, say which you picked, and go.

Every call needs a `why`: one line on what you expect from it, written before you
find out. It changes nothing and nobody argues with it. It is there so that later
it is possible to tell what you predicted from what you would say afterwards.

A day is a fixed number of steps and walking spends one per tile. Talking and
thinking cost nothing at all, so there is no hurry. You cannot end a day and you
cannot start one -- only the person can.

**Never work out for yourself whether you can reach something.** The picture of the
map in your view shows you the shape of the place; it is not a table and you will
misread it if you count cells off it. Ask `distance` instead. It costs nothing, it
is never wrong, and it answers in steps. Everything exact -- what is beside you, how
far each way is open, where each thing is -- is already written out underneath the
picture. Read it there rather than deriving it.

The map you are shown is the map you have walked. Ground you have never seen is
marked ?, and a route through it is a guess: `goto` assumes unseen ground is clear
and walks until something refuses it. Being stopped by a wall you could not have
known about is not a mistake. It is how the map gets filled in, and the walls you
hit come back to you in the answer, so a blocked walk is worth more than a
cautious one.

You do not keep this conversation. When the day ends it is thrown away, and
tomorrow you begin knowing nothing of it.
"""

WHO = ("status", "you", "gemma", "think", "error", "note", "view", "call", "result")


def _args(a):
    """Ollama hands arguments back already parsed, but not always.

    A string that will not parse is passed through as one argument rather than
    swallowed, so `skills` gets to reject it by name. Returning `{}` here would turn a
    malformed call into a missing-`why` complaint and hide what actually went wrong.
    """
    if isinstance(a, dict):
        return a
    if isinstance(a, str):
        try:
            got = json.loads(a)
            return got if isinstance(got, dict) else {"raw": got}
        except ValueError:
            return {"raw": a}
    return {}


class Conversation:
    """One day's talk. Thrown away at nightfall, which is the whole architecture.

    The model call runs on a thread and streams back through a queue, so the game
    keeps drawing at sixty frames a second while gemma is thinking. `pump()` drains
    that queue once a frame and is the only place the display state changes.
    """

    def __init__(self, world, tape=None):
        self.world = world        # the view is rebuilt from this on every request
        self.day = world.day
        self.messages = [{"role": "system", "content": SYSTEM}]
        self.lines = []           # (who, text) -- everything the pane shows
        self.say_buf = ""         # streaming answer, not yet a message
        self.think_buf = ""       # streaming reasoning, never becomes a message
        self.busy = False
        self.last = None          # (seconds, prompt_tokens, output_tokens)
        self.tape = tape
        self.q = queue.Queue()
        self.hops = 0             # tool calls so far this human turn
        self.capped = False       # ...and whether this turn has already been stopped
        self.calls = []           # every skills.Call this day, for reading back
        self.bad_args = 0         # what the `why` requirement and the parser cost
        self._t0 = 0.0

    # --- what goes in ----------------------------------------------------
    def open_day(self, w):
        """The morning. The numbers only -- the map arrives with the first request,
        the same way it will with every request after it."""
        self.write("status", status_line(w))
        self.messages.append({"role": "user", "content": status_line(w)})

    def send(self, text, who="you"):
        """A human turn. Marked as one, in the pane and on the tape.

        Human turns are labelled from the very first run so a day someone coached
        can never later be mistaken for a day the model worked out by itself.
        """
        if self.busy or not text.strip():
            return False
        self.write(who, text.strip())
        self.messages.append({"role": "user", "content": text.strip()})
        self.hops, self.capped = 0, False
        self._go()
        return True

    def _go(self, use_tools=True):
        """One request. The view is built now, sent, and thrown away.

        `use_tools=False` sends the schemas nowhere, so gemma physically cannot ask
        for anything and the turn has to end in words. That is the only hard stop in
        the loop -- see `_run`.

        `messages` is the durable history and the view is never in it. Appending it
        would leave gemma reasoning over a pile of stale maps and would eat MODEL_CTX
        in a morning; rebuilding it here means the block is current even in the middle
        of a tool chain, where gemma has just moved and its old position is a lie.

        It goes at the *end* for a second reason: Ollama caches the prompt prefix, so
        a block that changes every turn is free where it is and would invalidate the
        whole conversation if it sat at the front.
        """
        block = sight.view(self.world)
        self.write("view", sight.one_line(self.world), full=block)
        payload = self.messages + [{"role": "user", "content": block}]
        self.busy, self._t0 = True, time.monotonic()
        threading.Thread(target=self._stream, args=(payload, use_tools),
                         daemon=True).start()

    def write(self, who, text, full=None):
        """The pane gets `text`; the tape gets `full` when the two differ.

        That gap exists for exactly one record type. Context holds only the newest
        view, so unless every view is written down as it was, a finished run cannot be
        read back at all -- and reading one back, not testing, is how the wall bug was
        found. The pane gets a one-liner instead because twenty-five rows of grid a
        turn would bury the conversation it sits beside.
        """
        self.lines.append((who, text))
        del self.lines[:-400]
        if self.tape:
            self.tape.write({"day": self.day, "who": who, "text": full or text,
                             "t": round(time.time(), 3)})

    # --- the model -------------------------------------------------------
    def _stream(self, messages, use_tools=True):
        """Ollama, streamed, on a thread. Nothing here touches display state.

        `num_ctx` is set explicitly because Ollama's default is 4096 whatever the
        model can hold, and it drops the oldest messages without saying so. A day
        would quietly lose its own morning and gemma would read as forgetful.
        """
        payload = {
            "model": S.MODEL, "messages": messages, "stream": True,
            "think": S.MODEL_THINK, "keep_alive": S.MODEL_KEEP_ALIVE,
            "options": {"num_ctx": S.MODEL_CTX},
        }
        if use_tools:
            payload["tools"] = skills.TOOLS
        body = json.dumps(payload).encode()
        req = urllib.request.Request(S.OLLAMA_HOST, body,
                                     {"Content-Type": "application/json"})
        wanted = []
        try:
            with urllib.request.urlopen(req, timeout=S.MODEL_TIMEOUT) as r:
                for raw in r:
                    if not raw.strip():
                        continue
                    d = json.loads(raw)
                    m = d.get("message") or {}
                    if m.get("thinking"):
                        self.q.put(("think", m["thinking"]))
                    if m.get("content"):
                        self.q.put(("say", m["content"]))
                    for tc in m.get("tool_calls") or ():
                        wanted.append(tc.get("function") or {})
                    if d.get("done"):
                        # The calls ride with `done` rather than arriving separately,
                        # so pump() sees a whole turn at once and never acts on half
                        # of one.
                        self.q.put(("done", (d, wanted)))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            self.q.put(("error", f"{type(e).__name__}: {e}"))

    def pump(self):
        """Drain one frame's worth. Returns True if anything on screen changed."""
        changed = False
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                return changed
            changed = True
            if kind == "think":
                self.think_buf += payload
            elif kind == "say":
                self.say_buf += payload
            elif kind == "error":
                self._settle()
                self.write("error", payload)
            elif kind == "done":
                self._done(payload)

    def _done(self, payload):
        d, wanted = payload
        used = d.get("prompt_eval_count", 0)
        self.last = (round(time.monotonic() - self._t0, 1), used, d.get("eval_count", 0))
        self._settle(wanted)
        # The context filling up is the failure that looks like forgetfulness, so
        # say it in the pane rather than leaving it in a number nobody reads.
        if used > S.MODEL_CTX * 0.9:
            self.write("error", f"context {used}/{S.MODEL_CTX} -- the morning is "
                                f"being dropped. Raise MODEL_CTX.")
        if wanted:
            self._run(wanted)

    def _run(self, wanted):
        """Execute what gemma asked for, then hand it straight back to gemma.

        This is on the main thread: `pump()` is called once a frame from the game
        loop, so a walk that moves the player cannot land halfway through a redraw.

        The hop cap is not tidiness. A model that has misread its own position can
        reissue the same call forever, and `distance` costs no steps, so the day's
        budget is not a backstop against it -- only this is.

        **The cap has to take the tools away, not ask nicely.** The first version
        appended "stop and say what you have found" and then made an ordinary request:
        gemma called another tool, the cap fired again, and on 2026-08-26 that ran four
        times in a single turn while the model bounced between two adjacent cells. A
        limit enforced by asking the thing being limited is not a limit.

        **And withholding the schemas is still not enough**, which the second run
        showed: the cap fired eight times in one turn even with `tools` left out of the
        request. Whether that is Ollama parsing tool syntax out of the text or the
        template emitting it from the history does not matter -- a limit that depends
        on the model's cooperation, at any remove, is not one. `capped` is the actual
        stop: once a turn has been cut short, further calls are dropped on the floor
        rather than run, whatever comes back.
        """
        if self.capped:
            self.write("error", f"dropped {len(wanted)} call(s) -- this turn is over")
            return
        if self.hops >= S.MODEL_MAX_HOPS:
            self.capped = True
            self.messages.append({"role": "user", "content":
                                  f"You have made {self.hops} calls without saying "
                                  f"anything, so your skills are switched off for the "
                                  f"rest of this turn. Say what you found and what you "
                                  f"would try next."})
            self.write("error", f"hop cap: {self.hops} calls in one turn, tools off")
            self._go(use_tools=False)
            return

        for fn in wanted:
            self.hops += 1
            c = skills.call(self.world, fn.get("name"), _args(fn.get("arguments")),
                            history=self.calls)
            self.calls.append(c)
            if c.result.startswith("BAD_ARGS"):
                self.bad_args += 1
            self.write("call", f"{c}   why: {c.why or '--'}")
            self.write("result", c.result)
            self.messages.append({"role": "tool", "tool_name": c.name,
                                  "content": c.result + skills.budget_note(self.world)})
        self._go()

    def _settle(self, wanted=()):
        """Streaming buffers become history.

        The reasoning goes to the pane and the tape but never back into the
        context: it is the largest thing gemma produces, and what has to survive is
        the part it chose to say out loud.

        An assistant turn that asked for tools has to go into the history carrying
        them, even when it said nothing alongside -- drop the `tool_calls` and the
        tool results that follow answer a question no message ever asked.
        """
        if self.think_buf.strip():
            self.write("think", self.think_buf.strip())
        said = self.say_buf.strip()
        if said:
            self.write("gemma", said)
        if said or wanted:
            turn = {"role": "assistant", "content": said}
            if wanted:
                turn["tool_calls"] = [{"function": dict(fn)} for fn in wanted]
            self.messages.append(turn)
        self.say_buf = self.think_buf = ""
        self.busy = False


class Tape:
    """Append-only record of a conversation. The transcript is the actual output."""

    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = path.open("a", encoding="utf-8")

    def write(self, record):
        self.f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.f.flush()
