# HANDOFF

**Carries forward only the context the next conversation actually needs.** Rules for maintaining
this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

**Reflex Arc.** A language model issuing goals to frozen, learned control policies. The model has
knowledge and no hands; the policies have hands and no knowledge. Two implementations behind **one
skill interface**: Hollow Knight for coursework (separate team, already set), a rover for
hackathons. Full plan in [`README.md`](README.md); rover design in [`ROVER.md`](ROVER.md).

## Prototype 3 is the active work

**Start at [`prototype3/HANDOFF.md`](prototype3/HANDOFF.md).** It carries the plan in order — RLE
encoding, `end()`, `fog()`, the scratchpad, the prompt rewrite — with the reasoning attached and a
list of things already rejected, so none of it gets re-derived.

Code is a fork of prototype 2. **Prototype 2 stays the demo build** and is pushed to main, so the
encoding work cannot destabilise what five people watch.

## What prototype 2 settled

[`prototype2/results.md`](prototype2/results.md), and it is two findings.

**`why` is optional now**, which took `BAD_ARGS` from 16 of 21 calls to 0 of 13.

**gemma cannot count into the rendered grid and gemini can** — 0% at 4B *and* at 31B on counting a
box or a row, correct for gemini on the first try. So it is a gemma limitation rather than an LLM
one, the map is in the wrong channel for the model we ship, and the fix is the encoding. The
remaining probe questions are a good hand-off to someone on the team; free tier is 20 requests per
day per model, and failed requests count.

`prototype2/HANDOFF.md` and `prototype2/MAP-READING.md` were deleted as stale on 2026-09-03. They
are in history at `408e378` if the reasoning is ever wanted.

## Prototype 1 is paused, not finished

**Three areas, fog, mazes, a vault, A\* behind a console, gemma seeing and walking.** Still runs;
the reference for the coursework track. `interact(x, y, why)` is specified and unbuilt — spec in
[`prototype1/HANDOFF.md`](prototype1/HANDOFF.md); [`AUDIT.md`](prototype1/AUDIT.md) explains it on
paper for a judge.

**Read [`prototype1/FINDINGS.md`](prototype1/FINDINGS.md) before touching any prototype.** Twelve
items, nearly all invisible to a code review because the tests were green throughout. Three recur:
*a lying success code is worse than any failure code*, *a field is not a sentence*, and *check the
fact, not the label*. **Never quote one run as a result** — the same script gave 31, then 14, then
32 calls.

**Local model is settled: `gemma4:e4b` via Ollama** — ~20 tok/s, 3.6 GB VRAM, flat to 16k on the
6 GB RTX 3050. **Do not shop locally.** Hosted models are a diagnostic and are not constrained by
VRAM; `gemma-4-31b-it` is the controlled scaling arm, same family and tokenizer at ~8× the size.

## The live decision: which SIH track we submit

**Still open, closes 6 Sept** — three days. The argument is in
[`docs/sih-decision.md`](docs/sih-decision.md) (2026-08-24) and has not moved: the rover under
Student Innovation against PS 26167 (ISRO, *SatQuery AI*), which GHOST already half-answers. The
asymmetry is the judges — a ministry statement means the judge already believes the problem matters.

**A team may submit two ideas**, so what to *submit* and what to *build* are separate decisions.
Undecided: which we build, what the other four do on GHOST, whether to submit both. **Neither
prototype depends on any of it.**

## State as of 2026-09-03

- **Internal hackathon 4–5 Sept — tomorrow.** Registration closes 6 Sept. Grand Finale December.
  SIH is development time with a deadline; nothing depends on selection.
- **Team: six confirmed.** Ishan (planner and interface, both tracks), Abhishek (game dev), Koushik
  (IoT), Nithin (hardware), and two more. The coursework track is separately staffed.
- **The team ideation session has not happened** — called off 24 Aug. Roles stay undivided and no
  work-division document should be written before it runs; plan in
  [`docs/team-session.md`](docs/team-session.md). **Prototype 2 is what it will be run against.**
- **Mod layer is at zero and the gauge answers are still unwritten** — five questions in
  [`README.md`](README.md). Abhishek is the person for it and is idle for want of a spec.
- **Headcount does not parallelize the rover** — the arena waits on the terrain model, which waits
  on measuring the real rover.
- **The rover's "surprise" hazard family is held out from training from day one.**

## Novelty, unchanged

Five published instantiations ([`docs/02-critique-response.md`](docs/02-critique-response.md) §1);
what is unoccupied is the *regime* — on the rover track, latency. Live risk: no better than a
hardcoded table (Hösch: 46.4% vs 51.5%, p = 0.103), still unmeasurable. **Priority-weighted
objectives are what would make it measurable** — with region size as the only axis, "go to the
biggest blob" is the whole optimal policy and a lookup table ties by construction.

---
*Last rewritten: 2026-09-03. Rewrite by replacing "State as of" — do not keep both.*
