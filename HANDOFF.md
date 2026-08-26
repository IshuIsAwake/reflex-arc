# HANDOFF

**Carries forward only the context the next conversation actually needs.** Rules for maintaining
this file are in [`CLAUDE.md`](CLAUDE.md).

---

## The project

**Reflex Arc.** A language model issuing goals to frozen, learned control policies. The model has
knowledge and no hands; the policies have hands and no knowledge. Named 2026-08-23 — it was "Brain
and Spine" before, and the name has not gone outside the repo.

Two implementations behind **one skill interface**: Hollow Knight for coursework (separate team,
already set), a rover for hackathons. Full plan in [`README.md`](README.md); rover design in
[`ROVER.md`](ROVER.md).

## Prototype 1: the world and the planner are built

**Three areas, fog, mazes, snake pits, two counters, a vault, and A\* behind a console.** Read
[`prototype1/HANDOFF.md`](prototype1/HANDOFF.md) before touching the code, and
[`prototype1/NAVIGATION.md`](prototype1/NAVIGATION.md) before touching the planner.

**A\* plans over what has been seen, not the true map**, which is what keeps maps worth buying. Fog
is assumed empty, so a plan is a hypothesis and walking into an unseen wall is how the map fills in.
`Area.at` returns ground truth at every fog setting, so `nav.known()` is the single gated door onto
the grid — two tests now count the reads, because the view went through it too.

## Gemma can see and walk

**Built 2026-08-26.** `python game/main.py --gemma` puts the game on the left and gemma on the
right, with a view block injected on every request and two tools, `goto` and `distance`. It reads
its own coordinates and does the arithmetic: *"go 6 blocks north"* from (1,15) comes back
`goto(1,9) → DONE(steps=6)`. The model's whole side is written up in
[`prototype1/SIGHT.md`](prototype1/SIGHT.md); everything prototype-scoped is in
[`prototype1/HANDOFF.md`](prototype1/HANDOFF.md).

**The two shapes stayed distinct and it was worth it.** `goto` is a tool gemma asks for; the view
arrives unbidden and cannot be requested. There is no `look()` and never needs to be — with `goto`
as its only tool, *"what is around you?"* drew a `goto` to the cell it already stood on, twice out
of two. With the view injected, the same question now draws zero calls.

**Next is `interact`, and five live runs decided it.** Told *"go to the shop"*, gemma arrives in one
call and then wanders for seven more, because there is nothing to *do* at a shop and no reason to
prefer any direction. Every turn binds against the tool-call cap for that reason. The three
couplings in `world.py` that block `interact` are now on the critical path.

**Read [`prototype1/FINDINGS.md`](prototype1/FINDINGS.md) first.** Six bugs and four decisions from
the reverted `spike/gemma-integration` — rebuilt by hand rather than cherry-picked, and the four
decisions held up — plus six more from these runs. Nearly all were invisible to a code review
because the tests were green throughout. The oldest line in it, *a lying success code is worse than
any failure code*, keeps earning its place: both new failures were successes that could not advance
anything, and the sharpest new one is that **a field is not a sentence.**

**Model is settled: `gemma4:e4b` via Ollama.** Measured 2026-08-26 on the 6 GB RTX 3050 laptop: ~20
tok/s, 3.6 GB VRAM, flat out to 16k context; a turn is ~25s with thinking off. The 9.6 GB file is
59% unquantised per-layer embeddings and ~0.9 GB of unused vision and audio towers, so
`gemma4:e4b-it-qat` (6.1 GB) is the one swap worth trying. **Do not otherwise shop.** Native tool
calls work and arrive already parsed. It reliably misreads a monospace grid, which is why the view
names things rather than only drawing them.

## The live decision: which SIH track we build

**Still open, closes 6 Sept.** The whole argument is in
[`docs/sih-decision.md`](docs/sih-decision.md) (2026-08-24) and has not moved: the rover under
Student Innovation against PS 26167 (ISRO, *SatQuery AI*), which GHOST already half-answers. The
asymmetry is the judges — a ministry statement means the judge already believes the problem matters.

**A team may submit two ideas**, so what to *submit* and what to *build* are separate decisions.
Undecided: which we build, what the other four do on a GHOST track, whether to submit both.
**Prototype 1 does not depend on any of this** and can proceed regardless.

## State as of 2026-08-26 (evening)

- **Registration closes 6 Sept.** Internal hackathon Sept–Oct, Grand Finale December. SIH is not the
  goal — it is development time with a deadline. Nothing depends on selection.
- **Team: six confirmed.** Ishan (planner and interface, both tracks), Abhishek (game dev), Koushik
  (IoT), Nithin (hardware), and two more. The coursework track is separately staffed.
- **The team ideation session has not happened** — called off 24 Aug. Roles stay undivided and no
  work-division document should be written before it runs; the plan is in
  [`docs/team-session.md`](docs/team-session.md).
- **Mod layer is at zero and the gauge answers are still unwritten** — five questions in
  [`README.md`](README.md). Abhishek is the person for it and is idle for want of a spec.
- **Headcount does not parallelize the rover** — arena waits on the terrain model, which waits on
  measuring the real rover. Extra people need work off that chain.
- **The rover's "surprise" hazard family is held out from training from day one.** Let one member
  leak into the training distribution and the test is gone.

## Novelty, unchanged

Five published instantiations of LLM-over-RL-skills
([`docs/02-critique-response.md`](docs/02-critique-response.md) §1). What is unoccupied is the
*regime* — on the rover track specifically the latency argument, since terrain does not fight back.
Live risk: being no better than a hardcoded table (Hösch: 46.4% vs 51.5%, p = 0.103). Prototype 1 is
the cheapest available read on that risk.

---
*Last rewritten: 2026-08-26. Rewrite by replacing "State as of" — do not keep both.*
