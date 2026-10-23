"""Level 2: tell the rover what to do in plain words; the language model turns them into
moves. No map, no LiDAR. Double-click to run.

Needs Ollama running on this laptop, and the rover server running on the Pi.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop"))
import launch  # noqa: E402
import level2  # noqa: E402

launch.run(level2.main)
