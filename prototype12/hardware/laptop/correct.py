"""correct -- the simulation's rover moved to where the real one's LiDAR says it is.

Level 4 only. The rover checks every move with its LiDAR and ends each leg in the cell
it measured; this puts the simulation's rover in that same cell before the simulation
plans again, and tells the model, so it replans from where the rover really is. That is
ARCHITECTURE.md's rule -- errors are reported, not driven back -- carried through to the
map the model reads.

Nothing in game/ is edited. Everything here acts on the running simulation in memory:

  * after each rover pause, on the simulation's own thread (`after_pause`, from
    level3's `publish(world, [])`), the simulation's rover is moved the way its own
    `World.move` moves it -- `pos`, then `_arrive()`, which reveals fog, marks the
    cell visited and finds interests in sight -- but with no step or battery charged:
    the leg's steps were charged when the simulation drove it;
  * `nav.goto` is wrapped so the result the model reads names the measured cell, with
    one sentence saying it was the LiDAR's;
  * each move is written to the run record as a `lidar_fix` event.

Grids: when Level 4 starts the rover is reset to (0, 0) on the simulation's landing
cell, so simulation cell = rover cell + `offset`, fixed at the first leg.

A measured cell that is rock, storm or off the map in the simulation is not moved to
-- the floor has no rocks, the simulation's map does -- and the terminal says so.
"""

DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}   # the simulation's frame


def _c(cell):
    return f"({cell[0]},{cell[1]})"


class Corrector:
    def __init__(self, nav, send_pose=None):
        self.nav = nav
        self.send_pose = send_pose      # tell the rover its cell: (x, y, heading)
        self.offset = None              # simulation cell minus rover cell
        self.rover = (0, 0, "N")        # the rover's own idea of its cell, from its reports
        self.measured = None            # the cell the last leg ended in, by the LiDAR
        self.unsure = None              # heading, if the last leg ended with no trusted fix
        self.sim_at = None              # where the simulation's rover was left after a pause
        self.fixes = []                 # (planned, measured) within the current goto
        self._wrap_goto()

    # --- called by level3 -------------------------------------------------------
    def leg_handed(self, world, dirs):
        """A leg the simulation has driven, about to go to the rover (main thread)."""
        dx = sum(DIRS[d][0] for d in dirs)
        dy = sum(DIRS[d][1] for d in dirs)
        start = (world.pos[0] - dx, world.pos[1] - dy)
        if self.offset is None:
            self.offset = (start[0] - self.rover[0], start[1] - self.rover[1])
            return
        # Compared with where the *simulation's* rover was left, not with the real one: after
        # a correction that was refused (rock, off the map) the two differ on purpose, and the
        # real one's LiDAR cell is the truth -- it must not be overwritten.
        if self.sim_at is not None and start != self.sim_at:
            # The simulation moved its rover without a leg -- a new sol at the pad, say.
            print(f"[lidar] the simulation's rover jumped from {_c(self.sim_at)} to {_c(start)} "
                  f"without a leg. Put the real rover on {_c(start)}'s spot; it is being told "
                  f"it is there.")
            self._tell(start[0] - self.offset[0], start[1] - self.offset[1], self.rover[2])
        self.sim_at = None

    def leg_driven(self, pose):
        """The rover finished a checked leg, or stopped LOST; `pose` is what it measured."""
        self.rover = (pose["x"], pose["y"], pose["heading"])
        self.measured = (pose["x"], pose["y"])

    def leg_unsure(self, pose):
        """The rover stopped without a fix it trusted. A person puts it right."""
        self.unsure = (pose or {}).get("heading", self.rover[2])

    def after_pause(self, world):
        """The rover pause just ended and the simulation is about to plan (main thread)."""
        if self.offset is None:
            return
        if self.measured is not None:
            cell = (self.measured[0] + self.offset[0], self.measured[1] + self.offset[1])
            self.measured = None
            if cell != world.pos:
                why = self._move(world, cell)
                if why:
                    print(f"[lidar] measured {_c(cell)}, but that is {why}; the simulation's "
                          f"rover stays at {_c(world.pos)}")
        elif self.unsure is not None:
            # The person put the real rover where the screen shows it; the rover is told.
            x, y = world.pos[0] - self.offset[0], world.pos[1] - self.offset[1]
            self._tell(x, y, self.unsure)
            self.unsure = None
        self.sim_at = world.pos

    # --- inside ------------------------------------------------------------------
    def _tell(self, x, y, heading):
        self.rover = (x, y, heading)
        if self.send_pose:
            self.send_pose(x, y, heading)

    def _move(self, world, cell):
        area = world.here
        if not (0 <= cell[0] < area.w and 0 <= cell[1] < area.h):
            return "off the simulation's map"
        if area.blocked(*cell):
            return "rock or storm in the simulation"
        planned = world.pos
        world.pos = cell
        world._arrive()                 # what World.move does after setting pos, minus spend()
        world.record("lidar_fix", planned=planned, measured=cell)
        self.fixes.append((planned, cell))
        print(f"[lidar] the simulation's rover moved from the planned {_c(planned)} to "
              f"{_c(cell)}, where the LiDAR measured it")
        return None

    def _wrap_goto(self):
        nav, original = self.nav, self.nav.goto
        measured_result = type("MeasuredResult", (nav.Result,), {"advice": property(_advice)})

        def goto(world, x, y, *args, **kwargs):
            self.fixes = []
            r = original(world, x, y, *args, **kwargs)
            if self.fixes:
                planned, real = self.fixes[-1]
                # `goto` fills `at` before its last rover pause, so it holds the planned cell.
                if r.at == planned:
                    r.at = real
                if r.stopped == planned:
                    r.stopped = real
                if r.beside and abs(real[0] - r.beside[0]) + abs(real[1] - r.beside[1]) != 1:
                    r.beside = None
                r.lidar = (planned, real)
                r.__class__ = measured_result
            return r

        self.restore = lambda: setattr(nav, "goto", original)
        nav.goto = goto


def _advice(r):
    """The simulation's own advice, with one sentence first saying the LiDAR moved it."""
    base = type(r).__mro__[1].advice.fget(r)
    planned, real = r.lidar
    n = abs(planned[0] - real[0]) + abs(planned[1] - real[1])
    note = (f"the rover's LiDAR measured it at {_c(real)}, {n} cell{'s' * (n != 1)} from the "
            f"{_c(planned)} the drive planned. Your map now shows where it really is; plan "
            f"from there.")
    return f"{note} {base}" if base else note
