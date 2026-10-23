"""Level 3: the simulation in prototype12/game plans the mission and the rover drives every
leg. No LiDAR. Double-click to run.

Needs Ollama running on this laptop, and the rover server running on the Pi. Options for
the simulation go on the command line, e.g. `python run_level3.py --sols 2`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop"))
import launch  # noqa: E402
import level3  # noqa: E402

launch.run(level3.main)
