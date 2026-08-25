# What the gemma spike cost to learn

On 2026-08-26 the whole gemma integration was built in one session — skill interface, Ollama loop,
persistence, transcript replay and a watch window — and then reverted. The code is on the
`spike/gemma-integration` branch and works; it was taken off main because it landed in one go
instead of a feature at a time, which is not how this repo is meant to be built.

**This file is why the revert is not a loss.** Every item below was paid for by running the thing,
and most of them are invisible to a code review: the tests were green through all of them. Read it
before rebuilding any part of the interface. Where a decision was taken, the reasoning is here so it
is not re-argued; where a bug was found, the symptom is here because the symptom is the hard part.

## The three that cost the most

**A lying success code is worse than any failure code.** `goto` to a cell gemma could already see
was a wall answered `DONE`, because the "a solid target means get next to it" rule read `SOLID`,
which contains `#`. Gemma was told it had arrived somewhere it never went, so it had no failure to
reason about, and it spent four days stood next to the shop at nought coins re-issuing a move it had
been told succeeded. Its notes concluded *"physical progress is difficult."* The rule must apply
only to things you interact with. A **fogged** cell that turns out to be a wall is the opposite case
and must stay walkable — that one is a hypothesis and walking into it is how the map fills in.

**Ollama's `num_ctx` defaults to 4096 whatever the model can hold, and truncates silently.** It
drops the oldest messages without a word. A day loses its own morning, gemma reads as forgetful
rather than starved, and nothing in the transcript looks wrong. Set it explicitly and watch
`prompt_eval_count` — the day-one briefing alone is about 1,800 tokens.

**An ambiguous number in a line read after every call becomes a fact in the notes file.** The status
line said `antidotes 0/1`; gemma wrote down *"1 antidote available"* with none in the bag. Anything
repeated after every single call is read cold, out of context, and is worth spending six words on.

## Smaller, and still not obvious

- **`DONE(at=(10,15))` for a `goto(10,16)` reads as failure.** A solid target lands you beside it,
  and unless the answer says so, the model concludes it has not arrived. It asked for the same cell
  four times running. Adding a `beside=` field fixed it — and introduced the wall bug above, so add
  it to *things* only.
- **`goto` never advertised that it walks the whole way**, in neither the prompt nor the tool
  description, so gemma stepped one tile per call. Free to fix, and it changes the whole shape of a
  run.
- **How far it aims is set by what it wants, not by what it can see.** One sample each: with the
  Plaza mapped it walked 2 cells to a shop it could see; with nothing but fog it aimed 24 cells at
  (0,0) *because* it could not see. Do not expect a map to buy longer journeys.
- **The buzzer must not lock gemma out of its notes.** A `goto` that spends the last step mid-
  corridor was ending the day with the whole day's record unwritten. Calls that cost no steps should
  stay legal after the budget is gone, and the loop should leave a turn or two to write.
- **A tolerant argument parser must still fail loudly.** An `avoid` list that quietly parsed to
  "avoid nothing" would walk gemma through the exact cell it asked to dodge and never say why — and
  the notes file would take the blame for a parser bug.

## Decisions taken, with the reasoning

These were settled deliberately and are worth keeping. They answer three of the open questions at
the bottom of [`DESIGN.md`](DESIGN.md).

**A `why` on every call**, one line, written before the outcome comes back. The world never reads it
and it changes nothing. A rationale recorded *before* the result is a prediction; one offered
afterwards is a story. Count the calls that fail for want of one — that is what the requirement
costs.

**The notes are injected into the day's first message, not fetched with a `read_notes()`.** What is
under test is what gemma writes and whether it corrects it, not whether it remembers to go and look.
A forgotten `read_notes()` costs a whole day and teaches nothing anyone wanted to know.

**`play` and `interact` are separate, and playing needs adjacency.** Interacting with a terminal
discovers what game it runs; `play` spends the cooldown. Otherwise a cooldown is spent as a side
effect of walking somewhere. Playing from across the room would also delete the travel economy,
which is the only thing making the tribe's far corner mean anything.

**Discovery needs no rule of its own.** An undiscovered terminal is *called* `discover`, which is
not the name of a game, so there is no name gemma can pass to `play` for one it has not walked up
to. Falling out of the naming rule beats a check that can be forgotten.

## The order to rebuild in

One at a time, each landing with its own tests before the next starts.

1. **Break the three couplings in `world.py`** and move the naming rule out of `render.py`. No new
   files. The handoff lists all four.
2. **`look()`**, fog-gated. It is the second place after the planner where one missing `visible()`
   check hands over the whole map, so it wants the same "count the reads" test `nav.py` has.
3. **The rest of the skills** behind the console, typed by hand. A skill that is awkward to type is
   a skill that is awkward to call, and this is where that gets noticed for free.
4. **Persistence**, before any model loop. Prototype 1 is several days long and a process is not.
5. **The Ollama loop** — and nothing else in the same step.
6. **Reading runs back.** Worth its own tool early; the transcript is the actual output of this
   prototype, and the wall bug above was found by reading one, not by testing.
7. **A window to watch it in**, last. It is a demo aid, not part of the experiment.
