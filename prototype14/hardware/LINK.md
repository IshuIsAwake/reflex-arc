# The link: how the laptop talks to the rover

One TCP connection per laptop window, to port 5005 on the rover. Each message is one JSON
object on one line, ending in `\n`, both ways. The rover's side is
[`pi/server.py`](pi/server.py). The laptop's side is [`laptop/link.py`](laptop/link.py). An
ESP32 that answers these messages the same way can replace the Pi.

Several windows can be connected at once, such as the pad and the game. Each one has its own
connection. Only one drive runs at a time.

## Poses and commands

A pose is `{"x": 3, "y": -2, "heading": "E"}`:

- Cells are counted from the home spot, where the rover stood when it was reset.
- `y` grows to the south, as on the game's map.
- `heading` is one of `N`, `E`, `S`, `W`.

The pose is dead-reckoned. It is what the timings claim, and nothing measures it.

A drive's commands are a list of these:

| command | what it does |
|---|---|
| `F`, `B` | one cell forward or back |
| `L`, `R` | a quarter turn left or right, in place |
| `N`, `E`, `S`, `W` | turn to face that way, the short way round, then one cell forward |

The game sends `N E S W`. Level 2 sends `F B L R`.

## Laptop to rover

| message | answer |
|---|---|
| `{"op": "hello"}` | `{"ok": true, "pose": {...}, "fake": false, "forward_s": 1.0, "turn_s": 2.0, "cell_m": 0.1}` |
| `{"op": "reset", "heading": "N"}` | `{"ok": true, "pose": {...}}`. The rover is now on (0,0), facing `heading` |
| `{"op": "set_pose", "x": 3, "y": -2, "heading": "E"}` | `{"ok": true, "pose": {...}}`. Sent after a person has put the rover on that cell |
| `{"op": "drive", "id": 7, "cmds": ["N", "N", "E"]}` | step messages, then one done message (below) |
| `{"op": "manual", "left": 0.5, "right": -0.5}` | no answer. Wheel power from the pad, -1 to 1 each side |
| `{"op": "stop"}` | `{"ok": true, "note": "stopped"}` |

`forward_s`, `turn_s` and `cell_m` in the hello answer are the rover's timings and cell size,
for information. Level 3 uses `cell_m` to tell a person how far to move the rover.

An unknown `op` is answered `{"ok": false, "note": "unknown op ..."}`. A line that isn't JSON
is answered `{"ok": false, "note": "not JSON"}`, and a message with a missing or wrong field,
such as a heading that isn't `N E S W`, `{"ok": false, "note": "bad message: ..."}`. The
connection stays open after any of them.

## Rover to laptop, during a drive

After each command, a step message:

```
{"event": "step", "id": 7, "i": 1, "cmd": "N", "pose": {...}}
```

`i` counts the commands done, from 1. Then, always last, one done message:

```
{"event": "done", "id": 7, "result": "DONE", "pose": {...}}
```

`result` is one of these:

| result | when |
|---|---|
| `DONE` | every command was driven |
| `STOPPED` | a stop came in. The pose is a guess, since the rover stopped mid-move |
| `BUSY` | another drive was already running, so nothing moved |
| `REFUSED` | a command wasn't one of the eight. It carries a `"note"`, and nothing moved |

The rover drives runs of `F` (or `B`) as one pulse, even across commands. So `E E E E`
from facing north is one turn and one four-cell pulse. Each turn settles before the next
move.

## Safety

- **Stop.** A stop from any window ends the drive in progress, and the done message says
  `STOPPED`. The laptop doesn't send the rest again: a person has taken over.
- **Manual.** Manual power stops by itself 0.4 s after the last manual message. The pad
  sends one every 50 ms while a key or the stick is held.
- **Disconnect.** When the window that is driving disconnects, mid-drive or by hand, the
  motors stop. A window that isn't driving can come and go without stopping anything.
- **Retry.** The laptop resends after a dropped connection, up to five times. It waits 2,
  4 and 6 s before the first three resends and 8 s before each after that. Each resend
  carries the commands it has not yet seen a step message for, under a new `id`. The
  command that was moving when the link dropped is therefore driven again in full.

## Not decided

- Whether the link stays plain TCP. Krish's gRPC proposal (`krish/link-bot`) is the
  alternative, and the team hasn't agreed.
