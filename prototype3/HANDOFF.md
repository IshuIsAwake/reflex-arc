# HANDOFF — prototype 3

Scoped to `prototype3/`. Repo-wide context in [`../HANDOFF.md`](../HANDOFF.md); standing rules in
[`../CLAUDE.md`](../CLAUDE.md). The code is a copy of prototype 2 at `408e378` and runs the same
way — [`../prototype2/README.md`](../prototype2/README.md). Needs a venv with `pygame`.

## Why this exists

gemma cannot count cells off the map picture. gemini can. The table is in
[`../prototype2/results.md`](../prototype2/results.md).

So the picture is the wrong way to show a map to the model we actually run. We change how the map
is written, not which model reads it. Prototype 2 stays the demo build.

## The work, in order

**1 · RLE.** Write each row as spans instead of glyphs: `y12: x0 unseen, x1 rock, x2-7 open,
x8-49 unseen`. Same map, nothing lost. Every boundary carries its coordinate as text, so there is
nothing to count. She still has to compare spans, so the thinking stays hers.
Costs 0.9× the picture early in a sol and 1.7× late — about 5k characters at worst, against a 16k
window.

**2 · `end(summary)`.** A call she makes to finish her turn. Right now a reply with no call might
mean "I'm done" or might mean she forgot to act, and there is no way to tell them apart — a regex
tried and caught 0 of 12. `end()` makes the difference something the code can see. The summary also
feeds the scratchpad.
*Check it is still needed first.* The last sol had no such replies at all. The tape can't answer
whether that holds, because `chat.py` logs her text and her calls as separate rows with nothing
linking them. Add that link before deciding.

**3 · `fog()`.** Lists the unexplored patches — size and one coordinate each. **It must not say
which is best.** She finds the patches fine and ranks them wrong, twice measured. Giving her the
ranking makes this a lookup table, which is the thing the project exists to beat.
`world.components(w, h, member)` already does the search. Don't write a second one.

**4 · The scratchpad.** A short list of objectives she writes and strikes off. Text she wrote coming
back to her as text is the one channel measured as working. `fog()` corrects it, so nothing needs to
police it. Cap the size in code — she has invented four thousand characters of fake map before.

## What a sol fails on today

`runs/20260902-224413/`: 13 drives, 3 of them gaining nothing. She swept the west edge, swept it
back, drove it a third time, then asked to drive to the square she was standing on. She has no
record of where she has been.

Told the north and east were dust storms, she drove to (1,1) — the far north — and called it "a
long drive south". Holding a constraint is the pitch, and it now works one time in two.

## Probe bugs

- `near_rock` — all 42 questions had the same answer. Measures nothing.
- `biggest_fog` — so easy that a random guess scores 71–100%. Can't be failed.
- Rate limits — `settings.GEMINI_RPM` is 15, the real limit is 5. Daily cap is 20 requests per
  model and failures count. The 429 handler also reads "Please retry in 58.5s" as "no delay given"
  and gives up when it should wait.

## Good first task for someone else

Fix the rate-limit handling above, then finish the probe: 6 `region` and 3 `row` questions on
gemini-3.6-flash. That is 9 calls and answers whether counting works on a second model. Everything
needed is in the tape at `prototype2/runs/probe-gemini-3.7-flash-*/`.

*Written 2026-09-03.*
