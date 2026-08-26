# Prototype 1 — the world

A top-down grid world you can play with the keyboard, an A\* planner you can drive by typing at it,
and `gemma4:e4b` sitting beside it with eyes and one skill. **No RL yet** — the minigames are
weighted coin flips, and real policies go in behind the same interface later.

Why it is shaped the way it is: [`DESIGN.md`](DESIGN.md). How the planner works:
[`NAVIGATION.md`](NAVIGATION.md). What the model is told: [`SIGHT.md`](SIGHT.md). What went wrong
already: [`FINDINGS.md`](FINDINGS.md). What happens next: [`HANDOFF.md`](HANDOFF.md).

## Run

```sh
uv venv .venv && uv pip install --python .venv/bin/python pygame
.venv/bin/python game/main.py           # the human's game
.venv/bin/python game/main.py --gemma   # ...steps instead of a clock, gemma in a pane
```

Run the tests after touching anything: `test_world.py`, `test_nav.py`, `test_sight.py`,
`test_skills.py`, `test_chat.py`. None of them needs Ollama running.

## Controls

| | |
|---|---|
| `WASD` | move one cell; hold to keep going |
| `E` | interact with whatever you are standing next to |
| `M` | open the area map — `WASD` moves a cursor, `X` marks a cell |
| `B` | bag — coins, antidotes, keys, maps |
| `C` | terminals — cooldowns, and which ones you have found |
| `X` | mark the cell you are standing on |
| `T` | console — type `goto` and `distance` yourself |
| `Q` | end the day early |

Under `--gemma`, four more: `TAB` types to it, `V` prints the block it is actually being sent, `N`
starts the next day once you have ended one, and the wheel scrolls the pane.

Everything is interacted with by standing **next to** it and pressing `E`, gates included — walking
into a shut gate never opens it. Snake pits are the only thing that triggers by stepping on them.

That split is deliberate: it is the same split `interact()` and `goto()` have when the planner drives
this, so opening a gate stays a visible decision instead of a side effect of moving.

At the end of each day you choose whether to continue or exit. Coins, keys, maps and your `X` marks
carry over; the message log does not.

## The console

Press `T` and drive the planner the way the model will:

```
goto 19 13                    walk there over the map you have
goto 30 16 avoid=auto         ...dodging every X you marked. Visited targets only
goto 15 10 avoid=(3,4),(5,6)  ...dodging these cells, this trip only
distance 27 5                 planned length, optimistic, costs no steps
```

It prints back the exact string gemma gets — `DONE(at=(19,13), steps=9)`,
`BLOCKED(at=(10,6), stopped=(10,5), steps=26, walls=[...])` — so playtesting the planner and reading
a model transcript are the same activity. `M` draws the last planned route in blue.

**The plan is a guess, not a map.** A\* treats fog as empty, so it will happily route through walls it
has never seen, walk until one refuses it, and report where. That is how the map gets filled in, and
it is why `distance` to somewhere unmapped always comes out too low. Rules in
[`NAVIGATION.md`](NAVIGATION.md).

## The world

Areas are larger than the window. The view scrolls to follow you and stops at the edges; `M` shows
the whole area at once, but only the parts you have earned the right to see.

**Plaza** — spawn. A notice board that hands you the Plaza map, two terminals, a shop, and a locked
gate east. The whole north half is a maze with a coin bag at the far end, which is there because the
first day otherwise has more time in it than things to do.

**Savana** — a maze in the north-west holding a lost bag with *this area's map only*, an open field
with a coin bag, a gate south, and the tribe counter in the far south-east corner behind a two-turn
pit maze.

**Savana 2** — through the south gate, and you arrive with no map at all. A much harder maze, a lost
bag holding its map and a free antidote, the snake terminal in the bottom-right, and the vault.

### Things worth knowing

**Snake pits are never drawn.** Not in the world view, not in the map view, not at any fog radius.
You find them by falling in, which costs coins and puts you back in the Plaza. That is the entire
reason the `X` marking exists — it is the human version of the notes file.

**Terminals read `discover` until you walk up and press `E`**, and so does the vault. You find out
what something is by going to it, not by looking at it from across the room. The terminals panel
lists only the ones you have reached *and* hold the key for.

**Antidotes** cost 100 and absorb exactly one snake pit — no coins lost, no walk home. You can carry
one, or three after buying `tool_pouch` from the tribe for 300. Three is exactly what the vault
costs, and nothing tells you that.

Without an area's map you see only a small radius, and cells stay visible once walked. With the map
the whole area is revealed — except the pits. Emptied bags stop being drawn.

## Turning the knobs

[`game/settings.py`](game/settings.py) holds everything worth tuning: day length, payouts, cooldowns,
win rates, shop stock and prices, bag amounts, trap penalty, vision radius, pouch sizes, a
`TIME_SCALE`, `NAV_REPLANS`, and `DAY_MODE`.

**`DAY_MODE`** is the one to know about. `"human"` makes a day 300 seconds of wall clock, which is
the nicer way to play. `"gemma"` makes a day `DAY_STEPS` actions — one per tile walked, one per
interact, play or buy — and turns the clock into a stopwatch that only records. A model's thinking
time then costs it nothing, so the day is the same size on any machine and two runs compare.
Cooldowns count in steps in that mode for the same reason.

[`game/config.py`](game/config.py) is the maps, the view size and the drawing; you only go in there
to change the world's shape. The maps are ASCII with a legend at the top.

**`NAV_REPLANS`** is how many times one `goto` quietly replans around a wall it could not have known
about before handing control back. Higher spends steps to save model calls; 0 returns on the first
surprise. Either way every wall found on the way is reported.

Run `python game/economy.py` for what the current numbers are worth per step, which in gemma mode
is the only figure that matters. It shouts `INVERTED` if a change ever makes an earlier rung beat a
later one — right now the ladder reads `[ok]`.

## What is stubbed

`play(game)` is a weighted coin flip against a fixed win rate, with a cooldown. Real RL policies go
in behind it unchanged.

## Checking it still works

```sh
.venv/bin/python game/test_world.py
.venv/bin/python game/test_nav.py
```

The first walks the world and asserts its way through. It also flood-fills every area to prove each
object, pit and gate is reachable, that each link lands somewhere walkable, that `settings.BAGS`
lines up with the `$` and `*` tiles, and that the vault costs exactly a full upgraded pouch while
the tribe costs none. **Run it after editing a map** — a sealed room is invisible until someone
wastes a day looking for it, and it has already caught two of those plus a vault that needed four
antidotes when the pouch holds three.

The second checks the planner plans over what you know and nothing more: A\* agrees with a plain BFS
on a mapped area, a plan through fog walks into walls it has never seen, and a snake pit you fell
into but never marked is *still* walked into by `avoid="auto"`. That last one has to keep passing —
if it ever fails, something started marking pits for you and the notes file has stopped being the
thing under test.

## Known rough edges

- Coins and progress do not persist between processes. Exiting loses the run.
- Payouts are generous enough that a day of farming buys both keys. Farming is supposed to be a
  temptation, not a shortcut.
- The step budget is 400 and nobody has watched anything spend one.
- Payouts are lenient and the margins between games are thin (~4% a rung after travel).
  `game/economy.py` prints the table and shouts `INVERTED` if a change breaks the ladder.
