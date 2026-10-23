"""The arena and the palette. Tunable numbers live in settings.py.

    .  regolith, walkable      #  rock outcrop, impassable
    H  base pad, solid         @  where the rover lands (becomes '.' on load)

Nothing else is wired up, and the prompt may only promise what is.

No rim wall, deliberately: off the grid already reads as "#" through `nav.known`, so the
edge cells stay walkable and aiming at the far edge is a journey rather than a refusal.
Prototype 1 walled its areas and lost 22% of gemma's calls to the border.
"""

# --- display ---------------------------------------------------------------
# Either arena at 17px is on screen without scrolling -- 50 x 50 is 850px, the wider of
# the two. `render.viewport` centres a small area and follows a big one, so raising TILE
# just starts it scrolling. VIEW_W and VIEW_H are set by `use()` from the arena itself,
# never written down, so a resize cannot leave the window the wrong shape.
TILE = 30
HUD_H = 96
FPS = 60

# --- palette: Harsh's charcoal and muted teal, with 10d's rock -------------
VOID = (15, 17, 20)           # behind everything
REGOLITH = (124, 70, 49)      # ground you are standing near
REGOLITH_DIM = (79, 45, 32)   # ...ground you have seen and walked away from
# Rock must never be as dark as fog. "There is a rock there" and "I have never been
# there" are the one distinction this prototype is about, and at (30,22,19) against
# (13,11,11) they were the same black on screen.
ROCK = (74, 55, 48)        # outcrop, lit
ROCK_DIM = (52, 38, 33)    # outcrop, remembered
FOG = (23, 26, 29)         # never seen. Effectively the void, and nothing else is
GRIT = (78, 39, 30)       # pebbles, darker than the ground
GRIT_LIT = (187, 98, 59)   # ...and lighter. Both low-contrast on purpose

BASE = (105, 170, 181)     # the landing pad, pale metal against everything natural
BASE_DIM = (62, 101, 110)
ROVER = (228, 242, 247)    # a dot. Pale, because red would vanish into the ground
ROVER_RING = (16, 22, 26)

INK = (213, 217, 221)      # text on the dark side
MUTED = (157, 165, 172)
FAINT = (48, 54, 60)       # cell edges, panel rules
MARK = (111, 190, 183)      # your X. Cyan is the one hue the ground cannot supply
PATH = (112, 153, 184)      # a route being priced by `distance` -- blue, costs nothing
PLAN = (92, 152, 224)       # route driven by `goto` -- blue, costs steps
GOTO_ROUTE = (226, 182, 72) # yellow dots for the route driven by `goto`
BUMP = (240, 118, 96)      # the cell that refused, flashed as the plan is torn up
INTEREST = (186, 140, 236) # a square: something worth a closer look. No other violet here
WALKED = (167, 100, 69)    # ...and the ground it actually covered, under it
GOOD = (115, 196, 151)
BAD = (210, 126, 119)

# The sky, washed over the arena by phase: none by day, NIGHT at night, and dawn and dusk
# fading between the two over their own length.
NIGHT = (16, 18, 34)
NIGHT_ALPHA = 170          # how heavy the wash is at its darkest, of 255

# --- the chat pane: black, and not a game ----------------------------------
CHAT_BG = (23, 26, 30)
CHAT_TEXT = (213, 217, 221)
CHAT_MUTED = (157, 165, 172)
CHAT_RULE = (49, 55, 62)
CHAT_OPERATOR = (132, 174, 201)   # your side, so a coached day always shows
CHAT_PLANNER = (213, 217, 221)    # what gemma chose to say
CHAT_THINK = (151, 153, 173)      # ...and what it only thought
CHAT_SKILL = (190, 177, 148)      # a call going out
CHAT_RESULT = (111, 190, 183)     # ...and what came back
CHAT_GOOD = (115, 196, 151)
CHAT_BAD = (210, 126, 119)

ARENA_NAME = "Jezero flats"

