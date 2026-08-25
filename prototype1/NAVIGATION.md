# goto — A\* over the map gemma has

**Built.** `game/nav.py`, driven by `game/console.py`, checked by `game/test_nav.py`.

The world knows where every wall is. The planner is not allowed to. Everything below
follows from that one constraint.

## The contract

```python
goto(world, x, y)                        # dodge only the walls it knows about
goto(world, x, y, avoid=[(a, b), ...])   # ...and these cells, this trip only
goto(world, x, y, avoid="auto")          # ...and every cell it has marked
distance(world, x, y, avoid=...)         # planned length, costs nothing
```

| return | when |
|---|---|
| `DONE(at, steps)` | standing on the target, or beside it if the target is solid |
| `BLOCKED(at, stopped, steps, walls)` | the plan hit walls that were not on the known map |
| `TRAPPED(at, steps)` | a snake pit with no antidote left; gemma wakes in the Plaza |
| `LEFT_AREA(area, at, steps)` | walked onto a gate, so coordinates now mean something else |
| `UNREACHABLE(at)` | no route exists even assuming the fog is empty |
| `UNREACHABLE(avoid)(at)` | ...but there would be one without the avoid list |
| `NOT_VISITED(at)` | `avoid="auto"` to somewhere it has never stood |
| `OUT_OF_STEPS(at, steps)` | the day ended mid-path |

`at` is what the call is about — where gemma ended up, or the wall it hit. `stopped`
appears only when those differ. Every return carries `steps`, because the day is made
of steps and gemma has to be able to account for them. `walls` and `antidotes` are
appended to any result that collected them, so a trip that detoured around three walls
and burned an antidote still reports all four facts from one call.

## The planning graph

`nav.known()` is the only read of the grid in the module, and it returns `None` for a
fogged cell. Four rules:

| cell | in the plan |
|---|---|
| known wall | impassable |
| known floor | passable, cost 1 |
| **fogged** | **passable, cost 1 — assume it is clear** |
| in the `avoid` set | impassable |

**Fog is optimistically empty, and that is the whole design.** Treat it as wall and
gemma can never path into unexplored ground; treat it as truth and it is omniscient
and maps stop being worth buying. Assuming it is clear makes every plan a *hypothesis*
— walk it, and where reality disagrees you get a wall to write down.

The measurement falls out for free. Aiming at the Plaza coin bag with no map,
`distance()` promises 22 steps and the walk costs 43. That gap **is** what the map is
worth, in the same currency `economy.py` prints. `world.nav_log` records promised
against walked for every call.

`avoid` is impassable, never merely expensive. If gemma asks to dodge a cell and the
planner routes through it anyway because the detour looked long, the primitive is
untrustworthy and the notes file stops meaning anything.

### The trap that would kill this silently

**`Area.at` returns ground truth whether or not the cell is fogged.** `Area.visible`
does not gate it. Read one without the other and the planner sees the whole map,
everything keeps working, and the first symptom is wondering why nothing ever goes
wrong. `nav.known()` is the single door; `test_nav.py` counts the reads in the file and
fails if a second one ever appears.

The same property is why **the planner cannot cheat on snake pits even by accident** —
`Area.at()` returns `"."` for a pit at every fog setting, so there is no code path by
which A\* can see one. That is an absence of a special case, not the presence of one.
Do not add one.

## Executing

Steps go through `world.move(dx, dy)`, never a reimplementation — `move` already
charges the step, reveals fog, records `visited`, springs pits and crosses gates. Every
outcome is detected from observable effects rather than by reading `Area.traps`, so
there is nothing to leak.

**The walk stops face to face with the wall.** It carries on until a step is actually
refused, records the cell, and replans from there. It does *not* stop the moment fog
reveals a contradiction further down the path.

> **Rejected: a standoff margin.** Stopping at vision range wastes fewer steps, and on
> the rover a hazard is genuinely dangerous to approach. Ishan worked the trade on
> 2026-08-25 and picked the opposite: stopping three cells short discloses one tile of
> the obstruction, while walking up to it reveals the whole local arc — more map, fewer
> `goto` calls burned rediscovering the same wall, and touching a wall in a game costs
> nothing. The rover version of this rule will be different, and that is the rover's
> problem. Do not reintroduce a tunable margin here to serve both.

### One `goto` is atomic, and in fog that looks like teleporting

Nothing is drawn between steps, so the whole walk happens inside one console
command and the player appears at the far end of it. In a revealed area that is
invisible — the route is direct, a median of 7 cells, and it ends on the cell you
named. Through fog it is not. Measured on the Plaza, 40 unmapped trials:

| `NAV_REPLANS` | ends on the goal | median walk | worst walk |
|---|---|---|---|
| 0 | 14/40 | 7 | 15 |
| 5 | 24/40 | 13 | 39 |
| 10 | 25/40 | 13 | 71 |

