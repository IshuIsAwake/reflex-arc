"""Scores kept runs from their own logs: a row per sol, then the totals, side by side
for two or more runs. Usage: .venv/bin/python game/score.py runs/<stamp> [runs/<stamp> ...]"""

import json
import re
import sys
from pathlib import Path

import logs


def _words(text):
    return {word for word in re.findall(r"[a-z]+", text.lower()) if len(word) > 3}


def _mentions(text, said):
    """Whether `said` carries at least half of `text`'s longer words."""
    want = _words(text)
    return bool(want) and len(want & _words(said)) * 2 >= len(want)


def _cell(at):
    return f"({at[0]},{at[1]})"


def new_sol(n):
    return {"sol": n, "radio": 0, "battery_left": None, "day_used": None, "mapped": 0,
            "objectives": 0, "found": 0, "examined": [], "todos": 0, "struck": 0,
            "copies": 0, "written": 0, "forgotten": 0, "memory": 0,
            "report_names_finds": None, "remembered_finds": None, "ended": "", "home": ""}


def score(run):
    """One run as {"sols": [row per sol], "orders": {sol: [standing orders]}}."""
    start = {}
    if (run / "start.json").exists():
        start = json.loads((run / "start.json").read_text())
    tally = {
        "sols": {},  # sol -> its row
        "standing": {},  # sol -> the orders standing when it opened
        "woke": {},  # sol -> the battery it woke on
        "day_seconds": 600,
        "memory": dict(start.get("memory") or []),
        "orders": list(start.get("orders") or []),
        "objectives": set(),  # open objective cells, as "(x,y)"
    }
    for r in logs.read_rows(run / "game.jsonl"):
        count_game_row(tally, r)
    count_chat(tally, logs.read_rows(run / "chat.jsonl"))
    count_night(tally, run / "night.json")
    sols = tally["sols"]
    for s in sols.values():
        finish_sol(s, tally)
    return {"sols": [sols[k] for k in sorted(sols)], "orders": tally["standing"],
            "day_seconds": tally["day_seconds"]}


def count_game_row(tally, r):
    """One row of game.jsonl, added to its sol's row."""
    kind = r.get("kind")
    n = r.get("day", r.get("sol"))
    if kind == "settings":
        tally["day_seconds"] = r["values"].get("DAY_SECONDS", tally["day_seconds"])
        tally["standing"].setdefault(r["sol"], None)
        return
    if n is None:
        return
    if n not in tally["sols"]:
        tally["sols"][n] = new_sol(n)
    s = tally["sols"][n]
    if kind == "day_open":
        tally["standing"][n] = list(tally["orders"])
        tally["woke"][n] = r.get("battery")
    elif kind == "nav" and r.get("new"):
        s["mapped"] += r["new"]
    elif kind == "placed":
        tally["objectives"].add(_cell(r["at"]))
    elif kind == "objective":
        s["objectives"] += 1
        tally["objectives"].discard(_cell(r["at"]))
    elif kind == "interest_found":
        s["found"] += 1
    elif kind == "interest":
        s["examined"].append(r["text"])
    elif kind == "radio":
        s["radio"] += r.get("cost", 0)
    elif kind == "todo":
        s["todos"] += 1
        # An item that names an open objective's cell copies work the view already shows.
        for cell in tally["objectives"]:
            if cell in r["text"].replace(" ", ""):
                s["copies"] += 1
                break
    elif kind == "strike":
        s["struck"] += 1
    elif kind == "remember":
        s["written"] += 1
        tally["memory"][r["name"]] = r["text"]
    elif kind == "forget":
        s["forgotten"] += 1
        kept = {}
        for name, text in tally["memory"].items():
            if name.lower() != r["name"].lower():
                kept[name] = text
        tally["memory"] = kept
    elif kind == "order":
        tally["orders"].append(r["text"])
    elif kind == "retract":
        kept = []
        for i, order in enumerate(tally["orders"], 1):
            if i != r.get("n"):
                kept.append(order)
        tally["orders"] = kept
    elif kind == "orders_cleared":
        tally["orders"] = []
    elif kind == "sol_closed":
        s["ended"] = r["why"]
    elif kind == "report":
        s["report"] = r["text"]
    elif kind == "day_close":
        s["battery_left"] = r["battery"]
        s["home"] = "stranded" if r.get("stranded") else "home"
        s["memory_at_close"] = dict(tally["memory"])
    elif kind == "quit":
        s["memory_at_close"] = s.get("memory_at_close") or dict(tally["memory"])


