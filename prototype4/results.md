# What prototype 4 has shown so far

Three runs on 2026-09-04, first day the flyer existed. `gemma4:e4b`, temperature 0, on an
integrated GPU. **Everything here is n=1 or n=2 and none of it should be quoted as a
result** — [`../prototype1/FINDINGS.md`](../prototype1/FINDINGS.md) records the same script
giving 31, 14 and 32 calls on the same build, and nothing below has been repeated enough
to survive that.

## She reaches for the flyer unprompted

The whole question the flyer was built to ask. In `runs/20260904-164543/` the only thing
said to her was:

> Explore and map as much of the arena as you can

No mention of a flyer, a camera or scouting. Two calls later:

```
scout(x=10, y=5)  ->  SCOUTED(to=(10,5), at=(10,0), steps=20, new=121)
```

One sortie, unasked, 121 cells of ground she had not driven through.

**The first run says the opposite and is worth keeping.** In `runs/20260904-123623/`,
seven calls, all `goto`, not one sortie — and that run had `scout 25 15` typed at her as
its opening message. So on the evidence so far she uses it sometimes and ignores it
sometimes, and one run in each direction is exactly as much as we know.

## The recharge shaped what she did, which is more than it working

Her first reply in the run above opens:

> Currently, the rover is at (25, 25). **The flyer is charging and cannot be** ...

A console sortie by hand had put it into recharge before she was ever spoken to. She read
that off the status line, chose to drive instead, spent 46 steps clearing the 25-step
debt, and only then flew. Drive, scout, drive — produced by the constraint rather than by
the prompt, which is what the constraint was for.

The gate is not free of side effects. See below.

## Where the day actually went

178 steps over one sol. 138 driving, 40 in two sorties.

| | steps | new cells |
|---|---|---|
| `goto(25,0)` | 31 | 79 |
| `goto(10,0)` | 15 | 43 |
| `scout(10,5)` | 20 | 121 |
| `scout(10,5)` again | 0 | REFUSED, recharging |
| `goto(10,20)` | 19 | 67, BLOCKED |
| **`goto(10,0)`** | **19** | **0** |
| `goto(4,0)` | 6 | 7 |
| `goto(4,25)` | 24 | 123, BLOCKED |
| **`goto(4,0)`** | **24** | **0** |

**43 of 178 steps — 24% of the sol — were spent driving back to where she had come
from.** Both times the shape is identical: aim south, get BLOCKED, retreat to y=0.

The leading suspect is the recharge, and it is uncomfortable because it is our own rule.
Her reasoning before the first retreat reads:

> The rover is at (10, 19). **The flyer is charging and needs 6 more steps of driving to
> be ready.**

She owed six steps of driving, and paid them by driving nineteen back up a corridor she
had already mapped. The gate asks for *motion*, so motion is what it got. The second
retreat does not fit that story — the flyer was ready — so this is a hypothesis with one
supporting case, not a finding.

Coverage came out at ~28% of the arena. The flyer-less run reached the same 28% in 253
steps, so 178 against 253 is the only number pointing at the flyer being worth its price,
and it is one run against one run.

## Three ways the answers failed to stop her

**She asked twice.** Straight after the successful sortie she called `scout(10, 5)` again,
byte-identical, and got `RECHARGING`. The refusal had just told her it needed 25 more steps
of driving. She did drive next, so the refusal worked — one turn late, and a turn costs
about 160 seconds.

**`_stuck` never fired, and was right not to.** Its rule needs three *consecutive* calls
that gained nothing; each retreat sat between two calls that gained plenty. A streak
detector cannot see waste that alternates with usefulness. This is the third time
FINDINGS has recorded a detector missing the case that had not happened yet, and the
answer is the same each time: write the invariant, not the case.

**A gainless drive says nothing about being gainless.** `DONE(at=(10,0), steps=19, new=0)`
is a success code. `new=0` is a number in a line, and `Result.advice` has a sentence for a
drive that cost nothing and for a sortie that revealed nothing, but not for a drive that
revealed nothing. That is the one gap in a pattern the rest of the codebase already
follows.

## What it costs to run here

Nine model turns, 32 minutes, on an integrated GPU with shared VRAM.

| | |
|---|---|
| per turn | 111–237 s, mean 164 s |
| prompt | 3,503 → 5,550 tokens over nine calls |
| the tell | **130 s to produce 17 output tokens** |

Generation is not the cost; prompt processing is, and the prompt grows every turn, so the
sol gets slower as it goes. `settings.py` quotes ~20 tok/s on a 6 GB RTX 3050; this machine
is well under that. Nothing in the architecture is at fault and nothing here is worth
tuning — it is a hardware note, and it is the reason the ladder below has not been run.

## Not answered

- **Whether she reaches for the flyer reliably.** One run each way. The ladder that would
  settle it — a neutral prompt, then a hint at the toolbox, then naming the flyer, each
  repeated — needs a faster model than this machine runs.
- **Whether she can aim a window at fog she had to find on the grid.** Both sorties this
  run were aimed straight ahead of the rover. `../prototype2/results.md` measures her at
  0/42 on counting a region off the picture, so a window aimed at the *largest* unexplored
  patch may be beyond her and the capability would still look like it works.
- **Whether the retreat is the recharge's fault.** Set `SCOUT_RECHARGE = 0` for one run and
  count gainless drives. If they survive, the gate is innocent.
- **Where the south went.** Both runs latched onto the top rows and never came back down.
  She starts at (25,25) and the entire southern half stayed fogged in each.
