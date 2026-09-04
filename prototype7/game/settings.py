"""Every knob worth turning. None of them are tuned."""

# --- the day ---------------------------------------------------------------
# "gemma": a day is DAY_STEPS actions. "human": a day is DAY_SECONDS of wall clock.
# A wall clock for gemma is deferred -- it would make every run depend on machine speed.
DAY_MODE = "gemma"
DAY_SECONDS = 300
DAY_STEPS = 1000         # one per tile driven; crossing the arena is ~30

TIME_SCALE = 1.0        # 2.0 makes the day run twice as fast
VISION_RADIUS = 3       # how far the rover sees as it drives
BASE_REVEAL = 6         # and what it sees on arrival, so day one opens on ground

# How the map is written into the view. "grid" is the picture, one character a cell.
# "rle" is one line a row of coordinate-labelled runs, so no cell has to be counted off
# a row -- gemma scores 0% on every counting question off the picture.
#
# What rle costs, in gemma4:e4b's own tokens, measured 2026-09-04 off `prompt_eval_count`
# for the whole view block:
#
#            fresh sol        surveyed
#   30x30    845 -> 1070      772 -> 1414   (1.27x, 1.83x)
#   50x50   1280 -> 1285     1155 -> 3168   (1.00x, 2.74x)
#
# Runs fragment as the map fills in, so rle is most expensive exactly when the sol is
# going well, and the bigger arena separates the two formats far more. Measure in tokens,
# not chars: the grid's repeated characters pack much better than words, so the char
# ratio understates this badly -- 1.37x where the token ratio is 2.74x.
MAP_FORMAT = "grid"

# --- the model -------------------------------------------------------------
# Measured on a 6 GB RTX 3050: ~20 tokens/sec, 3.6 GB VRAM, flat to 16k context.
MODEL = "gemma4:e4b"
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
SHOW_THINKING = True    # whether the pane displays the trace; the tape records it anyway

CHAT_W = 1000           # pixel width of the pane, before the screen has a say

# The numbers above make an 1880x990 window, which does not fit a 1080p laptop once
# the title bar and taskbar are taken -- the bottom of the arena and the HUD with it
# end up off screen. `render.fit_to_display` shrinks the tiles, and then the pane,
# until it fits whatever it opens on. Turn it off to get the sizes above exactly,
# which is what a screenshot that has to match somebody else's needs.
FIT_TO_SCREEN = True
SCREEN_RESERVE_W = 60   # window border and a little air
SCREEN_RESERVE_H = 110  # title bar plus the taskbar

# --- how much rope she gets in one turn -------------------------------------
# She drives until she calls `end`, so these are what stop a turn that never would.
# Two budgets, because the two kinds of call fail differently.
#
# `goto` spends steps, so the day's budget eventually catches a loop of them. MOVE_HOPS
# is about pacing rather than safety.
MOVE_HOPS = 10
#
# `distance`, `count` and `count_cells` spend nothing, so nothing else would ever stop
# them: a model looping on `count` loops forever. The allowance is per *drive* -- every
# `goto` resets it to zero. So more looking has to be paid for with moving, and since
# moving is capped the whole turn terminates: at most (MOVE_HOPS + 1) * FREE_HOPS looks.
FREE_HOPS = 5
#
# Past a cap the call is refused rather than run, and this many refusals of a kind ends
# the turn for her. Refusing without ever stopping is how a model spends a whole turn
# being told no. Watched 2026-09-04: with one cap and no grace, the 31B lost 24 of 48
# calls in silence.
MOVE_GRACE = 3
FREE_GRACE = 5

# One tool call per request, always. The 31B emits four to six at a time, and they are
# *chosen* before any of their outcomes are known -- the second target in a batch is
# aimed at a map several drives out of date, which is where its BLOCKED results came
# from. Extra calls in one reply are refused, not queued: queueing runs exactly the
# stale decisions this exists to stop.
ONE_CALL_AT_A_TIME = True

MOVE_DELAY_MS = 220     # hold a direction this long before it repeats
MOVE_REPEAT_MS = 70     # then one step every this long

# --- the second model, for the probe only ----------------------------------
# Nothing in the game reads any of this. It lets `probe_map.py --backend gemini` put the
# same prompt, view and questions in front of a hosted model.
# GEMINI_MODEL: names move, so run `--list-models` and paste one back.
GEMINI_HOST = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-3.7-flash"

GEMINI_KEY_ENV = "GEMINI_API_KEY"   # the NAME of the variable. The key never lives here.

# AI Studio now issues `AQ.` keys, which this endpoint rejects with 401 unless sent as
# "bearer". "key" is correct for the older `AIza` keys.
GEMINI_AUTH = "key"

# Free-tier pacing. The probe sleeps rather than retrying into a quota.
# Known wrong: the observed per-minute limit is 5, not 15, and the daily cap is 20 requests
# per model with failed requests counting against it.
GEMINI_RPM = 15
GEMINI_TPM = 16000      # one call is ~5.5k tokens, so this binds before RPM does

