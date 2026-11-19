"""The rover's end of the link. Runs on the Pi; the laptop's windows connect to it.

    python3 server.py                 real motors, port 5005
    python3 server.py --fake          prints instead (also runs on the laptop, for testing)
    python3 server.py --fake --fast   and skips the waiting

Every message, both ways, is in ../LINK.md. The pose is dead-reckoned: what the timings
claim, measured by nothing."""

import argparse
import json
import socket
import threading
import time

import config
import grid
import moves
from motors import open_motors

MANUAL_DEADMAN_S = 0.4  # the pad repeats every 50 ms while a stick or key is held


def groups(prims):
    """['R','F','F','F','L','F'] -> [('R',1),('F',3),('L',1),('F',1)]. Forward runs merge
    into one pulse; turns stay single, so each quarter turn settles on its own."""
    out = []
    for p in prims:
        if out and out[-1][0] == p and p in "FB":
            out[-1] = (p, out[-1][1] + 1)
        else:
            out.append((p, 1))
    return out


def expand(cmds, heading):
    """Every command as motor moves (F B L R), each worked out against the heading the rover
    will have by then. Returns the moves, and {move index: command index} for the last move
    of each command."""
    flat = []
    ends = {}
    for k, cmd in enumerate(cmds):
        flat += grid.primitives(cmd, heading)
        ends[len(flat) - 1] = k
        heading = grid.apply(grid.Pose(0, 0, heading), cmd).heading
    return flat, ends


class Rover:
    """The rover's state, shared by every window's connection."""

    def __init__(self, motors):
        self.motors = motors
        self.pose = grid.Pose(0, 0, 0)
        self.lock = threading.Lock()  # one drive at a time
        self.abort = threading.Event()  # set by a stop: the drive in progress ends
        self.manual_at = 0.0  # time of the last manual command; 0 = not driving by hand
        self.owner = None  # the window whose drive or hand is on the wheels
        threading.Thread(target=self.watchdog, daemon=True).start()

    def manual(self, left, right, who):
        """Wheel power from the control pad. Ignored while a drive runs. It moves the rover
        without the grid knowing, so the pose is wrong until a reset."""
        if self.lock.locked():
            return
        self.motors.set(max(-1.0, min(1.0, left)), max(-1.0, min(1.0, right)))
        if left or right:
            self.manual_at = time.monotonic()
            self.owner = who
        else:
            self.manual_at = 0.0

    def watchdog(self):
        """A pad that goes quiet (closed, crashed, wifi gone) stops the wheels."""
        while True:
            time.sleep(0.05)
            if self.manual_at and time.monotonic() - self.manual_at > MANUAL_DEADMAN_S:
                self.manual_at = 0.0
                if not self.lock.locked():
                    self.motors.stop()

    def drive(self, msg, send, who):
        """One drive message: every command in it, a step message after each, then done."""
        did = msg.get("id")
        if not self.lock.acquire(blocking=False):
            send({"event": "done", "id": did, "result": "BUSY", "pose": grid.to_json(self.pose)})
            return
        try:
            self.abort.clear()
            self.owner = who
            cmds = grid.parse(" ".join(msg.get("cmds", [])))
            result = self.run(did, cmds, send)
            send({"event": "done", "id": did, "result": result, "pose": grid.to_json(self.pose)})
        except ValueError as e:
            send({"event": "done", "id": did, "result": "REFUSED", "note": str(e),
                  "pose": grid.to_json(self.pose)})
        finally:
            self.motors.stop()
            self.lock.release()

    def run(self, did, cmds, send):
        """Drive the commands. Runs of F (or B) go as one pulse even across commands, so the
        game's "E E E E" from facing north is one turn and one four-cell pulse. Returns DONE,
        or STOPPED if a stop came in."""
        flat, ends = expand(cmds, self.pose.heading)
        n = 0
        here = self.pose
        for prim, count in groups(flat):
            moves.do(self.motors, prim, stop_check=self.abort.is_set, n=count)
            if self.abort.is_set():
                return "STOPPED"  # the pose is a guess: it stopped mid-move
            for m in range(n, n + count):
                here = grid.apply(here, prim)
                if m in ends:
                    send({"event": "step", "id": did, "i": ends[m] + 1,
                          "cmd": cmds[ends[m]], "pose": grid.to_json(here)})
            n += count
            self.pose = here
        return "DONE"


