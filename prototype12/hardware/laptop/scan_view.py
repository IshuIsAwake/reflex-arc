"""The LiDAR map window -- see the room, map it, check the game's map fits, locate.

    python scan_view.py --rover 10.119.42.34        (or double-click run_lidar_map.py)

Two views, V to switch:
  room view   the room's map fixed, north up, home at the centre; the rover moves on it,
              its live scan in green. The blue square is the game's 30 x 30 map at the
              current cell size -- it must sit inside the walls.
  rover view  the rover fixed in the middle, front up, the live scan around it.

Mapping a room, once per arena:
  1. rover on its home spot, facing north, nothing moving near it -- H records home;
  2. M turns mapping on; drive slowly round the room with the arrow keys and stop for a
     moment now and then. Each stop that fits the map well (80 % of the scan already on
     it) and is 20 cm or 15 deg from the last view is added. The grey map grows;
  3. R checks the game's map fits, with the room map; K keeps the cell size it suggests.
     Too small and it says "clear the map", with the numbers, and keeps nothing.
  4. drive back to home, M off. The map is saved on the Pi; Level 4 uses it.

    arrows  drive (1-9 power)   H home   M mapping   R room check   K keep cell size
    L locate   A add this view now   V view   + - zoom   Q quit

Talks to the rover over two connections: one for the LiDAR work, in the background so
the window never freezes, and one for driving, so the arrows answer at once. Other
windows -- the game, the control pad -- can be open at the same time.
"""

import argparse
import math
import os
import queue
import sys
import threading
import time

import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link import RoverLink  # noqa: E402

W, H = 860, 760
BODY = (0.31, 0.245)             # the chassis, metres (PI_5's nav2 footprint)
BG, RING, DOT, ROVER, INK = (12, 16, 20), (40, 52, 60), (120, 230, 140), (230, 200, 90), (220, 230, 235)
REF, GAME = (120, 120, 132), (90, 150, 240)
VERDICT = {"OK": (120, 230, 140), "POOR": (240, 120, 90), "AMBIGUOUS": (240, 200, 90)}
ADD_M, ADD_DEG, STILL_S, MAP_MATCHED = 0.20, 15.0, 0.6, 0.8


class Poller:
    """The LiDAR work, on its own thread and connection: the latest scan, the latest fix,
    and the requests the keys make. Results are plain attributes the window reads."""

    def __init__(self, host, port=5005):
        self.link = RoverLink(host, port, timeout=10)
        self.hello = self.link.hello()
        self.cell_m = self.hello.get("cell_m")
        self.scan = self.fix = self.ref = self.room = None
        self.status, self.said = "", ""
        self.live = self.mapping = False
        self.still_since = time.monotonic()     # the window sets this when the arrows let go
        self.added_at, self.views = None, 0
        self.jobs = queue.Queue()
        self.ref = self._ref()
        threading.Thread(target=self._run, daemon=True).start()

    def _ref(self):
        r = self.link.reference()
        return (r["x_cm"], r["y_cm"]) if r.get("ok") else None

    def _run(self):
        while True:
            try:
                while not self.jobs.empty():
                    self._job(self.jobs.get())
                t0 = time.monotonic()
                s = self.link.scan()
                if s.get("ok"):
                    self.scan = s
                    self.status = (f"{len(s['range_mm'])} points  {s['hz']} Hz  link "
                                   f"{(time.monotonic() - t0) * 1000:.0f} ms  CRC fails {s['crc_fail']}")
                else:
                    self.status = s.get("note", "no scan")
                if (self.live or self.mapping) and self.ref:
                    w = self.link.where()
                    self.fix = w if w.get("ok") else None
                    if self.mapping and self.fix:
                        self._maybe_add()
                time.sleep(0.05)
            except OSError as e:
                self.status = f"link lost: {e}"[:70]
                time.sleep(1)
                try:
                    self.link.connect()
                except OSError:
                    pass

    def _maybe_add(self):
        f = self.fix
        if f["status"] != "OK" or f["matched"] < MAP_MATCHED:
            return
        if time.monotonic() - self.still_since < STILL_S:
            return                                  # only views taken standing still
        if self.added_at:
            x, y, yaw = self.added_at
            turned = abs((f["yaw_deg"] - yaw + 180) % 360 - 180)
            if math.hypot(f["x"] - x, f["y"] - y) < ADD_M and turned < ADD_DEG:
                return
        r = self.link.ref_add(min_matched=MAP_MATCHED)
        if r.get("added"):
            self.added_at = (r["x"], r["y"], r["yaw_deg"])
            self.views += 1
            self.ref = self._ref()
            self.said = f"mapping: view {self.views} added, the map has {r['ref_points']} points"

    def _job(self, job):
        kind = job[0]
        if kind == "home":
            r = self.link.ref_home()
            self.said = r.get("note", "") + (f" ({r['points']} points)" if r.get("ok") else "")
            self.ref, self.fix, self.added_at, self.views = self._ref(), None, (0, 0, 0), 0
        elif kind == "add":
            r = self.link.ref_add()
            self.said = (f"added this view ({r['ref_points']} points)" if r.get("added") else
                         f"not added: {r.get('status') or r.get('note')}")
            self.ref = self._ref()
        elif kind == "room":
            r = self.link.room(save=job[1])
            self.room = r
            if r.get("saved"):
                self.cell_m = r["cell_m"]
                self.said = f"kept: {r['saved']}. Restart the game to use it."
            elif job[1]:
                self.said = "nothing kept: the room check has no cell size to keep"


