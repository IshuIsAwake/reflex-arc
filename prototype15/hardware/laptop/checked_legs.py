"""Level 4: every leg the game drives goes to the rover a piece at a time, a straight run
or a quarter turn, and the LiDAR checks the rover before and after each piece.

Before a straight run it looks ahead. If something is in the way, the rover drives only the
cells that stop short of it, and the game is told there is rock there, so A* plans round it.

After each piece it asks where the rover really is:
  - Within POSITION_TOL_M of the plan: OK, the next piece goes.
  - Heading more than HEADING_TOL_DEG off: a short fix-up turn, then look again, up to
    FIX_TRIES times. The heading is the one thing driven back: a heading error is what turns
    the next straight run into a diagonal.
  - In another cell: OFF. The rest of the leg is dropped, the rover is told where it stands,
    and the game's rover is moved there (game/nav.py), which plans again from there to
    where it was going. Position is reported and replanned from, never driven back.
  - The LiDAR's answer can't be trusted, or the cell is rock in the game with no free cell
    beside it: LOST. The rover is a person's to put right, as after a stop from the pad.

Cells here are the rover's, counted from home; the game's are those plus `offset`."""

import math
import time

from level3_game import STEP, RoverLegs, show
from link import LinkError, RoverStopped

TURN_LEFT = {"N": "W", "W": "S", "S": "E", "E": "N"}
TURN_RIGHT = {"N": "E", "E": "S", "S": "W", "W": "N"}
COMPASS = {"N": 0, "E": 90, "S": 180, "W": 270}

POSITION_TOL_M = 0.08  # about what a stop coasts; a smaller miss isn't counted
HEADING_TOL_DEG = 5.0
FIX_TRIES = 3
FIX_POWER = 0.6  # the same as TURN_POWER in the Pi's calib.json, so turn_s holds for it
SETTLE_S = 0.6  # the rover's own settle after a move
STOP_SHORT_M = 0.05  # room left between the rover's front and something in its way
ROVER_FRONT_M = 0.15  # the rover's front edge from its middle, as in the Pi's lidar_config.py


def pieces(heading, dirs):
    """A leg in N E S W, starting from `heading`, as straight runs and quarter turns in the
    rover's F L R. ["N", "N", "E", "E"] facing N -> [["F", "F"], ["R"], ["F", "F"]]."""
    out = []
    for d in dirs:
        if d == heading:
            if out and out[-1][0] == "F":
                out[-1].append("F")
            else:
                out.append(["F"])
            continue
        if TURN_RIGHT[heading] == d:
            out.append(["R"])
        elif TURN_LEFT[heading] == d:
            out.append(["L"])
        else:
            out.append(["R"])  # turning round: two quarter turns, each one checked
            out.append(["R"])
        heading = d
        out.append(["F"])
    return out


def free_cell(world, cell):
    """`cell` if the game's rover can stand on it, else the nearest free cell around it, or
    None. The real floor has no rock where the game has some, so a rover measured "in" rock
    is really beside where the game drew it."""
    area = world.here
    if not area.blocked(*cell):
        return cell
    # the four sides first, then the corners, which are further away
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0), (1, -1), (1, 1), (-1, 1), (-1, -1)):
        beside = (cell[0] + dx, cell[1] + dy)
        if not area.blocked(*beside):
            return beside
    return None


