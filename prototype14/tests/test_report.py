"""The mission report: the world's record first, her own words after it."""


import report
import settings
import skills
from world import World


def played():
    """Sol 1: the interest at (8,20) examined, then home. Sol 2: out on the plain."""
    w = World()
    skills.call(w, "goto", {"x": 8, "y": 19})
    w.execute(w.adjacent_work())
    skills.call(w, "goto", {"x": 15, "y": 15})
    skills.call(w, "count", {"kind": "rock"})
    w.reports.append({"sol": 1, "text": "Found nothing of note today."})
    w.next_day()
    skills.call(w, "goto", {"x": 20, "y": 8})
    # The note she might write, wrong on purpose: the report must not take its word.
    w.notes.memory = {"findings": "No objectives were found during the expedition."}
    return w


def test_the_facts_come_from_the_world():
    w = played()
    text = report.build(w)
    done = w.finished[0]
    assert (f"- sol 1: interest at ({done['at'][0]},{done['at'][1]}), {done['cost']} "
               f"steps -- {done['text']}" in text), "the examined interest is there, with its sol and what it was"
    left = text.split("## Work still")[1]
    assert (all(f"({i.cell[0]},{i.cell[1]})" in left for i in w.interests)
                and "(not found)" in left), "the rest are listed as still out there, with whether she found them"
    seen = len(w.here.seen)
    assert f"{seen} of {w.here.w * w.here.h} cells seen" in text, "the map is counted"
    assert "Largest seen: 5 cells, middle (14,8)" in text, "and the largest formation seen, with its size"
    assert "| 1 |" in text and "beside the pad" in text and "| 2 |" in text, "each sol's ending is a row: home on sol 1, out on sol 2"


def test_her_note_is_hers():
    text = report.build(played())
    note = text.split("## The planner's memory")[1]
    assert ("not checked against the record" in note
               and "No objectives were found" in note), "her memory is under its own heading, marked unchecked"
    assert ("**Sol 1**" in text.split("## Her reports at dusk")[1]
                and "Found nothing of note today." in text), "her dusk report is under its own, in her words"
    assert "No objectives were found" not in text.split("## The planner's memory")[0], "and only there: the record above says otherwise"


def test_writing_it_changes_nothing():
    """`count` hands out formation ids and reports merges, and replay compares what it
    says. A report that assigned ids would change her next count."""
    w = played()
    sv = w.survey
    before = (dict(sv.owner), dict(sv.size), list(sv.merges), sv._next)
    report.build(w)
    assert before == (dict(sv.owner), dict(sv.size), list(sv.merges), sv._next), "the survey is untouched"


def test_a_lost_rover_says_so():
    w = World()
    w.pos, w.battery, w.day_over = (3, 3), 2, True
    assert "was lost on sol 1" in report.build(w), "the ending says lost"
