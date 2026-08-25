"""Every knob worth turning. Change things here, not in the code.

None of these are tuned. They are guesses, and you cannot balance a world you have
not watched anything play.
"""

# --- time ------------------------------------------------------------------
# "human" -- a day is DAY_SECONDS of wall clock, which is the nicer way to play.
# "gemma" -- a day is DAY_STEPS actions and the clock becomes a stopwatch that only
#            watches. A model's thinking time then costs it nothing, so the day is
#            the same size on any machine and two runs actually compare.
DAY_MODE = "human"
DAY_SECONDS = 300
DAY_STEPS = 400         # one per tile walked, one per interact / play / buy

TIME_SCALE = 1.0        # 2.0 makes the day and every cooldown run twice as fast
VISION_RADIUS = 3       # how far you see in an area whose map you do not have

MOVE_DELAY_MS = 220     # hold a direction this long before it repeats
MOVE_REPEAT_MS = 70     # then one step every this long

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so in a dense maze it will walk
# into a wall it could not have known about every few cells. This is how many
# times one call quietly replans around that before handing control back with
# BLOCKED. Every wall found on the way is reported either way, so a higher number
# costs steps and saves model calls. 0 gives strict one-surprise-per-call.
NAV_REPLANS = 5

# --- economy ---------------------------------------------------------------
START_COINS = 0
TRAP_PENALTY = 10       # coins lost falling into a pit, on top of the walk home

# game -> (cooldown, payout, win chance). The cooldown is seconds in human mode and
# steps in gemma mode -- same number, whichever the day is measured in. Otherwise a
# slow model would recover its cooldowns for free while it was thinking.
#
# In gemma mode a cooldown is therefore paid in walking, not waiting: ten steps of
# going somewhere is the price of the next cartpole run. That makes the budget
# something it can arithmetic its way around ahead of time, which is the point.
# Run `python game/economy.py` to see what these are actually worth per step.
GAMES = {
    "cartpole": (10, 10, 0.99),
    "flappy": (25, 30, 0.85),
    "snake": (50, 165, 0.40),
}

# counter -> what it stocks. An antidote burns up saving you from one snake pit.
# The tool pouch is a one-off upgrade and the only reason the treasure is reachable.
SHOPS = {
    "shop": {
        "flappy_key": 40,
        "savana_key": 60,
        "antidote": 100,
    },
    "tribe": {
        "tool_pouch": 300,
    },
}

POUCH = 1           # antidotes you can carry
POUCH_UPGRADED = 3  # ...and after buying tool_pouch. The vault costs exactly this.

# (area, cell) -> coins. Must line up with the '$' and '*' tiles in the maps.
BAGS = {
    ("plaza", (19, 1)): 30,       # end of the north maze
    ("savana", (27, 5)): 50,
    ("savana2", (4, 17)): 1000,   # the vault: three rings of pits, three antidotes
}

# lost bags hand over their area's map, and these extras on top
LOST_BAG_ITEMS = {
    ("savana2", (1, 1)): "antidote",
}
