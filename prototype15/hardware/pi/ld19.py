"""The LD19 LiDAR, read straight off its USB serial port. No ROS.

The LD19 sends by itself as soon as it has power; nothing is ever sent to it. 230400 baud,
47-byte packets (LD19 manual), little-endian:

    0x54 0x2C | speed u16 deg/s | start angle u16 0.01 deg | 12 x (distance u16 mm, intensity u8)
              | end angle u16 0.01 deg | timestamp u16 ms | crc8

A packet whose CRC is wrong is dropped. Angles handed out by this file are the rover's:
degrees anticlockwise from straight ahead, -180 to 180."""

import struct
import time

import serial

import lidar_config

PACKET_SIZE = 47
POINTS = 12


def make_crc_table():
    # CRC-8 with polynomial 0x4D, worked out once for every byte value
    table = []
    for value in range(256):
        crc = value
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x4D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
        table.append(crc)
    return table


CRC_TABLE = make_crc_table()


def crc8(data):
    crc = 0
    for byte in data:
        crc = CRC_TABLE[crc ^ byte]
    return crc


def parse(buf):
    """buf: bytes from the port. Returns (packets, bad, rest). Each packet is a dict with its
    speed, start and end angles and 12 (distance_mm, intensity) points; bad counts CRC
    failures; rest is an unfinished packet at the end, to go in front of the next read."""
    packets = []
    bad = 0
    i = 0
    while i + PACKET_SIZE <= len(buf):
        if buf[i] != 0x54 or buf[i + 1] != 0x2C:
            i += 1
            continue
        packet = buf[i:i + PACKET_SIZE]
        if crc8(packet[:46]) != packet[46]:
            bad += 1
            i += 1  # the header was junk, or the packet was damaged: look from the next byte
            continue
        speed, start = struct.unpack_from("<HH", packet, 2)
        end = struct.unpack_from("<H", packet, 42)[0]
        points = []
        for k in range(POINTS):
            points.append(struct.unpack_from("<HB", packet, 6 + 3 * k))
        packets.append({"speed": speed, "start": start / 100, "end": end / 100, "points": points})
        i += PACKET_SIZE
    return packets, bad, buf[i:]


def open_port():
    """The LiDAR's serial port, or None and why it would not open."""
    try:
        return serial.Serial(lidar_config.SERIAL_PORT, lidar_config.BAUD, timeout=0.1), None
    except serial.SerialException as e:
        return None, f"cannot open the LiDAR's port; is it plugged in? ({e})"


def read(port, seconds):
    """Every good packet that arrives in the next `seconds`, and how many failed their CRC."""
    port.reset_input_buffer()  # what is waiting was sent before now; only fresh data counts
    packets = []
    bad = 0
    rest = b""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        new, failed, rest = parse(rest + port.read(1024))
        packets += new
        bad += failed
    return packets, bad


def turns_a_second(packets):
    speed = 0
    for p in packets:
        speed += p["speed"]
    return speed / len(packets) / 360  # the speed is in degrees a second


def check(port, seconds=1.0):
    """Is the LD19 on this open port sending good data? Returns (True or False, a line
    saying why)."""
    packets, bad = read(port, seconds)
    if not packets:
        return False, f"its port is there but nothing good came in {seconds} s; is it spinning?"
    turns = turns_a_second(packets)
    return True, (f"{len(packets)} good packets in {seconds} s, {bad} CRC failures, "
                  f"{turns:.1f} turns a second")


def rover_angle(lidar_deg):
    """An LD19 angle -> the rover's: anticlockwise from straight ahead, -180 to 180."""
    if lidar_config.CLOCKWISE:
        angle = -lidar_deg + lidar_config.OFFSET_DEG
    else:
        angle = lidar_deg + lidar_config.OFFSET_DEG
    return (angle + 180) % 360 - 180


def points(packets):
    """The packets' points as (angle_deg, distance_m), in the rover's frame. Points closer than
    MIN_M or past MAX_M are dropped; so is 0, which the LD19 sends when nothing came back."""
    out = []
    for p in packets:
        # the 12 points are spread evenly from start to end, and end can wrap past 360
        step = ((p["end"] - p["start"]) % 360) / (POINTS - 1)
        for k in range(POINTS):
            metres = p["points"][k][0] / 1000
            if lidar_config.MIN_M <= metres <= lidar_config.MAX_M:
                out.append((rover_angle(p["start"] + step * k), metres))
    return out


def one_turn(port):
    """The points of one full turn that started after this call, or None. A turn ends where
    a packet's start angle comes round lower than the one before it."""
    packets, _ = read(port, 0.25)  # a turn takes about 0.1 s, so this holds two whole ones
    wraps = []
    for i in range(1, len(packets)):
        if packets[i]["start"] < packets[i - 1]["start"]:
            wraps.append(i)
    if len(wraps) < 2:
        return None
    return points(packets[wraps[0]:wraps[1]])
