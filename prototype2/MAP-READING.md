# The map-reading problem

**Temporary.** Opened 2026-08-30 to carry one issue into its own conversation. Rewritten 2026-09-01
after the question was measured properly, and again 2026-09-02 once the design was argued out.
**This file travels to `prototype3/` and is the document that conversation works from.**

**Start at [What was settled on 2026-09-02](#what-was-settled-on-2026-09-02).** Everything before it
is the evidence; everything in it is decided and unbuilt. `read_map()` is **dead as a fix** and the
A/B/C/D ladder is **replaced by five render-flag arms**. The build is the RLE encoding.

Everything below is measured against the view block she was shown, not against the world and not
read off the transcript. Method at the bottom.

---

## The one-line version

**Gemma cannot read the ASCII map, and the qualitative answers that looked like reading were
tracking the size of the target rather than its location.** Measured at n=420 across two prompt
arms, two temperatures and three world states, with every baseline computed in code.

The 2026-08-30 version of this document said she also believes she is *not allowed* to read it.
That was real but rare — explicit refusal language appears in 0–2% of answers at n=420. The
dominant failure was different and is described below.

## The probe

`game/probe_map.py` builds three worlds by driving fixed `goto` sequences (17%, 62%, 77% coverage),
renders the view, and asks 30 questions per world with no tools and no thinking. `game/probe_read.py`
scores the tape offline so a run can be re-scored without paying for it again.

Two arms: the live prompt, and the same prompt with the two **blocker** sentences restored
(`"Nothing else reveals ground."` and the heading telling her the grid is a picture and not to count
cells off it). Two temperatures: model default and greedy.

Tape: `runs/probe-20260831-152943/probe.jsonl`, 420 answers.

## Quantitative reads are zero

| question | unblocked | blocked | note |
|---|---|---|---|
| region — count rock/open/fog in a 30-cell box | **0/36** | **0/36** | |
| row — count along one full row | **0/18** | **0/18** | |
| cell — what is at (x,y) | 44% | 28% | not a read, see below |

**The 44% on cells is a habit, not a read.** By ground truth: rock **0/21**, open 8/21, unseen
**20/21**. She said "unseen" 41 times out of 63. A policy of always answering UNSEEN scores 33%.

And the unseen-rate runs *inverse* to the actual fog:

| world | fog on the map | times she said "unseen" |
|---|---|---|
| 0 | 83% | 52% |
| 1 | 38% | **100%** |
| 2 | 23% | 86% |

**Eighteen of eighteen fully-revealed boxes came back with fog in them.** Verbatim: truth
`rock=12 open=18 unseen=0`, answer `rock=12 open=13 unseen=5`.

## Qualitative reads are at or below chance

Every one of these is forced-choice with a baseline computed from the world, which is the only way
"she named a fog region and it was real" means anything.

| question | scored | baseline |
|---|---|---|
| biggest fog blob | 22% | **81%** |
| quadrant with most rock | 17% | 25% |
| quadrant with most unseen | 28% | 25% |

Five of fourteen "biggest fog blob" answers named cells that were **already explored**.

### The near-miss re-score

The above scores exact hits, which would miss a model that has the right area and the wrong
coordinate — the failure mode the live runs look like. So the tape was re-scored for near misses.

It looks supportive at first: of 23 blob answers, 9 landed inside the biggest blob, 5 more in some
fog, and the median Chebyshev distance to the blob is **1**.

Then the baseline:

| world | fog | biggest blob | blob + 1-cell halo | she landed in it |
|---|---|---|---|---|
| 0 | 83% | 2,075 cells | 89% of the map | 80% |
| 1 | 38% | 692 cells | 37% of the map | 80% |
| 2 | 23% | 408 cells | 22% of the map | **0/8** |

She tracks how big the target is, not where it is. World 2 is the case where a dart stops working,
and there she scores nothing.

Same result on cells: her claimed glyph was within 2 cells of the asked coordinate 24/50 times
(48%). **A dart thrown anywhere on the map scores 61%.** She is worse than the dart.

## Every coordinate she got right had been handed to her as text

From the human-played run `runs/20260901-000753/`, which is where the "but she *can* read it"
impression comes from — and it is the sharpest evidence in this document.

| she said | where it came from |
|---|---|
| base pad at (24,26) | the **status line**, verbatim |
| rock at (17,10) | `DONE(at=(15,10), steps=12, new=70, rock=[(17,10)])` |
| rock at (17,11), (17,12), (22,10), (20,10) | **nothing. Not in any result, not in any status line.** |

She took the first rock she was ever told about and grew a fictional cluster around it, then offered
three different answers to the same question inside one reply. Asked for the top-right quadrant, she
defined the first quadrant as X<25, Y<25.

Nothing she got right was read off the grid.

## Removing the blockers fixed the failure mode and not the accuracy

Worth doing, and already done in `sight.py` and `chat.py`. It is not the fix.

| | blocked | unblocked |
|---|---|---|
| no answer parsed | 40% | **7%** |
| wrote out a call instead of answering | 39% | **10%** |
| region counts that sum to 30 | 4/12 | **21/42** |
| median claimed total for a 30-cell box | **149** | 30 |
| wall clock / output tokens | 15.8 min, 17.9k | **5.4 min, 5.1k** |
| accuracy | 14% | 22% (p = 0.16) |

**The dominant blocked-arm failure was never the refusal.** It was answering a map question by
writing a `goto` call — 39% of replies. One verbatim: asked what was at a coordinate, she replied
`goto(1, 1, "To begin mapping the far northwest corner…")`.

## Two things that are not the cause

**The ruler is not making her answer in multiples of five.** Of 560 coordinates she emitted, 207
(37%) are multiples of 5 against 20% chance — but split by what she was doing with them, the
x-coordinates she *reads off a row* are 42/209 = **20%, exactly chance**. The bias lives only in
destinations she *chooses*, and the prompt causes it by telling her to aim at far corners and
distant edges.

**It is not context size.** Peak `tokens_in` across every run is 5,517 against `MODEL_CTX = 16384`.

## What is actually in the view

World 1, 4,373 characters. `SYSTEM` is another 5,871.

| | chars | |
|---|---|---|
| ruler + 50 grid rows | 2,856 | **65%** |
| `IMMEDIATELY AROUND YOU` (4 sightlines) | 304 | 7% |
| vision sentence + reveal rule | 291 | 7% |
| grid heading | 256 | 6% |
| "rewritten from scratch" preamble | 201 | 5% |
| size + axes | 201 | 5% |
| `WHAT YOU KNOW IS HERE` | 96 | 2% |
| status line | 83 | 2% |
| legend | 80 | 2% |

Two findings in that table. The preamble is **duplicated** — `SYSTEM` already says the block is
rebuilt each turn. And the ~400 characters of pre-computed prose (`IMMEDIATELY AROUND YOU`,
`WHAT YOU KNOW IS HERE`, the status line) are the **only part she demonstrably uses**; FINDINGS
measured her reading those back exactly.

Two prompt errors found while reading it: the vision disc is **29 cells, not 49** (`Area.disc` is
Euclidean at r=3; only the middle row is 7 wide), so "7-cell wide swath" overstates coverage by
~70%. And "the arena has no wall around it" is *correct* — `config.py` omits the rim deliberately —
but ambiguous enough to be worth replacing with a reachability statement.

Renaming any view heading breaks `sight.HALLMARKS`, which is how `chat.cut_fabrication` detects her
writing the environment's half of the conversation.

## A regression found on the way: `why`

Unrelated to map reading, and currently the most expensive bug in the prototype.

In `runs/20260901-000753/`: 25 calls, 21 ran, **16 came back `BAD_ARGS(why is required)` — 76%**.
Four refused at the hop cap. Five actual drives in the session. She emits `goto(x=35, y=10)` with no
`why` **six times in a row**; the error text does not recover her.

| run | missing `why` |
|---|---|
| `old_runs/20260829-163738` | 0/23 |
| `old_runs/20260830-001348` | 0/28 |
| `old_runs/20260830-095910` | 0/21 |
| `old_runs/20260830-100921` | 0/7 |
| `20260830-123557` | 4/11 |
| `20260830-124301` | 2/20 |
| `20260901-000753` | **16/21** |

Zero across 79 calls, then 42% across 52. Two mechanisms, both in code:

- **`without_why`** ([`chat.py:247`](game/chat.py), applied at `chat.py:689`) strips `why` from the
  assistant turns that re-enter history. Every past call she can see is now an example of a call
  *without* a `why`. She is few-shotting off her own stripped transcript. A5 removed the examples
  that were teaching the field.
- **`self.hops += 1` fires before the call runs** (`chat.py:652`), so a schema error costs a hop.
  Seventeen of them ate three turns of budget.

prototype2 is untracked so A5 cannot be git-dated, but its docstring cites "twenty-eight strings,
mean 196 characters", which matches `old_runs/20260830-001348` exactly — so it was written after
that run, and the break falls in the right window.

**Decided 2026-09-01: `why` becomes optional and stays out of context.** The reason it existed —
a stated reason timestamped earlier than its outcome — survives, because it still reaches the pane
and the tape whenever she supplies one, and will reach the scratchpad later. Making it optional also
repairs the A5 regression for free: omission was only ever punished by the refusal.

## What was settled on 2026-09-02

### The mechanism, which explains every number above

**She emits coordinates she has been handed as text. She never emits one read off the picture.**
It accounts for the whole table: 22% on blobs *below* an 81% baseline because she names explored
cells — the ones that appear in prose; the (17,10) cluster grown from the one rock a `DONE` string
mentioned; multiples of five only in destinations she *chooses*, at exactly chance in the x's she
reads off a row; the pad read verbatim off the status line.

The reason is architectural, not a gemma defect: answering "what is at (37,12)" means counting 37
characters into a run of `?` and `#`, and identical glyphs merge into tokens of unpredictable
length. Character-position arithmetic inside a row is not an operation the model has.

**This repo already reached that conclusion three times and acted on it** — `neighbours()` exists
because counting eleven characters into a row failed, `_sightline()` and `things()` for the same
reason, each after a measured failure. The probe is the fourth instance of one finding.

Read the other way, it is a **capability** statement: there is a channel into this model that works
perfectly. The map is in the wrong channel.

### `read_map()` — dead as a fix

The probe removed "she wasn't looking" — one question, map present, no tools, temp 0 — and she
still scored 0/36. Retrieval-framing fixes awareness; the failure is indexing. Asking for the same
string first does not supply an index. Keep the file idea only for inspectability and as a demo
artefact; it has no model-facing effect and is off the critical path.

**Also rejected: a windowed `read_map(x0,y0,x1,y1)`.** Small windows push her back toward short
`goto` hops, a regression already fought once. As an *addition* that objection dissolves — but once
you concede she needs a numbered 10-wide window you have conceded the picture loses to text, and
the consistent move is the encoding change below. Recorded so it is not rediscovered.

**Dropped: a textual diff line.** "47 cells opened" carries no map-level information.

### The encoding ladder, and RLE is the build

Not "teach her to count" — no tool grants an arithmetic capability the architecture lacks. The
question is what encoding needs no counting.

| | what she gets | what she must do | environment answers? |
|---|---|---|---|
| 1 | the picture (now) | index into a 50-char row | no — and she fails |
| 2 | `(0,12)=? (1,12)=? (2,12)=#` … | aggregate | no |
| 3 | **`y12: x0 unseen, x1 rock, x2-7 open, x8-49 unseen`** | aggregate | **no** |
| 4 | `box(12,30,17,34) → rock=12 open=18 unseen=0` | nothing | yes |

**Level 3.** Lossless — the same map, differently written. Every boundary carries its coordinate as
text, no counting anywhere, and she still has to compare spans to answer anything, so the reasoning
stays hers. Measured against the picture: **0.88× at 17% seen, 1.60× at 62%, 1.70× at 77%** — it
gets *more* expensive as the sol proceeds, worst case ~5k chars against a 16k window. Affordable,
and the argument for it is legibility, not economy.

### The five arms, replacing the A/B/C/D ladder

All render flags, one run, scored offline. `probe_map.view_for` already swaps view components.

| arm | | what it settles |
|---|---|---|
| current | prose + grid | measured, at chance |
| **grid only** | strip the prose | does removing the crutch force her onto the picture |
| **prose only** | strip the grid | **the null** |
| **RLE only** | level 3 above | does the encoding fix it |
| RLE + prose | | the shipping candidate if it does |

**Prose-only is the point.** It is 722 characters holding one landmark and four sightlines — almost
no map at all. So *current ≈ prose-only means the grid contributes zero*, and that is the number
nobody has. Note the probe already ran the informational half of the grid-only arm: for five of six
question types the prose never contained the answer, and she scored 0/36 anyway. The grid-only arm
therefore tests a *policy* ("the exact facts are underneath"), not an information effect.

**Arm 0 is a measurement, never a design.** The LLM's job begins *after* an area is mapped — which
rock to sample, which region to avoid, where to explore next — so the map is the substrate the
reasoning runs on and a coordinate system is non-negotiable. "Delete the grid" can only ever be a
question about what the picture is worth today.

That job spec also narrows what must work: those are all *regional* questions. She never needs
`box(12,30,17,34)`. She needs *"largest unexplored region, give me a coordinate in it"* — which is
`biggest_fog`, the question at chance. **The 0/36 on region counts is a symptom, not the blocker.**

### Pre-computing is architecturally honest, and the picture is the unrealistic part

A real rover has odometry and an IMU producing position as a number, and a terrain classifier
emitting detections — "obstacle, 3.2 m, bearing 047" — not a bitmap for something downstream to
squint at. Perception's whole job is turning pixels into structured facts. `neighbours()` and
`_sightline()` are the honest simulation of that; the ASCII picture is the simulation artefact.

Nothing here reads ground truth: `sight.py` cannot touch `Area.at`, `nav.known()` is the one gated
door, and `test_sight.py` counts the reads. Every pre-computed fact comes from *her* seen-set.

**Two maps, and only one is hers.** The occupancy grid belongs to the rover — she no more builds it
than she computes her own position. The *semantic* map is hers: "the southern strip below y=35 is
done", "region 4 is a boulder field", "sample site at (33,34), not collected". **That is the
scratchpad (Chat D), and it moves up the plan**, because a scratchpad is text she wrote arriving
back as text — the one channel measured as working.

### 4. Prompt rewrite, agreed and not yet done

Cut the *this-but-not-that* scaffolding throughout; drop the duplicated preamble; instruct short
replies (her 5 messages in `-000753` averaged 773 characters, the two longest cost 15.8s and 19.0s);
merge "aim far" / "maximize sensor footprint" / "space out your routes" into one idea; scope the
"already-mapped cells are a critical waste" line to exploration; fix the 29-vs-49 vision disc;
replace the wall paragraph with a reachability statement. Numbering all 50 columns needs two stacked
digit rows and does not fit — it is a layout change, not a one-liner.

## The hosted arm — built 2026-09-02, results pending

`probe_map.py --backend gemini --model X --thinking Y`. Only the transport differs: same
`make_questions`, same views, same `score`, same system prompt. Unblocked only — the blocked
paragraph is an artefact of the prompt gemma was given, and the question is whether a larger model
can read *the view we ship*.

**`gemma-4-31b-it` is on the same host, and it is Chat C.** Same family, tokenizer and training
recipe as `gemma4:e4b` at ~8× the size, so a difference is attributable to scale. A gemini Flash
model varies everything at once and can only say "a different model did better".

*Prediction, recorded before scoring:* both hosted models stay at or near 0 on `region` and `row`,
because counting inside a 50-glyph run is a tokenization problem rather than a capability one, and
both beat gemma clearly on `cell` and the quadrants. If so the prescription is one sentence —
never ask any model to count cells — and the RLE arm is aimed correctly. If 31B reads the region
boxes fine, the view was never the problem and most of the plan above is unnecessary.

Practicalities paid for once: the free tier now issues `AQ.`-prefixed keys that some accounts find
are rejected with 401 `ACCESS_TOKEN_TYPE_UNSUPPORTED` (`settings.GEMINI_AUTH` switches to Bearer;
an `AIza` key from the Cloud console is the reliable way out). Thinking levels are per-model —
`minimal|high` for gemma-4, `low` for gemini-3.x — so the arms carry different values and the
principle is *the lowest each model offers*. **The binding quota is input tokens per minute
(16,000), not requests**: one call is ~5.5k tokens, so it is ~3 calls a minute.

## Run-to-run variance is large on the qualitative axis

A second gemma tape, `runs/probe-20260902-182624/`, same questions and seed:

| | 31 Aug (samples 6) | 2 Sep (samples 3) |
|---|---|---|
| region | **0/36 0%** | **0/18 0%** |
| row | **0/18 0%** | **0/9 0%** |
| cell | 44% | 48% |
| biggest_fog | **22%** | **56%** |
| quad_unseen | **28%** | **56%** |

**The quantitative findings are bedrock; the qualitative ones are not.** No individual question type
reaches significance (biggest_fog p=0.108); pooled and excluding the broken `near_rock` row it is
p=0.023, which is weak evidence on a post-hoc comparison carrying three confounds — different
`--samples`, unpinned temperature, and `chat.SYSTEM` edited between the runs.

The conclusion *direction* survives — 56% is still well under the 81% baseline — but **no number on
the qualitative axis of this document should be quoted as stable.** For the five-arm run, pin
temperature to 0 and vary world state instead, which is what `probe_map.py`'s own docstring already
says and what this pair just demonstrated.

Every tape row now records `model`, `thinking` and `system_sha`, so the next pair either matches or
does not. Both existing gemma tapes say `unrecorded`, honestly.

## A bug in the probe itself

`near_rock` generated 42 items and **all 42 had truth `rocky`**. The 50% baseline was wrong; that
row measures a yes/no bias, not reading, and it is excluded from every table above. (She answered
CLEAR 26 of 29 times, consistent with the "everything is unseen" bias elsewhere.) Fix the generator
before the next run.

## Reproducing any of this

```
.venv/bin/python game/probe_map.py --samples 6        # writes runs/probe-<stamp>/probe.jsonl
.venv/bin/python game/probe_read.py runs/probe-<stamp>/probe.jsonl
```

**`--samples 6` is what produced the 420, and this line said `1` until 2026-09-01.**
30 questions × 2 arms × (1 greedy + 6 default) = 420. Following the old line gives 70
answers and a different set of numbers.

The hosted arm is the same two commands with `--backend gemini`, unblocked only, so
30 × 1 × 7 = 210 calls — see `probe_map.py` for the key and model setup.

`probe_map.audit()` parses the rendered grid back out of the view and asserts cell-by-cell agreement
with `nav.known` — it passes on all 50 rows of all three worlds. The rover's own cell is drawn as
`@` and is excluded from every question.

Human-played tapes: `runs/20260901-000753/` (latest, the `why` regression), `runs/20260830-123557/`
and `runs/20260830-124301/`.

**Do not score an answer against the true arena.** Score it against the view block from that turn —
that is her knowledge, not the world's.
