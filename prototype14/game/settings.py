"""Every knob worth turning. None of them are tuned."""

# --- the day ---------------------------------------------------------------
# A sol is dawn, day, dusk and night (`autopilot.py`), and only the day has a clock:
# DAY_SECONDS of wall clock from the moment it begins, which nothing pauses. Her thinking,
# the drives as they are drawn and a radio call all happen on it. Replay sets it from the
# tape instead. Ten minutes until runs say otherwise.
DAY_SECONDS = 600
# The battery, in steps: one per tile driven and one per step of work. The pad charges
# it overnight, and only the pad -- a rover stranded away from it wakes on whatever it
# had left, and one that runs flat away from it is lost.
# Getting across the 30 is about 30 steps and the objectives cost 40, 15 and 60, so the
# dearest one plus the drive to it is about 90 of 150: one objective a charge with room
# left to explore, and a second only by giving up the exploring. 500 is the 29 Sept
# recording's value, and it breaks that balance. Which is the default is undecided.
BATTERY = 500

TIME_SCALE = 1.0        # 2.0 makes the day's clock run twice as fast
# Sols in a mission. Once the last one ends, a run with a window waits: N plays one more
# sol, 1-9 that many, and ESC asks whether to keep it. A headless run is kept and exits.
# 0 is no limit.
MISSION_SOLS = 0
# Someone is at the desk, watching. On, each phase waits for the desk -- COMMS_WAIT after
# the last thing typed or said, or /next -- and the desk can talk at dawn and night, break
# in by day with one urgent message, and answer her radio. Off, nobody is there: every
# phase moves on as soon as she is quiet, she is told so, and she has no radio. A run
# with no window starts with it off.
COMMS = True
COMMS_WAIT = 60.0       # wall clock: the desk's patience
# What one radio message costs her, in steps of battery: the call itself, and every reply
# she speaks while the line is open.
RADIO_STEPS = 5
# A request that never reached the model is asked again after this long rather than
# counted as a turn. Counted, a dropped connection overnight would play out every
# remaining sol in seconds with nobody talking.
AUTO_RETRY_SECONDS = 30.0
# Driving opens fog, a disc this wide around every cell reached, and it is the only thing
# that does -- Ingenuity is cut, and a blind rover cannot answer the geology question by
# driving, which is the only way it is meant to be answered.
# **A guess sized to the smaller arena, not a swept value.** Two is roughly a fifth of the
# 30's width a sol; three made a single crossing hand over most of the map.
VISION_RADIUS = 2
BASE_REVEAL = 6         # the landing site, opened once on arrival -- the only free map

# --- the model -------------------------------------------------------------
# The planner for a multi-sol run. `gemma4:31b-cloud` is rate-limited per-model on
# Ollama cloud, so a long day can stall part-way through -- `--model` swaps it without
# editing this file, and `gemma4:e4b` is the local fallback that always answers.
# Measured on a 6 GB RTX 3050: e4b runs ~20 tokens/sec, 3.6 GB VRAM, flat to 16k.
MODEL = "gemma4:31b-cloud"
# When a request to MODEL fails, the same request goes here at once, and the run stays
# here until a probe of MODEL answers again (`chat.Link`). The same as MODEL turns it off.
MODEL_FALLBACK = "gemma4:e4b"
PROBE_SECONDS = 30      # how often MODEL is tried while the fallback answers
PROBE_TIMEOUT = 15      # a probe is one token; this long without one is still down
# Sols on which MODEL is unreachable, on purpose: its requests and probes go to a port
# nothing listens on, so the real connection-refused path runs. For showing the fallback
# without taking a real outage. `main.py --outage N`.
OUTAGE_SOLS = ()
OUTAGE_HOST = "http://127.0.0.1:9/api/chat"
OLLAMA_HOST = "http://localhost:11434/api/chat"
MODEL_CTX = 16384       # Ollama defaults to 4096 and truncates silently. Never unset.
MODEL_THINK = False     # measured: ~46s a turn and no better at reading the grid
MODEL_KEEP_ALIVE = "30m"   # a reload costs five seconds and a day has many pauses
MODEL_TIMEOUT = 600

