"""The rover's end of the link. Runs on the Pi; the laptop connects to it.

    python3 server.py                 real motors, port 5005
    python3 server.py --fake          prints instead (also runs on the laptop, for testing)
    python3 server.py --fake --fast   and skips the waiting

TCP, one JSON object a line each way, standard library only. Several laptop windows can
be connected at once -- the game, the LiDAR map, the control pad -- each its own
connection; one drive at a time still.

  laptop -> rover
    {"op": "hello"}
    {"op": "reset", "heading": "N"}          you are facing grid north now
    {"op": "set_pose", "x": 3, "y": -2, "heading": "E"}   you are on this cell now (after a
                                             person has put it right)
    {"op": "drive", "id": 7, "cmds": ["N", "N", "E"]}
    {"op": "drive", "id": 8, "cmds": [...], "check": true}   checked with the LiDAR (Level 4)
    {"op": "manual", "left": 0.5, "right": -0.5}  wheel power from the control pad, no reply;
                                                   stops by itself 0.4 s after the last one
    {"op": "stop"}
    {"op": "scan"}                                the latest full LiDAR turn
    {"op": "ref_home"}     record the room's reference here: this spot is (0,0), facing N
    {"op": "ref_add"}      locate, and if that is OK, add what it sees to the reference
    {"op": "where"}        locate against the reference, searching around the last fix
    {"op": "ref"}          the reference's points, for drawing
    {"op": "ref_add", "min_matched": 0.8}   mapping: add only where most of it agrees
    {"op": "room", "save": false}   does the game's map fit this room; what cell size (room_fit)

  rover -> laptop
    {"ok": true, "pose": {...}, "fake": false}             answer to hello / reset / stop
    {"event": "step", "id": 7, "i": 1, "cmd": "N", "pose": {...}}   after each command
    {"event": "done", "id": 7, "result": "DONE", "pose": {...}}     always last for a drive
                      result: DONE, STOPPED (a stop came in), BUSY (another drive running),
                      REFUSED (bad commands, or a check asked for and not possible), and on
                      a checked drive LOST (2+ cells out) or UNSURE (the fit not trusted)

  On a checked drive, a step carries "check": {result, manhattan, chebyshev, x, y, yaw_deg,
  heading_err_deg, fixes, matched}, and a check in the middle of one command arrives as
  {"event": "check", ...}. The pose is then the LiDAR's, not the timings'.

The pose is dead-reckoned: what the timings claim, measured by nothing. With no
LiDAR there is nothing to measure it with -- Level 4 swaps the source, not the link.

Safety: if the window that is driving disconnects mid-drive, the motors stop; any
window's "stop" stops them; manual driving stops 0.4 s after its last message. A drive id the rover
has already finished is answered from memory without moving, so a laptop that
retries after a drop cannot drive the same leg twice.
"""

import argparse
import json
import math
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


def scan_json(lidar):
    """The latest full LiDAR turn, rover frame: angles in 0.1 deg, ranges in mm, as
    integers so a turn of ~500 points is a few KB of JSON."""
    if lidar is None:
        return {"ok": False, "note": "no lidar on this rover"}
    s = lidar.latest()
    if s is None:
        return {"ok": False, "note": "lidar open but no full turn yet"}
    import numpy as np
    return {"ok": True, "age_s": round(time.monotonic() - s.t_end, 2), "hz": round(s.speed / 360, 1),
            "angle_ddeg": np.round(np.degrees(s.angle) * 10).astype(int).tolist(),
            "range_mm": np.round(s.range * 1000).astype(int).tolist(),
            "crc_fail": lidar.crc_fail, "turns": lidar.turns}


def lidar_op(rover, op, msg=None):
    """The reference, locate and room messages. Nothing here moves the rover.

    All of it holds `rover.ref_lock`: with several windows open, the map window may be
    locating or adding to the room's map while a drive checks against it.
    """
    msg = msg or {}
    if rover.lidar is None:
        return {"ok": False, "note": "no lidar on this rover"}
    with rover.ref_lock:
        return _lidar_op(rover, op, msg)


