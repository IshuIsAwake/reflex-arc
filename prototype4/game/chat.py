"""Gemma, in the window, with one sense and one pair of hands.

`goto` and `distance` are tools -- gemma asks, the world answers; `skills.py` owns them.
The view is injected rather than fetched: `sight.view(world)` is appended to every
request and stored nowhere, so context holds exactly one view and it is the current one.

The system prompt promises exactly what is wired up, and a test holds it to the two
skills. Describing a skill that does not exist invents a world the model reasons about
and cannot reach.

Every world change happens on the main thread inside `pump()`. The model call is a
socket on a background thread and produces only text and requests.

No pygame in here -- `render.draw_chat` draws, this file talks.
"""

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.request

import settings as S
import sight
import skills
from sight import status_line   # one wording for the morning and the view


SYSTEM = """\
Congratulations on being the first LLM deployed directly to the surface of Mars. 
Your task here is critical for future missions: you must map the uncharted terrain of 
Jezero Flats using the least number of turns possible. You are the high-level cognitive planner; 
the rover's low-level control policy provides the wheels, but you provide the judgment. 
A human operator is monitoring your telemetry at all times.

The terrain you are tasked to explore has been divided into a strict 50 x 50 grid. 
Every cell in this grid has an absolute coordinate (x, y) for you to use. 
Our mission objective is total coverage—we need information on every single cell.

At the end of every message you are sent there is a block headed WHAT YOU CAN SEE
RIGHT NOW. It is rebuilt from scratch each time and is always current. You never have
to ask for it and there is no way to request it -- it simply arrives. It holds where
the rover is, the map of everything it has seen so far, and a list of the landmarks
found, each with its coordinates. Only one copy exists: the newest. If something
mattered, say it out loud, because the older blocks are gone.

You have three skills and no others:

  goto(x, y, why)       drive there. One call drives the whole way.
  distance(x, y, why)   what that drive would cost. Spends nothing.
  scout(x, y, why)      send the flyer to look at a square you have not driven to.

All three take ABSOLUTE coordinates -- a cell on the map in your view, never an offset from
where the rover stands. If it is at (25,25) and you want it ten cells south, work out
that this is (25,35) and pass that. Nothing here has a facing, so "forward" and "back"
mean nothing on their own; if someone asks for one, pick a compass direction, say which
you picked, and go.

Every call takes an optional `why`: one line on what you expect from it, written before
you find out. It changes nothing, nobody argues with it, and leaving it out never stops
a call from running. It is there so that later it is possible to tell what you predicted
from what you would say afterwards, which is worth a few words when the call is a
judgement call.

A day is a fixed number of steps and driving spends one per tile. Talking and thinking
cost nothing at all, so there is no hurry. You cannot end a day and you cannot start
one -- only the person can.

**Answering without calling a skill ends your turn.** You get up to ten calls in a
row, and you keep them only for as long as you keep calling. The moment you reply with
words alone, control goes back to the person and you do not act again until they speak.
So never announce what you are about to do -- do it, and describe it afterwards. "I
will check the distance next" spends your turn on a sentence.

**Aim far to optimize your turns.** Because you must map the grid in minimal turns, 
your primary strategy must be maximizing the reach of your `goto` commands. A single `goto` 
call drives the entire way to the target, revealing a massive 7-cell wide swath of terrain along its entire path in one fell swoop. 
Therefore, a long shot into the unknown is exponentially more efficient than inching forward cell by cell. 

Maximize your sensor footprint. The rover’s cameras reveal a 3-cell radius in all directions at 
all times (a 7-cell wide footprint). Once a cell is revealed as clear (.) or rock (#), it is permanently 
mapped. Driving over or directly adjacent to already-mapped cells is a critical waste of your limited daily steps.

Space out your routes. Because your vision sweeps a 7-cell wide path, you could intentionally leave wide gaps between 
your parallel long drives to prevent overlapping sensor fields. For example, if you drive a long route down column 4, 
your vision maps columns 1 through 7. To be efficient, your next parallel sweep should target column 11 to map columns 8 through 14. 
You will have to deviate to navigate around rocks, but your intended routes should always space themselves out by 
at least 7 cells to map the unknown (?) fog efficiently.

**The flyer sees ground the rover has not crossed.** `scout(x, y)` puts a square window
over the map centred where you say and reveals what is under it.
**It does not move the rover** -- only the map changes.
It costs steps out of the same day the rover drives on, it only reaches a short way
from where the rover is standing, and it has to charge on the ground for a while after
each sortie -- the status line above the map says whether it is ready. A window over
ground you have already mapped costs the same and reveals nothing, so aim it at ?.

Ground never seen is marked ? and a route through it is a guess -- `goto` assumes
it is clear and drives until something refuses it. Being stopped by rock you could not
have known about is not a mistake, it is how the map fills in, and a blocked long drive
teaches you more than a cautious short one. Aim at far corners and distant edges. 
**The arena has no wall around it.** The outer rows and columns are ordinary ground the rover 
can stand on, so aiming at the far edge is a real journey and not a mistake.
Some of it is rock, like anywhere else, and you find that out by going.

**The map in your view is a real map and you can read it.** It is drawn to scale, one
character to a cell, and it is the accumulated record of everything the rover has seen.
Row numbers run down the left edge and a ruler across the top marks every fifth column.
If you are asked what is at a coordinate, or what is in a region, or where the biggest
unexplored patch is, the answer is on that map and you should read it off and say so.
You do not have to drive somewhere to describe ground you have already mapped.

**Do not work out reachability for yourself, though.** Whether a route exists and what
it would cost is the one question the picture answers badly, and `distance` answers it
exactly for no steps. What is beside the rover, how far each way is open and where each
landmark sits are also written out underneath the map -- when they answer the question,
use them, because they are quicker than counting.

Use `distance` only to compare journeys you are undecided about. Do not use it to check
something you have already decided to do: `goto` tells you what it cost when it is
finished, and asking twice for the same number wastes a call you could have spent
driving.

Nothing is scattered out there to collect yet and nothing is asked of you by the
mission. Exploring the area, and being able to say what is where, is the whole job for
now.

You do not keep this conversation. When the day ends it is thrown away, and tomorrow
you begin knowing nothing of it.
"""