def answer(msg, rover, fake, who, send, workers):
    """One message from a window."""
    op = msg.get("op")
    if op == "hello":
        send({"ok": True, "pose": grid.to_json(rover.pose), "fake": fake,
              "forward_s": config.FORWARD_S_PER_CELL, "turn_s": config.TURN_S_PER_90,
              "cell_m": config.CELL_M})
    elif op == "reset":
        heading = grid.HEADING_NAMES.index(msg.get("heading", "N"))
        rover.pose = grid.Pose(0, 0, heading)
        send({"ok": True, "pose": grid.to_json(rover.pose)})
    elif op == "set_pose":
        heading = grid.HEADING_NAMES.index(msg.get("heading", "N"))
        rover.pose = grid.Pose(int(msg["x"]), int(msg["y"]), heading)
        send({"ok": True, "pose": grid.to_json(rover.pose)})
    elif op == "stop":
        rover.abort.set()
        rover.motors.stop()
        send({"ok": True, "note": "stopped"})
    elif op == "manual":  # no reply: it repeats 20 times a second
        rover.manual(float(msg.get("left", 0)), float(msg.get("right", 0)), who)
    elif op == "drive":
        # On its own thread, so this window can still send a stop while it drives.
        t = threading.Thread(target=rover.drive, args=(msg, send, who), daemon=True)
        t.start()
        workers.append(t)
    else:
        send({"ok": False, "note": f"unknown op {op!r}"})


def serve(conn, rover, fake, who):
    """One laptop window, until it goes. Only the window whose drive or hand is on the
    wheels stops them when it goes, so closing the pad never stops the game's drive."""
    out_lock = threading.Lock()  # a drive's thread and this one both send

    def send(obj):
        with out_lock:
            conn.sendall((json.dumps(obj) + "\n").encode())

    workers = []
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    send({"ok": False, "note": "not JSON"})
                    continue
                try:
                    answer(msg, rover, fake, who, send, workers)
                except (ValueError, KeyError, TypeError) as e:
                    # A heading that isn't N E S W, or a missing x: say so, and keep the window.
                    send({"ok": False, "note": f"bad message: {e!r}"})
    except OSError:
        pass
    finally:
        if rover.owner == who:  # this window was driving: whatever it moved stops
            rover.abort.set()
            rover.manual_at = 0.0
            rover.motors.stop()
            rover.owner = None
        for t in workers:
            t.join(timeout=2)


def main():
    ap = argparse.ArgumentParser(description="The rover's end of the link")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--fake", action="store_true", help="print instead of driving")
    ap.add_argument("--fast", action="store_true", help="with --fake: no waiting")
    args = ap.parse_args()
    if args.fast:
        config.FORWARD_S_PER_CELL = 0.05
        config.TURN_S_PER_90 = 0.05
        config.SETTLE_S = 0.0

    rover = Rover(open_motors(args.fake))
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.port))
    srv.listen(8)
    motors = "fake" if args.fake else "real"
    print(f"rover listening on port {args.port}  ({motors} motors, "
          f"{config.FORWARD_S_PER_CELL:.2f} s/cell, {config.TURN_S_PER_90:.2f} s/90)")
    print("place it on its start cell facing grid north. Ctrl-C to quit.")

    def window(conn, addr, n):
        print(f"window {n} connected from {addr[0]}")
        try:
            serve(conn, rover, args.fake, n)
        finally:
            conn.close()
            print(f"window {n} disconnected")

    try:
        n = 0
        while True:
            conn, addr = srv.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            n += 1
            threading.Thread(target=window, args=(conn, addr, n), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        rover.motors.close()
        srv.close()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
