"""fake_world -- a pretend rover in a pretend room, for testing without hardware.

    world = FakeWorld(turn_gain=0.8)        # turns come up 20 % short
    motors, lidar = world.motors(), world.lidar()

`motors` takes the same set/stop calls as motors.Motors and moves the pretend rover;
`lidar` answers next_scan()/latest() like ld19.LD19, with a scan cast from wherever
the rover really is in the room. So server.py's drive loop runs on it unchanged --
`python3 server.py --fake-world` -- and the tests drive it with known errors to check
the LiDAR checks catch them.

Speeds come from config: full power covers one cell in FORWARD_S_PER_CELL and a
quarter turn in TURN_S_PER_90, times `fwd_gain` / `turn_gain`. A gain below 1 is slip.

Map frame as in locate.py: x forward at home, y left, yaw anticlockwise.
"""

import math
import threading
import time

import numpy as np

import config as C
from ld19 import Scan

# 4 m x 3 m with home off-centre and one box in a corner, so no two spots look alike.
ROOM = [((-1.0, -0.5), (3.0, -0.5)), ((3.0, -0.5), (3.0, 2.5)),
        ((3.0, 2.5), (-1.0, 2.5)), ((-1.0, 2.5), (-1.0, -0.5)),
        ((2.2, 1.8), (2.6, 1.8)), ((2.6, 1.8), (2.6, 2.2)),
        ((2.6, 2.2), (2.2, 2.2)), ((2.2, 2.2), (2.2, 1.8))]



def _box(x0, y0, x1, y1):
    return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]


# What `server.py --fake-world` drives in, laid out the way a real arena has to be: the
# simulation's 30 x 30 grid at 0.2 m a cell is 6 m across with home in the middle, and
# the simulation drives right along its edge rows, so all of that is clear floor and the
# walls stand 1 m beyond it. The boxes are landmarks in that margin, none placed
# symmetrically -- inside the 6 m the rover would drive into them. The pretend rover has
# no collisions: driven through a wall or a box, it stops matching, and the check says
# UNSURE.
ARENA = (_box(-4.2, -4.2, 4.2, 4.2) + _box(3.3, 1.0, 3.9, 1.6)
         + _box(-3.9, -2.0, -3.4, -1.4) + _box(1.5, -3.9, 2.1, -3.4))


def cast(segments, pose, rays=500, noise=0.01, rng=None):
    """A scan in the rover frame from `pose` in the map frame: (xs, ys), metres."""
    rng = rng or np.random.default_rng(0)
    px, py, yaw = pose
    ang = np.linspace(-math.pi, math.pi, rays, endpoint=False)
    dist = np.full(rays, np.inf)
    dx, dy = np.cos(ang + yaw), np.sin(ang + yaw)
    for (ax, ay), (bx, by) in segments:
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        with np.errstate(divide="ignore", invalid="ignore"):
            t = ((ax - px) * ey - (ay - py) * ex) / den
            u = ((ax - px) * dy - (ay - py) * dx) / den
        hit = (np.abs(den) > 1e-9) & (t > 0) & (u >= 0) & (u <= 1)
        dist = np.where(hit & (t < dist), t, dist)
    ok = np.isfinite(dist) & (dist > C.LIDAR_MIN_M)
    r = dist[ok] + rng.normal(0, noise, ok.sum())
    return r * np.cos(ang[ok]), r * np.sin(ang[ok])


class FakeWorld:
    def __init__(self, segments=ROOM, pose=(0.0, 0.0, 0.0), fwd_gain=1.0, turn_gain=1.0):
        self.segments = segments
        self.pose = tuple(pose)               # the truth, which nothing on the rover can read
        self.fwd_gain, self.turn_gain = fwd_gain, turn_gain
        self._cmd, self._t = (0.0, 0.0), time.monotonic()
        self._lock = threading.Lock()
        self._rng = np.random.default_rng(1)

    def _advance(self):
        now = time.monotonic()
        dt, self._t = now - self._t, now
        left, right = self._cmd
        v = (left + right) / 2 * (C.CELL_M / C.FORWARD_S_PER_CELL) * self.fwd_gain
        w = (right - left) / 2 * (math.pi / 2 / C.TURN_S_PER_90) * self.turn_gain
        x, y, yaw = self.pose
        steps = max(1, int(dt / 0.005))
        for _ in range(steps):                # small steps: a curve is a curve
            yaw += w * dt / steps
            x += v * math.cos(yaw) * dt / steps
            y += v * math.sin(yaw) * dt / steps
        self.pose = (x, y, yaw)

    def command(self, left, right):
        with self._lock:
            self._advance()
            self._cmd = (left, right)

    def scan(self):
        with self._lock:
            self._advance()
            pose = self.pose
        xs, ys = cast(self.segments, pose, rng=self._rng)
        now = time.monotonic()
        return Scan(np.arctan2(ys, xs), np.hypot(xs, ys), np.full(len(xs), 200.0), now, now, 3600.0)

    def motors(self):
        return _Motors(self)

    def lidar(self):
        return _Lidar(self)


class _Motors:
    def __init__(self, world):
        self.world = world

    def set(self, left, right):
        self.world.command(left, right)

    def stop(self):
        self.world.command(0.0, 0.0)

    def close(self):
        self.stop()


class _Lidar:
    crc_fail = 0

    def __init__(self, world):
        self.world, self.turns = world, 0

    def next_scan(self, timeout=1.0):
        self.turns += 1
        return self.world.scan()

    latest = next_scan

    def close(self):
        pass
