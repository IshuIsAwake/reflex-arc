"""Maps a pretend room the way a person does in the map window. No hardware, no window.

    python test_mapping.py

Starts `pi/server.py --fake-world --fast`, then uses the map window's own background
worker (scan_view.Poller) and a second, driving connection -- as the arrow keys do --
to record home, switch mapping on, and drive the pretend rover round the room with
stops. Checks the views are added at the stops and not on the move, the map grows, the
rover still finds itself on it far from home, and the room check then reads the map.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_view          # noqa: E402
from link import RoverLink  # noqa: E402

PORT = 5011


def drive(link, left, right, secs, poller=None):
    """Hold wheel power for `secs`, sending it 20 times a second like the window does."""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        link.manual(left, right)
        if poller:
            poller.still_since = time.monotonic()
        time.sleep(0.05)
    link.manual(0, 0)


def wait_for(cond, secs):
    end = time.monotonic() + secs
    while time.monotonic() < end and not cond():
        time.sleep(0.1)
    return cond()


def main():
    server = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "..", "pi", "server.py"),
                               "--fake-world", "--fast", "--port", str(PORT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        time.sleep(2)
        p = scan_view.Poller("127.0.0.1", PORT)
        wheel = RoverLink("127.0.0.1", PORT)

        p.jobs.put(("home",))
        assert wait_for(lambda: p.ref is not None, 10), "home was not recorded"
        home_points = len(p.ref[0])
        p.mapping = True

        # A lap of the room's inside: north, west, south, east, with a stop after each leg.
        legs = [(0.5, 0.5, 2.5), (-0.5, 0.5, 1.2), (0.5, 0.5, 3.0), (-0.5, 0.5, 1.2),
                (0.5, 0.5, 2.5), (-0.5, 0.5, 1.2), (0.5, 0.5, 3.0)]
        added_moving = 0
        for left, right, secs in legs:
            before = p.views
            drive(wheel, left, right, secs, poller=p)
            added_moving += p.views - before        # anything added while it was moving
            wait_for(lambda: p.views > before, 6)   # stop: a view should come
        print(f"  views added at stops: {p.views}, while moving: {added_moving}")
        assert added_moving == 0, "a view was added while the rover was moving"
        assert p.views >= 4, f"only {p.views} views added on a lap of the room"
        assert len(p.ref[0]) > home_points, "the map did not grow"
        print(f"  map points: {home_points} at home -> {len(p.ref[0])} after the lap")

        # Drift: the pretend room's walls are known exactly, and the map frame is the room's
        # (home at the origin, facing +x), so every map point can be measured against them.
        sys.path.insert(0, os.path.join(HERE, "..", "pi"))
        import numpy as np
        from fake_world import ARENA
        mx, my = np.array(p.ref[0]) / 100, np.array(p.ref[1]) / 100
        off = np.full(mx.shape, np.inf)
        for (ax, ay), (bx, by) in ARENA:
            ex, ey = bx - ax, by - ay
            t = np.clip(((mx - ax) * ex + (my - ay) * ey) / (ex * ex + ey * ey), 0, 1)
            off = np.minimum(off, np.hypot(mx - (ax + t * ex), my - (ay + t * ey)))
        p95 = float(np.percentile(off, 95))
        print(f"  map vs the true walls: median {np.median(off) * 100:.1f} cm, "
              f"95 % within {p95 * 100:.1f} cm")
        assert p95 < 0.05, "the map drifted from the room"

        assert wait_for(lambda: p.fix is not None and p.fix["status"] == "OK", 5)
        print(f"  far from home it still locates: {p.fix['status']} x {p.fix['x']:+.2f} "
              f"y {p.fix['y']:+.2f}, matched {p.fix['matched']:.0%}")
        assert p.fix["matched"] >= 0.9

        p.jobs.put(("room", False))
        assert wait_for(lambda: p.room is not None, 10)
        print(f"  room check from {p.room['from']}: {p.room['status']}, cell {p.room.get('cell_m')}")
        assert p.room["from"] == "the room map" and p.room["status"] in ("OK", "CAPPED")
        wheel.close()
        p.link.close()
    finally:
        server.terminate()
        server.wait(timeout=5)
    print("all mapping checks passed")


if __name__ == "__main__":
    main()
