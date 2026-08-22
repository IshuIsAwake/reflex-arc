# Brain and Spine

**Language models that decide. Learned policies that act. Neither doing the other's job.**

> The language model doesn't waste its weights on learning movements.
> The reinforcement learning doesn't waste its weights on making informed decisions.

---

## The problem

A language model can reason about what ought to be done and has no idea what the body it is
driving can physically do. It produces plans that are sensible on paper and fall apart on contact —
*walk through that gap* when the gap is too narrow, *take the shortcut* when the shortcut needs a
move the machine cannot make.

Control policies learned through reinforcement learning have the opposite deficit. Precise,
reactive, fast, and with no notion of what is worth doing. A policy that can reach any coordinate
you name has no opinion about which coordinate matters.

Bolt them together and each covers the other's hole. The interesting question is what happens at
the seam:

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

Two properties people consistently assume wrong:

**Nothing is trained while it runs.** The policies are frozen once learned and the language model
is never fine-tuned. Behaviour still changes, because every skill invocation returns a structured
outcome written to a log the planner reads before its next decision. *The model does not learn.
The system does.* Knowledge that lives in a file can be inspected, corrected and deleted.

**We are not claiming the architecture is new.** Language models directing learned control
policies is an established pattern with several independent instantiations, and we cite them
rather than claim them — see [`docs/02-critique-response.md`](docs/02-critique-response.md), where
we checked the prior art against primary sources and recorded which of our own earlier claims died
in the process. What is unoccupied is the regime — precision timing, a reactive opponent, hours of
unbroken execution — and the measurement of what knowledge is worth there.

## How we intend to test it

The architecture is the project. Anything it drives is an *implementation*.

**The main testbed: a precision action game.** *Hollow Knight*, chosen for four properties no
robotics simulator has together — a difficulty ladder authored by professionals, an opponent that
reacts to you, ground-truth access to what that opponent is about to do, and an enormous
population of expert humans to measure against. Completing it takes hours of unbroken play in
which a single mistimed input ends the attempt.

Every comparable system in the literature runs for minutes, or for many short episodes with resets
in between. If the composition layer survives here, it has survived something nothing else in this
literature has been asked to do.

**A second implementation, under discussion: a rover.** A wheeled robot running a Mars expedition
in a classroom-sized arena — a day of daylight it must return home before, sandstorms on a
forecast, terrain that costs battery, and a map revealed only in the pieces it has driven through
or flown over. Trained in a simulator we write ourselves, then deployed to hardware. It lets us
demonstrate the central argument literally: put a delay on the link to the planner and the machine
keeps operating, because the reflexes were never on the far end of that link.

Its value is that it fails differently. A design that works in exactly one place is hard to
distinguish from a design that was fitted to it.

Designed in detail in [`docs/rover-expedition.md`](docs/rover-expedition.md). **Genuinely not
committed** — it depends on people we have not finished talking to, and it is second in priority
to the game.

## Why this might matter elsewhere

A Mars rover cannot be driven from Earth in real time — the signal takes 3 to 22 minutes each way,
so reflexes have to be local and deliberation remote and slow. NASA's rovers already fly the
reflex half. The deliberating half is what is missing.

We claim architectural transfer rather than sim-to-real magic. What is defensible is the *pattern*,
and the rover is where we test whether it survives contact with hardware.

## Where we actually are

Ideation is done and documented. Implementation has not started. The architecture is settled; the
environment is not.

---

# Current phase

We are using the Smart India Hackathon window as development time with a deadline attached, and as
a cheap read on how the idea lands with people outside it. **SIH is not the goal** and nothing here
depends on being selected. Afterwards this goes to other hackathons, conferences and game jams.
What is being optimised is the state of the project at the end of the window.

| date | what |
|---|---|
| **6 Sept 2026** | team registration closes — hard |
| Sept–Oct 2026 | internal college hackathon |
| Dec 2026 | Grand Finale, if selected |

Entering under Student Innovation, so the framing is entirely ours.

### Which environment do we build first?

The destination is the game. The open question is what we build *while* the layer that drives it is
being made to work.

- **Hollow Knight directly.** The target, and what the rest of the project is measured against. It
  depends on a modding layer that does not exist yet.
- **A simulator we write, possibly ending in the rover.** We would own the physics, the reward, the
  reset and the clock, so it trains far faster than real time. Second in priority.
- **An abstract testbed** with no motor skill at all, to test the planning and memory layer alone.
  Nearly free, and it produces the measurement that most directly answers the first open question
  below. Largely absorbed by the rover simulator.

