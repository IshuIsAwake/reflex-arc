# Reflex Arc

**Language models decide. Learned policies act.**

> The language model doesn't waste its weights on learning movements.
> The reinforcement learning doesn't waste its weights on making informed decisions.

---

## The problem

A language model can reason about what ought to be done and has no idea what the body it is
driving can physically do. It plans *walk through that gap* when the gap is too narrow.

Learned control policies have the opposite deficit — precise, reactive, fast, and with no notion of
what is worth doing. A policy that can reach any coordinate you name has no opinion about which
coordinate matters.

## Two implementations

The architecture is the project. Anything it drives is an implementation, and there are two,
running in parallel with different teams.

**A rover.** A Mars expedition in a classroom-sized arena — trained in a simulator we write, then
driven on real hardware. Designed in [`ROVER.md`](ROVER.md).

**Hollow Knight.** The system plays a hard game start to finish, an Any% run. Designed in
[`docs/course.md`](docs/course.md).

## Current plan

*As of 24 October 2026.* Two prototypes were built off `main`, and both come back to it before
anything new starts. Each step below gets its own conversation. Prototype numbers carry no plan:
a new prototype takes the next free number.

The rover carries a 360° camera, which mimics the simulation's sight, and a LiDAR. The LiDAR
knows where fixed things are, which in testing means the room's four walls, and tracks the
rover's position from them. That is how wheel slip will get caught: the LiDAR reports where
the rover actually is, and the model replans from there. Errors are still reported, not
corrected. The overhead camera in [`ARCHITECTURE.md`](ARCHITECTURE.md) is superseded. The LiDAR
waits until after prototype 14.

**Done:**
- Prototypes 1–9 are archived in [`archive/`](archive/) and at the git tag `prototypes-1-9`,
  with their conclusions in [`docs/findings.md`](docs/findings.md). Prototype 10 is frozen as
  [`prototype10a/`](prototype10a/), the build the Angaraka recording ran on.
- [`prototype10b/`](prototype10b/) is the base, [`prototype10c/`](prototype10c/) the rover
  working sols by itself, and [`prototype10d/`](prototype10d/) the sol in four phases. Each one's
  `DESIGN.md` is its scope.
- [`prototype11/`](prototype11/) is 10d with Harsh's mission-control screen, merged on 23 Oct
  with the text-input bug fixed. The look is not final: Abhishek moves the view to Unity
  later, as a 3D view of everything.
- [`prototype12/`](prototype12/) is Koushik's, merged on 24 Oct and independent of 11. 10d's
  `game/`, copied untouched, drives the real rover through `hardware/`, up to Level 3: the
  rover replays each leg the simulation drove, and nothing measures where it ends up. Level 3
  has driven 14 legs on the rover with its wheels in the air. A stop from the pad ends the leg
  and hands the rover to a person, and one cell is 10 cm. His LiDAR and Level 4 are on the
  branch `old_level4`.
- [`prototype13/`](prototype13/) merges them: 11's simulation and screen, with 12's rover
  driving every leg up to Level 3. Under Level 3 it opens on the 30, 3 m of floor, and the
  screen says the rover reports when it has stopped. Nothing pauses her day while the rover
  drives, so on the rover the clock will end most days before the battery does. How the two
  fit is not decided.
- The rover's chassis is built and laser-cut.

**Next:**
1. **Prototype 14: the simplification.** The code is brought to
   [`repo_rules.md`](repo_rules.md) §7, so any teammate can explain it line by line. The rover
   goes up to Level 3. Names review found unclear change here: the `run_` files, and DONE, OFF
   and LOST if they survive.
2. **The repo goes back to the team for the final hardware:**
   - Level 4 and the LiDAR, redone by Koushik and Abhishek with Nithin, starting from the
     branch `old_level4`;
   - the bots and their circuits simulated in software, in a simulator such as Wokwi;
   - later, sensors: a thermometer, and temperature and humidity sensors. Their readings could
     become objectives in the simulation.
