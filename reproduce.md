# Run it on your machine

Written for Windows, because most of us are on it. macOS and Linux differ only in the two lines
marked. **You do not need a GPU** to see the rover drive, read the map, or run the tests — the only
thing a GPU buys is a local language model answering quickly.

About ten minutes, most of it downloading.

---

## 1 · Python

Install **Python 3.12** from [python.org](https://www.python.org/downloads/windows/). Tick **"Add
python.exe to PATH"** on the first screen of the installer — if you miss it, every command below
fails with *"python is not recognized"* and the fix is to re-run the installer and choose Modify.

Check it:

```bat
py --version
```

## 2 · The code

```bat
git clone https://github.com/IshuIsAwake/reflex-arc.git
cd reflex-arc
```

## 3 · A virtual environment

Keeps this project's packages out of the rest of your machine.

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

*macOS / Linux:* `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

Your prompt should now start with `(.venv)`. It will need `activate` again in every new terminal.

## 4 · Drive it yourself

This is the checkpoint — it needs no model, no key and no GPU.

```bat
cd prototype2
python game\main.py
```

A window opens on a 50×50 Martian plain with the rover at the centre and fog everywhere else.
`WASD` drives, `M` opens the map, `T` opens a console where you can type `goto 25 5` and watch the
planner route around rock it cannot see yet. Full controls are in
[`prototype2/README.md`](prototype2/README.md).

**If this works, your install is fine.** Everything after this is about who does the deciding.

## 5 · The tests

Also no model, no GPU. Run them after changing anything.

```bat
python game\test_world.py
python game\test_nav.py
python game\test_sight.py
python game\test_skills.py
python game\test_chat.py
python game\test_logs.py
python game\test_anim.py
```

`test_world.py` is the one to run after editing the map — it flood-fills the arena looking for
ground that is sealed off, which is invisible until somebody wastes a whole sol driving at it.

## 6 · The planner, locally

This is the part that wants a GPU, and works without one.

Install [Ollama](https://ollama.com/download), then pull the model this repo is set to
(`MODEL` in [`prototype2/game/settings.py`](prototype2/game/settings.py)):

```bat
ollama pull gemma4:e4b
```

Ollama serves on `http://localhost:11434` by itself once installed — there is nothing to start.
Run the game again and press `TAB` to talk to the planner.

**Without a GPU it still runs, on the processor, and it is slow.** Same answers, more waiting: a
reply that takes ten to twenty seconds on a 6 GB laptop GPU will take considerably longer. Nothing
breaks; you will just be watching a spinner. If that is your machine, drive it yourself with `T` and
the console — the planner is doing exactly what you can type by hand.

## 7 · Hosted models, and what is honestly not wired up

**The game talks to Ollama and nothing else.** `chat.py` posts to `OLLAMA_HOST`; there is no
API-key path into the pane. So a hosted model cannot fly the rover today. Wiring one in means
teaching `chat.py` a second transport that streams and carries tool calls — worth doing, not done.

What *is* wired up is the map-reading probe, which asks a model the same questions with the same
system prompt and the same view block, and scores the answers against ground truth. It runs
anything the key can reach, including hosted Gemma, and needs no GPU:

```bat
set GEMINI_API_KEY=your-key-here
python game\probe_map.py --list-models
python game\probe_map.py --backend gemini
```

*macOS / Linux:* `export GEMINI_API_KEY=your-key-here`

Keys come from [aistudio.google.com/apikey](https://aistudio.google.com/apikey). The key goes in
the environment and never in a file — `settings.GEMINI_KEY_ENV` holds the *name* of the variable,
not the key.

**Run `--list-models` first, always.** Model names move and this repo does not guess them; paste one
of the names it prints into `settings.GEMINI_MODEL`.

Three things that will bite, all known:

- **A key starting `AQ.` instead of `AIza`** is rejected with 401 `ACCESS_TOKEN_TYPE_UNSUPPORTED`.
  Set `GEMINI_AUTH = "bearer"` in settings and try once more; if that fails, get an `AIza` key from
  the Cloud console for the same project.
- **The free tier is stingier than the settings claim.** `GEMINI_RPM` says 15 and the real limit
  behaves like 5. Some models allow only about 20 requests a day, and *failed requests count*, so a
  misconfigured run can spend a day's quota learning nothing.
- **The 429 handler gives up too early.** It reads Google's "please retry in 58.5s" as no delay
  given and stops instead of waiting. Fixing that is a good first task.

## 8 · When it goes wrong

| what you see | what it is |
|---|---|
| `python is not recognized` | PATH box unticked at install. Re-run the installer, choose Modify. |
| `No module named pygame` | The venv is not active, or `pip install` was run without it. Look for `(.venv)` in your prompt. |
| `No module named settings` | You ran it from the wrong directory. `cd prototype2` first. |
| The window opens but the pane never answers | Ollama is not running, or the model is not pulled. `ollama list` should show it. |
| `context 15000/16384 -- the morning is being dropped` | Normal after a long sol. The conversation is thrown away at nightfall; press `N`. |
| A leftover `runs\pending-*` folder | Not an error. A run nobody answered `K` or `D` for, with everything still in it. |

## What to try once it runs

Press `T` and type `goto 2 2`. Watch the yellow route draw out into ground the rover has never seen,
the rover follow it, and a boulder refuse it somewhere in the middle — then watch the plan retract
and a different one grow from where it actually stopped.

That picture is the whole project. Nobody told it where the rock was.
