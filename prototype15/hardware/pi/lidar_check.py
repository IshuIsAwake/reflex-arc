"""Check the LD19 on the Pi: is it there, is its data good, and which way is forward.

    python3 lidar_check.py           2 s of data, then a summary
    python3 lidar_check.py --watch   the nearest thing's direction, twice a second (Ctrl-C ends)

Stop lidar_server.py first: two programs reading the port at once each get half the bytes.

--watch checks how the LiDAR is mounted. Hold a hand or a box 20-40 cm from the rover:
    straight in front   about 0 deg
    on its left         about +90 deg
    on its right        about -90 deg
If left and right come out swapped, flip CLOCKWISE in lidar_config.py. If straight in front
reads some other angle, take that angle away from OFFSET_DEG there."""

import sys
import time

import ld19


def nearest(points):
    """The closest (angle_deg, distance_m) of a list of them."""
    best = points[0]
    for p in points:
        if p[1] < best[1]:
            best = p
    return best


def summary():
    port, why = ld19.open_port()
    if port is None:
        print(why)
        return
    packets, bad = ld19.read(port, 2.0)
    port.close()
    if not packets:
        print("nothing good came from the LiDAR in 2 s. Is it plugged in and spinning?")
        return
    turns = ld19.turns_a_second(packets)
    points = ld19.points(packets)
    print(f"good packets:   {len(packets)} in 2 s")
    print(f"CRC failures:   {bad}  (should be 0)")
    print(f"turns a second: {turns:.1f}  (about 10 is right)")
    print(f"points a turn:  about {round(len(packets) * ld19.POINTS / 2 / turns)}")
    if points:
        angle, metres = nearest(points)
        print(f"nearest thing:  {metres:.2f} m at {angle:+.0f} deg")


def watch():
    port, why = ld19.open_port()
    if port is None:
        print(why)
        return
    try:
        while True:
            turn = ld19.one_turn(port)
            if turn:
                angle, metres = nearest(turn)
                print(f"nearest: {metres:.2f} m at {angle:+4.0f} deg")
            else:
                print("no full turn came in; is it spinning?")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        port.close()


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        summary()
