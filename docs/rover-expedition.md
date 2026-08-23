# The rover expedition

The hardware implementation of this project's architecture, and the hackathon track.

## The idea

Perseverance does not drive itself. A team on Earth reads yesterday's images, decides where it
should go, and uploads a plan. Ingenuity flew ahead and photographed ground the orbiters could not
resolve, and what it saw shaped the next plan. We rebuild that arrangement with a language model as
the team on Earth.

Anyone can build a robot with sensors that navigates a room on its own. That is a Roomba. This is a
rover that **thinks** — reflexes that were learned, and decisions made by a model that says out
loud, in English, why it did something.

Built in simulation first: a small world with slopes, sinkholes, pushable blocks and sandstorms that
arrive on a forecast. The rover is solar, starts at **home**, and runs on a day of three morning
minutes and two evening minutes. Objectives are scattered and must be driven to. RL learns the
traversal — where the battery goes, what ground can be crossed, which blocks move.

Then the same map goes onto a classroom floor in tape and coloured shapes: green walls, blue boxes,
red sinkholes. The rover is two motors and an ESP32, with no brain on board. The model stays on a
laptop and talks to it over the network. Put an artificial delay on that link and it keeps working.

A camera overhead does two jobs. It tracks the rover, so the simulator and the model always know
where it is. And it is Ingenuity — when the model asks to see a region, we crop that window out of
the feed and hand it over. The rest of the map stays dark until driven through or flown over.

## How the model sees

**It does not get the map.** With a full top-down view the planner's job collapses to running A\*
and reading out waypoints, and a hardcoded table should beat a language model at that. Revealing the
map in pieces changes the question from routing to information-gathering under a budget: is forty
seconds of daylight spent imaging a corridor worth more than an objective already known? It is also
the only thing that makes an experience log worth keeping, since a full map already says everything
the log would.

**Looking must cost something.** Left free, the model requests tiles from home until the fog is
gone. Two constraints fix it, both one line and both true of the real Ingenuity: **a flight budget
per day**, and **the window must be near the rover**.

**Ground truth is not what the model knows.** The camera tells *us* where the rover is, for the
simulator, the logs and the control loop. The fog lives in what goes into the model's context and is
enforced in software. With exact tracking we can measure how much had been discovered at any moment
and whether the model's beliefs were wrong.

The model gets **symbols, not pixels**. The colour scheme is already a symbolic encoding, and a
threshold pass over the crop recovers "wall here, box at (15,9), unknown beyond." Raw images to a
vision model would reintroduce a perception problem the camera removes.

**Two grids.** Fine continuous coordinates for the policy and the simulator, and ~32×32 for the
planner, cells roughly rover-sized, where a revealed patch describes in a few lines of text.

## What varies

The map is fixed. What varies must be things a human could not precompute — storm timing, sinkhole
positions, objective order. The headline experiment is *does the model beat a hardcoded table*, and
on a fixed map with nothing varying, the table wins and deserves to.

## The surprise

Simulation covers sandstorms, sinkholes, terrain and objective types, and the log fills with what
worked. Then at test time a hazard appears that was never in it — ground gives way across a corridor
that was clear all week.

The fog makes the world **unknown**. The surprise makes the model's world **wrong**. A hardcoded
table has no entry for it and a trained policy has no experience of it, so what is left is general
knowledge. This is the rover's version of the held-out protocol in [`ideas.md` §7](ideas.md).

- **Hazard overlays, not geometry changes.** A region becomes unsafe while walls stay put. In
  simulation that is a flip in a hazard layer; physically it is a shape placed on the floor. So
  **hazards can appear mid-day and geometry can only change between days.**
- **Semi-permanent, which is the interesting part.** A hazard that persists a while and then clears
  is a harder decision than one that lasts forever — route around now, or wait it out. It also lets
  the log poison itself: the model records that a corridor is impassable, the ground settles, and it
  keeps routing around clear ground for two days. That is the over-generalisation failure mode in
  [`ideas.md` §4](ideas.md), made concrete and measurable.
- Which hands the log schema a rule it did not have. **Facts about the world expire. Facts about
  yourself do not.** *The east corridor was blocked on day 2* needs a validity horizon. *I cannot
  climb a 30-degree slope* does not.
- **Hold it out from day one.** If hazards ever appear mid-expedition during training, the category
  is in the distribution and the test is gone. Written down because adding one to the simulator for
  fun would destroy the experiment without anyone noticing.
- **A family, sampled at test time**, rather than one scripted event. Members should differ in *what
  belief they invalidate* — blocking a route demands re-planning, slowing one demands re-budgeting,
  losing the home base demands both. Two hazards that block different corridors are the same test
  twice.

