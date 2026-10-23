# Prototype 16

Koushik's prototype: the rover's hardware, and its link to the simulation. Scope and levels are in
[`DESIGN.md`](DESIGN.md).

```
prototype16/
  game/        the simulation: prototype 10d's game/, copied untouched (COPIED_FROM.md)
  hardware/    everything added for the rover -- how to run it is in hardware/README.md
```

The two never mix. Nothing in `hardware/` edits `game/`; delete `hardware/` and what is left is a
plain copy of 10d. To take a newer simulation, replace `game/` with a fresh copy.

## Setup, once, on the laptop

As prototype 10d: Python with `pygame` (`python -m pip install pygame numpy`), and Ollama with the
model signed in:

```bash
ollama signin
ollama pull gemma4:31b-cloud
```

The simulation alone, with no rover, runs as in 10d: `python game/main.py`.
