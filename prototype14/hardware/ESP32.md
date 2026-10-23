# How a leg reaches the wheels, for the ESP32 build

*For Abhishek and Koushik.*

The laptop never knows a Pi is on the other end. It sends a leg, hears one step message per
command and one done message at the end, and that is all it needs. So the ESP32 has to do
what [`pi/server.py`](pi/server.py) and the small files beside it do now. The game, the model,
the retries and the take-over all stay on the laptop. Every message is written out exactly in
[`LINK.md`](LINK.md).

## One leg, start to finish

1. **The game drives it first.** The model calls `goto`, and the game moves the rover through
   the simulation cell by cell, revealing ground as it goes. There is no LiDAR yet, so the
   simulation is the truth, and the real rover replays what the game already drove.
2. **The leg becomes letters.** One compass letter per cell, such as `E E E N`. The game hands
   it to Level 3 through a hook in `game/nav.py`, then waits at a pause that reads "the rover
   says when it has stopped".
3. **The laptop sends it.** `laptop/level3_game.py` sends it as one line, over the phone
   hotspot's wifi, to port 5005 on the Pi:
   `{"op": "drive", "id": 7, "cmds": ["E", "E", "E", "N"]}`.
4. **The Pi turns letters into moves.** Each letter means: turn to face that way, the short way
   round, then go one cell forward. Forward moves in a row merge into one pulse. From facing
   north, `E E E N` is a right turn, a three-cell pulse, a left turn and a one-cell pulse.
5. **Every move is timed.** Power on for `FORWARD_S_PER_CELL` per cell, or `TURN_S_PER_90` per
   quarter turn, then power off. Then the rover waits `SETTLE_S` (0.6 s by default), so its
   coasting doesn't run into the next move. Nothing measures where it went: its position is
   its own count of what it was told to do.
6. **It reports back.** After each letter it sends a step message with the cell it believes
   it has reached. After the last letter it sends one done message, `DONE`.
7. **The game carries on.** Level 3 presses SPACE for the game, and the model gets its next
   turn.

## When something goes wrong

- **A person stops it.** SPACE on the pad (`level1_pad.py`), or `/stop` in Level 2, ends the
  drive at once from any window, and the done message says `STOPPED`. The laptop doesn't send
  the rest, since a person has taken over. The game's screen says where the leg ends, such as
  *"put it 3 cells (30 cm) east and 2 cells (20 cm) north of home, facing E"*. The person
  drives or carries the rover there and presses SPACE in the game. The laptop then tells the
  rover where it now stands (`set_pose`).
- **The wifi drops.** The rover stops its motors when the window that was driving goes away.
  The laptop reconnects and resends every letter it hadn't heard a step for, up to five
  times. The letter that was moving is driven again in full, because the rover can't say how
  far it got.
- **The pad goes quiet.** Hand driving sends a message every 50 ms while a key is held, and
  the rover stops itself 0.4 s after the last one.
- **A second drive arrives mid-drive:** `BUSY`, and nothing moves. **A letter it doesn't
  know:** `REFUSED`, and nothing moves.

## What runs on the Pi

| file | what it does |
|---|---|
| `server.py` | listens on port 5005, one connection per laptop window, and answers each message. A drive runs on its own thread, so a stop can still get in |
| `grid.py` | letters into moves, and where the rover should be after each |
| `moves.py` | one timed move |
| `motors.py` | left and right power to the SmartElex 15D: a PWM pin and a direction pin per side, at 490 Hz. Power from 0 to 1 is spread over a narrow duty band, 8.2% to 15.4% |
| `config.py`, `calibrate.py`, `settings.py` | the pins and the timings. `calibrate.py` measures the timings on the floor, and they are kept in `calib.json` |

`python pi/server.py --fake --fast` runs the same server on a laptop, printing the motors
instead of driving them. What it answers is what the laptop expects.

## Worth noticing

- The ESP32 has wifi too. One that listens on port 5005 and answers the same lines needs
  nothing changed on the laptop except the address in `rover_address.txt`, which also takes
  an IP.
- Taking over means the pad is open beside the game, so the Pi holds two connections at once.
  A Bluetooth serial link is one connection.
- On the Pi, a stop is heard mid-pulse because the drive has its own thread. A loop that
  waits out each pulse hears nothing until the pulse ends.
- With Bluetooth, the only laptop code that touches the connection is `link.py`'s `connect`,
  `send` and `receive`, and `launch.py`'s address lookup. Everything above them sees lines of
  JSON.
- The timings belong to one rover on one floor. The ESP32's rover needs its own, and
  `calibrate.py` is Python that runs on the Pi.
- A kept run replays the same legs every time, against the fake server or a real rover:
  `python laptop/level3_game.py --rover <address> --replay runs/<stamp>`.

## Not decided

- Whether the link stays on wifi or moves to Bluetooth.