# Pinned. Unset, Ollama uses the model's own ~0.8 and 3 of 12 turns wrote the tool call
# into the reply as prose instead of calling it. At 0, twelve of twelve called.
# None sends no sampler at all, which is what `--think` does -- greedy decoding over a
# long reasoning trace has no noise to break a repeating chain.
MODEL_TEMP = 0.0
# Sent with every request. Pins the sampler's own noise and nothing else: the model
# still cannot be made to repeat itself, because inference batches requests and float
# addition is not associative. `None` sends no seed. See DESIGN.md's determinism ledger.
MODEL_SEED = 0
SHOW_THINKING = True    # whether the pane displays the trace; the tape records it anyway
MAP_LABELS = False      # the rover's cell and its drive's target, labelled on the map

# A starting value only: `render.layout` sets it, and config's TILE, from the window.
CHAT_W = 990           # pixel width of the pane

# The window opens the desktop's size less these, so it fits under the title bar and
# above the taskbar. It can be dragged to any size after.
SCREEN_RESERVE_W = 60   # window border and a little air
SCREEN_RESERVE_H = 110  # title bar plus the taskbar

# --- how much rope she gets in one turn -------------------------------------
# She drives until she calls `end`, so these are what stop a turn that never would.
# Two budgets, because the two kinds of call fail differently.
#
# `goto` spends steps, so the day's budget eventually catches a loop of them. MOVE_HOPS
# is about pacing rather than safety.
MOVE_HOPS = 20
#
# `distance`, `count` and `count_cells` spend nothing, so nothing else would ever stop
# them: a model looping on `count` loops forever. The allowance is per *drive* -- every
# `goto` resets it to zero. So more looking has to be paid for with moving, and since
# moving is capped the whole turn terminates: at most (MOVE_HOPS + 1) * FREE_HOPS looks.
FREE_HOPS = 10
#
# Reaching either cap ends the turn by itself, and by day the clock opens the next one
# with both allowances back. She never has to call `end` for a cap: `end` is the day.


MOVE_DELAY_MS = 220     # hold a direction this long before it repeats
MOVE_REPEAT_MS = 70     # then one step every this long
TYPE_REPEAT_DELAY_MS = 400  # hold a key this long while typing before it repeats
TYPE_REPEAT_MS = 35     # then once every this long

# --- watching it drive -----------------------------------------------------
# `nav.goto` finishes in one go -- the model must get the outcome in the same breath as
# the call. So the world jumps and `anim.Reel` replays it afterwards. The screen lags the
# world on purpose. `main.py` does not pump the conversation while a reel is playing.
ANIMATE = True
ANIM_SPEED = 0.5        # 1.0 plays the timings below as written; the recording ran at 0.5
ANIM_PLAN = 0.012       # seconds a cell of the yellow plan takes to draw
ANIM_PROBE = 0.022      # a cell of a blue distance probe
ANIM_STEP = 0.070       # a cell of actual driving; 76 steps is about 5.3s
ANIM_BLOCK = 0.30       # the pause on an outcrop before the plan withdraws
ANIM_PRUNE = 0.008      # a cell of it retracting back to the rover
REEL_MAX = 12           # pending reels kept when nothing is drawing them

# The rover sits still this long after a drive before the planner is allowed to think
# again. A 31B answers in under two seconds, so without this a sol is a sequence of
# teleports with no drive legible between them. It is weight, not simulation -- nothing
# in the world changes during it.
SETTLE_SECONDS = 2.0

