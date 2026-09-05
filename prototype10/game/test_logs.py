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

# Clear skies unless a suite asks otherwise. The weather is real and shipped on,
# but it is a scenario, not terrain -- letting one drift across an arena would make
# every route assertion here depend on STORM_RADIUS. `test_hazards.py` turns it on.
S.STORM_ON = False


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

        w.say("BLOCKED(at=(14,9))", "bad")
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
        nav.goto(w, 14, 9)          # driven at rock, so there is something to record
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


def test_every_record_survives_a_real_recorder():
    """`World.record` stamps `day` itself, so a caller passing `day=` again raises --
    and only on a live run, because every test world has `recorder=None` and `record`
    is a no-op in all of them.

    That is exactly how `execute` shipped broken: eleven green suites, and the first
    console call after them was a TypeError. So this drives one world with a real
    recorder through every path that writes a line.
    """
    print("record() against something that is listening")
    import config as C
    import skills
    S.STORM_ON = True                   # the storm records on spawn; that counts too
    rows = []
    try:
        C.use("50")
        w = World(recorder=lambda kind, **f: rows.append((kind, f)))
        w.here.reveal_all()
        o = next(iter(w.here.objectives.values()))
        x, y = o.cell
        for cell in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
            if not w.here.blocked(*cell):
                w.pos = cell
                break
        skills.call(w, "execute", {"why": "the whole point of the sol"})
        nav.goto(w, *C.SPAWN)
        nav.distance(w, 5, 5)
        w.day_over = False
        w.next_day()
    finally:
        S.STORM_ON = False
        C.use(C.DEFAULT_ARENA)

    kinds = {k for k, _ in rows}
    ok = check("the objective was written down", "objective" in kinds, str(sorted(kinds)))
    for want in ("nav", "day_open", "day_close"):
        ok &= check(f"...and so was {want}", want in kinds)
    ok &= check("every line carries the sol it happened on",
                all("day" in f for _, f in rows))
    return ok


if __name__ == "__main__":
    S.DAY_MODE = "gemma"
    results = [test_a_run_is_on_disk_before_anyone_is_asked(),
               test_keeping_promotes_it_out_of_pending(),
               test_discarding_leaves_nothing_behind(),
               test_two_runs_in_the_same_second_do_not_collide(),
               test_the_game_log_carries_what_the_chat_log_cannot(),
               test_a_settled_run_stops_recording(),
               test_every_record_survives_a_real_recorder()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
