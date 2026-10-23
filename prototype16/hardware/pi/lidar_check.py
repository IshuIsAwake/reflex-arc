"""Check the LD19 on the Pi: is it there, is the data good, which way is "forward".

    python3 lidar_check.py            20 turns (2 s), then a summary
    python3 lidar_check.py --watch    the nearest thing's direction, live, every turn
    python3 lidar_check.py --mount    guided: sets the direction and offset, and marks the
                                      mounting checked -- needed before any checked drive

Stop the rover server first (it holds the port): `pkill -f server.py`.

The summary is the health check: turn rate (about 10 Hz), points per turn (about 500
on this rover), CRC failures (should be 0), and the spread of intensities, which is
what `C.LIDAR_MIN_INTENSITY` would be set from.

--watch checks the mounting. Hold a hand or a box 20-40 cm from the rover:
    straight in front   -> about   0 deg
    on its left side    -> about +90 deg
    on its right side   -> about -90 deg
If left and right are swapped, LIDAR_CLOCKWISE is the wrong way round. If "in front"
reads some other angle, that angle is LIDAR_OFFSET_DEG's error: add it to the offset.
Both live in config.py; `--save-offset DEG` writes the offset to calib.json.
"""

import argparse
import math
import sys
import time

import numpy as np

import config as C
from ld19 import open_lidar


def nearest(scan, max_m=1.0):
    """Direction and distance of the nearest thing within `max_m`, from the median of
    its closest few points so one stray return does not decide it."""
    near = scan.range < max_m
    if not near.any():
        return None
    idx = np.argsort(scan.range)[:5]
    ang = math.degrees(math.atan2(np.sin(scan.angle[idx]).mean(), np.cos(scan.angle[idx]).mean()))
    return ang, float(np.median(scan.range[idx]))


def bins(scan):
    """Nearest range in each 1-degree bin of a scan, inf where nothing came back."""
    out = np.full(360, np.inf)
    b = np.floor(np.degrees(scan.angle)).astype(int) % 360
    np.minimum.at(out, b, scan.range)
    return out


def appeared(base, scan, closer=0.08, within=0.8):
    """Direction of the nearest new thing in `scan` against `base` (from `bins`): of the
    points at least `closer` metres nearer than the room was there, and within `within`,
    the ones within 10 cm and 25 deg of the nearest. The person holding the object is
    new too, and bigger -- on 23 Oct they outweighed the hand; the hand is nearer.
    None if fewer than 3 such points."""
    b = np.floor(np.degrees(scan.angle)).astype(int) % 360
    new = (scan.range < base[b] - closer) & (scan.range < within)
    if new.sum() < 3:
        return None
    a, r = scan.angle[new], scan.range[new]
    k = int(np.argmin(r))
    gap = np.degrees(np.abs((a - a[k] + math.pi) % (2 * math.pi) - math.pi))
    near = (r < r[k] + 0.10) & (gap < 25)
    if near.sum() < 3:
        return None
    return math.degrees(math.atan2(np.sin(a[near]).mean(), np.cos(a[near]).mean()))


def mount(lidar):
    """Two readings of one object -- in front, then on the left -- give both settings.

    The room is recorded first with nothing held, and each reading is only what
    *appeared* since, so walls, furniture or the box the rover stands on do not count --
    on 23 Oct the nearest-thing version read a wall 34 cm away, twice.

    Rover angle = s * raw + offset, with s = -1 when the LD19 runs clockwise. In front
    must read 0 and on the left +90. If left came out at -90 the direction is the wrong
    way round; the offset is then whatever puts "in front" at 0.
    """
    input("\nNothing held near the rover; stand back a little so the room is recorded "
          "without you in it. Press Enter.")
    base = np.full(360, np.inf)
    for _ in range(5):
        s = lidar.next_scan(timeout=2)
        if s is not None:
            base = np.minimum(base, bins(s))

    def look(where):
        input(f"\nHold a box or your hand {where}, 15-30 cm from the rover, at the height of "
              f"the LiDAR's spinning head. Press Enter.")
        got = []
        for _ in range(5):
            s = lidar.next_scan(timeout=2)
            a = appeared(base, s) if s is not None else None
            if a is not None:
                got.append(a)
        if len(got) < 3:
            sys.exit("nothing new appeared -- hold it closer than whatever is already on that "
                     "side, and at the head's height; then try again")
        a = math.degrees(math.atan2(np.mean(np.sin(np.radians(got))), np.mean(np.cos(np.radians(got)))))
        print(f"  seen at {a:+.0f} deg")
        return a

    front = look("STRAIGHT IN FRONT")
    left = look("on its LEFT side")
    got = mount_settings(front, left, C.LIDAR_CLOCKWISE, C.LIDAR_OFFSET_DEG)
    if got is None:
        sys.exit(f"front to left read {(left - front + 180) % 360 - 180:+.0f} deg, not about "
                 f"+-90 -- nothing saved; try again")
    clockwise, offset = got
    C.save(LIDAR_CLOCKWISE=clockwise, LIDAR_OFFSET_DEG=offset, LIDAR_MOUNT_CHECKED=True)
    print(f"\nsaved to calib.json: LIDAR_CLOCKWISE={clockwise}, LIDAR_OFFSET_DEG={offset}, "
          f"mounting checked.\nRestart the server, and record home again: the old reference "
          f"was made with the old settings.")


