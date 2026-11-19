"""The LD19 LiDAR on this rover. Checked on the Pi on 2026-11-18: it is on its CP2102 USB
adapter at /dev/ttyUSB0, turning 9.9 times a second with about 500 points a turn."""

# The by-id name stays the same even if another USB serial device is plugged in first.
SERIAL_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
BAUD = 230400

# The LD19 counts its angles clockwise; the rover counts anticlockwise from straight ahead.
# OFFSET_DEG is where the LD19's 0 deg points. lidar_check.py --watch checks both.
# The LD19's 0 deg mark points at the Pi's end, the front. (On 19 Nov F first drove towards
# the LiDAR's end; the Pi's motor pins were swapped so it drives towards the Pi's.)
CLOCKWISE = True
OFFSET_DEG = 0.0

# Closer than MIN_M is the rover's own body (0.14 m was seen on 18 Nov). Past MAX_M is
# mostly noise indoors, though the LD19 is rated to 12 m.
MIN_M = 0.15
MAX_M = 8.0

# How far the LiDAR sits in front of the rover's middle, which is what it turns about;
# negative is behind. Measured 19 Nov with a tape: the LiDAR's centre is 6.5 cm from the
# top plate's back edge, and halfway between the axles is about 12 cm from that edge.
LIDAR_AHEAD_M = -0.055

# The rover's size, from its middle: its front edge, and half its width with the wheels.
# Measured 19 Nov: 30 cm from the back wheels to the front ones; the width is a guess.
ROVER_FRONT_M = 0.15
ROVER_HALF_WIDTH_M = 0.10
# Room kept either side of the rover when looking for something in its way.
SIDE_MARGIN_M = 0.03
# Points needed in the rover's way to call it blocked: one stray point is not a box.
BLOCK_POINTS = 3

# lidar_server.py listens here. server.py, which drives the motors, has 5005.
SERVER_PORT = 5006
