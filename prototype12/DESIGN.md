# Prototype 16 — the rover takes commands, and checks every one

Koushik's integration lab. The rover drives a list of grid commands and, after each one, compares
where it should be with where it is. Nothing in `prototype10*/` or `PI_5` is changed; this folder
borrows from them.

## The levels

| level | what drives | where the pose comes from | status |
|---|---|---|---|
| 1 | the keyboard, and a typed command list | a person typing the real cell | **built** |
| 2 | an LLM issuing simple commands (IoT level) | dead reckoning | **built**; the LLM run against a fake rover |
| 3 | the LLM through the whole simulation (`game/`'s `goto` → `plan.txt`) | the simulation | **built**; 14 legs on the real rover, wheels in the air |
| 4 | as 3 | the LD19 LiDAR | **built**, the simulation following the LiDAR; end to end on a pretend rover only |
| 5 | as 4, with the error budget tuned on the LiDAR's numbers | the LiDAR | not started |

Every level keeps the same check. What changes is who drives and who measures.

## Levels 2 and 3: drive everything, measure nothing

Until the LiDAR, the job is to complete every command with as little error as the open-loop
rover allows. The rover replays what it is sent and reports a dead-reckoned pose; at Level 3 the
simulation is the truth and the floor follows it.

- **The link** is TCP, one JSON object a line, standard library on both ends (`hardware/pi/server.py`,
  `hardware/laptop/link.py`). Motors stop if the laptop disconnects. A drive is retried under the same id
  after a drop and the rover answers a finished id from memory, so the whole list completes
  without any leg driving twice.
- **Level 2** offers the model only F B L R. With N E S W in the prompt as well, `gemma4:e4b`
  mixed the two ("forward two then left" came back `N N L N`). Anything outside the four is
  refused before the wheels.
- **Level 3** runs the simulation in `game/` unchanged. `hardware/laptop/level3.py` wraps `nav.publish`, where 10d hands a driven
  leg to the robot, sends the leg to the rover, and presses SPACE at 10d's rover pause when the
  rover reports it done. The rover keeps its heading between legs; it must start facing north.
- **Less error without a sensor:** forward runs merge into one pulse (one stop instead of three),
  every turn settles before the next move, and timings come from `calibrate.py` on the floor.

## The check

After each command the rover stops. `hardware/pi/grid.py` computes two distances between the expected
cell and the measured one:

- **Manhattan**, `|dx| + |dy|` — the N/E/S/W steps it costs to get back on plan, which is what A\*
  will pay to replan.
- **Chebyshev**, `max(|dx|, |dy|)` — the worst single-axis miss. "Within a cell" is Chebyshev ≤ 1.

On whole cells both are zero together, so either says whether it arrived. Where they differ is the
diagnosis: equal means the miss is along one axis (short, overshoot, sideways slide); Manhattan
larger means both axes, which on this skid-steer rover nearly always means the heading went first.

Results: `DONE`, `OFF` (report, carry on from the real cell), `LOST` (Chebyshev ≥ 2, stop).
Position is reported and never driven back; heading is corrected with a fix-up turn, as
[`ARCHITECTURE.md`](../ARCHITECTURE.md) says.

## Why a person measures at Level 1

Without a sensor there is nothing to check against: the rover's own idea of where it is comes from
the same timings that drove it, so it always agrees with itself. The team's earlier timed-pulse
link (`rover-bridge`) failed this way. A person reading the floor is the Level 1 sensor, and the
LiDAR replaces them at Level 4 without the check changing.

## What PI_5 settled, and what it did not

- **Motors:** PWM on the SmartElex, pins 12/23 and 13/24, duty 0.082–0.154, M1 = right,
  right side inverted. Copied into `hardware/pi/config.py` from what `stack.sh` launches.
- **Turning:** PI_5 has no "turn 90°" routine. Nav2 turns the rover, closed-loop on rf2o, which is
  odometry from the LiDAR. Open-loop, identical turn pulses measured 34 % apart
  (`calib_omega.py`, 4 of 6 tyres taped). So until Level 4, turns are the weak move, and the
  check is what shows it.
- **Pi 4:** gpiozero on the same BCM pins. Nothing here is Pi 5 specific.

## Level 4 so far: knowing where it is

The LD19 is read straight off its serial port (`hardware/pi/ld19.py`; on this rover 9.7 turns a
second, 502 points a turn, 0 CRC failures). A scan is fitted to a reference of the room recorded
at home (`hardware/pi/locate.py`, `hardware/pi/reference.py`), the method PI_5's `reseed.py` used here, with
one change that matters: the search runs only around where the rover should be (±30 cm, ±30°).
AMCL in the lab searched everywhere and found the 180° flip and the look-alikes between table
legs; a look-alike half a room away is never considered here. A fit that does not hold up comes
back POOR or AMBIGUOUS, never as a confident wrong pose.

Tested on made-up rooms (1 cm, 0.25° on a carried move and turn; the symmetric room does not
flip; a guess 90° off comes back POOR) and on the rover standing still (0.000 m, 0.2°, 100 %
matched, about 0.3 s a fix). The thresholds in `locate.py` are first values.

**The checked drive.** A drive sent with `check` stops after every turn and every forward run
(runs longer than 5 cells are split), locates around where it should be, and then:

- heading off by more than 5° — turns back by what it measured, up to 3 times. The one thing
  corrected. A fix shorter than the chassis can make is left and reported, not rounded up: a
  rounded-up fix overshot by more than the error in testing;
- in another cell — reported with Manhattan and Chebyshev, and the drive carries on from the
  measured cell. Never driven back;
- 2+ cells out (LOST), or the fit not trusted (UNSURE) — stops.

Checked on a pretend rover with a pretend LiDAR (`hardware/pi/fake_world.py`): 15–25 % short or
long turns are caught and fixed in one turn; the same turns unchecked end 36° off; slip under a
cell is reported and carried past; wheels spinning in place stop the drive after one check. Not
yet on the real rover: the motors were not connected, and `lidar_check.py --mount` has not been
run, so the rover refuses checked drives.

Two things the pretend runs showed about the real one. A room of the simulation's size at 0.2 m
cells is about 6 m across; a leg that leaves the room the reference covers ends UNSURE, which is
the right answer and a constraint on the arena. And the fix-up turn needs calibrated turns: at
today's 0.5 s a quarter turn, the smallest fix is about 14°, more than the 5° tolerance.

**The simulation follows.** After every leg, `hardware/laptop/correct.py` moves the simulation's
rover to the cell the LiDAR measured -- as its own `World.move` does, minus the battery, since
the leg was already charged -- and the `goto` result the model reads names that cell and says
why. That is "errors are reported, not corrected" carried through to the map: nothing drives
back, and the model replans from where the rover is. It runs on the simulation in memory; no
file in `game/` is edited. A measured cell the simulation calls rock or off its map is not moved
to: the floor and the simulation then disagree on purpose, the LiDAR's cell stays the rover's
truth, and the next leg may close the gap.

End to end on a pretend rover (the simulation, the 31B, `fake_world.py` with turns 15 % short):
11 legs, 53 checks (47 DONE, 6 OFF), 17 heading fixes, 3 cells followed, 5 refused (off the map
or rock in the simulation), no stops. The model read, for example: *"DONE(at=(28,0), steps=29,
new=39) -- the rover's LiDAR measured it at (28,0), 1 cell from the (29,0) the drive planned."*

