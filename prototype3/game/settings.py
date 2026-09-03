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

CHAT_W = 1000           # pixel width of the pane

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
REEL_MAX = 12           # pending reels kept when nothing is drawing them

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so it drives into outcrops it could not
# have known about. This is how many times one call replans before returning BLOCKED.
# Higher costs steps and saves model calls; 0 gives strict one-surprise-per-call.
# At 8 a drive absorbs so much of its own trouble that the rock list stops relating to
# what was asked.
NAV_REPLANS = 5
