# CLAUDE.md

Repo-scoped instructions. These are standing rules; anything true only *right now* belongs in
your own `HANDOFF.md` instead — untracked, one per person.

**Read [`repo_rules.md`](repo_rules.md) first** and follow its "For AI assistants" section for
the whole session; where it and this file differ, it wins. The exception is Ishan's own sessions
(git user `IshuIsAwake`), which work from this file and his own notes.

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
rover_ideas.md                   the long version of ROVER.md — reasoning, and what was cut
ARCHITECTURE.md                  the three layers and how a decision reaches the motors
work_division.md                 who owns what — allocated, with the detail linked
repo_rules.md                    the rules everyone shares, and how an AI assistant works with you
prototype10a/                    prototype 10 frozen — the build the Angaraka recording ran on
prototype10b/                    the base the team is testing; DESIGN.md is its scope
prototype10c/                    10b plus autonomy and comms, as the 13 Oct run left it
prototype10d/                    the sol in four phases; DESIGN.md is its scope
prototype11/                     10d with Harsh's screen, the newest simulation; DESIGN.md is its scope
prototype12/                     10d's game driving the real rover, up to Level 3 — Koushik's; DESIGN.md is its scope
prototype13/                     11 and 12 merged: 11's simulation driving the real rover, up to Level 3; DESIGN.md is its scope
archive/                         prototypes 1–9 as a tarball; also the git tag prototypes-1-9
docs/findings.md                 what prototypes 1–9 settled — the conclusions, without the code
docs/course.md                   the coursework track — design, experiments, constraints
docs/sih-decision.md             which SIH entries we made, and why — closed
docs/sih26226-portal-text.md     the Angaraka entry exactly as submitted — later rounds must agree with it
docs/sih-submission.md           the 15 Sept snapshot of both entries, kept for its sources
docs/SIH*.pdf                    the two decks as submitted, Angaraka and GHOST
docs/pitch.md                    how to explain this to someone from nothing, in eight beats
docs/novelty.md                  is this actually new — prior art, checked against primary sources
docs/literature.md               reading list, every link opened and verified
docs/phase1-problem-statement.md coursework deliverable
docs/00-raw-transcript.md        original ideation, verbatim
docs/critique/                   source critiques (mostly untracked binaries)
```

The two implementations sit at the root; everything else is in `docs/`. Code lives in numbered
`prototypeN/` directories — a lab rather than a deliverable, where the rules above bend and things
get messed with. Only the live ones stay as directories; a finished one goes into `archive/`, and
what it settled goes into `docs/findings.md` first.
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
