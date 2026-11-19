"""Plays a kept run again with no model: every call on its tape is re-issued, and the
world is re-run. The model is the one thing that can't be made to repeat itself, so this
is how a run comes out the same twice. If a call's result differs from the tape, the
replay stops: the world has changed since the run was kept.
Usage: .venv/bin/python game/main.py --replay runs/<stamp>"""

import json

import chat
import logs
import registry
import skills


class Script:
    """A kept run, read back as the calls and the operator's actions that have to happen again."""

    def __init__(self, run_dir):
        self.dir = run_dir
        chat_rows = logs.read_rows(run_dir / "chat.jsonl")
        game_rows = logs.read_rows(run_dir / "game.jsonl")

        # A turn is what she said and the one call that ran. Refused calls (ran=False) are not replayed.
        self.turns = []
        said, drain = [], 0
        for i, r in enumerate(chat_rows):
            who = r.get("who")
            drain += r.get("drain") or 0  # her words on an open radio line
            if who == "gemma":
                said.append(r.get("text", ""))
            elif who == "call" and r.get("ran"):
                # The call's result is the next `result` row.
                expect = None
                for n in chat_rows[i + 1:i + 3]:
                    if n.get("who") == "result":
                        expect = n.get("text")
                        break
                self.turns.append({"day": r.get("day"), "name": r.get("name"),
                                   "args": r.get("args") or {}, "clock": r.get("clock"),
                                   "over": r.get("over"), "turn": r.get("turn"),
                                   "phase": r.get("phase"), "drain": drain,
                                   "t": r.get("t"), "ops": [],
                                   "said": " ".join(said).strip(), "expect": expect})
                said, drain = [], 0

        # The operator's actions. Each is done again before the first call after it on the
        # same sol; anything after a sol's last call is done when that sol closes.
        self.ops = {}
        for r in game_rows:
            if r.get("kind") not in OPS:
                continue
            after = None
            for t in self.turns:
                if (t["day"] == r.get("day") and t["t"] is not None
                        and r.get("t") is not None and t["t"] > r["t"]):
                    after = t
                    break
            if after is not None:
                after["ops"].append(r)
            else:
                self.ops.setdefault(r.get("day"), []).append(r)

        # The settings each sol was played under, which replay uses instead of the viewer's.
        self.settings = registry.from_log(game_rows)
        # A resumed run's replay has to wake on the same night.
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
        """The next recorded call, or None once the tape has run out, or (given `day`) once
        the next call belongs to a later sol."""
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
        """Do again what the operator did after the last call of `day`. Returns what."""
        return apply(world, self.ops.get(day, ()))


# What the operator does to the world or the board, and the night beginning, which clears her list.
OPS = ("orders", "order", "retract", "orders_cleared", "placed", "placed_interest",
       "phase")


def apply(world, rows):
    """Do the operator's rows again, on the live world. Returns a line for each. Re-done
    rather than copied, so a placement the game would refuse today is refused here too.
    `orders` is the old single-string board, kept so older tapes still replay."""
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
    """A Conversation whose model is the tape. Everything else is inherited, so a replay
    runs the same turn loop as the live run."""

    def __init__(self, world, script, tape=None):
        super().__init__(world, tape)
        self.script = script
        self.diverged = None
        self.tape_turn = None  # the live turn this replay turn is playing
        self.playing = None  # the tape's row for the call about to run

    def send(self, text, who="you"):
        self.tape_turn = None
        return super().send(text, who)

    def _today(self, t):
        return t["day"] is None or t["day"] <= self.day

    def _allowed(self):
        """Every skill: every call on the tape already ran live in its phase."""
        return tuple(skills.NAMES)

    @property
    def holds_sol(self):
        """True while the tape has more calls for today, so today is not over."""
        t = self.script.peek()
        return not self.diverged and t is not None and self._today(t)

    def _stream(self, messages, allowed=None):
        """The model's turn, read off the tape, inline. A spent or diverged tape, or a sol with no
        more calls, gives `end` by day and a reply with no call otherwise, so the turn closes.
        A live turn that ended without `end` (a cap, an urgent message) ends here at the same call."""
        t = None
        if not self.diverged:
            t = self.script.peek()
        if (t is not None and self._today(t) and self.tape_turn is not None
                and t["turn"] is not None and t["turn"] != self.tape_turn):
            self.q.put(("done", ({"done": True}, [])))
            return
        turn = None
        if not self.diverged:
            turn = self.script.next_turn(self.day)
        if turn is None:
            if self.diverged:
                self.q.put(("say", "The replay stopped here."))
            elif self.script.spent:
                self.q.put(("say", "The tape ends here."))
            else:
                self.q.put(("say", f"The tape has nothing more for sol {self.day}."))
            calls = []
            if self.world.phase == "day" and not self.world.day_over:
                calls = [{"name": "end", "arguments": {}}]
            self.q.put(("done", ({"done": True}, calls)))
            return
        if turn["said"]:
            self.q.put(("say", turn["said"]))
        # The phase the live call ran in, set before `_run` checks what the phase allows.
        if turn["phase"]:
            self.world.phase = turn["phase"]
        self.playing = turn
        self.tape_turn = turn["turn"]
        self.q.put(("done", ({"done": True},
                             [{"name": turn["name"], "arguments": turn["args"]}])))

    def _answer(self, fn, move, counts=True):
        """Run the call, then check its result string against the tape's."""
        turn = self.playing
        self.playing = None
        want = None
        if turn is not None:
            for done in apply(self.world, turn["ops"]):
                self.write("status", f"operator -- {done}")
            if turn["drain"]:
                self.world.drain(turn["drain"])
            # The day's clock as it stood when the live call ran. Replay runs no clock of its own.
            if turn["clock"] is not None:
                self.world.set_clock(turn["clock"])
            # A sol she closed with time left: the tape closes it.
            if turn["over"]:
                self.world.day_over = True
            want = turn["expect"]
        super()._answer(fn, move, counts)
        got = self.calls[-1].result
        if want is not None and got != want:
            self.diverged = (want, got)
            self.write("error", "REPLAY DIVERGED -- the world no longer matches the "
                                "tape, so this is not the run that was kept.")
            self.write("error", f"tape said: {want}")
            self.write("error", f"now:       {got}")
            self._stop("the replay diverged")


def load(run_dir):
    """A run directory as a Script. Raises if it has nothing to play."""
    s = Script(run_dir)
    if not len(s):
        raise ValueError(f"{run_dir} has no calls that ran -- nothing to replay")
    return s
