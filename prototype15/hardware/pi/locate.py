"""Where the rover is, found by lining a new LiDAR scan up with the scan taken at home.

The method is the one PI_5's reseed.py used on this rover, without ROS:
  1. At home, a grid is made from the home scan. Each 3 cm square holds the distance to the
     nearest point the LiDAR saw, capped at CAP_M.
  2. A guessed pose is scored by moving the new scan's points to that pose and averaging
     the grid under them. A good pose puts the points on the walls, so the average is small.
  3. Only poses near where the rover should be are tried (SEARCH_M, SEARCH_DEG), first
     coarse, then fine. A look-alike spot across the room is never considered.
  4. The answer says OK, or POOR when too few points land on the walls to trust it.

Frame: the rover's middle at home. x is forward at home (grid north), y is left at home
(grid west), angles anticlockwise in degrees."""

import math

import numpy as np

import lidar_config

SQUARE = 0.03  # metres a side of each grid square
# Capping is what makes a chair that moved, or a person walking past, cost a fixed amount
# instead of pulling the answer towards them.
CAP_M = 0.30
SEARCH_M = 0.30  # tried either side of the guess
SEARCH_DEG = 30.0
MATCH_M = 0.05  # a point this close to a home point counts as on the wall
OK_MATCHED = 0.60  # share of points that must be on the walls for OK


def to_xy(points):
    """(angle_deg, distance_m) points from ld19 -> x and y arrays around the rover's middle.
    The LiDAR sits LIDAR_AHEAD_M in front of the middle, so every point is that much further
    forward from the middle than from the LiDAR."""
    angles = np.radians([p[0] for p in points])
    dists = np.array([p[1] for p in points])
    xs = dists * np.cos(angles) + lidar_config.LIDAR_AHEAD_M
    ys = dists * np.sin(angles)
    return xs, ys


def thin(xs, ys):
    """Keep one point per square, so a wall seen up close does not outweigh the rest."""
    seen = set()
    keep = []
    for i in range(len(xs)):
        square = (int(xs[i] // SQUARE), int(ys[i] // SQUARE))
        if square not in seen:
            seen.add(square)
            keep.append(i)
    return xs[keep], ys[keep]


def make_room(points):
    """The home scan -> the room: a grid of distances to the nearest wall point."""
    xs, ys = thin(*to_xy(points))
    x0 = xs.min() - CAP_M
    y0 = ys.min() - CAP_M
    width = int((xs.max() + CAP_M - x0) / SQUARE) + 1
    height = int((ys.max() + CAP_M - y0) / SQUARE) + 1
    grid = np.full((width, height), CAP_M)
    square_ys = y0 + np.arange(height) * SQUARE
    # one column of squares at a time: its distance to every wall point, keep the nearest
    for i in range(width):
        square_x = x0 + i * SQUARE
        dist = np.hypot(square_x - xs[:, None], square_ys[None, :] - ys[:, None])
        grid[i] = np.minimum(dist.min(axis=0), CAP_M)
    return {"grid": grid, "x0": x0, "y0": y0, "points": len(xs)}


def clear_ahead(points, look_m):
    """How far the rover can drive straight before its front edge meets something, looking
    look_m ahead in a strip as wide as the rover plus SIDE_MARGIN_M each side. None if the
    strip is clear. The distance is from the front edge."""
    xs, ys = to_xy(points)
    half = lidar_config.ROVER_HALF_WIDTH_M + lidar_config.SIDE_MARGIN_M
    front = lidar_config.ROVER_FRONT_M
    gaps = []
    for i in range(len(xs)):
        if abs(ys[i]) <= half and front < xs[i] <= front + look_m:
            gaps.append(xs[i] - front)
    if len(gaps) < lidar_config.BLOCK_POINTS:
        return None
    gaps.sort()
    # the nearest distance that BLOCK_POINTS points agree on
    return float(gaps[lidar_config.BLOCK_POINTS - 1])


def wall_distance(room, mx, my):
    """The capped distance to the nearest wall point, for points in the home frame."""
    i = np.rint((mx - room["x0"]) / SQUARE).astype(int)
    j = np.rint((my - room["y0"]) / SQUARE).astype(int)
    width, height = room["grid"].shape
    inside = (i >= 0) & (i < width) & (j >= 0) & (j < height)
    out = np.full(mx.shape, CAP_M)
    out[inside] = room["grid"][i[inside], j[inside]]
    return out


def place(xs, ys, pose):
    """Scan points seen from pose (x, y, heading) -> where they are in the home frame."""
    x, y, heading = pose
    a = math.radians(heading)
    mx = x + math.cos(a) * xs - math.sin(a) * ys
    my = y + math.sin(a) * xs + math.cos(a) * ys
    return mx, my


def search(room, xs, ys, guess, span_m, step_m, span_deg, step_deg):
    """Try every pose on a grid around guess (x, y, heading). Returns the best one: the
    one whose points land closest to the walls on average."""
    shifts = np.arange(-span_m, span_m + step_m / 2, step_m)
    turns = np.arange(-span_deg, span_deg + step_deg / 2, step_deg)
    best_score = CAP_M + 1
    best = guess
    for turn in turns:
        for dx in shifts:
            for dy in shifts:
                pose = (guess[0] + dx, guess[1] + dy, guess[2] + turn)
                score = wall_distance(room, *place(xs, ys, pose)).mean()
                if score < best_score:
                    best_score = score
                    best = pose
    return best


def locate(room, points, guess):
    """Where the rover is, near guess (x_m, y_m, heading_deg). Returns a dict: x, y,
    heading, matched (share of points on the walls) and status OK or POOR."""
    xs, ys = thin(*to_xy(points))
    if len(xs) < 30:
        return {"x": guess[0], "y": guess[1], "heading": guess[2], "matched": 0.0,
                "status": "POOR"}
    # coarse with about 150 points, then fine with all of them around the coarse answer.
    # On the Pi 4 these steps take about 1 s together; 3 cm and 2 deg steps took 2.6 s
    # and found the same pose.
    every = max(1, len(xs) // 150)
    pose = search(room, xs[::every], ys[::every], guess, SEARCH_M, 0.05, SEARCH_DEG, 3.0)
    pose = search(room, xs, ys, pose, 0.06, 0.01, 3.0, 0.5)
    x, y, heading = pose
    matched = float((wall_distance(room, *place(xs, ys, pose)) < MATCH_M).mean())
    status = "OK" if matched >= OK_MATCHED else "POOR"
    return {"x": float(x), "y": float(y), "heading": float(heading), "matched": matched,
            "status": status}
