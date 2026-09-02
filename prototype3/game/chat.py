"""Gemma, in the window, with one sense and one pair of hands.

The model side, copied from prototype 1. Two things live here and they are
deliberately different shapes:

  * **`goto` and `distance` are tools.** Gemma asks; the world answers. `skills.py`
    owns what they accept and what comes back.
  * **The view is injected and never fetched.** `sight.view(world)` is appended to
    every request and stored nowhere, so context holds exactly one view and it is
    always the current one. There is no `look()` and there never needs to be.

**The system prompt promises exactly what is wired up.** A prompt describing skills
that do not exist is the same failure as a success code for a move that never
happened: it invents a world the model then reasons about and cannot reach. A test
holds it to the two. That is why the prompt below says nothing about the base being
somewhere it must return to, nothing about storms, and nothing about samples --
those are items 2, 3 and 6, and they are not built.

**Every world change happens on the main thread, inside `pump()`.** The model call is
a socket on a background thread and produces nothing but text and requests; the tool
that drives the rover runs a frame later, where the renderer is.

No pygame in here. `render.draw_chat` does the drawing and this file does the talking,
the same split `world.py` and `render.py` already have.
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

# What gemma is told. Every paragraph corresponds to something that exists.
original_SYSTEM = """\
You are the planner for a solar rover on Mars. You are not on Mars -- you are the team
that decides where it goes. The rover has the wheels and no judgement; you have the
judgement and no wheels. A person at the screen can see everything you can and is
watching. 

At the end of every message you are sent there is a block headed WHAT YOU CAN SEE
RIGHT NOW. It is rebuilt from scratch each time and is always current. You never have
to ask for it and there is no way to request it -- it simply arrives. It holds where
the rover is, the map of everything it has seen so far, and a list of the landmarks
found, each with its coordinates. Only one copy exists: the newest. If something
mattered, say it out loud, because the older blocks are gone.

You have two skills and no others:

  goto(x, y, why)       drive there. One call drives the whole way.
  distance(x, y, why)   what that drive would cost. Spends nothing.

Both take ABSOLUTE coordinates -- a cell on the map in your view, never an offset from
where the rover stands. If it is at (25,25) and you want it ten cells south, work out
that this is (25,35) and pass that. Nothing here has a facing, so "forward" and "back"
mean nothing on their own; if someone asks for one, pick a compass direction, say which
you picked, and go.

Every call needs a `why`: one line on what you expect from it, written before you find
out. It changes nothing and nobody argues with it. It is there so that later it is
possible to tell what you predicted from what you would say afterwards.

A day is a fixed number of steps and driving spends one per tile. Talking and thinking
cost nothing at all, so there is no hurry. You cannot end a day and you cannot start
one -- only the person can.

**Answering without calling a skill ends your turn.** You get up to eight calls in a
row, and you keep them only for as long as you keep calling. The moment you reply with
words alone, control goes back to the person and you do not act again until they speak.
So never announce what you are about to do -- do it, and describe it afterwards. "I
will check the distance next" spends your turn on a sentence.

**Aim far.** `goto` drives the whole way in one call and reports every outcrop it
meets, so a long shot into unknown ground is the single most productive thing you can
do. Ground never seen is marked ? and a route through it is a guess -- `goto` assumes
it is clear and drives until something refuses it. Being stopped by rock you could not
have known about is not a mistake, it is how the map fills in, and a blocked drive
teaches you more than a cautious one. Aim at far corners and distant edges rather than
one cell at a time. **The arena has no wall around it.** The outer rows and columns are
ordinary ground the rover can stand on, so aiming at the far edge is a real journey and
not a mistake. Some of it is rock, like anywhere else, and you find that out by going.

**Never work out for yourself whether the rover can reach something.** The picture of
the map is the shape of the place, not a table, and you will misread it if you count
cells off it. Everything exact -- what is beside the rover, how far each way is open,
where each landmark is -- is written out underneath the picture. Read it there.

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

You have two skills and no others:

  goto(x, y, why)       drive there. One call drives the whole way.
  distance(x, y, why)   what that drive would cost. Spends nothing.

Both take ABSOLUTE coordinates -- a cell on the map in your view, never an offset from
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


