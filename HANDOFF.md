# HANDOFF

**Carries forward only the context the next conversation actually needs.** Rules for maintaining
this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

**Reflex Arc.** A language model issuing goals to frozen, learned control policies. The model has
knowledge and no hands; the policies have hands and no knowledge. Named 2026-08-23 — it was "Brain
and Spine" before, and the name has not gone outside the repo.

Two implementations behind **one skill interface**: Hollow Knight for coursework (separate team,
already set), a rover for hackathons (the six, being assembled). Full plan in
[`README.md`](README.md); rover design in [`docs/rover-expedition.md`](docs/rover-expedition.md).

## Next conversation: SIH problem statements

**The task.** Find which SIH problem statements the rover could match, and check whether the space
angle still has an edge — intel says many teams are building ISRO-themed ideas this year.

**Check first, before anything else.** The README records that we are entering under **Student
Innovation**, where teams propose their own idea rather than answering a ministry-issued problem
statement. If that is right, "matching a problem statement" may be the wrong frame entirely and the
real question is which *theme bucket* to file under. Verify against the actual SIH rules — do not
reason about it from memory.

**What the differentiator actually is**, if the ISRO field turns out crowded. Every other team doing
a rover will be doing autonomous navigation, obstacle avoidance or SLAM. Ours is the only one where:

- the reflexes are **learned**, not scripted, and run locally with no brain on board;
- the deliberation is **remote and slow**, and the demo proves it — delay the link and it keeps going;
- the map is **fogged**, so the planner's job is information-gathering under a budget rather than
  routing, which is what stops a hardcoded table from winning;
- the planner **says out loud, in English, why it did something.**

The line for this is already written: *anyone can build a robot with sensors that navigates a room
on its own — that is a Roomba. This is a rover that thinks.*

**Do not overclaim novelty.** The LLM-over-RL-skills architecture has five published
instantiations ([`docs/02-critique-response.md`](docs/02-critique-response.md) §1). What is
unoccupied is the regime, and on this track specifically the latency argument — terrain does not
fight back, so the reactive-opponent claim stays with the game. The live risk is being no better
than a hardcoded table (Hösch: 46.4% vs 51.5%, p = 0.103).

## State as of 2026-08-23

- **Registration closes 6 Sept.** Internal hackathon Sept–Oct, Grand Finale December. SIH is not the
  goal — it is development time with a deadline. Nothing depends on selection.
- **Team: three confirmed** — Ishan (interface, both tracks), Abhishek (game dev), Koushik (IoT).
  Nithin likely, hardware, meeting 24 Aug. Two slots open, one to be filled by a woman per SIH
  rules; a candidate has been contacted and has not replied yet.
- **Roles are deliberately undivided.** The full team ideates first and the division comes out of
  that session — it doubles as the only honest read on who will actually work. **Do not produce a
  work-division document before that session happens.**
- **Mod layer is at zero and the gauge answers are still unwritten.** It no longer gates the
  hackathon track. Abhishek is the person for it and was idle for want of a spec.
- **Headcount does not parallelize the rover** — arena waits on the terrain model, which waits on
  measuring the real rover. Extra people need work off that chain.
- **The rover's "surprise" hazard family is held out from training from day one.** Let one member
  leak into the training distribution and the test is gone.

## Docs, shortened 2026-08-23

Trimmed for a first-read audience — people need to understand the project before implementation
starts. Decisions and rejections were preserved; scaffolding was cut.

**`ideas.md` was split.** The idea stays in [`docs/ideas.md`](docs/ideas.md) (3349 → 1857 words);
design decisions, engineering constraints, process, the deferred list, failure modes, open questions
and vocabulary moved to [`docs/technicalities.md`](docs/technicalities.md). Nothing was deleted in
the split. Section numbers run continuously — `ideas.md` ends at §8, `technicalities.md` starts
at §9.

Left alone: [`docs/phase1-problem-statement.md`](docs/phase1-problem-statement.md) is a submitted
coursework artifact, and [`docs/literature.md`](docs/literature.md) is already table-dense.

Older restructure (2026-08-22): `01-ideas.md` + `03-ideas-2.md` merged into
[`docs/ideas.md`](docs/ideas.md), `scope-sih-2026.md` folded into the README. **Old paths in stale
context are wrong.** Ishan handles the remote himself.

---
*Last rewritten: 2026-08-23. Rewrite by replacing "State as of" — do not keep both.*