3. **Then optimisation:**
   - her memory and list overflow the context, past 90% of 16k tokens by sol 7 or 8. Try 32k,
     and hard rules in her prompt for when to do what and what goes in her memory and list;
   - what other papers tried, such as fine-tuning a small model on a large model's outputs;
   - prompt engineering, which everyone on the team learns;
   - the documentation overhaul: plain docs for people, technical or not, and deep docs for
     developers and AI, with the literature review, the LiDAR's included. Until then
     `ARCHITECTURE.md`'s camera section, `work_division.md` and `rover_ideas.md` are stale.

**Throughout, Himank tests the whole software.** He finds bugs by reading the run logs with a
model.

**The Robothon (October 2026)** is an RC race: one lap, fastest wins. One of our teams builds two
race bots for it, and the other works on Reflex Arc. Once the rovers and their connections are
done, the aim is a language model driving the race course on its own, outside the race's rules,
to see whether one can finish a real course. Not decided: whether the model steers, or sets the
goals the planner drives to.

**Deferred:**
- **The simulation game:**
  - a bigger map, with regions besides the Jezero flats that each have their own hazards;
  - bigger storms that move;
  - missions that span several sols, with enough objectives that choosing between them matters;
  - damage to the rover, with an HP system, where errors are injected and reported.

  Still open there: chunks of 50×50 cells, a scripted baseline to compare decisions against, and
  how the view scales. The grid view costs about 1,200 tokens at 50×50.
- RL for the rover's controller.
- A fallback for when the local model fails too. 10d already falls back from the cloud model to
  the local one.
- Gemini keys in the settings, and a test run on Windows.

Krish's `link-bot` branch is off the plan, and kept. Abhishek's `rover-bridge` and `rover-link`
were off it too, and he has deleted them.

---

## Repository

**Reading order for anyone new:** this file → [`ROVER.md`](ROVER.md) →
[`ARCHITECTURE.md`](ARCHITECTURE.md) → [`docs/findings.md`](docs/findings.md) →
[`repo_rules.md`](repo_rules.md) before you push anything. On the coursework track,
[`docs/course.md`](docs/course.md) instead of the rover. Not the raw transcript.

| | |
|---|---|
| [`ROVER.md`](ROVER.md) | the hardware implementation — the hackathon track |
| [`rover_ideas.md`](rover_ideas.md) | the rover in full — the reasoning, and what was already cut |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | how the three layers fit together |
| [`work_division.md`](work_division.md) | who owns what |
| [`prototype13/`](prototype13/) | 11's simulation driving the real rover, up to Level 3 — the newest |
| [`prototype12/`](prototype12/) | 10d's game driving the real rover, up to Level 3 |
| [`prototype11/`](prototype11/) | 10d with the mission-control screen, the newest simulation |
| [`prototype10d/`](prototype10d/) | the sol in four phases, interests and objectives |
| [`prototype10c/`](prototype10c/) | the rover working sols by itself, with comms modelled on a real mission |
| [`prototype10b/`](prototype10b/) | the base the team is testing — the simulation, the planner and the seam to the rover |
| [`prototype10a/`](prototype10a/) | prototype 10 frozen as the Angaraka recording ran it |
| [`docs/findings.md`](docs/findings.md) | what prototypes 1–9 settled — read before changing how the model is spoken to |
| [`archive/`](archive/) | prototypes 1–9, as a tarball |
| [`repo_rules.md`](repo_rules.md) | git, branches and prototypes, and how an AI assistant works with you |
| [`docs/course.md`](docs/course.md) | the Hollow Knight implementation — the coursework track |
| [`docs/sih-decision.md`](docs/sih-decision.md) | which SIH entries we made, and why — closed; links both decks |
| [`docs/novelty.md`](docs/novelty.md) | is this actually new — prior art, verified against primary sources |
| [`docs/pitch.md`](docs/pitch.md) | how to explain the project to someone from nothing |
| [`docs/literature.md`](docs/literature.md) | reading list with links |
| [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) | original ideation, verbatim |

Rejected ideas keep their reasoning rather than being deleted, so they don't get rediscovered.

Four references worth the time: [SayCan](https://arxiv.org/abs/2204.01691) for grounding a language
model in what a machine can actually do · [ExpeL](https://arxiv.org/abs/2308.10144) for learning
from logged experience with no weight updates ·
[Trackmania](https://www.youtube.com/watch?v=zFLQU70QstY) for what precision control costs to train
· [OC-STORM](https://arxiv.org/abs/2501.16443) for the game as a published benchmark.
