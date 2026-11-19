"""The laptop's end of the LiDAR server on the rover (hardware/pi/lidar_server.py), port 5006.
The motors keep their own link, link.py, on port 5005. The messages are in ../LIDAR.md.

    lidar, note = lidar_link.connect("nith.local")   # None and why, if there is no LiDAR
    lidar.home()                                      # rover on home, facing north
    lidar.locate({"x": 3, "y": -2, "heading": "E"}, 0.1)"""

import json
import socket

PORT = 5006


class LidarLink:
    def __init__(self, host):
        # locate takes about a second and a half on the Pi, home a little more
        self.sock = socket.create_connection((host, PORT), timeout=10)
        self.lines = self.sock.makefile("r", encoding="utf-8")

    def ask(self, msg):
        self.sock.sendall((json.dumps(msg) + "\n").encode())
        return json.loads(self.lines.readline())

    def home(self):
        return self.ask({"op": "home"})

    def locate(self, pose, cell_m):
        """Where the rover is, searched near `pose` (cells from home, heading N E S W)."""
        return self.ask({"op": "locate", "x": pose["x"], "y": pose["y"],
                         "heading": pose["heading"], "cell_m": cell_m})

    def ahead(self, look_m):
        """How far the rover's front edge can go straight before something, or None if
        nothing is within look_m."""
        return self.ask({"op": "ahead", "look_m": look_m})["clear_m"]

    def close(self):
        self.sock.close()


def connect(host):
    """The LiDAR link, or None. Returns (link or None, a line saying what was found)."""
    try:
        lidar = LidarLink(host)
        reply = lidar.ask({"op": "hello"})
    except (OSError, ValueError) as e:
        return None, (f"no LiDAR server at {host}:{PORT} ({e}). "
                      f"To use the LiDAR, run on the Pi: cd ~/p15 && python3 lidar_server.py")
    if not reply["lidar"]:
        lidar.close()
        return None, reply["note"]
    return lidar, reply["note"]
