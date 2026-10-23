"""The scorecard, against a run written by hand, so every number is known in advance.

    .venv/bin/python game/test_score.py
"""

import json
import sys
import tempfile
from pathlib import Path

import score


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'   ' + detail if detail else ''}")
    return bool(cond)


GAME = [
    {"kind": "settings", "sol": 1, "values": {"DAY_SECONDS": 600}},
    {"kind": "day_open", "day": 1, "battery": 500},
    {"kind": "placed", "day": 1, "at": [3, 17], "priority": "high", "cost": 30},
    {"kind": "todo", "day": 1, "n": 1, "text": "execute high priority objective at (3, 17)"},
    {"kind": "todo", "day": 1, "n": 2, "text": "explore the east"},
    {"kind": "nav", "day": 1, "new": 40},
    {"kind": "nav", "day": 1, "new": None},
    {"kind": "objective", "day": 1, "at": [3, 17], "cost": 30, "priority": "high"},
    {"kind": "strike", "day": 1, "n": 1},
    {"kind": "interest_found", "day": 1, "at": [6, 4]},
    {"kind": "interest", "day": 1, "at": [6, 4], "cost": 20,
     "text": "a ripple pattern pressed into the rock"},
    {"kind": "radio", "day": 1, "text": "found ripples", "cost": 5},
    {"kind": "remember", "day": 1, "name": "plan", "text": "east next"},
    {"kind": "remember", "day": 1, "name": "find", "text": "Ripple pattern in the rock."},
    {"kind": "sol_closed", "day": 1, "why": "she called end"},
    {"kind": "report", "day": 1, "text": "Examined a ripple pattern in the rock."},
    {"kind": "order", "day": 1, "n": 1, "text": "go east"},
    {"kind": "day_close", "day": 1, "battery": 300, "stranded": False},
    {"kind": "day_open", "day": 2, "battery": 500},
    {"kind": "forget", "day": 2, "name": "plan"},
    {"kind": "sol_closed", "day": 2, "why": "the clock ran out"},
    {"kind": "quit", "day": 2},
]
CHAT = [
    {"day": 1, "who": "call", "name": "goto", "ran": True, "phase": "day", "clock": 500.0},
    {"day": 1, "who": "call", "name": "goto", "ran": True, "phase": "day", "clock": 480.4},
    {"day": 1, "who": "note", "text": "her reply went over the radio", "drain": 5},
    {"day": 1, "who": "call", "name": "remember", "ran": True, "phase": "dusk",
     "clock": 470.0},
    {"day": 1, "who": "call", "name": "goto", "ran": False},
    {"day": 2, "who": "call", "name": "goto", "ran": True, "phase": "day", "clock": 0.0},
]
NIGHT = {"history": [{"day": 1, "battery": 300, "docked": True},
                     {"day": 2, "battery": 40, "docked": False}]}


def test_a_run_written_by_hand_scores_as_written():
    print("the scorecard")
    with tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "game.jsonl").write_text("\n".join(json.dumps(r) for r in GAME))
        (run / "chat.jsonl").write_text("\n".join(json.dumps(r) for r in CHAT))
        (run / "night.json").write_text(json.dumps(NIGHT))
        scored = score.score(run)
        one, two = scored["sols"]
        ok = check("battery used is what it woke with, less what it ended on",
                   one["steps_used"] == 200 and two["steps_used"] == 460,
                   f"{one['steps_used']} {two['steps_used']}")
        ok &= check("a sol with no close takes its ending from the night",
                    two["battery_left"] == 40 and two["home"] == "stranded")
        ok &= check("the radio: the call and her reply on the line", one["radio"] == 10)
        ok &= check("the day used is read off the last daytime call, not dusk's",
                    one["day_used"] == 120 and two["day_used"] == 600, str(one["day_used"]))
        ok &= check("cells mapped, objectives done, interests found and examined",
                    (one["mapped"], one["objectives"], one["found"], one["examined"])
                    == (40, 1, 1, 1))
        ok &= check("a list item naming an open objective's cell is a copy",
                    one["todos"] == 2 and one["copies"] == 1 and one["struck"] == 1)
        ok &= check("what she found is in her report and her memory",
                    one["report_names_finds"] == 1 and one["remembered_finds"] == 1)
        ok &= check("memory at each night: two entries, then one after a forget",
                    one["memory"] == 2 and two["memory"] == 1 and two["forgotten"] == 1)
        ok &= check("refused calls are counted", one["refused"] == 1)
        ok &= check("and why each day ended", (one["ended"], two["ended"])
                    == ("she called end", "the clock ran out"))
        ok &= check("orders are listed by the sol they stood on, never scored",
                    scored["orders"] == {1: [], 2: ["go east"]}, str(scored["orders"]))
        t = score.totals(scored)
        ok &= check("totals add the sols up", t["battery used, mean"] == 330
                    and t["memory writes / forgets"] == "2 / 1"
                    and t["stranded sols"] == 1, str(t))
    return ok


if __name__ == "__main__":
    results = [test_a_run_written_by_hand_scores_as_written()]
    print(f"\n{sum(results)}/{len(results)} groups passed")
    sys.exit(0 if all(results) else 1)