def wrap(text, width=100):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return out + ([line] if line else [])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True)
    args = ap.parse_args()

    try:
        p = Poller(args.rover)
        drive = RoverLink(args.rover, timeout=5)
        drive.hello()
    except OSError as e:
        sys.exit(f"cannot reach the rover at {args.rover}:5005 ({e}). Is server.py running?")
    if not p.hello.get("lidar"):
        sys.exit("the rover server has no LiDAR open (check its start-up line: 'lidar: ...')")

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"Rover LiDAR map -- {args.rover}")
    font = pygame.font.SysFont("consolas", 15)
    clock = pygame.time.Clock()
    px_per_m, room_view, power, sent = 70.0, bool(p.ref), 0.5, (0.0, 0.0)

    def to_screen(mx, my):          # map frame (x north, y west) -> room view pixels
        return W / 2 - my * px_per_m, H / 2 + 20 - mx * px_per_m

    try:
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type != pygame.KEYDOWN:
                    continue
                elif e.key == pygame.K_q:
                    running = False
                elif e.unicode in "+=":
                    px_per_m = min(600, px_per_m * 1.25)
                elif e.unicode == "-":
                    px_per_m = max(15, px_per_m / 1.25)
                elif e.unicode and e.unicode in "123456789":
                    power = int(e.unicode) / 9
                elif e.key == pygame.K_v:
                    room_view = not room_view
                elif e.key == pygame.K_h:
                    p.jobs.put(("home",))
                    room_view = True
                elif e.key == pygame.K_a:
                    p.jobs.put(("add",))
                elif e.key == pygame.K_r:
                    p.jobs.put(("room", False))
                elif e.key == pygame.K_k:
                    p.jobs.put(("room", True))
                elif e.key == pygame.K_l:
                    p.live = not p.live
                    p.said = "locating live" if p.live else "locating off"
                elif e.key == pygame.K_m:
                    p.mapping = not p.mapping
                    p.said = ("mapping on: drive slowly, stop now and then" if p.mapping
                              else f"mapping off ({p.views} views added)")

            # Driving: arrows, on its own connection, every frame while held.
            k = pygame.key.get_pressed()
            throttle = k[pygame.K_UP] - k[pygame.K_DOWN]
            turn = k[pygame.K_RIGHT] - k[pygame.K_LEFT]
            left, right = throttle + turn, throttle - turn
            big = max(1.0, abs(left), abs(right))
            cmd = (left / big * power, right / big * power)
            try:
                if cmd != (0.0, 0.0) or sent != (0.0, 0.0):
                    drive.manual(*cmd)
            except OSError:
                p.said = "the driving connection dropped"
            if cmd != (0.0, 0.0):
                p.still_since = time.monotonic()
            sent = cmd

            screen.fill(BG)
            fix, scan = p.fix, p.scan
            if room_view and p.ref:
                cell = (p.room or {}).get("cell_m") or p.cell_m
                if cell:                                    # the game's map, at that cell
                    half = cell * 15
                    x0, y0 = to_screen(half, half)
                    pygame.draw.rect(screen, GAME, (x0, y0, 2 * half * px_per_m, 2 * half * px_per_m), 1)
                for mx, my in zip(*p.ref):
                    screen.fill(REF, (*to_screen(mx / 100, my / 100), 2, 2))
                hx, hy = to_screen(0, 0)
                pygame.draw.line(screen, INK, (hx - 6, hy), (hx + 6, hy))
                pygame.draw.line(screen, INK, (hx, hy - 6), (hx, hy + 6))
                if fix and fix["status"] == "OK":
                    fx, fy, fyaw = fix["x"], fix["y"], math.radians(fix["yaw_deg"])
                    c, s_ = math.cos(fyaw), math.sin(fyaw)
                    if scan:
                        for a, d in zip(scan["angle_ddeg"], scan["range_mm"]):
                            th, m = math.radians(a / 10), d / 1000
                            rx, ry = m * math.cos(th), m * math.sin(th)
                            screen.fill(DOT, (*to_screen(fx + c * rx - s_ * ry, fy + s_ * rx + c * ry), 2, 2))
                    corners = [(BODY[0] / 2, BODY[1] / 2), (BODY[0] / 2, -BODY[1] / 2),
                               (-BODY[0] / 2, -BODY[1] / 2), (-BODY[0] / 2, BODY[1] / 2)]
                    pts = [to_screen(fx + c * bx - s_ * by, fy + s_ * bx + c * by) for bx, by in corners]
                    pygame.draw.polygon(screen, ROVER, pts, 2)
                    pygame.draw.line(screen, ROVER, to_screen(fx, fy),
                                     to_screen(fx + c * 0.3, fy + s_ * 0.3), 3)
            else:
                cx, cy = W // 2, H // 2 + 20
                for r in range(1, 30):
                    rad = int(r * 0.5 * px_per_m)
                    if rad > W:
                        break
                    pygame.draw.circle(screen, RING, (cx, cy), rad, 1)
                if p.ref and fix:
                    fx, fy, fyaw = fix["x"], fix["y"], math.radians(fix["yaw_deg"])
                    c, s_ = math.cos(-fyaw), math.sin(-fyaw)
                    for mx, my in zip(*p.ref):
                        dx, dy = mx / 100 - fx, my / 100 - fy
                        x, y = c * dx - s_ * dy, s_ * dx + c * dy
                        screen.fill(REF, (cx - y * px_per_m, cy - x * px_per_m, 2, 2))
                bw, bl = BODY[1] * px_per_m, BODY[0] * px_per_m
                pygame.draw.rect(screen, ROVER, (cx - bw / 2, cy - bl / 2, bw, bl), 2)
                pygame.draw.line(screen, ROVER, (cx, cy), (cx, cy - bl / 2 - 12), 3)
                if scan:
                    for a, d in zip(scan["angle_ddeg"], scan["range_mm"]):
                        th, m = math.radians(a / 10), d / 1000
                        x, y = m * math.cos(th), m * math.sin(th)
                        screen.fill(DOT, (cx - y * px_per_m, cy - x * px_per_m, 3, 3))

            lines = [(p.status, INK)]
            if fix:
                lines.append((f"{fix['status']}  x {fix['x']:+.2f}  y {fix['y']:+.2f} m  yaw "
                              f"{fix['yaw_deg']:+.1f} deg  cell {fix['cell']}  matched "
                              f"{fix['matched']:.0%}", VERDICT.get(fix["status"], INK)))
            elif not p.ref:
                lines.append(("no room map yet -- rover on home, facing north, press H", INK))
            mode = (("MAPPING  " if p.mapping else "") + ("room view" if room_view and p.ref
                    else "rover view") + f"   power {power:.2f}")
            lines.append((mode, GAME if p.mapping else INK))
            if p.room:
                colour = VERDICT["OK"] if p.room.get("cell_m") else VERDICT["POOR"]
                for t in wrap(f"room check ({p.room.get('from', '')}): {p.room.get('message', '')} "
                              f"{p.room.get('advice', '')}"):
                    lines.append((t, colour))
            for t in wrap(p.said):
                lines.append((t, INK))
            for i, (t, colour) in enumerate(lines):
                screen.blit(font.render(t, True, colour), (12, 8 + 18 * i))
            screen.blit(font.render("arrows drive  H home  M map  R room check  K keep cell  "
                                    "L locate  A add  V view  +- zoom  Q quit", True, INK), (12, H - 24))
            pygame.display.flip()
            clock.tick(30)
    finally:
        try:
            drive.manual(0, 0)
        except OSError:
            pass
        drive.close()
        p.link.close()
        pygame.quit()


if __name__ == "__main__":
    main()
