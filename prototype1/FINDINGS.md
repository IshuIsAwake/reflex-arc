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

## Not from the spike, but found the same day

**A `goto` executes atomically, and through fog that reads as teleporting.** Nothing redraws between
steps, so the player appears at the end of a walk that may have been 31 cells long, doubled back on
itself, and stopped somewhere nobody asked for. It is not a correctness bug — every move is one cell
and every path is shortest given what was known — and the numbers are in
[`NAVIGATION.md`](NAVIGATION.md). Two things follow. A watcher needs a redraw per step to be worth
having, which is what `world.on_move` existed for in the spike. And `NAV_REPLANS` trades legibility
against facts per call: at 0 it stops on the first surprise, at 5 it comes back with six walls and no
obvious connection between what you asked for and where it ended up.

**A picture of the plan gets read as a picture of the walk.** The map view drew `last_path`, which is
replaced on every replan, so a blocked `goto` showed the sixth hypothesis and nothing of the five
attempts that had produced the walls it was reporting. Read off the screen by hand on 2026-08-26:
`goto(1,1)` from the Savana's west gate came back `BLOCKED(at=(12,8), stopped=(13,8), steps=24,
walls=[(1,11), (4,11), (7,11), (10,11), (13,11), (12,8)])`, and the drawing ran west across walls
nothing had ever touched. That reads as a planner routing through walls, and it cannot answer the one
question worth asking — how did the thing get inside a maze behind a sealed band. Through the single
gap at (15,11), five replans in. `world.last_walk` now records every cell actually stepped on and the
map shades it. The walk can never cross a wall and the plan can, so where the two disagree is exactly
where the fog lied.

## What sight and `goto` cost to learn, 2026-08-26

Four live runs, rebuilding the interface by hand. The build is written up in
[`SIGHT.md`](SIGHT.md); this is what running it taught that speccing it did not.

**A field is not a sentence.** The `beside=` field above was the fix for "arriving reads as not
arriving", and it was not enough. Gemma read `DONE(at=(10,15), beside=(10,16))` as a failure to reach
(10,16) and spent an entire run trying to step into a shop counter — *"moving there has no apparent
effect."* The same failure as August, one layer further in. `Result.advice` now says it in words:
*"(10,16) is solid, so stopping beside it IS arriving."* It is kept off `__str__` because the HUD
does not wrap and the console truncates at 88 characters, so folding it in overflowed one surface
and silently cut the other.

**A costless success is the polite cousin of a lying one.** Seven identical `goto(3,8)` calls, seven
honest `DONE(steps=0)` answers, and no reason to stop: a success that cannot advance anything leaves
the caller nothing to correct. It repeats. `skills._stuck` says so from the third repeat. The real
cause was that it wanted to *use* the board and `interact` does not exist — which is what put
`interact` next.

**A limit enforced by asking is not a limit.** The tool-call cap first appended *"stop and say what
you have found"* and made an ordinary request; gemma called another tool and it fired four times in
one turn. Withholding the tool schemas was still not enough — it fired **eight** times. Only a flag
that drops later calls on the floor actually stopped it. Assume anything delegated to the model's
cooperation, at any remove, will not hold.

**Gemma cannot index a monospace grid, and will state wrong readings confidently.** At (10,15) it
announced "clearly visible floor tiles" east and west, called `goto` on both, and got `UNREACHABLE`
twice; both are walls and the planner was right every time. Its conclusion was that it was "stuck in
a cycle of failure." The view now names the four adjacent cells in words, after which it read them
back exactly. **Any coordinate the model has to count out of a grid is suspect** — give it the
answer instead.

**With one tool it uses that tool for everything.** Asked *"what is around you?"* with `goto` as its
only skill, it called `goto` on the cell it was already standing on, two times out of two. That is
the measurement behind injecting the view rather than offering a `look()`. Once the view was
injected and a second skill existed, the same question drew **zero** tool calls.

**An optional argument gets volunteered.** With `avoid` described merely as "optional", gemma passed
`avoid="auto"` unasked, which would have returned `NOT_VISITED` for a reason it never intended.
Describing it as *"omit it entirely unless you have a specific cell in mind"* fixed it three for
three. Related to the `'<nil>'` note above and the same lesson: an argument the model does not need
must be made actively unattractive, not merely not-required.

**The cheap news.** `bad_args` was 0 across every run, 56 calls in total, so the required `why` and
the tolerant parser cost nothing measurable.

**Run-to-run variance is large, and an n=1 comparison here is worthless.** The same four-turn script
on the same build gave 31 calls, then 14, then 32. A drop from 31 to 14 was written up as a win and
was mostly luck; the next run took it straight back. **Do not report a single run as a result** —
what survived repetition was the structural stuff (the cap firing at most once, zero `bad_args`, the
arithmetic on "go six blocks north" landing right three times out of three), not the totals.

**Check the fact, not the label.** The "you have asked for this three times" nudge originally fired
only on `DONE`, because `DONE(beside=..., steps=0)` was the loop being watched. A live tape then
showed the identical loop wearing a different code: five consecutive `goto(0,5)` calls, five
`UNREACHABLE(at=(13,5), steps=0)`, no nudge. The rule is now an invariant rather than a list —
**a call that spends no steps cannot have changed the world, so an identical call after it is
guaranteed the identical answer** — which covers arriving beside something solid, an unreachable
target and pricing the same trip twice, all at once. A detector written around the case in front of
you will keep missing the case that has not happened yet.

**The template leaks into what the model "said."** Every one of eight gemma turns ended `<channel|>`,
and because the reply becomes an assistant message, the token went back into context every turn and
into the transcript. Found by reading a tape; no test would have caught it and nothing looked wrong
on screen. `chat.clean()` strips a known list and counts what it strips — an explicit list rather
than a catch-all `<...>` sweep, which would one day eat real content and never say so.

**Raising the context window is not free, even locally.** `ollama ps` reports `gemma4:e4b` at 10.85
GB total with **3.69 GB on the GPU** — the other 7.2 GB already runs on CPU, which is what the 20
tok/s actually is. A larger `num_ctx` grows the KV cache and pushes more layers off the card, so it
buys context by making every token slower. And it does not fix the cause: within one day, 40 tool
calls appended 6–8k tokens of pure call history, so doubling the window buys one session. The
nightly reset and the notes file are the design's own answer; `gemma4:e4b-it-qat` (6.1 GB) is the
swap that would change the hardware picture.

**What it does when it has nothing to do is wander.** Told *"go to the shop"*, it arrives in one
call and then spends the remaining seven exploring at random, hitting the hop cap. Every turn binds
against the cap for the same reason. This is not a loop bug and no wording fixes it: there is
nothing to *do* at a shop without `interact` and `buy`, and no reason to prefer one direction over
another without a goal. It is the clearest argument in the file for what to build next.

### Two things measured because they looked obvious and were not

**Dropping the empty cells makes the view five times *bigger*.** The intuition is that feeding 400
mostly-blank tiles every turn is wasteful, and it is wrong. Counted on `gemma4:e4b`, mapped plaza:

| representation | tokens |
|---|---|
| ASCII grid with rulers | **196** |
| rows as run-length spans (`15: wall 0, floor 1-7, ...`) | 598 |
| only non-floor cells, as coordinate lists | 972 |

A run of `#####` collapses to almost nothing, while `(3,4)` costs about six tokens *per cell*.
Anything coordinate-shaped is expensive and anything repetitive is nearly free. The whole day-one
view is 467 tokens against a fixed 1,028 for the system prompt and tool schemas together — **the map
is not the expensive part of the request and never was.** Do not re-derive this by argument.

