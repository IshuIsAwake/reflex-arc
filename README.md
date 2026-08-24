# Reflex Arc

**Language models that decide. Learned policies that act. Neither doing the other's job.**

*A reflex arc runs sense → spinal cord → muscle and never consults the brain. The brain finds out
afterwards, and decides what to do next.*

> The language model doesn't waste its weights on learning movements.
> The reinforcement learning doesn't waste its weights on making informed decisions.

---

## The problem

A language model can reason about what ought to be done and has no idea what the body it is
driving can physically do. It plans *walk through that gap* when the gap is too narrow.

Learned control policies have the opposite deficit — precise, reactive, fast, and with no notion of
what is worth doing. A policy that can reach any coordinate you name has no opinion about which
coordinate matters.

Bolt them together and each covers the other's hole. The question is what happens at the seam:

> **How much is world knowledge actually worth, when the low-level skills are frozen and no
> further training is allowed?**

Nobody has measured this where being 200 milliseconds late is fatal.

## The architecture

```
  language model — thinks in seconds        knows the world, knows nothing about timing
  retrieval over documentation
  + a log of its own past attempts
             │
             │   goto(place) · engage(target)
             ▼
  frozen learned policies — real time       knows timing, knows nothing about the world
             │
             ▼
  the body — whatever it happens to be
```

**Nothing is trained while it runs.** Policies are frozen once learned; the language model is never
fine-tuned. Behaviour still changes, because every skill invocation returns a structured outcome
written to a log the planner reads before its next decision. *The model does not learn. The system
does.* Knowledge in a file can be inspected, corrected and deleted.

**The architecture is not new and we don't claim it.** Language models directing learned policies
has several published instantiations — [`docs/02-critique-response.md`](docs/02-critique-response.md)
cites them and records which of our own earlier claims died in the process. What is unoccupied is
the *regime*: precision timing, a reactive opponent, hours of unbroken execution.

## Two implementations

The architecture is the project. Anything it drives is an implementation, and there are two,
running in parallel with different teams.

**Hollow Knight — the research testbed.** Four properties no robotics simulator has together: a
difficulty ladder authored by professionals, an opponent that reacts to you, ground truth on what
that opponent is about to do, and a huge population of expert humans to measure against. Every
comparable system in the literature runs for minutes, or for short episodes with resets between.
Completing this takes hours in which one mistimed input ends the attempt.

**A rover — the hardware implementation.** A Mars expedition in a classroom-sized arena: daylight
it must return home before, sandstorms on a forecast, terrain that costs battery, and a map
revealed only where it has driven or flown. Trained in a simulator we write, then deployed. It
demonstrates the argument literally — delay the link to the planner and the machine keeps
operating, because the reflexes were never on the far end of it. Designed in
[`ROVER.md`](ROVER.md).

Its value is failing differently. A design that works in exactly one place is hard to distinguish
from a design fitted to it.

**One interface serves both.** Signatures, preconditions, return values, failure codes — written
once, both implementations behind it. That is what makes two tracks cheaper than two projects.
Design it against the rover, where `goto()` must also return an estimated battery cost, and the
game inherits a superset.

## Why it might matter elsewhere

A Mars rover cannot be driven from Earth in real time — 3 to 22 minutes each way. Reflexes must be
local, deliberation remote and slow. NASA already flies the reflex half; the deliberating half is
missing. We claim architectural transfer, not sim-to-real magic.

---

# Current phase

Ideation is done. Implementation has not started.

| track | implementation | team | deliverable |
|---|---|---|---|
| **coursework** | Hollow Knight | separate, already set, retrieval covered | PRJ-1 |
| **hackathon** | the rover | the six, being assembled | SIH |

**Why the rover leads the hackathon track.** Judges reward something they can watch move; a
game-playing agent reads as a toy to anyone outside the field, however much harder it is. **What it
costs:** terrain does not fight back, so the reactive-opponent claim lives on the coursework track
only, and the hackathon pitch leans on latency instead.

**SIH is not the goal.** It is development time with a deadline, and a cheap read on how the idea
lands with outsiders. Nothing depends on selection. Entering under Student Innovation, so the
framing is ours.

| date | what |
|---|---|
| **6 Sept 2026** | team registration closes — hard |
| Sept–Oct 2026 | internal college hackathon |
| Dec 2026 | Grand Finale, if selected |

