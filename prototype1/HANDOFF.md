# HANDOFF — prototype 1

Scoped to `prototype1/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md).

---

## Where it stands

**Gemma can see, and it can walk.** Built 2026-08-26. It gets a view block on every request and two
tools, `goto` and `distance`. It reads its own coordinates, does the arithmetic, and *"go 6 blocks
north"* from (1,15) comes back `goto(1,9) → DONE(steps=6)`.

```sh
.venv/bin/python game/main.py           # the human's game, unchanged
.venv/bin/python game/main.py --gemma   # ...steps instead of a clock, gemma in a pane
# and run all five: test_world, test_nav, test_sight, test_skills, test_chat
```

`settings.py` is every knob, `config.py` the maps and drawing, `nav.py` the planner, `sight.py` the
sense, `skills.py` the interface, `chat.py` the model loop, `console.py` the human's way in.
`world.py` is pure state with no pygame. Design in [`DESIGN.md`](DESIGN.md), planner in
[`NAVIGATION.md`](NAVIGATION.md), **the model's side in [`SIGHT.md`](SIGHT.md)**.

**The one edit that breaks everything silently:** never read `Area.at` without `Area.visible`.
`nav.known()` is the single gated door; `test_nav.py` and `test_sight.py` both count the reads.

## What four live runs cost to learn

**Written up in [`FINDINGS.md`](FINDINGS.md), new section — read it before touching the interface.**
Eight items. The two that will bite again: *a field is not a sentence* (the `beside=` fix from August
was not enough, and gemma spent a run trying to walk into a shop counter), and *a limit enforced by
asking is not a limit* (the tool-call cap fired eight times in one turn until it stopped depending on
the model's cooperation).

**Two measurements to stop anyone re-deriving them by argument.** Gemma reads a named cell off the
grid correctly **5 times in 10**, and exactly 5 in 10 with thinking on at 187× the wall clock — so
assume any coordinate it counts out of the grid is wrong, and leave `MODEL_THINK` off. And dropping
the empty cells to shrink the view makes it **five times bigger**: the ASCII grid is 196 tokens
where coordinate lists are 972, because `(3,4)` costs six tokens and `#####` costs almost none. The
map is not the expensive part of the request — the system prompt and tool schemas are, at a fixed
1,028.

## Next: `interact`, and then `mark`

**`interact` is the blocking one and the runs say so.** Gemma arrives places and there is nothing to
do there, so it re-issues `goto`. FINDINGS' rebuild order puts the three couplings in `world.py`
first — [world.py:210](game/world.py:210), [:266](game/world.py:266), [:289](game/world.py:289) —
and they are now on the critical path rather than deferred.

**Then `mark()`, which brings `avoid="auto"` back.** It is refused by name today because gemma
cannot mark a cell, and advertising it would describe a capability whose other half does not exist.
That refusal is load-bearing: with `avoid` described merely as "optional", gemma volunteered
`avoid="auto"` unasked.

**`NAV_REPLANS` is an ablation, not a comfort setting.** Left at 5; run it at 0 before concluding
anything about whether gemma reasons about failure.

## Still true, still not done

Persistence does not exist and prototype 1 is several days long. There are no notes, so nothing
survives a night. [`DESIGN.md`](DESIGN.md) still asks two questions FINDINGS answered; the step
budget is still a guess. `M` revealing an area's extent is now **settled deliberately** — the view
discloses it, because `nav.known()` already does.

**The vault is what all of this is for** — every route in crosses pits and `avoid="auto"` is not
offered for it, so gemma overrides a habit it spent days forming.

## Numbers, measured 2026-08-26

`MODEL_CTX` raised 8192 → 16384: real runs reached 9,391 tokens *before* a view existed. A four-turn
session runs 3k → 12k prompt tokens. The view is ~280 tokens for the largest area fully mapped and
is replaced rather than appended, so that is a flat tail cost. `bad_args` was **0 across 56 calls**.

**Variance between runs is large — never quote one run as a result.** The same script on the same
build gave 31 calls, then 14, then 32. The 31 → 14 drop went into an earlier draft of this file as a
win and was mostly luck. What repeated: the cap fires at most once a turn, `bad_args` stays 0, and
"go six blocks north" landed on the right cell three times out of three.

## Balance

`economy.py` prints the ladder and shouts `INVERTED` if a change breaks it. **The 600-step day is not
balance-neutral**: the 66-step walk to snake now amortises over a longer day, its edge over flappy
went from +3.7% to +17.6%, and the vault chain from 1.0 days of farming to 0.6. Still guesses, still
lenient. **Run all five tests after touching a map.**

---
*Last rewritten: 2026-08-26. Rewrite by replacing "Where it stands" — do not keep both.*
