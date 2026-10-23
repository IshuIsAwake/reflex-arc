"""grid -- where the rover should be after a command, and how far off it actually is.

Pure. No motors, no keyboard, no network, so it runs the same on the laptop, the Pi 5
and a Pi 4, and the tests import it without hardware.

The frame is prototype10d's, so a 10d `plan.txt` can be fed in unchanged:
cells are (x, y), N is y-1, and headings go clockwise N=0 E=1 S=2 W=3.

Two kinds of command, because the team speaks both:

  * relative  F B L R   -- forward a cell, back a cell, turn left 90, turn right 90.
                           What a person types: "forward, right, left, forward".
  * absolute  N E S W   -- what 10d's route file holds. The rover faces that way
                           first (turning the short way round), then goes forward one
                           cell. It never assumes a heading it has not been told.

After every command the rover's *expected* pose is compared with its *measured* one.
Two distances, because they answer different questions:

  * Manhattan  |dx| + |dy|      how many N/E/S/W steps it costs to get back on plan.
                                That is A*'s cost, so it is the replanning bill.
  * Chebyshev  max(|dx|, |dy|)  the worst single-axis miss. "Within one cell" is
                                Chebyshev <= 1, a square around the target.

On whole cells they are both zero together, so either one says whether it arrived.
Where they disagree is the useful part: equal means the miss is along one axis
(stopped short, overshot, or slid sideways); Manhattan bigger means it is off on both
axes, which on a skid-steer rover nearly always means the heading went wrong first.

Errors are reported, not corrected (ARCHITECTURE.md). Heading is the exception: a
wrong heading makes every later move wrong, so `check` flags it for a fix-up turn.
"""

from dataclasses import dataclass

HEADING_NAMES = ("N", "E", "S", "W")
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))   # indexed by heading, same as 10d's nav.DIRS
RELATIVE = ("F", "B", "L", "R")
COMMANDS = RELATIVE + HEADING_NAMES


@dataclass(frozen=True)
class Pose:
    x: int
    y: int
    heading: int   # 0..3, clockwise from N

    def __str__(self):
        return f"({self.x},{self.y}) facing {HEADING_NAMES[self.heading]}"


def parse(text):
    """'F, R, L, F F' or 'forward right left forward forward' -> ['F','R','L','F','F'].

    Accepts the words as well as the letters. Anything else raises rather than being
    skipped -- a rover that quietly drops one command drives the rest from the wrong cell.
    """
    words = {"FORWARD": "F", "BACK": "B", "BACKWARD": "B", "LEFT": "L", "RIGHT": "R",
             "NORTH": "N", "EAST": "E", "SOUTH": "S", "WEST": "W"}
    out = []
    for tok in text.replace(",", " ").split():
        t = words.get(tok.upper(), tok.upper())
        if t not in COMMANDS:
            raise ValueError(f"unknown command {tok!r}; use {' '.join(COMMANDS)}")
        out.append(t)
    return out


def turns_to_face(heading, target):
    """Signed quarter-turns from `heading` to `target`, the short way. +1 is right.
    A U-turn is +2 (two rights), so it is always the same two turns.
    """
    d = (target - heading) % 4
    return d - 4 if d == 3 else d


def primitives(cmd, heading):
    """What the motors actually do for one command, given the heading the rover
    believes it has: a list of 'L', 'R', 'F', 'B'. Absolute commands expand to the
    turns that face that way, then one 'F'.
    """
    if cmd in RELATIVE:
        return [cmd]
    q = turns_to_face(heading, HEADING_NAMES.index(cmd))
    return ["R"] * q + ["L"] * -q + ["F"]


def apply(pose, cmd):
    """The pose the rover should be in after `cmd`, if every motion were perfect."""
    x, y, h = pose.x, pose.y, pose.heading
    for p in primitives(cmd, h):
        if p == "L":
            h = (h - 1) % 4
        elif p == "R":
            h = (h + 1) % 4
        else:
            dx, dy = DIRS[h]
            s = 1 if p == "F" else -1
            x, y = x + s * dx, y + s * dy
    return Pose(x, y, h)