WHO = ("status", "you", "gemma", "think", "error", "note", "view", "call", "result")


# Control tokens the template leaks into `content`. Every one of eight gemma turns ended
# `<channel|>`, which then fed back into context as something she had said.
# Explicit rather than a catch-all `<...>` sweep, which would one day eat real content.
JUNK = re.compile(r"<\|?(?:channel|end_of_turn|start_of_turn|eot_id|im_end|im_start|"
                  r"eos|bos|end_of_text)\|?>")


def clean(text):
    """Strip template scaffolding out of what gemma said. Returns (text, how_many)."""
    out, n = JUNK.subn("", text)
    return out.strip(), n


# A view block can only ever be something *we* wrote. Anchored to the start of a line so
# that a reply merely mentioning the heading is not cut in half.
FABRICATED = re.compile(r"^[\s\-*#]*(?:" + "|".join(sight.HALLMARKS) + ")", re.M)


def cut_fabrication(text):
    """Drop the environment's half of the conversation when the model writes it itself.

    Returns (kept, characters_dropped).

    Gemma once answered with a sentence, a call typed as text, then four thousand
    characters of invented view -- a full grid, a step count, a position it had never
    occupied. Left alone that becomes an assistant message and she spends the next turn
    reasoning over a map she made up. Same family as the `<channel|>` leak `clean()`
    handles, one floor up: there a stray token, here the entire other speaker.
    """
    m = FABRICATED.search(text or "")
    if not m:
        return text, 0
    return text[:m.start()].rstrip(), len(text) - m.start()


