# Scope — the SIH window

First scoped target. Everything numbered before this document was idea work; this is the first
time the project is aimed at a date. Written 2026-08-20.

## What SIH is for

**It is not the goal.** Getting selected under Student Innovation is a genuine maybe and nothing
here depends on it. What the window is actually for:

1. **Free development time** with a real deadline attached, which is worth more than the deadline.
2. **A read on how interesting the idea is to people outside it.** The internal round is a cheap
   way to find that out.

After this the refined version goes to other hackathons, conferences and game jams. So the thing
being optimised is *the state the project is in at the end of the window*, not a placing.

That changes the tradeoff. We do not need the safest possible demo. We can afford to spend some
of the window finding out whether the harder thing works.

## Dates

| date | what |
|---|---|
| 25 Aug 2026 | SIH problem statements release — irrelevant under Student Innovation, worth reading anyway |
| **6 Sept 2026** | team registration closes — hard |
| Sept–Oct 2026 | internal college hackathon |
| Dec 2026 | Grand Finale, if selected |

## The framing this window has to establish

**The project is the architecture. Everything it drives is an implementation.**

This is the reframe that solves the problem we kept circling — that games are discounted at
hackathons and conferences. The answer is not to hide Hollow Knight, and it is not to demote it.
It is to have more than one implementation, so the architecture is visibly the constant and the
domain is visibly the variable.

**Hollow Knight remains the primary implementation.** Two reasons, and both are binding:

1. **It is the hard test.** It is the only candidate with precision timing, a reactive opponent
   and an hours-long horizon. A second implementation proves the architecture is not fitted to one
   domain; it does not prove the architecture is any good. Only the hard case does that.
2. **It is the coursework substrate.** PRJ-1 and the course projects have Hollow Knight as the
   deliverable. That is not negotiable and it is not a detail — a plan that quietly makes the game
   secondary breaks commitments already made to faculty.

Note there is no tension between this and the pitch discipline in `01-ideas.md` §8. *Never lead
with Hollow Knight* is about the first slide. It was never about where the work happens.

## The decision that is not made yet

**Which environment we train in.** Three candidates, and the first one is being measured this
weekend before anything is committed.

### 1. Hollow Knight directly

The only option that produces the demo we actually want. Blocked on a modding layer that is
currently at zero.

