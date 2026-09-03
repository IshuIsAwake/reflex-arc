# Who owns what

Allocated, as of 2026-09-04. The hackathon is close enough that these are assignments, not
starting points. If your part turns out to need something from someone else's, say so the day you
find out.

Read [`README.md`](README.md), then [`ROVER.md`](ROVER.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).
The long version of the rover design, with the reasoning and the things already ruled out, is
[`rover_ideas.md`](rover_ideas.md) — go to the section that covers your part.
[`repo_rules.md`](repo_rules.md) before you push.

---

## Nithin — hardware integration

Getting a decision from the laptop to the wheels. The rover is built: six wheels, a Raspberry Pi,
a motor driver, a buck converter, no sensors and no brain.

- The link from the laptop to the rover, and keeping it working with an artificial delay on it.
- The controller on board that takes "waypoint at this speed" and closes the loop. The policy emits
  the waypoint; nothing clever runs on the rover.
- Where the real machine disagrees with the simulator that issued the command, measured rather than
  guessed — drive it up ramps at a few grades and fit the curve.

Detail: [`rover_ideas.md` § Sim and reality](rover_ideas.md).

## Abhishek and Koushik — Unity and the RL

The simulator and the policy that drives one cell at a time.

- The Unity world: slopes, sinkholes, pushable blocks, and a battery cost that depends on grade.
- The policy that crosses a cell, and evidence that it worked rather than got lucky.
- `goto()` returns an estimated battery cost alongside its failure code. The planner budgets what
  the policy spends, so that number is an interface obligation, not a nice-to-have.

Detail: [`rover_ideas.md` § What the RL does](rover_ideas.md).

## Harshvardhan — Ingenuity and computer vision

Two jobs that share a camera.

- **Ingenuity, and how it gets nerfed.** Flying ahead to see ground the rover has not driven is
  powerful, so it has to cost something: a flight budget per day, and the window has to be near the
  rover. Both are true of the real Ingenuity. Free looking means the fog is gone by mid-morning and
  there is no decision left in the project.
- **OpenCV.** Find the rover in the overhead frame and report position and heading — printed ArUco
  tags, no dataset. Then the floor: walls, boxes, sinkholes, by colour. Threshold in HSV, not RGB —
  classroom fluorescents are uneven. Do not reuse a colour between terrain and rover markers.

Detail: [`rover_ideas.md` § How the model sees, § Sim and reality](rover_ideas.md).

## Harshita — objectives, hazards, and other models

What the rover is for, and what goes wrong.

- **Objectives.** What it is sent to do, what counts as done, and in what order they can be
  discovered.
- **Hazards.** Sandstorms and earthquakes. These are overlays on a region, not changes to the
  geometry — a corridor becomes unsafe while the walls stay where they are. Hazards can appear
  mid-day; geometry only changes between days.
- **Other LLMs in the simulation.** More than one model in the world, and what they are for.

One rule that is not negotiable and is easy to break by accident: the **surprise hazard family is
held out of training**. If a hazard of that kind ever appears mid-expedition while the policy is
learning, the category is in the distribution and the headline experiment is gone. Read
[`rover_ideas.md` § The surprise](rover_ideas.md) before adding anything to the hazard config.

## Ishan — the planner and the interface

prototype3, and the seam every other part plugs into.

- The map encoding — run-length, so a 32×32 grid costs a few lines of context instead of a
  thousand tokens.
- The `end` skill. Ending a day is a decision the model makes, not a timer that fires.
- Fog: what the model is allowed to know, enforced in software rather than by being polite about it.
- Scratchpad and memory — what carries across a day, and what expires. Facts about the world have a
  validity horizon; facts about yourself do not.
- The skill interface. Signatures, arguments, failure codes. This is what lets the four tracks above
  be built at the same time instead of one after another, so it freezes early and changes loudly.

## Shared

- **Camera setup — Ishan and Abhishek.** Mounting, framing, the grid drawn onto the image, and the
  one overhead frame that generates the simulator's map so the two maps cannot drift.
- **Integration — Ishan, Abhishek, Nithin, Harshvardhan.** Laptop to rover to camera to simulator to
  model, end to end. This is where projects this size die, and it is not a step at the end.

---

## How this works

Whoever owns a part writes it down, in the repo, in the file that covers it. Not a separate note,
not a chat message.

The parts connect through the skill interface, so it is the one thing that cannot drift quietly.
Rejected ideas keep their reasoning in the document that rejected them, so nobody rediscovers them
in November.
