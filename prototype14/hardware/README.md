# hardware/ — the rover side of prototype 13

```
hardware/
  run_remote.py       Level 1 -- drive it by hand, keys or a gamepad        double-click
  run_level2.py       Level 2 -- plain words, the language model drives     double-click
  run_level3.py       Level 3 -- the simulation in ../game drives, no LiDAR double-click
  rover_address.txt   how the run_ files find the Pi (rpi5.local)
  laptop/             the code behind the run_ files
  pi/                 what runs on the Raspberry Pi -- copied to ~/p16 there
```

Every mode uses the same rover server and the same link. Several run_ files can be open at
once -- the pad beside the game, say; one drive at a time still.

## Each session

1. Phone hotspot on; laptop and Pi on it; motor battery on.
2. Start the rover server on the Pi, and leave it running:
   ```bash
   ssh nithin@rpi5.local
   ~/rover stop                       # only if PI_5's ROS stack was started
   cd ~/p16 && python3 server.py      # prints "rover listening on port 5005"
   ```
3. On the laptop, double-click one `run_` file, or run it: `python run_remote.py`.

`run_level3.py` takes the simulation's options: `python run_level3.py --sols 2`. It opens on the
30, which is 3 m across; `--arena 50` is 5 m. Type `/next` in its chat to start each phase. While
a leg drives, the screen reads "the rover says when it has stopped": the launcher presses SPACE
when the rover reports the leg done, and a SPACE of yours is ignored.

No Pi? In one terminal `python pi/server.py --fake --fast` -- motors only, printed -- then any
run_ file with `--rover 127.0.0.1`.

## Taking over

Keep `run_remote.py` open beside the game. SPACE on the pad (A on a gamepad) stops the rover at
once, and the leg it was driving ends there; so does quitting the pad. The pad then drives it by
hand. The screen, and the window `run_level3.py` runs in, say where the leg ends, counted from
home, and which way to face: *"put it 3 cells (30 cm) east and 2 cells (20 cm) north of home,
facing E"*. Put it there and press SPACE in the game, and the rover is told it is there. A failed link is handled the same way.

Several windows can be connected at once; only the one driving stops the motors when it closes.

## Changing the real-life values

On the Pi, server stopped:

```bash
python3 settings.py                  # every value, what it means, default or calib.json
python3 settings.py CELL_M 0.15      # set one; then restart the server
python3 settings.py --reset CELL_M   # back to the default
```

One simulation cell is `CELL_M` metres, 0.10 by default; the landing cell is the home spot;
north on screen is the way the rover faces there. A `calib.json` left on the Pi from earlier
runs overrides the defaults, and `settings.py` shows which. Timings are measured, not typed:
`calibrate.py forward` and `calibrate.py turn`, again after any change of tyres or battery. The
simulation's own values -- arena, sols, model -- are its options
(`python run_level3.py --sols 2 --arena 50`) or its settings screen (O), saved in
`prototype13/user_settings.json`. Here the arena is a flag only: without one the launcher
picks the 30.

## On the Pi, setting up (server stopped: `pkill -f server.py`)

```bash
cd ~/p16
python3 test_grid.py                         # no hardware
python3 calibrate.py forward 3 --reps 3      # on the floor: seconds per cell
python3 calibrate.py turn 1.5 --reps 4       # on the floor: seconds per quarter turn
python3 teleop.py                  # Level 1 over SSH, keyboard
python3 run.py "F R L F F"         # Level 1, a list; you type the real cell after each
```

Measured values go to `pi/calib.json`, which is not committed.

To put new code on the Pi: copy `pi/` to `~/p16` (`scp -r pi/* nithin@rpi5.local:~/p16/`) and
restart the server.

## Files

```
pi/
  server.py      the link: commands, manual driving, drives
  config.py      pins, duty band, cell size, timings; calib.json overrides
  grid.py        grid poses, commands, the Manhattan/Chebyshev check
  motors.py      left/right power to the SmartElex PWM; FakeMotors for laptops
  moves.py       one primitive (F B L R), timed; runs of F merge into one pulse
  settings.py    see and change the real-life values (calib.json)
  keys.py, teleop.py, run.py, calibrate.py      Level 1 over SSH, and calibration
  test_grid.py
laptop/
  launch.py      what the run_ files share: find the rover, keep the window open on errors
  link.py        the laptop's end of the link
  pad.py         control pad window              (run_remote.py)
  level2.py      words -> Ollama -> F B L R      (run_level2.py)
  level3.py      runs ../game, sends each leg    (run_level3.py)
  test_level3.py the Level 3 hook against ../game's real planner
```

## What this changes in the simulation

Nothing on disk. When `run_level3.py` runs, these change *in memory, for that run only*:

- `--pause key` is forced on, so the simulation waits at its rover pause after every leg, and
  `--arena 30` unless you give an arena;
- `nav.publish`, where the simulation hands a leg to the robot, is wrapped: it still writes
  `runs/plan.txt`, and also sends the leg to the rover;
- `pygame.event.get` is wrapped: a SPACE from the keyboard is dropped while a leg is driving;
- `dashboard.ROVER_HINT`, the pause's hint on the screen, says the rover reports by itself,
  or, after a stop, where to put it.

Run the simulation directly (`python game/main.py` from `prototype13/`) and none of this applies.
