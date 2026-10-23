"""The mission report, written from the world's record. Her note goes under it as hers.

    runs/<stamp>/report.md     rewritten every nightfall, and once more at the end

**Facts are the world's to keep, not hers.** Two unattended runs ended on a report that
said no objective had ever been found, after she had finished all three. Her note was
the report then, and her note is a paragraph she rewrites from memory every evening --
one bad rewrite and a fact is gone for good. Asking her more nicely at dusk would only
make that less likely. So everything checkable here is read off the world: what was
finished and on which sol, what is still out there, how much is mapped, the largest
formation seen, where each sol ended and on what charge. Her note follows, labelled as
hers and not checked against any of it, because what she judged and why is the part
only she can say.

Read-only. `Survey.rock` assigns ids and records merges, and `count` reports both, so
calling it here would change what she is told next -- and replay compares every result.
The formations are found again with `components` and named off ids already assigned.

No pygame in here, so the tests can read it.
"""

import settings as S
from world import centre_of, components


def _c(cell):
    return f"({cell[0]},{cell[1]})"


def _formations(world):
    """Revealed rock as (name, cells), named by the ids `count` has already handed out."""
    a, owner = world.here, world.survey.owner
    out = []
    for cells in components(a.w, a.h,
                            lambda x, y: (x, y) in a.seen and a.at(x, y) == "#"):
        ids = sorted({owner[c] for c in cells if c in owner})
        out.append((f"R{ids[0]}" if ids else None, cells))
    return out


def _ending(world):
    if world.day_over and world.lost:
        return (f"The rover was lost on sol {world.day}: too little charge to reach the "
                f"pad, and nothing else recharges it.")
    if world.day_over and S.MISSION_SOLS and world.day >= S.MISSION_SOLS:
        return f"The mission ran its {S.MISSION_SOLS} sols."
    if world.day_over:
        return f"Written at the end of sol {world.day}."
    return f"Written partway through sol {world.day}, which counts as played."


def build(world):
    """The report, as Markdown."""
    a = world.here
    seen = sum(1 for y in range(a.h) for x in range(a.w) if (x, y) in a.seen)
    lines = ["# Mission report", "", _ending(world), ""]

    lines += ["## Work finished", ""]
    lines += [f"- sol {f['sol']}: {f['priority']} priority objective at {_c(f['at'])}, "
              f"{f['cost']} steps of work" if f["kind"] == "objective" else
              f"- sol {f['sol']}: interest at {_c(f['at'])}, {f['cost']} steps -- "
              f"{f['text']}" for f in world.finished] or ["- none"]
    lines += ["", "## Work still out there", ""]
    lines += ([f"- {o.priority} priority objective at {_c(o.cell)}, {o.cost} steps of work"
               for o in world.objectives]
              + [f"- interest at {_c(i.cell)}, {i.cost} steps -- {i.text}"
                 + ("" if i.found else " (not found)") for i in world.interests]
              or ["- none"])

    rock = _formations(world)
    lines += ["", "## The map", "",
              f"- {seen} of {a.w * a.h} cells seen.",
              f"- {len(rock)} rock formations seen."]
    if rock:
        biggest = max(len(cells) for _, cells in rock)
        for name, cells in rock:
            if len(cells) == biggest:
                called = (f", which `count` calls {name}" if name else
                          ", not yet named by `count`")
                lines.append(f"- Largest seen: {len(cells)} cells, middle "
                             f"{_c(centre_of(cells))}{called}. Seen size: rock still "
                             f"under fog is not counted.")

    lines += ["", "## Sol by sol", "",
              "| sol | steps | ended at | home | battery after |",
              "|---|---|---|---|---|"]
    for h in world.history + [world._sol_record()]:
        if "at" not in h:            # a night saved before sols kept these
            lines.append(f"| {h['day']} | {h['steps']} | | | |")
            continue
        lines.append(f"| {h['day']} | {h['steps']} | {_c(h['at'])} | "
                     f"{'beside the pad' if h['docked'] else 'stranded'} | "
                     f"{h['battery']} of {S.BATTERY} |")

    lines += ["", "## Her reports at dusk", "",
              "In her words, and not checked against the record above.", ""]
    for r in world.reports:
        lines += [f"**Sol {r['sol']}**", ""] + [f"> {line}" for line in
                                               r["text"].splitlines()] + [""]
    if not world.reports:
        lines.append("> (none)")

    lines += ["", "## The planner's memory", "",
              "Written by the planner and not checked against the record above.", ""]
    for name, text in world.notes.memory.items():
        lines += [f"**{name}**", ""] + [f"> {line}" for line in text.splitlines()] + [""]
    if not world.notes.memory:
        lines.append("> (none)")
    if world.notes.orders:
        lines += ["", "## Standing orders at the end", ""]
        lines += [f"{i}. {t}" for i, t in enumerate(world.notes.orders, 1)]
    return "\n".join(lines) + "\n"
