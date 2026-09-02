# HANDOFF — prototype 2

Scoped to `prototype2/`. Repo-wide context is in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md). What it is and how to run it: [`README.md`](README.md).

> **The 100-line cap is deliberately suspended on this file, 2026-08-29.** It is carrying a work plan
> across several conversations, with the reasoning attached so each one can start without re-deriving
> it. **Delete each item as it lands** — that is what keeps this from becoming a document. When the
> plan is spent, the cap comes back and this note goes with it.

---

## Where it stands, 2026-09-02

**The hackathon rehearsal** for the 4–5 Sept internal round, so the other five see the vision run
before roles are divided ([`../docs/team-session.md`](../docs/team-session.md), still not held).

> **Next conversation: score two hosted probe tapes, write `results.md`, fork `prototype3/`, push
> prototype2 to main.** Then the five-arm run, in the conversation after.
>
> The map work is entirely in [`MAP-READING.md`](MAP-READING.md), which is ahead of this file and
> travels to prototype3. Start there, at *"What was settled on 2026-09-02"*. In one line: **gemma
> reads coordinates off text perfectly and off the picture never**, the fix is to change the map's
> *encoding* (run-length, lossless) rather than to add a retrieval step, and `read_map()` is dead.

**Chat A is finished** and four sols were audited (section below). Seven test files pass;
`.venv/bin/python game/main.py`. **Nothing in [`../prototype1/FINDINGS.md`](../prototype1/FINDINGS.md)
was re-derived and nothing should be.**

Landed 2026-09-02, verified by running them rather than by the suite going green:

- **`why` is optional.** A5 stripped it from history, which was right; *requiring* what had been
  stripped is what broke — she stopped sending it (0/79 missing before, 16/21 in
  `runs/20260901-000753/`) and each `BAD_ARGS` cost a hop. `skills._why` returns `None` instead of
  raising, `why` is off both `required` lists, `chat.SYSTEM` says optional, and `written_call` now
  accepts `goto(25,15)` — a written call must not face a stricter schema than a real one. Three
  tests inverted. The exact call that died sixteen times now drives 30 steps. **`without_why` is
  unchanged**: out of context, still on the tape, never punished when absent.
- **The hosted probe arm** — `--backend gemini --model X --thinking Y`, `--list-models`, retries on
  429/5xx only, abort after three consecutive failures, and the server's error body surfaced
  (urllib was discarding it, which is what made a 401 opaque for twenty minutes).
- **Every tape row now records `model`, `thinking` and `system_sha`.** Two tapes were compared as
  replications when `chat.SYSTEM` had changed between them and nothing said so.
- **`probe_read.py` derives arms from the tape** instead of assuming two.
- **`MAP-READING.md`'s reproduce line was wrong** — the 420 came from `--samples 6`, not `1`.

**The hop bug is still live and deliberately unfixed**: `self.hops += 1` at `chat.py:652` fires
before the call runs, so any `BAD_ARGS` costs a hop. Making `why` optional removed the only observed
trigger. **B3 owns the real fix** — doing it now means doing it twice.

**The 2026-08-29 runs are gone from this file.** They were played on an arena that no longer exists;
`runs/20260829-155623/` still has them.

## What the four runs showed

`runs/20260830-001348/`, `-095910/`, `-100921/`, `-102123/`. Ground truth was rebuilt by flood-filling
`config.ARENA` and by parsing the view block out of every turn, so each number below is checked
against what gemma was actually shown. `-102123` reproduces headless, byte for byte.

**The features work.** `view₀.seen + Σnew == view_last.seen` exactly, all four runs. The arena
flood-fills to 30 components, 20 of 16 cells and 10 of 9, as `config.py` claims. `_stuck` fired on
runs of 3, 4 and 5 gainless drives *on different targets* — the alternating loop the old rule was
blind to — and never once on `distance`. Gainless drives fell from 358 of 439 steps to 12 of 28 and 6
of 21 drives.

