"""reference -- the picture of the room the rover locates itself against.

Recorded once per arena setup, with the rover standing still on its home spot facing
grid north. Home is the map frame's origin and its facing is the map's x axis, so this
is also the moment that defines where cell (0,0) is and which way is north.

A reference made from home alone covers what home can see. Far from home the rover
sees walls and box sides home never did, and those points simply fail to match --
`locate` stays honest, but its `matched` share drops. `add_view` fixes that: stand the
rover somewhere else, locate it against the reference so far, and fold in what it sees.
If anything in the arena moves, record the reference again.

Saved on the Pi as reference.npz, next to this file. It belongs to one room on one day,
so it is not committed.
"""

import os

import numpy as np

from locate import Reference, locate, transform

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference.npz")
TURNS = 10             # about a second at home, still; averaging out single-turn noise


def record_home(lidar, turns=TURNS):
    """A new reference from `turns` full scans at home. Returns (Reference, points used)."""
    xs, ys = [], []
    for _ in range(turns):
        s = lidar.next_scan(timeout=2.0)
        if s is None:
            raise RuntimeError("the LiDAR stopped sending full turns")
        x, y = s.xy()
        xs.append(x)
        ys.append(y)
    ref = Reference(np.concatenate(xs), np.concatenate(ys))
    return ref, len(ref.xs)


def add_view(ref, lidar, guess, min_matched=0.0):
    """Locate the rover against `ref` from `guess`, and if the fit is OK -- and at least
    `min_matched` of the scan already lines up with the map -- add what it sees there.
    Returns the locate result with "added"; the reference only changes when it is True.

    Mapping a room by driving (the map window's M) asks for 0.8: each view is added only
    where most of it already agrees with the map, so a slightly wrong fit cannot bend the
    map. Without loop closing a map built this way still drifts a little over a big
    room; this keeps that small, it does not remove it.
    """
    s = lidar.next_scan(timeout=2.0)
    if s is None:
        raise RuntimeError("the LiDAR stopped sending full turns")
    x, y = s.xy()
    res = locate(ref, x, y, guess)
    res["added"] = res["status"] == "OK" and res["matched"] >= min_matched
    if res["added"]:
        mx, my = transform(x, y, res["pose"])
        ref.add(mx, my)
    return res


def save(ref, path=None):
    np.savez_compressed(path or FILE, xs=ref.xs, ys=ref.ys)


def load(path=None):
    """The saved reference, or None if there is none yet."""
    path = path or FILE
    if not os.path.exists(path):
        return None
    d = np.load(path)
    return Reference(d["xs"], d["ys"])
