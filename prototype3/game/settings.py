"""Every knob worth turning. Change things here, not in the code.

None of these are tuned. They are guesses, and you cannot balance an arena you have
not watched anything cross.
"""

# --- the day ---------------------------------------------------------------
# **Steps for now, a wall clock later.** The clock is item 4 of eight and gets built
# once the rest is in. Decided 2026-08-29, and the reasoning is worth keeping: on Mars
# the longer the planner deliberates the less daylight is left, and gemma has to work
# out for itself that a ticking clock means turn for home. A step budget cannot teach
# that. But a clock also makes every run depend on how fast the machine is, so it
# lands *after* everything it would otherwise be entangled with.
#
# "human" -- a day is DAY_SECONDS of wall clock.
# "gemma" -- a day is DAY_STEPS actions and the clock becomes a stopwatch that only
#            watches. The stopwatch runs in both modes and is shown in both, because
#            what it records is the measurement item 4 has to be designed against.
DAY_MODE = "gemma"
DAY_SECONDS = 300
DAY_STEPS = 1000         # one per tile driven. A guess -- crossing the arena is ~50

TIME_SCALE = 1.0        # 2.0 makes the day run twice as fast
VISION_RADIUS = 3       # how far the rover sees as it drives
BASE_REVEAL = 6         # ...and how much of the landing site it can see on arrival,
                        # so day one opens on ground rather than on a wall of '?'

# --- the model -------------------------------------------------------------
# Measured on a 6 GB RTX 3050 laptop, 2026-08-26: about 20 tokens a second, 3.6 GB of
# VRAM, flat out to 16k of context. A reply is ten to twenty seconds.
MODEL = "gemma4:e4b"
OLLAMA_HOST = "http://localhost:11434/api/chat"
MODEL_CTX = 16384       # Ollama defaults to 4096 and truncates silently. Never unset.
MODEL_THINK = False     # ask the model to reason out loud. Measured 2026-08-26: on,
                        # a turn is ~46s and it reads the grid no better (5/10 either
                        # way). Off by default; H hides the trace when it is on.
                        # `--think` turns it on *and* unpins the sampler below; the two
                        # go together and the comment on MODEL_TEMP says why.
MODEL_KEEP_ALIVE = "30m"   # a reload costs five seconds and a day has many pauses
MODEL_TIMEOUT = 600

# --- the second model, for the probe only ----------------------------------
# **Nothing in the game reads any of this.** It exists so `probe_map.py --backend
# gemini` can put the identical system prompt, view block and questions in front of a
# hosted model, because nothing measured so far separates *"the view is unreadable"*
# from *"a 4B model cannot read any view"* -- and those two prescribe opposite work.
# See `MAP-READING.md`. A demo that depended on this would need network at the venue,
# which is a separate decision nobody has taken.
#
# `GEMINI_MODEL` is deliberately blank. Model names move, and this repo does not guess
# them: run `probe_map.py --list-models` with a key set and paste one back.
GEMINI_HOST = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-3.7-flash"

# The NAME of an environment variable, not the key. The key never lives in a file.
GEMINI_KEY_ENV = "GEMINI_API_KEY"

# **Which header carries the key, and it is a real fork as of 2026-09-02.** AI Studio
# has started issuing keys prefixed `AQ.` instead of the old `AIza`, and those are
# rejected by generativelanguage.googleapis.com with 401 ACCESS_TOKEN_TYPE_UNSUPPORTED
# and the message "Expected OAuth 2 access token" -- widely reported, not our bug.
#   "key"    -- x-goog-api-key: <key>.       Correct for AIza keys.
#   "bearer" -- Authorization: Bearer <key>. Worth one call with an AQ. key.
# If neither works, an AIza key from the Cloud console for the same project is the
# reliable way out; see the note in `probe_map.list_models`.
GEMINI_AUTH = "key"

# Free-tier requests per minute. The probe sleeps to stay under it rather than
# retrying on 429, because a retry storm against a shared quota is rude and a probe
# that takes an extra four minutes costs nothing.
GEMINI_RPM = 15

# **And the limit that actually binds is this one, not the one above.** Measured
# 2026-09-02 against gemma-4-31b-it: the free tier refuses with
# `generate_content_free_tier_input_token_count, limit: 16000`. One probe call is the
# system prompt plus a 4.4k-character view -- about 5.5k tokens -- so 16k a minute is
# roughly three calls, and pacing at 15/min spent the run in retry backoff.
# The probe paces on whichever of the two is slower, using the token count the previous
# call actually reported rather than an estimate.
GEMINI_TPM = 16000

# Retries for 429 and 5xx only, at 2s, 4s, 8s. A busy model answers "high demand,
# spikes in demand are usually temporary" with a 500, and a fourteen-minute run should
# survive one. Auth and malformed-request faults are never retried: they are not
# weather, and retrying them burns quota to learn nothing.
GEMINI_RETRIES = 3

# Longest single backoff worth taking. Past this the 429 is a spent quota window rather
# than congestion, and waiting it out means sleeping through a probe run to no purpose;
# the probe stops and names the metric instead. Free-tier allowances differ wildly per
# model -- gemini-3.5-flash gave 20 requests total, gemma-4-31b-it ran 210 without one.
GEMINI_MAX_BACKOFF = 30

