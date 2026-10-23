"""The conversation with the model, over Ollama. Each request is the history plus a fresh
view (sight.view), which is never stored, so the context holds only the current view.
The model call streams on a background thread; every change to the world happens on the
main thread, in pump(). No pygame here."""

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.request

import autopilot
import settings as S
import sight
import skills
import prompts
from sight import status_line  # one wording for the morning and the view

# Calls that only write her own notes. Several in one reply all run.
WRITES = ("todo", "strike", "remember", "forget")


# Template tokens Ollama leaks into the reply text. Listed one by one, so real <...> text survives.
JUNK = re.compile(r"<\|?(?:channel|end_of_turn|start_of_turn|eot_id|im_end|im_start|"
                  r"eos|bos|end_of_text)\|?>")


def clean(text):
    """Strip template tokens out of what she said. Returns (text, how_many)."""
    out, n = JUNK.subn("", text)
    return out.strip(), n


# A view block is only ever something we wrote. Anchored to a line start, so a mere mention isn't cut.
FABRICATED = re.compile(r"^[\s\-*#]*(?:" + "|".join(sight.HALLMARKS) + ")", re.M)


def cut_fabrication(text):
    """Cut off a view she has written herself (she once invented four thousand characters of
    map). Returns (kept, characters_dropped)."""
    m = FABRICATED.search(text or "")
    if not m:
        return text, 0
    return text[:m.start()].rstrip(), len(text) - m.start()


def without_why(fn):
    """The call as history carries it: without `why`, which stays on the tape. `why` filled
    half the history, mostly copied from itself. A copy, since skills.call reads the original."""
    out = dict(fn)
    args = out.get("arguments")
    if isinstance(args, dict):
        out["arguments"] = {k: v for k, v in args.items() if k != "why"}
    return out


def _args(a):
    """Ollama's arguments, parsed if they came as a string. A string that won't parse is passed
    on as one argument, so skills can refuse it by name."""
    if isinstance(a, dict):
        return a
    if isinstance(a, str):
        try:
            got = json.loads(a)
            return got if isinstance(got, dict) else {"raw": got}
        except ValueError:
            return {"raw": a}
    return {}


def installed_models(timeout=2):
    """What `ollama list` shows, as tags, or None if Ollama didn't answer."""
    url = S.OLLAMA_HOST.rsplit("/api/", 1)[0] + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return sorted(m["name"] for m in json.load(r).get("models", ()))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        return None


def host_for(model, day):
    """Where a request to `model` goes on sol `day`. An --outage sol sends it to a dead port, so it fails for real."""
    if model == S.MODEL and day in S.OUTAGE_SOLS:
        return S.OUTAGE_HOST
    return S.OLLAMA_HOST


