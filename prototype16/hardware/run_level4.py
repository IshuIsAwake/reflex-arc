"""Level 4: Level 3 with the LiDAR. The rover checks every turn and every run with its
LiDAR and fixes its heading; after every leg the simulation's rover is moved to the
cell the LiDAR measured, and the model is told. Double-click to run.

Before the first run: `python3 lidar_check.py --mount` on the Pi, then record home in
run_lidar_map.py (rover on its home spot facing north, press H). The floor the
simulation can drive over must be clear -- hardware/README.md, "The arena".
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop"))
import launch  # noqa: E402
import level3  # noqa: E402

sys.argv.insert(1, "--check")
launch.run(level3.main)
