r"""A kept run, re-issued with no model in the loop.

    .venv/bin/python game/main.py --replay runs/20260905-084200

The script for a scripted run is a run that already happened. Go live until a sol comes
out well, press K to keep it, and that directory is the demo -- operator orders and
objective placements included, because those are lines on the tape like anything else.

**Why this exists at all.** Everything else in the stack can be pinned: the arena is
authored strings, the storm is seeded from `f"{name}:{w}x{h}:sol{day}"`, the day is
counted in steps rather than wall-clock, and the view sorts before it emits. The model
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


class Divergence(Exception):
    """The replay stopped agreeing with the tape. Carries both sides."""


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
        said = []
        for i, r in enumerate(chat_rows):
            who = r.get("who")
            if who == "gemma":
                said.append(r.get("text", ""))
            elif who == "call" and r.get("ran"):
                # The result is written immediately after the call it belongs to, so it
                # is the next `result` row and not a search.
                expect = next((n.get("text") for n in chat_rows[i + 1:i + 3]
                               if n.get("who") == "result"), None)
                self.turns.append({"day": r.get("day"), "name": r.get("name"),
                                   "args": r.get("args") or {},
                                   "said": " ".join(said).strip(), "expect": expect})
                said = []

        # What the operator typed at nightfall, filed under the sol she typed it on.
        # Applied when that sol closes, which is when she typed it.
        self.ops = {}
        for r in game_rows:
            if r.get("kind") in ("orders", "placed"):
                self.ops.setdefault(r.get("day"), []).append(r)

        self.i = 0

    def __len__(self):
        return len(self.turns)

    @property
    def spent(self):
        return self.i >= len(self.turns)

    def next_turn(self):
        """The next recorded call, or None once the tape has run out."""
        if self.spent:
            return None
        t = self.turns[self.i]
        self.i += 1
        return t

    def operator(self, world, day):
        """Re-do what the operator did at the close of `day`. Returns what she typed.

        Orders and placements are re-applied against the live world rather than having
        their effects copied out of the tape: a placement that the guard would refuse
        today must refuse today too, or replay would smuggle in a state the game does
        not permit.
        """
        done = []
        for r in self.ops.get(day, ()):
            if r["kind"] == "orders":
                world.notes.order(r.get("text", ""))
                done.append(f"orders: {r.get('text') or '(cleared)'}")
            else:
                cell = tuple(r["at"]) if isinstance(r["at"], list) else r["at"]
                o, why = world.place_objective(cell, r.get("priority", "medium"),
                                               r.get("cost", 30))
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

    def _stream(self, messages, allowed=None):
        """The model's turn, read off the tape instead of asked for.

        Runs inline rather than on a thread. There is nothing to wait for, and a thread
        would put a frame between the call and its result for no reason. The queue is
        still the seam, so `pump` cannot tell the difference.

        A spent tape emits `end`. The alternative is a turn that never closes, which
        reads on screen as the planner having hung.

        So does a diverged one, and it has to be checked here rather than left to
        `_answer`: `_run` calls `_want` straight after `_answer` returns, so a `_stop`
        raised down there is immediately undone by the next request being asked for.
        This is the only point in the loop where refusing to speak actually stops it.
        """
        turn = None if self.diverged else self.script.next_turn()
        if turn is None:
            self.q.put(("say", "The replay stopped here." if self.diverged else
                               "The tape ends here."))
            self.q.put(("done", ({"done": True}, [{"name": "end", "arguments": {}}])))
            return
        if turn["said"]:
            self.q.put(("say", turn["said"]))
        self._expect = turn["expect"]
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
