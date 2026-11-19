# Prototype 14 — 13, made plain for the hand-over

14 is the code the team takes over. Abhishek and the others build an ESP32 version of Level 3
from it. So every line had to become one a teammate can explain, to the bar in
[`repo_rules.md`](../repo_rules.md) §7, without changing what the game or the rover does. 14
behaves exactly as 13 did. The design is 13's: the simulation is
[`../prototype11/DESIGN.md`](../prototype11/DESIGN.md), the rover's levels are
[`../prototype12/DESIGN.md`](../prototype12/DESIGN.md), and 13's changes are
[`../prototype13/DESIGN.md`](../prototype13/DESIGN.md).

## Copied from

13 at `aad1f83`, committed unchanged as the first commit. `git diff e1c00da HEAD -- .` shows
everything 14 did.

## What changed

| | 13 | 14 |
|---|---|---|
| code (not tests) | 11,339 lines in 44 files | 8,673 lines in 37 files |
| comments and docstrings | 26% of those lines | 10% |
| functions over 40 lines | 39; the longest, `main()`, 626 | 24; the longest is the prompt's text, 110 |
| tests | 20 files, five kinds of runner | one `tests/` folder, `pytest`, 209 tests |

The changes, by kind:

- **Comments carry conclusions, not history.** Dates, run directories, measurement tables
  and "prototype 7 did X" are gone; git and [`docs/findings.md`](../docs/findings.md) keep
  them.
- **One job per function.** `main()` is now a `Game` object with one method per mode's keys,
  plus `nightfall`, `await_rover` and `frame`. The desk's commands are in `desk.py`.
  `nav.goto`, `skills.call`, `score`, `report.build` and the screen's long functions are
  split up the same way.
- **Plain Python.** These went:
  - lambdas, nested comprehensions and walrus loops;
  - `getattr` with defaults and `getattr("_" + phase)` dispatch;
  - one-item lists used as boxes, and nested ternaries.

  Modules are imported by their own names (`settings.BATTERY`, not `S.BATTERY`), and a
  world is called `world`.
- **One copy of each thing.** There is one JSONL reader, one disc, one `neighbours()`, one
  set of colours, and one calib.json reader on the Pi. Ollama's transport is its own module,
  `ollama.py`.
- **Level 3 uses named hooks.** `game/nav.py` has `wait_for_rover`, `leg_started`,
  `leg_finished` and `rover_driving`, None unless Level 3 sets them. Level 3 no longer swaps
  out `nav.publish` or `pygame.event.get` at runtime.
  [`hardware/README.md`](hardware/README.md) says what each hook does.
- **The link is written down** in [`hardware/LINK.md`](hardware/LINK.md): every message both
  ways, for the ESP32 side.
- **Three entry files.** `hardware/laptop/level1_pad.py`, `level2_words.py` and
  `level3_game.py` replace the `run_` wrappers. This settles the README's naming question.

## Cut

- **`probe_map.py` and `probe_read.py`**, the 3 Sept map-reading experiment. Its answer is in
  `docs/findings.md`, and the probe no longer ran against the current prompt.
- **`plan_txt.py`**, the offline route writer. Nothing ran it.
- **`--map rle` and `--executor plan`**, with `MAP_FORMAT` and `EXECUTOR`. These were old
  experiments' other arms, and every run since 10d used the grid map and real drives. The
  `--prompt` flag had only one choice.
- **Level 1 over SSH** (`pi/run.py`, `teleop.py`, `keys.py`), and with it `grid.check` and
  DONE, OFF and LOST. The pad is Level 1, and Levels 2 and 3 never used the check.
- Code nothing read:
  - the Gemini probe settings;
  - the save-format branches no version-2 night reaches;
  - `ONE_CALL_AT_A_TIME`, `Storm.day` and the like.

## Bugs found and fixed

Each is its own commit, after 14 was shown to behave like 13:

- **Level 2's `/stop` then `/reset` crashed.** `link.stop()` never read the rover's answer,
  so the next question got the stop's answer. Now `stop()` reads it, except when Level 3
  exits.
- **A malformed message dropped the window.** A bad heading or a missing field ended that
  window's connection on the Pi. Now the rover answers `{"ok": false, "note": ...}` and
  keeps the connection.
- **The docs promised the laptop reused drive ids.** The retry was said to go "under the same
  id", but it never did, so the rover's memory of finished ids was never used. That memory
  is gone, and the docs say what happens.
- **One test in `test_chat` had never run,** because it was missing from its file's list.
  Under pytest it ran and failed: it tested the rle map paragraph, so it went with rle.

## Found, not fixed

- **10d's kept runs no longer replay cleanly.** Some result wordings changed after 10d, so a
  replay halts on the first changed sentence. 13 does the same.
- **A tape recorded by a replay may not replay itself.** Rows written in the same millisecond
  are ordered only by their timestamps. Runs recorded live are slow enough not to hit this.

## How "behaves exactly as 13" was checked

After every commit, against 13 itself. The checking scripts were scratch work and are not in
the repo.

- Three real-model runs from 10d were replayed through 13 once, to make tapes in 13's own
  wording. Replays of those tapes through 14 give the same transcript, row for row: 452,
  1,258 and 1,368 rows, with every view, result and prompt hash. The replay's `report.md`
  and `night.json` match too.
- **The screen:** `preview.png` and seven more screens are pixel-identical. Those are the
  world mid-drive with map labels, the memory card, the view, the map, the terminal, the quit
  question and the settings screen.
- **`score.py`** prints the same tables over four runs.
- **All three levels against the fake rover.** Level 3's replay prints the same 616 motor
  lines and 700 leg lines. Level 2 with typed moves, and the pad with keys held, send the
  same motor commands.
- **New tests** in `tests/test_keys.py` and `tests/test_link.py`. They press every mode's
  keys through `Game.frame()` with no window, and drive the real `server.py` through
  `RoverLink`.

## Not checked

- 14 hasn't driven the real rover, and nobody has played it with a live model; 13 was the
  same.
- Windows is written but not tested.

## Not decided

- **The room,** as in 12 and 13. Nothing is measured yet.
- **Whether the link stays plain TCP.** Krish's gRPC proposal is the alternative.