What the pretend runs taught about a real arena: the simulation drives right along its own
edges, so all 6 m of the 30 x 30 map at 0.2 m must be clear floor, with walls and landmark boxes
a metre beyond. A box inside was driven into; a wall at the edge was driven through.

Whether the team wants the final prototype to follow the LiDAR this way, or with a hook built
into the simulation itself, is the team's call; this does it without touching their code.

**The room's map** is the 360° scan from home: the walls it sees. Where something hides a wall
from home, the map window's mapping mode fills it in by driving: a view is added at each stop
that already fits the map by 80 % or more and is 20 cm or 15° from the last. No loop closing,
so a big room can drift; the 80 % rule keeps that small. On a pretend lap: 7 views, none added
on the move, the map within 1 cm of the true walls (median; 95 % within 2 cm).

**The nearest wall sets the size** (Koushik's rule). The game's map is 30 x 30 cells with home in
the middle, so its side is 2 x (nearest wall − 0.4 m for the rover's body) and the cell that
over 30. "Nearest" is along the grid, max(|x|, |y|): the map is a square whose corners reach
further than its sides, so a box near a corner counts as near as it is to the square. Kept
between 3 m of map (0.1 m cells, Koushik's floor) and 10 m (the cap); smaller says "clear the
map", with how far and which way the nearest thing is, and keeps nothing. Below about 0.16 m a cell's own half is
under the size of a stop's coast, so a miss is counted only past 8 cm (`POSITION_TOL_M`) at any
cell size. Forward timing is stored as a measured speed, so a new cell size needs no
recalibrating.

## Not decided

- Cell size on the floor. `CELL_M = 0.5` is a placeholder, and it has to fit 10d's legs: a
  single 10d leg ran 16 cells in testing, 8 m at 0.5 m. With no LiDAR nothing on the floor
  corresponds to the sim's rocks, so the cell can shrink to whatever fits the room.
- Whether the link stays plain TCP. Krish's gRPC proposal (`krish/link-bot`) is the alternative;
  its `DONE`/`SHORT`/`FAILED` map onto `DONE`/`OFF`/`LOST`. Not agreed by the team.
- The start heading. Krish's `start-heading.md` covers it for the LiDAR; at Level 1 the rover is
  placed facing north by hand.
- Whether this becomes the README's prototype 12 (hardware integration, the team with Koushik).
