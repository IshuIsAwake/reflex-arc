# CLAUDE.md

Repo-scoped instructions. These are standing rules; anything true only *right now* belongs in
[`HANDOFF.md`](HANDOFF.md) instead.

## The project

Hollow Knight played autonomously by a language model that issues goals to frozen, learned
control policies. The model has knowledge and no hands; the policies have hands and no
knowledge.

This is **not a paper.** It is a from-scratch build, and learning and explainability outrank
using the best available method.

## Layout

```
docs/00-raw-transcript.md        original ideation, verbatim
docs/01-ideas.md                 the superset of ideas — architecture, domain, constraints
docs/02-critique-response.md     prior art and novelty, checked against primary sources
docs/03-ideas-2.md               current decisions — read this first
docs/phase1-problem-statement.md coursework deliverable
docs/critique/                   source critiques (mostly untracked binaries)
```

`docs/` is the source of truth. Numbered files are a sequence: later ones supersede parts of
earlier ones and say so explicitly rather than editing history.

## Phases, and not mixing them

Work proceeds **idea → scope → execution**, gated, in separate conversations.

Scope is deliberately blocked until team headcount and commitment levels are known, because a
plan written before that doesn't survive contact with the real team. During the idea phase, do
not produce timelines, task breakdowns, or work allocation. If something is scope-shaped, note
it in one line and move on.

## Maintaining HANDOFF.md

`HANDOFF.md` carries forward only the context the next conversation actually needs. Reading it
should cost a negligible fraction of a context window.

1. **Hard cap: 100 lines.** At the cap, delete before adding.
2. **Two-conversation horizon.** Anything older is deleted or compressed to a single pointer.
3. **Pointers, not copies.** If it's written down in a file, link the file.
4. **No general rules there.** Standing instructions belong in this file.
5. **Rewrite, don't append.** Each conversation replaces it rather than adding to it.

## How to write documents here

Short and story-shaped, not specification-shaped. Lead with the thesis, then narrate how the
design was arrived at, then implications, then references. Roughly a page for anything
outward-facing; the detailed version lives in the repo and gets linked.

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
