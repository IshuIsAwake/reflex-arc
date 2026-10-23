# game/ — a copy of prototype 10d's simulation, untouched

`game/` is `prototype10d/game/` exactly as committed at `6f60d68` (14 Oct 2026, "10d: four prompt
fixes from the first 31B run, and a scorecard"), copied on 23 Oct 2026. Nothing in it has been
edited. It sits at the same path as in every other prototype, and prototype12 runs on it alone:
deleting or changing `prototype10d/` does not affect it.

Everything added for the hardware is in `hardware/`. Nothing there edits `game/`;
`hardware/laptop/level3.py` imports it and wraps two functions in memory at start-up (see the
README). Delete `hardware/` and what is left is a plain copy of 10d.

`game/` writes its runs to `prototype12/runs/` and its settings to `prototype12/user_settings.json`,
separate from 10d's.

To check it is still untouched, from the repo root:

```bash
git diff 6f60d68:prototype10d/game HEAD:prototype12/game
```

No output means identical. To take a newer simulation later, replace `game/` with a fresh copy and
update the commit above.
