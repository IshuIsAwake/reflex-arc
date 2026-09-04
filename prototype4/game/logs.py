"""The run directory: two streams, written as they happen, kept or discarded at quit.

Write first, decide afterwards -- buffering until the answer arrives would lose a crashed
run silently. A run streams to `runs/pending-<stamp>/` from the first frame:

    keep     ->  renamed to  runs/<stamp>/
    discard  ->  deleted
    crash    ->  left as     runs/pending-<stamp>/

A leftover `pending-` directory is a run nobody answered for, not an error.

    chat.jsonl   what gemma was told and said. Every view goes in full, because context
                 holds only the newest and the tape is the only way to read a run back.
    game.jsonl   what happened to the world, fed by `World.recorder` so `world.py` does
                 no I/O of its own.

No pygame in here, so the tests can drive the whole thing.
"""

import json
import shutil
import time
from datetime import datetime


class Run:
    """One session's logs. Create it, hand `record` to the World, answer at the end."""

    def __init__(self, runs_dir, stamp=None):
        self.stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.runs_dir = runs_dir
        self.dir = runs_dir / f"pending-{self.stamp}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.game = (self.dir / "game.jsonl").open("a", encoding="utf-8")
        self.settled = False

    @property
    def chat_path(self):
        """Where `chat.Tape` should write. It opens the file itself."""
        return self.dir / "chat.jsonl"

    def record(self, kind, **fields):
        """One line of the game log. This is what `World.recorder` is set to.

        Flushed every line on purpose -- an unflushed buffer is exactly the crash case
        this module is built around.
        """
        if self.settled:
            return
        row = {"t": round(time.time(), 3), "kind": kind, **fields}
        self.game.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        self.game.flush()

    # --- the answer at quit ----------------------------------------------
    def keep(self):
        """Promote the run out of `pending-`. Returns where it ended up.

        Named for the moment it started, not the moment it finished, so the directory
        sorts next to the conversation that produced it.
        """
        self._close()
        kept = self.runs_dir / self.stamp
        if kept.exists():                       # two runs in the same second
            kept = self.runs_dir / f"{self.stamp}-{int(time.time() * 1000) % 1000}"
        self.dir.rename(kept)
        self.dir = kept
        return kept

    def discard(self):
        """Throw the whole run away. Nothing is left behind."""
        self._close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _close(self):
        self.settled = True
        if not self.game.closed:
            self.game.close()
