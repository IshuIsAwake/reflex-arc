# Prototype 10 — one screen, one seam

Prototype 9 scaled down until there is exactly one thing to watch: the planner decides, the
real rover drives, and `plan.txt` is the only thing that crosses between them. Every leg the
planner commits to appears on disk as directions, the rover executes them and stops, and only
then does the planner get to think again. The pause is the demo.

Inherited from prototype 9 whole: the scratchpad and the memory (`notes.py`), the skills, the
chat pane, the tape.

## The seam

`plan.txt` holds one of `N`, `E`, `S`, `W` per line and nothing else. No header, no comments,
no coordinates, no leg structure.

Absolute rather than rover-relative, decided after tracing a 5×5 example by hand. Relative
directions make every turn a function of a heading the simulation never measured — `nav.py`
admits as much today — and with a pause at every leg boundary that assumed heading is exactly
where the sim's belief and the robot's reality drift apart. Absolute removes the quantity
rather than correcting it. It is also shorter: the worked example came to 1, 5 and 4 tokens a
leg against 1, 8 and 7 relative.

The cycle, per leg:

1. `goto` plans over the map the rover knows, fog assumed drivable
2. the simulation drives the plan until it arrives or runs into rock
3. **the prefix that actually worked** is written to `plan.txt`
4. the real rover replays it and stops
5. the file is wiped; if the leg ended on rock, replan and go again

The robot only ever receives moves the simulation has already proved, so it cannot be sent
into an outcrop. That is what step 3 buys, and it is why the file holds a record rather than a
hypothesis.

The model is unaffected by any of this. One `goto` returns one result however many legs it
took. `NAV_REPLANS = 5` now bounds hardware round-trips at six per call. The full journey,
detours included, lives in the tape — never in `plan.txt`, which holds the current leg only.

`BACKWARD` stops existing, and with it the turn arithmetic in `route_actions`, the heading in
the leg tuple, `--heading` in `plan_txt.py`, and the contract note about a rover that cannot
reverse. `HEADING_NAMES` is already indexed by the same `DIRS` order the old turn maths used,
so a step is `HEADING_NAMES[DIRS.index(step)]` and nothing else.

## The world

**30×30, and the rover can see again.** Ingenuity is cut. Prototype 8 blinded the rover on the
grounds that the flyer was the only eye worth having; remove the flyer from that and nothing
can see at all, and the geology question below becomes unanswerable. So driving reveals once
more, at `VISION_RADIUS = 2` — a guess sized to the smaller arena, not a swept value.

New geology: formations of six and eight cells, and one C of twelve opening east as the
unique largest. Two clear cells between formations so the flood fill and the eye agree on
where one ends. The C is what brings back the one effect the 30 used to lack — crossing its
mouth is expensive, so `goto` returns BLOCKED for a reason other than being driven at a wall.

`DAY_STEPS = 150`, and objective costs stay at 40/15/60. A crossing is about 30, so the
dearest objective plus getting there is 90: one objective a sol, with room left to explore.
Difficulty is tuned here.

**One dust storm a sol at `STORM_RADIUS = 2`.** It already behaves the way we want — an
impassable overlay reseeded each day, visible from the moment it exists, and distinct from
rock. It must stay distinct: `count` reports rock formations, and a storm counted as one
breaks the largest-formation question. `STORM_TRIES` and `STORM_MAX_CUTOFF` are dead weight
at this size.

## What is written down

Three stores, and they differ by who holds the pen.

| store | written by | lifetime | example |
|---|---|---|---|
| **orders** | the operator, at nightfall | until replaced | *finish objective 3 today* |
| **scratchpad** | the model, each morning | wiped at nightfall | *today: objectives 1 and 2* |
| **memory** | the model, before nightfall | crosses the night | *objective 3 was missed, do it today* |

