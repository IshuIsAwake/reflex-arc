# The LiDAR: Level 4, catching the rover's errors

The rover carries an LDROBOT LD19 LiDAR on a CP2102 USB adapter. Level 4 is Level 3 with the
LiDAR checking the rover before and after every straight run and every turn. When the rover
ends up somewhere else, the game's rover is moved to where it really is. When something is in
its way, that cell becomes rock in the game. Either way A\* plans again to where it was going.
The model is not changed: it reads the same `goto` result, which now names the cell the rover
really reached.

With no LiDAR, Level 4 says why and runs as Level 3.

## How a leg is checked

The game drives a leg, say 10 cells north and 5 east. Level 4 sends it to the rover in
pieces, `F x10`, `R`, `F x5`, using the F L R moves the link already has.

**Before a straight run** it looks ahead, in a strip as wide as the rover plus 3 cm a side
and as long as the run plus 5 cm. If 3 or more points are in it, the rover drives only the
cells that stop 5 cm short, the cell the thing is in becomes rock in the game, and the leg
ends there so A\* can plan round it. The LiDAR sees one flat slice at its own height:
anything lower than it is not seen.

**After each piece** it asks where the rover is:

| what the LiDAR finds | what happens |
|---|---|
| within 8 cm of the plan | OK, the next piece goes |
| heading more than 5 deg off | a short turn back with the pad's `manual` message, then look again, up to 3 times |
| in another cell | OFF: the rest of the leg is dropped, the rover is told its cell, the game's rover is moved there and A\* plans again |
| that cell is rock in the game | the nearest free cell beside it is used instead; the real floor has no rock there |
| no free cell beside it, or a fit it can't trust | LOST: the screen says where to put the rover, as after a stop from the pad |

Position is reported and replanned from, never driven back. The heading is the one thing
turned back, because a heading error turns the next straight run into a diagonal.

**Where it is** comes from `pi/locate.py`. At the start, with the rover on home facing north,
the LiDAR's view of the room is kept. After each piece, a new scan is slid and turned around
where the rover should be (30 cm and 30 deg either way) until its points land on the home
scan's walls. Fewer than 60 % of the points on the walls is POOR, and is not trusted. On the
Pi 4 a check takes about 1.2 s. This is the method of `old_level4`'s `locate.py`, made
simpler.

## Files

```
pi/lidar_config.py      the LiDAR's port and angles, where it sits, the rover's size
pi/ld19.py              reads the LD19's packets off the serial port, checks their CRC
pi/locate.py            where the rover is (a scan lined up with the home scan), and what is ahead
pi/lidar_check.py       run by hand: is it healthy, and which way is forward
pi/lidar_server.py      hello, home, locate and ahead, on port 5006
laptop/lidar_link.py    the laptop's end of lidar_server.py
laptop/checked_legs.py  each leg in pieces, looked ahead of and checked after
laptop/level4_game.py   finds the LiDAR, records home, runs the game with checked legs
```

`game/nav.py` is the one file changed from prototype 14. `leg_finished` may return the cell
the rover is really on and the cells something was found in; those become rock
(`_real_rock`), the rover is moved, and `goto` plans again inside the same `NAV_REPLANS` limit
that rock in the fog uses. When it returns nothing, as in Level 3, the game is as before.
`tests/test_lidar_replan.py` checks all three cases.

## Messages, port 5006

| laptop sends | rover answers |
|---|---|
| `{"op": "hello"}` | `{"ok": true, "lidar": true, "note": "435 good packets in 1.0 s, ..."}` |
| `{"op": "home"}` | `{"ok": true, "points": 426}`: the room from here is kept |
| `{"op": "locate", "x": 3, "y": -2, "heading": "E", "cell_m": 0.1}` | `{"ok": true, "status": "OK", "x": 3.1, "y": -1.8, "heading": 92.5, "matched": 0.84}` |
| `{"op": "ahead", "look_m": 0.35}` | `{"ok": true, "clear_m": null}`, or the metres from the rover's front edge to what is in the way |

Cells are counted from home with `y` growing south, as in `LINK.md`. The answer's `x` and `y`
are not rounded; `heading` is degrees clockwise from north.

