# Game Plan — Real Rover Integration

**Goal:** get the physical rover behaving as close to the Unity policy as possible.

## Phase 1 — Prove the link works (now)
- [ ] Wire motors to driver board, set real pin numbers in `motor_control.py`
- [ ] `python3 motor_control.py` on the Pi — confirm forward/turn/stop, fix any reversed wheel
- [ ] `python3 server.py` + drive from the browser webapp (`http://<pi-ip>:5000`)
- [ ] Drive from Unity via `RoverBridgeClient.cs` (manual/keyboard mode) — real rover responds to Unity input

## Phase 2 — Calibrate real vs. sim motion
- [ ] Measure real wheel speed at a few fixed throttle values (stopwatch + distance, or encoder if available)
- [ ] Fit throttle → real speed curve; adjust `motor_control.py` so a given throttle produces roughly sim-equivalent motion
- [ ] Sanity check: same action sequence in sim vs. real ends up covering roughly the same ground

## Phase 3 — Mirror the trained policy
- [ ] In `RoverAgent.cs`, call `roverBridgeClient.SendDrive(throttle, turn)` from `OnActionReceived`
- [ ] Turn off manual control — real rover now mirrors the ONNX policy live
- [ ] Run side-by-side, note where real behavior diverges from sim (obstacle avoidance, drift, stopping distance)

## Phase 4 — Close remaining gaps (later, not blocking)
- [ ] Nithin's ramp-grade cost curve → feed back into Unity's physics randomization ranges — **sync with him first, don't duplicate**
- [ ] Position feedback into Unity (ArUco/overhead camera — Harshvardhan/Ishan's piece)
- [ ] Wrap into this repo's `goto`/`distance` Seam contract (`DONE`/`BLOCKED`/`UNREACHABLE`, step/battery cost)

**Right now:** Phase 1, step 1 — wire it up and tell me the pin numbers / driver board.