### The mod layer — coursework track

At zero, and the critical path for Hollow Knight. It no longer gates the hackathon track, which is
what the split bought. Five questions, in order of how badly a "no" hurts:

1. Can we read game state — position, velocity, health, enemy state?
2. Can we inject inputs through the game's own input handling?
3. Can we reset a fight quickly? Without this there is no training budget.
4. Can we run faster than real time, and does behaviour change when we do?
5. Can we run more than one instance at once?

A "no" on 1 or 2 means Hollow Knight is not the training environment this window. On 3, training is
slow but possible. On 4 or 5, survivable — OC-STORM ran this game at 9 FPS control, clearing
several bosses on ~100k samples (~3.1 hours of gameplay). Compute was never the constraint.

**Write the answers down, including the ugly ones.** Not done yet.

### Worth building either way

- **The skill interface — first and blocking, on both tracks.** Its failure codes are the schema of
  the experience log.
- **Scripted skill stubs.** A `goto()` that cheats, a `kill()` that runs a dumb attack loop — so the
  planner gets built alongside training rather than after it.
- **The Any% route** (coursework). Which bosses, what order, which abilities. Defines the demo
  boundary.

### Open questions

- **Is the language model worth its place?** The one that matters. In the closest published
  comparison it tied with a hand-written decision table. If we can't beat a lookup table, we've
  learned something important and unflattering.
- **What granularity of decision?** *"Go to that landmark and retrieve the thing"* is a good unit.
  Whether every useful decision has that shape is unclear.
- **What does the model control beyond skill choice?** A dial is only justified for something the
  planner knows and the policy cannot see.
- **How much does the experience log help**, and how does it stay small over a long run?
- **Policies may need to see the space they are in** — over or around an obstacle depends on
  geometry the observation design lacks.

### Team — hackathon track

Six required, three confirmed: Ishan (planner and interface, both tracks), Abhishek (game dev),
Koushik (IoT). A fourth on hardware is likely; two slots open. The coursework track is separately
staffed.

**Roles are deliberately not divided yet.** The whole team ideates first and the division comes out
of that session. People who shape a thing don't need to be assigned to it, and the session is the
only honest read on who will actually work.

Two constraints on whatever comes out of it: the interface role is the integration point and should
not go to someone joining cold, and **headcount does not parallelize the rover** — the arena waits
on the terrain model, which waits on measuring the real rover. Extra people need work off that
chain.

### Not doing in this window

*Coursework.* Path of Pain, White Palace, the Pantheons, any hard boss; procgen rooms; the
competence table; the style dial and reward-weight knobs; charm selection; Silksong; retrieval over
the full wiki.

*Hackathon.* The surprise hazard family — it only means something against a system that already
succeeds without it. Keys, locked rooms, seesaws, extra days and real walls are all droppable.

Model choice is settled by default: Gemma via Ollama, because it already runs. Do not shop.

---

## Repository

**Reading order for anyone new:** this file → [`ROVER.md`](ROVER.md) →
[`docs/hollow-knight.md`](docs/hollow-knight.md). Not the raw transcript.

| | |
|---|---|
| [`ROVER.md`](ROVER.md) | the hardware implementation — the hackathon track |
| [`docs/hollow-knight.md`](docs/hollow-knight.md) | the coursework implementation — design and experiments |
| [`docs/technicalities.md`](docs/technicalities.md) | design decisions, constraints, deferred list — for implementing |
| [`docs/sih-decision.md`](docs/sih-decision.md) | which SIH entry to make — open, closes 6 Sept |
| [`docs/02-critique-response.md`](docs/02-critique-response.md) | prior art and novelty, verified against primary sources |
| [`docs/literature.md`](docs/literature.md) | reading list with links |
| [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) | original ideation, verbatim |

Rejected ideas keep their reasoning rather than being deleted, so they don't get rediscovered.

Four references worth the time: [SayCan](https://arxiv.org/abs/2204.01691) for grounding a language
model in what a machine can actually do · [ExpeL](https://arxiv.org/abs/2308.10144) for learning
from logged experience with no weight updates ·
[Trackmania](https://www.youtube.com/watch?v=zFLQU70QstY) for what precision control costs to train
· [OC-STORM](https://arxiv.org/abs/2501.16443) for the game as a published benchmark.
