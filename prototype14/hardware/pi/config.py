"""Everything about this particular rover. The wiring and the duty band are the working
rover's (PI_5's stack.sh), not the motor node's defaults. The timings are placeholders until
calibrate.py measures them; it writes calib.json beside this file, which overrides them."""

import json
import os

# SmartElex 15D in PWM mode (DIP 3). BCM pin numbers, the same on a Pi 4 and a Pi 5.
M1_PWM, M1_DIR = 12, 23
M2_PWM, M2_DIR = 13, 24
PWM_HZ = 490
LEFT_IS_M1 = False  # this build: M1 is the right side, M2 the left
INVERT_LEFT = False
INVERT_RIGHT = True

# Duty band. Below MIN_DUTY the wheels don't move; MAX_DUTY keeps the taped tyres
# controllable. The board allows 0.08..0.94.
MIN_DUTY = 0.082
MAX_DUTY = 0.154

# Share of the band each motion uses. 1.0 = MAX_DUTY.
DRIVE_POWER = 1.0
TURN_POWER = 1.0

# One simulation cell, in metres of floor: ten cells to the metre.
CELL_M = 0.10

# Seconds of motor-on time per cell and per quarter turn. Placeholders: run calibrate.py.
FORWARD_S_PER_CELL = 1.0  # about 0.10 m/s
TURN_S_PER_90 = 2.0
# The measured forward speed. Once known, FORWARD_S_PER_CELL follows from it and CELL_M.
FORWARD_M_PER_S = None

# Wait after a stop before the next move, so the rover's coasting doesn't run into it.
SETTLE_S = 0.6

# Keyboard driving: a held motion stops by itself after this long with no key.
LATCH_MAX_S = 3.0

CALIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib.json")
# What calib.json may override: the values that belong to one rover on one floor.
_CALIBRATED = ("CELL_M", "FORWARD_M_PER_S", "FORWARD_S_PER_CELL", "TURN_S_PER_90", "SETTLE_S",
               "DRIVE_POWER", "TURN_POWER", "MIN_DUTY", "MAX_DUTY")


# The values above, before calib.json. settings.py shows and restores these.
DEFAULTS = {k: globals()[k] for k in _CALIBRATED}


def _derive():
    """With a measured speed, the time per cell is the cell over the speed."""
    global FORWARD_S_PER_CELL
    if FORWARD_M_PER_S:
        FORWARD_S_PER_CELL = round(CELL_M / FORWARD_M_PER_S, 3)


def load():
    """Overlay calib.json, if there is one. Returns the keys it changed."""
    if not os.path.exists(CALIB_FILE):
        return {}
    with open(CALIB_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    got = {k: v for k, v in data.items() if k in _CALIBRATED}
    globals().update(got)
    _derive()
    return got


def save(**values):
    """Merge `values` into calib.json."""
    data = {}
    if os.path.exists(CALIB_FILE):
        with open(CALIB_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    data.update(values)
    with open(CALIB_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    globals().update({k: v for k, v in values.items() if k in _CALIBRATED})
    _derive()


load()
