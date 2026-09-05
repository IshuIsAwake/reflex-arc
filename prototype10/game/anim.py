"""Replaying a drive that has already happened, one cell at a time.

Nothing here slows the rover down. `nav.goto` finishes in one go and must -- the model
has to be handed the true outcome in the same breath as the call. So the world jumps,
`nav` writes down what it did as `(kind, payload)`, and this plays it back afterwards.
Otherwise a goto through fog reads as teleporting.

    plan     the route A* believed in, in yellow, drawn cell by cell
    step     the rover moving, fog opening as it goes
    block    the cell that refused -- flashed, then the yellow is torn up
    probe    `distance` only, in blue: priced, never driven

The frame after `block` is the interesting one: the yellow ran through an outcrop nobody
had seen, and it comes back a different shape. That is the fog lying, made visible.
"""

import settings as S


def frames(timeline):
    """Flatten a nav timeline into (kind, payload, seconds) frames.

    A `plan` of forty cells becomes forty frames each showing one more cell, so the
    route draws itself rather than appearing. Cheap: this is built once when the reel
    is loaded, never per frame.
    """
    out = []
    for kind, data in timeline:
        if kind == "start":
            out.append(("at", data, 0.0))
        elif kind == "plan":
            out += [("plan", data[:n], S.ANIM_PLAN) for n in range(1, len(data) + 1)]
        elif kind == "probe":
            out += [("probe", data[:n], S.ANIM_PROBE) for n in range(1, len(data) + 1)]
        elif kind == "step":
            out.append(("step", data, S.ANIM_STEP))
        elif kind == "block":
            # The route does not blink out, it **retracts**: the far end withdraws a
            # cell at a time back to the rover, then the next plan draws outward from
            # there. Clearing it in one frame was correct and read as a glitch; pulling
            # it back reads as the planner giving up on ground it had committed to.
            out.append(("block", data, S.ANIM_BLOCK))
            out.append(("prune", None, S.ANIM_PRUNE))
    return out


class Reel:
    """One drive at a time, drawn out of `world.reel`.

    Everything on it is display state and none of it is ever read back into the world.
    If this class stopped existing the game would still be correct, just instant.
    """

    def __init__(self, world):
        self.world = world
        self.frames = []
        self.i = 0
        self.wait = 0.0
        self._clear()

    def _clear(self):
        self.frames, self.i, self.wait = [], 0, 0.0
        self.at = None        # where the rover is drawn, or None to use world.pos
        self.plan = []        # the route being believed in, yellow
        self.probe = []       # the route being priced, blue
        self.trail = []       # cells driven so far this reel
        self.bump = None      # the cell that refused, flashed
        self.hidden = set()   # revealed already, held shut until the drive reaches it

    @property
    def busy(self):
        return self.i < len(self.frames) or bool(self.world.reel)

    def tick(self, dt):
        """Advance by `dt` seconds. Call once a frame; it is the only thing driving it."""
        if self.i >= len(self.frames):
            if not self.world.reel:
                if self.frames:
                    self._clear()     # the last one just finished
                return
            self._load(self.world.reel.pop(0))

        self.wait -= dt
        # A long dt -- a stall, or a slow model turn holding the loop -- catches up
        # rather than playing in slow motion afterwards.
        while self.wait <= 0 and self.i < len(self.frames):
            kind, data, secs = self.frames[self.i]
            self._apply(kind, data)
            self.i += 1
            self.wait += max(secs, 1e-4)

    def skip(self):
        """Drop everything queued and show the world as it already is.

        Nothing is lost: the drive happened the moment the skill was called, and this
        only stops drawing the journey to it.
        """
        self.world.reel.clear()
        self._clear()

    def _load(self, timeline):
        self._clear()
        self.frames = frames(timeline)
        # Everything this call revealed starts hidden and is handed back as the reel
        # reaches it. Without it the fog is already gone before the rover sets off.
        self.hidden = {c for kind, d in timeline if kind == "step" for c in d[1]}

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
        elif kind == "prune":
            # One cell off the far end per frame, re-queueing itself until the route
            # ends where the rover is actually standing. What is left is ground it
            # reached; what withdrew is the part of the guess that was wrong.
            if len(self.plan) > 1 and self.plan[-1] != self.at:
                self.plan = self.plan[:-1]
                self.frames.insert(self.i + 1, ("prune", None, S.ANIM_PRUNE))

    # --- what the renderer asks -----------------------------------------
    def veiled(self, cell):
        """Is this cell fog *for drawing purposes*, even though the world has seen it?"""
        return cell in self.hidden

    def where(self, fallback):
        return self.at or fallback
