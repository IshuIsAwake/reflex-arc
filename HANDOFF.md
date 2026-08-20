# HANDOFF

**Carries forward only the context the next conversation actually needs.** Not a history, not
a changelog. Rules for maintaining this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

Hollow Knight played autonomously by a language model issuing goals to frozen, learned control
policies. The model has knowledge and no hands; the policies have hands and no knowledge. Not a
paper — a from-scratch build prioritising learning and explainability.

## Current phase

**Scope, as of 2026-08-20.** The idea phase closed and the project is now aimed at a date.

Read [`docs/scope-sih-2026.md`](docs/scope-sih-2026.md) first. Everything below is context for it.

The scope gate — "wait for team headcount" — was released by a hard external deadline rather
than satisfied. Team is six: Ishan, the Unity friend, and four arriving 22–23 Aug.

**SIH is not the goal.** It is development time with a deadline attached, plus a cheap read on
how interesting the idea is to outsiders. What is being optimised is the state of the project at
the end of the window, not a placing. Do not plan as though selection matters.

## What to read

`docs/` is the source of truth. Numbered files are ideation, in sequence; later ones supersede
parts of earlier ones and say so.

- [`README.md`](README.md) — public-facing idea plus the open questions. What outsiders see.
- [`docs/scope-sih-2026.md`](docs/scope-sih-2026.md) — **the current plan. Start here.**
- [`docs/03-ideas-2.md`](docs/03-ideas-2.md) — the decisions the scope rests on.
- [`docs/01-ideas.md`](docs/01-ideas.md) — the idea superset. §2, §5, §8, §10 still current.
- [`docs/02-critique-response.md`](docs/02-critique-response.md) — prior art and novelty. Only
  when the question is "has this been done" or "is this claim defensible."
- [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) — verbatim ideation. Rarely needed.

## State as of 2026-08-20

- Registration closes **6 Sept**, internal hackathon Sept–Oct, Grand Finale **December**.
- Entering under **Student Innovation**, so the framing is entirely ours.
- **Mod layer is at zero**, and it is the critical path. Ishan starts Hollow Knight RL over the
  weekend of 22–23 Aug to gauge whether it is viable at all.
- **The training environment is genuinely undecided** between Hollow Knight directly, a small
  game written in-house, and the abstract door game. The weekend gauge decides it. The five
  questions to answer are listed in the scope document and the answers should be written down.
- **A physical robot idea opened 2026-08-20**, and is **second priority and not committed**: write
  the game as a simulator for a small wheeled bot, train there, deploy to hardware. Turns the Mars
  latency argument into a ten-second table demo. Needs conversations with the embedded friend and
  the team that have not happened yet — do not plan around it.
- **Hollow Knight stays primary**, for two binding reasons: it is the only candidate with
  precision timing, a reactive opponent and an hours-long horizon, and **PRJ-1 and the course
  projects have it as the deliverable**. Note that "never lead with Hollow Knight" (`01-ideas.md`
  §8) is about the first slide of a pitch, not about where the work happens — those were being
  conflated.
- Correction worth keeping: RL here is cheaper than we assumed. OC-STORM ran this game at **9 FPS
  control**, ~100k samples ≈ 3.1 hours of gameplay, and cleared several bosses. Compute was never
  the constraint; the mod layer is.
- Repo went public-facing this session: merged `ideas/` into `docs/`, added `README.md` and
  `CLAUDE.md`, gitignored the full Gemini critique and kept the novelty one. Nothing committed
  yet — Ishan sets up the remote himself.

## Open, and deliberately unresolved

`04-ideas-3.md` was started and never written. Three threads were worked through in conversation
and live in the "Deferred" section of the scope document instead: ability progression, combat
observations needing local geometry, and the reward-weight knobs.

The knob thread reached a position worth keeping: **a dial is for what the planner knows and the
policy cannot see, not for what the policy has not learned yet.** That collapses four proposed
axes to roughly two, and it is also what a per-boss lookup table cannot replicate.

## Next conversation

Driven by the weekend gauge. If the mod layer works, execution in Hollow Knight. If it doesn't,
the environment decision reopens and the in-house game is the leading candidate.

Either way the first two artifacts are the same: the **Any% route**, then the **skill interface**.
Both block everything else, and the interface is what keeps the environment choice reversible.

---
*Last rewritten: 2026-08-20. Rewrite by replacing "State as of" — do not keep both.*