def mount_settings(front, left, clockwise, offset):
    """(clockwise, offset) that put `front` at 0 and `left` at +90, from two angles read
    with the current settings. None if the two readings are not about 90 deg apart."""
    turn = (left - front + 180) % 360 - 180
    old = -1.0 if clockwise else 1.0
    if 60 <= turn <= 120:
        sign = old                      # the direction was right
    elif -120 <= turn <= -60:
        sign = -old                     # mirrored: flip it
    else:
        return None
    raw = (front - offset) / old        # what the LD19 itself said for "in front"
    return sign < 0, round((-sign * raw + 180) % 360 - 180, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--mount", action="store_true")
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--save-offset", type=float, metavar="DEG",
                    help="write LIDAR_OFFSET_DEG to calib.json and stop")
    args = ap.parse_args()

    if args.save_offset is not None:
        C.save(LIDAR_OFFSET_DEG=args.save_offset)
        print(f"LIDAR_OFFSET_DEG = {args.save_offset} saved to calib.json")
        return

    lidar, why = open_lidar()
    if lidar is None:
        sys.exit(f"no LiDAR: {why}\nIs it plugged in, and is the rover server stopped?")
    print(f"LD19 on {C.LIDAR_PORT}  (clockwise={C.LIDAR_CLOCKWISE}, offset={C.LIDAR_OFFSET_DEG} deg)")

    try:
        if args.mount:
            mount(lidar)
            return
        if args.watch:
            print("nearest thing within 1 m -- Ctrl-C to stop")
            while True:
                s = lidar.next_scan(timeout=2)
                if s is None:
                    print("  no turn for 2 s -- is it spinning?")
                    continue
                n = nearest(s)
                print("  nothing within 1 m" if n is None else
                      f"  {n[0]:+6.0f} deg   {n[1]:.2f} m   ({len(s)} points)", flush=True)

        # next_scan waits for a turn that *starts* after the call, so collecting with it
        # takes every other turn. The rate comes from the reader's own count instead.
        scans, t0, n0 = [], time.monotonic(), lidar.turns
        while len(scans) < args.turns and time.monotonic() - t0 < args.turns * 0.3 + 2:
            s = lidar.next_scan(timeout=2)
            if s is not None:
                scans.append(s)
        dt, turned = time.monotonic() - t0, lidar.turns - n0
        if not scans:
            sys.exit("no full turns arrived")
        kept = [len(s) for s in scans]
        raw = [s.raw_points for s in scans]
        inten = np.concatenate([s.intensity for s in scans])
        print(f"  turns          {turned} in {dt:.1f} s  ({turned / dt:.1f} Hz, "
              f"head {np.mean([s.speed for s in scans]) / 360:.1f} rev/s)")
        print(f"  points/turn    {np.mean(raw):.0f} raw, {np.mean(kept):.0f} kept "
              f"({C.LIDAR_MIN_M}-{C.LIDAR_MAX_M} m, intensity >= {C.LIDAR_MIN_INTENSITY})")
        print(f"  packets        {lidar.packets} ok, {lidar.crc_fail} CRC failures")
        print(f"  intensity      p5 {np.percentile(inten, 5):.0f}  p50 {np.percentile(inten, 50):.0f}"
              f"  p95 {np.percentile(inten, 95):.0f}")
        s = scans[-1]
        print("  last turn, nearest per direction (rover frame, 0 = forward, + = left):")
        for lo in range(-180, 180, 45):
            sel = (np.degrees(s.angle) >= lo) & (np.degrees(s.angle) < lo + 45)
            if sel.any():
                print(f"    {lo:+4d}..{lo + 45:+4d} deg   {s.range[sel].min():5.2f} m   n={sel.sum()}")
    except KeyboardInterrupt:
        pass
    finally:
        lidar.close()


if __name__ == "__main__":
    main()
