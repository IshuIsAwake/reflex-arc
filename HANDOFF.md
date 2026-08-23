# HANDOFF

**Carries forward only the context the next conversation actually needs.** Not a history, not
a changelog. Rules for maintaining this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

**Reflex Arc.** A language model issuing goals to frozen, learned control policies. The model has
knowledge and no hands; the policies have hands and no knowledge. Not a paper — a from-scratch
build prioritising learning and explainability.

Named on 2026-08-23. It was "Brain and Spine" until then, so older context still says that. The
name has not gone outside the repo yet.

## Two tracks, since 2026-08-23

The environment question was never one question. It is two, with different teams:

| track | implementation | team | deliverable |
|---|---|---|---|
| **coursework** | Hollow Knight | separate, already set, retrieval covered | PRJ-1 |
| **hackathon** | the rover | the six, being assembled | SIH |

The rover leads the hackathon track because judges reward something they can watch move, and
because it demonstrates the latency argument literally rather than by analogy. The cost: terrain
does not fight back, so the reactive-opponent claim — the novel part — lives only on the
coursework track.

**The skill interface is what makes this two tracks rather than two projects.** Written once, both
implementations behind it. Design it against the rover, where `goto()` must also return an
estimated battery cost, and the game inherits a superset.

## Current phase

**Scope.** Read [`README.md`](README.md) first — the idea *and* the current plan: dates, the
mod-layer gauge, team, out of scope per track.

**SIH is not the goal.** Development time with a deadline, plus a cheap read on how the idea lands
with outsiders. What is optimised is the state of the project at the end of the window, not a
placing.

## What to read

- [`README.md`](README.md) — **the idea and the current plan. Start here.**
- [`docs/ideas.md`](docs/ideas.md) — the full idea, vision then technicalities.
- [`docs/rover-expedition.md`](docs/rover-expedition.md) — the hackathon track, designed.
- [`docs/02-critique-response.md`](docs/02-critique-response.md) — prior art and novelty. Only
  when the question is "has this been done" or "is this claim defensible."
- [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) — verbatim ideation. Rarely needed.

## State as of 2026-08-23

- **Registration closes 6 Sept — two weeks.** Internal hackathon Sept–Oct, Grand Finale December.
- **Team: three confirmed** — Ishan (interface, both tracks), Abhishek (game dev), Koushik (IoT).
  Nithin likely, hardware, meeting 24 Aug. Two slots open, one must be filled by a woman per SIH
  rules; one candidate contacted and yet to reply, another is unavailable.
- **Roles are deliberately undivided.** The full team ideates first and the division comes out of
  that session. It also doubles as the only honest read on who will actually work. Do not produce
  a work-division document before that session happens.
- **Mod layer is still at zero and the gauge answers are still unwritten.** It no longer gates the
  hackathon track, which is what the split bought. Abhishek is the person for it and was idle for
  want of a spec — giving him the five README questions is the cheapest unblock available.
- **The rover's "surprise" hazard family is held out from training from day one.** Let one member
  leak into the training distribution and the test is gone. It also gave the log a schema rule:
  *facts about the world expire, facts about yourself do not.*
- **Headcount does not parallelize the rover.** Arena waits on the terrain model, which waits on
  measuring the real rover. Extra people need work genuinely off that chain.
- RL here is cheaper than assumed: OC-STORM ran the game at **9 FPS control**, ~100k samples ≈ 3.1
  hours of gameplay, several bosses cleared. Compute was never the constraint.
- Repo restructured 2026-08-22 — `01-ideas.md` + `03-ideas-2.md` merged into
  [`docs/ideas.md`](docs/ideas.md), `scope-sih-2026.md` folded into the README, numbered-sequence
  convention gone. **Old paths in stale context are wrong.** Ishan handles the remote himself.

## Next conversation

Recruiting closes out first — Nithin on 24 Aug, then the two open slots. After that the whole
team ideates, and work division comes out of that rather than before it.

The first artifact either track needs is the **skill interface**. It is what keeps two
implementations from becoming two projects, and its failure codes are the schema of the
experience log.

---
*Last rewritten: 2026-08-23. Rewrite by replacing "State as of" — do not keep both.*
