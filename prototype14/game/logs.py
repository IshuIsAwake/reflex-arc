"""A run's directory. It is written as it happens in runs/pending-<stamp>/, then renamed
at quit if kept, or deleted. A crash leaves the pending- folder behind.

    chat.jsonl   everything she was sent and said
    game.jsonl   what happened to the world
    night.json   what the last night kept, for --resume
    report.md    the mission so far (report.py)
    start.json   a resumed run's starting night, for replay
"""

import json
import os
import shutil
import time
from datetime import datetime


def load_night(run_dir):
    """The run's night.json, or ValueError saying why there is none."""
    path = run_dir / "night.json"
    if not path.exists():
        # A resumed run that crashed before its first nightfall wakes where it woke.
        path = run_dir / "start.json"
    if not path.exists():
        raise ValueError(f"{run_dir} has no night.json, so there is nothing to resume. "
                         f"Runs kept before resume was added never wrote one.")
    return json.loads(path.read_text(encoding="utf-8"))


class Run:
    """One session's logs. Hand `record` to the World, and keep or discard at the end."""

    def __init__(self, runs_dir, stamp=None, headless=False):
        self.stamp = ((stamp or datetime.now().strftime("%Y%m%d-%H%M%S"))
                      + ("-headless" if headless else ""))
        self.runs_dir = runs_dir
        self.dir = runs_dir / f"pending-{self.stamp}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.game = (self.dir / "game.jsonl").open("a", encoding="utf-8")
        self.settled = False

    @property
    def chat_path(self):
        return self.dir / "chat.jsonl"

    def record(self, kind, **fields):
        """One line of the game log, flushed at once so a crash loses nothing."""
        if self.settled:
            return
        row = {"t": round(time.time(), 3), "kind": kind, **fields}
        self.game.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        self.game.flush()

    def save_night(self, world):
        """Written beside and swapped in, so a crash mid-write leaves the previous night."""
        tmp = self.dir / "night.json.tmp"
        tmp.write_text(json.dumps(world.carry()), encoding="utf-8")
        os.replace(tmp, self.dir / "night.json")

    def save_report(self, text):
        tmp = self.dir / "report.md.tmp"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.dir / "report.md")

    def save_start(self, carried, source):
        """A resumed run keeps the night it woke from, so its replay can wake there too."""
        (self.dir / "start.json").write_text(json.dumps(carried), encoding="utf-8")
        self.record("resumed", source=str(source), sol=carried["day"] + 1)

    def keep(self):
        """Rename the run out of pending-. Returns where it ended up."""
        self._close()
        kept = self.runs_dir / self.stamp
        if kept.exists():  # two runs in the same second
            kept = self.runs_dir / f"{self.stamp}-{int(time.time() * 1000) % 1000}"
        self.dir.rename(kept)
        self.dir = kept
        return kept

    def discard(self):
        self._close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _close(self):
        self.settled = True
        if not self.game.closed:
            self.game.close()
