# Prototype 13 — 11's simulation drives the real rover

13 merges 11 and 12. It runs prototype 11's simulation, with its mission-control screen, and
the real rover can drive every leg of it up to Level 3, as in 12. The simulation is 11's
design, in [`../prototype11/DESIGN.md`](../prototype11/DESIGN.md). The rover's levels, the
link and what was cut on landing are 12's, in [`../prototype12/DESIGN.md`](../prototype12/DESIGN.md).
Both hold here except where this file says otherwise.

## Copied from

- **`game/`** is `prototype11/game/` at `8a740a6`, with the changes below.
- **`hardware/`** is `prototype12/hardware/` at `24eb7c0`. Only the laptop's side changed. `pi/`
  is identical, so the Pi needs only what 12 already needed.
- **`MANUAL.md` and `preview.png`** are 11's.

From the repo root, these show everything 13 changed:

```bash
git diff 8a740a6:prototype11/game HEAD:prototype13/game
git diff 24eb7c0:prototype12/hardware HEAD:prototype13/hardware
```

## What 13 changes

- **The rover pause's hint says who presses SPACE.** 11 asks whoever is watching to press
  SPACE once the rover has stopped, on the strip under the map and in her chat. Under Level 3
  the launcher presses it, so the hint reads "the rover says when it has stopped". After a stop
  from the pad, or a failed link, it says where to put the rover:
  "STOPPED: put it 3 cells (30 cm) east and 2 cells (20 cm) north of home, facing E, then SPACE".
  The game alone reads "SPACE once the rover has stopped". The hint is `dashboard.ROVER_HINT`,
  and `level3.py` sets it.
- **Level 3 opens on the 30.** 11 opens on the 50, which at 10 cm a cell needs 5 m of clear
  floor. 12 was built and run on the 30, which is 3 m. `run_level3.py --arena 50` still gives
  the 50, and the game alone still opens on it.
- **The window's title says prototype 13.**

## The rover's driving comes off her day

Nothing pauses the day's clock, by 11's design, so every second the rover drives is a second
of her day. The placeholder timings are a second per cell and two per quarter turn, with
0.6 s to settle after each stop. So a full 500-step battery of driving costs at least 500 s
of a 600-second day. That is before her thinking, and before the screen redraws each drive
after the rover has finished it, though SPACE skips the redraw. On the rover, the clock rather
than the battery will end most days. The clock also stands still on screen while a leg drives,
and drops by the whole leg when it ends.

## Not decided

- **How the day and the rover's driving fit.** The options are a longer day under Level 3, or
  a clock that stops while the rover drives. Neither is built. To be settled once the timings
  are measured on the floor.
- **The room,** as in 12. Nothing is measured yet.
