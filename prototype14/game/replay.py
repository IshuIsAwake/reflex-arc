r"""A kept run, re-issued with no model in the loop.

    .venv/bin/python game/main.py --replay runs/20260905-084200

The script for a scripted run is a run that already happened. Go live until a sol comes
out well, press K to keep it, and that directory is the demo -- operator orders and
objective placements included, because those are lines on the tape like anything else.

**Why this exists at all.** Everything else in the stack can be pinned: the arena is
authored strings, the storm is seeded from `f"{name}:{w}x{h}:sol{day}"`, the day's clock
is read off the tape at every call, and the view sorts before it emits. The model
cannot be. `MODEL_TEMP = 0.0` is greedy and usually reproduces on a fixed local build,
but inference batches requests and floating-point addition is not associative, so
identical prompts can give different logits depending on what else was in the batch.
Hosted models are worse. One differing token cascades through the whole sol. So for
anything that has to come out the same twice, take the model out of the loop -- which
is this file.

**What is replayed and what is re-run.** The calls are replayed; the world is not. Every
`goto` is planned and driven again from scratch over the map the rover has rebuilt for
itself, and `plan.txt` is written again leg by leg. That is the point: if the world is
deterministic, re-running it must land on the recorded outcome, and `_answer` below
checks every call against what the tape says it returned. A mismatch means something
upstream changed and the run on screen is no longer the run that was kept, so it stops
rather than carrying on plausibly.

**Replay assumes the hardware obeys.** Live, the simulation leads and the robot follows,
so a robot that stops early feeds back into a replan. Here there is no planner to react:
a slipped wheel puts the rover somewhere the tape does not know about and every leg after
it is wrong. The pause at each leg is still real -- `main.py` still waits -- and the
result check below is what turns a silent divergence into a halt.
"""

import json

import chat
import registry
import skills


def _rows(path):
    """One JSONL file as a list of dicts. A half-written line is skipped: a crashed run
    leaves one at the end, and it is the one record nobody promised was complete."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


class Script:
    """A kept run, read back as the things that have to happen again.

    Two streams and one ordering. `chat.jsonl` holds what the planner asked for and
    `game.jsonl` holds what the operator did between sols; both carry `t`, so the merge
    is by timestamp and neither file has to know about the other.
    """

    def __init__(self, run_dir):
        self.dir = run_dir
        chat_rows = _rows(run_dir / "chat.jsonl")
        game_rows = _rows(run_dir / "game.jsonl")

        # A turn is what it said and the one call that ran. `ran=False` rows are the
        # calls `_run` refused, and re-issuing one would replay a run that never
        # happened -- the refusal is the record, not the request.
        self.turns = []
        said, drain = [], 0
        for i, r in enumerate(chat_rows):
            who = r.get("who")
            drain += r.get("drain") or 0       # her words on an open radio line
            if who == "gemma":
                said.append(r.get("text", ""))
            elif who == "call" and r.get("ran"):
                # The result is written immediately after the call it belongs to, so it
                # is the next `result` row and not a search.
                expect = next((n.get("text") for n in chat_rows[i + 1:i + 3]
                               if n.get("who") == "result"), None)
                # `turn` and `over` are absent on tapes kept before they were written,
                # and those replay as they always did.
                self.turns.append({"day": r.get("day"), "name": r.get("name"),
                                   "args": r.get("args") or {}, "clock": r.get("clock"),
                                   "over": r.get("over"), "turn": r.get("turn"),
                                   "phase": r.get("phase"), "drain": drain,
                                   "t": r.get("t"), "ops": [],
                                   "said": " ".join(said).strip(), "expect": expect})
                said, drain = [], 0

        # What the operator did to the world and the board. Each is applied before the
        # first call that came after it on the same sol -- a placement typed in the
        # morning window is there for the whole sol -- and anything typed after a sol's
        # last call is applied when that sol closes, before the night reseeds the storm.
        self.ops = {}
        for r in game_rows:
            if r.get("kind") not in OPS:
                continue
            after = next((t for t in self.turns if t["day"] == r.get("day")
                          and t["t"] is not None and r.get("t") is not None
                          and t["t"] > r["t"]), None)
            if after is not None:
                after["ops"].append(r)
            else:
                self.ops.setdefault(r.get("day"), []).append(r)

        # The settings each sol was played under. Replay puts these in force rather
        # than the viewer's own, or a changed default would break every kept run.
        self.settings = registry.from_log(game_rows)
        # A resumed run woke from a saved night, and its replay has to wake there too.
        start = run_dir / "start.json"
        self.start = json.loads(start.read_text(encoding="utf-8")) if start.exists() else None
        self.first_sol = self.start["day"] + 1 if self.start else 1

        self.i = 0

    def __len__(self):
        return len(self.turns)

    @property
    def spent(self):
        return self.i >= len(self.turns)

    def peek(self):
        return None if self.spent else self.turns[self.i]

    def next_turn(self, day=None):
        """The next recorded call, or None once the tape has run out -- or, given `day`,
        once the next call belongs to a later sol. That one is left on the tape for the
        sol it was made on, which is how an unattended replay finds where a sol ended."""
        if self.spent:
            return None
        t = self.turns[self.i]
        if day is not None and t["day"] is not None and t["day"] > day:
            return None
        self.i += 1
        return t

    def use_settings(self, sol):
        """Put sol `sol`'s world settings in force. Returns the names that were refused."""
        return registry.apply(self.settings.get(sol, {}), only=lambda s: s.replayed)

    def operator(self, world, day):
        """Re-do what the operator did after the last call of `day`. Returns what."""
        return apply(world, self.ops.get(day, ()))


