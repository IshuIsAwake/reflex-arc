"""See and change the values that tie the simulation to the real floor. Runs on the Pi.

    python3 settings.py                  every value, what it means, where it comes from
    python3 settings.py CELL_M 0.25      set one -- saved in calib.json
    python3 settings.py --reset CELL_M   back to the default in config.py

Restart the rover server after a change; it reads them when it starts.

How the simulation and the floor line up:
  * one simulation cell is CELL_M metres of floor;
  * the simulation's landing cell is the rover's home spot -- where home is recorded and
    where the rover stands when Level 3 or 4 starts;
  * north, up on the simulation's screen, is the way the rover faces on that spot;
  * a cell takes FORWARD_S_PER_CELL seconds to drive and a quarter turn TURN_S_PER_90
    -- measure both with calibrate.py on the floor rather than typing them.
Change CELL_M and the forward timing must be measured again: it is seconds per cell.
"""

import json
import os
import sys

import config as C

MEANING = {
    "CELL_M": "metres of floor per simulation cell",
    "FORWARD_M_PER_S": "measured forward speed (calibrate.py forward); sets the line below",
    "FORWARD_S_PER_CELL": "seconds to drive one cell -- CELL_M / speed once speed is measured",
    "TURN_S_PER_90": "seconds for a quarter turn (calibrate.py turn)",
    "SETTLE_S": "pause after each move, so coasting ends before the next",
    "DRIVE_POWER": "share of the duty band used driving, 0..1",
    "TURN_POWER": "share of the duty band used turning, 0..1",
    "MIN_DUTY": "PWM duty below which the wheels do not move (measured on PI_5)",
    "MAX_DUTY": "PWM duty ceiling (PI_5's, keeps the taped tyres controllable)",
    "LIDAR_CLOCKWISE": "LD19 angles run clockwise (lidar_check.py --mount sets it)",
    "LIDAR_OFFSET_DEG": "where the LD19's 0 deg points on the rover (--mount sets it)",
    "LIDAR_MIN_INTENSITY": "LiDAR returns weaker than this are dropped",
    "LIDAR_MOUNT_CHECKED": "--mount has been run; checked drives refuse until it has",
    "LIDAR_CHECK_EVERY": "a checked forward run is checked at least every this many cells",
    "HEADING_TOL_DEG": "heading error a checked drive leaves alone",
    "FIX_MIN_S": "shortest pulse that moves the chassis; smaller fixes are not tried",
    "POSITION_TOL_M": "a miss this small counts as the right cell, whatever the cell size",
}

DEFAULTS = C.DEFAULTS


def saved():
    if not os.path.exists(C.CALIB_FILE):
        return {}
    with open(C.CALIB_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def parse(name, text):
    kind = type(DEFAULTS[name]) if DEFAULTS[name] is not None else float
    if kind is bool:
        if text.lower() in ("true", "yes", "1", "on"):
            return True
        if text.lower() in ("false", "no", "0", "off"):
            return False
        raise ValueError(f"{name} is true or false")
    return kind(float(text)) if kind is int else float(text)


def show():
    mine = saved()
    print(f"values from config.py, overridden by {C.CALIB_FILE}\n")
    for name in C._CALIBRATED:
        value = getattr(C, name)
        where = "calib.json" if name in mine else "default"
        print(f"  {name:<20} {str(value):<10} {where:<11} {MEANING.get(name, '')}")
    print("\nset one: python3 settings.py NAME VALUE    then restart the server")


def main():
    args = sys.argv[1:]
    if not args:
        show()
        return
    if args[0] == "--reset" and len(args) == 2:
        name = args[1]
        mine = saved()
        if name not in mine:
            print(f"{name} is already the default ({DEFAULTS.get(name)})")
            return
        del mine[name]
        with open(C.CALIB_FILE, "w", encoding="utf-8") as fh:
            json.dump(mine, fh, indent=2)
        print(f"{name} back to the default {DEFAULTS[name]}. Restart the server.")
        return
    if len(args) != 2 or args[0] not in C._CALIBRATED:
        sys.exit(f"usage: settings.py [NAME VALUE | --reset NAME]\nNAME is one of: "
                 f"{', '.join(C._CALIBRATED)}")
    name, text = args
    try:
        value = parse(name, text)
    except ValueError as e:
        sys.exit(f"not a value for {name}: {text} ({e})")
    C.save(**{name: value})
    print(f"{name} = {value}  (saved in calib.json). Restart the server.")
    if name == "CELL_M":
        print(f"FORWARD_S_PER_CELL is now {C.FORWARD_S_PER_CELL} s, from the measured speed."
              if C.FORWARD_M_PER_S else
              "No forward speed measured yet: run calibrate.py forward so a cell takes the "
              "right time.")


if __name__ == "__main__":
    main()
