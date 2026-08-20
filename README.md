# Brain and Spine

**Language models that decide. Learned policies that act. Neither doing the other's job.**

> The language model doesn't waste its weights on learning movements.
> The reinforcement learning doesn't waste its weights on making informed decisions.

---

## The problem

A language model can reason about what ought to be done and has no idea what the body it is
driving can physically do. So it produces plans that are sensible on paper and fall apart on
contact — *walk through that gap* when the gap is too narrow, *take the shortcut* when the
shortcut needs a move the machine cannot make.

Control policies learned through reinforcement learning have exactly the opposite deficit.
Precise, reactive, fast — and no notion of what is worth doing or why. A policy that can reach
any coordinate you name has no opinion about which coordinate matters.

Bolt them together and each covers the other's hole. The interesting question is what happens at
the seam:

> **How much is world knowledge actually worth, when the low-level skills are frozen and no
> further training is allowed?**

Nobody has measured this in a setting where being 200 milliseconds late is fatal. That is the gap
this project is aimed at.

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

Two properties that people consistently assume wrong, so we state them up front:

**Nothing is trained while it runs.** The policies are frozen once learned; the language model is
never fine-tuned. Behaviour still changes over time, because every skill invocation returns a
structured outcome that is written to a log the planner reads before its next decision. *The
model does not learn. The system does.* This matters practically — knowledge that lives in a file
can be inspected, corrected and deleted. Knowledge baked into weights cannot.

**We are not claiming the architecture is new.** Language models directing learned control
policies is an established pattern with several independent instantiations, and we cite them
rather than claim them — see [`docs/02-critique-response.md`](docs/02-critique-response.md),
where we checked the prior art against primary sources and recorded which of our *own* earlier
claims died in the process. What is unoccupied is the regime — precision timing, a reactive
opponent, hours of unbroken execution rather than minutes — and the measurement of what the
knowledge is worth there.

## How we intend to test it

The architecture is the project. Anything it drives is an *implementation* — and the primary one
is deliberately the hardest we could find.

**The main testbed: a precision action game.** *Hollow Knight*, chosen for four properties that
no robotics simulator has together — a difficulty ladder authored by professionals, an opponent
that reacts to you, ground-truth access to what that opponent is about to do, and an enormous
population of expert humans to measure against. Completing it takes hours of unbroken play in
which a single mistimed input ends the attempt.

This is where the claim actually gets tested. Every comparable system in the literature runs for
minutes, or for many short episodes with resets in between. If the composition layer survives
here, it has survived something nothing else in this literature has been asked to do.

It is not there because we wanted to play games. Precision-critical, adversarial, long-horizon
control is genuinely hard to obtain, and one of the few honest sources of it is a medium where
professionals spend years tuning difficulty. We take the measurements, not the entertainment.

**A second implementation, under discussion: a small physical robot.** A wheeled bot trained in a
simulator we write ourselves and then deployed to hardware — real physics, real sensor noise,
real communication delay. It would let us demonstrate the central argument literally rather than
by analogy: put a delay on the link to the planner and the machine keeps operating, because the
reflexes were never on the far end of that link.

Its value is that it fails *differently*. The robot can be slow and still succeed; the game
cannot. The game can be reset infinitely; the robot cannot. A design that works in exactly one
place is hard to distinguish from a design that was fitted to it, and a second implementation is
the cheapest available proof that the architecture is the constant.

It is genuinely not committed. It depends on people we have not finished talking to, and it is
second in priority to the game.

## Why this might matter elsewhere

A Mars rover cannot be driven from Earth in real time — the signal takes 3 to 22 minutes each
way. Reflexes have to be local and deliberation has to be remote and slow. That is not a design
preference, it is the speed of light. NASA's rovers already fly the reflex half; the deliberating
half is what is missing.

We claim architectural transfer, not sim-to-real magic. Nobody should believe a policy trained in
a game moves a robot, and they would be right. What is defensible is the *pattern* — and the
robot track is where we test whether it survives contact with hardware.

## Where we actually are

Ideation is done and documented. Implementation has not started. The architecture is settled; the
environment is not, and the section below says so honestly rather than pretending otherwise.

