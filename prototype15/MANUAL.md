# Prototype 14 — the manual

Everything you can do in the simulation and what it does. Setup is in [`README.md`](README.md),
and why it is built this way is in [`DESIGN.md`](DESIGN.md). In the app, `/help` in her chat and
`help` in your terminal list the same commands. Driving the real rover from it is in
[`hardware/README.md`](hardware/README.md).

**The idea in one paragraph.** She is the planner: a language model choosing where a rover on a
fogged Martian plain goes and what it does. A sol is dawn, day, dusk and night. You sit at
mission control's desk. At dawn and night you talk with her. The day is hers, on a clock
nothing pauses; you can break in with one urgent message, and she can radio you. At dusk she
reports.

## Launching

```bash
.venv/bin/python game/main.py --model gemma4:31b-cloud --sols 5 --objectives auto
```

| flag | what it does |
|---|---|
| `--arena 30\|50` | which plain; the 50 by default. The 50 hides six interests, one inside the C-shaped rock |
| `--sols N` | sols in the mission; `0` is no limit |
| `--comms on\|off` | whether anyone is at the desk. On by default with a window, off without one |
| `--objectives manual\|auto` | auto: three objectives from sol 2, one of each priority, a new set once the last is done |
| `--model TAG` | the planner, e.g. `gemma4:31b-cloud` or `gemma4:e4b` |
| `--preset design` | a 150-step battery and a 200-second day, for this launch only |
| `--resume runs/<stamp>` | carry on a kept run from the sol after it stopped |
| `--replay runs/<stamp>` | play a kept run again, exactly, with no model |
| `--outage N` | cut the cloud model off for sol N, to watch the fallback |
| `--think`, `--pause key\|none` | a reasoning trace, and the SPACE pause per leg |

## A sol, start to finish

1. **Dawn.** The day has not begun: no time passes and nothing drives. She reads her memory,
   the board and the work, and sets up her list. Talk to her and post orders. `/next` begins
   the day, or it begins 60 s after the last thing typed or said.
2. **Day.** The clock runs for 600 s, and nothing pauses it. She works in turns until she
   calls `end`, the clock runs out or the battery runs flat. She is told to keep working until
   the battery is down to the trip home or the clock is nearly out. Anything you type in her
   chat is the one urgent message. When she radios, you answer; `/next` closes the line.
3. **Dusk.** She brings her memory up to date, then reports in a few lines. You read; `/next`
   or 60 s moves on.
4. **Night.** Her list is cleared as the night begins, so what she puts on it now is the
   next day's. Talk to her. `/next` starts the next sol, or 60 s of quiet does.

The battery recharges overnight only if the rover is beside the pad. If not, it is stranded
and wakes where it stopped, on whatever charge was left.

With comms off, nobody is at the desk: every phase moves on by itself, and she has no radio.
At the end of the mission the app waits: `sols N` in your terminal plays N more, and ESC
finishes (K keeps the run). A run with no window, or a replay, never waits.

## When you can reach her, and what it costs

| when | how | what it costs her |
|---|---|---|
| dawn | words in her chat; `/order`, `/retract` | nothing |
| day | anything typed in her chat is one urgent message. It reaches her after the call in hand and ends her turn, not her day | the turn |
| day, she radios | answer in her chat; `/next [words]` closes the line | 5 steps of battery for her call and for each reply she speaks, and the clock runs throughout |
| dusk | nothing reaches her; this is her report | — |
| night | words in her chat; `/order`, `/retract` | nothing |
| comms off | nothing reaches either side | — |

## Her chat (TAB)

| command | what it does |
|---|---|
| words | at dawn and night, talk to her. By day, the one urgent message. On a radio line, your answer |
| `/next [words]` | move on: dawn to day, dusk to night, night to the next sol, or close a radio line. The words go to her with whatever comes next |
| `/order <text>` | post an order on her board, and tell her. By day this is the urgent message |
| `/orders` | show the board. `/orders clear` takes everything down |
| `/retract N` | take order N down; the rest renumber |
| `/status` | the status line, as she reads it |
| `/help` | this list |

## Your terminal (T)

For running the mission and playing by hand. A leading `/` is fine.

| command | what it does |
|---|---|
| `comms on\|off` | someone at the desk, or nobody. C does the same |
| `sols N` | N more sols in the mission |
| `place X Y high\|medium\|low COST` | an objective, on ground the rover has mapped. She sees it at once |
| `place X Y interest COST TEXT` | hide an interest. She finds it only by driving near it; TEXT is what examining it turns up |
| `goto X Y`, `distance X Y`, `execute` | drive, price a drive, or do the work, by hand |
| `help` | this list |

## Keys

| key | what it does |
|---|---|
| TAB | her chat; ESC leaves it |
| T | your terminal; ESC leaves it |
| C | comms on or off, for this run |
| P | flip the scratchpad between today's list and what lasts: her memory and the board |
| V | the exact view she was sent last |
| H | show or hide her reasoning |
| M | the map of what she has seen, over the whole window |
| O | settings, each saying when it applies |
| Q | end the day now |
| SPACE | skip the drive or the work being drawn. It also saves day time, since the clock runs while they are |
| WASD | drive by hand. Avoid it in a test: she isn't told |
| ESC | quit: K keeps the run, D discards it, ESC goes back |