def _lidar_op(rover, op, msg):
    import locate as L
    import reference as R
    if op == "ref":                               # the reference's points, for the viewer
        if rover.ref is None:
            return {"ok": False, "note": "no reference yet"}
        return {"ok": True, "x_cm": [int(v * 100) for v in rover.ref.xs],
                "y_cm": [int(v * 100) for v in rover.ref.ys]}
    if op == "ref_home":
        rover.ref, n = R.record_home(rover.lidar)
        if rover.ref_file:
            R.save(rover.ref, rover.ref_file)
        rover.map_pose = (0.0, 0.0, 0.0)
        rover.pose = grid.Pose(0, 0, 0)
        return {"ok": True, "points": n, "note": "home recorded: this spot is (0,0), facing N"}
    if op == "room":
        import room_fit
        if rover.ref is not None:                 # the room's map: sees round corners
            r = room_fit.fit(rover.ref.xs, rover.ref.ys)
            r["from"] = "the room map"
        else:                                     # no map yet: one look from here
            s = rover.lidar.next_scan(timeout=2.0)
            if s is None:
                return {"ok": False, "note": "no full LiDAR turn"}
            r = room_fit.fit(*s.xy())
            r["from"] = "one scan from where the rover stands (record home for a map)"
        if msg.get("save") and r.get("cell_m"):
            C.save(CELL_M=r["cell_m"])
            r["saved"] = f"CELL_M = {r['cell_m']}, a cell takes {C.FORWARD_S_PER_CELL} s"
        r["ok"] = True
        return r
    if rover.ref is None:
        return {"ok": False, "note": "no reference yet -- record home first"}
    if op == "ref_add":
        res = R.add_view(rover.ref, rover.lidar, rover.map_pose,
                         min_matched=float(msg.get("min_matched", 0.0)))
        if res.get("added") and rover.ref_file:
            R.save(rover.ref, rover.ref_file)
    else:                                         # "where"
        s = rover.lidar.next_scan(timeout=2.0)
        if s is None:
            return {"ok": False, "note": "no full LiDAR turn"}
        res = L.locate(rover.ref, *s.xy(), rover.map_pose)
    if res["status"] == "OK":
        rover.map_pose = res["pose"]
    x, y, yaw = res["pose"]
    gx, gy, h = L.to_cell(res["pose"], C.CELL_M)
    return {"ok": True, "status": res["status"], "x": round(x, 3), "y": round(y, 3),
            "yaw_deg": round(math.degrees(yaw), 1), "cost": round(res["cost"], 3),
            "matched": round(res["matched"], 2), "cell": [gx, gy, grid.HEADING_NAMES[h]],
            "points": res.get("points", 0), "note": res.get("note", ""),
            "added": bool(res.get("added")), "ref_points": len(rover.ref.xs)}


def groups(prims, cap=None):
    """['R','F','F','F','L','F'] -> [('R',1),('F',3),('L',1),('F',1)]. Forward runs
    merge into one pulse; turns stay single, so each quarter turn settles on its own.
    `cap` splits a run longer than that, so a checked drive looks part-way along it."""
    out = []
    for p in prims:
        if out and out[-1][0] == p and p in "FB" and (cap is None or out[-1][1] < cap):
            out[-1] = (p, out[-1][1] + 1)
        else:
            out.append((p, 1))
    return out


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


