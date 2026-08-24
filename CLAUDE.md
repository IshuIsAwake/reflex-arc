# CLAUDE.md

Repo-scoped instructions. These are standing rules; anything true only *right now* belongs in
[`HANDOFF.md`](HANDOFF.md) instead.

## The project

**Reflex Arc.** A language model that issues goals to frozen, learned control policies. The model
has knowledge and no hands; the policies have hands and no knowledge. Two implementations behind
one skill interface — Hollow Knight for coursework, a rover for hackathons.

This is **not a paper.** It is a from-scratch build, and learning and explainability outrank
using the best available method.

## Layout

```
README.md                        the idea and the current phase — read this first
ROVER.md                         the hardware implementation — the hackathon track
docs/hollow-knight.md            the coursework implementation — design and experiments
docs/technicalities.md           design decisions, constraints, deferred list
docs/sih-decision.md             which SIH entry to make — open, closes 6 Sept
docs/02-critique-response.md     prior art and novelty, checked against primary sources
docs/literature.md               reading list, every link opened and verified
docs/phase1-problem-statement.md coursework deliverable
docs/00-raw-transcript.md        original ideation, verbatim
docs/critique/                   source critiques (mostly untracked binaries)
```

The two implementations sit at the root; everything else is in `docs/`.
`00-raw-transcript.md` is history and is never edited; everything else is rewritten in place
rather than superseded by a new numbered file. Rejected ideas stay in the document that rejected
them, with the reasoning, so they don't get rediscovered.

## Phases, and not mixing them

Work proceeds **idea → scope → execution**, gated, in separate conversations. Scope opened
2026-08-20 and the current plan lives in the README. Don't reopen settled idea questions during
scope and execution — there is a deferred list for that.

## Maintaining HANDOFF.md

`HANDOFF.md` carries forward only the context the next conversation actually needs. Reading it
should cost a negligible fraction of a context window.

1. **Hard cap: 100 lines.** At the cap, delete before adding.
2. **Two-conversation horizon.** Anything older is deleted or compressed to a single pointer.
3. **Pointers, not copies.** If it's written down in a file, link the file.
4. **No general rules there.** Standing instructions belong in this file.
5. **Rewrite, don't append.** Each conversation replaces it rather than adding to it.

## How to write documents here

Short and story-shaped. Lead with the thesis, then narrate how the design was arrived at, then
implications, then references. Roughly a page for anything outward-facing; the detailed version
lives in the repo and gets linked.

**Cut the scaffolding.** Constructions of the form *this and only this*, *this and not that*, and
*this, and here is why this* are padding. State the conclusion. Keep a contrast only where the
wrong option is a real temptation someone would otherwise take.

**Argue it out before writing it down.** Reach the conclusions in conversation, offer a recap to
check, then write once. Documents drafted mid-discussion are mostly material that gets deleted.

**State plainly what has not been decided.** Padding an open question to fill a heading is
dishonest and gets revised anyway. A gap framed as a deliberate choice reads as control.

## Simplicity first

Start at core-level RL and implement from scratch rather than reaching for state-of-the-art
methods. Sophisticated approaches are ablations or later phases, never milestone one.

When citing advanced work, separate the **facts** that hold regardless of method — sample
budgets, decision frequencies, benchmark numbers — from the **method recommendation**, and lead
with the facts.

## Citations

Verify load-bearing citations against primary sources before they go in a document. Do not cite
from memory and do not guess URLs. Where a claim failed verification, record that it failed —
the same wrong claim tends to come back.
