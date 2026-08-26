# HANDOFF — prototype 1

Scoped to `prototype1/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md).

---

## Next conversation: read every line of this, then build `interact`

**The next session is a code read, not a build.** Opus in VS Code, medium–high effort, one file at a
time. Nothing here is trusted to be understood and the point is to end that. Dependency order, which
is also the reading order — ~2,600 lines of source, ~1,400 of tests:

`settings.py` (knobs) → `config.py` (maps) → `world.py` (state) → `nav.py` (planner) → `sight.py`
(the sense) → `skills.py` (the interface) → `chat.py` (the model loop) → `console.py` → `render.py`
→ `main.py`. **Only the last two touch pygame**; everything else runs headless, which is why all
five test files need no display.

Read [`FINDINGS.md`](FINDINGS.md) first — most odd-looking code is there because of something in it,
and the comments name which. Then [`NAVIGATION.md`](NAVIGATION.md) beside `nav.py`,
[`SIGHT.md`](SIGHT.md) beside `sight.py` and `skills.py`.

**Check these three invariants really hold**, because all three fail silently: `nav.known()` is the
only read of the grid anywhere (two tests count it); the view is never stored in `chat.messages`;
every world change happens on the main thread inside `pump()`.

## Where it stands

**Gemma can see, and it can walk.** Built 2026-08-26. A view block on every request and two tools,
`goto` and `distance`. It reads its own coordinates and does the arithmetic: *"go 6 blocks north"*
from (1,15) comes back `goto(1,9) → DONE(steps=6)`.

```sh
.venv/bin/python game/main.py           # the human's game, unchanged
.venv/bin/python game/main.py --gemma   # ...steps instead of a clock, gemma in a pane
```

## What the runs cost to learn

**[`FINDINGS.md`](FINDINGS.md) has eleven items — read it before touching the interface.** The two
that will bite again: *a field is not a sentence* (the `beside=` fix was not enough, and gemma spent
a run trying to walk into a shop counter) and *check the fact, not the label* (the repeat-detector
read the return code, so the same loop wearing a different code went unnoticed for five calls).

**Two measurements, so nobody re-derives them by argument.** Gemma reads a named cell off the grid
correctly **5 times in 10**, and 5 in 10 with thinking on at 187× the wall clock — assume any
coordinate it counts out of the grid is wrong, and leave `MODEL_THINK` off. And shrinking the view
by dropping empty cells makes it **five times bigger**: the grid is 196 tokens where coordinate
lists are 972. The map was never the expensive part; the system prompt and tool schemas are, at a
fixed 1,028.

## Next: `interact`, and then `mark`

**`interact` is the blocking one and every run says so.** Gemma arrives somewhere and there is
nothing to do, so it re-issues `goto` — its own words: *"I don't see any obvious mechanism for
interaction yet."* Three couplings in `world.py` block it: [:210](game/world.py:210),
[:266](game/world.py:266), [:289](game/world.py:289). Now the critical path, not deferred.

**Then `mark()`, which brings `avoid="auto"` back.** Refused by name today because gemma cannot mark
a cell, and advertising it would describe a capability whose other half does not exist. Load-bearing:
with `avoid` described merely as "optional", gemma volunteered `avoid="auto"` unasked.

**`NAV_REPLANS` is an ablation, not a comfort setting.** Left at 5; run it at 0 before concluding
anything about whether gemma reasons about failure.

## The first human-played run, 2026-08-26

Ishan played it rather than Claude, which is how it goes from here. **It works.**

**A hint about the fog paid for itself.** Told *"try `goto` to a coordinate you cannot see"*, gemma
aimed at (0,2) from across the map and came back `BLOCKED(at=(0,4), stopped=(1,4), steps=26)` —
twenty-six cells of map from one call, off a nudge rather than a rule.

**It re-walks ground it has already mapped**, 45+ steps of it, because it has no record of where it
has been. The notes file does not exist.

**Context ran out at 40 calls** (`16162/16384`, the morning being dropped). Raising `MODEL_CTX` is
not the fix and is not free: `ollama ps` shows 10.85 GB total with only **3.69 GB on the GPU**, so
7.2 GB already runs on CPU and a bigger KV cache pushes more off. The nightly reset and the notes
file are the design's own answer; `gemma4:e4b-it-qat` (6.1 GB) changes the hardware picture.

## Still true, still not done

Persistence does not exist and prototype 1 is several days long. [`DESIGN.md`](DESIGN.md) still asks
two questions FINDINGS answered; the step budget is still a guess. `M` revealing an area's extent is
**settled deliberately** — the view discloses it, because `nav.known()` already does. **The vault is
what all of this is for**: every route in crosses pits, `avoid="auto"` is not offered for it, and
gemma has to override a habit it spent days forming.

**Never quote one run as a result.** The same script on the same build gave 31 calls, then 14, then
32 — a 31 → 14 drop went into an earlier draft of this file as a win and was luck. What repeated:
the cap fires at most once a turn, `bad_args` stays 0 (56 calls), and "go six blocks north" landed
right three times out of three.

`economy.py` prints the ladder and shouts `INVERTED` if a change breaks it. **The 600-step day is
not balance-neutral**: snake's edge over flappy went +3.7% → +17.6%, the vault chain 1.0 days of
farming → 0.6. Still guesses. **Run all five tests after touching a map.**

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
