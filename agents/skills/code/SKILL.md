---
name: code
description: Write simple code the user can explain line by line, split into modules so notebooks and experiment files stay short and pieces get reused. Starts with a plan the user approves. Use when writing or changing code.
argument-hint: "[what to build]"
---

# Code

Explainable and a little longer beats short and clever. A line the user can't explain gets rewritten, even if it
works.

## Before writing
- Read the repo's rules (`agents/repo_rules.md` and `agents/this_repo.md`, if the repo has them), its `HANDOFF.md`
  and its memory. Where they disagree with this file, the repo wins.
- Read the code already in the repo and match it.

## Start with a plan
Skip this section only when the user says to build straight away. Then name the files you will touch in two lines
and start.
- Enter plan mode before changing anything. Where your tool has no plan mode, write the plan in the chat and wait for
  a yes.
- The plan lists:
  - every file to create, change or delete, and what changes in each
  - new modules, classes and functions by name, one line each on what they do
  - what will be run to check the work, and on which slice
  - anything still undecided, as a question
- Discuss the structure until the user approves the plan. Change nothing before that.
- If the open question is what to build rather than how, settle that in conversation first instead of inside the
  plan.

## Who reads the code
The user, and anyone who knows the language and the basics of the subject but has never seen this project. After
one read they can say what every line does and why it is there. The user has to be able to defend each line in an
exam, a review or a demo without looking anything up.

## Layout: a short top level, modules underneath
- The notebook or experiment file is the story: load, change, show, conclude. It imports the rest.
- Move code into the project's module folder (such as `src/`) when it is used twice, or when it is detail that
  hides the story: a plot, a statistic's formula, a model's maths, a file format, an API call.
- One module per job: `plots.py` draws, `stats.py` computes statistics, `base.py` plus one file per model family. In
  bigger projects, one module each for logging, storing results and comparing runs.
- A plot is a function written once and called in one line from any notebook. It aggregates first, then draws one
  figure whose title says what it shows.
- An experiment file only imports and runs. A new experiment is a short file and its settings, never a copy of the
  previous experiment.

## Classes
- Use a class when several versions of one thing share a shape. The base class fixes the steps and each subclass
  overrides only what differs. In `examples/`, `Model` runs gradient descent, `LogisticRegression` fills in the
  formula, and `WeightedLogisticRegression` changes only the loss.
- Use a class when something keeps state between calls, like a trained model or a client holding a connection.
- A job with no state stays a function.
- Keep inheritance shallow: a base, its versions, and at most one version of a version.

## Inside a function
- Plain building blocks: `for` loops, `if`, lists, dicts, pandas and torch operations.
- Names are plain words from the problem (`members`, `stretches`, `coverage`). Short maths names (`X`, `W`, `p`, `lr`)
  are fine when a comment gives the formula they come from.
- One job per function, one you can say in a sentence. Short enough to explain in a minute.
- No tricks: nested comprehensions, lambdas passed around, chained `a if x else b if y else c`, the walrus `:=`,
  attributes looked up by a string at runtime. Write three plain lines instead.
- No dead code, unused parameters, or options nobody asked for.
- Don't guard against cases that can't happen. Do check what really can fail: downloads, files, user input, API
  replies.
- With large data, use pandas or torch operations (`groupby`, `rolling`, matrix maths). Loop over groups, never over
  rows.
- Normal formatting: 4-space indents, a space after each comma and none before, no lining up `=` signs or comments
  into columns. Two matching values may share a line (`y1, y0 = y[z == 1], y[z == 0]`), and a formula inside a
  docstring or comment may be laid out in columns so it reads like maths.
- No new library without asking.

## Comments and docstrings
- A comment gives the reason or the maths. It never repeats what the line says and never tells history ("changed from
  X"). For example:
  - the derivation above a model method: `# dJ/dW = X.T (p - y) / n`
  - why a number was picked: `# 5 days of slack, a spin-off can join the index a day or two before it starts trading`
  - where a hand-picked list came from: `# old ticker: ticker today, each one confirmed by a web search`
- Short and lowercase, one or two lines. No banner comments, and no docstring on every function.
- A module function's docstring says what goes in, in plain words:
  `table: one row per year, share = member days with prices / member days`.
- No em dashes, no words in capitals for emphasis, no jargon such as "canonical" or "load-bearing".

## Notebooks
Read `notebooks.md` before writing or changing a notebook.

## Production code
The same rules. On top of them:
- Follow the repo's folder layout and its config file.
- Type hints where the repo already uses them.
- A test file for each module whose logic could break quietly.

## Checking and handing over
- Run each piece on a small slice (a few rows, one year, a few images) before handing it over. The user does the
  full run.
- A long run gets one command the user can paste.
- Before showing the result, go through `checklist.md` against the changed code and fix what it finds. If your tool
  can start a fresh subagent, give the checklist to one, so the code isn't checked by the session that wrote it.
- Hand over: what changed, what was run and on which slice, and what wasn't checked.

## Examples
The examples show a style, not a method. They come from coursework that asked for models written from scratch,
which is why there is no sklearn in them. Use libraries as usual unless your project says otherwise.

- `examples/base.py`: a base class that fixes the training loop. Subclasses fill in three methods.
- `examples/logistic.py`: a model and a weighted version, with the derivation above each method.
- `examples/stats.py`: statistics as plain functions, each built up from its formula in the comments.
- `examples/plots.py`: one function per chart. Each aggregates first, then draws one plotly express figure.
- `examples/notebook_cells.md`: cells from a data notebook, an EDA check and a model notebook.
