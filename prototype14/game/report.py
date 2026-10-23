"""The mission report, runs/<stamp>/report.md, rewritten every nightfall.
Every fact is read off the world, never from her notes; her dusk reports go under it as hers.
Read-only: it must not call `Survey.rock`, which hands out ids that replay checks.
"""

import settings
from world import centre_of, components


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def _formations(world):
    """Seen rock as (name, cells), named by the ids `count` has already handed out."""
    area = world.here
    owner = world.survey.owner
    out = []
    for cells in components(area.w, area.h, area.seen_rock()):
        ids = sorted({owner[c] for c in cells if c in owner})
        if ids:
            out.append((f"R{ids[0]}", cells))
        else:
            out.append((None, cells))
    return out


def _ending(world):
    if world.day_over and world.lost:
        return (f"The rover was lost on sol {world.day}: too little charge to reach the "
                f"pad, and nothing else recharges it.")
    if world.day_over and settings.MISSION_SOLS and world.day >= settings.MISSION_SOLS:
        return f"The mission ran its {settings.MISSION_SOLS} sols."
    if world.day_over:
        return f"Written at the end of sol {world.day}."
    return f"Written partway through sol {world.day}, which counts as played."


def build(world):
    lines = ["# Mission report", "", _ending(world), ""]
    lines += _work_lines(world)
    lines += _map_lines(world)
    lines += _sol_lines(world)
    lines += _her_lines(world)
    return "\n".join(lines) + "\n"


def _work_lines(world):
    lines = ["## Work finished", ""]
    for f in world.finished:
        if f["kind"] == "objective":
            lines.append(f"- sol {f['sol']}: {f['priority']} priority objective at "
                         f"{_c(f['at'])}, {f['cost']} steps of work")
        else:
            lines.append(f"- sol {f['sol']}: interest at {_c(f['at'])}, {f['cost']} steps -- "
                         f"{f['text']}")
    if not world.finished:
        lines.append("- none")
    lines += ["", "## Work still out there", ""]
    for o in world.objectives:
        lines.append(f"- {o.priority} priority objective at {_c(o.cell)}, {o.cost} steps of work")
    for i in world.interests:
        line = f"- interest at {_c(i.cell)}, {i.cost} steps -- {i.text}"
        if not i.found:
            line += " (not found)"
        lines.append(line)
    if not world.objectives and not world.interests:
        lines.append("- none")
    return lines


def _map_lines(world):
    area = world.here
    seen = sum(1 for cell in area.cells() if cell in area.seen)
    rock = _formations(world)
    lines = ["", "## The map", "",
             f"- {seen} of {area.w * area.h} cells seen.",
             f"- {len(rock)} rock formations seen."]
    if not rock:
        return lines
    biggest = max(len(cells) for _, cells in rock)
    for name, cells in rock:
        if len(cells) != biggest:
            continue
        if name:
            called = f", which `count` calls {name}"
        else:
            called = ", not yet named by `count`"
        lines.append(f"- Largest seen: {len(cells)} cells, middle {_c(centre_of(cells))}"
                     f"{called}. Seen size: rock still under fog is not counted.")
    return lines


def _sol_lines(world):
    lines = ["", "## Sol by sol", "",
             "| sol | steps | ended at | home | battery after |",
             "|---|---|---|---|---|"]
    for h in world.history + [world._sol_record()]:
        if h["docked"]:
            home = "beside the pad"
        else:
            home = "stranded"
        lines.append(f"| {h['day']} | {h['steps']} | {_c(h['at'])} | {home} | "
                     f"{h['battery']} of {settings.BATTERY} |")
    return lines


def _her_lines(world):
    """Her dusk reports, her memory and the orders, in her words, unchecked."""
    lines = ["", "## Her reports at dusk", "",
             "In her words, and not checked against the record above.", ""]
    for r in world.reports:
        lines += [f"**Sol {r['sol']}**", ""]
        for line in r["text"].splitlines():
            lines.append(f"> {line}")
        lines.append("")
    if not world.reports:
        lines.append("> (none)")

    lines += ["", "## The planner's memory", "",
              "Written by the planner and not checked against the record above.", ""]
    for name, text in world.notes.memory.items():
        lines += [f"**{name}**", ""]
        for line in text.splitlines():
            lines.append(f"> {line}")
        lines.append("")
    if not world.notes.memory:
        lines.append("> (none)")
    if world.notes.orders:
        lines += ["", "## Standing orders at the end", ""]
        for i, text in enumerate(world.notes.orders, 1):
            lines.append(f"{i}. {text}")
    return lines
