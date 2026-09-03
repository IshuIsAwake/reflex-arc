# The rover

## Two machines on Mars

Perseverance has been driving across Jezero Crater since February 2021. It crosses ground nobody
has stood on, photographs it, drills rock and stores the samples. Ingenuity, a small helicopter,
flew with it — up over the terrain ahead, looking at ground the rover could not see yet.

Between them the job is the same one: cross the terrain, and carry out the missions along the way.

## The problem

Mars is 3 to 22 minutes away at the speed of light, each way. Nothing there can be driven live. By
the time a picture of an obstacle reaches Earth and an answer gets back, the better part of an hour
is gone and the rover has been sitting still for all of it.

So the driving is done from Earth, a day at a time. A team reads yesterday's images, decides where
the rover should go and what it should do there, writes the day out as a sequence of commands and
sends it up. The rover runs the day and the team finds out how it went tomorrow. It can pick its own
way around a rock in the path — that much is onboard. What it cannot do is decide where the path
should lead.

## The question

What if it decided for itself?

## Not a Roomba

A Roomba navigates. It covers the floor, avoids the furniture, finds its way back to the dock — and
it never decides anything. Told to clean, it cleans. There is no version of a Roomba that works out
that the kitchen is the room that matters today.

Navigation is not the hard part and it is not what is missing. We want a machine that thinks: one
that can look at where it is, what it has found and what it was sent to do, and choose what to do
next.

## Reflex Arc

Three parts, each doing the job it is actually good at.

- **A language model decides.** What is worth doing, and where to go next.
- **A\* plans the route.** Given a destination, work out the way there.
- **A learned policy drives.** It handles the ground itself, reacting far faster than anything that
  has to be thought about.

The knowledge sits in the model, the reflexes sit in the policy, and neither is doing the other's
job. What comes out is a machine that can make the call on the spot. How the three fit together is
in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## What exists

**The rover is built.** Six wheels, a Raspberry Pi, a motor driver and a buck converter, about a
foot long. It has no sensors and no brain — it does what it is told and nothing else.

**It drives on a floor map** watched by one fixed camera overhead. Nothing is painted on the floor:
the camera does not move, so the grid is drawn onto the image instead. Markers on the rover tell the
camera where it is and which way it is pointing.

**The planner runs, the simulator is being built.** The language model and route planning are
mostly in place; the Unity simulation and the learned driving policy are underway.

## The rest of it

This page is the shape of the thing. [`rover_ideas.md`](rover_ideas.md) is the design in full — how
the model is kept from seeing the map, what the RL actually has to learn, how the simulator and the
floor are kept from drifting apart, and the ideas already ruled out with the reasons they were.
[`work_division.md`](work_division.md) says who is building which part of it.
