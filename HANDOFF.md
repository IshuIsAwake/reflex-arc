# HANDOFF

**Carries forward only the context the next conversation actually needs.** Not a history, not
a changelog. Rules for maintaining this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

Hollow Knight played autonomously by a language model issuing goals to frozen, learned control
policies. The model has knowledge and no hands; the policies have hands and no knowledge. Not a
paper — a from-scratch build prioritising learning and explainability.

## Current phase

**Scope, since 2026-08-20.** Read [`README.md`](README.md) first — it now holds the idea *and*
the current plan, including the dates, the mod-layer gauge, the team shape and what is out of
scope for this window.

**SIH is not the goal.** It is development time with a deadline, plus a cheap read on how the idea
lands with outsiders. What is optimised is the state of the project at the end of the window, not
a placing. Do not plan as though selection matters.

## What to read

- [`README.md`](README.md) — **the idea and the current plan. Start here.**
- [`docs/ideas.md`](docs/ideas.md) — the full idea, vision then technicalities.
- [`docs/rover-expedition.md`](docs/rover-expedition.md) — the second implementation.
- [`docs/02-critique-response.md`](docs/02-critique-response.md) — prior art and novelty. Only
  when the question is "has this been done" or "is this claim defensible."
- [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) — verbatim ideation. Rarely needed.

## State as of 2026-08-22

- Registration closes **6 Sept**, internal hackathon Sept–Oct, Grand Finale **December**.
- **Mod layer is at zero** and is the critical path. The weekend gauge (22–23 Aug) answers the
  five questions in the README. **Write the answers down, including the ugly ones** — that has not
  happened yet.
- **The training environment is still undecided.** The gauge decides it.
- **The rover expedition was designed out on 2026-08-22** — Perseverance/Ingenuity dynamic, a day
  the rover must return home before, sandstorms, fog of war revealed by an overhead camera that
  doubles as Ingenuity, RL on terrain. Full design in
  [`docs/rover-expedition.md`](docs/rover-expedition.md). **Second priority, not committed**,
  blocked on the embedded friend owning it end to end. It merges the old environment candidates 2
  and 3, and it is the takeover risk the old scope doc warned about.
- **Hollow Knight stays primary** — the only candidate with precision timing, a reactive opponent
  and an hours-long horizon, and PRJ-1 has it as the deliverable.
- RL here is cheaper than assumed: OC-STORM ran this game at **9 FPS control**, ~100k samples ≈
  3.1 hours of gameplay, several bosses cleared. Compute was never the constraint.

## Repo restructure, 2026-08-22

Done this session, so the old paths in any stale context are wrong:

- `01-ideas.md` + `03-ideas-2.md` → merged into [`docs/ideas.md`](docs/ideas.md).
- `scope-sih-2026.md` → **deleted**; its live content is now the README's "Current phase".
- Numbered-sequence convention is gone. Files are rewritten in place; only the raw transcript is
  immutable. See [`CLAUDE.md`](CLAUDE.md).
- Nothing committed. Ishan handles the remote himself.

## Next conversation

Driven by the weekend gauge. If the mod layer works, execution in Hollow Knight. If it doesn't,
the environment decision reopens and the rover simulator is the leading candidate.

Either way the first two artifacts are the same: the **Any% route**, then the **skill interface**.
Both block everything else, and the interface is what keeps the environment choice reversible.

---
*Last rewritten: 2026-08-22. Rewrite by replacing "State as of" — do not keep both.*
