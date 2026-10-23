"""The run directory: two streams, written as they happen, kept or discarded at quit.

Write first, decide afterwards -- buffering until the answer arrives would lose a crashed
run silently. A run streams to `runs/pending-<stamp>/` from the first frame:

    keep     ->  renamed to  runs/<stamp>/     (<stamp>-headless/ with no window)
    discard  ->  deleted
    crash    ->  left as     runs/pending-<stamp>/

A leftover `pending-` directory is a run nobody answered for, not an error.

    chat.jsonl   what gemma was told and said. Every view goes in full, because context
                 holds only the newest and the tape is the only way to read a run back.
    game.jsonl   what happened to the world, fed by `World.recorder` so `world.py` does
                 no I/O of its own.
    night.json   what the last night kept, so `--resume` can wake on the next sol.
    report.md    the mission so far, written from the world's record. `report.py`.
    start.json   on a resumed run only: the night it woke from, for replay.

No pygame in here, so the tests can drive the whole thing.
"""

import json
import os
import shutil
import time
from datetime import datetime


def load_night(run_dir):
    """The `night.json` of a run directory, or ValueError saying why there is none."""
    path = run_dir / "night.json"
    if not path.exists():
        # A resumed run that crashed before its first nightfall: wake where it woke.
        path = run_dir / "start.json"
    if not path.exists():
        raise ValueError(f"{run_dir} has no night.json, so there is nothing to resume. "
                         f"Runs kept before resume was added never wrote one.")
    return json.loads(path.read_text(encoding="utf-8"))


class Run:
    """One session's logs. Create it, hand `record` to the World, answer at the end."""

    def __init__(self, runs_dir, stamp=None, headless=False):
        # A run with no window says so in its name: those are tests, not sessions.
        self.stamp = ((stamp or datetime.now().strftime("%Y%m%d-%H%M%S"))
                      + ("-headless" if headless else ""))
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

    def save_night(self, world):
        """What the night keeps, replaced whole. Written beside and then swapped in, so a
        crash mid-write leaves the previous night rather than half of this one."""
        tmp = self.dir / "night.json.tmp"
        tmp.write_text(json.dumps(world.carry()), encoding="utf-8")
        os.replace(tmp, self.dir / "night.json")

    def save_report(self, text):
        """The report, replaced whole, the same way and for the same reason as the night."""
        tmp = self.dir / "report.md.tmp"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.dir / "report.md")

    def save_start(self, carried, source):
        """A resumed run keeps the night it woke from, so its replay can wake there too."""
        (self.dir / "start.json").write_text(json.dumps(carried), encoding="utf-8")
        self.record("resumed", source=str(source), sol=carried["day"] + 1)

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
