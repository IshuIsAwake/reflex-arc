"""Where the rover should be after a command. No hardware here.
Cells are (x, y) with N at y-1, as in the game, and headings go clockwise N=0 E=1 S=2 W=3.

    relative  F B L R   forward a cell, back a cell, turn left 90, turn right 90
    absolute  N E S W   the game's route file: face that way (the short way round), then F"""

from dataclasses import dataclass

HEADING_NAMES = ("N", "E", "S", "W")
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # indexed by heading, the same as the game's nav.DIRS
RELATIVE = ("F", "B", "L", "R")
COMMANDS = RELATIVE + HEADING_NAMES


@dataclass(frozen=True)
class Pose:
    x: int
    y: int
    heading: int  # 0..3, clockwise from N

    def __str__(self):
        return f"({self.x},{self.y}) facing {HEADING_NAMES[self.heading]}"


def parse(text):
    """'F, R, L, F F' or 'forward right left forward forward' -> ['F','R','L','F','F'].
    Anything else raises: a dropped command would drive the rest from the wrong cell."""
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
    """Signed quarter-turns from `heading` to `target`, the short way. +1 is right; a U-turn is +2."""
    d = (target - heading) % 4
    return d - 4 if d == 3 else d


def primitives(cmd, heading):
    """What the motors do for one command from `heading`: a list of L, R, F, B."""
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


def to_json(pose):
    """A pose as the link sends it: {"x": 3, "y": -2, "heading": "E"}."""
    return {"x": pose.x, "y": pose.y, "heading": HEADING_NAMES[pose.heading]}


def from_json(d):
    """The pose a link message carries."""
    return Pose(d["x"], d["y"], HEADING_NAMES.index(d["heading"]))