**`reveals~` was the one that lied, and the fix above is only the label.** Priced `steps=53,
reveals~299`; drove it from the identical state and got `steps=69, new=315`. Swept 38 priced-then-
driven trips: **9 revealed more than promised**, worst 68 against an actual 112. `goto` and `distance`
are both correct — replanning round rock sweeps ground the straight route never passed, which is the
mechanism the docstring already named and then pointed the wrong way.

**It holds a spatial constraint.** Told *"only explore south of the basepad, the north has a dust
storm"*, it wrote `y ≥ 26` in prose and held it for all six drives, max goal `y=35`, zero northward
goals. A natural-language constraint became a coordinate predicate and survived seven turns. **This
is the pitch, and it is the strongest thing in the four runs.**

**It gets the density right and the counting invented.** Asked for the largest boulder, it said the
bottom-left was densest — true, 23.6% of what it had seen against 13.9–17.1% elsewhere. Then it
backed that up with rows it had never seen: *"row 49, x=0–15, all rock"* where all sixteen cells were
fog, and *"32 cells"* for an object that cannot exist, since no component exceeds 16 by construction.
**The reading that this only happens downstream of a conclusion did not survive the evening probes**
— see [`MAP-READING.md`](MAP-READING.md), where a neutral question about an empty-of-context box got
a uniform wrong fill too.

**Fog: it finds the regions and ranks them wrong.** Four regions named, all four real, one box 77%
fog — but the largest (359 cells, centre (31.7, 41.1)) was called "pockets" and the two smaller ones
recommended. Asked again later it named a box that was 21% fog as the largest. **Detection yes,
ranking no**, which is exactly B1's line.

**The stall is the thing that stops a sol. 12 of 25 replies state an intention and make no call.**
`skills.looks_like_a_call` catches **0 of 12** — measured by running the real function over the real
text. In `-100921` that was 7 of 9 replies, three consecutive turns producing the same paragraph
about driving to (24,25) while nothing moved, and **every recovery was a human noticing.**

**The hop cap held 4 times out of 4, and it has still never produced a summary.** Every one of the
four cap events had gemma emit a tool call into a request carrying no tools; `capped` dropped all
four on the floor. The *"say what you found"* request got a tool call instead of a sentence, 0 for 4.

**Context is not the constraint and repetition is not literal.** Peak 8,305 tokens of 16,384, growing
~156/call. Exact duplicate sentences: 0, 0, 5, 1. What repeats is the template — "maximiz-" ×13,
"sweep" ×18, "sensor footprint" ×9 across six replies, ~1,200 characters every turn whether it acts
or not.

## Three principles, unchanged

**Pre-compute facts, never preferences.** "Four unexplored regions, sizes and centres" is a fact; "go
to the biggest" is a preference and stays gemma's. Past that line this is the hardcoded decision table
the README warns about (Hösch, 46.4% vs 51.5%, p = 0.103).

**Free means free on the world's clock, not uncounted.** Only calls that move the rover spend steps.
Every skill still spends *something*, because every call is a model round trip.

**A limit that depends on the model's cooperation is not one.** Now 4 for 4 on fresh data, above.

---

# The work, in three conversations

**Delete items from this file as they land.**

## Chat B — two new skills, and splitting the budget

**B2 · `end(summary)`. Promoted to first, and it is no longer a convenience.**
*Why it moved:* the stall above cannot be detected from the reply. Two replies in `-100921`, same
turn depth, same sentence — *"I will use `goto` to drive to (25, 19)"* which called, and *"I will use
`goto` to drive from (24, 15) to (24, 25)"* which did not. **Widening the regex was tried and
abandoned: 6 caught against 5 false positives**, and a false positive tells gemma to *"make the call
itself now"* on a turn it was told not to move. The signal is absent because **speaking and stopping
are the same act**, so "a reply with no call" is ambiguous by construction. `end()` removes the
ambiguity in code: no call and no `end()` is an unfinished turn.
*Second payoff:* the summary is the natural seed for the scratchpad and for notes across sols.
*It does not replace the hop cap.* A model that ignores "answering ends your turn" will ignore
`end()` — and the cap has now failed to extract a summary four times out of four, so `end()` is also
the only candidate for making a capped turn produce anything.

