"""Checks the LD19 reader against packets built by hand. No LiDAR needed.

    python test_lidar.py

A rover sits in a 4 m x 3 m room; packets are made the way the LD19 makes them
(clockwise angles, mm, CRC-8), fed in with junk and one corrupted packet between them,
and every point that comes out must land on a wall. If the clockwise flip or the
angle spread inside a packet were wrong, the points would land off the walls.
"""

import math
import struct

import numpy as np

import config as C
import ld19

ROOM = (-1.5, 2.5, -1.0, 2.0)          # x0, x1, y0, y1 in metres; rover at the origin


def wall_distance(theta):
    """From (0,0) along rover-frame angle theta to the room's walls, metres."""
    x0, x1, y0, y1 = ROOM
    c, s = math.cos(theta), math.sin(theta)
    best = 1e9
    for edge, comp in ((x1, c), (x0, c)):
        if abs(comp) > 1e-9 and (edge / comp) > 0:
            best = min(best, edge / comp)
    for edge, comp in ((y1, s), (y0, s)):
        if abs(comp) > 1e-9 and (edge / comp) > 0:
            best = min(best, edge / comp)
    return best


def packet(start_deg, end_deg, speed=3600):
    span = ((end_deg - start_deg) % 360.0) / 11
    body = struct.pack("<BBHH", ld19.HEADER, ld19.VERLEN, speed, int(round(start_deg * 100)))
    for k in range(12):
        a = (start_deg + span * k) % 360.0
        theta = -math.radians(a)                 # LD19 is clockwise
        body += struct.pack("<HB", int(round(wall_distance(theta) * 1000)), 200)
    body += struct.pack("<HH", int(round(end_deg * 100)) % 36000, 1234)
    return body + bytes([ld19.crc8(body)])


def stream(turns=3, per_turn=42):
    out = b"\x00\x54\x13junk"                    # garbage, including a stray header byte
    step = 360.0 / per_turn
    for n in range(turns * per_turn):
        start = (n * step) % 360.0
        out += packet(start, (start + step * 11 / 12) % 360.0)
        if n == 5:
            bad = bytearray(packet(0.0, 8.0))
            bad[10] ^= 0xFF                      # corrupt one point: CRC must catch it
            out += bytes(bad)
    return out


def test_crc_matches_the_ld19_polynomial():
    assert ld19.crc8(b"") == 0
    t = ld19._crc_table()
    assert t[1] == 0x4D and len(set(t)) == 256


def test_parse_drops_junk_and_bad_packets():
    pkts, bad, rest = ld19.parse(stream(turns=1))
    assert bad == 1, f"the corrupted packet was not caught ({bad})"
    assert len(pkts) == 42
    assert len(rest) < ld19.SIZE


def test_a_full_turn_lands_on_the_walls():
    keep = C.LIDAR_CLOCKWISE, C.LIDAR_OFFSET_DEG, C.LIDAR_MIN_M
    C.LIDAR_CLOCKWISE, C.LIDAR_OFFSET_DEG, C.LIDAR_MIN_M = True, 0.0, 0.15
    try:
        pkts, _, _ = ld19.parse(stream(turns=3))
        asm, scans = ld19.Assembler(), []
        for i, p in enumerate(pkts):
            s = asm.feed(p, float(i))
            if s is not None:
                scans.append(s)
        assert len(scans) == 2, f"expected 2 closed turns, got {len(scans)}"
        s = scans[1]
        assert len(s) == 42 * 12
        x, y = s.xy()
        x0, x1, y0, y1 = ROOM
        off = np.minimum.reduce([abs(x - x0), abs(x - x1), abs(y - y0), abs(y - y1)])
        assert off.max() < 0.003, f"a point is {off.max():.3f} m off the walls"
        # anticlockwise and sorted: angles rise through the turn
        assert np.all(np.diff(s.angle) >= 0)
    finally:
        C.LIDAR_CLOCKWISE, C.LIDAR_OFFSET_DEG, C.LIDAR_MIN_M = keep


