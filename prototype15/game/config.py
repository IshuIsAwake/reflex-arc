"""The arenas and the colours. The numbers people tune live in settings.py.

    .  ground, drivable      #  rock, impassable
    H  the landing pad       @  where the rover lands (ground once loaded)

There is no wall round the edge: the outer cells are ordinary ground."""

# VIEW_W and VIEW_H are set by use() from the arena itself.
TILE = 30
HUD_H = 96
FPS = 60

# Colours
VOID = (15, 17, 20)  # behind everything
REGOLITH = (124, 70, 49)  # ground near the rover
REGOLITH_DIM = (79, 45, 32)  # ground seen and left behind
# Rock must never look as dark as fog: "rock there" and "never been there" must differ.
ROCK = (74, 55, 48)  # outcrop, lit
ROCK_DIM = (52, 38, 33)  # outcrop, remembered
FOG = (23, 26, 29)  # never seen
GRIT = (78, 39, 30)  # pebbles, darker than the ground
GRIT_LIT = (187, 98, 59)  # ...and lighter

BASE = (105, 170, 181)  # the landing pad
BASE_DIM = (62, 101, 110)
ROVER_RING = (16, 22, 26)

INK = (213, 217, 221)  # text
MUTED = (157, 165, 172)
FAINT = (48, 54, 60)  # cell edges, panel rules
PATH = (112, 153, 184)  # a route priced by `distance`
PLAN = (92, 152, 224)  # a route driven by `goto`
GOTO_ROUTE = (226, 182, 72)  # yellow dots for the route driven by `goto`
BUMP = (240, 118, 96)  # the cell that refused
INTEREST = (186, 140, 236)  # an interest
WALKED = (167, 100, 69)  # the ground a drive actually covered
GOOD = (115, 196, 151)
BAD = (210, 126, 119)
AMBER = (190, 177, 148)  # headings, and a call going out
CYAN = (111, 190, 183)  # your X marks, the bars, and what a call brought back
PANEL = (30, 34, 39)  # the cards
BORDER = (53, 60, 67)

# The night sky, washed over the arena: none by day, NIGHT at night, fading at dawn and dusk.
NIGHT = (16, 18, 34)
NIGHT_ALPHA = 170  # how heavy the wash is at its darkest, of 255

# The chat pane
CHAT_BG = (23, 26, 30)
CHAT_RULE = (49, 55, 62)
CHAT_OPERATOR = (132, 174, 201)  # the operator
CHAT_THINK = (151, 153, 173)  # ...and what it only thought

ARENA_NAME = "Jezero flats"

# The arenas. Only the size differs. test_world fails on a sealed pocket of ground,
# so run it after editing either.

# 74 rock of 900, in ten formations at least two cells apart. The largest is a C opening
# east, the only concave shape, so `goto` can come back BLOCKED for the shape of the ground.
FLATS_30 = [
    "..............................",
    "..............................",
    "....................##........",
    ".........###........##........",
    ".........###........##........",
    "....................##........",
    "..............................",
    ".............##...............",
    ".............##...............",
    ".............##...............",
    "........................##....",
    "...####.................##....",
    "...#....................##....",
    "...#..........................",
    "...#..........................",
    "...#...........@..............",
    "...####.......HHH.............",
    "..............HHH........##...",
    ".........................##...",
    ".........................##...",
    ".................###.....##...",
    ".................###..........",
    "..##..........................",
    "..##..........................",
    "..##......####................",
    "..........####................",
    ".....................###......",
    ".....................###......",
    "..............................",
    "..............................",
]

# 440 rock of 2500. One formation of thirty (a C opening east at x30-39, y15-21), so
# "the largest formation" has exactly one answer.
FLATS_50 = [
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
    ".............####....###......##########..........",
    "...............##..#.###......##..................",
    "..#................#####......##..................",
    ".###...............###........##..................",
    ".##.....#.....................##...............#..",
    "###....####...................##..............####",
    ".......###....................##########......####",
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

# Interests the arena hides: cell -> (what is there, steps of work to examine it).
# They lie over the ground rather than being characters in the rows above.
INTERESTS_30 = {
    (24, 6): ("signs of past water: cracked, layered sediment", 40),
    (8, 20): ("abnormal humidity just under the surface", 15),
    (2, 28): ("a vein of a rare mineral", 60),
}
# Six on the 50; the fourth is inside the C, reached only through its mouth.
INTERESTS_50 = {
    (40, 10): ("signs of past water: cracked, layered sediment", 40),
    (14, 30): ("abnormal humidity just under the surface", 15),
    (9, 42): ("a vein of a rare mineral", 60),
    (36, 18): ("methane at ground level, well above background", 30),
    (44, 44): ("an iron meteorite, half buried", 45),
    (6, 4): ("a ripple pattern pressed into the rock", 20),
}

ARENAS = {"30": (FLATS_30, (15, 15), INTERESTS_30),
          "50": (FLATS_50, (25, 25), INTERESTS_50)}

# What the tests get. Their coordinates are written against the 30.
DEFAULT_ARENA = "30"
# What main.py opens on.
APP_ARENA = "50"


def use(name):
    """Load an arena. The rover lands dead centre with the pad just south of it."""
    global ARENA, SPAWN, VIEW_W, VIEW_H, INTERESTS
    ARENA, SPAWN, INTERESTS = ARENAS[name]
    VIEW_H, VIEW_W = len(ARENA), len(ARENA[0])


use(DEFAULT_ARENA)