class CheckedLegs(RoverLegs):
    def __init__(self, rover, lidar, press_space, start, cell_m, turn_s):
        super().__init__(rover, press_space, start, cell_m)
        self.lidar = lidar
        self.turn_s = turn_s  # seconds for a quarter turn, from the rover's hello
        self.offset = None  # game cell - rover cell, worked out at the first leg
        self.measured = None  # the game cell the rover really ended a leg on, if not the plan's
        self.rocks = []  # game cells the LiDAR found something in, for the game's map

    def game_cell(self, x, y):
        return x + self.offset[0], y + self.offset[1]

    def leg_started(self, world, dirs):
        if self.offset is None:
            # the game has already driven this leg, so its start is the end minus the moves
            x, y = world.pos
            for d in dirs:
                x -= STEP[d][0]
                y -= STEP[d][1]
            self.offset = (x - self.pose["x"], y - self.pose["y"])
        super().leg_started(world, dirs)

    def leg_finished(self, world):
        """Called by the game once its pause is over. Returns None if the rover is where the
        game thinks, or (the game cell it is really on, rock cells found), for game/nav.py
        to move to, mark and plan again from."""
        super().leg_finished(world)
        if self.measured is None and not self.rocks:
            return None
        answer = (self.measured or world.pos, self.rocks)
        self.measured = None
        self.rocks = []
        return answer

    def drive(self, world, dirs):
        print(f"[rover] leg: {' '.join(dirs)}")
        start = self.pose
        stopped_early = False
        for piece in pieces(self.pose["heading"], dirs):
            if piece[0] == "F":
                wanted = len(piece)
                piece = self.clear_part(piece)
                if len(piece) < wanted:
                    stopped_early = True
                if not piece:
                    break  # something right in front: nothing to drive
            try:
                self.pose = self.rover.drive(piece, on_step=show)
            except RoverStopped as e:
                print(f"[rover] STOPPED: {e}")
                self.pose = start  # hand_back counts the leg's end from its start
                self.hand_back(dirs)
                return
            except (LinkError, OSError) as e:
                print(f"[rover] FAILED: {e}")
                self.pose = start
                self.hand_back(dirs)
                return
            verdict = self.check(world)
            if verdict == "LOST":
                self.pose = start
                self.hand_back(dirs)
                return
            if verdict == "OFF" or stopped_early:
                stopped_early = True
                break  # the game plans again from where the rover really is
        if stopped_early:
            self.measured = self.game_cell(self.pose["x"], self.pose["y"])
        print(f"[rover] leg done, rover on {self.pose}")
        self.driving -= 1
        self.release(world, dirs)

    def clear_part(self, piece):
        """A straight run cut short of anything in the rover's way. Something found goes in
        self.rocks as the game cell it is in."""
        look_m = len(piece) * self.cell_m + STOP_SHORT_M
        gap = self.lidar.ahead(look_m)
        if gap is None:
            return piece
        cells = int((gap - STOP_SHORT_M) / self.cell_m)  # whole cells that stop short of it
        cells = max(0, min(len(piece), cells))
        # the cell the thing is in, counted from the rover's middle
        away = round((gap + ROVER_FRONT_M) / self.cell_m)
        dx, dy = STEP[self.pose["heading"]]
        rock = self.game_cell(self.pose["x"] + dx * away, self.pose["y"] + dy * away)
        self.rocks.append(rock)
        print(f"[lidar] something {gap * 100:.0f} cm ahead, in {rock}: driving {cells} of "
              f"{len(piece)} cells")
        return piece[:cells]

    def check(self, world):
        """Ask the LiDAR where the rover is after a piece. Returns OK, OFF or LOST."""
        for tries in range(FIX_TRIES + 1):
            found = self.lidar.locate(self.pose, self.cell_m)
            if not found["ok"] or found["status"] != "OK":
                print(f"[lidar] LOST: can't trust where it is: {found}")
                return "LOST"
            # -180..180: + means it faces further clockwise than it should
            off_deg = (found["heading"] - COMPASS[self.pose["heading"]] + 180) % 360 - 180
            if abs(off_deg) <= HEADING_TOL_DEG or tries == FIX_TRIES:
                break
            print(f"[lidar] heading {off_deg:+.0f} deg off, turning back")
            self.fix_heading(off_deg)

        planned = (self.pose["x"], self.pose["y"])
        cell = (round(found["x"]), round(found["y"]))
        miss_m = math.hypot(found["x"] - planned[0], found["y"] - planned[1]) * self.cell_m
        line = (f"[lidar] at ({found['x']:.1f}, {found['y']:.1f}) facing {found['heading']:.0f}, "
                f"planned {planned} facing {self.pose['heading']}: {miss_m * 100:.0f} cm off")
        if miss_m <= POSITION_TOL_M or cell == planned:
            print(line + " -> OK")
            return "OK"

        manhattan = abs(cell[0] - planned[0]) + abs(cell[1] - planned[1])
        chebyshev = max(abs(cell[0] - planned[0]), abs(cell[1] - planned[1]))
        game_cell = self.game_cell(*cell)
        free = free_cell(world, game_cell)
        if free is None:
            print(line + f" -> LOST: {game_cell} is rock in the game, with no free cell beside it")
            return "LOST"
        if free != game_cell:
            print(f"[lidar] {game_cell} is rock in the game; using {free} beside it")
        self.pose = self.rover.set_pose(free[0] - self.offset[0], free[1] - self.offset[1],
                                        self.pose["heading"])["pose"]
        print(line + f" -> OFF by {manhattan} (Manhattan), {chebyshev} (Chebyshev): "
              f"the game's rover moves to {free} and plans again")
        return "OFF"

    def fix_heading(self, off_deg):
        """A short turn back by off_deg, with the pad's manual message, which has to come
        again within 0.4 s or the rover stops by itself."""
        if off_deg > 0:
            left, right = -FIX_POWER, FIX_POWER  # anticlockwise, as moves.py's L
        else:
            left, right = FIX_POWER, -FIX_POWER
        end = time.monotonic() + abs(off_deg) / 90 * self.turn_s
        while time.monotonic() < end:
            self.rover.manual(left, right)
            time.sleep(0.05)
        self.rover.manual(0, 0)
        time.sleep(SETTLE_S)
