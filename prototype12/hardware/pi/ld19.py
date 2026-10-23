"""ld19 -- the LD19 LiDAR read straight off its serial port. No ROS.

    lidar = LD19()               # starts reading in the background
    scan = lidar.next_scan()     # a full 360 deg turn that began after this call
    xs, ys = scan.xy()           # points in the rover's frame, metres
    lidar.close()

The LD19 streams by itself as soon as it has power; nothing is ever sent to it.
230400 baud, 8N1, 47-byte packets (LD19 manual):

    0x54 0x2C | speed u16 deg/s | start u16 0.01deg | 12 x (dist u16 mm, intensity u8)
              | end u16 0.01deg | timestamp u16 ms | crc8

Little-endian. The 12 points are spread evenly from the start angle to the end angle,
which can wrap past 360. The CRC is CRC-8 with polynomial 0x4D over the first 46
bytes; a packet that fails it is dropped, never used. On this rover's LD19 that was
831 good packets and 0 failures in a 2 s read (23 Oct 2026).

A turn is complete when a packet's start angle comes round below the previous one's.

Rover frame, used everywhere above this file: x forward, y left, angles anticlockwise
from forward, in radians. The LD19's own angles run the other way (`C.LIDAR_CLOCKWISE`)
and its 0 deg may not face the rover's front (`C.LIDAR_OFFSET_DEG`). Both are applied
here, once, and nowhere else.

`next_scan` exists because a turn that started while the rover was still moving is
smeared across the motion. After a stop, ask for the next one, not the latest.
"""

import math
import struct
import threading
import time

import numpy as np

import config as C

HEADER, VERLEN, SIZE, POINTS = 0x54, 0x2C, 47, 12


def _crc_table(poly=0x4D):
    out = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        out.append(c)
    return out


_CRC = _crc_table()


def crc8(data):
    c = 0
    for b in data:
        c = _CRC[c ^ b]
    return c


def parse(buf):
    """Every whole packet in `buf`. Returns (packets, bad, rest): each packet is
    (start_deg, end_deg, speed_dps, [(dist_mm, intensity), ...12]); `bad` counts CRC
    failures; `rest` is the tail that may be the start of the next packet.
    """
    out, bad, i = [], 0, 0
    n = len(buf)
    while i + SIZE <= n:
        if buf[i] != HEADER or buf[i + 1] != VERLEN:
            i += 1
            continue
        pkt = buf[i:i + SIZE]
        if crc8(pkt[:SIZE - 1]) != pkt[SIZE - 1]:
            bad += 1
            i += 1            # a header byte inside a corrupt packet: resync from the next
            continue
        speed, start = struct.unpack_from("<HH", pkt, 2)
        end = struct.unpack_from("<H", pkt, 42)[0]
        pts = [struct.unpack_from("<HB", pkt, 6 + 3 * k) for k in range(POINTS)]
        out.append((start / 100.0, end / 100.0, speed, pts))
        i += SIZE
    return out, bad, buf[i:]


class Scan:
    """One full turn, filtered, in the rover frame."""

    def __init__(self, angle, rng, intensity, t_start, t_end, speed):
        self.angle = angle            # radians, anticlockwise from forward
        self.range = rng              # metres
        self.intensity = intensity
        self.t_start, self.t_end = t_start, t_end
        self.speed = speed            # deg/s the head was spinning

    def __len__(self):
        return len(self.range)

    def xy(self):
        return self.range * np.cos(self.angle), self.range * np.sin(self.angle)


class Assembler:
    """Packets in, full turns out."""

    def __init__(self):
        self.rows = []                # (ld19_deg, dist_mm, intensity)
        self.prev_start = None
        self.t_start = None
        self.speeds = []

    def feed(self, packet, now):
        """Add one packet. Returns a Scan if this packet began a new turn."""
        start, end, speed, pts = packet
        done = None
        if self.prev_start is not None and start < self.prev_start and self.rows:
            done = self._finish(now)
        if self.t_start is None:
            self.t_start = now
        self.prev_start = start
        self.speeds.append(speed)
        step = ((end - start) % 360.0) / (POINTS - 1)
        for k, (d, inten) in enumerate(pts):
            self.rows.append(((start + step * k) % 360.0, d, inten))
        return done

    def _finish(self, now):
        a = np.array([r[0] for r in self.rows], dtype=float)
        d = np.array([r[1] for r in self.rows], dtype=float) / 1000.0
        i = np.array([r[2] for r in self.rows], dtype=float)
        sign = -1.0 if C.LIDAR_CLOCKWISE else 1.0
        ang = np.radians(sign * a + C.LIDAR_OFFSET_DEG)
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        keep = (d >= C.LIDAR_MIN_M) & (d <= C.LIDAR_MAX_M) & (i >= C.LIDAR_MIN_INTENSITY)
        order = np.argsort(ang[keep])
        scan = Scan(ang[keep][order], d[keep][order], i[keep][order], self.t_start, now,
                    sum(self.speeds) / len(self.speeds))
        scan.raw_points = len(self.rows)
        self.rows, self.speeds, self.t_start = [], [], now
        return scan


class LD19:
    """Reads the port on its own thread and keeps the latest full turn."""

    def __init__(self, port=None, baud=None):
        import serial
        self.ser = serial.Serial(port or C.LIDAR_PORT, baud or C.LIDAR_BAUD, timeout=0.1)
        self.ser.reset_input_buffer()
        self.packets = self.crc_fail = self.turns = 0
        self._latest = None
        self._cv = threading.Condition()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asm, buf = Assembler(), b""
        first = True          # the first turn began wherever the head was: partial, dropped
        while not self._stop:
            try:
                buf += self.ser.read(2048)
            except Exception:         # unplugged: stop quietly, latest() goes stale
                break
            pkts, bad, buf = parse(buf)
            self.crc_fail += bad
            now = time.monotonic()
            for p in pkts:
                self.packets += 1
                scan = asm.feed(p, now)
                if scan is not None and first:
                    first = False
                elif scan is not None:
                    with self._cv:
                        self._latest = scan
                        self.turns += 1
                        self._cv.notify_all()

    def latest(self):
        """The most recent full turn, or None before the first one."""
        return self._latest

    def next_scan(self, timeout=1.0):
        """A full turn that started after this call. None if none arrives in time."""
        since = time.monotonic()
        deadline = since + timeout
        with self._cv:
            while True:
                s = self._latest
                if s is not None and s.t_start >= since:
                    return s
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._cv.wait(left)

    def close(self):
        self._stop = True
        self._thread.join(timeout=1)
        self.ser.close()


def open_lidar():
    """The LD19, or None (and why) if it is not there."""
    try:
        return LD19(), None
    except ImportError:
        return None, "pyserial not installed (sudo apt install python3-serial)"
    except Exception as e:
        return None, str(e)