# What the operator does to the world or the board, which a replay has to do again --
# and the night beginning, which clears her list between the last call of dusk and the
# first of the night.
OPS = ("orders", "order", "retract", "orders_cleared", "placed", "placed_interest",
       "phase")


def apply(world, rows):
    """Re-do operator rows against the live world. Returns a line for each; the night
    beginning is not the operator's, and says nothing.

    Re-applied rather than copied out of the tape: a placement that the guard would refuse
    today must refuse today too, or replay would smuggle in a state the game does not
    permit. `orders` is the old single-string board, kept so older tapes still replay.
    """
    done, n = [], world.notes
    for r in rows:
        kind = r["kind"]
        if kind == "phase":
            if r.get("phase") == "night":
                world.evening()
        elif kind == "orders":
            n.clear_orders()
            if r.get("text"):
                n.order(r["text"])
            done.append(f"orders: {r.get('text') or '(cleared)'}")
        elif kind == "order":
            n.order(r.get("text", ""))
            done.append(f"order posted: {r.get('text')}")
        elif kind == "retract":
            n.retract(r.get("n", 0))
            done.append(f"order {r.get('n')} retracted")
        elif kind == "orders_cleared":
            n.clear_orders()
            done.append("orders cleared")
        elif kind == "placed_interest":
            cell = tuple(r["at"])
            i, why = world.place_interest(cell, r.get("text", ""), r.get("cost", 30))
            done.append(f"interest hidden at {cell}" if i
                        else f"interest at {cell} REFUSED on replay: {why}")
        else:
            cell = tuple(r["at"])
            o, why = world.place_objective(cell, r.get("priority", "medium"),
                                           r.get("cost", 30), r.get("auto", False))
            done.append(f"placed {o.glyph} at {cell}" if o
                        else f"placement at {cell} REFUSED on replay: {why}")
    return done


