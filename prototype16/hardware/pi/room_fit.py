"""room_fit -- the nearest wall sets the size of the game's map in this room.

    python3 room_fit.py           measure from here (server stopped), print the answer
    python3 room_fit.py --save    ...and save the cell size

Also from the LiDAR map window, key R, with the server running. Either way the rover is
on its home spot facing north, the way the game's map is laid over the room.

One number decides it: how far the nearest wall (or anything else) is from home. The
game's map is 30 x 30 cells with home in the middle, so

    map side = 2 x (nearest wall - MARGIN_M)        cell = map side / 30

The distance is taken along the grid, max(|x|, |y|): the map is a square, and its
corners reach further than its sides, so a box near a corner counts as close as it
really is to the square. Facing a wall, it is just the distance to that wall.

Kept between MIN_SIDE_M (3 m, cells of 0.1 m) -- smaller says "clear the map" and
saves nothing -- and MAX_SIDE_M (10 m, 0.33 m cells), the cap for a big room.

The LiDAR sees one flat slice at its own height: a low box or the feet of a chair
under it are not in the answer. Look at the floor as well.
"""

import argparse
import math
import sys

import numpy as np

CELLS = 30            # the game's 30 x 30 arena
MIN_SIDE_M = 3.0      # the smallest map: 0.1 m cells
MAX_SIDE_M = 10.0     # the cap: 0.33 m cells
MARGIN_M = 0.4        # half the rover's 0.31 m length, its turn at the edge, a little slip


def fit(xs, ys, cells=CELLS):
    """Points in the home frame (x north, y west, metres, home at 0,0) -> the answer."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    keep = np.hypot(xs, ys) > 0.15                    # the rover's own body
    xs, ys = xs[keep], ys[keep]
    if len(xs) < 20:
        return {"status": "NO_DATA", "message": "the LiDAR saw almost nothing; is it spinning?"}
    grid_dist = np.maximum(np.abs(xs), np.abs(ys))
    i = int(np.argmin(grid_dist))
    nearest = float(grid_dist[i])
    where = _direction(xs[i], ys[i])
    side = 2 * (nearest - MARGIN_M)
    out = {"nearest_m": round(nearest, 2), "nearest_dir": where}
    if side < MIN_SIDE_M:
        need = MIN_SIDE_M / 2 + MARGIN_M
        out.update(status="TOO_SMALL", cell_m=None, map_m=None, message=(
            f"clear the map: the nearest wall or object is {nearest:.2f} m away ({where}); "
            f"the game needs {need:.1f} m clear all round home ({MIN_SIDE_M:.0f} m of map, "
            f"{MARGIN_M} m to spare)."))
        return out
    status = "OK"
    if side > MAX_SIDE_M:
        side, status = MAX_SIDE_M, "CAPPED"
    cell = round(side / cells, 3)
    out.update(status=status, cell_m=cell, map_m=round(cell * cells, 2), message=(
        f"nearest wall {nearest:.2f} m ({where}): the map is {cell * cells:.1f} m x "
        f"{cell * cells:.1f} m, cells of {cell:.2f} m"
        + (" (capped at 10 m)" if status == "CAPPED" else "")))
    return out


def _direction(x, y):
    """Compass word for a point in the home frame (x north, y west)."""
    a = math.degrees(math.atan2(y, x))                  # 0 = north, +90 = west
    names = ["north", "north-west", "west", "south-west", "south", "south-east", "east",
             "north-east"]
    return names[int(((a % 360) + 22.5) // 45) % 8]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--save", action="store_true", help="save the cell size")
    args = ap.parse_args()

    import config as C
    from ld19 import open_lidar
    lidar, why = open_lidar()
    if lidar is None:
        sys.exit(f"no LiDAR: {why}\nIs the rover server stopped? (pkill -f server.py)")
    xs, ys = [], []
    try:
        for _ in range(10):
            s = lidar.next_scan(timeout=2)
            if s is not None:
                x, y = s.xy()
                xs.append(x)
                ys.append(y)
    finally:
        lidar.close()
    r = fit(np.concatenate(xs), np.concatenate(ys)) if xs else {"status": "NO_DATA",
                                                                 "message": "no full turns"}
    print(f"  {r['status']}: {r['message']}")
    if args.save and r.get("cell_m"):
        C.save(CELL_M=r["cell_m"])
        print(f"  saved CELL_M = {r['cell_m']}"
              + (f"; a cell now takes {C.FORWARD_S_PER_CELL} s" if C.FORWARD_M_PER_S else
                 "; run calibrate.py forward so a cell takes the right time"))


if __name__ == "__main__":
    main()
