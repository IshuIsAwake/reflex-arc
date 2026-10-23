# hardware/ — the rover side of prototype 12

```
hardware/
  run_remote.py       Level 1 -- drive it by hand, keys or a gamepad        double-click
  run_lidar_map.py    the LiDAR live; map the room, room check, locate      double-click
  run_level2.py       Level 2 -- plain words, the language model drives     double-click
  run_level3.py       Level 3 -- the simulation in ../game drives, no LiDAR double-click
  run_level4.py       Level 4 -- Level 3, every move checked by the LiDAR   double-click
  rover_address.txt   how the run_ files find the Pi (rpi5.local)
  laptop/             the code behind the run_ files
  pi/                 what runs on the Raspberry Pi -- copied to ~/p16 there
```

Every mode uses the same rover server and the same link. The LiDAR adds a step to the same
loop; it is not a second program. Several run_ files can be open at once -- the map beside
the game, say; one drive at a time still.

## Each session

1. Phone hotspot on; laptop and Pi on it; motor battery on.
2. Start the rover server on the Pi, and leave it running:
   ```bash
   ssh nithin@rpi5.local
   ~/rover stop                       # only if PI_5's ROS stack was started
   cd ~/p16 && python3 server.py      # prints "lidar: LD19 open" and "listening"
   ```
3. On the laptop, double-click one `run_` file, or run it: `python run_remote.py`.

`run_level3.py` takes the simulation's options: `python run_level3.py --sols 2`. Type `/next` in
its chat to start each phase. Don't press SPACE while it shows ROVER DRIVING; the launcher does
that when the rover reports the leg done.

No Pi? In one terminal `python pi/server.py --fake-world --fast` -- a pretend rover in a pretend
6.6 m room, with a LiDAR, whose turns come up 15 % short -- then any run_ file with
`--rover 127.0.0.1`. `--fake` alone is motors only, printed.

## Setting up a room, once

1. **Mount check.** On the Pi, server stopped: `python3 lidar_check.py --mount`. It records the
   room first, then you hold an object 15–30 cm in front, then on the left, at the height of the
   LiDAR's head. Until this is done the rover refuses every LiDAR-checked drive. Restart the server.
2. **The room's map** in `run_lidar_map.py`: rover on its home spot facing north, **H**. One
   360° scan, and the walls it sees are the map. Only if something hides a wall from home: **M**,
   drive round with the **arrow keys** stopping now and then, back to home, **M** off.
3. **Room check**: **R**. The **nearest wall** sets the size: map side = 2 x (nearest wall −
   0.4 m), cells = map / 30, drawn as the blue square; **K** keeps it. Smallest map 3 x 3 m
   (0.1 m cells), cap 10 m. Too small: *"clear the map: the nearest wall or object is 0.98 m
   away (east) ..."*, and nothing is kept. The LiDAR only sees its own height: look at the floor.
4. **Calibrate** on the floor: `calibrate.py forward` measures the speed, so any cell size then
   takes the right time; `calibrate.py turn`.
5. Rover on home, facing north. `run_level4.py` -- the map window can stay open beside it.

Several windows can be connected at once (game, map, pad); only the one driving stops the
motors when it closes, and any window's stop stops them.

After every turn and every forward run (long runs every 5 cells) the rover stops, locates, and:
heading off by more than 5 deg -- turns back by what it measured, up to 3 times; in the wrong
cell -- says so (Manhattan, Chebyshev) and carries on from where it really is; 2+ cells out --
stops LOST; the fit not trusted even on a second, wider look -- stops UNSURE.

After every leg the **simulation follows the LiDAR** (`laptop/correct.py`): its rover is moved to
the measured cell, fog and visits updated, no battery charged, and the model reads it in the
`goto` result -- *"the rover's LiDAR measured it at (28,0), 1 cell from the (29,0) the drive
planned. Your map now shows where it really is; plan from there."* Each move is a `lidar_fix`
event in the run record. A measured cell that is rock or off the map in the simulation is not
moved to, and the terminal says so. LOST is followed the same way, with nobody touching it;
UNSURE waits for you to put the rover where the screen shows and press SPACE, and the rover is
then told that cell. `python run_level4.py --no-correct` checks without moving the simulation.

**The arena.** Everything the simulation can drive over must be clear floor: at 0.2 m a cell the
30 x 30 map is 6 m across, home in the middle, and the simulation drives right along its edges.
Walls or boxes go at least ~1 m beyond that -- boxes as landmarks in that margin, not placed
symmetrically. A box inside the 6 m is driven into; a wall at its edge is driven through, and
from outside the reference nothing matches (UNSURE). Smaller room: smaller `CELL_M`.

