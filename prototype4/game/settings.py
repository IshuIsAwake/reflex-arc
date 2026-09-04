"""Every knob worth turning. None of them are tuned."""

# --- the day ---------------------------------------------------------------
# "gemma": a day is DAY_STEPS actions. "human": a day is DAY_SECONDS of wall clock.
# A wall clock for gemma is deferred -- it would make every run depend on machine speed.
DAY_MODE = "gemma"
DAY_SECONDS = 300
DAY_STEPS = 1000         # one per tile driven; crossing the arena is ~50

TIME_SCALE = 1.0        # 2.0 makes the day run twice as fast
VISION_RADIUS = 3       # how far the rover sees as it drives
BASE_REVEAL = 6         # and what it sees on arrival, so day one opens on ground

# How the map is written into the view. "grid" is the picture, one character a cell.
# "rle" is one line a row of coordinate-labelled runs, so no cell has to be counted off
# a row -- gemma scores 0% on every counting question off the picture. Measured on
# gemma4:e4b: the grid is a flat ~780 tokens, rle is 1.9x that on a fresh sol and 3.8x
# once the map is filled in, because exploring the map is what fragments the runs.
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
# Windows has taken its title bar and taskbar -- the bottom of the arena and the HUD
# with it end up off screen. `render.fit_to_display` shrinks the tiles, and then the
# pane, until it fits whatever it opens on. Turn it off to get the sizes above exactly,
# which is what you want for a screenshot that has to match somebody else's.
FIT_TO_SCREEN = True
SCREEN_RESERVE_W = 60   # window border and a little air
SCREEN_RESERVE_H = 110  # title bar plus the taskbar

# Tool calls in one human turn before gemma is made to stop and speak. `distance` costs
# no steps, so a model looping on one would never be stopped by the day's budget.
MODEL_MAX_HOPS = 10

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
ANIM_STEP = 0.035       # a cell of actual driving; 76 steps is about 2.7s
ANIM_BLOCK = 0.30       # the pause on an outcrop before the plan withdraws
ANIM_PRUNE = 0.008      # a cell of it retracting back to the rover
ANIM_SCOUT = 0.55       # the scout window sits drawn this long before its fog lifts
REEL_MAX = 12           # pending reels kept when nothing is drawing them

# --- the flyer -------------------------------------------------------------
# Scouting reveals a box of ground the rover has not driven through. Three knobs, and
# each one shuts a different door.
#
# A separate budget would have been easier to explain and much worse: charge the flyer
# in its own currency and it competes with nothing, so every sortie is free at the
# margin and gets spent every sol. There is no decision in that. One pool, flat price.
#
# **These were set by sweeping them, and the first guess was wrong.** 500 steps, five
# seeds, random long drives, scouting aimed at the fogged window in range -- against a
# drive-only baseline of 66.4% of the arena mapped:
#
#     window   range  cost   mapped   vs baseline
#      9x9      10     20    66.2%      -0.2pp     <- the first guess. A wash.
#      9x9      10     10    70.2%      +3.7pp
#     13x13     10     20    77.1%     +10.7pp     <- shipped
#     13x13     16     20    78.5%     +12.1pp
#     17x17     16     20    90.7%     +24.3pp     <- deletes the rover
#
# 9x9 at 20 is not a hard choice, it is a bad deal: a full window is 81 cells for 20
# steps, and random driving already averages ~3.3 cells a step over a whole sol, so the
# best case barely ties and the typical case loses. A capability nobody would rationally
# use measures nothing. 17x17 is the opposite failure -- the map falls over in two sols
# and there is no exploration left to watch. 13x13 at 20 is clearly worth using and
# clearly not free, which is the only place the decision is real.
#
# Structural, and worth knowing before retuning: **range and value fight each other.**
# A window near the rover covers ground the rover was going to reveal anyway, so raising
# SCOUT_RANGE is worth more than it looks and lowering it makes the flyer redundant
# rather than merely weak.
#
# Still not tuned against a *model*. All of the above is a scripted driver aiming
# perfectly; whether gemma can aim a window at fog it has to find on the grid is the
# open question, and it is the same map-reading it is measured bad at in results.md.
SCOUT_BOX = 6        # radius, so 6 -> a 13x13 window, 169 cells at full size
SCOUT_RANGE = 10     # how far from the rover the window may be centred
SCOUT_COST = 20      # steps, out of the same day the rover drives on
# Ingenuity recharged on the ground between sorties. This is that, in steps, and it is
# what stops a sol being spent parked: the rover has to go somewhere between flights.
# SCOUT_RANGE stops knowledge teleporting across the map, this stops it being spammed
# from one spot, and the cost makes it compete with driving. Three doors, three knobs.
SCOUT_RECHARGE = 25

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so it drives into outcrops it could not
# have known about. This is how many times one call replans before returning BLOCKED.
# Higher costs steps and saves model calls; 0 gives strict one-surprise-per-call.
# At 8 a drive absorbs so much of its own trouble that the rock list stops relating to
# what was asked.
NAV_REPLANS = 5