class Replay(chat.Conversation):
    """A `Conversation` whose model is a file.

    Everything else is inherited on purpose. The same `pump`, the same `_run`, the same
    one-call-per-turn rule, the same `_await_rover` pause between legs -- so what is on
    screen during a replay is the machinery that was on screen during the live run, with
    one function swapped. A separate driver that issued calls its own way would be a
    second implementation of the turn loop, and the demo would be testing that instead.
    """

    def __init__(self, world, script, tape=None):
        super().__init__(world, tape)
        self.script = script
        self.diverged = None
        self._tape_turn = None    # the live turn this replay turn is playing

    def send(self, text, who="you"):
        self._tape_turn = None
        return super().send(text, who)

    def _allowed(self):
        """Everything: every call on the tape ran live, in the phase it ran in, so none
        is refused here. The phase is set from the tape before each call all the same."""
        return tuple(skills.NAMES)

    @property
    def holds_sol(self):
        """The tape has more calls for today, so today is not over, whoever says so."""
        t = self.script.peek()
        return (not self.diverged and t is not None
                and (t["day"] is None or t["day"] <= self.day))

    def _stream(self, messages, allowed=None):
        """The model's turn, read off the tape instead of asked for.

        Runs inline rather than on a thread. There is nothing to wait for, and a thread
        would put a frame between the call and its result for no reason. The queue is
        still the seam, so `pump` cannot tell the difference.

        A spent tape emits `end` by day, and a reply with no call in any other phase. The
        alternative is a turn that never closes, which reads on screen as the planner
        having hung. So does a sol whose calls have all been made: the next one on the
        tape is tomorrow's.

        So does a diverged one, and it has to be checked here rather than left to
        `_answer`: `_run` calls `_want` straight after `_answer` returns, so a `_stop`
        raised down there is immediately undone by the next request being asked for.
        This is the only point in the loop where refusing to speak actually stops it.

        **A live turn that ended without `end`** -- a cap, an urgent call -- ends here at
        the same call, with nothing said and nothing called, so the next turn starts with
        its allowances back as the live one did.
        """
        t = None if self.diverged else self.script.peek()
        if (t is not None and (t["day"] is None or t["day"] <= self.day)
                and self._tape_turn is not None and t["turn"] is not None
                and t["turn"] != self._tape_turn):
            self.q.put(("done", ({"done": True}, [])))
            return
        turn = None if self.diverged else self.script.next_turn(self.day)
        if turn is None:
            # By day `end` closes it; in any other phase a reply with no call ends the turn.
            self.q.put(("say", "The replay stopped here." if self.diverged else
                               "The tape ends here." if self.script.spent else
                               f"The tape has nothing more for sol {self.day}."))
            day = self.world.phase == "day" and not self.world.day_over
            self.q.put(("done", ({"done": True},
                                 [{"name": "end", "arguments": {}}] if day else [])))
            return
        if turn["said"]:
            self.q.put(("say", turn["said"]))
        # Before `_run` checks what the phase allows: the live call ran in this one.
        if turn["phase"]:
            self.world.phase = turn["phase"]
        self._expect = turn["expect"]
        self._ops = turn["ops"]
        self._drain = turn["drain"]
        self._clock = turn["clock"]
        self._over = turn["over"]
        self._tape_turn = turn["turn"]
        self.q.put(("done", ({"done": True},
                             [{"name": turn["name"], "arguments": turn["args"]}])))

    def _answer(self, fn, move, counts=True):
        """Run the call, then check the world still agrees with the tape.

        The comparison is the recorded result string against the one just produced. It
        is the whole outcome of the call in one value -- where the rover ended up, what
        it cost, what it revealed, which code came back -- so a single equality catches
        a divergence anywhere in the world without a field-by-field list that would go
        stale the moment a result gains a clause.
        """
        for done in apply(self.world, getattr(self, "_ops", None) or ()):
            self.write("status", f"operator -- {done}")
        self._ops = None
        if getattr(self, "_drain", 0):
            self.world.drain(self._drain)
            self._drain = 0
        # The day's clock as it stood when the live call ran. A replay runs no clock of
        # its own, so this is the only thing that moves it.
        clock = getattr(self, "_clock", None)
        self._clock = None
        if clock is not None:
            self.world.set_clock(clock)
        # A sol she closed with time left: the clock would not close it, the tape does.
        if getattr(self, "_over", None):
            self.world.day_over = True
        self._over = None
        super()._answer(fn, move, counts)
        got = self.calls[-1].result
        want = getattr(self, "_expect", None)
        self._expect = None
        if want is not None and got != want:
            self.diverged = (want, got)
            self.write("error", "REPLAY DIVERGED -- the world no longer matches the "
                                "tape, so this is not the run that was kept.")
            self.write("error", f"tape said: {want}")
            self.write("error", f"now:       {got}")
            self._stop("the replay diverged")


def load(run_dir):
    """A run directory as a Script. Raises if there is nothing in it to play."""
    s = Script(run_dir)
    if not len(s):
        raise ValueError(f"{run_dir} has no calls that ran -- nothing to replay")
    return s
