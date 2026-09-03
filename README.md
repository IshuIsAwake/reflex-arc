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

## Current phase

The rover is what is in scope until **5 September**, for the internal hackathon. Everything that
matters for it is in [`ROVER.md`](ROVER.md); the coursework track runs separately and on its own
schedule.

---

## Repository

**Reading order for anyone new:** this file → [`ROVER.md`](ROVER.md) →
[`ARCHITECTURE.md`](ARCHITECTURE.md) → [`work_division.md`](work_division.md) for your part →
[`repo_rules.md`](repo_rules.md) before you push anything. On the coursework track,
[`docs/course.md`](docs/course.md) instead of the rover. Not the raw transcript.

| | |
|---|---|
| [`ROVER.md`](ROVER.md) | the hardware implementation — the hackathon track |
| [`rover_ideas.md`](rover_ideas.md) | the rover in full — the reasoning, and what was already cut |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | how the three layers fit together |
| [`work_division.md`](work_division.md) | who owns what |
| [`reproduce.md`](reproduce.md) | run the simulation on your own machine — Windows, no GPU needed |
| [`repo_rules.md`](repo_rules.md) | git, context budget, and how ideas get written down |
| [`docs/course.md`](docs/course.md) | the Hollow Knight implementation — the coursework track |
| [`docs/sih-decision.md`](docs/sih-decision.md) | which SIH entry to make — open, closes 6 Sept |
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
