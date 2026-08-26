# HANDOFF — prototype 1

Scoped to `prototype1/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md).

---

## Next conversation: read every line of this

**The next session is a code read, not a build.** Opus in VS Code, medium–high effort, one file at a
time. Nothing here is trusted to be understood and the point is to end that. Dependency order, which
is also the reading order — ~2,600 lines of source, ~1,400 of tests:

`settings.py` (knobs) → `config.py` (maps) → `world.py` (state) → `nav.py` (planner) → `sight.py`
(the sense) → `skills.py` (the interface) → `chat.py` (the model loop) → `console.py` → `render.py`
→ `main.py`. **Only the last two touch pygame**, which is why no test needs a display.

Read [`FINDINGS.md`](FINDINGS.md) first — most odd-looking code is there because of something in it,
and the comments name which. Then [`NAVIGATION.md`](NAVIGATION.md) beside `nav.py`,
[`SIGHT.md`](SIGHT.md) beside `sight.py` and `skills.py`.

**Check these three invariants really hold** — all fail silently: `nav.known()` is the only read of
the grid anywhere (two tests count it); the view is never stored in `chat.messages`; every world
change happens on the main thread in `pump()`.

## Where it stands

**Gemma can see, and it can walk.** Built 2026-08-26. A view block injected on every request and two
tools, `goto` and `distance`. It reads its own coordinates and does the arithmetic — *"go 6 blocks
north"* from (1,15) comes back `goto(1,9) → DONE(steps=6)`.

```sh
.venv/bin/python game/main.py --gemma   # steps instead of a clock, gemma in a pane
```

## What the runs cost to learn

**[`FINDINGS.md`](FINDINGS.md) has eleven items — read it before touching the interface.** Three
recur: *a field is not a sentence*, *check the fact not the label*, and *a call that vanishes is the
lying success code inverted* — all three were answers that were true and useless, and all three were
found by reading a tape rather than by testing.

**Two measurements, so nobody re-derives them by argument.** Gemma reads a named cell off the grid
correctly **5 times in 10**, and 5 in 10 with thinking on at 187× the wall clock — assume any
coordinate it counts out of the grid is wrong, and leave `MODEL_THINK` off. And shrinking the view
by dropping empty cells makes it **five times bigger**: the grid is 196 tokens where coordinate
lists are 972. The map was never the expensive part; the prompt and tool schemas are, at ~1,300.

## Next: notes, then `interact`

**Notes and `interact`, in that order — every remaining failure is one of the two.** It cannot
remember what it has done, and there is nothing to do when it arrives. Neither is a perception
problem and no prompt touches either. `interact` is blocked by three couplings in `world.py`:
[:210](game/world.py:210), [:266](game/world.py:266), [:289](game/world.py:289).

**Then `mark()`, which brings `avoid="auto"` back.** Refused by name today because gemma cannot mark
a cell, and advertising it would describe a capability whose other half does not exist — with
`avoid` described merely as "optional", gemma volunteered `avoid="auto"` unasked.

**`NAV_REPLANS` is an ablation, not a comfort setting.** Left at 5; run it at 0 before concluding
anything about whether gemma reasons about failure.

## The human-played runs, 2026-08-26

Ishan plays it, Claude reads the tape afterwards — the order from here. **It works: 397 of the
plaza's 399 cells mapped in eight turns**, off nudges rather than rules.

**Telling it to aim far was the single biggest change.** Walks went from one cell at a time to 17,
18, 21, 24 and 35 steps, one finding six walls. It extrapolates past the edge unprompted.

**The 22% that is wasted has one cause.** 14 of 64 calls returned `steps=0`, nearly all aimed at the
border wall — `goto(20,17)` four times running — because the rim is `#` and a known wall is
deliberately `UNREACHABLE`. Aiming far works; the far thing is usually the wall around the world.
**Cheapest fix: have `UNREACHABLE` on a known wall name the nearest reachable cell instead.**

**It re-walks corridors it has already mapped** — ~100 steps along plaza row 1 in one run. It knows
the cells are there and has no record of having been down them. No prompt fixes this.

**Context ran out at 40 calls** (`16162/16384`). Raising `MODEL_CTX` is not the fix and is not free:
`ollama ps` shows 10.85 GB total with only **3.69 GB on the GPU**, so 7.2 GB already runs on CPU and
a bigger KV cache pushes more off. The nightly reset and the notes file are the design's own answer;
`gemma4:e4b-it-qat` (6.1 GB) changes the hardware picture.

## Still true, still not done

Persistence does not exist and prototype 1 is several days long. [`DESIGN.md`](DESIGN.md) still asks
two questions FINDINGS answered; the step budget is still a guess. `M` revealing an area's extent is
**settled deliberately** — the view discloses it, because `nav.known()` already does. **The vault is
what all of this is for**: every route crosses pits, `avoid="auto"` is not offered, and gemma has to
override a habit it spent days forming.

**Never quote one run as a result**: the same script on the same build gave 31 calls, then 14, then
32, and the 31 → 14 drop went into an earlier draft of this file as a win. It was luck.

`economy.py` prints the ladder and shouts `INVERTED` if a change breaks it. **The 600-step day is
not balance-neutral**: snake's edge over flappy went +3.7% → +17.6%, the vault chain 1.0 days of
farming → 0.6. Still guesses. **Run all five tests after touching a map.**

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
