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

**Three areas, fog, mazes, snake pits, two counters, a vault, and A\* behind a console.** Playable by
hand, no model in it. It is committed — `prototype1/` had never been in git until 2026-08-26, which
is why there was nothing to step back to when the next part went wrong.

Everything prototype-scoped is in [`prototype1/HANDOFF.md`](prototype1/HANDOFF.md). Read that before
touching the code, and [`prototype1/NAVIGATION.md`](prototype1/NAVIGATION.md) before touching the
planner.

**A\* plans over what has been seen, not the true map**, which is what keeps maps worth buying. Fog
is assumed empty, so a plan is a hypothesis and walking into an unseen wall is how the map fills in.
`Area.at` returns ground truth at every fog setting, so `nav.known()` is the single gated door onto
the grid and a test counts the reads to keep it that way. The map view draws the plan and the walk
together for the same reason: the plan may cross walls, the walk cannot, and the gap between them is
what the fog cost.

## Next conversation: rebuild the skill interface, one piece at a time

**A spike built the whole gemma integration in one session on 2026-08-26 and it was reverted** —
skill interface, Ollama loop, persistence, replay and a watch window, all at once, which is more
than one gate's worth of work. It survives on `spike/gemma-integration` and it worked. **Rebuild it
by hand anyway — do not cherry-pick from that branch.** Decided 2026-08-26: it is a record of what
went wrong, not a patch to apply, and its four decisions stay settled rather than re-argued.

**Read [`prototype1/FINDINGS.md`](prototype1/FINDINGS.md) first.** It is what that spike cost to
learn: six bugs and four decisions, most of them invisible to a code review because the tests were
green throughout. It ends with the order to rebuild in. The single most useful line in it — *a lying
success code is worse than any failure code* — came from a four-day model run that went nowhere
because `goto` answered `DONE` for a move that never happened.

Model is settled: `gemma4:e4b` via Ollama, confirmed installed. **Do not shop and do not benchmark
alternatives.**

## The live decision: which SIH track we build

[`docs/sih-decision.md`](docs/sih-decision.md) (2026-08-24) is the full argument. In short:

- **Student Innovation is not a separate track** — it is 34 of SIH 2026's 226 statements. The rover
  files under Hardware / Space Technology. ISRO issued 11 statements and none is a rover.
- **A second way in appeared.** PS 26167 (ISRO, *SatQuery AI*) fits GHOST, the hyperspectral
  framework Ishan and Abhishek already shipped — honestly ~15–20% of that deliverable, with the
  entire language half unbuilt.
- **The asymmetry is the judges.** A ministry statement means the judge already believes the problem
  matters. Student Innovation means carrying 100% of the explanation to people who did not ask — the
  configuration that failed GHOST at a previous hackathon.

**A team may submit two ideas**, so what to *submit* and what to *build* are separate decisions.
Undecided: which we build, what the other four do on a GHOST track, whether to submit both.
**Prototype 1 does not depend on any of this** and can proceed regardless.

## State as of 2026-08-26

- **Registration closes 6 Sept.** Internal hackathon Sept–Oct, Grand Finale December. SIH is not the
  goal — it is development time with a deadline. Nothing depends on selection.
- **Team: six confirmed.** Ishan (planner and interface, both tracks), Abhishek (game dev), Koushik
  (IoT), Nithin (hardware), and two more. The coursework track is separately staffed.
- **The team ideation session has not happened** — called off 24 Aug for lack of availability. Roles
  stay undivided and no work-division document should be written before it runs. The plan for it is
  prepared and unused in [`docs/team-session.md`](docs/team-session.md); it is not re-derived here.
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
