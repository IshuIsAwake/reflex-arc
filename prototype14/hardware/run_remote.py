"""Level 1, for showing: drive the rover by hand -- keys or a gamepad. Double-click to run.

The rover server must be running on the Pi. See hardware/README.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop"))
import launch  # noqa: E402
import pad     # noqa: E402

launch.run(pad.main)
