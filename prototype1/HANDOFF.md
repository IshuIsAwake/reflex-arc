# HANDOFF — prototype 1

Scoped to `prototype1/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md).

---

## Where it stands

**The world is built and `goto` works.** Three areas, keyboard controls, A\* behind a console. No
model in it yet. Run it and the tests:

```sh
cd prototype1                              # first-time setup is in README.md
.venv/bin/python game/main.py
.venv/bin/python game/test_world.py
.venv/bin/python game/test_nav.py
```

`game/settings.py` is every knob. `game/config.py` is the maps and the drawing. `game/world.py` is
pure state with no pygame in it — **that is the file the planner drives.** `game/nav.py` is the
planner, `game/console.py` the human's way into it. Design in [`DESIGN.md`](DESIGN.md), controls and
world tour in [`README.md`](README.md), the planner in [`NAVIGATION.md`](NAVIGATION.md).

Numbers are guesses and lenient on purpose for now. `game/economy.py` prints what they are worth
and is the thing to run after touching any of them — see **Balance** below.

## The planner, built 2026-08-25

Press `T`, type `goto 19 13`. It prints the exact string gemma will get. Every decision and every
rejected alternative is argued in [`NAVIGATION.md`](NAVIGATION.md) — read it rather than re-deriving.
Closed there: face-to-face stopping, `NAV_REPLANS = 5`, antidotes not ending a trip, gates aimed at
rather than routed through, and `UNREACHABLE(avoid)` as its own answer.

**Never let anything read `Area.at` without `Area.visible`.** It returns ground truth at every fog
setting. That is the one edit that breaks this silently, and it applies to `look()` next just as much
as it did to the planner — see the trap section in NAVIGATION.md and the two tests it names.

## Next: the rest of the skill interface

`console.py` covers `goto` and `distance`. Missing: `look()`, `interact(thing)`, `play(game)`,
`buy(item)`, `read_notes`/`write_notes`, `end_day`. **The failure codes are the schema of the notes
file** ([`DESIGN.md`](DESIGN.md) §What the model gets), so settle the whole interface before writing
the Ollama loop. Build it against the console first — it is the same driver gemma will use.

**A spike built all of it in one go and was reverted on 2026-08-26**; it survives on the
`spike/gemma-integration` branch. **Read [`FINDINGS.md`](FINDINGS.md) first** — it has what that
spike cost to learn, an order to rebuild in, and bugs no review would catch.

**Three couplings in `world.py` have to be broken before any of it fits.** Found 2026-08-25, not yet
touched:

1. **`interact()` takes no argument** ([world.py:203](game/world.py:203)) — it acts on the first
   adjacent thing `facing()` returns. The skill is `interact(thing)`, so it needs a name or a cell,
   an adjacency check, and `NOT_HERE`.
2. **Interacting with a terminal auto-plays it** ([world.py:259](game/world.py:259)), which makes
   `play(game)` redundant and hides a cooldown decision inside a movement one. Split them: interact
   discovers the terminal, play spends the cooldown.
3. **`play(game, ch)` needs the tile character** ([world.py:282](game/world.py:282)) to look up
   `NEEDS_KEY`. A skill call has a name, not a char.

**`look()` has no home yet.** The "a terminal reads `discover` until you walk up to it" rule exists
only in [`render.py:62`](game/render.py:62), which is pygame-land and cannot be imported by the model
loop. Move it into `world.py` and have both callers share it, or the human and the model will drift
apart on what a thing is called.

**Before the first run:** set `settings.DAY_MODE = "gemma"`, and solve saving — nothing persists
between processes, and prototype 1 is several days long.

Three things are still open and are listed at the bottom of [`DESIGN.md`](DESIGN.md): whether the
notes file is injected each day or read via `read_notes()`, the size of the step budget, and whether
gemma's rationale is a required field on every call.

**Settled, not to be reopened:** both day modes are built and cooldowns tick per step in gemma mode,
so they are paid in walking not waiting ([`README.md`](README.md) §Turning the knobs). Marks stay in
world state, not the notes file. `world.history` is one record per day — hang model latencies there.

**The vault is what all of this is for** — every route in crosses pits on purpose and `avoid="auto"`
is not offered for it, so gemma must override a habit it spent days forming. Argued in
[`DESIGN.md`](DESIGN.md) §The chain worth watching.

## Balance

`python game/economy.py` prints the ladder and shouts `INVERTED` if a change breaks it. It reads
`[ok]`: cartpole < flappy < snake, per step and after the walk from spawn.

**Coins per day *after the walk* is the column that decides anything.** Gemma respawns in the Plaza
and the snake terminal is 66 steps away, out of the same 400. Snake paid 145 once, looked better per
step, and still was not worth going to. Margins are ~4% a rung after travel, on purpose, so the
ladder is worth climbing without farming being a strawman. **All still guesses**, and lenient ones.

Steps spent clearing a cooldown can be spent walking *somewhere useful*, so exploring is partly
subsidised by a cost farming pays in pointless back-and-forth. That may matter more than the table.

**Run both tests after touching a map.** `test_world.py` flood-fills all three areas and checks
every object, pit and gate is reachable, links land somewhere walkable, `settings.BAGS` matches the
`$`/`*` tiles, and the vault costs exactly `POUCH_UPGRADED` antidotes. It has already caught two
sealed rooms and a vault needing four antidotes when the pouch holds three.

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
