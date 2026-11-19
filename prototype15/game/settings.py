"""Every number worth changing. registry.py says which ones the settings screen shows."""

# The day. Only the day has a clock, of wall-clock seconds, and nothing pauses it.
DAY_SECONDS = 600
# The battery, in steps: one per cell driven and one per step of work. Only the pad
# recharges it, overnight. The work costs were balanced for 150; which default to ship is undecided.
BATTERY = 500

TIME_SCALE = 1.0  # 2.0 makes the day's clock run twice as fast
# Sols in a mission; 0 is no limit.
MISSION_SOLS = 0
# Someone is at the desk. On, each phase waits for the desk, which can talk to her and
# answer her radio. Off, every phase moves on by itself. A run with no window starts with it off.
COMMS = True
COMMS_WAIT = 60.0  # seconds the desk is waited for
# What one radio message costs her in battery: the call, and each reply on the open line.
RADIO_STEPS = 5
# A request that never reached the model is asked again after this long.
AUTO_RETRY_SECONDS = 30.0
# Fog lifts in a disc this wide around every cell the rover reaches.
VISION_RADIUS = 2
BASE_REVEAL = 6  # the landing site, opened once on arrival

# The model
MODEL = "gemma4:31b-cloud"
# When a request to MODEL fails it goes here instead, until a probe of MODEL answers
# again. The same as MODEL turns the fallback off.
MODEL_FALLBACK = "gemma4:e4b"
PROBE_SECONDS = 30  # how often MODEL is tried while the fallback answers
PROBE_TIMEOUT = 15  # seconds a one-token probe may take
# Sols on which MODEL is made unreachable on purpose, to show the fallback (--outage N).
OUTAGE_SOLS = ()
OUTAGE_HOST = "http://127.0.0.1:9/api/chat"
OLLAMA_HOST = "http://localhost:11434/api/chat"
MODEL_CTX = 16384  # Ollama defaults to 4096 and truncates silently
MODEL_THINK = False  # a reasoning trace; slow, and no better at reading the map
MODEL_KEEP_ALIVE = "30m"  # keeps the model loaded through the day's pauses
MODEL_TIMEOUT = 600

# Temperature 0: unpinned, the model sometimes wrote its tool call as prose.
# None sends no sampler at all, which is what --think does.
MODEL_TEMP = 0.0
# Sent with every request. It pins the sampler only; the model still can't repeat itself exactly.
MODEL_SEED = 0
SHOW_THINKING = True  # whether the pane shows the reasoning; the tape records it anyway
MAP_LABELS = False  # label the rover's cell and its drive's target on the map

# A starting value: render.layout sets it from the window.
CHAT_W = 990  # pixel width of the pane

# The window opens at the desktop's size less these.
SCREEN_RESERVE_W = 60  # window border and a little air
SCREEN_RESERVE_H = 110  # title bar plus the taskbar

# The turn's two allowances. A turn ends after MOVE_HOPS drives, or after FREE_HOPS
# looks (distance, count, count_cells) since the last drive.
MOVE_HOPS = 20
FREE_HOPS = 10


MOVE_DELAY_MS = 220  # hold a direction this long before it repeats
MOVE_REPEAT_MS = 70  # then one step every this long
TYPE_REPEAT_DELAY_MS = 400  # hold a key this long while typing before it repeats
TYPE_REPEAT_MS = 35  # then once every this long

# Drawing a drive. goto finishes at once; anim.Reel plays it back afterwards.
ANIMATE = True
ANIM_SPEED = 0.5  # 1.0 plays the timings below as written
ANIM_PLAN = 0.012  # seconds a cell of the yellow plan takes to draw
ANIM_PROBE = 0.022  # a cell of a blue distance probe
ANIM_STEP = 0.070  # a cell of actual driving
ANIM_BLOCK = 0.30  # the pause on an outcrop before the plan withdraws
ANIM_PRUNE = 0.008  # a cell of it pulling back to the rover
REEL_MAX = 12  # pending reels kept when nothing is drawing them

# The pause after a drive before the planner may think again, so each drive can be seen.
SETTLE_SECONDS = 2.0

# What she writes down. Over-long items are refused, not cut. Struck items keep their
# place, so TODO_MAX counts everything written today.
TODO_MAX = 12
TODO_CHARS = 200
# Her memory: named entries, written whole. At the cap she must forget before she adds.
MEMORY_ENTRIES = 10
MEMORY_CHARS = 300  # one entry
# One order on the operator's board.
ORDERS_CHARS = 400
# What she says when she radios mission control.
RADIO_CHARS = 400

# The work. Interests are hidden in the arena (config). Objectives are placed by the
# desk, or with "auto", three at a time from sol 2, a new set once the last is done.
OBJECTIVES = "manual"
OBJECTIVE_COST = (15, 60)  # an auto objective's work, in steps, drawn in fives

# The weather: one dust storm a sol (hazards.py).
STORM_ON = True
# a disc of radius 2 is 13 cells
STORM_RADIUS = 2

# How many times one goto replans around rock it finds before returning BLOCKED.
NAV_REPLANS = 5

# The route file the real rover drives: one leg, already driven in the simulation, one
# of N/E/S/W a line. Wiped once the leg is done. Relative to the prototype folder; None turns it off.
PLAN_FILE = "runs/plan.txt"

# Who says the rover has finished a leg: "none" does not wait, "key" waits for SPACE
# (or for the rover, under Level 3).
ROVER_PAUSE = "none"