The training cost is smaller than we assumed. [OC-STORM](https://arxiv.org/abs/2501.16443) ran
this game at **9 FPS control** and reached 98.3% on Mawlek and 66.7–100% on Hornet Protector at
**100k samples ≈ 3.1 hours of gameplay** — an overnight run, not a fortnight. See
[`02-critique-response.md` §4](02-critique-response.md) for the full table.

So the constraint was never compute. It is the mod layer, and that is a question about Unity and
Harmony rather than about machine learning.

### 2. A game we write ourselves — and possibly a robot at the end of it

A small game requiring dodging, movement and timing. No mod layer at all. We would own the
physics, the reward, the reset and the clock, so it runs far faster than real time and is
debuggable in a way a commercial game is not.

**Potential extension — second priority, and not committed:** build the game as a simulation of a
small wheeled robot, train the traversal policy in it, then deploy that policy to actual hardware
at RC-car scale. One of us has a friend who is strong on the embedded side, so the hardware is
not the fantasy it would otherwise be.

**This requires conversations that have not happened yet** — with the embedded friend about
whether he wants it and can own it, and with the wider team about whether it earns its place. Do
not plan around it until those have happened. It is recorded here so the idea is not lost, not
because it is decided.

If it does land, three things follow:

- **The architecture becomes visibly the constant** — one design, one physical implementation and
  one in a game. That makes the framework claim without anyone having to assert it.
- **The Mars argument stops being an analogy.** Put an artificial delay on the link between the
  planner and the robot and it keeps operating, because the reflexes were never on the far end of
  that link. The entire thesis, on a table, in ten seconds.
- **Sim-to-real becomes a result rather than a disclaimer.** A wheeled robot on a flat floor is
  about the friendliest reality gap in robotics.

Two cautions, so this is entered with eyes open:

1. **A robot is not a substitute for the game as a testbed.** `01-ideas.md` §5 chose Hollow Knight
   for four properties — authored difficulty ladder, reactive opponent, ground truth about that
   opponent, human expert baseline. A wheeled bot in a room has none of them. The robot would show
   the architecture is physically real and not fitted to one domain; only the game shows it works
   under precision timing and adversarial pressure. **Different jobs, and the robot is the easier
   and more fun one to build — which is exactly why it could quietly take over. It must not.**
2. **Hardware eats time** — batteries, calibration, wireless, latency, and a long tail of things
   that do not exist in simulation. This only works if the embedded friend owns it end to end
   rather than it being a side task for someone already loaded.

### 3. Abstract testbed

The door game in [`03-ideas-2.md` §7](03-ideas-2.md). No motor skill whatsoever. Tests only
whether the planning and memory layer works, and produces one graph — deaths-to-clear against
attempt number, with and without the write path — which happens to be the clearest answer we can
cheaply get to the project's top open question.

Runs on a laptop against a model that is already installed. Effectively free.

**These are not exclusive.** The likely answer is more than one, and the interface below is what
makes that cheap.

## The weekend gauge

The point of starting Hollow Knight RL this weekend is to make the decision above with evidence
instead of guesses. Five things to find out, roughly in order of how badly a "no" hurts:

1. **Can we read game state?** Player position, velocity, health; enemy position and state.
2. **Can we inject inputs reliably?** Through the game's own input handling, not OS-level key
   events.
3. **Can we reset a fight quickly?** Without this the training budget does not exist.
4. **Can we run faster than real time,** and does the game's behaviour change when we do?
5. **Can we run more than one instance at once?**

A "no" on 1 or 2 means Hollow Knight is not the training environment for this window and option 2
above becomes the plan. A "no" on 3 means training is possible but slow. A "no" on 4 and 5 is
survivable given the 9 FPS numbers above.

Write the answers down, even the ugly ones. This decision gets revisited later and we will not
remember why we chose.

## What is worth building regardless

### The skill interface — first, and blocking

Signatures, preconditions, return values, structured failure codes. `01-ideas.md` §10 already
calls this the single most important artifact in the project.

It matters more now, because it is what lets the environment decision stay open. If the planner
talks only to the interface, then Hollow Knight, a hand-written game and the door game are all
*implementations*, swappable without touching the planner. The environment question stops being
a bet.

> The failure codes are not error handling. They are the schema of the experience log, and the
> log is how the system learns.

### The Any% route

Which bosses, in what order, in which rooms, with which abilities held at each point. Cheap
document, and it defines the demo boundary, the ability tiers and any scripted paths. Also the
source of concrete decision units like *"go to King's Station and take the Hallownest Seal"* —
knowledge-heavy to choose, mechanically demanding to execute, which is exactly the shape of
decision the architecture is arguing for.

### Scripted skill stubs

A `goto()` that cheats and a `kill()` that runs a dumb attack loop, per `01-ideas.md` §10.2. They
let the planner be built and demonstrated in parallel with any training, rather than after it,
and they are what makes a demo possible even if every environment above disappoints.

## Team

Six: Ishan and the Unity friend, four more from 22–23 Aug. Shape below; adjust to what the four
can actually do.

| group | owns |
|---|---|
| platform | mod layer, state extraction, input injection, resets — and the weekend gauge |
| environment | whichever of the three candidates survives the gauge |
| planner | **the interface**, prompts, retrieval, experience log — works across all candidates |
| robot | *not staffed.* Only opens if the embedded friend takes it end to end. Second priority behind the game either way. |
| pitch | deck, framing, demo recording |

The planner role is the integration point and should not go to someone joining cold.

**Reading for the four, in order:** [`../README.md`](../README.md) →
[`../CLAUDE.md`](../CLAUDE.md) → [`03-ideas-2.md`](03-ideas-2.md) → [`01-ideas.md`](01-ideas.md)
§2. Not the raw transcript.

## Not doing in this window

- Path of Pain, White Palace, the Pantheons, any hard boss
- procedurally generated rooms
- the competence table — needs measured policies to exist
- the style dial and reward-weight knobs — need trained policies and reward terms first
- charm selection, Silksong
- retrieval over the full wiki — curated pages covering the demo route are enough

Model choice is settled by default: Gemma via Ollama, because it already runs. Do not shop.

## Risks

| risk | mitigation |
|---|---|
| mod layer is the critical path and is at zero | the weekend gauge answers it in days, not weeks; two fallback environments exist |
| four people arrive cold | fixed reading order above; the interface gives them something concrete to build against |
| the environment decision gets made by momentum rather than by the gauge | write the five answers down |
| effort goes into a demo instead of into the idea | SIH is not the goal — the state of the project at the end of the window is |

## Deferred, not dropped

Carried from `03-ideas-2.md` §9 and the sessions since:

- [ ] Does the language model beat a hard-coded lookup table? *Still highest priority.*
- [ ] What state must accompany every experience-log entry?
- [ ] How does the log stay small enough to retrieve well over a long run?
- [ ] Ability progression — availability flag per ability, input blocked when off. Agreed in
      principle, deferred: real robots launch with a fixed toolset, so this is a property of the
      game rather than of the problem.
- [ ] Knobs, if any. Position reached: a dial is for what the planner knows and the policy cannot
      see, not for what the policy has not learned yet. That collapses four proposed axes to
      roughly two, and it is also what a per-boss lookup table cannot replicate.
- [ ] Combat observations need local room geometry, which the current design lacks.
- [ ] `Plan4MC` and `ExpeL` belong in the prior-art section and are not there yet. ExpeL matters
      most: it is the experience log, published, and `03-ideas-2.md` §4 currently reads as though
      we invented it.
