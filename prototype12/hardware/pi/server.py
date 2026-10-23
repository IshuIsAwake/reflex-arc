"""The rover's end of the link. Runs on the Pi; the laptop connects to it.

    python3 server.py                 real motors, port 5005
    python3 server.py --fake          prints instead (also runs on the laptop, for testing)
    python3 server.py --fake --fast   and skips the waiting

TCP, one JSON object a line each way, standard library only. Several laptop windows can
be connected at once -- the game and the control pad -- each its own connection; one
drive at a time still.

  laptop -> rover
    {"op": "hello"}
    {"op": "reset", "heading": "N"}          you are facing grid north now
    {"op": "set_pose", "x": 3, "y": -2, "heading": "E"}   you are on this cell now (after a
                                             person has put it right)
    {"op": "drive", "id": 7, "cmds": ["N", "N", "E"]}
    {"op": "manual", "left": 0.5, "right": -0.5}  wheel power from the control pad, no reply;
                                                   stops by itself 0.4 s after the last one
    {"op": "stop"}

  rover -> laptop
    {"ok": true, "pose": {...}, "fake": false}             answer to hello / reset / stop
    {"event": "step", "id": 7, "i": 1, "cmd": "N", "pose": {...}}   after each command
    {"event": "done", "id": 7, "result": "DONE", "pose": {...}}     always last for a drive
                      result: DONE, STOPPED (a stop came in), BUSY (another drive running),
                      REFUSED (bad commands)

The pose is dead-reckoned: what the timings claim, measured by nothing.

Safety: if the window that is driving disconnects mid-drive, the motors stop; any
window's "stop" stops them; manual driving stops 0.4 s after its last message. A drive id the rover
has already finished is answered from memory without moving, so a laptop that
retries after a drop cannot drive the same leg twice.
"""

import argparse
import json
import socket
import threading
import time

import config as C
import grid
import moves
from motors import open_motors


MANUAL_DEADMAN_S = 0.4    # the pad repeats every 50 ms while a stick or key is held


def pose_json(p):
    return {"x": p.x, "y": p.y, "heading": grid.HEADING_NAMES[p.heading]}


def groups(prims):
    """['R','F','F','F','L','F'] -> [('R',1),('F',3),('L',1),('F',1)]. Forward runs
    merge into one pulse; turns stay single, so each quarter turn settles on its own."""
    out = []
    for p in prims:
        if out and out[-1][0] == p and p in "FB":
            out[-1] = (p, out[-1][1] + 1)
        else:
            out.append((p, 1))
    return out


class Rover:
    def __init__(self, motors):
        self.motors = motors
        self.pose = grid.Pose(0, 0, 0)
        self.lock = threading.Lock()      # one drive at a time
        self.abort = threading.Event()
        self.finished = {}                # drive id -> its "done" message
        self.manual_at = 0.0              # last manual command; 0 = not driving by hand
        self.owner = None                 # the connection whose drive or hand is on the wheels
        threading.Thread(target=self._watchdog, daemon=True).start()

    def manual(self, left, right, who=None):
        """Wheel power straight from the control pad. Ignored while a drive runs, and it
        moves the rover without the grid knowing, so the pose is stale until a reset."""
        if self.lock.locked():
            return
        self.motors.set(max(-1.0, min(1.0, left)), max(-1.0, min(1.0, right)))
        self.manual_at = time.monotonic() if (left or right) else 0.0
        if left or right:
            self.owner = who

    def _watchdog(self):
        """A pad that goes quiet -- closed, crashed, wifi gone -- stops the wheels."""
        while True:
            time.sleep(0.05)
            if self.manual_at and time.monotonic() - self.manual_at > MANUAL_DEADMAN_S:
                self.manual_at = 0.0
                if not self.lock.locked():
                    self.motors.stop()

    def drive(self, msg, send):
        did = msg.get("id")
        if did in self.finished:
            send(self.finished[did])
            return
        if not self.lock.acquire(blocking=False):
            send({"event": "done", "id": did, "result": "BUSY", "pose": pose_json(self.pose)})
            return
        try:
            self.abort.clear()
            self.owner = msg.get("_from")
            result = "DONE"
            cmds = grid.parse(" ".join(msg.get("cmds", [])))
            # The whole list as primitives, each command's worked out against the heading it
            # will have by then. `ends[n]` is the command whose last primitive is flat[n].
            flat, ends, h = [], {}, self.pose.heading
            for k, cmd in enumerate(cmds):
                flat += grid.primitives(cmd, h)
                ends[len(flat) - 1] = k
                h = grid.apply(grid.Pose(0, 0, h), cmd).heading
            # Runs of F (or B) drive as one pulse across command boundaries: 10d's "E E E E"
            # from facing north is one turn and one four-cell pulse, not four stops.
            n, here = 0, self.pose
            for prim, count in groups(flat):
                moves.do(self.motors, prim, stop_check=self.abort.is_set, n=count)
                if self.abort.is_set():
                    result = "STOPPED"   # the pose below is a guess: it stopped mid-move
                    break
                for m in range(n, n + count):
                    here = grid.apply(here, prim)
                    if m in ends:
                        send({"event": "step", "id": did, "i": ends[m] + 1,
                              "cmd": cmds[ends[m]], "pose": pose_json(here)})
                n += count
                self.pose = here
            done = {"event": "done", "id": did, "result": result, "pose": pose_json(self.pose)}
            self.finished[did] = done
            send(done)
        except ValueError as e:
            send({"event": "done", "id": did, "result": "REFUSED", "note": str(e),
                  "pose": pose_json(self.pose)})
        finally:
            self.motors.stop()
            self.lock.release()