# Control tokens the template leaks into `content`. Found 2026-08-26 by reading a tape:
# every one of eight gemma turns ended `<channel|>`, and because the reply becomes an
# assistant message, the token was being fed back into context every turn and written
# into the transcript. It looks like nothing and it is the model reading its own
# scaffolding as though it were something it had said.
#
# The list is explicit rather than a catch-all `<...>` sweep: silently eating anything
# in angle brackets would one day eat real content and never say so.
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

    Found by reading `runs/20260829-134215/`: gemma answered with one sentence, a call
    typed out as text, and then **four thousand characters of invented view** -- a full
    grid, `399 steps left`, a position of (31,25) it had never occupied. It had slipped
    out of answering and into completing the whole dialogue.

    Left alone that becomes an assistant message, so from the next turn on the model is
    reasoning over a map it made up, and the transcript shows the game printing its own
    prompt. This is the same family as the `<channel|>` leak `clean()` handles -- the
    template's shape reaching content -- one floor further up: there it was a stray
    token, here it is the entire other speaker.
    """
    m = FABRICATED.search(text or "")
    if not m:
        return text, 0
    return text[:m.start()].rstrip(), len(text) - m.start()


def without_why(fn):
    """The call as history should carry it: everything except the rationale.

    **A5, and it is an experiment rather than a tidy-up.** Its whole job is to sit on
    the tape with a timestamp earlier than the result, so a reason given before an
    outcome cannot be rewritten into a story told after one -- and that job is untouched
    here. What it was *also* doing was riding back into context inside every assistant
    turn.

    **A5 held, and the requirement it was paired with did not.** Stripping the field
    from history also removed every example gemma had of a call carrying one, and she
    duly stopped sending it -- 0 of 79 calls missing it before, 22 of 52 after, 16 of 21
    in `runs/20260901-000753/`. Each omission was a `BAD_ARGS` that still cost a hop, so
    the turn hit the cap having driven five times out of twenty-one. **The stripping was
    not the mistake; requiring what had been stripped was.** `skills._why` made the
    field optional on 2026-09-01 and this function is unchanged, which is the pairing
    that was intended: out of context, still on the tape, never punished when absent.

    Measured over the two unattended stretches on 2026-08-30 -- the ones that look like
    the demo, where nobody is typing -- `why` was **51% and 47% of durable history**, more
    than gemma's own prose, the results and the map put together. Twenty-eight strings,
    mean 196 characters, nearly all a variation of *"I will drive south ... to maximize
    sensor coverage"*. The model is reading its own habits back and copying them, and a
    loop that survived five consecutive `_stuck` warnings is what that looks like from
    outside.

    **The 200-character cap in `skills._why` never touched this.** It trims `Call.why`,
    which is what reaches the tape; the raw arguments went to the model whole. So the cap
    was shortening the record and nothing else, and 26 of 28 strings hit it exactly.

    **The copy is not optional.** `_settle` runs before `_run`, so `fn` here is the same
    dict `skills.call` is about to read. Stripping in place would take the field out from
    under it and every call would come back BAD_ARGS for want of the argument it had just
    lost -- a parser bug wearing a model's face, which is the failure `skills` opens by
    warning about.

    Arguments that arrive as an unparsed string are left alone. `_args` would have to
    guess at them, and guessing here would change what the model is shown for reasons
    having nothing to do with `why`.
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
        # **The planner waits for the rover.** `ready()` is asked before every request
        # goes out; `main.py` points it at the animation so the next call cannot be
        # made until the drive it follows has finished on screen.
        #
        # Decided 2026-08-29, and it costs wall clock on purpose. The alternative --
        # thinking through the drive -- hides the round trip that is the entire
        # architectural claim: a planner that is seconds away from the body it is
        # driving. Watching gemma sit still while the rover crosses the arena is the
        # demo, not an accident of the demo.
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

        **Built at the moment it is sent, not the moment it was wanted.** With the
        planner held until the drive finishes, those are different instants, and the
        view has to describe the world the rover is actually in by then.

        `use_tools=False` sends the schemas nowhere, so gemma physically cannot ask for
        anything and the turn has to end in words. That is the only hard stop in the
        loop -- see `_run`.

        `messages` is the durable history and the view is never in it. Appending it
        would leave gemma reasoning over a pile of stale maps and would eat MODEL_CTX in
        a morning; rebuilding it here means the block is current even in the middle of a
        tool chain, where the rover has just moved and its old position is a lie.

        It goes at the *end* for a second reason: Ollama caches the prompt prefix, so a
        block that changes every turn is free where it is and would invalidate the whole
        conversation if it sat at the front.
        """
        block = sight.view(self.world)
        self.write("view", sight.one_line(self.world), full=block)
        payload = self.messages + [{"role": "user", "content": block}]
        self.busy, self._t0, self._tools_sent = True, time.monotonic(), use_tools
        threading.Thread(target=self._stream, args=(payload, use_tools),
                         daemon=True).start()

    def write(self, who, text, full=None, pane=True, **data):
        """The pane gets `text`; the tape gets `full` when the two differ.

        That gap exists for exactly one record type. Context holds only the newest view,
        so unless every view is written down as it was, a finished run cannot be read
        back at all -- and reading one back, not testing, is how the rock bug was found.
        The pane gets a one-liner instead because fifty rows of grid a turn would bury
        the conversation it sits beside.

        `data` rides on the tape record and never on the pane. It is for rows whose
        point is a number rather than a sentence, because a figure that has to be
        parsed back out of prose is a worse record than a field.

        `pane=False` is the other half of the same idea: a row the tape wants and the
        conversation does not. The cost line is the only one so far -- the footer
        already draws it live from `self.last`, and a copy per response would push the
        conversation off its own pane. Still one door onto the tape, so nothing can
        write a record that forgets the day or the timestamp.
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
        # **`MODEL_TEMP = None` means send no sampler at all**, which is not the same as
        # sending a number and is the whole point of the setting. Ollama then falls back
        # to the model's own Modelfile parameters -- for `gemma4:e4b`, temperature 1,
        # top_k 64, top_p 0.95 -- rather than to a default we picked. Pinning temperature
        # to 0 while leaving top_k and top_p at the model's values is a mixture nobody
        # ever measured; omitting the key is the only way to say "the defaults" and mean
        # every one of them. `--think` is what sets this, and `settings.py` says why.
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
        # **What the request actually cost, on the tape and not only in the pane.**
        # Every claim about what the view and the system prompt cost is a count of
        # characters -- `test_sight.py` says so in as many words and has since it was
        # written. This is the tokenizer, and it is Ollama's own: `prompt_eval_count`
        # is what the model was really charged for the request we really sent.
        #
        # `hops` is the calls already run this turn, so the row says how deep in a turn
        # the request was -- a tenth-hop prompt carries nine results the first did not.
        # `tools` is here because a capped turn is sent without the schemas, and its
        # prompt count drops for a reason that is nothing to do with the map.
        secs, tin, tout = self.last
        self.write("cost", f"{secs}s   {tin} tok in, {tout} out", pane=False,
                   seconds=secs, tokens_in=tin, tokens_out=tout,
                   hops=self.hops, tools=self._tools_sent)
        said, junk, faked = self._reply()
        if faked:
            self.faked += 1
            self.write("error", f"cut {faked} chars of view block it wrote for itself")

        # **Recovery happens before `_settle`, not after, and that ordering is the
        # whole trick.** `_settle` is what appends the assistant turn, so the call has
        # to be in `wanted` by then or it rides on no message at all -- and a tool
        # result answering a question no assistant turn asked is the dangling history
        # `_refuse` already exists to avoid.
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
        arena that never moves, and there is nothing in it for the model to correct --
        **the vanishing call, one more time.**

        `MODEL_TEMP` is the fix and this is the backstop, so it fires at most once per
        human turn. A second narrated reply in the same turn is left alone: at that point
        it is not sampling noise, it is the model choosing prose, and re-asking forever
        is the same mistake as a cap that asks nicely.
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

        The hop cap is not tidiness. A model that has misread its own position can
        reissue the same call forever, and `distance` costs no steps, so the day's
        budget is not a backstop against it -- only this is.

        **The cap has to take the tools away, not ask nicely.** The first version
        appended "stop and say what you have found" and then made an ordinary request:
        gemma called another tool, the cap fired again, and on 2026-08-26 that ran four
        times in a single turn. **And withholding the schemas is still not enough** --
        the cap fired eight times in one turn even with `tools` left out. A limit that
        depends on the model's cooperation, at any remove, is not one. `capped` is the
        actual stop: once a turn has been cut short, further calls are dropped on the
        floor rather than run, whatever comes back.
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

        Writing this to the pane alone left gemma asking for something and getting
        silence -- eight turns running on 2026-08-26, one refused call in every one of
        them and not a word about any. **A call that vanishes is the lying success code
        inverted**: no outcome, nothing to reason about, so the same call comes back.

        It also keeps the history well formed. `_settle` has already appended the
        assistant turn carrying these `tool_calls`, so a call with no answer dangles,
        and a conversation where a call has no answer is one no template was written
        for. Both refusal paths go through here so neither can forget.

        **And it goes on the tape by name.** Reading back the 2026-08-29 run, the
        transcript said `refused 1 call(s)` and nothing else: not which skill, not with
        what arguments, not what gemma was told in reply. The model knew -- it gets the
        REFUSED message below -- but the record did not, so the one question worth
        asking of that run ("what did it keep trying to do?") could not be answered.
        A call that vanishes from the log is the same failure one level up.
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

        An assistant turn that asked for tools has to go into the history carrying them,
        even when it said nothing alongside -- drop the `tool_calls` and the tool
        results that follow answer a question no message ever asked. It carries the
        arguments without `why`; `without_why` says why, and it is the A5 experiment.

        Returns what it actually said, which `_done` needs to tell a reply apart from a
        call written out as one.
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
