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
import prompts
from sight import status_line   # one wording for the morning and the view


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
        self.messages = [{"role": "system", "content": prompts.SYSTEM}]
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
        self.hops = 0             # tool calls so far this human turn, of any kind
        self.moves = 0            # ...of which drives, against MOVE_HOPS
        self.frees = 0            # ...and looks since the last drive, against FREE_HOPS
        self.move_denied = 0      # drives refused past the cap, against MOVE_GRACE
        self.free_denied = 0      # looks refused past the cap, against FREE_GRACE
        self.ended = False        # she called `end`, or it was called for her
        self.nudged = False       # ...and whether it has been told it narrated a call
        self.narrated = 0         # how often it wrote a call out and could not be read
        self.recovered = 0        # ...and how often one was read out of the text and run
        self.faked = 0            # view blocks it wrote for itself, cut before context
        self.calls = []           # every skills.Call this day, for reading back
        self.bad_args = 0         # what the `why` requirement and the parser cost
        self.junk = 0             # template tokens stripped out of what it said
        self._t0 = 0.0
        self._tools_sent = None   # ...and which schemas the request carried. A capped
                                  # turn goes out with fewer, so its prompt is smaller
                                  # for a reason that has nothing to do with the view --
                                  # which the cost record would otherwise hide. The names
                                  # and not a flag, so the tape says *which* were gone.

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
        self.hops = self.moves = self.frees = 0
        self.move_denied = self.free_denied = 0
        self.ended = self.nudged = False
        self._want()
        return True

    def _want(self):
        """Ask for a request. It goes out as soon as `ready()` allows, not before."""
        self.pending = True
        self._maybe_go()

    def _allowed(self):
        """Which schemas the next request carries, given what the turn has left.

        Read here rather than when the request was wanted, for the same reason the view
        is: the planner is held until the rover stops, so a drive may have landed in
        between and the allowance is a different number by the time this goes out.

        `end` is always in it. The way out cannot be the thing she is unable to reach.
        """
        names = ["end"]
        if self.moves < S.MOVE_HOPS:
            names += ["goto", "execute"]   # both spend steps
        if self.frees < S.FREE_HOPS:
            # Writing is a look: it spends no steps, so nothing else would ever stop a
            # model that took to writing instead of driving. It stays offered after the
            # day's steps are gone, which is deliberate -- a `goto` that spends the last
            # step mid-drive used to end the sol with the whole day unwritten.
            names += ["distance", "count", "count_cells", "todo", "strike", "remember"]
        return tuple(n for n in skills.NAMES if n in names)

    def _maybe_go(self):
        if self.pending is not None and self.ready():
            self.pending = None
            self._go()

    @property
    def waiting(self):
        """Mid-turn, but held: the rover is still driving where the last call sent it."""
        return self.pending is not None

    def _go(self):
        """One request. The view is built now, sent, and thrown away.

        Built when it is sent, not when it was wanted: the planner is held until the
        drive finishes, so those are different instants. `_allowed` is read at the same
        instant and for the same reason.

        A turn with nothing left goes out carrying `end` alone, so the only call it can
        make is the one that hands back. That is the hard stop in the loop.

        `messages` is durable history and the view is never in it -- rebuilding it here
        keeps it current mid-tool-chain, where the rover has just moved and its old
        position is a lie. It goes at the *end* because Ollama caches the prompt prefix,
        so a block that changes every turn is free there and would invalidate the whole
        conversation at the front.
        """
        block = sight.view(self.world)
        self.write("view", sight.one_line(self.world), full=block)
        payload = self.messages + [{"role": "user", "content": block}]
        allowed = self._allowed()
        self.busy, self._t0, self._tools_sent = True, time.monotonic(), allowed
        threading.Thread(target=self._stream, args=(payload, allowed),
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
    def _stream(self, messages, allowed=None):
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
        # The last row of the determinism ledger that can be pinned at all. It does not
        # make the model reproducible -- batching and non-associative float addition see
        # to that, which is why replay exists -- but leaving it unset guarantees it is
        # not, and costs one line to fix.
        if S.MODEL_SEED is not None:
            options["seed"] = S.MODEL_SEED
        payload = {
            "model": S.MODEL, "messages": messages, "stream": True,
            "think": S.MODEL_THINK, "keep_alive": S.MODEL_KEEP_ALIVE,
            "options": options,
        }
        payload["tools"] = skills.tools_for(allowed)
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
        # the request was; `tools` is the schemas it carried, because a capped turn is
        # sent with fewer and its prompt count drops for reasons unrelated to the map.
        secs, tin, tout = self.last
        self.write("cost", f"{secs}s   {tin} tok in, {tout} out", pane=False,
                   seconds=secs, tokens_in=tin, tokens_out=tout,
                   hops=self.hops, tools=list(self._tools_sent or skills.NAMES))
        said, junk, faked = self._reply()
        if faked:
            self.faked += 1
            self.write("error", f"cut {faked} chars of view block it wrote for itself")

        # Recovery happens before `_settle`, which is what appends the assistant turn:
        # the call must be in `wanted` by then or its result dangles off no message.
        if not wanted and not self.ended:
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
        """Run one call, refuse any others, and decide whether the turn goes on.

        This is on the main thread: `pump()` is called once a frame from the game loop,
        so a drive that moves the rover cannot land halfway through a redraw.

        **One call per request, always.** Watched 2026-09-04: the 31B asked for four to
        six drives in a single reply, and every one after the first had been chosen
        before any of their outcomes were known -- aimed at a map several drives out of
        date, which is where its BLOCKED results came from. It got one view per batch
        instead of one per drive. Running the extras would carry out decisions it had no
        way to make well, so they are turned down and it gets the map back instead.

        She drives until she calls `end`, so the two allowances below are the only
        things that stop a turn that never would.
        """
        first, extra = wanted[0], wanted[1:]
        if extra:
            self._refuse(extra, "REFUSED -- one call at a time. This one did not run "
                                "and nothing happened. You get the map back after the "
                                "call that did run; decide again then.")
        name = (first.get("name") or "").strip()
        if name == "end":
            # Never budgeted. Handing back has to stay available even to a turn that
            # has run out of everything else, or the way out is the thing she cannot do.
            self._answer(first, move=False, counts=False)
            self._stop("she called end")
            return

        # What spends steps, not what changes position: a piece of work costs the day
        # even though it leaves the rover where it stands.
        move = name in ("goto", "execute")
        spent = self.moves >= S.MOVE_HOPS if move else self.frees >= S.FREE_HOPS
        if spent:
            self._deny(first, move)
            return

        self._answer(first, move)
        self._want()

    def _deny(self, fn, move):
        """A call past its allowance: refused, counted, and eventually fatal to the turn.

        Refusing forever is its own failure -- a turn can be spent entirely on being
        told no, which is what happened when the cap had no grace. After MOVE_GRACE
        drives or FREE_GRACE looks are turned down, the turn is ended for her.
        """
        if move:
            self.move_denied += 1
            note = (f"REFUSED -- you have used all {S.MOVE_HOPS} drives this turn, so "
                    f"this one did not run and nothing moved. Call end to hand back.")
            spent = self.move_denied >= S.MOVE_GRACE
        else:
            self.free_denied += 1
            # Only offer the drive back when there is one. With both allowances gone,
            # "driving gives it back" names a way out that does not exist.
            back = ("Driving anywhere gives the allowance back, or call end to hand back."
                    if self.moves < S.MOVE_HOPS else "Call end to hand back.")
            note = (f"REFUSED -- you have looked {S.FREE_HOPS} times without driving, "
                    f"so this one did not run. {back}")
            spent = self.free_denied >= S.FREE_GRACE
        self._refuse([fn], note)
        if spent:
            self._stop("it kept asking after the allowance ran out")
        else:
            self._want()

    def _stop(self, why):
        """The turn is over. The *turn* -- the sol runs until the steps do.

        Nothing further is asked for, so `pump` falls idle and the crew can speak. She
        is not made to say anything on the way out: a model that has just been told no
        three times has nothing to add, and demanding a summary was only ever a way of
        making the cap look voluntary.
        """
        self.ended = True
        self.pending = None
        self.write("error", f"turn ended -- {why}")

    def _refuse(self, wanted, note):
        """Turn down calls that will not run, out loud and in the context.

        Writing it to the pane alone left gemma asking and getting silence for eight
        turns running. A call that vanishes is the lying success code inverted: no
        outcome, nothing to reason about, so the same call comes back.

        It also keeps history well formed -- `_settle` has already appended the assistant
        turn carrying these `tool_calls`, so a call with no answer dangles. Every refusal
        path goes through here. It goes on the tape by name, because `refused 1 call(s)`
        cannot answer what it kept trying to do.
        """
        if not wanted:
            return
        # The allowance rides on a refusal exactly as it rides on a result. Leaving it
        # off meant the one turn that most needed the numbers -- the one being told no --
        # was the only one that got a bare sentence.
        note += skills.budget_note(self.world, self._left())
        self.write("error", f"refused {len(wanted)} call(s)")
        for fn in wanted:
            name = fn.get("name") or "unknown"
            args = {k: v for k, v in (_args(fn.get("arguments")) or {}).items()
                    if k != "why"}
            # `ran=False`: this one was turned down and nothing happened. Replay must
            # not re-issue it, or the run it plays back is not the run that happened.
            self.write("call", f"{name}({args}) REFUSED", full=f"{name}({args})  {note}",
                       name=name, args=args, ran=False)
            self.messages.append({"role": "tool", "tool_name": name, "content": note})

    def _left(self):
        """What the turn has left, handed back with every result rather than once it is
        gone. A cap discovered only by hitting it cannot be planned around.

        The exhausted cases are spelled out rather than left to read as zeroes. The
        general phrasing promises a drive -- *"0 drives left this turn; 5 looks before
        you have to drive again"* -- and that was the last thing the 31B read before it
        spent its grace re-sending a drive it had just been told it could not make.
        """
        drives, looks = S.MOVE_HOPS - self.moves, S.FREE_HOPS - self.frees
        if not drives and not looks:
            return " [nothing left this turn -- call end to hand back]"
        if not drives:
            return (f" [no drives left this turn, and no more are coming until the crew "
                    f"speaks again; {looks} looks, then call end to hand back]")
        if not looks:
            return f" [{drives} drives left this turn; no looks until you drive again]"
        return (f" [{drives} drives left this turn; "
                f"{looks} looks before you have to drive again]")

    def _answer(self, fn, move, counts=True):
        """One call, run and recorded. Does not ask for the next request -- the caller
        decides whether there is one, because `end` is a call that has no next.

        `counts=False` is `end`, which is exempt from the allowances and so must not
        draw one down either: a counter that a free call moves does not describe the
        budget it is named after.
        """
        self.hops += 1
        if not counts:
            pass
        elif move:
            self.moves += 1
            self.frees = 0      # driving buys the looking allowance back
        else:
            self.frees += 1
        c = skills.call(self.world, fn.get("name"), _args(fn.get("arguments")),
                        history=self.calls)
        self.calls.append(c)
        if c.result.startswith("BAD_ARGS"):
            self.bad_args += 1
        # Name and arguments ride as fields, not only inside the sentence. Replay
        # re-issues these calls with no model in the loop, and a call parsed back out
        # of its own display string is exactly the worse record `write` warns about.
        self.write("call", f"{c}   why: {c.why or '--'}",
                   name=c.name, args=c.args, ran=True)
        self.write("result", c.result)
        self.messages.append({"role": "tool", "tool_name": c.name,
                              "content": c.result + skills.budget_note(self.world,
                                                                       self._left())})

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
