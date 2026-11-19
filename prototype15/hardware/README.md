# hardware/ — the rover side of prototype 14

```
hardware/
  LINK.md             every message between the laptop and the rover
  ESP32.md            how a leg reaches the wheels, in plain words, for the ESP32 build
  rover_address.txt   how the laptop finds the Pi (rpi5.local)
  laptop/
    level1_pad.py     Level 1: drive it by hand, keys or a gamepad          double-click
    level2_words.py   Level 2: plain words, the language model drives       double-click
    level3_game.py    Level 3: the simulation in ../game drives, no LiDAR   double-click
    link.py           the laptop's end of the link
    launch.py         finds the rover, and keeps a window open on an error
  pi/                 what runs on the Raspberry Pi; copied to ~/p16 there
```

Every level uses the same rover server and the same link. Several can be open at once, such
as the pad beside the game, but only one drive runs at a time.

## Each session

1. Phone hotspot on; laptop and Pi on it; motor battery on.
2. Start the rover server on the Pi, and leave it running:
   ```bash
   ssh nithin@rpi5.local
   ~/rover stop                       # only if PI_5's ROS stack was started
   cd ~/p16 && python3 server.py      # prints "rover listening on port 5005"
   ```
3. On the laptop, double-click one of the three level files in `laptop/`, or run it, e.g.
   `python laptop/level1_pad.py`. It finds the Pi by the name in `rover_address.txt`.

Running Level 3:
- It takes the simulation's options: `python laptop/level3_game.py --sols 2`.
- It opens on the 30, which is 3 m across; `--arena 50` is 5 m.
- Type `/next` in its chat to start each phase.
- While a leg drives, the screen reads "the rover says when it has stopped". Level 3 presses
  SPACE when the rover reports the leg done, and a SPACE of yours is ignored.

No Pi? In one terminal run `python pi/server.py --fake --fast`, which prints the motors
instead of driving them. Then run any level with `--rover 127.0.0.1`.

## Taking over

Keep `level1_pad.py` open beside the game:
- SPACE on the pad, or A on a gamepad, stops the rover at once, and the leg it was driving
  ends there. Quitting the pad does the same.
- The pad then drives the rover by hand.
- The game's screen and Level 3's window say where that leg ends, counted from home, and
  which way to face: *"put it 3 cells (30 cm) east and 2 cells (20 cm) north of home,
  facing E"*.
- Put the rover there and press SPACE in the game. The rover is then told where it stands.

A failed link is handled the same way.

Only the window that is driving stops the motors when it closes.

## How Level 3 reaches the game

`level3_game.py` sets four hooks in `game/nav.py`. They are None when the game runs alone.

- `nav.leg_started(world, dirs)`: a driven leg is in the route file, so it is sent to the
  rover.
- `nav.wait_for_rover`: `main.py` sets it to its SPACE pause.
- `nav.rover_driving()`: True while the rover is still driving. `main.space_ends_pause`
  ignores a keyboard SPACE while it is, so the pause ends when the rover says so.
- `nav.leg_finished(world)`: the game has stopped waiting. If a person put the rover right
  after a stop, the rover is told where it now stands.

`level3_game.py` also sets `dashboard.ROVER_HINT`, the pause's hint on the screen. It forces
`--pause key`, and uses `--arena 30` unless you give an arena.

## Changing the real-life values

On the Pi, with the server stopped:

```bash
python3 settings.py                  # every value, what it means, default or calib.json
python3 settings.py CELL_M 0.15      # set one; then restart the server
python3 settings.py --reset CELL_M   # back to the default
```

How the simulation and the floor line up:
- One simulation cell is `CELL_M` metres of floor, 0.10 by default.
- The landing cell is the home spot.
- North on screen is the way the rover faces there.

A `calib.json` left on the Pi from earlier runs overrides the defaults, and `settings.py`
shows which. The timings are measured rather than typed: run `calibrate.py forward` and
`calibrate.py turn` again after any change of tyres or battery.

The simulation's own values (arena, sols, model) are its options, e.g.
`python laptop/level3_game.py --sols 2 --arena 50`, or its settings screen (O). Under Level 3
the arena is a flag only: without one, Level 3 uses the 30.

## On the Pi, setting up (server stopped: `pkill -f server.py`)

```bash
cd ~/p16
python3 calibrate.py forward 3 --reps 3      # on the floor: seconds per cell
python3 calibrate.py turn 1.5 --reps 4       # on the floor: seconds per quarter turn
```

Measured values go to `pi/calib.json`, which is not committed.

To put new code on the Pi, copy `pi/` to `~/p16` (`scp -r pi/* nithin@rpi5.local:~/p16/`)
and restart the server. The Pi's code is tested on the laptop, by `tests/test_grid.py` and
`tests/test_link.py`.

## Files on the Pi

```
pi/
  server.py      the rover's end of the link: drives, manual driving, stops (LINK.md)
  config.py      pins, duty band, cell size, timings; calib.json overrides
  grid.py        poses and commands: what a command does, and where the rover ends up
  motors.py      left/right power to the SmartElex PWM; FakeMotors prints instead
  moves.py       one move (F B L R), timed; runs of F merge into one pulse
  settings.py    see and change the real-life values (calib.json)
  calibrate.py   measure a cell and a quarter turn on the floor
```