def without_why(fn):
    """The call as history should carry it: everything except the rationale.

    `why` stays on the tape, timestamped before its result, but is kept out of context.
    In the unattended stretches it was 51% and 47% of durable history -- more than
    gemma's prose, the results and the map together -- and almost all of it a variation
    on one sentence she was copying back off herself.

    Stripping it also removed every example of a call carrying one, so she stopped
    sending it: 0 of 79 calls missing before, 16 of 21 after. That was fixed by making
    the field optional in `skills._why`, not by putting it back in context.

    The copy is not optional: `_settle` runs before `_run`, so `fn` is the same dict
    `skills.call` is about to read, and stripping in place would make every call come
    back BAD_ARGS for want of the argument it just lost. Unparsed string arguments are
    left alone rather than guessed at.
    """
    out = dict(fn)
    args = out.get("arguments")
    if isinstance(args, dict):
        out["arguments"] = {k: v for k, v in args.items() if k != "why"}
    return out


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

    The model call runs on a thread and streams back through a queue, so the game keeps
    drawing at sixty frames a second while gemma is thinking. `pump()` drains that queue
    once a frame and is the only place the display state changes.
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
        # The planner waits for the rover: `ready()` is asked before every request, and
        # `main.py` points it at the animation. Thinking through the drive would hide the
        # round trip that is the architectural claim.
        self.ready = lambda: True
        self.pending = None       # a request wanted but not yet allowed out
        self.hops = 0             # tool calls so far this human turn
        self.capped = False       # ...and whether this turn has already been stopped
        self.nudged = False       # ...and whether it has been told it narrated a call
        self.narrated = 0         # how often it wrote a call out and could not be read
        self.recovered = 0        # ...and how often one was read out of the text and run
        self.faked = 0            # view blocks it wrote for itself, cut before context
        self.calls = []           # every skills.Call this day, for reading back
        self.bad_args = 0         # what the `why` requirement and the parser cost
        self.junk = 0             # template tokens stripped out of what it said
        self._t0 = 0.0
        self._tools_sent = True   # ...and whether the request carried the schemas. A
                                  # capped turn goes out without them, so its prompt is
                                  # smaller for a reason that has nothing to do with the
                                  # view -- which the cost record would otherwise hide.

    # --- what goes in ----------------------------------------------------
    def open_day(self, w):
        """The morning. The numbers only -- the map arrives with the first request,
        the same way it will with every request after it."""
        self.write("status", status_line(w))
        self.messages.append({"role": "user", "content": status_line(w)})

    def send(self, text, who="you"):
        """A human turn. Marked as one, in the pane and on the tape.

        Human turns are labelled from the very first run so a day someone coached can
        never later be mistaken for a day the model worked out by itself.
        """
        if self.busy or not text.strip():
            return False
        self.write(who, text.strip())
        self.messages.append({"role": "user", "content": text.strip()})
        self.hops, self.capped, self.nudged = 0, False, False
        self._want()
        return True

    def _want(self, use_tools=True):
        """Ask for a request. It goes out as soon as `ready()` allows, not before."""
        self.pending = use_tools
        self._maybe_go()

    def _maybe_go(self):
        if self.pending is not None and self.ready():
            use_tools, self.pending = self.pending, None
            self._go(use_tools)

    @property
    def waiting(self):
        """Mid-turn, but held: the rover is still driving where the last call sent it."""
        return self.pending is not None

    def _go(self, use_tools=True):
        """One request. The view is built now, sent, and thrown away.

        Built when it is sent, not when it was wanted: the planner is held until the
        drive finishes, so those are different instants.

        `use_tools=False` sends no schemas, so gemma cannot ask for anything and the turn
        has to end in words. That is the only hard stop in the loop.

        `messages` is durable history and the view is never in it -- rebuilding it here
        keeps it current mid-tool-chain, where the rover has just moved and its old
        position is a lie. It goes at the *end* because Ollama caches the prompt prefix,
        so a block that changes every turn is free there and would invalidate the whole
        conversation at the front.
        """
        block = sight.view(self.world)
        self.write("view", sight.one_line(self.world), full=block)
        payload = self.messages + [{"role": "user", "content": block}]
        self.busy, self._t0, self._tools_sent = True, time.monotonic(), use_tools
        threading.Thread(target=self._stream, args=(payload, use_tools),
                         daemon=True).start()

    def write(self, who, text, full=None, pane=True, **data):
        """The pane gets `text`; the tape gets `full` when the two differ.

        The gap exists for views: context holds only the newest, so a finished run can
        only be read back if every one was written down as it was. The pane gets a
        one-liner, since fifty rows of grid a turn would bury the conversation.

        `data` rides on the tape and never on the pane -- a figure parsed back out of
        prose is a worse record than a field. `pane=False` is the same idea: a row the
        tape wants and the conversation does not. One door onto the tape either way, so
        nothing can write a record that forgets the day or the timestamp.
        """
        if pane:
            self.lines.append((who, text))
            del self.lines[:-400]
        if self.tape:
            self.tape.write({"day": self.day, "who": who, "text": full or text,
                             "t": round(time.time(), 3), **data})

    # --- the model -------------------------------------------------------
    def _stream(self, messages, use_tools=True):
        """Ollama, streamed, on a thread. Nothing here touches display state.

        `num_ctx` is set explicitly because Ollama's default is 4096 whatever the model
        can hold, and it drops the oldest messages without saying so. A day would
        quietly lose its own morning and gemma would read as forgetful.
        """
        # `MODEL_TEMP = None` omits the key entirely, which is the only way to say "the
        # model's own defaults" and mean all of them. Pinning temperature while leaving
        # top_k and top_p at the model's values is a mixture nobody measured.
        options = {"num_ctx": S.MODEL_CTX}
        if S.MODEL_TEMP is not None:
            options["temperature"] = S.MODEL_TEMP
        payload = {
            "model": S.MODEL, "messages": messages, "stream": True,
            "think": S.MODEL_THINK, "keep_alive": S.MODEL_KEEP_ALIVE,
            "options": options,
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
                # A request held for the rover gets its chance every frame.
                self._maybe_go()
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

    def _reply(self):
        """What it actually said: scaffolding stripped, invented environment cut off."""
        said, junk = clean(self.say_buf)
        said, faked = cut_fabrication(said)
        return said, junk, faked

    def _done(self, payload):
        d, wanted = payload
        used = d.get("prompt_eval_count", 0)
        self.last = (round(time.monotonic() - self._t0, 1), used, d.get("eval_count", 0))
        # The real token count, not a character estimate. `hops` says how deep in a turn
        # the request was; `tools` is here because a capped turn is sent without the
        # schemas, so its prompt count drops for reasons unrelated to the map.
        secs, tin, tout = self.last
        self.write("cost", f"{secs}s   {tin} tok in, {tout} out", pane=False,
                   seconds=secs, tokens_in=tin, tokens_out=tout,
                   hops=self.hops, tools=self._tools_sent)
        said, junk, faked = self._reply()
        if faked:
            self.faked += 1
            self.write("error", f"cut {faked} chars of view block it wrote for itself")

        # Recovery happens before `_settle`, which is what appends the assistant turn:
        # the call must be in `wanted` by then or its result dangles off no message.
        if not wanted and not self.capped:
            got = skills.written_call(said)
            if got:
                wanted = [{"name": got[0], "arguments": got[1]}]
                self.recovered += 1
                self.write("error", "call was typed out, not made -- running it anyway")

        self._settle(wanted, said, junk)
        # The context filling up is the failure that looks like forgetfulness, so say
        # it in the pane rather than leaving it in a number nobody reads.
        if used > S.MODEL_CTX * 0.9:
            self.write("error", f"context {used}/{S.MODEL_CTX} -- the morning is "
                                f"being dropped. Raise MODEL_CTX.")
        if wanted:
            self._run(wanted)
        elif not self.nudged and skills.looks_like_a_call(said):
            self._nudge()

    def _nudge(self):
        """It wrote the call out instead of making it. Say so, and give it one more go.

        Watched live on 2026-08-29: asked to explore, gemma replied *"I will drive north
        ... goto(25, 15, "Driving north to explore the unknown area ahead")"* with no
        tool call attached. Nothing ran. On screen that is a confident sentence and an
        arena that never moves, and nothing in it for the model to correct.

        `MODEL_TEMP` is the fix and this is the backstop, so it fires at most once per
        human turn. A second narrated reply is left alone -- by then it is the model
        choosing prose, not sampling noise, and re-asking forever is the same mistake as
        a cap that asks nicely.
        """
        self.nudged = True
        self.narrated += 1
        self.write("error", "that call was written as text, so nothing ran -- asking again")
        self.messages.append({"role": "user", "content":
                              "You wrote that call out as text in your reply instead of "
                              "making it. Nothing ran, nothing moved and no steps were "
                              "spent. Make the call itself now."})
        self._want()

    def _run(self, wanted):
        """Execute what gemma asked for, then hand it straight back to gemma.

        This is on the main thread: `pump()` is called once a frame from the game loop,
        so a drive that moves the rover cannot land halfway through a redraw.

        The hop cap is not tidiness: `distance` costs no steps, so a model looping on a
        misread position would never be stopped by the day's budget.

        The cap has to take the tools away, not ask nicely -- asking ran it four times
        in one turn, and withholding the schemas still let it fire eight. A limit that
        depends on the model's cooperation is not one. `capped` is the actual stop:
        further calls are dropped on the floor rather than run.
        """
        if self.hops >= S.MODEL_MAX_HOPS:
            first, self.capped = not self.capped, True
            self._refuse(wanted)
            if first:
                self.messages.append({"role": "user", "content":
                                      f"You have made {self.hops} calls without saying "
                                      f"anything, so your skills are switched off for "
                                      f"the rest of this turn. Say what you found and "
                                      f"what you would try next."})
                self.write("error", f"hop cap: {self.hops} calls in one turn, tools off")
                self._want(use_tools=False)
            return

        self._answer(wanted)

    def _refuse(self, wanted):
        """Turn down calls that arrive after the cap, out loud and in the context.

        Writing it to the pane alone left gemma asking and getting silence for eight
        turns running. A call that vanishes is the lying success code inverted: no
        outcome, nothing to reason about, so the same call comes back.

        It also keeps history well formed -- `_settle` has already appended the assistant
        turn carrying these `tool_calls`, so a call with no answer dangles. Both refusal
        paths go through here. It goes on the tape by name, because `refused 1 call(s)`
        cannot answer what it kept trying to do.
        """
        if not wanted:
            return
        self.write("error", f"refused {len(wanted)} call(s) -- this turn is over")
        note = (f"REFUSED -- you had already used all {S.MODEL_MAX_HOPS} calls for this "
                f"turn, so this one did not run and nothing happened. Say something to "
                f"be given another turn.")
        for fn in wanted:
            name = fn.get("name") or "unknown"
            args = {k: v for k, v in (_args(fn.get("arguments")) or {}).items()
                    if k != "why"}
            self.write("call", f"{name}({args}) REFUSED", full=f"{name}({args})  {note}")
            self.messages.append({"role": "tool", "tool_name": name, "content": note})

    def _answer(self, wanted):
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
        self._want()

    def _settle(self, wanted=(), said=None, junk=0):
        """Streaming buffers become history.

        The reasoning goes to the pane and the tape but never back into the context: it
        is the largest thing gemma produces, and what has to survive is the part it
        chose to say out loud.

        An assistant turn that asked for tools carries them into history even when it
        said nothing alongside -- drop them and the results answer a question no message
        asked. Arguments go in without `why`; `without_why` says why.

        Returns what it actually said, which `_done` needs to tell a reply from a call
        written out as one.
        """
        if self.think_buf.strip():
            self.write("think", clean(self.think_buf)[0])
        if said is None:                      # the error path settles without a reply
            said, junk, _ = self._reply()
        self.junk += junk
        if said:
            self.write("gemma", said)
        if said or wanted:
            turn = {"role": "assistant", "content": said}
            if wanted:
                turn["tool_calls"] = [{"function": without_why(fn)} for fn in wanted]
            self.messages.append(turn)
        self.say_buf = self.think_buf = ""
        self.busy = False
        return said


class Tape:
    """Append-only record of a conversation. The transcript is the actual output.

    It writes as it goes rather than at the end. Whether a finished run is *kept* is a
    separate question and `logs.py` answers it -- buffering here so the answer could be
    "no" would lose a crashed run silently, which is the one thing the tape exists to
    prevent.
    """

    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = path.open("a", encoding="utf-8")

    def write(self, record):
        self.f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.f.flush()

    def close(self):
        if not self.f.closed:
            self.f.close()
