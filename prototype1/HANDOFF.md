# HANDOFF — prototype 1

Scoped to `prototype1/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md).

---

## Where it stands

**The world is built, `goto` works, and the map now shows what it actually did.** Three areas,
keyboard controls, A\* behind a console. No model in it yet. From `prototype1/`, setup in README:

```sh
.venv/bin/python game/main.py        # and test_world.py, test_nav.py -- run both
```

`game/settings.py` is every knob, `game/config.py` the maps and the drawing, `game/nav.py` the
planner, `game/console.py` the human's way into it. `game/world.py` is pure state with no pygame in
it — **that is the file the planner drives.** Design in [`DESIGN.md`](DESIGN.md), controls and world
tour in [`README.md`](README.md), the planner in [`NAVIGATION.md`](NAVIGATION.md). Numbers are
guesses and lenient on purpose; `game/economy.py` prices them — see **Balance**.

## The planner

Press `T`, type `goto 19 13`. It prints the exact string gemma will get. Every decision and every
rejected alternative is argued in [`NAVIGATION.md`](NAVIGATION.md) — read it rather than re-deriving.

**Never let anything read `Area.at` without `Area.visible`.** It returns ground truth at every fog
setting. That is the one edit that breaks this silently, and it applies to `look()` next just as much
as it did to the planner — see the trap section in NAVIGATION.md and the two tests it names.

Closed 2026-08-26, both found by reading a run off the screen rather than by a test. **The map draws
the plan and the walk together** — `world.last_walk` is every cell stepped on, handed over by
reference so a per-step watcher needs no second channel. **`DONE` at a solid target carries
`beside=`**, or arriving next to a thing reads as not arriving; it and the `_targets` guard that
keeps it off walls now name each other, because the first fixed one bug by causing another.

**`NAV_REPLANS` is an ablation, not a comfort setting.** At 5 one `goto` makes up to six plans and
reports every wall it met, so an unmapped maze falls in two calls; at 0 it stops on the first
surprise. The dial moves the searching across the seam — at 5 the skill does it, at 0 the planner
does. Steps are charged either way; a replan buys model calls, not distance. Left at 5 on purpose,
but run it at 0 before concluding anything about whether gemma reasons about failure.

## Next: the rest of the skill interface

`console.py` covers `goto` and `distance`. Missing: `look()`, `interact(thing)`, `play(game)`,
`buy(item)`, `read_notes`/`write_notes`, `end_day`. **The failure codes are the schema of the notes
file** ([`DESIGN.md`](DESIGN.md) §What the model gets), so settle the whole interface before writing
the Ollama loop. Build it against the console first — it is the same driver gemma will use.

**Read [`FINDINGS.md`](FINDINGS.md) first.** It is what the reverted gemma spike cost to learn — six
bugs and four decisions, most invisible to a code review — and it ends with the order to rebuild in.

**Write it by hand. Do not cherry-pick from `spike/gemma-integration`.** Decided 2026-08-26: the
branch records what went wrong, it is not a patch to apply. Read it for a symptom, then build the
thing yourself. Its four decisions stay settled and are not re-argued. `beside=` was the one piece
taken across, and its guard was rewritten rather than copied.

**Three couplings in `world.py` have to be broken before any of it fits.** Found 2026-08-25, not yet
touched:

1. **`interact()` takes no argument** ([world.py:210](game/world.py:210)) — it acts on the first
   adjacent thing `facing()` returns. The skill is `interact(thing)`, so it needs a name or a cell,
   an adjacency check, and `NOT_HERE`.
2. **Interacting with a terminal auto-plays it** ([world.py:266](game/world.py:266)), which makes
   `play(game)` redundant and hides a cooldown decision inside a movement one. Split them: interact
   discovers the terminal, play spends the cooldown.
3. **`play(game, ch)` needs the tile character** ([world.py:289](game/world.py:289)) to look up
   `NEEDS_KEY`. A skill call has a name, not a char.

**`look()` has no home yet.** The "a terminal reads `discover` until you walk up to it" rule lives
only in [`render.py:62`](game/render.py:62), which the model loop cannot import. Move it into
`world.py` and share it, or human and model drift on what a thing is called. **Before the first
run:** set `settings.DAY_MODE = "gemma"` and solve saving — a process is not several days long.

**[`DESIGN.md`](DESIGN.md) still lists two questions FINDINGS has since answered** — notes injected
into the day's first message rather than fetched, and a `why` required on every call. Fold the
reasoning back or it gets re-argued. Still open there: the step budget, and whether `M` should reveal
an area's extent.

**Settled, not to be reopened:** both day modes are built and cooldowns tick per step in gemma mode,
so they are paid in walking not waiting ([`README.md`](README.md) §Turning the knobs). Marks stay in
world state, not the notes file. `world.history` is one record per day — hang model latencies there.

**The vault is what all of this is for** — every route in crosses pits and `avoid="auto"` is not
offered for it, so gemma overrides a habit it spent days forming. Argued in [`DESIGN.md`](DESIGN.md).

## Balance

`game/economy.py` prints the ladder and shouts `INVERTED` if a change breaks it: cartpole < flappy <
snake, per step and after the walk from spawn. **Coins per day *after the walk* is the column that
decides anything** — the snake terminal is 66 steps from the Plaza spawn, out of the same 400.
Margins are ~4% a rung after travel, on purpose. All still guesses, and lenient ones.

**Run both tests after touching a map.** `test_world.py` flood-fills the areas and checks every
object, pit and gate is reachable, links land walkable, `BAGS` matches the tiles, and the vault costs
exactly `POUCH_UPGRADED` antidotes.

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