While you type in her chat, the terminal or a setting, LEFT and RIGHT move the caret, HOME and
END jump to either end, BACKSPACE and DELETE work at the caret, and a held key repeats.

With the mouse, the M, T and O buttons are their keys, a click on the chat's input line is
TAB, and MEMORY at the scratchpad's top right is P (LIST flips it back). The wheel scrolls the
scratchpad when it is over it, and her chat anywhere else.

## What she can do

| skill | what it does | when | costs |
|---|---|---|---|
| `goto(x, y)` | drive there, the whole way in one call | day | a step a tile |
| `distance(x, y)` | what that drive would cost | any | nothing |
| `execute()` | do the work at the objective or interest she is beside | day | its cost in steps, and the time to do them |
| `count(kind)` | every rock formation or fog patch, with size and middle | any | nothing |
| `count_cells(x, y)` | the exact cells of one formation | any | nothing |
| `todo(text)`, `strike(n)` | add to and cross off her list | any | nothing |
| `remember(name, text)` | write or replace one entry of her memory | any | nothing |
| `forget(name)` | drop an entry | any | nothing |
| `radio(text)` | call the desk, from anywhere, with comms on | day | 5 steps, and 5 for each reply on the line |
| `end()` | end the day | day | nothing |

Each turn allows 20 drives, and 10 looks between drives. Reaching either ends the turn, and
the next one starts with both back. One call per reply, except that several writes
(`todo`, `strike`, `remember`, `forget`) all run, with the one call after them.

## What is written down

| place | who writes it | lifetime |
|---|---|---|
| her list (the scratchpad) | she does, with `todo` and `strike` | cleared when dusk ends; what she writes at night is the next day's |
| her memory | she does, with `remember` and `forget`. Up to 10 entries of 300 characters | survives every night |
| the board | you do, from her chat | until you take an order down |
| `report.md` | the record, and her dusk reports in her own words | the run |

She is told that anything she meets in the sol and wants to carry forward must go into her
memory, and anything she means to do must go on her list. She is told to keep her memory
lean:
- one subject to an entry;
- change an entry rather than add a near-copy;
- forget what's no longer true;
- don't copy what her view already shows (the map, the finished work, the board);
- keep what an interest turned out to be, since nothing else does;
- write sols as numbers: "until the end of sol 3", never "for two more sols".

## Terms

- **Sol:** one Martian day, in four phases: dawn, day, dusk and night.
- **Day:** the phase that works. 600 seconds of wall clock from the moment it begins, which
  nothing pauses.
- **Battery:** 500 steps. A tile driven, a step of work or a radio message costs from it.
  Only the pad recharges it, overnight. A flat battery ends the day. Driving and work also
  take time: each is drawn a step at a time while the clock runs.
- **Beside the pad (docked):** next to any side of the landing pad, where she recharges.
- **Stranded:** the day ended away from the pad, so there is no recharge.
- **Lost:** less charge than the shortest trip home. The mission ends.
- **Turn:** one stretch of her working, from a message to her stopping. A day has many; only
  her `end` closes the day.
- **Objective:** mission control's work, on mapped ground, with a priority and a cost.
- **Interest:** the arena's own, hidden until the rover sees it. Shown as a square on screen
  and `*` on her map. Examining it says what it is, once.
- **Urgent:** your one message by day. It ends her turn, not her day.
- **Radio line:** opened by her `radio`. Her replies on it cost battery, and it closes after
  60 s of quiet or on `/next`.
- **Comms / the desk:** whether anyone is at mission control. Off, every phase moves on by
  itself.
- **Board / orders:** your numbered standing instructions, shown to her on every request.
- **Memory:** her named entries, the only thing of hers that survives the night.
- **Fallback:** if the cloud model drops, the local `gemma4:e4b` answers until it is back.
- **Replay / resume:** play a kept run again exactly, or carry it on from its next sol.

## Scoring a run

```bash
.venv/bin/python game/score.py runs/<stamp> [runs/<stamp> ...]
```

A row per sol: battery used and left, radio spending, day seconds used, cells mapped, work
done, interests found and whether they reached her report and memory, list items and how
many copy an objective, memory size, refused calls, and how the day ended. The orders
standing each sol are listed under it, for you to judge. Several runs also get their
totals side by side.

## A run directory

Every session writes to `runs/pending-<stamp>/` as it goes. K keeps it as `runs/<stamp>/`, and a
run with no window is kept as `runs/<stamp>-headless/`. A `pending-` folder left behind is a run
that crashed.

| file | what is in it |
|---|---|
| `chat.jsonl` | everything she was sent and said, every call with its phase and clock, and its result |
| `game.jsonl` | what happened to the world: settings per sol, phases, windows, orders, placements, reports |
| `report.md` | the mission from the record, her dusk reports, then her memory, rewritten every night |
| `night.json` | what the last night kept, for `--resume` |