The rover finds out through a failure code — `goto()` comes back unsafe rather than done, and the
planner must interpret a code it has never seen in that context, which makes this a stress test of
the skill interface as much as of the model.

Measured against the table baseline on the same event: daylight lost, and whether the expedition
still completes. **Same seed for both**, or the comparison is noise. With a family the finding gets
sharper than pass or fail — *re-routes reliably, fails to re-budget when terrain slows* is a real
answer. The measurement lives in simulation across many draws; the classroom gets one draw from the
same family, which makes demo day an honest sample rather than a rehearsed set piece.

Keep the family in its own module, out of the training environment config. Not MVP either way — a
surprise only means something against a system that already succeeds without it.

## What the RL does

Terrain. Slopes make battery cost a function of grade, and that cost depends on real motor
efficiency, mass and wheel slip, so it can only be learned. Seesaw bridges make crossing depend on
approach speed and weight distribution. Jagged paths bring traction and getting stuck.

Planner and policy also come to share a currency: **battery**. The planner budgets it and the policy
spends it, which forces `goto()` to return an **estimated cost** alongside its failure code. The
skill interface is already the project's blocking artifact, and this domain puts pressure on it the
game does not.

## Sim and reality

**The camera removes half the reality gap.** The policy sees the same clean state in both worlds —
position, heading, battery, local slope — leaving only dynamics to bridge.

Track the rover with a **printed ArUco tag**: OpenCV finds it out of the box and returns position
and heading, sub-centimetre, with no dataset. Tag the pushable blocks and the simulator knows the
arena's full state continuously.

On dynamics, cheapest first. **Move the interface up** so the policy emits "waypoint at this speed"
and a dumb controller on the rover closes the loop, keeping accurate physics out of the simulator.
**Measure rather than derive** by driving the real rover up ramps at a few grades and fitting a
curve. **Randomize mass, friction and motor strength each episode** so the policy never leans on any
of them. No physics engine — a 2D heightmap, a velocity and a battery integrator is enough, and the
seesaw is two states and a tip condition.

**Generate the simulator's map from a photo of the real arena.** One overhead frame through the same
colour detector emits the grid, and the two maps cannot drift.

Build notes worth banking: threshold in **HSV**, since classroom fluorescents are uneven and RGB
fails under them. Do not reuse a colour between terrain and rover markers. Wheel odometry drifts
badly under the wheel slip that slopes cause deliberately, so use it only to fill gaps between
camera frames.

## Where to start

Tape maze on the floor, one ramp, one camera, a tag on the rover, two motors and an ESP32, a 2D
simulator, and a single day: leave home, reach a waypoint, return before dark, with the sandstorm as
an announced timer. That is a weekend. Keys, locked rooms, seesaws, extra days and real walls stack
on top and are each independently droppable.

Arena size is set by what one camera covers. Make the maze denser rather than bigger. Tape has one
cost — nothing physically stops the rover crossing a line, so walls are a software penalty and it
looks fake on camera. **Tape for the lab, walls for the shoot.**

Headcount does not parallelize this. The chain is serial: the arena cannot be built until the
terrain model is fixed, and that cannot be fixed until the real rover has been measured.

## Already considered and cut

- **Minigames** (Breakout, Tetris at physical terminals) — added to prove there was RL in the
  project, which terrain now does. Arriving is the objective; the terminal plays an animation.
- **YOLO for tracking** — needs a labelled dataset of your own rover and returns a box with no
  heading.
- **Onboard localization** — with a discovered map this becomes SLAM, which would eat the project.
  The overhead camera makes it not exist.
- **A full top-down map**, per above.
- **Raw pixels to a vision model** — a good ablation later.

## Open

- What the rover senses onboard. Sets both the observation space and the parts list.
- Whether the storm forecast is free or has to be earned.
- Day length, grid size, flight budget.

## Status and risks

**Committed, as of 2026-08-23.** This is the hackathon track and it has its own team; Hollow Knight
keeps a separate one and stays the PRJ-1 deliverable. The old worry here was that the robot is the
easier and more fun build and would quietly displace the game. It did — but by splitting into two
teams rather than by one team drifting, which is the version that costs nothing.

The arena is escape-room construction, weeks of someone's time and none of it machine learning, and
it exists for one rented day. **The classroom is a shoot. The simulator is the lab.**

Terrain does not fight back, so this track cannot carry the reactive-opponent claim. That one stays
with the game, and the pitch here leans on latency instead.