class Rover:
    def __init__(self, motors, lidar=None):
        self.motors = motors
        self.lidar = lidar                # an ld19.LD19, or None when there is none
        self.ref = None                   # the room's reference (reference.py), if recorded
        self.map_pose = (0.0, 0.0, 0.0)   # last LiDAR-measured pose, map frame, metres/rad
        self.ref_file = None              # where the reference is kept; None = never on disk
        if lidar is not None:
            import reference
            self.ref_file = reference.FILE
            self.ref = reference.load(self.ref_file)
        self.pose = grid.Pose(0, 0, 0)
        self.lock = threading.Lock()      # one drive at a time
        self.ref_lock = threading.Lock()  # the room's map, read and changed from several windows
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

    # --- checking with the LiDAR ---------------------------------------------------
    def can_check(self):
        """None if a drive can be checked with the LiDAR, else why not."""
        if self.lidar is None:
            return "no lidar on this rover"
        if self.ref is None:
            return "no reference of the room -- record home first (run_lidar_map, H)"
        if not C.LIDAR_MOUNT_CHECKED:
            return "LiDAR mounting not checked -- run `python3 lidar_check.py --mount` on the Pi"
        return None

    def _fix(self, guess):
        """A fresh scan located around `guess` (map frame). None if no scan came.

        If it does not fit around the guess, it is looked for again over twice the range
        before giving up: a long run that slipped 40 % ends beyond the first look, and
        finding it there turns an UNSURE stop into a LOST one with a real position the
        simulation can follow. The verdict rules are the same either way.
        """
        import locate as L
        s = self.lidar.next_scan(timeout=2.0)
        if s is None:
            return None
        xs, ys = s.xy()
        with self.ref_lock:
            res = L.locate(self.ref, xs, ys, guess)
            if res["status"] != "OK":
                wide = L.locate(self.ref, xs, ys, guess, span_m=2 * L.SEARCH_M)
                if wide["status"] == "OK":
                    wide["note"] = "found on the wider look"
                    return wide
        return res

    def check_here(self, expected):
        """Stopped where the grid says `expected` (a grid.Pose): measure, fix the heading,
        compare. Returns a dict for the step message, with "measured" a grid.Pose."""
        import locate as L
        want = L.from_cell(expected.x, expected.y, expected.heading, C.CELL_M)
        res = self._fix(want)
        if res is None or res["status"] != "OK":
            return {"result": "UNSURE", "status": res["status"] if res else "NO SCAN",
                    "note": "the LiDAR fit cannot be trusted here; stopped"}
        fixes, err, first, why = 0, 0.0, None, ""
        for fixes in range(C.HEADING_FIX_TRIES + 1):
            err = wrap_deg(math.degrees(res["pose"][2] - want[2]))
            first = err if first is None else first
            if abs(err) <= C.HEADING_TOL_DEG or fixes == C.HEADING_FIX_TRIES:
                break
            # Heading is the one thing corrected (ARCHITECTURE.md): turn back by what was measured.
            secs = abs(err) / 90.0 * C.TURN_S_PER_90
            if secs < C.FIX_MIN_S:
                # Rounding the pulse up would overshoot by more than the error; leave it, say so.
                why = f"{err:+.0f} deg is below the smallest turn the chassis makes"
                break
            moves.do(self.motors, "R" if err > 0 else "L", stop_check=self.abort.is_set, secs=secs)
            x, y, _ = res["pose"]
            # Look around the heading it was meant to reach: an over- or undershoot of the fix
            # itself, up to SEARCH_DEG, is still found.
            res = self._fix((x, y, want[2]))
            if res is None or res["status"] != "OK":
                return {"result": "UNSURE", "status": res["status"] if res else "NO SCAN",
                        "note": "lost the fit during a heading fix; stopped"}
        self.map_pose = res["pose"]
        gx, gy, h = L.to_cell(res["pose"], C.CELL_M)
        x, y, yaw = res["pose"]
        if math.hypot(x - want[0], y - want[1]) <= max(C.POSITION_TOL_M, C.CELL_M / 2):
            gx, gy = expected.x, expected.y   # within tolerance: the planned cell, at any size
        measured = grid.Pose(gx, gy, h)
        c = grid.check(expected, measured)
        return {"result": c.result, "manhattan": c.manhattan, "chebyshev": c.chebyshev,
                "kind": c.kind, "measured": measured, "heading_err_deg": round(err, 1),
                "heading_err_was": round(first, 1), "fixes": fixes, "heading_note": why,
                "x": round(x, 3), "y": round(y, 3),
                "yaw_deg": round(math.degrees(yaw), 1), "matched": round(res["matched"], 2)}

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
            result, note = "DONE", ""
            check = bool(msg.get("check"))
            if check and self.can_check():
                raise ValueError(self.can_check())
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
            # Checked, every pulse ends in a LiDAR check, and long runs are split for it.
            n, here = 0, self.pose
            for prim, count in groups(flat, C.LIDAR_CHECK_EVERY if check else None):
                moves.do(self.motors, prim, stop_check=self.abort.is_set, n=count)
                if self.abort.is_set():
                    result = "STOPPED"   # the pose below is a guess: it stopped mid-move
                    break
                done_here = []                       # commands that ended in this pulse
                for m in range(n, n + count):
                    here = grid.apply(here, prim)
                    if m in ends:
                        done_here.append((ends[m], here))
                n += count
                seen = self.check_here(here) if check else None
                if seen and "measured" in seen:
                    # Position is reported, not driven back: carry on from where it is.
                    here = seen.pop("measured")
                    if done_here:
                        done_here[-1] = (done_here[-1][0], here)
                for j, (k, pose) in enumerate(done_here):
                    step = {"event": "step", "id": did, "i": k + 1, "cmd": cmds[k],
                            "pose": pose_json(pose)}
                    if seen and j == len(done_here) - 1:
                        step["check"] = seen
                    send(step)
                if seen and not done_here:           # a check in the middle of a command
                    send({"event": "check", "id": did, "pose": pose_json(here), "check": seen})
                self.pose = here
                if seen and seen["result"] in ("LOST", "UNSURE"):
                    result, note = seen["result"], seen.get("note", seen.get("kind", ""))
                    break
            done = {"event": "done", "id": did, "result": result, "pose": pose_json(self.pose)}
            if note:
                done["note"] = note
            self.finished[did] = done
            send(done)
        except ValueError as e:
            send({"event": "done", "id": did, "result": "REFUSED", "note": str(e),
                  "pose": pose_json(self.pose)})
        finally:
            self.motors.stop()
            self.lock.release()


