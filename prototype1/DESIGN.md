# Prototype 1 — Songclave

**A small world where a language model earns coins at games it is not very good at.**

The point is not the game. It is to watch `gemma4:e4b` decide, on a laptop, with no hardware and no
trained policies in the way. Gemma has knowledge and no hands. The minigame policies have hands and
no knowledge. Everything interesting happens in the gap.

This is the door game from [`../docs/course.md`](../docs/course.md) §14, grown a map.
It is a lab, not a deliverable.

## The question it asks

Gemma spawns in the same room every day with a safe, boring, always-available income source, a
fixed budget of moves, and a world it knows nothing about.

**Does it get curious, or does it farm?**

Everything in the design exists to make that a genuine dilemma. If farming the safe game all day
wins, gemma will farm and it will be right. If exploring obviously wins, farming is a strawman and
the answer means nothing. The numbers get fixed by watching, not by argument.

## What is built

Three areas, playable now by a human on the keyboard, and `goto` behind a console. The world exists
first; the model drops in behind it. Details and controls in [`README.md`](README.md).

**Plaza** — spawn, and the only area whose map is free: a notice board hands it over. A cartpole
terminal, a locked flappy terminal, a shop, a locked gate east. The northern half is a maze with a
coin bag at the end of it, because the first day otherwise has more time in it than things to do.

**Savana** — through the east gate. A maze in the north-west holding a lost bag with *this area's
map only*, an open field with a coin bag, a gate south, and the tribe counter in the far south-east
corner, deliberately as far from the entrance as the area allows.

**Savana 2** — through the south gate, and you arrive with no map at all. A hard maze, a lost bag
holding its map and one free antidote, the snake terminal in the bottom-right, and the vault.

### The chain worth watching

Find the tribe → pay 300 for the tool pouch → carry three antidotes instead of one → cross three
rings of snake pits → open the vault for 1000.

That is instrumental reasoning: spending on a capacity upgrade that pays nothing at the moment of
purchase. It is the hardest problem in the world and nothing announces it. The vault is labelled
`discover`, exactly like a terminal it has not walked up to. Gemma has to reach it, open it, and
only then find out what it was worth — and by then the antidotes are spent.

**The vault is also the one place `avoid` must be overridden.** Every route in crosses pits on
purpose, and `avoid="auto"` is not even offered for it. A planner that has learned "pits are bad,
always avoid" cannot open it. Whether gemma can tell the difference between a rule and a habit is
the sharpest thing this world asks.

The tribe is the gentle version of the same lesson: a two-turn pit maze guards it, where each wrong
straight-ahead is a pit. Solvable once mapped, and it costs nothing if you know the way.

## Fog, and the two things it never reveals

Gemma does not see the screen. The renderer shows the human everything; what reaches the model is
filtered in software, so at any moment we know exactly what it had been told and can check its
beliefs against the truth.

- An area whose map has been acquired is fully revealed.
- An area without one is visible only within a small radius, and cells stay known once walked.

**Snake pits are exempt from all of it.** No radius, no map, no `look()` ever reveals a pit. They
are revealed by being fallen into. Get this wrong and the avoid-list mechanic dies silently, and the
first symptom is wondering why nothing ever goes wrong.

**Names are earned too.** A terminal reads `discover` until gemma walks up to it. You find out what
a game is by going to it, not by looking at it from across the room. The panel of cooldowns lists
only terminals it has reached and holds the key for.

Pits cost a small flat sum and teleport you home. The walk is the real penalty. Keep the coin loss
low — the first fall into every pit is unavoidable by design, so a heavy penalty taxes exactly the
exploration this is trying to observe.

## What the model gets

The skill interface, which is the blocking artifact here as everywhere. **The failure codes are the
schema of the notes file** — they are what gemma has to write down and reason about.

```
look()                     contents and coordinates of the current area, fog-filtered
goto(x, y, avoid=[...])    A* over the map as gemma knows it; pits trigger on contact
goto(x, y, avoid="auto")   ...avoiding every cell gemma has marked. Visited targets only
interact(thing)            gates, terminals, bags, counters
play(game)                 run the policy -> coins, or not
buy(item)                  at a counter only
read_notes() write_notes() the file
end_day()
```

| call | returns |
|---|---|
| `goto` | `DONE` · `TRAPPED(at)` · `BLOCKED(at, stopped, walls)` · `LEFT_AREA(area, at)` · `UNREACHABLE` · `UNREACHABLE(avoid)` · `NOT_VISITED` · `OUT_OF_STEPS` |
| `interact` | `DONE` · `LOCKED(needs: item)` · `ALREADY_DONE` · `NOT_HERE` |
| `play` | `WON(coins)` · `LOST` · `ON_COOLDOWN(seconds)` · `LOCKED(needs: item)` |
| `buy` | `DONE` · `INSUFFICIENT_COINS` · `NOT_STOCKED` |

**`goto` plans over the map gemma has, not the map that exists.** Walls it has not seen are not in
the plan, so it walks the route until reality refuses it, stops there, and reports what it hit:
`BLOCKED(at=(10,6), stopped=(10,5), steps=26, walls=[...])`. A blocked move is therefore not a
wasted one — it is how the map gets filled in. Nothing about this is omniscient, and that is what
keeps maps worth buying. **An antidote absorbing a pit does not end the trip**; only falling in with
an empty pouch does, because only that moves gemma to another room. Built, with the reasoning, in
[`NAVIGATION.md`](NAVIGATION.md).

