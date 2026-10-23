"""Everything about this particular rover, in one place.

The wiring and duty band are copied from what PI_5's `stack.sh` launches
`l298n_node.py` with on the working rover, not from the node's defaults -- the
defaults are wrong for this build (it runs left_is_a=false, invert_right=true).

The timings are placeholders until `calibrate.py` has measured them on the floor.
It writes `calib.json` next to this file, which overrides them and is not committed:
it belongs to one chassis, one set of tyres and one battery charge.
"""

import json
import os

# SmartElex 15D, PWM independent mode (DIP 3). BCM pin numbers -- the same header on a
# Pi 4 and a Pi 5, so nothing here changes if the rover moves to a Pi 4.
M1_PWM, M1_DIR = 12, 23
M2_PWM, M2_DIR = 13, 24
PWM_HZ = 490
LEFT_IS_M1 = False      # this build: M1 is the right side, M2 the left
INVERT_LEFT = False
INVERT_RIGHT = True

# Duty band. Below MIN_DUTY the drivetrain does not move at all (measured on PI_5, 0.082).
# MAX_DUTY is the ceiling PI_5 settled on so the taped tyres stay controllable (0.154).
# The board's legal window is 0.08..0.94; never go near the top on a bench.
MIN_DUTY = 0.082
MAX_DUTY = 0.154

# Fraction of the band each motion runs at. 1.0 = MAX_DUTY.
DRIVE_POWER = 1.0
TURN_POWER = 1.0

# One grid cell on the floor. room_fit.py measures the room and suggests one: the game's
# 30 x 30 map at 0.1 m (3 m, the smallest allowed) up to 0.33 m (10 m, the cap).
CELL_M = 0.50

# Seconds of motor-on time per cell and per quarter turn. PLACEHOLDERS -- run calibrate.py.
FORWARD_S_PER_CELL = 5.0    # ~0.10 m/s, the speed PI_5's nav2_params measured at this ceiling
TURN_S_PER_90 = 2.0
# The rover's measured forward speed, m/s, from `calibrate.py forward`. When it is known,
# FORWARD_S_PER_CELL follows from it and CELL_M, so a new cell size needs no recalibrating.
FORWARD_M_PER_S = None

# Time to wait after a stop before the next motion, so coast does not run into it.
# PI_5's spin_test.py exists because this rover keeps turning after the stop.
SETTLE_S = 0.6

# Keyboard driving: a held motion stops by itself after this long with no key.
LATCH_MAX_S = 3.0

# --- the LiDAR (LDROBOT LD19) ------------------------------------------------
# Its CP2102 USB adapter; /dev/ttyUSB0 on this Pi. The by-id path survives other USB
# serial devices being plugged in first.
LIDAR_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
LIDAR_BAUD = 230400
# Which way the LD19's own angles run, and where its 0 deg points on this rover. The
# rover frame is x forward, y left, angles anticlockwise from forward. LD19 angles are
# documented as clockwise; both values are checked on the rover with
# `lidar_check.py --watch` (a hand in front should read 0, on the left +90).
LIDAR_CLOCKWISE = True
LIDAR_OFFSET_DEG = 0.0
# Points kept. Closer than LIDAR_MIN_M is the rover's own body and mount; the LD19 is
# rated to 12 m but beyond 8 m it is mostly noise indoors. Intensity 0 keeps everything
# until lidar_check has shown what a weak return looks like here.
LIDAR_MIN_M = 0.15
LIDAR_MAX_M = 8.0
LIDAR_MIN_INTENSITY = 0
# Set by `lidar_check.py --mount` once a hand in front read 0 deg and on the left +90.
# The drive loop refuses LiDAR checks until then: with the scan mirrored, a heading fix
# would turn the wrong way.
LIDAR_MOUNT_CHECKED = False

# --- checking a drive with the LiDAR (Level 4) --------------------------------
LIDAR_CHECK_EVERY = 5      # a forward run longer than this many cells is checked part-way
HEADING_TOL_DEG = 5.0      # heading error, measured, beyond which a fix-up turn is made
HEADING_FIX_TRIES = 3      # fix-up turns before giving up and reporting the heading as off
# Shorter pulses than this do not move the chassis at all -- a guess until measured. A
# heading error needing less is left and reported. At TURN_S_PER_90 = 2 s that is 3.6 deg,
# under HEADING_TOL_DEG; at 0.5 s it is 14 deg, so calibrate turns before trusting fixes.
FIX_MIN_S = 0.08
# A measured position this close to the planned cell's centre counts as that cell, however
# small the cells. At 0.1 m cells, "the right cell" alone would be +-5 cm -- about what a
# stop coasts -- and every move would be reported as a miss.
POSITION_TOL_M = 0.08

CALIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib.json")
# What calib.json may override -- the values that belong to one rover on one floor.
# `settings.py` shows and sets them.
_CALIBRATED = ("CELL_M", "FORWARD_M_PER_S", "FORWARD_S_PER_CELL", "TURN_S_PER_90", "SETTLE_S",
               "DRIVE_POWER", "TURN_POWER", "MIN_DUTY", "MAX_DUTY",
               "LIDAR_CLOCKWISE", "LIDAR_OFFSET_DEG", "LIDAR_MIN_INTENSITY", "LIDAR_MOUNT_CHECKED",
               "LIDAR_CHECK_EVERY", "HEADING_TOL_DEG", "FIX_MIN_S", "POSITION_TOL_M")


# The values above, before calib.json touches them. settings.py shows and restores these.
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