def test_offset_turns_the_whole_scan():
    keep = C.LIDAR_OFFSET_DEG
    C.LIDAR_OFFSET_DEG = 90.0
    try:
        pkts, _, _ = ld19.parse(stream(turns=2))
        asm = ld19.Assembler()
        scans = [s for i, p in enumerate(pkts) if (s := asm.feed(p, float(i))) is not None]
        x, y = scans[0].xy()
        # turned 90 anticlockwise, the room's +x wall (2.5 m ahead) is now on the left
        x0, x1, y0, y1 = ROOM
        on = np.minimum.reduce([abs(y - x1), abs(y - x0), abs(-x - y1), abs(-x - y0)])
        assert on.max() < 0.003
    finally:
        C.LIDAR_OFFSET_DEG = keep


def test_close_points_are_dropped():
    keep = C.LIDAR_MIN_M
    C.LIDAR_MIN_M = 1.2                          # the walls 1.0 m away must disappear
    try:
        pkts, _, _ = ld19.parse(stream(turns=2))
        asm = ld19.Assembler()
        s = next(s for i, p in enumerate(pkts) if (s := asm.feed(p, float(i))) is not None)
        assert s.range.min() >= 1.2
    finally:
        C.LIDAR_MIN_M = keep


def test_mount_settings_put_front_at_0_and_left_at_90():
    from lidar_check import mount_settings

    # The model ld19.py uses: rover angle = s * raw + offset, s = -1 when clockwise.
    def reads(raw, clockwise, offset):
        return ((-raw if clockwise else raw) + offset + 180) % 360 - 180

    # Real mountings: the LD19's own 0 at some angle, turning one way or the other.
    # Inverting the model: an object at rover angle a gives raw = (a - offset) * s.
    for true_cw in (True, False):
        s = -1 if true_cw else 1
        for true_off in (0.0, 37.0, -90.0, 180.0):
            raw_front = ((0 - true_off) * s) % 360
            raw_left = ((90 - true_off) * s) % 360
            for cur_cw, cur_off in ((True, 0.0), (False, 15.0)):   # whatever config says now
                got = mount_settings(reads(raw_front, cur_cw, cur_off),
                                     reads(raw_left, cur_cw, cur_off), cur_cw, cur_off)
                assert got is not None
                cw, off = got
                assert abs(reads(raw_front, cw, off)) < 0.2, (true_cw, true_off, got)
                assert abs(reads(raw_left, cw, off) - 90) < 0.2, (true_cw, true_off, got)
    assert mount_settings(0.0, 170.0, True, 0.0) is None     # not a quarter turn: refuse


def test_mount_sees_what_appeared_not_what_was_there():
    """A wall 34 cm away on the front-left (23 Oct's reading) and a hand 20 cm in front:
    the hand must win, though the wall is in sight the whole time."""
    from lidar_check import appeared, bins
    ang = np.radians(np.arange(-180, 180, 0.72))

    def scan(hand, person=None):
        r = np.full(ang.shape, 3.0)
        r[(np.degrees(ang) > 40) & (np.degrees(ang) < 90)] = 0.34     # the wall, front-left
        if person is not None:                                         # whoever holds it:
            r[np.abs(np.degrees(ang) - person) < 30] = 0.50            # big, and further out
        if hand is not None:
            r[np.abs(np.degrees(ang) - hand) < 6] = 0.20               # a hand
        return ld19.Scan(ang, r, np.full(ang.shape, 200.0), 0, 0, 3600)

    base = bins(scan(None))
    assert appeared(base, scan(None)) is None, "the room itself counted as new"
    assert abs(appeared(base, scan(0.0))) < 2
    assert abs(appeared(base, scan(90.0)) - 90) < 2
    # 23 Oct, second try: the person stood at -90 while holding the hand out in front
    assert abs(appeared(base, scan(0.0, person=-90))) < 2, "the person outweighed the hand"
    assert abs(appeared(base, scan(90.0, person=-135)) - 90) < 2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all lidar checks passed")