# The local gemma arm ran with thinking OFF, and `--think` was measured to make gemma
# *worse* at seven times the cost. So the comparison is only fair at **the lowest
# setting each model offers** -- which is a principle, not a string, because the allowed
# values differ per model and there is no shared vocabulary:
#
#   gemini-3.x   low
#   gemma-4      minimal | high   ("'low' is not a supported thinking level")
#   empty        send no setting at all
#
# So two hosted arms will legitimately carry different values here, and the tape records
# what each row was actually asked with. `--thinking` overrides it per run.
GEMINI_THINKING = "low"

# **Pinned, and this is the fix for the bug that made gemma look broken.** Ollama uses
# the model's own default (~0.8) when this is not sent, and prototype 1 never sent it.
# Measured 2026-08-29 against a live gemma4:e4b, same request the game builds, twelve
# turns: unset, **9 of 12** emitted a real tool call and 3 wrote `goto(25, 15, "...")`
# into the reply as prose, where it does nothing at all. At 0, twelve of twelve called.
# The prompt was never the problem -- the sampler was.
#
# Two other reasons to keep it here rather than leave it to chance: two runs of the same
# script only compare if the sampler is fixed, and FINDINGS is explicit that run-to-run
# variance already swamps n=1 conclusions. Raise it if the conversation reads too flat;
# `chat._nudge` is the backstop either way.
#
# **`None` means send no sampler at all and let the model's own defaults stand** --
# temperature 1, top_k 64, top_p 0.95 for `gemma4:e4b`. That is what `--think` sets, and
# it is not a preference: greedy decoding over a long reasoning trace is the one place
# temperature 0 reliably misbehaves, because a chain that starts repeating has no noise
# available to break out of it. Pinning temperature to 0 while top_k and top_p stay at
# the model's values is a mixture nobody here has measured, so a thinking run either
# takes the whole default set or it is not a clean sample.
#
# **The cost of that is stated rather than hidden: the vanishing call comes back.** The
# 9-of-12 above is what an unpinned sampler measured. So a `--think` run is a diagnostic
# with a known confound, not a mode to demo, and its result is only ever read against a
# `--think` run of the same question -- never against a greedy one.
MODEL_TEMP = 0.0
SHOW_THINKING = True    # whether the pane *displays* the trace. Separate from
                        # MODEL_THINK: the tape records it either way.

CHAT_W = 1000           # pixel width of the pane. 880 + 1000 = 1880 on a 1920 screen

# Tool calls gemma may make in one human turn before it is made to stop and speak.
# Not tidiness: `distance` costs no steps, so a model looping on a misread position
# would never be stopped by the day's budget. This is the only backstop.
MODEL_MAX_HOPS = 10

MOVE_DELAY_MS = 220     # hold a direction this long before it repeats
MOVE_REPEAT_MS = 70     # then one step every this long

# --- watching it drive -----------------------------------------------------
# `nav.goto` finishes in one go and always has: the model must get the true outcome in
# the same breath as the call. So the rover does not really move slowly -- the world
# jumps, nav writes down what it did, and `anim.Reel` replays that afterwards. The
# screen lags the world on purpose; nothing waits on the drawing.
#
# The one coupling this creates is in `main.py`: the conversation is not pumped while a
# reel is playing, so the next call cannot land on top of the drive you are watching.
ANIMATE = True
ANIM_PLAN = 0.012       # seconds a cell of the yellow plan takes to draw
ANIM_PROBE = 0.022      # ...and a cell of a blue distance probe, which is slower
                        # because pricing a trip is the only thing there is to watch
ANIM_STEP = 0.035       # ...and a cell of actual driving. 76 steps is about 2.7s
ANIM_BLOCK = 0.30       # the pause on an outcrop before the plan starts withdrawing
ANIM_PRUNE = 0.008      # ...and a cell of it retracting back to the rover
REEL_MAX = 12           # pending reels kept if nothing is drawing them (a headless
                        # run has no player, and this stops the list growing forever)

# --- navigation ------------------------------------------------------------
# A goto plans over fog as though it were empty, so it will drive into an outcrop it
# could not have known about. This is how many times one call quietly replans around
# that before handing control back with BLOCKED. Every rock found on the way is
# reported either way, so a higher number costs steps and saves model calls. 0 gives
# strict one-surprise-per-call, and is the setting to use before concluding anything
# about whether gemma reasons about failure.
#
# **Back to 5 on 2026-08-29**, for legibility: at 8 a drive absorbs so much of its own
# trouble that what comes back is a rock list with no obvious connection to what was
# asked, which FINDINGS records as the cost of a high number.
#
# It is no longer entangled with the tests, and it briefly looked as though it were.
# `test_nav.py` was red at 8 and green at 5, which read like the setting being wrong;
# the setting was innocent. The test asserted that `world.last_path` crosses rock, and
# that field holds only the *newest* hypothesis -- so a drive that replans through to
# DONE leaves behind the one plan that turned out right. It now asks the reel, which
# keeps every plan the drive laid, and passes at 0, 1, 5, 8 and 12.
NAV_REPLANS = 5
