"""Draws a drive that has already happened, one cell at a time. nav.goto finishes at
once and records what it did as (kind, payload) steps; this plays them back on screen:

    plan     the route A* believed in, yellow
    step     the rover moving, fog opening as it goes
    block    the cell that refused; then the yellow route pulls back
    probe    a `distance`, blue: priced, never driven
    work     an `execute`, a step at a time
"""

import settings


def frames(timeline):
    """A nav timeline as (kind, payload, seconds) frames, one cell more of a route each frame."""
    out = []
    for kind, data in timeline:
        if kind == "start":
            out.append(("at", data, 0.0))
        elif kind == "plan":
            out += [("plan", data[:n], settings.ANIM_PLAN) for n in range(1, len(data) + 1)]
        elif kind == "probe":
            out += [("probe", data[:n], settings.ANIM_PROBE) for n in range(1, len(data) + 1)]
        elif kind == "step":
            out.append(("step", data, settings.ANIM_STEP))
        elif kind == "work":
            cell, n = data
            out += [("work", (cell, i, n), settings.ANIM_STEP) for i in range(1, n + 1)]
        elif kind == "block":
            # The route pulls back a cell at a time to the rover, rather than vanishing.
            out.append(("block", data, settings.ANIM_BLOCK))
            out.append(("prune", None, settings.ANIM_PRUNE))
    return out


def destination(timeline):
    """Where a drive is headed: the end of its first plan. A `distance` has none."""
    for kind, data in timeline:
        if kind == "plan" and data:
            return data[-1]
    return None


class Reel:
    """One drive at a time from `world.reel`. Display only: nothing here changes the world."""

    def __init__(self, world):
        self.world = world
        self.frames = []
        self.i = 0
        self.wait = 0.0
        self.destination = None  # for MAP_LABELS; kept after the drive, to say REACHED
        self._clear()

    def _clear(self):
        self.frames, self.i, self.wait = [], 0, 0.0
        self.at = None  # where the rover is drawn, or None to use world.pos
        self.plan = []  # the route being believed in, yellow
        self.probe = []  # the route being priced, blue
        self.trail = []  # cells driven so far this reel
        self.bump = None  # the cell that refused, flashed
        self.work = None  # (cell, steps done, steps in all) while work is drawn
        self.hidden = set()  # revealed already, but kept fogged until the drive reaches it

    @property
    def busy(self):
        return self.i < len(self.frames) or bool(self.world.reel)

    def tick(self, dt):
        """Advance by `dt` seconds. Called once a frame."""
        if self.i >= len(self.frames):
            if not self.world.reel:
                if self.frames:
                    self._clear()  # the last one just finished
                return
            self._load(self.world.reel.pop(0))

        self.wait -= dt * settings.ANIM_SPEED
        # A long frame catches up rather than playing in slow motion afterwards.
        while self.wait <= 0 and self.i < len(self.frames):
            kind, data, secs = self.frames[self.i]
            self._apply(kind, data)
            self.i += 1
            self.wait += max(secs, 1e-4)

    def skip(self):
        """Drop everything queued and show the world as it already is."""
        for timeline in self.world.reel:
            self.destination = destination(timeline)
        self.world.reel.clear()
        self._clear()

    def _load(self, timeline):
        self._clear()
        self.frames = frames(timeline)
        self.destination = destination(timeline)
        # What this drive revealed stays fogged until the drawn rover reaches it.
        self.hidden = set()
        for kind, data in timeline:
            if kind == "step":
                cell, revealed = data
                self.hidden.update(revealed)

    def _apply(self, kind, data):
        if kind == "at":
            self.at = data
        elif kind == "plan":
            self.plan, self.probe, self.bump = data, [], None
        elif kind == "probe":
            self.probe = data
        elif kind == "step":
            cell, revealed = data
            self.at = cell
            self.trail.append(cell)
            self.hidden.difference_update(revealed)
        elif kind == "block":
            self.bump = data
        elif kind == "work":
            self.work = data
        elif kind == "prune":
            # One cell off the far end each frame, until the route ends where the rover is.
            if len(self.plan) > 1 and self.plan[-1] != self.at:
                self.plan = self.plan[:-1]
                self.frames.insert(self.i + 1, ("prune", None, settings.ANIM_PRUNE))

    @property
    def destination_status(self):
        if self.destination == self.where(self.world.pos):
            return "REACHED"
        if self.bump:
            return "BLOCKED / REPLANNING"
        if self.busy:
            return "APPROACHING"
        return "STOPPED"

    def veiled(self, cell):
        """Fogged on screen, though the world has already seen it?"""
        return cell in self.hidden

    def where(self, fallback):
        return self.at or fallback
