"""The run directory, and the promise that a crash never costs a run.


The feature is "ask at quit whether to keep the logs". The way *not* to build it is to
buffer everything in memory until the answer arrives, because then a crash loses the
run and says nothing. So the whole file is really one assertion:
`test_a_run_is_on_disk_before_anyone_is_asked`.
"""

import json
import tempfile
from pathlib import Path

import chat
import logs
import nav
import settings
from world import World


def rig(root):
    run = logs.Run(Path(root), stamp="20260904-101500")
    w = World(recorder=run.record)
    return run, w


def lines(path):
    return [json.loads(li) for li in path.read_text().splitlines() if li.strip()]


def test_a_run_is_on_disk_before_anyone_is_asked():
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        assert run.dir.is_dir(), "a pending directory exists straight away"
        assert run.dir.name.startswith("pending-"), "named so it is obviously unanswered"
        # Nothing has been closed, nothing flushed by hand. This is the crash case.
        assert lines(run.dir / "game.jsonl")[0]["kind"] == "day_open", "and the first record is already readable"

        w.say("BLOCKED(at=(14,9))", "bad")
        assert len(lines(run.dir / "game.jsonl")) == 2, "every record lands as it happens"
        run.discard()


def test_keeping_promotes_it_out_of_pending():
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        tape = chat.Tape(run.chat_path)
        tape.write({"who": "you", "text": "hello"})
        tape.close()

        kept = run.keep()
        assert kept.name == "20260904-101500", "renamed to the timestamp"
        assert not list(Path(d).glob("pending-*")), "nothing is left pending"
        assert (kept / "game.jsonl").exists() and (kept / "chat.jsonl").exists(), "both streams came with it"
        assert lines(kept / "chat.jsonl")[0]["text"] == "hello", "and the chat is readable"


def test_discarding_leaves_nothing_behind():
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        chat.Tape(run.chat_path).write({"who": "you", "text": "hello"})
        run.discard()
        assert not run.dir.exists(), "the directory is gone"
        assert not list(Path(d).iterdir()), "and so is everything in it"


def test_two_runs_in_the_same_second_do_not_collide():
    with tempfile.TemporaryDirectory() as d:
        a, _ = rig(d)
        a.keep()
        b = logs.Run(Path(d), stamp="20260904-101500")
        kept = b.keep()
        assert kept.name != "20260904-101500", "the second gets its own directory"
        assert (Path(d) / "20260904-101500").is_dir(), "and the first is untouched"


def test_the_game_log_carries_what_the_chat_log_cannot():
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        nav.goto(w, 14, 9)  # driven at rock, so there is something to record
        w.next_day()
        rows = lines(run.dir / "game.jsonl")
        kinds = [r["kind"] for r in rows]
        assert kinds.count("day_open") == 2 and kinds.count("day_close") == 1, "the sol opening and closing are both there"
        assert all("day" in r and "t" in r for r in rows), "every row is stamped with its sol"

        drive = next(r for r in rows if r["kind"] == "nav")
        # The gap between what the plan promised and what the drive cost is the direct
        # read on what unmapped ground costs. It is only in this file.
        assert {"start", "goal", "planned", "steps", "code"} <= set(drive), "a drive records plan against outcome"
        assert drive["code"] == "BLOCKED" and drive["steps"] < drive["planned"], "and it was surprised by rock"
        assert next(r for r in rows if r["kind"] == "day_close")["steps"] > 0, "the sol that closed reports what it spent"
        run.discard()


def test_a_settled_run_stops_recording():
    with tempfile.TemporaryDirectory() as d:
        run, w = rig(d)
        before = len(lines(run.dir / "game.jsonl"))
        kept = run.keep()
        w.say("this happened after the file was closed")
        assert len(lines(kept / "game.jsonl")) == before, "a late record is dropped, not crashed on"


def test_every_record_survives_a_real_recorder():
    """`World.record` stamps `day` itself, so a caller passing `day=` again raises --
    and only on a live run, because every test world has `recorder=None` and `record`
    is a no-op in all of them.

    That is exactly how `execute` shipped broken: eleven green suites, and the first
    console call after them was a TypeError. So this drives one world with a real
    recorder through every path that writes a line.
    """
    import config
    import skills
    settings.STORM_ON = True  # the storm records on spawn; that counts too
    rows = []
    try:
        config.use("50")
        w = World(recorder=lambda kind, **f: rows.append((kind, f)))
        w.here.reveal_all()
        w.place_objective((30, 30), "high", 20)
        w.place_interest((20, 20), "planted", 10)
        for target in ((30, 30), next(iter(w.here.interests))):
            x, y = target
            for cell in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
                if not w.here.blocked(*cell):
                    w.pos = cell
                    w._arrive()
                    break
            skills.call(w, "execute", {"why": "the whole point of the sol"})
        nav.goto(w, *config.SPAWN)
        nav.price(w, 5, 5)
        w.day_over = False
        w.next_day()
    finally:
        settings.STORM_ON = False
        config.use(config.DEFAULT_ARENA)

    kinds = {k for k, _ in rows}
    assert "objective" in kinds, "the objective was written down"
    for want in ("interest", "interest_found", "placed", "placed_interest", "nav",
                 "day_open", "day_close"):
        assert want in kinds, f"...and so was {want}"
    assert all("day" in f for _, f in rows), "every line carries the sol it happened on"


def test_a_run_with_no_window_says_so_in_its_name():
    with tempfile.TemporaryDirectory() as d:
        run = logs.Run(Path(d), stamp="20261013-120000", headless=True)
        assert run.dir.name == "pending-20261013-120000-headless", "pending under the headless name"
        kept = run.keep()
        assert kept.name == "20261013-120000-headless", "and kept under it"
        plain = logs.Run(Path(d), stamp="20261013-120001")
        assert plain.dir.name == "pending-20261013-120001", "a run with a window is not"
        plain.discard()
