# Phase 1 — Problem Statement

**Autonomous play of a precision action game, by separating reflexes from reasoning.**

> The LLM doesn't waste its weights on learning movements.
> The RL doesn't waste its weights on making informed decisions.

## The problem

We want a system that plays *Hollow Knight* from start to finish on its own, with no human
input. The game demands several hundred deliberate button presses per minute, frame-accurate
reactions to opponents that react back, and knowledge of a large interconnected world that the
game never explains — where to go, what is worth fighting, what to ignore. Those two demands
pull in opposite directions: one needs a response in milliseconds, the other needs deliberation
over minutes. Our problem is not "can a machine play a hard game." It is **what a system's
architecture has to look like for fast reflexes and slow reasoning to coexist in one agent.**

## How we got here

We began with something narrower: train a reinforcement learning agent to beat a single
mechanically difficult boss. That much has precedent and we expect it to work.

It stopped being enough once we asked what beating the *whole game* would require. A single
learned policy would have to hold the entire game at once — every enemy, every room, every
route decision — and reinforcement learning is at its worst over horizons that long, where the
consequence of a choice arrives hours after the choice.

So we split the problem by the kind of skill it needs. **A combat module**, which learns to
fight a target given what that target is doing. **A traversal module**, which learns to reach a
requested point in the world through hazards. Both are motor skills — things a human learns by
practising, not by reading.

That exposed the remaining hole. Neither module knows *what to do*. A traversal policy can
reach any coordinate and has no idea which coordinate matters. That knowledge is exactly what
large language models already hold, from years of wikis, guides and discussion. So the language
model became the third piece: it decides where to go and what to fight; the learned policies
carry it out. The model has knowledge and no hands. The policies have hands and no knowledge.

## Why this is hard — for machines and for people

The strongest reference point is Trackmania, where a hobbyist spent roughly **400 hours of
training** to beat a human world record on a **single 23-second track** — solo, deterministic,
no opponent. Hollow Knight's fastest completion is about **33 minutes** of continuous play
across hundreds of distinct rooms against enemies that respond to you. Humans need dozens of
hours to finish it once at all. The gap between those two facts is the difficulty of this
project, stated honestly.

The game also contains sections that isolate each half of our architecture cleanly. The Path
of Pain is a pure movement gauntlet with no enemies to fight — several minutes of unbroken,
frame-accurate platforming that a large share of players never complete. It is the clearest
possible statement of what the traversal module alone has to be capable of.

## What this could mean beyond the game

The reason we think this is worth doing is what the split implies elsewhere. A Mars rover
cannot be driven from Earth in real time — the signal takes 3 to 22 minutes each way. Reflexes
must be local; deliberation must be remote and slow. That is the same brain-and-spine division,
forced by physics rather than chosen by us. NASA's rovers already have the reflex half. The
deliberating half is what is missing. If the composition works in a game that punishes bad
timing, the pattern is worth testing where timing matters for real.

## Input and methodology — where we honestly are

Phase 1 has been ideation, and we have deliberately kept it there. The scope of this project is
large enough that committing to a methodology now would mean committing to one we revise in a
month. The architecture above is settled. The process is not, and we would rather say so.

**Settled:** the three-part architecture; that the learned policies are frozen once trained and
the language model is never fine-tuned; that the system is built and understood from scratch
rather than assembled from existing frameworks.

**Still open:** the exact interface between the language model and the policies, which we
consider the most important remaining decision; the observation format for the policies; the
training environment and how much of it must be generated rather than taken from the game.

*A note on documentation: the ideation behind this summary is considerably more extensive than
what is above, and is being organised into a public repository. We will share the link through
Classroom comments once it is presentable.*

## Expected output

The architecture completing an **Any% run of Hollow Knight autonomously** — the game finished
end to end, planned and executed by the system with no human in the loop.

Our measure of success is deliberately not a flawless run. A system that misjudges a jump,
dies, walks back and re-plans is demonstrating the thing we are actually building; a perfect run
is indistinguishable from a script.

## References

1. **[AI just Broke Trackmania's Greatest World Record](https://www.youtube.com/watch?v=zFLQU70QstY)** — reinforcement learning applied to a
   precision driving game. Shows both that this class of method works and how much training a
   *single short track* costs. Covered by [PC Gamer](https://www.pcgamer.com/one-mans-years-long-quest-to-train-an-unbeatable-trackmania-ai-may-have-finally-crossed-the-line/).
2. **[Hollow Knight — Path of Pain, hitless](https://www.youtube.com/watch?v=a5EUUB5_HwY)** — an
   optional platforming gauntlet with no combat in it. This is the precision the traversal
   module has to reach, isolated from every other demand of the game.
3. **[Hollow Knight Any% in 33:07 by fireb0rn](https://www.youtube.com/watch?v=FFZy2gtwpI4)** — a
   world-record human completion. Useful for seeing the required input density and reaction
   speed, and the scale of what "finishing the game" means. Category leaderboards on
   [speedrun.com](https://www.speedrun.com/hollowknight).
4. **NASA AutoNav (Perseverance)** — onboard autonomous navigation with no human in the loop,
   the flight-proven version of our traversal module.