**B1 · `fog()`.** Names the unexplored regions: connected components of unseen cells, each with size
and a representative cell. **It must not rank them or recommend one** — facts, never preferences.
*Why:* measured above — detection yes, ranking no, twice.
*The flood fill is already there.* `world.components(w, h, member)` is the function this needs — pass
"cell not in `area.seen`" where geology passes "cell is rock". Do not write a second one.
*Called, not injected.* Injecting it everywhere risks pulling gemma off an objective it is halfway
through. But leave **one line in the free view** saying how many regions remain and that a skill will
name them: a forgotten sense costs a whole sol, which is why `look()` was measured and rejected.

**B3 · Split the hop budget.** `MODEL_MAX_HOPS` is doing two unrelated jobs — a **resource** ("you get
ten actions") and a **runaway guard** ("something has gone wrong"). That conflation is why `distance`
reads as expensive: every price check is one fewer drive. Give driving calls their own budget and free
calls a separate, larger, still-hard one; the turn ends when either blows.
*The guard must survive the split.* It is the only backstop against a loop on free skills.

**B4 · Warn at call 9 that call 10 is the last.** `budget_note` already appends *"Only N steps left
today"*. Hops have no equivalent — the first thing gemma hears about the cap is the refusal.

**B5 · Reword the prompt, last.** What is wrong with it: every worked example is an edge, and *"space
parallel sweeps 7 apart"* asks for bookkeeping with nowhere to keep the state. **Nothing tells gemma
that `new=` or `reveals~` exist** — it learned `reveals~` only by calling `distance`, which it did
once in four sols and only when told to use a function by name. It goes last because its other flaw is
referencing facts the environment did not report until A and B landed.
*Two tests pin it and will fail, correctly:* `test_chat.py test_the_prompt_promises_exactly_what_exists`
and `test_skills.py test_the_schema_matches_what_is_wired_up`. Updating them is the work.
*Keep `chat.original_SYSTEM`* — it is the control.

## Chat C — 31B hosted against 4B local · **half done**

**The probe half ran on 2026-09-02** as `gemma-4-31b-it` and a gemini Flash model through
`probe_map.py --backend gemini`; tapes are in `runs/probe-<model>-<stamp>/`, unscored. Three
outcomes, unchanged: 31B reads it → a 4B ceiling, and pre-computing is earned. 31B also fails → the
view is unreachable at any size and the model was never the variable. 31B only when told →
attention, not capability, and the fix is one sentence.

*Trap:* at temp 0 one ask is one sample. Vary the **world state**, not the asking — and the two
gemma tapes have now demonstrated exactly why (see `MAP-READING.md`, run-to-run variance).

**Still to do: drive a live sol against the better hosted model**, not just the probe. That is a
transport swap in `chat.py` rather than in `probe_map.py`, and it is the thing Ishan wants to try
by hand. *Hosted, so VRAM is irrelevant.* A video of 31B doing visibly better is a **pitch asset**:
a remote planner outperforming a local one is the latency claim. **Open, not settled:** a demo
depending on a rate-limited API needs network at the venue, and the free tier binds at 16k input
tokens a minute — about three calls.

## Chat D — the scratchpad · **moved up**

*Why it moved:* a scratchpad is text she wrote, arriving back as text — and text is the one channel
measured as working. Every other subsystem is a guess at an encoding she will tolerate; this one is
her choosing it. It is also the *semantic* map, which is the half that is properly hers: the
occupancy grid belongs to the rover, exactly as her position does.

**Model-written**, corrected by `fog()` rather than policed — a false "region done" is contradicted by
the next call, so no world-owned coverage list is needed.

**Objectives, not notes.** Entries get struck off, and that generalises: when sample sites land,
"collect at (33,34)" is the same object as "explore region 4", and striking off is what prevents the
revisit loop prototype 1 measured.

**The size cap is enforced in code, not requested in the prompt.** This model has already fabricated
four thousand characters of view block unprompted; `chat.cut_fabrication` exists because of it.

**Maintain it the way `../CLAUDE.md` says to maintain this file:** hard cap, rewrite don't append.

---

## Good to hand to the team as a question

Ishan leads by letting people arrive at the answer, so these are written as the thing to *notice*
rather than the thing to do. Each is self-contained, has a real answer to discover, and is not on the
MVP critical path — B2, B5 and the A5 measurement stay in-house.

- **The repetition.** *"Look at how much of this is gemma quoting herself. Is there a way to stop
  that?"* Leads to the scratchpad (Chat D) and to B4. Highest wow factor of the three, and genuinely
  open — the size cap and "objectives, not notes" are the two traps to let them find.
- **Ranking the fog.** *"She can see the fog. Can she tell you which patch is biggest?"* Leads to
  B1 and to `world.components`, which is already written and which they should be allowed to find
  rather than be pointed at. The discipline to teach is facts-not-preferences.
- **The geology names.** Depends on the probe below. If gemma cannot pick the lumps out, `things()`
  naming boulders is a well-shaped piece of work with a visible payoff on screen.

## Open, and deferred

**Priority-weighted objectives are what make the Hösch risk measurable here.** With fog size as the
only axis, "go to the biggest blob" is the whole optimal policy and a lookup table ties by
construction. A high-priority region against two moderate ones is the first configuration where
gemma's judgement is actually on trial. Not scheduled.

**Item 4, the timer.** Steps make two runs comparable; a wall clock is what Mars does to you. Settled:
steps now, clock once the rest is in. **When it lands, B3's "free" calls stop being free.**

**The arena, for reference.** 410 rock of 2500 (16.4%), seed 78, twenty boulders of 16 and ten of 9,
two clear cells between any two, and they are allowed on the outer ring — keeping them off left the
free perimeter gemma ping-ponged along. Identity is recovered by flood fill, not written down, so a
merge (25) or a split fails outright. `test_world.py` asserts all thirty.

---

## The order, and the thing that keeps slipping

1. **Score the two hosted tapes** → `probe_read.py runs/probe-<model>-<stamp>/probe.jsonl`.
2. **`results.md`** — what prototype2 *closed*: the four-sol audit, the `why` regression, the
   map-reading probe, the hosted answer. `MAP-READING.md` keeps only what is *open* and travels.
3. **Fork `prototype3/`**, push prototype2 to main. prototype2 stays the demo build; prototype3 is
   the map lab, so three days of encoding experiments cannot destabilise what five people watch.
4. **The five-arm run** (`MAP-READING.md`), then RLE.
5. Then B, then D.

> **`end()` is still last and the internal round is 4–5 Sept.** The stall is 12 of 25 replies with
> the detector catching 0 of 12, and every recovery so far was a human noticing. Either that round
> does not need a clean unattended run, or **B2 jumps the map work.** Raised twice, still open.

**A full sol against the current build has not been run since `why` became optional.** `why` was 51%
and 47% of durable history in the two unattended stretches; A5 asked whether self-imitation was
load-bearing and the answer is still unmeasured. Read back `runs/<stamp>/`: count `new=0` drives,
count `distance` calls, flood-fill the final `seen`, compare gainless-drive run lengths to the
numbers above. *Known risk:* with no trail of its own it may lose track of what it tried and repeat
**more**. That is the finding, not a bug.

---
*Last rewritten: 2026-09-02. Rewrite by replacing "Where it stands" — do not keep both. The line cap
is suspended while the plan above is live; restore it when the plan is spent.*
