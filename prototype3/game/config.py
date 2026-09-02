"""The arena and the palette. Tunable numbers live in settings.py.

    .  regolith, walkable      #  rock outcrop, impassable
    H  base pad, solid         @  where the rover lands (becomes '.' on load)

Nothing else is wired up, and the prompt may only promise what is.

No rim wall, deliberately: off the grid already reads as "#" through `nav.known`, so the
edge cells stay walkable and aiming at the far edge is a journey rather than a refusal.
Prototype 1 walled its areas and lost 22% of gemma's calls to the border.
"""

# --- display ---------------------------------------------------------------
# 50 x 50 at 17px fits on screen without scrolling. `render.viewport` centres a small
# area and follows a big one, so raising TILE just starts it scrolling.
TILE = 17
VIEW_W = 50
VIEW_H = 50
HUD_H = 110
FPS = 60

# --- palette: martian red-brown and black ----------------------------------
VOID = (8, 7, 7)           # behind everything
REGOLITH = (124, 70, 49)      # ground you are standing near
REGOLITH_DIM = (79, 45, 32)   # ...ground you have seen and walked away from
# Rock must never be as dark as fog. "There is a rock there" and "I have never been
# there" are the one distinction this prototype is about, and at (30,22,19) against
# (13,11,11) they were the same black on screen.
ROCK = (74, 55, 48)        # outcrop, lit
ROCK_DIM = (52, 38, 33)    # outcrop, remembered
FOG = (12, 10, 11)         # never seen. Effectively the void, and nothing else is
GRIT = (101, 57, 40)       # pebbles, darker than the ground
GRIT_LIT = (146, 86, 61)   # ...and lighter. Both low-contrast on purpose

BASE = (178, 180, 186)     # the landing pad, pale metal against everything natural
BASE_DIM = (108, 110, 116)
ROVER = (228, 242, 247)    # a dot. Pale, because red would vanish into the ground
ROVER_RING = (16, 22, 26)

INK = (233, 227, 221)      # text on the dark side
MUTED = (150, 138, 130)
FAINT = (58, 44, 38)       # cell edges, panel rules
MARK = (94, 206, 214)      # your X. Cyan is the one hue the ground cannot supply
PATH = (92, 152, 224)      # a route being priced by `distance` -- blue, costs nothing
PLAN = (226, 182, 72)      # ...and one being driven by `goto` -- yellow, costs steps
BUMP = (240, 118, 96)      # the cell that refused, flashed as the plan is torn up
WALKED = (167, 100, 69)    # ...and the ground it actually covered, under it
GOOD = (116, 202, 134)
BAD = (232, 100, 88)

# --- the chat pane: black, and not a game ----------------------------------
CHAT_BG = (10, 10, 12)
CHAT_TEXT = (216, 214, 210)
CHAT_MUTED = (118, 118, 124)
CHAT_RULE = (40, 40, 46)
CHAT_OPERATOR = (122, 170, 236)   # your side, so a coached day always shows
CHAT_PLANNER = (238, 236, 232)    # what gemma chose to say
CHAT_THINK = (106, 106, 114)      # ...and what it only thought
CHAT_SKILL = (206, 172, 100)      # a call going out
CHAT_RESULT = (156, 196, 172)     # ...and what came back
CHAT_GOOD = (122, 202, 142)
CHAT_BAD = (234, 112, 96)

ARENA_NAME = "Jezero flats"

# --- the arena -------------------------------------------------------------
# 410 rock of 2500 (16.4%), one connected region. Twenty boulders of sixteen cells and
# ten of nine, none touching, at least two clear cells apart so the flood fill can tell
# them apart and so can an eye. Generator seed 78.
#
# Boulders are allowed on the outer ring: keeping them off left a clear lap round the
# arena, and gemma ping-ponged along that free perimeter for 439 steps.
#
# Identity is recovered by flood fill, not written down, so every component must be
# exactly nine or sixteen -- a merge or a split fails outright.
#
# Run test_world.py after editing. It also fails on a sealed pocket, which is invisible
# until someone has wasted a day walking to it.
ARENA = [
    ".........................................###......",
    "...................##...................###.......",
    "...................##..##..............#####......",
    "..................###..#####..............##......",
    "..................#.#..####...............##......",
    "........................###...............#.......",
    ".............#............#...................#...",
    "............##............#........#.........##...",
    "............#####............#.....##......####...",
    "#.#.........#####............##....##....######...",
    "###..........#..##.........######..##.......###...",
    "##.........................#.####..#..............",
    "##...........................##....#..............",
    ".............######...............................",
    ".............####.....#...........................",
    ".............####....###..........................",
    "...............##..#.###..........................",
    "..#................#####..........................",
    ".###...............###............................",
    ".##.....#......................................#..",
    "###....####...................................####",
    ".......###....................................####",
    ".......#......#...................................",
    ".............##...................................",
    "..........##.###............................####..",
    "....####..####...........@..................####..",
    "...#####..####..........HHH.....###..........####.",
    "...#####................HHH......####........###..",
    ".....#...........................####.........#...",
    ".....#....#######................##.#.............",
    "................##...............##........#......",
    "...........................................#......",
    ".............#............................###.....",
    "...........#####...#..##.........###......###.....",
    "...........#####..#####....#....#####......###....",
    ".........#####....####....##......#.......###.....",
    "...................##....####..............##.....",
    "...................##...####......................",
    ".............#...........####..................###",
    "............###.#...........#..................###",
    ".....#......#####.......................##.##...##",
    ".....##......####.......................#####...#.",
    "....####.....##........##...............######....",
    "....##...............######...............#.......",
    "......................######......................",
    "............##........#...#.......................",
    ".........#...#####................................",
    ".....#..##...#####................................",
    ".....##.###...###.................................",
    "....#######...#...................................",
]

# Dead centre. The pad sits immediately south -- behind the rover, where it landed.
SPAWN = (25, 25)
