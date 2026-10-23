"""locate -- where the rover is, by fitting a LiDAR scan to a reference of the room.

Pure maths: points in, pose out. No serial port, no motors, so it is tested on a
laptop with made-up rooms (test_locate.py).

The method is the one PI_5's reseed.py used on this rover (2-3 cm in issue.md), without
ROS around it:

  1. The reference is the room's points, recorded at setup (reference.py). From them a
     grid is built where each 3 cm cell holds the distance to the nearest reference
     point, capped at CLAMP_M.
  2. A pose is scored by moving the scan's points to that pose and averaging the grid
     under them. Capping is what makes a person walking by, or a chair that moved, cost
     a fixed amount instead of dragging the answer towards them.
  3. The search runs only *around the pose the rover should be in* -- +-SEARCH_M and
     +-SEARCH_DEG, coarse then fine. That is the difference from what failed in the lab:
     AMCL searched the whole map and found the 180 deg flip and the look-alike spots
     between table legs. A look-alike half a room away is never considered.
  4. The answer comes with a verdict. OK; POOR, when not enough of the scan lands on
     the reference to trust it; AMBIGUOUS, when a clearly different pose fits almost as
     well. Anything but OK means "do not act on this".

The thresholds below are first values, not tuned on the floor yet.

Map frame: the rover's own frame at the moment the reference was recorded at home.
x = forward at home (grid north), y = left at home (grid west), yaw anticlockwise.
`to_cell` / `from_cell` convert to the grid of grid.py (x east, y south, N/E/S/W).
"""

import math

import numpy as np

RES = 0.03             # metres per likelihood cell
CLAMP_M = 0.30         # distance cap: further than this from every wall costs the same
SEARCH_M = 0.30        # translation searched either side of the guess
SEARCH_DEG = 30.0      # rotation searched either side of the guess
MATCH_M = 0.05         # a point within this of the reference counts as matched
OK_MATCHED = 0.60      # share of points that must match for OK
OK_COST = 0.06         # mean capped distance, metres, at or below which a fit is OK
AMBIG_RATIO = 1.25     # a far-away fit within this factor of the best is AMBIGUOUS
AMBIG_M, AMBIG_DEG = 0.15, 10.0   # "far away" for the line above


def transform(xs, ys, pose):
    """Points from the rover frame into the map frame at pose (x, y, yaw)."""
    x, y, yaw = pose
    c, s = math.cos(yaw), math.sin(yaw)
    return x + c * xs - s * ys, y + s * xs + c * ys


def thin(xs, ys, cell=0.03):
    """One point per `cell` square, so a wall seen up close does not outweigh the rest."""
    keys = np.stack([np.floor(xs / cell), np.floor(ys / cell)], axis=1)
    _, idx = np.unique(keys, axis=0, return_index=True)
    idx = np.sort(idx)
    return xs[idx], ys[idx]


class Reference:
    def __init__(self, xs, ys):
        self.xs, self.ys = thin(np.asarray(xs, float), np.asarray(ys, float))
        self._build()

    def _build(self):
        pad = CLAMP_M + RES
        self.x0, self.y0 = self.xs.min() - pad, self.ys.min() - pad
        nx = int(math.ceil((self.xs.max() + pad - self.x0) / RES)) + 1
        ny = int(math.ceil((self.ys.max() + pad - self.y0) / RES)) + 1
        field = np.full((nx, ny), CLAMP_M)
        # Stamp a capped distance disc around every reference point.
        r = int(math.ceil(CLAMP_M / RES))
        off = np.arange(-r, r + 1) * RES
        disc = np.minimum(np.hypot(off[:, None], off[None, :]), CLAMP_M)
        for px, py in zip(self.xs, self.ys):
            fx, fy = (px - self.x0) / RES, (py - self.y0) / RES
            ix, iy = int(round(fx)), int(round(fy))
            # the disc is centred on the cell, not the point: at most RES/2 of error
            a0, a1 = max(ix - r, 0), min(ix + r + 1, nx)
            b0, b1 = max(iy - r, 0), min(iy + r + 1, ny)
            sub = disc[a0 - (ix - r):a1 - (ix - r), b0 - (iy - r):b1 - (iy - r)]
            np.minimum(field[a0:a1, b0:b1], sub, out=field[a0:a1, b0:b1])
        self.field = field

    def add(self, xs, ys):
        """Grow the reference with more points, already in the map frame."""
        self.xs, self.ys = thin(np.concatenate([self.xs, xs]), np.concatenate([self.ys, ys]))
        self._build()

    def lookup(self, mx, my):
        """Capped distance to the reference at map points; off the grid is CLAMP_M."""
        ix = np.rint((mx - self.x0) / RES).astype(int)
        iy = np.rint((my - self.y0) / RES).astype(int)
        inside = (ix >= 0) & (ix < self.field.shape[0]) & (iy >= 0) & (iy < self.field.shape[1])
        out = np.full(mx.shape, CLAMP_M)
        out[inside] = self.field[ix[inside], iy[inside]]
        return out


