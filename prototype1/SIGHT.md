# What gemma is told, and what it can ask for

**Built.** `game/sight.py` is the sense, `game/skills.py` is the hands, `game/chat.py` bolts them
to the model. Checked by `test_sight.py`, `test_skills.py`, `test_chat.py`.

Two capabilities landed together on 2026-08-26 and they are deliberately different shapes. Getting
them backwards is the mistake this file exists to prevent.

- **`goto` and `distance` are tools.** Gemma asks; the world answers.
- **The view is injected.** It arrives unbidden at the end of every request and there is no way to
  request it.

## Why there is no `look()`

What prototype 1 is trying to watch is what gemma does with what it sees, not whether it remembers
to look. A forgotten `look()` costs a whole day and teaches nobody anything, which is the same
argument that put the notes file in the day's first message rather than behind a `read_notes()`.

It is also what the model does when you give it the choice. Measured before any of this was built:
asked *"what is around you?"* with `goto` as its only tool, gemma called `goto` on the cell it was
already standing on, twice out of two. **Given one tool it will use that tool for everything.** The
sense has to be free, or it gets paid for in steps.

## Live means replaced, not appended

`chat.py` builds every request as `messages + [view(world)]` and stores the view nowhere. Context
therefore holds exactly one view and it is always the current one.

Appending would accumulate stale maps to reason off, and the real runs already reached 9,391 prompt
tokens before a grid existed. Rebuilding per *request* rather than per human turn matters for a
second reason: in the middle of a tool chain gemma has just moved, so the previous block's position
is a lie. It sits at the end rather than the front because Ollama caches the prompt prefix — a block
that changes every turn is free where it is and would invalidate the whole conversation at the
front.

**The trap that follows.** Context keeps only the newest view, so unless every view is written down
as it was, a finished run cannot be read back at all — and reading a run back, not testing, is how
the wall bug was found. The tape gets each view in full; the pane gets a one-line summary, because
twenty-five rows of ASCII a turn would bury the conversation beside it. `V` prints the real block.

## It shows the accumulated map, not the sighted disc

This was the open question in the handoff. It went to the accumulated map on an argument that was
not on the table when the question was written: **`nav.known()` returns `"#"` off the edge of an
area, so the planner already reasons over the whole seen-set and the area's extent.** Show gemma
only the radius-3 disc and it cannot explain its own `UNREACHABLE`, cannot price a trip, and cannot
tell a wall it has met from one it merely guessed at. The mismatch was the whole objection to the
disc, and it is fatal.

The cost objection died on measurement: the largest area, fully mapped, is about 280 prompt tokens,
and the block is replaced rather than appended, so that is a flat tail cost per request.

**And the obvious economy — dropping the cells that are empty or unseen — makes it five times
bigger.** Mapped plaza: the ASCII grid is 196 tokens, the same rows as run-length spans are 598, and
a list of only the non-floor cells is 972. Repetitive characters collapse to almost nothing;
`(3,4)` costs about six tokens on its own. Anything coordinate-shaped is expensive. For scale, the
system prompt and tool schemas together are a fixed 1,028 tokens per request against a day-one view
of 467 — **the map is not the expensive part and never was.**

**The area's extent is disclosed on purpose.** `DESIGN.md` left this open for `M`. A grid you cannot
index is useless, the planner already knows the dimensions, and hiding them would reintroduce
exactly the mismatch above.

The block carries the status line, the axis convention in words, the grid with rulers, a legend of
only the glyphs actually on it, the four cells you could step into, and **a named list of every
known thing with its coordinate**.

**The grid is a picture and not a lookup table, and the difference is measured.** Asked what
character sits at ten named cells of a fully mapped plaza, gemma answered **5 out of 10** correctly —
and exactly 5 out of 10 with thinking switched on, at 562 seconds against 3. It cannot index a
monospace grid and it states wrong readings with complete confidence.

That is the whole reason the block pre-computes everything exact. Standing in the shop alcove at
(10,15), gemma announced it could see "clearly visible floor tiles" east and west, called `goto` on
both, got `UNREACHABLE` twice, and concluded it was "stuck in a cycle of failure." Both cells are
walls; the planner was right every time. So the grid carries shape, the things list carries
landmarks with their coordinates, and the neighbour list answers *can I step there* and *how far is
this direction open* in words. The heading over the grid says it is not a table.

**The system prompt also forbids it from doing the planner's job.** `distance` is exact, never
wrong, and costs no steps — it was sitting unused while gemma counted characters and got it wrong.
A model asked to reason about reachability from a picture will try, and fail quietly.

## The one gated door, again

`Area.at` returns ground truth at every fog setting. `nav.known()` is the single read of the grid in
the whole codebase, and `sight.py` is the second thing through it after the planner. One dropped
`visible()` check makes the view omniscient, everything keeps working, and the first symptom is
wondering why nothing ever goes wrong.

`test_sight.py` counts the reads the way `test_nav.py` does, and asserts a snake pit reads as
ordinary floor in an area whose map has been bought — not merely that no `^` appears, which would
pass if pits were drawn as something else.

## The skill interface

```
goto(x, y, why, avoid=[(a,b), ...])       walk there. One step per tile
distance(x, y, why, avoid=[(a,b), ...])   what it would cost. Spends nothing
```

Return codes and the planner's rules are in [`NAVIGATION.md`](NAVIGATION.md). Three things belong
here instead.

**Coordinates are absolute, and the schema says so.** It is the only way *"go ten blocks north"*
works: gemma reads its own position out of the view, does the arithmetic, and passes the answer. Six
for six on the probe, and again live.

**`why` is required on every call** — one line, written before the outcome comes back. A rationale
recorded before the result is a prediction; one offered afterwards is a story. The world never reads
it. `conv.bad_args` counts the calls rejected for want of one, and that count is what the
requirement costs.

**`avoid="auto"` is not offered yet**, and is refused by name if asked for. It skips every cell gemma
has marked, and gemma cannot mark a cell until `mark()` lands — advertising it would describe a
capability whose other half does not exist. It was not a hypothetical risk: with `avoid` described
loosely as *"optional"*, gemma volunteered `avoid="auto"` unasked, which would have returned
`NOT_VISITED` for a reason it never intended. Tightening the description to *"omit it entirely
unless you have a specific cell in mind"* fixed it three for three.

Everything is parsed generously and rejected loudly. `(3,4),(5,6)`, `3,4 5,6` and `[[3,4],[5,6]]` all
mean the same thing; `'<nil>'`, an odd number of coordinates, and a string with no numbers in it are
all `BAD_ARGS`. **A `BAD_ARGS` spends no steps** — a malformed call is a mistake, not an action, and
charging the day for it would make the parser part of the difficulty. The failure being guarded
against is specific: an `avoid` list that quietly became "avoid nothing" would walk gemma through
the exact cell it named, say nothing, and the notes file would take the blame.

## The loop, and where the world changes

The model call is a socket on a background thread and produces nothing but text and requests.
**Every world change happens on the main thread inside `pump()`**, one frame later, where the
renderer is. A walk cannot land halfway through a redraw, and the whole exchange stays drivable from
a test by pushing onto the same queue.

`MODEL_MAX_HOPS` caps tool calls per human turn. It is not tidiness: `distance` costs no steps, so
the day's budget is no backstop against a model looping on a misread position. **The cap takes the
tools away rather than asking** — the first version appended *"stop and say what you have found"*
and then made an ordinary request, gemma called another tool, and the cap fired four times in one
turn. A limit enforced by asking the thing being limited is not a limit.