# --- what she writes down ---------------------------------------------------
# Both stores ride in the view on every request, so both are a flat tail cost paid every
# turn. The caps are backstops against a loop rather than a design feature -- an honest
# sol's list is four or five items, and a model that has written twelve is casting about,
# which is the same thing `skills._stuck` says out loud.
#
# Struck items keep their place so their ids keep their meaning, so this counts
# everything written today and not just what is still open.
TODO_MAX = 12
TODO_CHARS = 200        # one line. Longer is a retelling, and the tape already has one.
#
# Her memory: named entries, each written or replaced whole by `remember` and dropped by
# `forget`. A hard cap, like the handoff's, so at the cap she forgets before she adds. An
# over-long entry is refused rather than cut: truncating a rewrite silently loses the end,
# which is usually the part she has just changed her mind about. Bullets fit inside one.
MEMORY_ENTRIES = 10
MEMORY_CHARS = 300      # one entry
#
# One order on the operator's board, refused rather than cut for the same reason.
ORDERS_CHARS = 400
# What she says when she radios mission control. A call, not a report.
RADIO_CHARS = 400

# --- the work ----------------------------------------------------------------
# Interests are the arena's own (`config`), hidden until the rover sees them. Objectives
# are mission control's: placed with `place` in the terminal, or, with "auto", three at a
# time -- one of each priority -- from sol 2, a new set only once the last is finished.
OBJECTIVES = "manual"
OBJECTIVE_COST = (15, 60)   # an auto objective's work, in steps, drawn in fives

# --- the weather -----------------------------------------------------------
# One dust storm a sol, lasting the sol, visible from the moment it exists. Impassable
# rather than lethal: `nav` folds its cells into `avoid`, so a route goes round it or
# is refused, and the rover never touches one. See `hazards.py`.
STORM_ON = True
# A disc, so 2 is 13 cells -- 1.6% of the 30's open ground. Enough to be worth planning
# around on a 150-step day and too small to seal anything: measured over 500 sols, the
# worst placement still left 97.4% of the arena reachable. `STORM_TRIES` and
# `STORM_MAX_CUTOFF` guarded against the placement that walls the rover in and are gone
# with them; `hazards.py` says what brings them back.
STORM_RADIUS = 2

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so it drives into outcrops it could not
# have known about. This is how many times one call replans before returning BLOCKED.
# Higher costs steps and saves model calls; 0 gives strict one-surprise-per-call.
# At 8 a drive absorbs so much of its own trouble that the rock list stops relating to
# what was asked.
NAV_REPLANS = 5

# --- the route file --------------------------------------------------------
# The live route: one leg, already driven in the simulation, as one of N/E/S/W a line
# and nothing else. Written after the drive rather than before it, so the robot is only
# ever handed ground the simulation has proved and cannot be sent into rock. Wiped once
# the leg has been replayed -- the dangerous failure is a reader still executing a route
# after the planner has moved on from it.
#
# This is the seam to the physical rover: it reads this file and drives it. Relative
# paths resolve against the prototype directory, not the shell's. Only a live run writes
# it (`nav.live_file` checks `world.recorder`), so importing nav in a test puts nothing
# on disk. None turns it off altogether.
PLAN_FILE = "runs/plan.txt"

# How the planner finds out the rover has finished the leg on disk. The pause is the
# architectural claim -- nothing is replanned until the body has caught up -- so this
# chooses who says so, never whether anyone does.
#   "none"  do not wait. For testing, and for recording a tape with no rover attached.
#   "key"   the operator watches the rover stop and presses SPACE. A stand-in.
# The bridge reporting back for itself replaces both and is Abhishek's. `nav._await_rover`
# is the only thing that changes when it lands; the file format does not.
#
# **"none" is the default from 10c on,** because the clock runs every sol and nobody has
# to be at the keys. "key" is for a run with a rover on the floor and someone watching
# it, where the pause is the thing being demonstrated: without it `plan.txt` is written
# and wiped with nothing on the other end.
ROVER_PAUSE = "none"