def _search(ref, xs, ys, cx, cy, cyaw, span_m, step_m, span_deg, step_deg):
    """Cost of every pose on a grid around (cx, cy, cyaw). Returns (costs, poses)."""
    d = np.arange(-span_m, span_m + step_m / 2, step_m)
    yaws = cyaw + np.radians(np.arange(-span_deg, span_deg + step_deg / 2, step_deg))
    dx, dy = np.meshgrid(d, d, indexing="ij")
    dx, dy = dx.ravel(), dy.ravel()
    costs, poses = [], []
    for yaw in yaws:
        c, s = math.cos(yaw), math.sin(yaw)
        rx, ry = c * xs - s * ys, s * xs + c * ys            # rotated once per yaw
        mx = (cx + dx)[:, None] + rx[None, :]
        my = (cy + dy)[:, None] + ry[None, :]
        costs.append(ref.lookup(mx, my).mean(axis=1))
        poses.append(np.stack([cx + dx, cy + dy, np.full(dx.shape, yaw)], axis=1))
    return np.concatenate(costs), np.concatenate(poses)


def locate(ref, xs, ys, guess, span_m=SEARCH_M):
    """Fit scan points (rover frame) to `ref`, searching around `guess` (x, y, yaw),
    +-`span_m` in translation.

    Returns a dict: pose (x, y, yaw), cost (m), matched (0..1), status
    (OK / POOR / AMBIGUOUS) and, when AMBIGUOUS, the rival pose.
    """
    xs, ys = thin(np.asarray(xs, float), np.asarray(ys, float))
    if len(xs) < 30:
        return {"pose": tuple(guess), "cost": CLAMP_M, "matched": 0.0, "status": "POOR",
                "note": f"only {len(xs)} usable points"}
    sub = slice(None, None, max(1, len(xs) // 150))         # ~150 points for the coarse pass
    gx, gy, gyaw = guess
    step = 0.03 if span_m <= SEARCH_M else 0.05          # a wider look, coarser at first
    costs, poses = _search(ref, xs[sub], ys[sub], gx, gy, gyaw, span_m, step, SEARCH_DEG, 2.0)
    best = int(np.argmin(costs))
    bx, by, byaw = poses[best]
    # a rival: the best pose clearly away from the winner
    far = (np.hypot(poses[:, 0] - bx, poses[:, 1] - by) > AMBIG_M) | \
          (np.degrees(np.abs((poses[:, 2] - byaw + math.pi) % (2 * math.pi) - math.pi)) > AMBIG_DEG)
    rival = int(np.argmin(np.where(far, costs, np.inf))) if far.any() else None
    # fine pass with every point
    costs2, poses2 = _search(ref, xs, ys, bx, by, byaw, step + 0.01, 0.01, 2.0, 0.25)
    k = int(np.argmin(costs2))
    pose = tuple(float(v) for v in poses2[k])
    mx, my = transform(xs, ys, pose)
    dist = ref.lookup(mx, my)
    out = {"pose": pose, "cost": float(dist.mean()), "matched": float((dist < MATCH_M).mean()),
           "points": int(len(xs))}
    if out["matched"] < OK_MATCHED or out["cost"] > OK_COST:
        out["status"] = "POOR"
    elif rival is not None and costs[rival] < costs[best] * AMBIG_RATIO:
        out["status"] = "AMBIGUOUS"
        out["rival"] = tuple(float(v) for v in poses[rival])
    else:
        out["status"] = "OK"
    return out


# --- the map frame and grid.py's grid -----------------------------------------
# map x = north, map y = west;  grid x = east, grid y = south;  grid heading N E S W = 0..3
def to_cell(pose, cell_m):
    """Map pose (x, y, yaw) -> nearest grid cell (gx, gy) and heading index 0..3."""
    x, y, yaw = pose
    gx, gy = int(round(-y / cell_m)), int(round(-x / cell_m))
    h = int(round(-math.degrees(yaw) / 90.0)) % 4
    return gx, gy, h


def from_cell(gx, gy, h, cell_m):
    """Grid cell and heading index -> map pose (x, y, yaw)."""
    return (-gy * cell_m, -gx * cell_m, math.radians(-90.0 * h))
