"""Quit, come back, and wake on the next sol as though the night had passed.


The whole claim is one comparison: a world rebuilt from `carry()` must be the world
`next_day` would have produced, down to the view the model is sent.
"""

import pytest
import json
import tempfile
from pathlib import Path

import config as C
import logs
import replay
import settings as S
import sight
import skills
from world import World


@pytest.fixture(autouse=True)
def storm_on():
    S.STORM_ON = True


def played():
    """A sol with something in every store the night keeps."""
    w = World()
    skills.call(w, "goto", {"x": 8, "y": 19})
    o = w.adjacent_work()
    assert o and o.cell == (8, 20), f"the rover is not beside the interest: {w.pos}"
    w.execute(o)
    for x, y in ((20, 8), (25, 25)):
        skills.call(w, "goto", {"x": x, "y": y})
    skills.call(w, "count", {"kind": "rock"})
    w.here.reveal(21, 22, r=1)
    assert w.place_objective((21, 22), "high", 40)[0]
    assert w.place_interest((3, 25), "a find planted for the test", 20)[0]
    w.reports.append({"sol": 1, "text": "Examined one interest."})
    w.toggle_mark((3, 3))
    w.notes.add("an item the night wipes")
    w.notes.memory = {"the C": "it opens east", "plan": "- north first\n- then the C"}
    w.notes.order("finish objective 1")
    return w


def roundtrip(w):
    return json.loads(json.dumps(w.carry()))


def same(a, b):
    """Every piece of state the next sol can see."""
    return {
        "view": sight.view(a) == sight.view(b),
        "day": a.day == b.day,
        "pos": a.pos == b.pos,
        "seen": a.here.seen == b.here.seen,
        "visited": a.here.visited == b.here.visited,
        "marks": a.here.marks == b.here.marks,
        "objectives": {c: (o.glyph, o.priority, o.cost, o.auto)
                       for c, o in a.here.objectives.items()}
                      == {c: (o.glyph, o.priority, o.cost, o.auto)
                          for c, o in b.here.objectives.items()},
        "interests": {c: (i.text, i.cost, i.found) for c, i in a.here.interests.items()}
                     == {c: (i.text, i.cost, i.found) for c, i in b.here.interests.items()},
        "reports": a.reports == b.reports,
        "survey": (a.survey.owner, a.survey.size, a.survey._next)
                  == (b.survey.owner, b.survey.size, b.survey._next),
        "storm": a.here.storm_cells == b.here.storm_cells,
        "notes": (a.notes.memory, a.notes.orders, a.notes.todos)
                 == (b.notes.memory, b.notes.orders, b.notes.todos),
        "history": a.history == b.history,
        "battery": (a.stranded, a.battery) == (b.stranded, b.battery),
        "finished": a.finished == b.finished,
    }


def test_a_resumed_world_is_the_one_that_slept():
    w = played()
    kept = roundtrip(w)
    slept = w
    slept.next_day()
    woke = World(carried=kept)
    diff = [k for k, v in same(slept, woke).items() if not v]
    assert not diff, "identical, view included"
    assert woke.day == 2, "on the next sol"
    assert (8, 20) not in woke.here.interests, "the examined interest stays examined"
    assert (21, 22) in woke.here.objectives, "the placed objective is still there"
    assert (3, 25) in woke.here.interests and not woke.here.interests[(3, 25)].found, "and the planted interest, still hidden"
    assert woke.notes.todos == [], "the list did not survive"
    assert woke.stranded and woke.pos != C.SPAWN, "it ended the sol out on the plain, so it wakes there, stranded"
    assert woke.battery == kept["battery"] < S.BATTERY, "on the charge it had left, not a full one"

    # Twice over: a resumed sol carries again like any other.
    skills.call(woke, "goto", {"x": 2, "y": 2})
    skills.call(slept, "goto", {"x": 2, "y": 2})
    again = World(carried=roundtrip(woke))
    slept.next_day()
    diff = [k for k, v in same(slept, again).items() if not v]
    assert not diff and again.day == 3, "and a second night the same way"


def test_a_night_saved_by_10c_is_refused():
    kept = roundtrip(played())
    kept["version"] = 1
    assert _raises(lambda: World(carried=kept)), "a night saved by 10c, whose work was all objectives, is refused"


def test_the_wrong_arena_is_refused():
    kept = roundtrip(World())
    C.use("50")
    try:
        World(carried=kept)
        refused = False
    except ValueError:
        refused = True
    finally:
        C.use(C.DEFAULT_ARENA)
    assert refused, "a 30 resumed on the 50 is an error, not a scrambled map"


def test_a_replay_of_a_resumed_run_starts_where_it_did():
    with tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "start.json").write_text(json.dumps(roundtrip(played())))
        (run / "chat.jsonl").write_text("")
        (run / "game.jsonl").write_text(
            json.dumps({"kind": "settings", "sol": 2, "values": {"BATTERY": 140}}))
        script = replay.Script(run)
        keep = S.BATTERY
        try:
            assert script.start["day"] == 1, "it knows the state it began from"
            assert script.first_sol == 2, "and its first sol"
            script.use_settings(script.first_sol)
            assert S.BATTERY == 140, "whose settings it takes"
        finally:
            S.BATTERY = keep


def test_the_night_is_written_down():
    with tempfile.TemporaryDirectory() as d:
        run = logs.Run(Path(d), stamp="20261011-120000")
        w = played()
        run.save_night(w)
        assert (run.dir / "night.json").exists(), "night.json is written while the run is still pending"
        kept = run.keep()
        back = logs.load_night(kept)
        assert back["memory"][0] == ["the C", "it opens east"], "and read back from the kept run"
        assert _raises(lambda: logs.load_night(Path(d))), "a directory with no night says so"


def test_a_list_made_at_night_survives_a_resume():
    """Quit at night and the list she made is tomorrow's, resumed or not. Quit any
    earlier and it is today's, and goes with the sol -- `played()` is that case."""
    w = played()
    w.phase = "night"
    w.evening()
    w.notes.add("explore north")
    kept = roundtrip(w)
    w.next_day()
    woke = World(carried=kept)
    diff = [k for k, v in same(w, woke).items() if not v]
    assert not diff, "identical, view included"
    assert woke.notes.todos == [["explore north", False]], "the list made at night came with it"
    older = dict(kept)
    del older["todos"]
    assert World(carried=older).notes.todos == [], "a night kept before the list crossed it wakes with none"


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False
