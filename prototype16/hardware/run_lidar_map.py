"""For showing: what the rover's LiDAR sees, live, and where it locates itself. Double-click to run.

The rover server must be running on the Pi. See hardware/README.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop"))
import launch     # noqa: E402
import scan_view  # noqa: E402

launch.run(scan_view.main)
