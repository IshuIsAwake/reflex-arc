# HANDOFF — prototype 3

Scoped to `prototype3/`. Repo-wide context in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md). The code is a fork of prototype 2 at `408e378` and runs the same
way — [`../prototype2/README.md`](../prototype2/README.md). Needs a venv with `pygame` in it.

## Why this exists

**gemma cannot count into the rendered grid, and gemini can.** Table and n in
[`../prototype2/results.md`](../prototype2/results.md): 0% for gemma at 4B *and* at 31B, correct
for gemini on the first try. So the map is in the wrong channel for the model we actually ship,
and the fix is the encoding rather than a bigger model or a retrieval step.

Prototype 2 stays the demo build. This is where the encoding changes and the two missing skills
get built, so that work cannot destabilise what gets shown.

## The order

**1 · RLE — the map as text.** `y12: x0 unseen, x1 rock, x2-7 open, x8-49 unseen`. Lossless, the
same map differently written. Every boundary carries its coordinate as text so nothing has to be
counted, and she still has to compare spans, so the reasoning stays hers. Measured against the
picture: 0.88× at 17% seen, 1.60× at 62%, 1.70× at 77% — it gets *more* expensive as the sol runs,
worst case ~5k characters against a 16k window. The argument for it is legibility, not economy.

**2 · `end(summary)`.** A skill that ends her turn carrying a summary. Speaking and stopping are
the same act, so "a reply with no call" is ambiguous by construction — `looks_like_a_call` caught
0 of 12 stalls. `end()` makes the distinction exist in code. The summary also seeds item 4.
*Before building it, check whether it is still needed:* the last sol (`20260902-224413`) had no
stalls at all, and making `why` optional is the plausible cause. **The tape cannot currently answer
that** — `chat.py:696` writes text and calls as separate rows with no message index joining them,
so "text accompanying a call" and "text-only reply" are indistinguishable. Add the join first.

**3 · `fog()`.** Names the unexplored regions: connected components of unseen cells, each with a
size and one representative cell. **It must not rank them or recommend one** — facts, never
preferences; past that line this is the hardcoded decision table the README argues against.
Measured twice: she detects fog regions and ranks them wrong, calling a 359-cell region "pockets"
and recommending two smaller ones. `world.components(w, h, member)` already exists — pass "cell not
in `area.seen`". Do not write a second flood fill. Called, not injected, but leave one line in the
free view saying how many regions remain.

**4 · The scratchpad.** Model-written objectives that come back to her as text and get struck off.
This is the one channel measured as working — text she wrote arriving back as text. It is the
*semantic* map, which is the half that is properly hers; the occupancy grid belongs to the rover,
as her position does. Corrected by `fog()` rather than policed: a false "region done" is
contradicted by the next call. **Objectives, not notes** — striking off is what prevents the
revisit loop. **The size cap goes in code, not in the prompt**: she has already fabricated four
thousand characters of view block unprompted, which is why `chat.cut_fabrication` exists.

**5 · The prompt rewrite.** Every worked example is an edge case, and nothing tells her `new=` or
`reveals~` exist — she learned `reveals~` only by calling `distance`, once in four sols. Also: the
vision disc is 29 cells, not 49, so "7-cell wide swath" overstates coverage by ~70%; cut the
duplicated preamble; ask for short replies. Two tests pin it and will fail, correctly —
`test_chat.py test_the_prompt_promises_exactly_what_exists` and `test_skills.py
test_the_schema_matches_what_is_wired_up`. Keep `chat.original_SYSTEM` as the control.

**6 · Longer sols.** Everything above is aimed at an unattended run that lasts.

## What a sol actually fails on

`runs/20260902-224413/`, the most recent: 13 drives, 679 new cells, **3 gainless**. The shape is
retracing — swept the west edge, swept it back, drove it a third time for `new=3`, then asked to
drive to the cell it was already standing on. She has no record of where she has been and cannot
read the one she is shown. Separately, told north and east were dust storms she drove to **(1,1)**
and narrated it as *"a long drive south… which moved the rover far north."* The spatial-constraint
result that is the pitch is now **1 for 2**, and the failure was the two-axis version.

## Already rejected — with the reasoning, so it is not rediscovered

- **`read_map()`**, and the windowed `read_map(x0,y0,x1,y1)`. The probe already removed "she wasn't
  looking" — one question, map present, no tools, temp 0, still 0/36. The failure is indexing, not
  awareness, and asking for the same string first supplies no index. The windowed version also
  pushes her back toward short `goto` hops, a regression already fought once.
- **A textual diff line** ("47 cells opened") — carries no map-level information.
- **`look()`** — measured and rejected, which is why `fog()` needs its one line in the free view: a
  forgotten sense costs a whole sol.
- **Widening the stall regex** — 6 caught against 5 false positives, and a false positive tells her
  to act on a turn she was told not to move.

## Three things wrong with the probe, fix before using it again

- **`near_rock` generated 42 items all with truth `rocky`.** It measures a yes-bias, not reading.
- **`biggest_fog` has a baseline of 0.71 to 1.00** depending on world — in world 0 it cannot be
  failed. It can only detect a model that is *worse* than a dart.
- **`settings.GEMINI_RPM = 15`; the observed free-tier limit for gemini-3.x is 5**, and the daily
  cap is 20 requests per model with **failed requests counted against it**. The 429 handler in
  `probe_map.py` also misreads "Please retry in 58.5s" as no delay offered, and aborts a run that
  should have waited. Quota is per model and resets at midnight Pacific.

*Written 2026-09-03.*
