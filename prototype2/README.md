# Prototype 2 — the rover expedition

**The build we mimic on hackathon day.** One 50×50 Martian plain, fog you can only clear by driving
through it, a landing pad at dead centre, and `gemma4:e4b` in a pane beside it with `goto` and
`distance`.

It is a rehearsal, not a research instrument. Prototype 1 answered the questions
([`../prototype1/FINDINGS.md`](../prototype1/FINDINGS.md)); this one exists so five other people can
see the vision run before the roles are divided. The design it is heading toward is
[`../ROVER.md`](../ROVER.md).

## Run

```sh
uv venv .venv && uv pip install --python .venv/bin/python pygame
.venv/bin/python game/main.py
```

Needs Ollama up with `gemma4:e4b` for the pane to answer. Everything else — driving, the console,
the map, the logs — works without it.

## Controls

| | |
|---|---|
| `WASD` | drive one cell; hold to keep going |
| `SPACE` | skip the drive being replayed and jump to where the rover already is |
| `M` | the arena map — `WASD` moves a cursor, `X` marks a cell |
| `X` | mark the cell you are on |
| `T` | console — type `goto` and `distance` yourself |
| `TAB` | talk to the planner · `ESC` stops typing |
| `V` | print the exact block gemma is being sent |
| `H` | hide or show its reasoning |
| `N` | next sol, once you have ended one |
| `Q` | end the sol · `ESC` quit |

## The arena

50 × 50, in [`game/config.py`](game/config.py). **410 rock of 2,500 cells (16.4%), one connected
region: a boulder field and nothing else.** Twenty large boulders of sixteen cells and ten medium of
nine — irregular but compact, with two clear cells between any two of them.

**Two arenas have been thrown away here, both for the same reason.** The first was 517 rock of
uniform texture, whose comment claimed boulder fields thickening toward the rim; measured, it was
21% in the outer ring against 20% in the core. The second put twelve boulders among five long
ridges at 9.6% — on screen the ridges read as drawn lines rather than geology, and four-cell
boulders read as specks. Neither is a thing worth asking a model to recognise.

Because that is what the arena is now for. **Nothing tells gemma where the boulders are** —
`things()` reports only the landing pad. Whether a 4B model can pick the lumps out of the grid,
count them and say roughly where they are is open: prototype 1 measured gemma failing to *index* a
grid (naming the cell at a coordinate, 5 times in 10), and recognising a shape is a different skill.
If it cannot, the boulders get named and the view grows a line each; if it can, the picture was
carrying more than anyone credited.

Size is still the point. A single-cell boulder is dodged by one step sideways and the route barely
changes shape; nine or sixteen cells has to be gone round, so the plan visibly gives up and commits
somewhere else. And boulders sit on the outer ring as readily as anywhere — a clear lap round the
edge is the highway the first long run ping-ponged along for 439 steps.

The rover lands at **(25, 25)** and the base pad sits directly behind it at (24–26, 26–27). The pad
is solid, so `goto(25,26)` puts you next to it and that counts as arriving.

**There is no rim wall, and that is the one deliberate departure from prototype 1.** Prototype 1
walled every area, and 22% of gemma's calls were wasted on it — the prompt says aim far, the far
thing was the border, and a known wall is deliberately `UNREACHABLE`. Off the grid already reads as
`#` through `nav.known`, so the boundary needs no tiles. Aiming at the far edge is now a real
journey.

**Fog is the only difficulty there is right now.** You see three cells as you drive and a cell stays
known once seen; the landing site starts revealed to a radius of six. There is no map to buy and no
way to reveal ground except by going there.

## What gemma gets

Two skills, `goto(x, y, why)` and `distance(x, y, why)`, and a view block appended to **every**
request that it never asks for and cannot request. The view holds the grid as it knows it, the four
cells around it named in words, how far each direction is open, and every landmark with its
coordinate. Everything exact is pre-computed, because a 4B model reads a named cell off a monospace
grid right about half the time.

The reasoning behind all of that is [`../prototype1/SIGHT.md`](../prototype1/SIGHT.md) and
[`../prototype1/FINDINGS.md`](../prototype1/FINDINGS.md); nearly every sentence in the prompt and
the tool schemas was paid for by a live run and none of it was re-derived here.

**The conversation is thrown away at nightfall.** Carrying it across sols is item 7.

## Watching it drive

A `goto` finishes instantly — it has to, because the model must be handed the true
outcome in the same breath as the call. So the world jumps, `nav` writes down what it did as a list
of events, and [`game/anim.py`](game/anim.py) replays that afterwards. **The screen lags the world
on purpose**; nothing waits on the drawing.

| | |
|---|---|
| **yellow dots** | the route `goto` believes in, drawn cell by cell before the rover follows it |
| **blue dots** | a route `distance` is pricing. Never driven, never costs a step |
| **red cross** | the cell that refused — the yellow then withdraws to the rover, a cell at a time |
| **pale trail** | ground actually covered so far this drive |

