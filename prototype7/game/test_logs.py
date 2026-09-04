"""The run directory, and the promise that a crash never costs a run.

    .venv/bin/python game/test_logs.py

The feature is "ask at quit whether to keep the logs". The way *not* to build it is to
buffer everything in memory until the answer arrives, because then a crash loses the
run and says nothing. So the whole file is really one assertion:
`test_a_run_is_on_disk_before_anyone_is_asked`.
"""

import json
import sys
import tempfile
from pathlib import Path

import chat
import logs
import nav
import settings as S
from world import World


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


def rig(root):
    run = logs.Run(Path(root), stamp="20260904-101500")
    w = World(recorder=run.record)
    return run, w


def lines(path):
    return [json.loads(li) for li in path.read_text().splitlines() if li.strip()]


def test_a_run_is_on_disk_before_anyone_is_asked():
    print("write first, decide afterwards")
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        ok = check("a pending directory exists straight away", run.dir.is_dir(),
                   run.dir.name)
        ok &= check("named so it is obviously unanswered",
                    run.dir.name.startswith("pending-"), run.dir.name)
        # Nothing has been closed, nothing flushed by hand. This is the crash case.
        ok &= check("and the first record is already readable",
                    lines(run.dir / "game.jsonl")[0]["kind"] == "day_open")

        w.say("BLOCKED(at=(15,7))", "bad")
        ok &= check("every record lands as it happens",
                    len(lines(run.dir / "game.jsonl")) == 2)
        run.discard()
    return ok


def test_keeping_promotes_it_out_of_pending():
    print("keep")
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        tape = chat.Tape(run.chat_path)
        tape.write({"who": "you", "text": "hello"})
        tape.close()

        kept = run.keep()
        ok = check("renamed to the timestamp", kept.name == "20260904-101500", kept.name)
        ok &= check("nothing is left pending",
                    not list(Path(d).glob("pending-*")))
        ok &= check("both streams came with it",
                    (kept / "game.jsonl").exists() and (kept / "chat.jsonl").exists())
        ok &= check("and the chat is readable",
                    lines(kept / "chat.jsonl")[0]["text"] == "hello")
    return ok


def test_discarding_leaves_nothing_behind():
    print("discard")
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        chat.Tape(run.chat_path).write({"who": "you", "text": "hello"})
        run.discard()
        ok = check("the directory is gone", not run.dir.exists())
        ok &= check("and so is everything in it", not list(Path(d).iterdir()))
    return ok


def test_two_runs_in_the_same_second_do_not_collide():
    print("same stamp twice")
    with tempfile.TemporaryDirectory() as d:
        a, _ = rig(d)
        a.keep()
        b = logs.Run(Path(d), stamp="20260904-101500")
        kept = b.keep()
        ok = check("the second gets its own directory",
                   kept.name != "20260904-101500", kept.name)
        ok &= check("and the first is untouched",
                    (Path(d) / "20260904-101500").is_dir())
    return ok


def test_the_game_log_carries_what_the_chat_log_cannot():
    print("game.jsonl")
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        nav.goto(w, 15, 7)          # driven at rock, so there is something to record
        w.next_day()
        rows = lines(run.dir / "game.jsonl")
        kinds = [r["kind"] for r in rows]
        ok = check("the sol opening and closing are both there",
                   kinds.count("day_open") == 2 and kinds.count("day_close") == 1,
                   str(kinds))
        ok &= check("every row is stamped with its sol",
                    all("day" in r and "t" in r for r in rows))

        drive = next(r for r in rows if r["kind"] == "nav")
        # The gap between what the plan promised and what the drive cost is the direct
        # read on what unmapped ground costs. It is only in this file.
        ok &= check("a drive records plan against outcome",
                    {"start", "goal", "planned", "steps", "code"} <= set(drive),
                    str(drive))
        ok &= check("and it was surprised by rock",
                    drive["code"] == "BLOCKED" and drive["steps"] < drive["planned"],
                    str(drive))
        ok &= check("the sol that closed reports what it spent",
                    next(r for r in rows if r["kind"] == "day_close")["steps"] > 0)
        run.discard()
    return ok


def test_a_settled_run_stops_recording():
    print("after the answer")
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        before = len(lines(run.dir / "game.jsonl"))
        kept = run.keep()
        w.say("this happened after the file was closed")
        ok = check("a late record is dropped, not crashed on",
                   len(lines(kept / "game.jsonl")) == before)
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_run_is_on_disk_before_anyone_is_asked(),
               test_keeping_promotes_it_out_of_pending(),
               test_discarding_leaves_nothing_behind(),
               test_two_runs_in_the_same_second_do_not_collide(),
               test_the_game_log_carries_what_the_chat_log_cannot(),
               test_a_settled_run_stops_recording()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