# --- the arenas ------------------------------------------------------------
# Two, and the size is the only thing that differs on purpose. `--arena 50` picks the
# old one; everything else in the game reads `ARENA` and does not care which is loaded.
#
# The 30x30 is the size the real classroom arena will be, so it is the default. It is
# also small enough that three effects went flat on it -- `distance` is optimistic by at
# most 4 cells against 12, `goto` returns BLOCKED only when driven straight at rock, and
# `rle` costs 1.31x the grid against 3.8x. The 50x50 is where those are measurable.
#
# Run test_world.py after editing either. It fails on a sealed pocket, which is
# invisible until someone has wasted a day walking to it.

# 74 rock of 900 (8.2%), one connected region. Ten formations: six of six cells, three
# of eight, and exactly one of twelve. At least two clear cells between any two, so the
# flood fill and an eye agree on where one ends.
#
# **The largest is a C, four wide and six tall, open along its east face.** Every other
# formation here is a rectangle, and a rectangle is a question about merging rows of
# `sight.rle` and nothing else. The C is not: it is the one shape whose size cannot be
# read off a single row, and it is the one the geology question has as its answer.
#
# It is also the only concavity on the map. A route planned west across its mouth goes
# through the spine, which is fog until it is driven at, and the detour is round one of
# the bars -- so `goto` can come back BLOCKED for the shape of the ground rather than
# for having been pointed at a wall. The old 30 had nothing that did that.
#
# Formations are allowed on the outer ring: keeping them off left a clear lap round the
# arena, and gemma ping-ponged along that free perimeter for 439 steps.
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

# 440 rock of 2500 (17.6%), one connected region. One formation of thirty, twenty of
# sixteen and ten of nine, none touching, two clear cells apart. Generator seed 78, plus
# the thirty placed by hand.
#
# The thirty is a **C opening east** at x30-39, y15-21, and it is concave on purpose.
# Convex boulders two cells apart get walked round in silence, so `goto` almost never
# returned BLOCKED and no route was ever expensive. Crossing this one's mouth costs 24
# steps where the straight line is 6.
#
# It is also the only formation of its size, which is what makes "the largest formation"
# answerable. Twenty tied sixteens made it a question with no answer and it was asked
# four times before that was noticed; `test_the_geology_is_exactly_what_was_authored`
# now guards both arenas so it cannot come back.
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

# --- interests -------------------------------------------------------------
# What the arena hides: `cell: (what is there, steps of work to examine it)`. Nobody knows
# where they are, the desk included, and one shows on her map only once the rover has seen
# it. Examining one is what says what it is. Objectives are the desk's, placed during the
# mission (`world.place_objective`), so none are written here.
#
# **Not characters in the arena strings.** They are laid over `Area.at` instead, so the
# rows above stay pure ground and rock -- one map, edited in one place -- and finishing
# one is a deletion rather than an edit to the terrain.
INTERESTS_30 = {
    (24, 6): ("signs of past water: cracked, layered sediment", 40),
    (8, 20): ("abnormal humidity just under the surface", 15),
    (2, 28): ("a vein of a rare mineral", 60),
}
# Six on the 50, so a multi-sol mission has something to find after the first sol. The
# fourth sits inside the C, reached only through its mouth on the east side.
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

# Two defaults, because they answer different questions and running them together
# broke seven suites at once. This one is what anything gets that does not ask --
# the tests and the probes, whose coordinates are all written against the 30.
DEFAULT_ARENA = "30"
# ...and this is what `main.py` opens on. The 50, from prototype 11: every run since
# 14 Oct has been played on it. The 30 is still the size the real arena will be.
APP_ARENA = "50"


def use(name):
    """Load an arena. `main.py` calls this before anything reads the module.

    The spawn is dead centre of each and the pad sits immediately south, behind the
    rover, where it landed. The view size comes off the rows rather than being written
    down beside them, which is how the two used to disagree.
    """
    global ARENA, SPAWN, VIEW_W, VIEW_H, INTERESTS
    ARENA, SPAWN, INTERESTS = ARENAS[name]
    VIEW_H, VIEW_W = len(ARENA), len(ARENA[0])


use(DEFAULT_ARENA)