Both trails are drawn **over** the fog and neither lifts it. That is the frame worth pointing at:
yellow dots running out into pure black, because a route through unseen ground is a guess. A few
seconds later some of it turns out to be a boulder, the rover stops, the yellow retracts to the last
cell it actually stood on, and a different route draws outward from there.

The fog is held shut ahead of the rover even though the world has already lifted it, so it peels
back in time with the drive rather than all at once before it sets off.

**The planner waits for the rover, and that costs wall clock on purpose.** No request goes out while
a drive is still being drawn, so gemma sees the outcome of one call before it can make the next. An
eight-call turn runs ~45s, of which ~12s is the planner sitting still. The alternative — thinking
through the drive — hides the round trip that is the entire architectural claim: a planner seconds
away from the body it drives. `SPACE` skips a drive, driving manually skips it, and
`ANIMATE = False` turns the whole thing off.

The hold is `conv.ready`, checked before every request. The loop still pumps every frame, so
streaming text keeps arriving while the rover drives; what is held is only the next *request*.

## The console

Press `T` and drive the planner the way the model does:

```
goto 25 5                     drive there over the map you have
goto 40 40 avoid=(3,4),(5,6)  ...treating these cells as impassable, this trip only
goto 25 25 avoid=auto         ...dodging every X you marked. Visited targets only
distance 2 2                  planned length, optimistic, costs no steps
```

It prints the exact string gemma gets — `DONE(at=(40,40), steps=49, rock=[(27,33), (30,33)])` — so
playtesting the planner and reading a model transcript are the same activity.

**The plan is a guess, not a map.** A\* treats fog as clear ground, so it will route through
outcrops it has never seen, drive until one refuses it, and report where. `M` draws the last plan in
blue over the ground actually covered; wherever the two disagree is where the fog lied.

## Logs

A run streams to `runs/pending-<timestamp>/` from the first frame and `ESC` asks what to do with it:

| | |
|---|---|
| `K` | keep — renamed to `runs/<timestamp>/` |
| `D` | discard — deleted, nothing left behind |
| `ESC` | cancel, keep playing |

**Write first, decide afterwards.** Buffering until the answer arrives would lose a crashed run and
say nothing, so a leftover `pending-` directory is not an error — it is a run nobody answered for,
and it still holds everything.

Two streams. `chat.jsonl` is what gemma was told and said, with every view written out **in full**,
because context holds only the newest one and the tape is the only place a finished run can be read
back from. `game.jsonl` is what happened to the world — sols opening and closing, every HUD message,
and every drive with what it planned against what it cost.

## Turning the knobs

[`game/settings.py`](game/settings.py) holds the sol length, vision radius, model, context window,
hop cap and `NAV_REPLANS`. [`game/config.py`](game/config.py) holds the map, the tile size and the
palette.

**`MODEL_TEMP` is pinned to 0 and should stay there.** Ollama uses the model's own default (~0.8)
when it is not sent, and at that setting the model more often writes `goto(25, 15, "…")` into its
reply as text with no tool call attached. Measured over forty samples on the request the game
actually builds: **9/10 at temperature 0, 7/10 unset.** The remaining ~1 in 10 is handled by
`skills.written_call`, which reads a complete typed-out call and runs it, saying so in the pane and
on the tape. Incomplete ones are refused rather than guessed at.

**`DAY_MODE`** is the one to know about, and it is the open design question. `"gemma"` — the shipped
setting — makes a sol `DAY_STEPS` drives and turns the clock into a stopwatch that only records.
`"human"` makes it `DAY_SECONDS` of wall clock. Item 4 is deciding which the real thing uses; the
stopwatch runs and is displayed in both modes so that decision has a measurement behind it.

## Checking it still works

```sh
.venv/bin/python game/test_world.py    # flood-fills the arena: no sealed pockets
.venv/bin/python game/test_nav.py      # A* == BFS, not omniscient, one door onto the grid
.venv/bin/python game/test_sight.py    # fog holds, texture is not terrain, the view is affordable
.venv/bin/python game/test_skills.py   # the schema promises only what is wired up
.venv/bin/python game/test_chat.py     # the view is replaced not appended; the cap actually caps
.venv/bin/python game/test_logs.py     # keep, discard, and what a crash leaves behind
.venv/bin/python game/test_anim.py     # the playback draws the world and never changes it
```

None of them needs Ollama. **Run `test_world.py` after editing the map** — a sealed pocket of ground
is invisible until somebody has wasted a whole sol driving toward it, and prototype 1's version of
that test caught two.

## What is not built

The arena is bare. Nothing is scattered in it to collect and the mission asks the planner for
nothing. That is on purpose: prototype 1 measured what happens when gemma can see something it
cannot use — told to go to the shop, it arrived in one call and spent the next seven wandering. A
bare arena is the honest version of this pass.

What goes into it next is the team's to decide. Two rules hold whatever that turns out to be: **the
prompt mentions none of it**, because a capability the model is told about proves nothing about
whether it would have found it; and tests land with each addition rather than after all of them.