---

# Current phase — open, and being worked out

We are using the Smart India Hackathon window as development time with a deadline attached, and
as a cheap read on how the idea lands with people outside it. **SIH is not the goal** and nothing
here depends on being selected. Afterwards this goes to other hackathons, conferences and game
jams.

Everything in this section is undecided on purpose. It is written down so it can be argued with.

### Which environment do we build first?

The destination is the game. The open question is only what we build *while* the layer that
drives it is being made to work.

- **Hollow Knight directly.** The target, and the one the rest of the project is measured
  against. It depends on a modding layer that does not exist yet — being tested first, precisely
  so this choice gets made with evidence rather than optimism.
- **A hand-written simulator, possibly ending in a physical bot.** We would own the physics, the
  reward, the reset and the clock, so it trains far faster than real time. Cheaper, fully
  controllable, and a fallback that is not a downgrade. Second in priority, and dependent on
  conversations that have not happened yet.
- **An abstract testbed** with no motor skill at all, to test the planning and memory layer
  alone. Nearly free, and it produces the one measurement that most directly answers the first
  question below.

These are not exclusive. A single frozen skill interface is what lets us keep the choice open —
if the planner only ever talks to the interface, every environment is swappable behind it, and
nothing built against one is wasted if another wins.

### Open questions

- **Is the language model actually worth its place?** The one that matters most. In the closest
  published comparison, a language model directing learned skills tied with a hand-written
  decision table. If we cannot beat a lookup table we have learned something important and
  unflattering, and we would rather find that out early than late.
- **What is the right granularity of decision?** Something like *"go to that landmark and
  retrieve the thing"* is a good unit — knowledge-heavy to choose, mechanically demanding to
  execute. Whether all the useful decisions have that shape is not yet clear.
- **What does the model control beyond which skill to run?** Possibly a few dials — how urgently
  to act, whether to spend resources or conserve them. Current position: a dial is only justified
  for something the planner knows that the policy cannot see. Everything else is the policy's job
  to learn.
- **How much does the experience log help**, and how does it stay small enough to remain useful
  over a long run?
- **The policies may need to see the space they are in.** Deciding whether to go over an obstacle
  or around it depends on geometry the current observation design does not include.
- **Capability changes over time.** Tools become available that were not available before. Likely
  answer is a per-capability availability flag with the action blocked when it is off, but this
  is deferred — real robots launch with a fixed toolset.

### Not doing yet

Anything requiring trained policies to already exist. The full breakdown, including what is
deliberately excluded and why, is in [`docs/scope-sih-2026.md`](docs/scope-sih-2026.md).

---

## Repository

| | |
|---|---|
| [`docs/scope-sih-2026.md`](docs/scope-sih-2026.md) | the current working plan |
| [`docs/01-ideas.md`](docs/01-ideas.md) | the full idea, including what we rejected and why |
| [`docs/02-critique-response.md`](docs/02-critique-response.md) | prior art and novelty, verified against primary sources |
| [`docs/03-ideas-2.md`](docs/03-ideas-2.md) | current decisions |
| [`docs/literature.md`](docs/literature.md) | reading list with links |
| [`docs/00-raw-transcript.md`](docs/00-raw-transcript.md) | original ideation, verbatim |

Rejected ideas are kept with their reasoning rather than deleted, so they do not get
rediscovered. Numbered documents are a sequence — later ones supersede parts of earlier ones and
say so explicitly rather than editing history.

## A few references worth the time

Full list in [`docs/literature.md`](docs/literature.md).

1. [Do As I Can, Not As I Say](https://arxiv.org/abs/2204.01691) — the origin of grounding a
   language model in what the machine can actually do.
2. [ExpeL](https://arxiv.org/abs/2308.10144) — agents that learn from their own logged experience
   with no weight updates.
3. [AI just Broke Trackmania's Greatest World Record](https://www.youtube.com/watch?v=zFLQU70QstY)
   — reinforcement learning on precision control, and how much training a *single 23-second
   track* costs.
4. [OC-STORM](https://arxiv.org/abs/2501.16443) — the game as a published RL benchmark, with
   numbers to compare against.
