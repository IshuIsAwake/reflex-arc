# Prototype 12 — the rover takes commands from the simulation

Koushik's integration lab, cut back to Levels 1–3 when it landed. The rover drives a list of grid
commands from a person, a model, or the whole simulation. Nothing in `prototype10*/` or `PI_5` is
changed; this folder borrows from them.

## The levels

| level | what drives | where the pose comes from | status |
|---|---|---|---|
| 1 | the keyboard, and a typed command list | a person typing the real cell | **built** |
| 2 | an LLM issuing simple commands (IoT level) | dead reckoning | **built**; the LLM run against a fake rover |
| 3 | the LLM through the whole simulation (`game/`'s `goto` → `plan.txt`) | the simulation | **built**; 14 legs on the real rover, wheels in the air |
| 4 | as 3, every move checked by the LiDAR | the LiDAR | **deferred** until after prototype 14 |

Level 3 is the rover replaying the simulation blind. Nothing measures where it really ends up.

## Cut on landing

- **The LiDAR and Level 4** were built but run end to end only on a pretend rover with a pretend
  LiDAR. They are on the branch `old_level4`, for Koushik and Abhishek, with Nithin, to start
  from after 14. That covered `ld19.py`, `locate.py`, `reference.py`, `room_fit.py`,
  `lidar_check.py`, `fake_world.py`, `correct.py`, the map window, `run_level4.py` and their
  tests.
- **A stop sticks.** A stop from the pad used to make the laptop resend the rest of the leg
  straight away. Now it ends the leg. Level 3 hands the rover to you. When you press SPACE, the
  rover is told it stands where the leg ends, facing its last move.
- **One cell is 10 cm**, Ishan's call: ten cells to the metre, so 10d's 30 x 30 map is 3 m
  across. The forward placeholder becomes 1 s a cell at the same 0.10 m/s.

## Levels 2 and 3: drive everything, measure nothing

The job is to complete every command with as little error as the open-loop rover allows. The
rover replays what it is sent and reports a dead-reckoned pose; at Level 3 the simulation is the
truth and the floor follows it.

- **The link** is TCP, one JSON object a line, standard library on both ends
  (`hardware/pi/server.py`, `hardware/laptop/link.py`). Motors stop if the laptop disconnects. A
  drive is retried under the same id after a drop and the rover answers a finished id from
  memory, so the whole list completes without any leg driving twice.
- **Level 2** offers the model only F B L R. With N E S W in the prompt as well, `gemma4:e4b`
  mixed the two ("forward two then left" came back `N N L N`). Anything outside the four is
  refused before the wheels.
- **Level 3** runs the simulation in `game/` unchanged. `hardware/laptop/level3.py` wraps
  `nav.publish`, where 10d hands a driven leg to the robot, sends the leg to the rover, and
  presses SPACE at 10d's rover pause when the rover reports it done. The rover keeps its heading
  between legs; it must start facing north.
- **Less error without a sensor:** forward runs merge into one pulse (one stop instead of three),
  every turn settles before the next move, and timings come from `calibrate.py` on the floor.

## The check, at Level 1

`hardware/pi/run.py` stops after each command, and a person types the cell the rover really
reached. `hardware/pi/grid.py` compares it with the planned cell:

- **Manhattan**, `|dx| + |dy|` — the N/E/S/W steps it costs to get back on plan.
- **Chebyshev**, `max(|dx|, |dy|)` — the worst single-axis miss.

Results: `DONE`, `OFF` (report, carry on from the real cell), `LOST` (Chebyshev ≥ 2, stop).
Position is never driven back; heading is corrected with a fix-up turn, as
[`ARCHITECTURE.md`](../ARCHITECTURE.md) says. Levels 2 and 3 measure nothing, so they never use it.

A person measures because without a sensor there is nothing to check against: the rover's own
idea of where it is comes from the same timings that drove it, so it always agrees with itself.
The team's earlier timed-pulse link (`rover-bridge`) failed this way.

## What PI_5 settled, and what it did not

- **Motors:** PWM on the SmartElex, pins 12/23 and 13/24, duty 0.082–0.154, M1 = right,
  right side inverted. Copied into `hardware/pi/config.py` from what `stack.sh` launches.
- **Turning:** PI_5 has no "turn 90°" routine. Nav2 turns the rover, closed-loop on rf2o, which is
  odometry from the LiDAR. Open-loop, identical turn pulses measured 34 % apart
  (`calib_omega.py`, 4 of 6 tyres taped). So turns are the weak move.
- **Pi 4:** gpiozero on the same BCM pins. Nothing here is Pi 5 specific.

## Not decided

- The room. Nothing has been measured, and the timings are placeholders until `calibrate.py`
  runs on that floor.
- Whether the link stays plain TCP. Krish's gRPC proposal (`krish/link-bot`) is the alternative.
  Not agreed by the team.
- The start heading. At every level the rover is placed facing north by hand.
