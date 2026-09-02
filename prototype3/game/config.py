"""The arena and the palette. Tunable numbers live in settings.py.

Legend -- deliberately three characters, because the system prompt is only allowed to
promise what is actually wired up:

    .  regolith, walkable      #  rock outcrop, impassable
    H  base pad, solid         @  where the rover lands (becomes '.' on load)

Ridges, craters, dust storms, quakes, sample sites and Ingenuity are **not here yet**.
Adding a tile gemma can see and cannot use is the failure prototype 1 measured: told to
go to the shop, it arrived in one call and spent the next seven wandering, because
there was nothing to *do* there. A bare arena is the honest version of this pass.

**There is no rim wall, and that is deliberate.** Prototype 1 walled its areas and
22% of gemma's calls were wasted on it -- `goto` is told to aim far, the far thing was
the border, and a known wall is deliberately UNREACHABLE. Off the grid already reads as
"#" through `nav.known`, so the boundary needs no tiles and the edge cells stay
walkable. Aiming at the far edge is a real journey rather than a guaranteed refusal --
though individual edge cells are still rock here and there, the way anywhere is.
"""

# --- display ---------------------------------------------------------------
# 50 x 50 at 17px is 850px of arena, so the whole thing is on screen at once and
# nothing scrolls. `render.viewport` still centres a small area and follows a big
# one, so raising TILE just starts it scrolling -- there is nothing to rewrite.
TILE = 17
VIEW_W = 50
VIEW_H = 50
HUD_H = 110
FPS = 60

# --- palette: martian red-brown and black ----------------------------------
VOID = (8, 7, 7)           # behind everything
REGOLITH = (124, 70, 49)      # ground you are standing near
REGOLITH_DIM = (79, 45, 32)   # ...ground you have seen and walked away from
# Rock is dark, but it must never be as dark as fog. The first pass had outcrop at
# (30,22,19) against fog at (13,11,11) and on screen they were the same black: you
# could not tell "there is a rock there" from "I have never been there", which is the
# one distinction this whole prototype is about. Stone reads as stone; absence is
# reserved for the fog.
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
# **410 rock of 2500 cells (16.4%), 2084 walkable, one connected region. A boulder
# field, and nothing else.** Twenty large boulders of sixteen cells and ten medium of
# nine, none of them touching. Rewritten 2026-08-30; reproducible at generator seed 78.
#
# **Two arenas have been thrown away here, and both for the same reason.** The first
# was 517 rock of uniform texture, whose comment in this spot claimed boulder fields
# thickening toward the rim -- measured, 21% in the outer ring against 20% in the core.
# The second put twelve boulders among five long ridges at 9.6%. Looked at on screen
# the ridges read as drawn lines rather than geology, and the four-cell boulders read
# as specks. Neither is a thing worth asking a model to recognise, which is what the
# arena is now for.
#
# **Nothing names a boulder for gemma.** `sight.things()` reports only the landing pad.
# Whether a 4B model can pick a compact lump out of the grid, count the lumps and say
# roughly where they are is the open question; FINDINGS measured it failing to *index*
# a grid, and recognising a shape is a different skill nobody has tested. So the shapes
# have to be honest: bounding-box fill between 0.45 and 0.75, which rules out both a
# straggle and the filled rectangle a generator reaches for.
#
# **Two clear cells between any two boulders, in Chebyshev.** One is enough for the
# flood fill to separate them and not enough for a human eye: at a single cell gap a
# run of boulders reads as one amorphous mass, which is the whole recognition question
# begged. Two costs nothing -- thirty boulders at this size pack comfortably.
#
# **Boulders are allowed on the outer ring.** Keeping them off left a clear lap all the
# way round the arena, and a free perimeter is exactly the highway gemma ping-ponged
# along for 439 steps on 2026-08-29. There is no rim wall here and no rim road either.
#
# **Identity is recovered, not written down** -- flood-fill the rock, read the sizes.
# With no ridges there is no size band and nothing that is terrain-rather-than-boulder,
# so every component must be exactly nine or sixteen and a merge (25) or a split fails
# outright. `test_world.py` asserts all thirty, by size and by a cell each contains.
#
# Run test_world.py after editing this. It flood-fills from the pad and fails on a
# sealed pocket -- prototype 1's version caught two of those, and a sealed pocket is
# invisible until somebody has wasted a day walking to it.
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