def serve(conn, rover, fake, who=None):
    """One laptop window. Several can be connected at once -- the game, the LiDAR map,
    the control pad. `who` names this one; only the window whose drive or hand is on the
    wheels stops them when it goes, so closing the map never stops the game's drive."""
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
                          "lidar": rover.lidar is not None, "ref": rover.ref is not None,
                          "cell_m": C.CELL_M,
                          "can_check": rover.can_check() or "yes"})
                elif op == "scan":
                    send(scan_json(rover.lidar))
                elif op in ("ref", "ref_home", "ref_add", "where", "room"):
                    try:
                        send(lidar_op(rover, op, msg))
                    except Exception as e:      # a LiDAR fault must not take the link down
                        send({"ok": False, "note": f"{op} failed: {e}"})
                elif op == "reset":
                    h = grid.HEADING_NAMES.index(msg.get("heading", "N"))
                    rover.pose = grid.Pose(0, 0, h)
                    rover.map_pose = (0.0, 0.0, math.radians(-90.0 * h))   # home, that heading
                    send({"ok": True, "pose": pose_json(rover.pose)})
                elif op == "set_pose":        # the laptop says where the rover is now
                    h = grid.HEADING_NAMES.index(msg.get("heading", "N"))
                    rover.pose = grid.Pose(int(msg["x"]), int(msg["y"]), h)
                    import locate as L
                    rover.map_pose = L.from_cell(rover.pose.x, rover.pose.y, h, C.CELL_M)
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
    ap.add_argument("--no-lidar", action="store_true", help="do not open the LD19")
    ap.add_argument("--fake-world", action="store_true",
                    help="a pretend rover in a pretend room (fake_world.py): motors and LiDAR, "
                         "for trying everything on a laptop")
    args = ap.parse_args()
    if args.fast:
        C.FORWARD_S_PER_CELL, C.TURN_S_PER_90, C.SETTLE_S = 0.05, 0.05, 0.0
        C.FIX_MIN_S = 0.0           # a physical limit of the real chassis; time is compressed here
        if args.fake_world:
            # Pulses must stay long next to how late a sleep can wake on a busy laptop --
            # tens of ms with the simulation drawing. At 0.05 s a cell that was 0.3 m.
            C.FORWARD_S_PER_CELL, C.TURN_S_PER_90 = 0.25, 0.6

    lidar = None
    if args.fake_world:
        from fake_world import ARENA, FakeWorld
        world = FakeWorld(ARENA, turn_gain=0.85)   # turns come up short, as on the real floor
        motors, lidar = world.motors(), world.lidar()
        C.LIDAR_MOUNT_CHECKED = True
        C.CELL_M = 0.2                             # the cell ARENA is sized for, as on the Pi
        args.fake = True
        print("fake world: an 8.4 m square room, home in the middle, turns 15 % short")
    else:
        if not args.no_lidar and not args.fake:
            from ld19 import open_lidar
            lidar, why = open_lidar()
            print(f"lidar: {'LD19 open' if lidar else 'none -- ' + why}")
        motors = open_motors(args.fake)
    rover = Rover(motors, lidar)
    if args.fake_world:
        # The pretend room is never read from or written to reference.npz: a fake room saved
        # there would be copied to the Pi with the code and taken for the real one.
        rover.ref, rover.ref_file = None, None
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
        if rover.lidar:
            rover.lidar.close()
        srv.close()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
