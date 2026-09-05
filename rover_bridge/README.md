# Rover Bridge — the real rover's motors, over HTTP

Minimal HTTP bridge so anything on the network can drive the physical rover's wheel
motors with a `(throttle, turn)` pair. Three clients speak to it today: the browser page
it serves itself, [`prototype8/game/rover_link.py`](../prototype8/game/rover_link.py)
replaying an LLM-planned route, and Unity's `RoverAgent.cs` over in the IngenuitySim
repo, which outputs that same action shape in sim.

```
rover_link.py / Browser / Unity  --HTTP JSON-->  server.py (Flask, on the Pi)  -->  motor_control.py  -->  wheel motors
```

The planner-driven path through here is called **Ventral Root** — `plan.txt`, the
watcher, this server, the wheels. See
[`../prototype10/RUNNING.md`](../prototype10/RUNNING.md).

## Files

- `motor_control.py` — talks to the actual GPIO pins / H-bridge driver. **Runs on the Pi only.**
- `server.py` — Flask server exposing `/drive`, `/stop`, `/status`. Runs on the Pi.
- `templates/index.html` — press-and-hold directional buttons, served by `server.py`, for testing from any phone/laptop browser on the same network — no Unity needed.
- `requirements.txt`
- `Assets/Scripts/RoverBridgeClient.cs` — Unity-side client. **In the IngenuitySim repo**
  (`AnakinSkywalker0/IngenuitySim`, locally `D:\IngenuitySim`), not this one: the Unity
  project did not come across with the bridge.

## Step 1 — Driver board (done)

The rover's actual driver is a **SmartElex 15D** board in PWM independent mode, not a generic H-bridge. `motor_control.py` is a non-ROS strip-down of the tested/calibrated ROS2 node pulled from Nithin's rover_ros2 Pi (see `rover_drive_logic/` at the repo root for the original + writeup) — same pins, same gpiozero library, same measured duty calibration:

```python
LEFT_MOTOR  = {"pwm": 12, "dir": 23}
RIGHT_MOTOR = {"pwm": 13, "dir": 24}
MIN_DUTY = 0.082   # measured: duty at which the drivetrain starts moving
MAX_DUTY = 0.154   # measured: ceiling that keeps it controllable
```

If a wheel spins the wrong way, flip `INVERT_LEFT`/`INVERT_RIGHT` in `motor_control.py` rather than re-wiring. If the calibration ever needs re-measuring (tyres/load/battery changed), see `rover_drive_logic/README.md`.

## Step 2 — Test motors directly, no server yet

On the Pi (this OS is externally-managed, so apt rather than `pip install -r requirements.txt`):

```bash
sudo apt install -y python3-flask python3-gpiozero python3-lgpio
python3 motor_control.py
```

This drives forward for 1s, turns for 1s, then stops. Confirms wiring and direction before adding the network layer on top. If a wheel spins the wrong way, flip its `INVERT_LEFT`/`INVERT_RIGHT` flag in `motor_control.py` rather than re-wiring.

## Step 3 — Run the bridge server, test from a browser

```bash
python3 server.py
```

Find the Pi's IP (`hostname -I`), then from any device on the same Wi-Fi/network open:

```
http://<pi-ip>:5000/
```

Press-and-hold the directional buttons. This exercises the exact same `/drive` endpoint Unity will use, so if this works, Unity will too — it's purely a networking question from there.

Note the built-in safety watchdog: if no `/drive` command arrives for 0.5s, the motors auto-stop. That's why the webapp buttons re-send every 200ms while held rather than sending once.

## Step 4 — Connect from Unity

1. Put both the Pi and the machine running Unity on the same network.
2. Add the `RoverBridgeClient` component (already in the IngenuitySim repo at `Assets/Scripts/RoverBridgeClient.cs`) to any GameObject — the Rover itself is fine.
3. Set `Rover IP` to the Pi's IP address in the Inspector.
4. Press Play with `Manual Control Enabled` checked — arrow keys / WASD now drive the *real* rover from Unity, independent of the trained policy. This is the "does the link work at all" test.
5. Once that's solid, wire it into the trained policy: in `RoverAgent.cs`'s `OnActionReceived`, alongside the sim movement code, call:
   ```csharp
   roverBridgeClient.SendDrive(throttleAction, turnAction);
   ```
   and turn off `Manual Control Enabled`. Now the real rover mirrors the Unity policy live — this is your actual sim-vs-real comparison.

## What this doesn't do yet

This is deliberately the minimal "prove the link and motors work" version — it does not do:

- Mapping real wheel speed (m/s) to Unity's sim motion scale — the `MIN_DUTY`/`MAX_DUTY` calibration in `motor_control.py` is Nithin's measured duty-vs-stall/ceiling curve for *this chassis*, not a throttle-to-sim-equivalent-speed fit. Phase 2 in `GAME_PLAN.md` still applies.
- Nithin's documented ramp-grade cost-curve measurement (see `reflex-arc-team-and-status` — that's his piece of the project; worth syncing before duplicating it)
- The `goto`/`distance` Seam contract reflex-arc expects (`DONE`/`BLOCKED`/`UNREACHABLE` results, step/battery cost) — this bridge is raw throttle/turn only, one level below that contract
- Position feedback from the rover back to Unity (no localization yet — that's the ArUco/overhead-camera piece owned by Harshvardhan/Ishan)

Good next step once basic movement is confirmed: log real wheel speed at a few fixed throttle values (stopwatch + measured distance) against sim's motion for the same action, and adjust the throttle→duty mapping if the magnitudes don't line up.