GEMINI_RETRIES = 3      # 429 and 5xx only, at 2s/4s/8s. Auth faults are never retried.

# Past this, a 429 is a spent quota rather than congestion, so the probe stops and names
# the metric. Free allowances differ wildly: 20 requests on one model, 210 on another.
GEMINI_MAX_BACKOFF = 30

# The comparison is only fair at the lowest setting each model offers, and the allowed
# values differ: `low` for gemini-3.x, `minimal|high` for gemma-4, empty to send nothing.
GEMINI_THINKING = "low"

# --- watching it drive -----------------------------------------------------
# `nav.goto` finishes in one go -- the model must get the outcome in the same breath as
# the call. So the world jumps and `anim.Reel` replays it afterwards. The screen lags the
# world on purpose. `main.py` does not pump the conversation while a reel is playing.
ANIMATE = True
ANIM_PLAN = 0.012       # seconds a cell of the yellow plan takes to draw
ANIM_PROBE = 0.022      # a cell of a blue distance probe
ANIM_STEP = 0.070       # a cell of actual driving; 76 steps is about 5.3s
ANIM_BLOCK = 0.30       # the pause on an outcrop before the plan withdraws
ANIM_PRUNE = 0.008      # a cell of it retracting back to the rover
ANIM_SCOUT = 0.55       # the scout window sits drawn this long before its fog lifts
REEL_MAX = 12           # pending reels kept when nothing is drawing them

# The rover sits still this long after a drive before the planner is allowed to think
# again. A 31B answers in under two seconds, so without this a sol is a sequence of
# teleports with no drive legible between them. It is weight, not simulation -- nothing
# in the world changes during it.
SETTLE_SECONDS = 2.0

# --- the flyer -------------------------------------------------------------
# Scouting reveals a box of ground the rover has not driven. Three knobs, each shutting
# a different door: range stops knowledge teleporting, recharge stops it being spammed
# from one spot, cost makes it compete with driving. Any two leave a hole.
#
# One currency on purpose -- a separate flyer budget competes with nothing, so every
# sortie is free at the margin and there is no decision in it.
#
# Swept on the 50x50: 500 steps, five seeds, random long drives, scouting aimed at the
# fogged window in range, against a drive-only baseline of 66.4% of the arena mapped.
#
#     window   range  cost   mapped   vs baseline
#      9x9      10     20    66.2%      -0.2pp    a wash: 81 cells for 20 steps, and
#      9x9      10     10    70.2%      +3.7pp    random driving already averages ~3.3
#     13x13     10     20    77.1%     +10.7pp    <- shipped
#     13x13     16     20    78.5%     +12.1pp
#     17x17     16     20    90.7%     +24.3pp    map falls over in two sols
#
# Range and value fight each other: a window near the rover covers ground the rover was
# going to reveal anyway, so lowering SCOUT_RANGE makes the flyer redundant rather than
# merely weak. Still untuned against a *model* -- the sweep aimed perfectly, and whether
# she can aim a window at fog she has to find on the grid is the open question.
SCOUT_BOX = 6        # radius, so 6 -> a 13x13 window, 169 cells at full size
SCOUT_RANGE = 10     # how far from the rover the window may be centred
SCOUT_COST = 20      # steps, out of the same day the rover drives on
SCOUT_RECHARGE = 25  # steps of driving owed before the next sortie

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so it drives into outcrops it could not
# have known about. This is how many times one call replans before returning BLOCKED.
# Higher costs steps and saves model calls; 0 gives strict one-surprise-per-call.
# At 8 a drive absorbs so much of its own trouble that the rock list stops relating to
# what was asked.
NAV_REPLANS = 5

# --- the route file --------------------------------------------------------
# The live route: the current plan, and only ever the current one. Rewritten on every
# fresh `goto` and on every replan inside one, so a reader holds the rover's present
# intention rather than a queue of stale ones. Emptied when there is no route -- the
# dangerous failure is a reader still executing the last good plan after the planner
# has given up on it.
#
# This is the seam to Unity and to the learned policy: they read this file and drive
# the physical rover from it. Relative paths resolve against the prototype directory,
# not the shell's. Only a live run writes it (`nav.publish` checks `world.recorder`),
# so importing nav in a test puts nothing on disk. None turns it off altogether.
PLAN_FILE = "runs/plan.txt"

# What a `goto` from the model actually does. `main.py --executor` sets it.
#   teleport  step cell to cell, writing the route as it goes (the default)
#   plan      plan, write the route file, and move nothing
# `plan` is for watching the planner alone: the rover stays put, so no fog lifts and
# every plan is made over the same map. The model is told this in the result rather
# than being left to work out why its situation never changes.
EXECUTOR = "teleport"