def serve(conn, rover, fake, who=None):
    """One laptop window. Several can be connected at once -- the game and the control
    pad. `who` names this one; only the window whose drive or hand is on the wheels stops
    them when it goes, so closing the pad never stops the game's drive."""
    out_lock = threading.Lock()

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
                op = msg.get("op")
                if op == "hello":
                    send({"ok": True, "pose": pose_json(rover.pose), "fake": fake,
                          "forward_s": C.FORWARD_S_PER_CELL, "turn_s": C.TURN_S_PER_90,
                          "cell_m": C.CELL_M})
                elif op == "reset":
                    h = grid.HEADING_NAMES.index(msg.get("heading", "N"))
                    rover.pose = grid.Pose(0, 0, h)
                    send({"ok": True, "pose": pose_json(rover.pose)})
                elif op == "set_pose":        # the laptop says where the rover is now
                    h = grid.HEADING_NAMES.index(msg.get("heading", "N"))
                    rover.pose = grid.Pose(int(msg["x"]), int(msg["y"]), h)
                    send({"ok": True, "pose": pose_json(rover.pose)})
                elif op == "stop":
                    rover.abort.set()
                    rover.motors.stop()
                    send({"ok": True, "note": "stopped"})
                elif op == "manual":          # no reply: it repeats 20 times a second
                    rover.manual(float(msg.get("left", 0)), float(msg.get("right", 0)), who)
                elif op == "drive":
                    msg["_from"] = who
                    t = threading.Thread(target=rover.drive, args=(msg, send), daemon=True)
                    t.start()
                    workers.append(t)
                else:
                    send({"ok": False, "note": f"unknown op {op!r}"})
    except OSError:
        pass
    finally:
        if rover.owner == who:    # this window was driving: whatever it moved stops
            rover.abort.set()
            rover.manual_at = 0.0
            rover.motors.stop()
            rover.owner = None
        for t in workers:
            t.join(timeout=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--fake", action="store_true", help="print instead of driving")
    ap.add_argument("--fast", action="store_true", help="with --fake: no waiting")
    args = ap.parse_args()
    if args.fast:
        C.FORWARD_S_PER_CELL, C.TURN_S_PER_90, C.SETTLE_S = 0.05, 0.05, 0.0

    rover = Rover(open_motors(args.fake))
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.port))
    srv.listen(8)
    print(f"rover listening on port {args.port}  ({'fake' if args.fake else 'real'} motors, "
          f"{C.FORWARD_S_PER_CELL:.2f} s/cell, {C.TURN_S_PER_90:.2f} s/90)")
    print("place it on its start cell facing grid north. Ctrl-C to quit.")

    def window(conn, addr, n):
        print(f"window {n} connected from {addr[0]}")
        try:
            serve(conn, rover, args.fake, who=n)
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