## Once, on the Pi

```bash
sudo apt install -y python3-serial python3-numpy
```

From `prototype15/` on the laptop:

```bash
ssh rover "mkdir -p ~/p15"
scp hardware/pi/lidar_config.py hardware/pi/ld19.py hardware/pi/locate.py hardware/pi/lidar_check.py hardware/pi/lidar_server.py rover:p15/
```

The motor server stays in `~/p16`, prototype 16's Pi code. Its `config.py` on the Pi has the
left and right pins swapped so that `F` drives towards the Pi's end (19 Nov); the file before
is kept as `config.py.before-swap`. Its `calib.json` holds the timings measured with the
LiDAR: 0.53 s a cell, 1.77 s a quarter turn.

## Checking the LiDAR

On the Pi, with `lidar_server.py` stopped:

```bash
cd ~/p15 && python3 lidar_check.py
```

It should show about 830 good packets in 2 s, 0 CRC failures and about 10 turns a second.

```bash
cd ~/p15 && python3 lidar_check.py --watch
```

Hold a hand in front: about 0 deg. On the left: about +90. If left and right are swapped,
flip `CLOCKWISE` in `lidar_config.py`. If in front reads another angle, take it away from
`OFFSET_DEG`.

## Each session

1. Phone hotspot on; laptop and Pi on it; motor battery on.
2. On the Pi, two servers, each in its own SSH window (`ssh rover`):

   ```bash
   cd ~/p16 && python3 server.py
   ```

   ```bash
   cd ~/p15 && python3 lidar_server.py
   ```

3. The rover on its home spot, the Pi's end forward: that way is north in the game. Clear
   floor around it, walls or furniture in sight, nobody within a metre.
4. On the laptop, from `prototype15/`:

   ```bash
   .venv/Scripts/python.exe hardware/laptop/level4_game.py --rover nith.local --sols 1
   ```

5. Type `/next` in her chat to start each phase. The terminal prints a `[lidar]` line before
   and after every piece. To stop the rover, switch off the motor battery, or keep
   `level1_pad.py` open and press SPACE.

Give `--rover nith.local`: `rover_address.txt` still names the Pi 5. The arena is the 30 at
0.1 m a cell, 3 m across with home in the middle.

## Measured

18 Nov 2026, standing still: 831 good packets in 2 s, 0 CRC failures, 9.9 turns a second,
about 500 points a turn. The nearest point was 0.14 m, the rover's own body, so points closer
than 0.15 m are dropped.

19 Nov 2026, standing still on home: from the right guess, (0, 0) facing 0 with 100 % of
points on the walls; from a guess 2 cells and 1 cell off, (0.1, 0), within 1 cm; from a guess
90 deg off, POOR, as it should be.

19 Nov 2026, on the floor, the first drives:
- `F` first drove towards the LiDAR's end. With the old 1 s a cell, `F x3` went 57 cm (the
  LiDAR said 57, the tape about the same) and a quarter turn went 163 deg. The check said
  OFF after the run and LOST after the turn, as it should.
- After the pin swap and the new timings: `F x3` ended 1 cm off; the right turn came out at
  84 deg and two fix-up turns brought it to 89; `F x2` ended 4 cm off. Every check OK, 77 to
  85 % of points on the walls.

## Not checked yet

- A whole Level 4 game run with the model.
- Something in the rover's way on the floor: `ahead` has only been seen to say clear, and a
  wall 1.86 m off.
- The rover's half width, `ROVER_HALF_WIDTH_M = 0.10`, is a guess.
- `FIX_POWER` in `checked_legs.py` must match `TURN_POWER` in the Pi's calib.json (0.6).

## Not decided

- Whether `rover_address.txt` should name the Pi 4 (`nith.local`).
- Whether prototype 15's `pi/motors.py` and `pi/config.py` become the L298N's, with the
  swapped pins, so the Pi can run from prototype 15 alone.
- Telling the model in words that the LiDAR moved it, beyond the `goto` result's cell.
- The rover is 30 cm long and a cell is 10 cm, so a route that passes beside a rock can
  clip it. The map's size from the nearest wall, and the cell size that follows, is the
  next step.