def _probe(model, host):
    """One token from `model`. True if it answered at all."""
    body = json.dumps({"model": model, "stream": False, "keep_alive": S.MODEL_KEEP_ALIVE,
                       "messages": [{"role": "user", "content": "ok"}],
                       "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request(host, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=S.PROBE_TIMEOUT) as r:
            return "error" not in json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


class Link:
    """Which model is answering, for the whole run. When MODEL fails, requests go to
    MODEL_FALLBACK, and MODEL is probed every PROBE_SECONDS on a thread until it answers again.
    Every cost row on the tape names the model that answered."""

    def __init__(self, probe=None):
        self.down = False  # MODEL failed, and hasn't answered a probe since
        self.hold = False  # a sol's first request waits for the morning probe
        self._probe = probe or _probe
        self._next = 0.0
        self._results = queue.Queue()
        self._probing = False

    @property
    def model(self):
        return S.MODEL_FALLBACK if self.down else S.MODEL

    def failed(self, model):
        """A request to `model` got no answer. True if the link has switched to the fallback."""
        if (self.down or model != S.MODEL or not S.MODEL_FALLBACK
                or S.MODEL_FALLBACK == S.MODEL):
            return False
        self.down = True
        self._next = time.monotonic() + S.PROBE_SECONDS
        return True

    def morning(self):
        """A new sol tries MODEL at once, and holds the sol's first request until that probe answers."""
        if self.down:
            self.hold = True
            if not self._probing:
                self._next = 0.0

    def poll(self, day):
        """Once a frame. True at the moment MODEL is back."""
        try:
            answered = self._results.get_nowait()
        except queue.Empty:
            answered = None
        if answered is not None:
            self._probing = False
            self.hold = False
            if answered and self.down:
                self.down = False
                return True
            self._next = time.monotonic() + S.PROBE_SECONDS
        if self.down and not self._probing and time.monotonic() >= self._next:
            self._probing = True
            model, host = S.MODEL, host_for(S.MODEL, day)
            threading.Thread(target=lambda: self._results.put(self._probe(model, host)),
                             daemon=True).start()
        return False


class Conversation:
    """One day's talk, thrown away at nightfall. The model streams back through a queue on a
    thread; pump() drains it once a frame and is the only place the screen's state changes."""

    def __init__(self, world, tape=None, link=None):
        self.world = world  # the view is rebuilt from this on every request
        self.link = link or Link()  # which model answers; outlives the sol
        self.day = world.day
        self.messages = [{"role": "system", "content": prompts.SYSTEM}]
        self.lines = []  # (who, text): everything the pane shows
        self.say_buf = ""  # streaming answer, not yet a message
        self.think_buf = ""  # streaming reasoning, never becomes a message
        self.busy = False
        self.last = None  # (seconds, prompt_tokens, output_tokens)
        self.tape = tape
        self.q = queue.Queue()
        # Asked before every request; main.py points it at the animation, so she waits for the rover.
        self.ready = lambda: True
        self.pending = None  # a request wanted but not yet allowed out
        self.hops = 0  # tool calls so far this turn, of any kind
        self.moves = 0  # ...of which drives, against MOVE_HOPS
        self.frees = 0  # ...and looks since the last drive, against FREE_HOPS
        self.ended = False  # she called `end`, or the turn was ended for her
        self.cutting = False  # the desk has called: stop after the call in hand
        self.on_line = False  # a radio line is open: every reply she speaks costs battery
        self.nudged = False  # whether she has been told she wrote a call as text
        self.narrated = 0  # calls she wrote as text that couldn't be read
        self.recovered = 0  # ...and calls read out of her text and run
        self.faked = 0  # view blocks she wrote herself, cut before context
        self.calls = []  # every skills.Call this day
        self.bad_args = 0  # calls refused for bad arguments
        self.failures = 0  # requests that never got an answer; autopilot asks again
        self.turn_by = None  # who opened the latest turn: "you", "auto", ...
        self.turn = 0  # turns opened today, on every call row so a replay can end turns where the live run did
        self.junk = 0  # template tokens stripped from what she said
        self._t0 = 0.0
        self._tools_sent = None  # which schemas the request carried; a capped turn carries fewer

    def open_day(self, w):
        """The morning: the status line. The map comes with the first request."""
        self.link.morning()
        self.link.poll(w.day)
        self.write("status", status_line(w))
        self.messages.append({"role": "user", "content": status_line(w)})

    def send(self, text, who="you"):
        """A turn opened by `who`, shown as theirs in the pane and on the tape."""
        if self.busy or not text.strip():
            return False
        self._on_shift()
        self.turn_by = who
        self.turn += 1
        self.write(who, text.strip())
        self.messages.append({"role": "user", "content": text.strip()})
        self.hops = self.moves = self.frees = 0
        self.ended = self.nudged = self.cutting = False
        self._want()
        return True

    @property
    def holds_sol(self):
        """Whether something other than the clock decides where today ends. Live, no."""
        return False

    def _on_shift(self):
        """Someone sat down at the desk or left it since the last turn: swap in the new system
        prompt and tell her. Only between turns, so the history stays well formed."""
        if self.messages[0]["content"] == prompts.SYSTEM:
            return
        self.messages[0] = {"role": "system", "content": prompts.SYSTEM}
        note = autopilot.desk(S.COMMS)
        self.write("note", note)
        self.messages.append({"role": "user", "content": note})

    def cut(self):
        """The desk has called. The call in hand finishes, then the turn stops."""
        if self.busy:
            self.cutting = True
        elif self.pending is not None:  # held for the rover: the call has already run
            self._stop("mission control called")

    def _next(self):
        """The turn goes on, unless the desk has called."""
        if self.cutting:
            self._stop("mission control called")
        else:
            self._want()

    def retry(self):
        """Ask again for a request that got no answer. Not a new turn."""
        if self.busy or self.pending is not None:
            return False
        self._want()
        return True

    def _want(self):
        """Ask for a request. It goes out as soon as ready() allows."""
        self.pending = True
        self._maybe_go()

    def _allowed(self):
        """Which skills the next request offers: what the phase allows and the turn has left.
        Driving, work, the radio and `end` are the day's; looking and writing work in every phase."""
        names = ["distance", "count", "count_cells", "todo", "strike", "remember",
                 "forget"]
        if self.world.phase == "day" and not self.world.day_over:
            names += ["goto", "execute", "end"]
            if S.COMMS:
                names.append("radio")
        return tuple(n for n in skills.NAMES if n in names)

    def _not_now(self, name):
        """Why a call outside `_allowed` did not run."""
        if name == "radio" and self.world.phase == "day" and not self.world.day_over:
            return ("REFUSED -- nobody is at the desk, so nobody would hear it. Nothing "
                    "was sent.")
        if name == "radio":
            return "REFUSED -- it is not day: just say it. Nothing was sent."
        if name == "end":
            return ("REFUSED -- end closes the day, and it is not day. Nothing happened; "
                    "a reply with no call in it ends your turn.")
        return (f"REFUSED -- {name} drives or works, and the rover only does that by "
                f"day. Nothing moved and nothing was spent.")

    def _maybe_go(self):
        if self.pending is not None and self.ready() and not self.link.hold:
            self.pending = None
            self._go()

    @property
    def waiting(self):
        """Mid-turn, but held: the rover is still driving where the last call sent it."""
        return self.pending is not None

    def _go(self):
        """One request. The view and the allowed skills are worked out now, when it is sent, not
        when it was wanted. A turn with nothing left carries only `end`."""
        block = sight.view(self.world)
        self.write("view", sight.one_line(self.world), full=block)
        payload = self.messages + [{"role": "user", "content": block}]
        allowed = self._allowed()
        self.busy, self._t0, self._tools_sent = True, time.monotonic(), allowed
        # Chosen here on the main thread: the link can switch under a request in flight.
        self._sent_model = self.link.model
        self._sent_host = host_for(self._sent_model, self.world.day)
        threading.Thread(target=self._stream, args=(payload, allowed),
                         daemon=True).start()

    def write(self, who, text, full=None, pane=True, **data):
        """The pane gets `text`; the tape gets `full` when they differ (a view is one line on the
        pane, in full on the tape). `data` goes on the tape only; `pane=False` keeps a row off the pane."""
        if pane:
            self.lines.append((who, text))
            del self.lines[:-400]
        if self.tape:
            self.tape.write({"day": self.day, "who": who, "text": full or text,
                             "t": round(time.time(), 3), **data})

    def _stream(self, messages, allowed=None):
        """Ollama, streamed, on a thread. Nothing here touches the screen."""
        # MODEL_TEMP None sends no sampler options at all: the model's own defaults.
        options = {"num_ctx": S.MODEL_CTX}
        if S.MODEL_TEMP is not None:
            options["temperature"] = S.MODEL_TEMP
        # A fixed seed doesn't make the model repeat itself, but leaving it unset guarantees it won't.
        if S.MODEL_SEED is not None:
            options["seed"] = S.MODEL_SEED
        model = getattr(self, "_sent_model", S.MODEL)
        payload = {
            "model": model, "messages": messages, "stream": True,
            "think": S.MODEL_THINK, "keep_alive": S.MODEL_KEEP_ALIVE,
            "options": options,
        }
        payload["tools"] = skills.tools_for(allowed)
        body = json.dumps(payload).encode()
        req = urllib.request.Request(getattr(self, "_sent_host", S.OLLAMA_HOST), body,
                                     {"Content-Type": "application/json"})
        wanted, finished = [], False
        try:
            with urllib.request.urlopen(req, timeout=S.MODEL_TIMEOUT) as r:
                for raw in r:
                    if not raw.strip():
                        continue
                    d = json.loads(raw)
                    # Ollama reports an unreachable model as a line in the stream, not a status.
                    if d.get("error"):
                        raise ValueError(f"Ollama: {d['error']}")
                    m = d.get("message") or {}
                    if m.get("thinking"):
                        self.q.put(("think", m["thinking"]))
                    if m.get("content"):
                        self.q.put(("say", m["content"]))
                    for tc in m.get("tool_calls") or ():
                        wanted.append(tc.get("function") or {})
                    if d.get("done"):
                        # The calls come with `done`, so pump() sees a whole turn at once.
                        self.q.put(("done", (d, wanted)))
                        finished = True
            if not finished:
                raise ValueError("the stream ended without finishing")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            self.q.put(("error", f"{type(e).__name__}: {e}"))

    def pump(self):
        """Drain one frame's worth. Returns True if anything on screen changed."""
        changed = False
        if self.link.poll(self.world.day):
            self.write("note", f"{S.MODEL} answered a probe -- it takes the next request "
                               f"again")
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
                asked = getattr(self, "_sent_model", S.MODEL)
                if self.link.failed(asked):
                    # Not a failure to count: the same request goes out again now, to the fallback.
                    staged = (" (a simulated outage, --outage)"
                              if self.world.day in S.OUTAGE_SOLS else "")
                    self.write("error", f"{asked} did not answer{staged}: {payload} -- "
                                        f"{S.MODEL_FALLBACK} answers until it is back",
                               fallback=S.MODEL_FALLBACK)
                    self._next()
                else:
                    self.failures += 1
                    self.write("error", payload)
            elif kind == "done":
                self._done(payload)

    def _reply(self):
        """What she actually said: template tokens stripped, any fake view cut off."""
        said, junk = clean(self.say_buf)
        said, faked = cut_fabrication(said)
        return said, junk, faked

    def _done(self, payload):
        d, wanted = payload
        used = d.get("prompt_eval_count", 0)
        self.last = (round(time.monotonic() - self._t0, 1), used, d.get("eval_count", 0))
        # The real token counts; `hops` is how deep in the turn, `tools` the schemas sent.
        secs, tin, tout = self.last
        self.write("cost", f"{secs}s   {tin} tok in, {tout} out", pane=False,
                   seconds=secs, tokens_in=tin, tokens_out=tout,
                   hops=self.hops, tools=list(self._tools_sent or skills.NAMES),
                   model=getattr(self, "_sent_model", S.MODEL))
        said, junk, faked = self._reply()
        if faked:
            self.faked += 1
            self.write("error", f"cut {faked} chars of view block it wrote for itself")

        # A call typed as text is recovered before _settle, which writes the assistant turn.
        if not wanted and not self.ended:
            got = skills.written_calls(said)
            if got:
                wanted = [{"name": name, "arguments": args} for name, args in got]
                self.recovered += len(got)
                self.write("error", "call was typed out, not made -- running it anyway"
                           if len(got) == 1 else
                           f"{len(got)} calls were typed out, not made -- running them "
                           f"as if made")

        self._settle(wanted, said, junk)
        # Words spoken on an open line cost battery; `drain` goes on the tape for replay.
        if self.on_line and said and self.world.phase == "day":
            self.world.drain(S.RADIO_STEPS)
            self.write("note", f"her reply went over the radio: {S.RADIO_STEPS} steps of "
                               f"battery", drain=S.RADIO_STEPS)
        # Say it in the pane when the context is nearly full.
        if used > S.MODEL_CTX * 0.9:
            self.write("error", f"context {used}/{S.MODEL_CTX} -- the morning is "
                                f"being dropped. Raise MODEL_CTX.")
        if wanted:
            self._run(wanted)
        elif not self.nudged and skills.looks_like_a_call(said):
            self._nudge()

    def _nudge(self):
        """She wrote the call out instead of making it. Say so, and give her one more go, at most
        once a turn."""
        self.nudged = True
        self.narrated += 1
        self.write("error", "that call was written as text, so nothing ran -- asking again")
        self.messages.append({"role": "user", "content":
                              "You wrote that call out as text in your reply instead of "
                              "making it. Nothing ran, nothing moved and no steps were "
                              "spent. Make the call itself now."})
        self._next()

    def _run(self, wanted):
        """Run the calls one reply may make, refuse the rest, and decide whether the turn goes
        on. One call per reply, apart from writes: later calls were chosen before the first one's
        outcome was known. On the main thread, so a drive can't land mid-redraw."""
        # Writes change nothing a later call is chosen against, so a run of them all goes through, with the next call.
        n = next((i for i, fn in enumerate(wanted)
                  if (fn.get("name") or "").strip() not in WRITES), len(wanted) - 1)
        run, extra = wanted[:n + 1], wanted[n + 1:]
        on = True
        for i, fn in enumerate(run):
            on = self._one(fn)
            if not on:
                extra = run[i + 1:] + extra
                break
        if extra:
            self._refuse(extra, "REFUSED -- one call at a time, apart from writes to your "
                                "list and memory. This one did not run and nothing "
                                "happened. You get the map back after the call that did "
                                "run; decide again then.")
        if on:
            self._next()

    def _one(self, fn):
        """Run one call. Returns whether the turn has room for another."""
        name = (fn.get("name") or "").strip()
        if name in skills.NAMES and name not in self._allowed():
            # Counted as a look, so asking to drive at dawn still reaches the cap.
            self._refuse([fn], self._not_now(name))
            self.frees += 1
            return self._room()
        if name == "end":
            self._answer(fn, move=False, counts=False)
            self._stop("she called end")
            return False
        if name == "radio":
            # A radio call that got through ends her turn.
            self._answer(fn, move=False, counts=False)
            if skills.got_through(self.calls[-1]):
                self._stop("she radioed mission control")
                return False
            return True
        # What spends steps: work costs the day even though the rover stays put.
        self._answer(fn, move=name in ("goto", "execute"))
        return self._room()

    def _room(self):
        """Either allowance used up ends the turn; by day the clock opens the next one."""
        if self.moves >= S.MOVE_HOPS:
            self._stop(f"{S.MOVE_HOPS} drives this turn")
            return False
        if self.frees >= S.FREE_HOPS:
            self._stop(f"{S.FREE_HOPS} looks without a drive")
            return False
        return True

    def _stop(self, why):
        """The turn is over, not the sol. Nothing more is asked for."""
        self.ended = True
        self.pending = None
        self.cutting = False
        self.write("error", f"turn ended -- {why}")

    def _refuse(self, wanted, note):
        """Turn down calls that won't run, out loud and in the context, so she knows what happened
        and every tool call in the history gets an answer."""
        if not wanted:
            return
        # The allowance goes with a refusal too.
        note += skills.budget_note(self.world, self._left())
        self.write("error", f"refused {len(wanted)} call(s)")
        for fn in wanted:
            name = fn.get("name") or "unknown"
            args = {k: v for k, v in (_args(fn.get("arguments")) or {}).items()
                    if k != "why"}
            # ran=False: replay must not re-issue it.
            self.write("call", f"{name}({args}) REFUSED", full=f"{name}({args})  {note}",
                       name=name, args=args, ran=False)
            self.messages.append({"role": "tool", "tool_name": name, "content": note})

    def _left(self):
        """What the turn has left, sent with every result."""
        drives, looks = S.MOVE_HOPS - self.moves, S.FREE_HOPS - self.frees
        if self.world.phase != "day":
            return f" [{looks} looks left this turn]"
        return (f" [{drives} drives left this turn; "
                f"{looks} looks before you have to drive again]")

    def _answer(self, fn, move, counts=True):
        """One call, run and recorded. `counts=False` is `end`, which uses no allowance."""
        self.hops += 1
        if not counts:
            pass
        elif move:
            self.moves += 1
            self.frees = 0  # driving buys the looking allowance back
        else:
            self.frees += 1
        # The clock as the call found it, and whether the sol was already over, for replay.
        clock, over = self.world.time_left, self.world.day_over
        c = skills.call(self.world, fn.get("name"), _args(fn.get("arguments")),
                        history=self.calls)
        self.calls.append(c)
        if c.result.startswith("BAD_ARGS"):
            self.bad_args += 1
        # Name and arguments go on the tape as fields, so replay never parses the display text.
        self.write("call", f"{c}   why: {c.why or '--'}",
                   name=c.name, args=c.args, ran=True, clock=clock, over=over,
                   turn=self.turn, phase=self.world.phase)
        self.write("result", c.result)
        self.messages.append({"role": "tool", "tool_name": c.name,
                              "content": c.result + skills.budget_note(self.world,
                                                                       self._left())})

    def _settle(self, wanted=(), said=None, junk=0):
        """The streaming buffers become history. The reasoning goes to the pane and the tape but
        never back into the context. Tool calls go into history without `why`."""
        if self.think_buf.strip():
            self.write("think", clean(self.think_buf)[0])
        if said is None:  # the error path settles without a reply
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
    """The transcript, appended as it goes so a crash loses nothing. logs.py decides whether it is kept."""

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