**Thinking does not help it read the grid, and costs 187× the time.** Ten cells named by coordinate,
answered against a fully mapped plaza:

| | correct | wall clock | output tokens |
|---|---|---|---|
| `MODEL_THINK = False` | 5/10 | 3s | 20 |
| `MODEL_THINK = True` | 5/10 | 562s | 12,006 |

On one cell it spent 124 seconds and still answered "floor" where a coin bag is. **The real number
is the 50%**, which holds either way: gemma cannot index a monospace grid and will state a wrong
reading with complete confidence. That is not fixable by giving it more room to think, so the view
pre-computes every exact fact — the four neighbours, how far each direction is open, and every thing
with its coordinate — and the grid heading now tells it the picture is not a table. The prompt also
tells it never to work out reachability itself: `distance` is exact, costs no steps, and was sitting
there unused while gemma counted characters and got it wrong.

## The model types the call out instead of making it, 2026-08-29

**About one turn in ten, `gemma4:e4b` writes `goto(25, 15, "…")` into its reply as text with no
`tool_calls` attached.** Nothing runs, nothing moves, and the pane shows a confident sentence beside
a rover that never went anywhere. **It is the vanishing call again** — the third variant in this
file after the lying success code and the refused call nobody was told about — and someone watching
reasonably concludes the skill is broken.

Measured against a live model on the exact request the game builds, five prompts, ten samples per
cell. Both prototypes ship without `temperature`, so Ollama uses the model's own ~0.8:

| | `temperature` 0 | ~0.8 (unset) |
|---|---|---|
| streamed — what the game does | **9 / 10** | 7 / 10 |
| non-streamed | 9 / 10 | 8 / 10 |

**Three warnings, each of which cost a wrong answer on the way to that table.**

*The prompt is not the problem.* Swapping in a different system prompt, and stripping the map out of
the view entirely, both changed nothing. Do not go rewriting prompt paragraphs at this symptom.

*Do not report a rate off four samples.* The number was first given as 9/12, then as "temperature
does not help at all", before forty samples settled it at roughly 1 in 10 with temperature pinned
and 2–3 in 10 without. Both earlier figures were noise, and this file's own **never quote one run as
a result** applies just as hard to ten.

*A backstop that re-asks is not a fix.* Told it had typed the call out and given another turn, the
model typed it out again. The retry is worth having because it makes the failure visible; it does
not recover it.

**What actually works is reading the call and running it.** A written `goto(35, 25, "why")` names
the skill and every required argument — it is a decision the model made and Ollama failed to encode,
so parsing it is reading intent, not inventing it. Prototype 2 does this in `skills.written_call`,
accepts only a *complete* call, validates it like any other, and labels every recovery in the pane
and on the tape. Incomplete ones still get refused.

**And the worse half: the model writes our side of the conversation too.** In the failing turns it
frequently keeps going past the typed call and produces **four thousand characters of invented view
block** — a full grid, a step count, a position it has never occupied. Left alone that becomes an
assistant message and every later turn reasons over a map it made up. It is the `<channel|>` leak
one floor up: there a stray token, here the entire other speaker. `chat.cut_fabrication` cuts at the
view's own headings.

**Prototype 1 has all of this, unfixed**, and the code is byte-identical. `MODEL_TEMP = 0.0` in
`settings.py` plus sending it at [chat.py:233](game/chat.py:233) is two lines; the recovery and the
fabrication cut are worth porting before the next real run here.

Caveat: `temperature = 0` is *near*-deterministic, not exactly so — identical requests still
diverge, because Ollama is not bit-exact across a GPU/CPU layer split.

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