At 5 a single call has been seen walking 31 cells, revisiting 9 of them, and
stopping `BLOCKED` six walls later somewhere the caller never asked for. That is
the design working — each replan is a fresh hypothesis over a map that is still
mostly fantasy — but **it is not a correctness bug and it is not erratic**; every
move is one cell and every path is shortest given what was known when it was
planned. If it needs to *look* right, the fix is a redraw per step, not a change
here. Turning `NAV_REPLANS` down to 0 buys legibility at four fewer facts a call.

`settings.NAV_REPLANS = 5` is how many times one call replans before handing back
`BLOCKED`. Aiming north out of the Plaza with no map, that one call comes back having
found six walls and walked 26 steps against a promised 14 — six facts for one model
call. Set it to 0 for strict one-surprise-per-call and compare; it is a setting, not an
architecture. If a replan finds no route at all, the call returns `BLOCKED` rather than
`UNREACHABLE` — gemma is somewhere new by then and calls again from there.

The second-opinion search happens **only from the get-go**. If the very first plan
fails, the planner tries once more without the avoid list to tell
`UNREACHABLE(avoid)` from `UNREACHABLE` — "drop your list and you could get there" and
"there is no way" are different facts. Mid-walk, no second opinion: gemma calls again.

**A solid target means "get next to it."** Terminals, counters, bags and the board are
solid, so `goto(30, 16)` at the tribe would be `UNREACHABLE` taken literally. The plan
ends on the cheapest free neighbour and returns `DONE` from there, so `goto` followed
by `interact` reads the way gemma expects.

**A known wall gets none of this.** The rule reads `THINGS`, not `SOLID`, and `#` is
the difference. Asking to walk into a wall already on the map is a mistake and the
honest answer is `UNREACHABLE`; `DONE` says you arrived somewhere you never went,
and a caller that believes it has moved has nothing to correct. That cost a four-day
model run on 2026-08-26 — see [`FINDINGS.md`](FINDINGS.md). A **fogged** cell that
turns out to be a wall is untouched: that one is a hypothesis, and walking into it is
how the map fills in.

**Gates are aimed at, never routed through.** Stepping on one teleports you, so no plan
may cross one in transit. A shut gate as the destination counts as solid: you stop
beside it, `DONE`, and press E — gates never open by being walked into. An open one as
the destination you step onto, and the call returns `LEFT_AREA`. Crossing therefore
costs two `goto` calls and the second one is in different coordinates, which is the
honest way to say what happened.

## Pits and antidotes

An antidote absorbs a pit and **the walk carries on**. It is a note to write down, not a
reason to hand control back; gemma is still standing where it meant to be. Falling in
with an empty pouch ends the trip, because it puts gemma in another room.

With one antidote and two pits on the route, the first is absorbed and the second ends
it: `TRAPPED(at=(14,14), steps=4, antidotes=[(12,14)])`. Both cells are reported, so a
single call is worth two notes.

## `avoid="auto"`

Skips every cell in `Area.marks`, and is legal **only when the destination is in
`Area.visited`** — somewhere gemma has actually stood. Otherwise `NOT_VISITED`.

This is the commute, not the expedition. Going back to the tribe or the snake terminal
is one call forever. Somewhere new, or a one-time pickup like a coin bag or the vault,
means naming the cells by hand — so the explicit list keeps a real job instead of being
shadowed by the convenient one.

`distance()` does not enforce the visited rule. That rule is about committing steps,
and `distance` commits none.

**The vault is the deliberate exception.** Every route in crosses pits on purpose,
`avoid="auto"` is not offered for it, and a planner that has spent days learning "pits
are bad" has to override itself. Do not soften it.

## What the tests are actually for

Most of `test_nav.py` is ordinary — A\* agrees with a plain BFS on a mapped area, a
solid target lands adjacent, steps charged equal tiles walked. Two are load-bearing:

- **`test_the_planner_is_not_omniscient`** — a plan made through fog must walk straight
  into walls it has never met. If it starts dodging them, `visible()` has been dropped
  somewhere.
- **`test_an_unmarked_pit_is_still_walked_into`** — a pit fallen into but never marked
  is still walked into by `avoid="auto"`. **If this ever goes green the mechanic is
  dead**: it would mean the world is marking pits for gemma, and the notes file has
  stopped being the thing under test.

## The human's way in

Press `T`. Type `goto 19 13`, `goto 30 16 avoid=auto`, `goto 15 10 avoid=(3,4),(5,6)`,
`distance 27 5`. It prints back the exact string gemma gets, so playtesting the planner
and reading a model transcript are the same activity. `M` draws the last planned route
in blue, which makes a wrong plan visible instead of inferred — and through fog it often
is wrong, which is the point.

## Deviation from the original spec

The spec called for `plan(area, start, goal, avoid)` and `walk(world, path)`. Replanning
has to own the plan, so the split is `plan()` — pure, testable, no world — and `goto()`,
which drives it. `walk()` as a separate public function would only ever be called by
`goto`.
