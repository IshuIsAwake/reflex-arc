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
TILE = 17
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
SCOUT = (196, 170, 230)    # ...and the flyer's window -- violet, the one hue neither
                           # the ground, the plan nor the probe already speaks
STORM = (150, 128, 96)     # dust in the air: the regolith's own colour, lifted and pale
STORM_DARK = (112, 94, 68) # ...and the hatching through it, so it reads as weather
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

# 124 rock of 900 (13.8%), one connected region. Twelve boulders of nine cells and
# exactly one of sixteen, none touching, at least two clear cells apart so the flood
# fill can tell them apart and so can an eye. Generator seed 4.
#
# **Every boulder is a square, and only one is 4x4.** A 3x3 cannot be seen from any
# single row of `sight.rle` -- three rows each reading `x7-9 rock` have to be merged --
# so "which formation is largest" is a question about merging rows and nothing else.
#
# Boulders are allowed on the outer ring: keeping them off left a clear lap round the
# arena, and gemma ping-ponged along that free perimeter for 439 steps.
FLATS_30 = [
    "..............................",
    "........................###...",
    "....###.................###...",
    "....###.................###...",
    "....###.......................",
    "..............###.............",
    "..............###.............",
    "..............###.............",
    ".........................###..",
    "###....####..............###..",
    "###....####........###...###..",
    "###....####........###........",
    ".......####........###........",
    "..............................",
    "..............................",
    "...............@..............",
    ".......###....HHH.............",
    ".......###....HHH.............",
    ".......###....................",
    "..............................",
    "..........................###.",
    "..........................###.",
    "..................###.....###.",
    "...###............###.........",
    "...###............###.........",
    "...###...###..................",
    ".........###..................",
    ".........###........###.......",
    "....................###.......",
    "....................###.......",
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

# --- objectives ------------------------------------------------------------
# What the rover is out there to do. `cell: (glyph, priority, step cost)`.
#
# **Not characters in the arena strings.** They are laid over `Area.at` instead, so the
# rows above stay pure ground and rock -- one map, edited in one place, with no new tile
# to declare to the flood-fill or the word table. It also means an objective can be
# completed by deleting it rather than by rewriting a row.
#
# Priority and cost are independent on purpose. Tie them together -- highest priority
# also the most work -- and there is only one sensible order, so the decision collapses
# into reading a column. The interesting choice is a cheap low-priority one nearby
# against an expensive high-priority one across the arena, and that only exists if the
# two axes can disagree.
#
# Both are facts handed over, not judgements: mission control assigns priority and the
# instrument determines the cost. Which to do first, and which to abandon when the sol
# runs short, is the model's.
OBJECTIVES_30 = {
    (24, 6): ("1", "high", 40),
    (8, 20): ("2", "medium", 15),
    (2, 28): ("3", "low", 60),
}
OBJECTIVES_50 = {
    (40, 10): ("1", "high", 40),
    (14, 30): ("2", "medium", 15),
    (9, 42): ("3", "low", 60),
}

ARENAS = {"30": (FLATS_30, (15, 15), OBJECTIVES_30),
          "50": (FLATS_50, (25, 25), OBJECTIVES_50)}

# Two defaults, because they answer different questions and running them together
# broke seven suites at once. This one is what anything gets that does not ask --
# the tests and the probes, whose coordinates are all written against the 30.
DEFAULT_ARENA = "30"
# ...and this is what `main.py` opens on. The 50, because the flyer's window and range
# were swept there: on the 30 a single sortie buys a fifth of the arena.
APP_ARENA = "50"


def use(name):
    """Load an arena. `main.py` calls this before anything reads the module.

    The spawn is dead centre of each and the pad sits immediately south, behind the
    rover, where it landed. The view size comes off the rows rather than being written
    down beside them, which is how the two used to disagree.
    """
    global ARENA, SPAWN, VIEW_W, VIEW_H, OBJECTIVES
    ARENA, SPAWN, OBJECTIVES = ARENAS[name]
    VIEW_H, VIEW_W = len(ARENA), len(ARENA[0])


use(DEFAULT_ARENA)
