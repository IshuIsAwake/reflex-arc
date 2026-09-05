# Rover Manual

## What this is

`rover_bridge` is a small Flask app that runs **on the rover's Raspberry Pi**
and drives its two motors (differential drive: throttle + turn). It exposes
a JSON API and a browser-based WASD control page, and it's the same API
Unity's `RoverAgent.cs` talks to for real-world driving.

Hardware: Pi 5 -> SmartElex 15D motor driver (independent PWM mode) -> two
DC drive motors. See `motor_control.py`'s docstring for wiring/pin details.

## Known hardware fault (2026-09-05): left motor won't reverse

Confirmed via isolated single-motor `/drive` calls against the real running
server (e.g. `{"throttle":0.5,"turn":0.5}` = left-only forward,
`{"throttle":-0.5,"turn":-0.5}` = left-only reverse -- both spun the wheel
the same direction): the **left** motor does not reverse, regardless of
commanded sign. Right motor was confirmed to spin correctly in isolation.

(An earlier version of this note wrongly blamed the right motor -- that was
based on flakier raw `gpiozero` test scripts hitting pin-claim/release
issues, not real hardware behavior. Isolated tests through the actual
`server.py`/`Rover`/`Motor` code path, one motor at a time, are the
trustworthy method -- see "Testing a single motor" below.)

This is a **hardware fault, not a software bug** -- the mixing/direction
logic in `motor_control.py` is symmetric and correct for both motors.
`INVERT_LEFT` cannot fix it: that flag only relabels which value (0 or 1)
gets sent on the DIR pin, it doesn't change what the driver board actually
does with a stuck line.

**To fix**: physically inspect the left motor's DIR1 wire -- BCM 23 (Pi) to
the SmartElex board's DIR1 input for that channel. Right channel (BCM 24,
same board, same code path) works, so the fault is specific to that one
wire/connection/input, not the Pi or the shared code.

## Testing a single motor

With the server already running (real code path, no GPIO conflicts), drive
just one wheel via `/drive` by picking throttle/turn so the other wheel's
mixed speed is 0:

| Intent | throttle | turn | left | right |
|---|---|---|---|---|
| Left forward only | 0.5 | 0.5 | 1 | 0 |
| Left reverse only | -0.5 | -0.5 | -1 | 0 |
| Right forward only | 0.5 | -0.5 | 0 | 1 |
| Right reverse only | -0.5 | 0.5 | 0 | -1 |

```bash
curl -s -X POST http://10.7.20.227:5000/drive -H "Content-Type: application/json" -d '{"throttle":0.5,"turn":0.5}'
sleep 1.5
curl -s -X POST http://10.7.20.227:5000/stop
```
Prefer this over standalone `gpiozero` scripts (like `test_wheels.py`) --
those construct fresh pin objects outside the running server and have shown
`GPIO busy` / inconsistent-direction flakiness in practice.

## Software stack

| Piece | File | Runs where | Purpose |
|---|---|---|---|
| Motor driver | `motor_control.py` | Pi | Low-level GPIO/PWM control of the two motors via `gpiozero`. Defines the `Rover` class: `drive(throttle, turn)`, `stop()`, watchdog auto-stop. |
| Web server | `server.py` | Pi | Flask app wrapping `Rover`. Serves the control page and a JSON API. |
| Control page | `templates/index.html` | Browser (any device on the same network) | WASD keyboard UI — holds keys, streams drive commands. |
| Wheel diagnostic | `test_wheels.py` | Pi | Standalone script to test each wheel individually (wiring/direction sanity check). |

**API** (also used by Unity/curl, not just the web page):
- `POST /drive` — body `{"throttle": -1..1, "turn": -1..1}`
- `POST /stop` — stop both motors immediately
- `GET /status` — last command sent

**Safety watchdog**: if no `/drive` call arrives for 0.5s (`WATCHDOG_TIMEOUT_S`
in `motor_control.py`), the motors auto-stop. The web page re-sends the
current command every 200ms while a key is held, well inside that window.

## Connecting

```
ssh nithin@10.7.20.227
```
Passwordless (ed25519 key already on this machine). Rover's Pi must be on
the same network.

## Starting the server

Easiest: double-click `start_server.bat` in this folder (Windows). It checks
whether the server's already running, starts it if not, and prints status.

Manually:
```bash
ssh nithin@10.7.20.227 "cd ~/rover_bridge && nohup python3 server.py > ~/rover_bridge/server.log 2>&1 </dev/null &"
```

Then open, from any device on the same network:
```
http://10.7.20.227:5000/
```
Click the page to focus it, then hold **W/S** for throttle, **A/D** to turn,
**Space** to stop. Speed is capped at `SPEED` in `index.html` (currently
`1.0` = full).

> The SSH command above sometimes reports "command timed out" / a nonzero
> exit even though the server started fine — that's the SSH session hanging
> on the backgrounded process, not a real failure. Always verify with the
> check command below rather than trusting the exit code.

## Checking it's running

```bash
ssh nithin@10.7.20.227 "pgrep -af server.py; echo ---; tail -n 10 ~/rover_bridge/server.log"
```
A `python3 server.py` PID plus `Running on http://10.7.20.227:5000` in the
log means it's up.

Quick remote status check without SSH:
```bash
curl -s http://10.7.20.227:5000/status
```

## Stopping the server

```bash
ssh nithin@10.7.20.227 "pkill -f 'python3 server.py'"
```
This also cleans up GPIO via `Rover.cleanup()` (registered in `server.py`'s
`finally` block), so motors are left in a safe stopped state.

## Restarting (after deploying a code change)

Flask caches `index.html`/routes in memory when `debug=False` (it is here),
so editing files on the Pi or re-`scp`ing them has **no effect** until the
process restarts:
```bash
ssh nithin@10.7.20.227 "pkill -f 'python3 server.py'"
# then run the start command again
```

## Deploying a change

Per project convention: **never edit files directly on the Pi.** Edit
locally in this repo, then push the finished file:
```bash
scp rover_bridge/motor_control.py nithin@10.7.20.227:~/rover_bridge/motor_control.py
scp rover_bridge/server.py        nithin@10.7.20.227:~/rover_bridge/server.py
scp rover_bridge/templates/index.html nithin@10.7.20.227:~/rover_bridge/templates/index.html
```
Then restart the server (previous section) — required for both Python
changes (new process needed) and template changes (cached otherwise).

## Tuning drive feel

All in `motor_control.py`:
- `MIN_DUTY` / `MAX_DUTY` — usable PWM duty band (stall floor / max-speed
  ceiling). Re-measure if tyres, load, or battery change.
- `INVERT_LEFT` / `INVERT_RIGHT` — flip a motor in software if it spins
  backwards.
- `WATCHDOG_TIMEOUT_S` — auto-stop window if commands stop arriving.

Web UI top speed: `SPEED` constant in `templates/index.html`.
