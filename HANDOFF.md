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

## Next conversation: Gemma

Toying with the Gemma already installed via Ollama. **Model choice is settled — do not shop and do
not benchmark alternatives.**

This is the first execution-phase activity, so keep it pointed at the planner rather than at the
model. The blocking artifact on both tracks is the **skill interface**, and its failure codes are
the schema of the experience log. Scripted skill stubs — a `goto()` that cheats — let the planner
be built before any policy is trained.

## The live decision: which track we build

[`docs/sih-decision.md`](docs/sih-decision.md) (2026-08-24) is the full argument. In short:

- **Student Innovation is not a separate track** — it is 34 of SIH 2026's 226 statements. The rover
  files under Hardware / Space Technology. ISRO issued 11 statements and none is a rover.
- **A second way in appeared.** PS 26167 (ISRO, *SatQuery AI*) fits GHOST, the hyperspectral
  framework Ishan and Abhishek already shipped — honestly ~15–20% of that deliverable, with the
  entire language half unbuilt.
- **The asymmetry is the judges.** A ministry statement means the judge already believes the
  problem matters. Student Innovation means carrying 100% of the explanation to people who did not
  ask — the configuration that failed GHOST at a previous hackathon.

**A team may submit two ideas**, so what to *submit* and what to *build* are separate decisions.
Undecided: which we build, what the other four do on a GHOST track, whether to submit both.

## State as of 2026-08-24

- **Registration closes 6 Sept.** Internal hackathon Sept–Oct, Grand Finale December. SIH is not the
  goal — it is development time with a deadline. Nothing depends on selection.
- **Team: six confirmed.** Ishan (planner and interface, both tracks), Abhishek (game dev), Koushik
  (IoT), Nithin (hardware), and two more. The coursework track is separately staffed.
- **The team ideation session was called off on 24 Aug** for lack of availability. It has not
  happened, so **roles are still undivided** and no work-division document should be produced
  before it.
- **Mod layer is at zero and the gauge answers are still unwritten** — five questions in
  [`README.md`](README.md). Abhishek is the person for it and is idle for want of a spec.
- **Headcount does not parallelize the rover** — arena waits on the terrain model, which waits on
  measuring the real rover. Extra people need work off that chain.
- **The rover's "surprise" hazard family is held out from training from day one.** Let one member
  leak into the training distribution and the test is gone.

## The team session, when it is rescheduled

Prepared 2026-08-24, unused. Recorded so it is not re-derived:

**Bottom-up, eight beats, the project named only at beat 6.** Hand on a hot stove → Mars at 3–22
minutes each way, so who stops the rover driving into a hole → Earth's half of the loop is a room
full of PhDs and was never automated → why an LLM cannot drive and RL cannot decide → tape floor,
ESP32, no brain on board → **delay the link twenty seconds and it keeps going** → the map is fogged,
so the job is deciding what is worth looking at → and it says why, in English.

- **Beat 4 is the transcript, not an argument.** `docs/00-raw-transcript.md` 262–345 — the model
  finds the Seal, derives a farm route, is told to go get it, and has no hands. Show it.
- **The target is "what if we…", not "wow."** Awe that is not understood produces politeness, and a
  finished design can only be delegated, not joined.
- **Each half must be load-bearing for the other**, or each side files the other under *not my part*
  and stops listening. The latency demo works *because* the rover has no brain; the RL is necessary
  *because* battery cost per slope can only be measured off the real machine. Shared currency:
  battery.
- **Leave the open questions genuinely open** — onboard sensing, day length, grid size, flight
  budget, storm forecast. Roles come out of the session.
- **Hold the onboard-sensing question unclaimed** for the member who could not attend, so she joins
  into ownership rather than a settled plan.
- Say the hardcoded-table risk out loud. It is what makes this a problem rather than a task.

## Novelty, unchanged

Five published instantiations of LLM-over-RL-skills
([`docs/02-critique-response.md`](docs/02-critique-response.md) §1). What is unoccupied is the
*regime* — on the rover track specifically the latency argument, since terrain does not fight back.
Live risk: being no better than a hardcoded table (Hösch: 46.4% vs 51.5%, p = 0.103).

**Docs were reorganised 2026-08-24 and old paths in stale context are wrong.**
`docs/rover-expedition.md` → [`ROVER.md`](ROVER.md), `docs/ideas.md` →
[`docs/hollow-knight.md`](docs/hollow-knight.md), `problem_statement_issue.md` →
[`docs/sih-decision.md`](docs/sih-decision.md). The transcript was kept deliberately — it holds a
worked example Ishan wants. Ishan handles the remote himself.

---
*Last rewritten: 2026-08-24. Rewrite by replacing "State as of" — do not keep both.*
