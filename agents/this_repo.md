# This repo

What only this repo has. `repo_rules.md` points here, and where the two differ this file wins.

## Owner
Ishan Batra, git user `IshuIsAwake`. He merges into `main` and reviews plan changes.

## Own setup
Ishan's own sessions (git user `IshuIsAwake`) follow his personal skills, `HANDOFF.md` and `memory/` instead of
"For AI assistants". Everyone else's assistant follows "For AI assistants".

## Read at the start of a conversation
- `DESIGN.md`: the plan. The data and time rules, the ladder, the backtest, and what isn't decided yet.
- `README.md`: the overview and the list of notebooks.
- `CONTRIBUTING.md`: the rules for people, which the user is held to.
- The notebook being worked on, and the notebooks it reads from.

## Plan documents
`DESIGN.md`. A change to it is written beside the decision it changes, with the reason, marked "Pending owner review"
(`repo_rules.md`, "For AI assistants" §5). Its section "Not decided yet" lists what the team still has to settle.

## Folders
- Notebooks sit at the top level, numbered, one job each, in the order of `DESIGN.md`. Each has one owner, and only
  its owner edits it. Notebook files merge badly.
- `self_module/` holds code used by more than one notebook: models, plots, statistics and the backtest. Ask before
  changing a function someone else uses.
- `data/` is created by the notebooks and never committed. Notebooks are committed with their outputs; `data/` is the
  run output that stays out (rule 6).
- Don't edit `agents/` (copied from the owner's master folder), `docs/`, or any top-level file without asking the
  owner. The one exception is `DESIGN.md`, changed through a plan-change pull request.

## Never commit
- `data/`
- `edgar_contact.txt`, which holds a name and email for SEC EDGAR, and `.env`
- `HANDOFF.md`, `memory/` and `.claude/`

## Checks
- The notebook runs top to bottom on a fresh kernel. Check each piece on a small slice first, such as a few tickers
  and one year. The owner of the notebook does the full run.
- A rung notebook ends by writing `data/results/<rung>.parquet` in the format of `DESIGN.md` section 8.
- Every number in a markdown cell is visible in an output above it.

## Other rules
- **One conversation, one task.** After about 15 turns, rewrite `HANDOFF.md` and suggest that the user starts a new
  conversation.
- **Notes:** `HANDOFF.md` and `memory/` follow §8 unless the user keeps notes their own way. Both stay git-ignored.
- **Time-ordered data:** the rules in `DESIGN.md` sections 3 and 4. Never shuffle. Never read the locked test year
  before `11_compare`. Use a label only once its window has closed.
- **Models:** every model has `train(X , y)` and `forward(X)`, where `forward` returns P(y = 1). Never `fit`, which
  reads as sklearn. sklearn and XGBoost models go through a thin adapter in `self_module`.
- **A model written from scratch** gets a cell that runs the library's version with no comments, then a table
  comparing the two.
- **Plots:** one call per cell to a function in `self_module/plots.py`. Each function aggregates first, then draws
  one plotly express figure. Seaborn only for a correlation heatmap.
- **Large data:** per-stock features use pandas `groupby` and `rolling`. Loops go over tickers or dates, never rows.
- **Notebooks:** `# Title`, the imports, then the settings cell (dark theme) copied from `01_data.ipynb`. Then
  `## n. Section`, and short `###` lines in plain words under each output. No em dashes, no LaTeX. A
  markdown cell that comments on an output ends with a blank line and `---`.