def count_chat(tally, rows):
    """The day's clock at each sol's last daytime call, her words on an open line, and the
    calls refused."""
    sols = tally["sols"]
    for r in rows:
        n = r.get("day")
        if n not in sols:
            continue
        if r.get("who") == "call" and r.get("ran") and r.get("phase") == "day":
            sols[n]["day_used"] = round(tally["day_seconds"] - (r.get("clock") or 0))
        sols[n]["radio"] += r.get("drain") or 0
        if r.get("who") == "call" and not r.get("ran"):
            sols[n]["refused"] = sols[n].get("refused", 0) + 1


def count_night(tally, night):
    """Where each sol ended and on what charge. The night has every sol's, the last included."""
    if not night.exists():
        return
    for h in json.loads(night.read_text()).get("history", []):
        s = tally["sols"].get(h.get("day"))
        if s is not None and s["battery_left"] is None and "battery" in h:
            s["battery_left"] = h["battery"]
            s["home"] = "home" if h.get("docked") else "stranded"


def finish_sol(s, tally):
    """The sol's totals, once every log has been read."""
    woke = tally["woke"].get(s["sol"])
    s["steps_used"] = None
    if woke is not None and s["battery_left"] is not None:
        s["steps_used"] = woke - s["battery_left"]
    memory = s.pop("memory_at_close", None) or tally["memory"]
    s["memory"] = len(memory)
    s["refused"] = s.get("refused", 0)
    if s["examined"]:
        s["report_names_finds"] = 0
        s["remembered_finds"] = 0
        for text in s["examined"]:
            if _mentions(text, s.get("report", "")):
                s["report_names_finds"] += 1
            if any(_mentions(text, entry) for entry in memory.values()):
                s["remembered_finds"] += 1
    s["examined"] = len(s["examined"])
    s.pop("report", None)


def totals(scored):
    rows = scored["sols"]
    used = [r for r in rows if r["steps_used"] is not None]
    return {
        "sols": len(rows),
        "battery used, mean": (round(sum(r["steps_used"] for r in used) / len(used))
                               if used else None),
        "day used, mean s": (round(sum(r["day_used"] or 0 for r in rows) / len(rows))
                             if rows else None),
        "cells mapped": sum(r["mapped"] for r in rows),
        "battery on the radio": sum(r["radio"] for r in rows),
        "objectives done": sum(r["objectives"] for r in rows),
        "interests found / examined": f"{sum(r['found'] for r in rows)} / "
                                      f"{sum(r['examined'] for r in rows)}",
        "list items / copying an objective": f"{sum(r['todos'] for r in rows)} / "
                                             f"{sum(r['copies'] for r in rows)}",
        "memory entries at the end": rows[-1]["memory"] if rows else 0,
        "memory writes / forgets": f"{sum(r['written'] for r in rows)} / "
                                   f"{sum(r['forgotten'] for r in rows)}",
        "refused calls": sum(r["refused"] for r in rows),
        "stranded sols": sum(r["home"] == "stranded" for r in rows),
    }


COLUMNS = [("sol", "sol"), ("battery used", "steps_used"), ("left", "battery_left"),
           ("radio", "radio"), ("day s", "day_used"), ("mapped", "mapped"), ("objectives", "objectives"),
           ("found", "found"), ("examined", "examined"), ("in report", "report_names_finds"),
           ("in memory", "remembered_finds"), ("list", "todos"), ("copies", "copies"),
           ("struck", "struck"), ("memory", "memory"), ("+", "written"), ("-", "forgotten"),
           ("refused", "refused"), ("ended", "ended"), ("night", "home")]


def table(scored):
    out = ["| " + " | ".join(h for h, _ in COLUMNS) + " |",
           "|" + "---|" * len(COLUMNS)]
    for r in scored["sols"]:
        out.append("| " + " | ".join("" if r.get(k) is None else str(r.get(k))
                                     for _, k in COLUMNS) + " |")
    return out


def main(paths):
    runs = [Path(p) for p in paths]
    every = []
    for run in runs:
        scored = score(run)
        every.append((run, scored, totals(scored)))
        print(f"## {run.name}\n")
        print("\n".join(table(scored)))
        print()
        for k, v in every[-1][2].items():
            print(f"- {k}: {v}")
        print("\nOrders standing each sol, to judge against the numbers above:")
        for n, standing in sorted(scored["orders"].items()):
            for i, text in enumerate(standing or [], 1):
                print(f"- sol {n}, order {i}: {text}")
            if not standing:
                print(f"- sol {n}: none")
        print()
    if len(every) > 1:
        keys = list(every[0][2])
        print("## Side by side\n")
        print("| | " + " | ".join(r.name for r, _, _ in every) + " |")
        print("|---|" + "---|" * len(every))
        for k in keys:
            print(f"| {k} | " + " | ".join(str(t[k]) for _, _, t in every) + " |")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
