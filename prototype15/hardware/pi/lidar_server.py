"""The LiDAR's own server on the rover, beside server.py, which drives the motors. One laptop
at a time on port 5006, one JSON object a line, as with server.py.

    cd ~/p15 && python3 lidar_server.py

    {"op": "hello"}
        {"ok": true, "lidar": true, "note": "415 good packets in 1 s, ..."}
        "lidar" is false when the LD19 isn't plugged in, sends nothing, or pyserial is
        missing, and the note says which. Every hello looks again.
    {"op": "home"}
        the rover is on its home spot facing north: the room as seen from here is kept,
        and every locate is measured against it.
        {"ok": true, "points": 480}
    {"op": "locate", "x": 3, "y": -2, "heading": "E", "cell_m": 0.1}
        where the rover is, searched near the cell it should be on (cells counted from
        home, y growing south, as in LINK.md).
        {"ok": true, "status": "OK", "x": 3.1, "y": -1.8, "heading": 92.5, "matched": 0.84}
        x and y in cells, not rounded; heading in degrees clockwise from north (E = 90).
        status POOR means too few points landed on the walls to trust it.
    {"op": "ahead", "look_m": 0.35}
        is anything in the rover's way, straight ahead, within look_m of its front edge?
        {"ok": true, "clear_m": null}  or  {"ok": true, "clear_m": 0.21}"""

import json
import socket
import time

import lidar_config

try:
    import ld19
    import locate
except ImportError as e:
    ld19 = None  # pyserial or numpy is missing; hello says so
    missing = str(e)

port = None  # the LiDAR's serial port, opened by the first hello that finds it
room = None  # the home scan made into a grid, by "home"

COMPASS = {"N": 0, "E": 90, "S": 180, "W": 270}


def lidar_found():
    global port
    if ld19 is None:
        return False, f"{missing} on the Pi: sudo apt install python3-serial python3-numpy"
    if port is None:
        port, why = ld19.open_port()
        if port is None:
            return False, why
    return ld19.check(port, 1.0)


def full_turns(n):
    """The points of n full turns, together: a denser picture than one turn alone."""
    points = []
    for _ in range(n):
        turn = ld19.one_turn(port)
        if turn:
            points += turn
    return points


def home():
    global room
    if port is None:
        return {"ok": False, "note": "no LiDAR: send hello first"}
    start = time.monotonic()
    room = locate.make_room(full_turns(3))
    print(f"home recorded: {room['points']} points, {time.monotonic() - start:.1f} s")
    return {"ok": True, "points": room["points"]}


def where(msg):
    """locate: cells and compass in, the home frame's metres and angles to locate.py, and back."""
    if room is None:
        return {"ok": False, "note": "no home scan yet: send home first"}
    cell_m = msg["cell_m"]
    # home frame: x forward at home (north), y left at home (west), angles anticlockwise
    guess = (-msg["y"] * cell_m, -msg["x"] * cell_m, -COMPASS[msg["heading"]])
    start = time.monotonic()
    found = locate.locate(room, full_turns(1), guess)
    heading = -found["heading"] % 360
    print(f"locate: {found['status']} at ({-found['y'] / cell_m:.1f}, {-found['x'] / cell_m:.1f}) "
          f"heading {heading:.0f}, {found['matched']:.0%} on the walls, "
          f"{time.monotonic() - start:.1f} s")
    return {"ok": True, "status": found["status"], "x": -found["y"] / cell_m,
            "y": -found["x"] / cell_m, "heading": heading, "matched": found["matched"]}


def answer(line):
    global port
    try:
        msg = json.loads(line)
    except ValueError:
        return {"ok": False, "note": "not JSON"}
    try:
        if msg.get("op") == "hello":
            found, note = lidar_found()
            return {"ok": True, "lidar": found, "note": note}
        if msg.get("op") == "home":
            return home()
        if msg.get("op") == "locate":
            return where(msg)
        if msg.get("op") == "ahead":
            clear_m = locate.clear_ahead(full_turns(1), msg["look_m"])
            print(f"ahead {msg['look_m']:.2f} m: {'clear' if clear_m is None else f'{clear_m:.2f} m'}")
            return {"ok": True, "clear_m": clear_m}
    except OSError as e:
        port = None  # unplugged mid-run; the next hello opens it again
        return {"ok": False, "note": f"the LiDAR stopped answering: {e}"}
    return {"ok": False, "note": f"unknown op {msg.get('op')!r}"}


def serve(conn):
    """One laptop, until it goes."""
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    conn.sendall((json.dumps(answer(line)) + "\n").encode())
    except OSError:
        return  # the laptop dropped


def main():
    found, note = lidar_found()
    if found:
        print(f"LiDAR found: {note}")
    else:
        print(f"no LiDAR: {note}")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", lidar_config.SERVER_PORT))
    srv.listen(1)
    print(f"lidar server listening on port {lidar_config.SERVER_PORT}. Ctrl-C to quit.")
    try:
        while True:
            conn, addr = srv.accept()
            print(f"laptop connected from {addr[0]}")
            serve(conn)
            conn.close()
            print("laptop disconnected")
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


if __name__ == "__main__":
    main()