Orders are new and need their own store rather than a corner of an existing one. `next_day`
clears the message log and the todos, so anything typed at nightfall is gone by morning unless
it lives somewhere that survives — and the only such place today is `memory`, which `remember`
replaces wholesale (`n.memory = text`). Put orders there and the model deletes mission control
on its next call. So: written only by the operator, read-only to her, riding in the view on
every request the way the other two already do.

The map already crosses the night, so a survey sol makes the **map** valuable. What makes
*memory* valuable is the deferral — the sixty-step objective left undone and the line that
says do it first tomorrow — which a 150-step day produces on its own.

## Nightfall

The day ends, the operator gives the rover its work, and the operator presses `N`. Most of
this exists: the operator can already type at the model and it lands in the pane as `OPERATOR`,
the prompt already tells her a human operator gives her work, and the rollover is already a
keypress. What is new is that orders may **place an objective on the map** — a cell, a
priority, a cost — and not only say things in words.

A run would typically go:

| sol | orders |
|-----|--------|
| 1 | survey only — find and report the largest formation |
| 2 | one objective placed |
| 3 | survey only |
| 4 | one objective placed |
| 5 | one objective placed in ground the rover has not been to |

That is a shape to type, not machinery to build. Sol 1 needs a stated job or it is a blank day
and `_stuck` fires; the geology question is that job, it is only answerable by driving, and it
is the natural first thing to write in the scratchpad.

## Live and replay

Two modes, because a demo and an experiment want opposite things.

**Live** — the model decides. Might be brilliant, might flop.

**Replay** — a kept tape re-issues the recorded tool calls and the model is never asked. The
tape already holds enough: `chat.jsonl` keeps every prompt and reply in full, and `game.jsonl`
keeps every world event. With no model in the loop and everything else deterministic, the same
`plan.txt` gets written and the rover drives the same route.

So the script for a scripted run is a run that already happened. Go live until a sol comes out
well, keep it, and that directory is the demo — operator orders and objective placements
included, since those are lines on the tape like anything else.

**Replay assumes the hardware obeys.** Live, the sim leads and the robot follows, so a robot
that stops early feeds back into a replan. In replay there is no planner to react: a slipped
wheel puts the rover somewhere the tape does not know about and every leg after that is wrong.
Replay still reads the robot's report at each pause and halts loudly on a mismatch.

### The determinism ledger

| | |
|---|---|
| **arena** | authored strings |
| **storm** | seeded `f"{name}:{w}x{h}:sol{day}"`, and Python seeds from the bytes via SHA-512, so `PYTHONHASHSEED` cannot reach it |
| **the day** | counted in steps, not wall-clock, so it does not depend on machine speed |
| **the view** | `_count` and `_runs` sort before emitting, so no set-iteration order reaches the model |
| **Ollama** | only `num_ctx` and `temperature` are sent — **no `seed`**. One line. |
| **animation** | wall-clock, so pacing varies between runs. Affects a video, not an outcome. |
| **the model** | **not controllable.** `MODEL_TEMP = 0.0` is greedy and usually reproduces on a fixed local build, but inference batches requests and floating-point addition is not associative, so identical prompts can give different logits depending on what else was in the batch. Hosted models are worse. One differing token cascades through the sol. |

The last row is why replay exists. Everything above it can be pinned; the model cannot, so for
anything that has to come out the same twice, take it out of the loop.

## Open

- **A placed objective needs a reachability guard.** One behind the C's closed side or under
  the storm is a broken sol that reads identically to a hard one in a transcript. Same failure
  class as the sealed pocket `test_world.py` already checks for. This is the cost of letting
  the operator place rather than only instruct.
- **`VISION_RADIUS = 2` is untested.** Set it, run a sol, look.
- **Turns are free in the budget and slow in the room.** The day is charged one step per tile
  driven, so a turn-heavy route costs the same as a straight one in the sim and considerably
  more on hardware. Already true in prototype 9; it starts to matter once a physical rover is
  in the loop.
