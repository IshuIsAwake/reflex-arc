# AUDIT — explaining this on pen and paper

**What this is for.** Anyone on the team should be able to explain how Reflex Arc works to a judge
with nothing but a pen and paper — no laptop, no scrolling through files. This document is that
explanation, built one piece at a time. The code snippets in here are **cut down for reading**, so
every one of them names the real file and line beside it. If a snippet and the code ever disagree,
the code is right and this document is stale.

Covers prototype 1 as of 2026-08-27: gemma can see and walk. It cannot interact yet.

---

## 1. The map

The map is ASCII art. That is not a simplification for this document — that is literally what is in
the file and literally what the model is sent.

```
#####################
#.............#....$#
#######.#.#####.#####
#.......#...........#
```

`.` is an empty cell you can walk on, `#` is a wall, `^` is a snake pit, and letters are things:
`S` shop counter, `T` tribe counter, `B` notice board, `C` `F` `N` game terminals, `L` lost bag,
`$` coin bag, `*` the vault, `D E v n` doors and gates. The full legend is at the top of
[`config.py`](game/config.py), which is where the maps are typed out by hand.

### The four layers, and this is the part worth drawing

The same cell passes through four functions on its way to gemma, and each one is allowed to change
it. Almost every confusion about this codebase is a confusion about which layer does what.

| Layer | Where | What it does to a cell |
|---|---|---|
| The map on disk | [`config.py`](game/config.py) | the raw character, exactly as typed |
| `Area.at(x, y)` | [world.py:56](game/world.py:56) | ground truth, **except `^` always comes back as `.`** |
| `nav.known(a, x, y)` | [nav.py:30](game/nav.py:30) | that, but `None` if you have not seen it yet |
| `sight.grid(w)` | [sight.py:84](game/sight.py:84) | that, but `None` is drawn `?` and you are drawn `@` |

**The correction worth making out loud: nav does not hide the snake pit — `Area.at` does.**

```python
return "." if ch == "^" else ch  # traps are invisible, always
```
<sub>[world.py:60](game/world.py:60)</sub>

The pit is gone before nav is ever involved. There is no code path anywhere that can leak one,
because the ground-truth function itself refuses to say `^`. That is why `sight.py` has no
trap-handling code at all — and it must never grow any. Pits exist only in `Area.traps`, which the
world checks when you step on a cell, and nothing that talks to gemma is allowed to read.

So what does nav actually add? **The fog.** `Area.at` will happily tell you what is in a cell on the
other side of the map that you have never been near. `nav.known` is the one function that refuses:

```python
def known(area, x, y):
    if not (0 <= x < area.w and 0 <= y < area.h):
        return "#"                                   # off the edge reads as wall
    return area.at(x, y) if area.visible(x, y) else None   # None means fogged
```
<sub>[nav.py:30](game/nav.py:30)</sub>

**It is the map from nav that is fed to gemma**, never `Area.at` directly. That is the single
most important rule in the codebase, and two tests exist purely to count how many times the grid is
read, so that nobody quietly adds a second door.

### Turning it into the picture

`grid()` walks every cell of the area and makes three decisions:

```python
ch = nav.known(a, x, y)
if (x, y) == w.pos:   line.append("@")    # you
elif ch is None:      line.append("?")    # never seen
else:                 line.append(ch)     # whatever nav says is there
```
<sub>[sight.py:84](game/sight.py:84)</sub>

That is the whole conversion. Anything not revealed yet becomes `?`, your own position becomes `@`,
and everything else passes through as it is.

### How a `?` becomes a real character

Two ways, and they are the same line of code:

```python
def visible(self, x, y):
    return self.has_map or (x, y) in self.seen
```
<sub>[world.py:63](game/world.py:63)</sub>

**By vicinity** — every step you take fills in a circle of radius 3 around you, and a cell stays
known once seen. **Or by buying the map** — `has_map` flips the entire area visible at once, which
is what makes maps worth spending coins on.

### One worked example, which is the whole section in miniature

Take the shop counter at (10,16) and a snake pit somewhere on the way to it.

| | shop `S` at (10,16) | a snake pit `^` |
|---|---|---|
| on disk | `S` | `^` |
| `Area.at` | `S` | `.` |
| `nav.known`, not yet seen | `None` | `None` |
| `nav.known`, seen | `S` | `.` |
| what gemma is drawn | `?` then `S` | `?` then `.` |

The shop becomes visible once you get near it. **The pit never does, at any point, under any
condition.** Gemma walks into it and finds out the way anybody finds out.

### And the last point, which is the one people get wrong

**It is not something that is called — it is something that is handed over every single time.**

There is no `look()` function. Gemma cannot ask what it can see. The map is rebuilt from scratch and
attached to the end of every single request:

```python
block = sight.view(self.world)
payload = self.messages + [{"role": "user", "content": block}]
```
<sub>[chat.py:200](game/chat.py:200)</sub>

Note `payload` is a local variable — the map is never stored in the conversation history. Gemma
holds exactly one map, and it is always the current one.

"Every time" means every *request*, not every time you type something. If gemma walks and then
walks again, it gets a fresh map in between, because after the first walk its old position is a lie.

Why it was built this way: what we are trying to watch is what gemma *does* with what it sees, not
whether it remembers to look. A forgotten `look()` costs a whole in-game day and teaches nobody
anything. And when it was tested with `goto` as the only tool, asking *"what is around you?"* made
gemma call `goto` on the cell it was already standing on, twice out of two. Given one tool, it will
use that tool for everything. The sense has to be free, or it gets paid for in steps.