## Changing the real-life values

On the Pi, server stopped:

```bash
python3 settings.py                  # every value, what it means, default or calib.json
python3 settings.py CELL_M 0.15      # set one; then restart the server
python3 settings.py --reset CELL_M   # back to the default
```

One simulation cell is `CELL_M` metres; the landing cell is the home spot; north on screen is
the way the rover faces there. Timings are measured, not typed: `calibrate.py forward` and
`calibrate.py turn`, again after any change of `CELL_M`, tyres or battery. The simulation's own
values -- arena, sols, model -- are its options (`python run_level3.py --sols 2 --arena 30`) or
its settings screen (O), saved in `prototype12/user_settings.json`.

## On the Pi, setting up (server stopped: `pkill -f server.py`)

```bash
cd ~/p16
python3 test_grid.py && python3 test_lidar.py && python3 test_locate.py   # no hardware
python3 lidar_check.py             # LiDAR health: ~10 Hz, ~500 points/turn, 0 CRC failures
python3 lidar_check.py --watch     # which way is forward: a hand in front reads ~0 deg
python3 lidar_check.py --mount     # sets direction + offset; needed once before Level 4
python3 test_drive_check.py        # the checked drive loop on a pretend rover
python3 calibrate.py forward 3 --reps 3      # on the floor: seconds per cell
python3 calibrate.py turn 1.5 --reps 4       # on the floor: seconds per quarter turn
python3 teleop.py                  # Level 1 over SSH, keyboard
python3 run.py "F R L F F"         # Level 1, a list; you type the real cell after each
```

Measured values go to `pi/calib.json`, the room to `pi/reference.npz`; neither is committed.

To put new code on the Pi: copy `pi/` to `~/p16` (`scp -r pi/* nithin@rpi5.local:~/p16/`) and
restart the server.

## Files

```
pi/
  server.py      the link: commands, manual driving, LiDAR scans, locate, checked drives
  config.py      pins, duty band, cell size, timings, LiDAR settings; calib.json overrides
  grid.py        grid poses, commands, the Manhattan/Chebyshev check
  motors.py      left/right power to the SmartElex PWM; FakeMotors for laptops
  moves.py       one primitive (F B L R), timed; runs of F merge into one pulse
  ld19.py        the LD19: packets, CRC, full turns, rover-frame angles
  locate.py      fits a scan to the room's reference: pose and OK / POOR / AMBIGUOUS
  reference.py   records, extends, saves the room's reference
  lidar_check.py LiDAR health, and the guided mounting check (--mount)
  settings.py    see and change the real-life values (calib.json)
  room_fit.py    the nearest wall sets the game map's cell size (also key R in the map)
  test_room_fit.py
  fake_world.py  a pretend rover and room with a LiDAR, for testing without hardware
  keys.py, teleop.py, run.py, calibrate.py      Level 1 over SSH, and calibration
  test_grid.py, test_lidar.py, test_locate.py, test_drive_check.py
laptop/
  launch.py      what the run_ files share: find the rover, keep the window open on errors
  link.py        the laptop's end of the link
  pad.py         control pad window              (run_remote.py)
  scan_view.py   LiDAR map window: room view, mapping, room check, arrows drive (run_lidar_map.py)
  test_mapping.py maps a pretend room with the window's own worker; measures drift
  level2.py      words -> Ollama -> F B L R      (run_level2.py)
  level3.py      runs ../game, sends each leg    (run_level3.py; --check for run_level4.py)
  correct.py     Level 4: the simulation's rover moved to the LiDAR's cell, the model told
  test_level3.py the Level 3 hook against ../game's real planner
```

## What this changes in the simulation

Nothing on disk. When `run_level3.py` runs, three things about the simulation change *in memory,
for that run only*; the files in `game/` stay as copied:

- `--pause key` is forced on, so the simulation waits at its rover pause after every leg;
- `nav.publish`, where the simulation hands a leg to the robot, is wrapped: it still writes
  `runs/plan.txt`, and also sends the leg to the rover;
- `pygame.event.get` is wrapped: a SPACE from the keyboard is dropped while a leg is driving.

`run_level4.py` adds two more, from `laptop/correct.py`:

- after each rover pause the simulation's rover may be moved to the LiDAR's cell: `world.pos`
  set, then `world._arrive()` -- what the simulation's own `World.move` does, without `spend()`;
- `nav.goto` is wrapped so its result names that cell and says, in one sentence, why.

Run the simulation directly (`python game/main.py` from `prototype12/`) and none of this applies.