**`avoid="auto"` is the commute, not the expedition.** It skips every cell gemma has marked, and is
legal only for a destination gemma has already stood on. Going back to the tribe or the snake
terminal is one call. Going somewhere new, or after a one-time pickup like a coin bag or the vault,
means naming the coordinates to dodge by hand. So the two forms of `avoid` have genuinely different
jobs rather than one shadowing the other.

`unlock()` is deliberately absent — holding the key is a precondition the world checks, and
`interact(east_gate) → LOCKED(needs: savana_key)` teaches gemma more than a separate verb would.
Gates open by interacting and never by walking into them, so opening one stays a visible decision
rather than a side effect of moving. `buy()` stays separate because it is the only action that
spends the scarce resource, and it should stand out in the transcript.

**`write_notes` replaces the whole file rather than appending.** Append-only means gemma can never
correct itself, and correction is the thing most worth watching — the corridor it marked dangerous
that never was, the game it wrote off after two bad runs. Over-generalising from a tiny sample is a
known failure mode and it is only observable if revision is possible.

## The day

**Two modes, one world.** A human day is five minutes of wall clock. A gemma day is a fixed budget
of *steps* — one per tile walked, one per interact, play or buy — and the clock becomes a stopwatch
that only watches.

The reason is that a model's thinking time would otherwise set the difficulty. Longer notes mean
slower calls mean fewer decisions, so gemma would appear to get worse over a run while actually only
getting more to read. Counting steps makes the day the same size on any machine, makes two runs
comparable, and gives walking an honest fixed price — which is the only thing that makes putting the
tribe in the far corner mean anything. Cooldowns count in steps too, or thinking would recover them
for free.

Coins, world state and the notes file all persist; the conversation does not —
each day is a fresh context, and **the notes file is the only thing gemma carries across.** That is
the whole architecture in one sentence, and it is why the file matters more than the prompt.

The map is static and does not reshuffle, so day one is the exploration story and later days are
optimisation. An accepted limit of prototype 1, taken because the goal is to read its reasoning
rather than to measure a learning curve.

## Stub the games first

`play(game)` is a weighted coin flip against a fixed win rate with a cooldown. Real policies go in
behind the same interface. Building the planner against scripted stubs is the project's standing
doctrine and it is the difference between a working prototype and a stalled one.

When the real policies arrive: **train them all for the same ten minutes and let them land where
they land.** Cartpole will come out near-perfect, snake mediocre. That unevenness is not a defect to
polish out — it is the thing gemma has to discover about its own body, by losing cooldowns to a game
that pays the most and works the least.

## Numbers

**Every one of these is a guess.** They live in [`game/settings.py`](game/settings.py) and they will
be wrong. You cannot balance a world you have not watched anything play. The current payouts are
deliberately generous to make human playtesting quick, which almost certainly makes farming too
strong for the real experiment.

If the ladder is too slow, **scale the payouts, not the cooldowns** — cooldowns cap each game's
daily yield and are what force the ladder to be climbed at all. Prices are the cheap knob.

`game/economy.py` prints coins-per-step for the current numbers **and the same figure after the
walk from spawn**, which is the one that decides anything — the snake terminal is 66 steps away and
gemma starts every day in the Plaza. A game can pay better per step and still not be worth going to.
It shouts `INVERTED` if a change ever makes an earlier rung beat a later one.

## What to watch

- **First purchase.** A key, an antidote, or nothing.
- **Pit recall.** Diff its `TRAPS:` notes against ground truth. Does it then pass them to `avoid`?
  Writing it down and not using it is a different failure from not noticing.
- **Revision.** Does a wrong note ever get corrected, or does it harden?
- **The tribe chain.** Does it buy a capacity upgrade that pays nothing when bought?
- **The vault.** Does it walk into pits on purpose, having learned not to?
- **Snake.** Pays the most, works the least. Does it notice, and after how many days?

## Not in prototype 1

Deferred, with reasons, so they do not get rediscovered:

- **Four or more regions.** The three-area chain already carries the instrumental-reasoning test.
  More rooms is more walking, not more question. Prototype 2.
- **Reshuffling pits and items between days** — what would turn one observation into a repeated
  measurement. The strongest candidate for prototype 2.
- **Three-level game upgrades.** Pure optimisation. A lookup table does this perfectly, which makes
  it the part of the design least connected to the thesis.
- **Auto-miner.** Deferred gratification through a pit corridor is a lovely test, but once bought
  every strategy converges and every later day is contaminated. Better later as a win condition.
- **Flea brew, instant cooldown ender, 2× coins, teleport waypoints.** Scalar multipliers. No
  dilemma in any of them.
- **Dynamic hazards** — a corridor that becomes unsafe and later clears. That is the held-out
  surprise family from [`../ROVER.md`](../ROVER.md) and it belongs nowhere near this one.

## Open

- **Whether the notes file is injected each day or read via `read_notes()`.**
- **The size of the step budget.** 400 is a guess and nobody has watched anything spend one.
- **Whether gemma's rationale is a required field in every call** or a free-text line between them.
- Pressing `M` reveals an area's *extent* even with no map — you learn how big it is and how many
  cells exist, just not what is in them. Deliberate for now, and worth a decision before the model
  run.
