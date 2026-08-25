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

`game/settings.py` is every knob. `game/config.py` is the maps and the drawing. `game/world.py` is
pure state with no pygame in it — **that is the file the planner drives.** `game/nav.py` is the
planner, `game/console.py` the human's way into it. Design in [`DESIGN.md`](DESIGN.md), controls and
world tour in [`README.md`](README.md), the planner in [`NAVIGATION.md`](NAVIGATION.md). Numbers are
guesses and lenient on purpose; `game/economy.py` prices them — see **Balance**.

## The planner

Press `T`, type `goto 19 13`. It prints the exact string gemma will get. Every decision and every
rejected alternative is argued in [`NAVIGATION.md`](NAVIGATION.md) — read it rather than re-deriving.

**Never let anything read `Area.at` without `Area.visible`.** It returns ground truth at every fog
setting. That is the one edit that breaks this silently, and it applies to `look()` next just as much
as it did to the planner — see the trap section in NAVIGATION.md and the two tests it names.

Closed 2026-08-26, both found by reading a run off the screen rather than by a test. **The map draws
the plan and the walk together** — `world.last_walk` is every cell actually stepped on, handed over
by reference so a per-step watcher needs no second channel; the walk can never cross a wall and the
plan can, so where they disagree is where the fog lied. **`DONE` at a solid target carries
`beside=`**, ported from the spike, and this time the field and the guard keeping it off walls name
each other in both files — because the fix for one of those bugs is what caused the other.

**`NAV_REPLANS` is an ablation, not a comfort setting.** At 5 one `goto` makes up to six plans and
reports every wall it met, so an unmapped maze falls in two calls; at 0 it hands control back on the
first surprise. The dial moves the searching across the seam — at 5 the skill does it, at 0 the
planner does — which is this project's own question in miniature. Steps are charged either way; a
replan buys model calls, not distance. Left at 5 on purpose. Run it at 0 before concluding anything
about whether gemma reasons about failure, and expect fog to cost dozens of calls a day when you do.

## Next: the rest of the skill interface

`console.py` covers `goto` and `distance`. Missing: `look()`, `interact(thing)`, `play(game)`,
`buy(item)`, `read_notes`/`write_notes`, `end_day`. **The failure codes are the schema of the notes
file** ([`DESIGN.md`](DESIGN.md) §What the model gets), so settle the whole interface before writing
the Ollama loop. Build it against the console first — it is the same driver gemma will use.

**Read [`FINDINGS.md`](FINDINGS.md) first.** It is what the reverted gemma spike cost to learn — six
bugs and four decisions, most invisible to a code review — and it ends with the order to rebuild in.
The spike itself survives on `spike/gemma-integration`.

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
only in [`render.py:62`](game/render.py:62), which is pygame-land and cannot be imported by the model
loop. Move it into `world.py` and share it, or the human and the model drift on what a thing is
called. **Before the first run:** set `settings.DAY_MODE = "gemma"`, and solve saving — nothing
persists between processes and prototype 1 is several days long.

**[`DESIGN.md`](DESIGN.md) still lists two questions FINDINGS has since answered** — notes injected
into the day's first message rather than fetched, and a `why` required on every call. Fold the
reasoning back or it gets re-argued. Still open there: the step budget, and whether `M` should reveal
an area's extent.

**Settled, not to be reopened:** both day modes are built and cooldowns tick per step in gemma mode,
so they are paid in walking not waiting ([`README.md`](README.md) §Turning the knobs). Marks stay in
world state, not the notes file. `world.history` is one record per day — hang model latencies there.

**The vault is what all of this is for** — every route in crosses pits on purpose and `avoid="auto"`
is not offered for it, so gemma must override a habit it spent days forming.
[`DESIGN.md`](DESIGN.md) §The chain worth watching.

## Balance

`game/economy.py` prints the ladder and shouts `INVERTED` if a change breaks it: cartpole < flappy <
snake, per step and after the walk from spawn. **Coins per day *after the walk* is the column that
decides anything** — the snake terminal is 66 steps from the Plaza spawn, out of the same 400.
Margins are ~4% a rung after travel, on purpose. All still guesses, and lenient ones.

**Run both tests after touching a map.** `test_world.py` flood-fills all three areas and checks every
object, pit and gate is reachable, links land somewhere walkable, `settings.BAGS` matches the `$`/`*`
tiles, and the vault costs exactly `POUCH_UPGRADED` antidotes.

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
