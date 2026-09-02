# HANDOFF

**Carries forward only the context the next conversation actually needs.** Rules for maintaining
this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

**Reflex Arc.** A language model issuing goals to frozen, learned control policies. The model has
knowledge and no hands; the policies have hands and no knowledge. Two implementations behind **one
skill interface**: Hollow Knight for coursework (separate team), a rover for hackathons. Plan in
[`README.md`](README.md); rover design in [`ROVER.md`](ROVER.md).

## The next conversation restructures the repo for the team

**Five teammates start on this repo on 2026-09-04.** The whole job is making it simple enough to
walk into. Three things were named:

1. **Rewrite [`README.md`](README.md) and [`ROVER.md`](ROVER.md).** Both are long and assume the
   reader was in the room.
2. **Move every coursework-related section into `docs/course.md`**, so the rover track reads on its
   own. The coursework team is separate; mixing the two is what makes both hard to follow.
3. **Simplify the rest of `docs/`.** Judge each file by whether a teammate with no context can read
   it — that is the bar now, not completeness.

The precedent to follow is the pass just done on prototype 3: comments and docstrings were 31% of
the code and are now 26%, every block cut to one or two lines carrying the fact rather than the
history of how it was reached. Two documents that had accumulated contradictions were deleted
outright rather than patched, after committing so the reasoning stays in history.

## Prototype 3 is the active work

**Start at [`prototype3/HANDOFF.md`](prototype3/HANDOFF.md)** — 60 lines, four items in order:
**RLE encoding → `end()` → `fog()` → the scratchpad**, each with what it is and why. It also lists
three probe bugs and one self-contained task worth handing to a teammate.

**Prototype 2 is the demo build and is pushed.** Do not develop in it.

## What prototype 2 settled

[`prototype2/results.md`](prototype2/results.md), two findings.

**`why` is optional now**, which took `BAD_ARGS` from 16 of 21 calls to 0 of 13.

**gemma cannot count cells off the map picture and gemini can** — 0% at 4B *and* at 31B on counting
a box or a row, correct for gemini on the first try. It is a gemma limitation rather than an LLM
one, so the fix is how the map is written, not which model reads it.

`prototype2/HANDOFF.md` and `prototype2/MAP-READING.md` were deleted as stale on 2026-09-03; they
are in history at `408e378` if the reasoning is ever wanted.

## Prototype 1 is paused, not finished

Three areas, fog, mazes, a vault, A\* behind a console. Still runs; the reference for the coursework
track. `interact(x, y, why)` is specified and unbuilt — spec in
[`prototype1/HANDOFF.md`](prototype1/HANDOFF.md); [`AUDIT.md`](prototype1/AUDIT.md) explains it for
a judge.

**Read [`prototype1/FINDINGS.md`](prototype1/FINDINGS.md) before touching any prototype.** Twelve
items, nearly all invisible to a code review because the tests were green throughout. Three recur:
*a lying success code is worse than any failure code*, *a field is not a sentence*, and *check the
fact, not the label*. **Never quote one run as a result.**

**Local model is settled: `gemma4:e4b` via Ollama** on a 6 GB RTX 3050. Do not shop locally. Hosted
models are a diagnostic and are not constrained by VRAM.

## State as of 2026-09-03

- **Internal hackathon 4–5 Sept.** SIH registration closes 6 Sept. Grand Finale December.
- **Which SIH track to submit is still open** — the argument is in
  [`docs/sih-decision.md`](docs/sih-decision.md) and has not moved: the rover under Student
  Innovation against PS 26167 (ISRO). A team may submit two ideas, so what to *submit* and what to
  *build* are separate questions. **Neither prototype depends on any of it.**
- **Team: six confirmed.** Ishan (planner and interface), Abhishek (game dev), Koushik (IoT),
  Nithin (hardware), and two more.
- **The team ideation session has not happened** — called off 24 Aug. Roles stay undivided and no
  work-division document should be written before it runs; plan in
  [`docs/team-session.md`](docs/team-session.md). **Prototype 2 is what it will be run against.**
- **Mod layer is at zero and the gauge answers are unwritten** — five questions in `README.md`.
  Abhishek is the person for it and is idle for want of a spec.
- **Headcount does not parallelize the rover** — the arena waits on the terrain model, which waits
  on measuring the real rover.

## Novelty, unchanged

Five published instantiations ([`docs/02-critique-response.md`](docs/02-critique-response.md) §1);
what is unoccupied is the *regime* — on the rover track, latency. Live risk: no better than a
hardcoded table (Hösch: 46.4% vs 51.5%, p = 0.103), still unmeasurable. **Priority-weighted
objectives are what would make it measurable** — with region size as the only axis, "go to the
biggest blob" is the whole optimal policy and a lookup table ties by construction.

---
*Last rewritten: 2026-09-03. Rewrite by replacing "State as of" — do not keep both.*
