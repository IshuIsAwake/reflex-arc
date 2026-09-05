# Ventral Root — running prototype 10 on the real rover

**Ventral Root** is the path a decision takes from the planner to the motors:
`runs/plan.txt`, [`game/rover_link.py`](game/rover_link.py), the bridge on the Pi, and
the wheels. It is named for the motor root of a spinal nerve, which carries commands out
of the cord to muscle and carries nothing back — the deciding happens elsewhere, in the
ventral horn, and the root only delivers. Cut it and you get paralysis with sensation
intact, which is exactly what killing `rover_link.py` does: the simulation still sees,
still plans, still knows where everything is, and the rover cannot act on any of it.

Three processes, one file between them. The game plans and drives a leg in simulation,
writes the headings it *actually* drove to `runs/plan.txt`, and stops. `rover_link.py`
sees the file change and drives the same leg on the floor. You press `SPACE`, the file
is wiped, the game plans the next leg, and round it goes.

The rover is therefore always one leg behind the simulation and never ahead of it. It
is never handed a move the sim has not already proved against the map, which is why the
plan is written *after* the drive rather than before — [`DESIGN.md`](DESIGN.md), "The
seam".

## Start these, in this order

**1. The bridge, on the Pi.** Double-click
[`../rover_bridge/start_server.bat`](../rover_bridge/start_server.bat), or run the SSH
one-liner in [`../rover_bridge/MANUAL.md`](../rover_bridge/MANUAL.md). Everything about
the Pi — starting, stopping, restarting after a deploy, testing one motor at a time —
lives in that manual and is not repeated here.

Check it before going further:

```sh
curl -s http://10.7.20.227:5000/status
```

`{"last_command":{"throttle":0.0,"turn":0.0}}` means up and idle. No answer means the
server is not running — **a reboot kills it**, and the Pi answering a ping proves
nothing about the server.

**2. The game.**

```sh
.venv\Scripts\python.exe game\main.py
```

**3. The watcher**, in its own terminal, from `prototype10/`:

```sh
.venv\Scripts\python.exe -u game\rover_link.py --heading N
```

`--heading` is which way the rover is **physically pointing right now**. Get it wrong
and every turn is wrong by that much for the whole session. `-u` matters: without it
Python buffers and the terminal tells you nothing while the rover moves.

Add `--dry-run` to watch the whole loop print its pulses without sending anything. Do
that first in a new room.

**The game and the watcher can start in either order.** Whatever is in `plan.txt` when
the watcher opens has already been driven — the game writes a leg and then waits, so a
file with content in it is the *last* leg, not the next one. The watcher remembers it
before it starts watching and says which leg it is ignoring. Only the bridge has to be
up first, and only by the time something actually drives.

## Then just play

Drive the game as normal. Every `goto` writes a leg, the rover drives it, you press
`SPACE` when it has stopped, and the game continues. Nothing else to press.

```
[10:39:15] leg: E S S S S E E E E E
           14 pulse(s), E -> E
      1/14  FORWARD
      2/14  LEFT
      3/14  LEFT
      4/14  LEFT
      ...
           done. facing E. waiting for the next leg.
```

The first line is what the game asked for; the second is what it costs on hardware and
where the nose ends up. `waiting for the next leg` means the rover has stopped and
`SPACE` is safe to press.

## Why a right turn costs three pulses

One motor's DIR line is faulted and spins forward whatever it is told
(`../rover_bridge/MANUAL.md`). `Rover.drive` mixes `left = throttle + turn`, so
`turn = -1` asks *that* motor to reverse — and a stuck-forward motor answers by driving
both wheels forward. It is a pivot on the wire and a straight line on the floor, which
is exactly what it was seen doing. Only `turn = +1` pivots, because that asks the
healthy motor to reverse.

So the rover goes **forward and anticlockwise, and nothing else.** `turn = -1` is never
sent. Turning east from north is three left pivots rather than one right, and in the log
above every `E -> S` costs three `LEFT`s while `S -> E` costs one.

That asymmetry is free in the game and expensive in the room: the sol is charged one
step per tile driven, so a turn-heavy route costs the same as a straight one in the sim
and three times as much on the floor. [`DESIGN.md`](DESIGN.md) flags it under "Open".

## The two numbers nobody has measured

At the top of [`game/rover_link.py`](game/rover_link.py):

```python
FORWARD_SECONDS = 1.0      # one grid cell
TURN_SECONDS = 1.0         # 90 degrees anticlockwise
```

Both are placeholders. Calibrate them with the browser page at
`http://10.7.20.227:5000/` — *Pulse forward*, measure how far it went, and set
`FORWARD_SECONDS` to whatever covers one grid cell; *Pulse left*, and adjust
`TURN_SECONDS` until one pulse lands on a quarter turn. The page's two duration boxes
let you try values before committing them to the file.

Every leg is driven out of these two numbers, so error in them compounds across a sol.

## Stopping, and starting again

`Ctrl+C` in the watcher's terminal. It sends a stop on the way out. If it cannot reach
the bridge to do so, the Pi's own watchdog halts the motors 0.5s after commands stop
arriving — killing the process is itself a hard stop.

**A heading is only true while the watcher is alive.** It counts turns; nothing measures
the rover. So after any interruption — `Ctrl+C`, a lost bridge, a wheel that slipped —
look at the rover, then restart with `--heading` set to what you actually see. The
watcher quits rather than continuing when a leg fails part-way through, for that reason.

## When it does not move

| symptom | cause |
|---|---|
| `bridge unreachable`, but ping works | `server.py` is not running. A reboot kills it. Restart per `MANUAL.md`. |
| watcher prints nothing at all | no `-u`, so output is buffered. Restart with it. |
| `REFUSED: ... is not one of N/E/S/W` | something other than a heading is in the file. Nothing is sent until it changes. |
| a leg drives twice | it will not — identical bytes are never re-driven. If it happens, the file genuinely changed. |
| rover drives straight when it should pivot | `turn = -1` reached the motors from somewhere. Nothing in this repo sends it; check what else is talking to the bridge. |

## What is not built

The rover does not report back. `SPACE` is you standing in for it —
`nav._await_rover`'s docstring says so, and it is the only function that has to change
when the bridge reports for itself. Until then, **press `SPACE` only once the watcher
says `waiting for the next leg`**; pressing early lets the simulation run ahead of a
rover that is still moving, and the two stop describing the same machine.