These are not exclusive. A single frozen skill interface is what keeps the choice open — if the
planner only ever talks to the interface, every environment is swappable behind it.

**The mod layer is at zero and is the critical path.** Five questions answer whether Hollow Knight
can be the training environment, roughly in order of how badly a "no" hurts:

1. Can we read game state — player position, velocity, health, enemy position and state?
2. Can we inject inputs reliably, through the game's own input handling?
3. Can we reset a fight quickly? Without this the training budget does not exist.
4. Can we run faster than real time, and does behaviour change when we do?
5. Can we run more than one instance at once?

A "no" on 1 or 2 means Hollow Knight is not the training environment for this window. A "no" on 3
means training is possible but slow. A "no" on 4 or 5 is survivable — OC-STORM ran this game at
9 FPS control and cleared several bosses on ~100k samples, about 3.1 hours of gameplay. Compute was
never the constraint.

**Write the answers down, including the ugly ones.** This decision gets revisited and we will not
remember why we chose.

### Worth building regardless of that answer

- **The skill interface — first, and blocking.** Signatures, preconditions, return values,
  structured failure codes. It is what lets the environment decision stay open, and the failure
  codes are the schema of the experience log.
- **The Any% route.** Which bosses, in what order, in which rooms, with which abilities at each
  point. A cheap document that defines the demo boundary and the ability tiers.
- **Scripted skill stubs.** A `goto()` that cheats and a `kill()` that runs a dumb attack loop, so
  the planner can be built and demonstrated in parallel with training rather than after it.

### Open questions

- **Is the language model actually worth its place?** The one that matters most. In the closest
  published comparison, a language model directing learned skills tied with a hand-written decision
  table. If we cannot beat a lookup table we have learned something important and unflattering.
- **What is the right granularity of decision?** Something like *"go to that landmark and retrieve
  the thing"* is a good unit. Whether all the useful decisions have that shape is not yet clear.
- **What does the model control beyond which skill to run?** Current position: a dial is only
  justified for something the planner knows that the policy cannot see.
- **How much does the experience log help**, and how does it stay small enough over a long run?
- **The policies may need to see the space they are in.** Deciding whether to go over an obstacle
  or around it depends on geometry the current observation design does not include.
- **Capability changes over time.** Likely a per-capability availability flag with the action
  blocked when off. Deferred — real robots launch with a fixed toolset.

### Team

Six people. The shape: a **platform** group owning the mod layer, state extraction, input
injection and resets; an **environment** group owning whichever candidate survives; a **planner**
group owning the interface, prompts, retrieval and the experience log; and **pitch**. The rover is
not staffed and only opens if someone takes it end to end.

The planner role is the integration point and should not go to someone joining cold.

**Reading order for anyone new:** this file → [`CLAUDE.md`](CLAUDE.md) →
[`docs/ideas.md`](docs/ideas.md). Not the raw transcript.

### Not doing in this window

Path of Pain, White Palace, the Pantheons, any hard boss; procedurally generated rooms; the
competence table, which needs measured policies to exist; the style dial and reward-weight knobs,
which need trained policies first; charm selection; Silksong; retrieval over the full wiki, since
curated pages covering the demo route are enough.

Model choice is settled by default: Gemma via Ollama, because it already runs. Do not shop.

---

## Repository

| | |
|---|---|
| [`docs/ideas.md`](docs/ideas.md) | the full idea — vision first, technicalities after |
| [`docs/rover-expedition.md`](docs/rover-expedition.md) | the second implementation, designed |
| [`docs/02-critique-response.md`](docs/02-critique-response.md) | prior art and novelty, verified against primary sources |
| [`docs/literature.md`](docs/literature.md) | reading list with links |
| [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) | original ideation, verbatim |

Rejected ideas are kept with their reasoning rather than deleted, so they do not get rediscovered.

## A few references worth the time

Full list in [`docs/literature.md`](docs/literature.md).

1. [Do As I Can, Not As I Say](https://arxiv.org/abs/2204.01691) — the origin of grounding a
   language model in what the machine can actually do.
2. [ExpeL](https://arxiv.org/abs/2308.10144) — agents that learn from their own logged experience
   with no weight updates.
3. [AI just Broke Trackmania's Greatest World Record](https://www.youtube.com/watch?v=zFLQU70QstY)
   — reinforcement learning on precision control, and how much training a *single 23-second track*
   costs.
4. [OC-STORM](https://arxiv.org/abs/2501.16443) — the game as a published RL benchmark, with
   numbers to compare against.
