# Notebooks

## Shape
- Numbered, one job each: `01_data`, `02_eda`, `03_logistic_regression`. A notebook reads what the one before it
  saved.
- `# Title`, then `## 1. Why this notebook`: what it is for and what later notebooks need from it, in plain words.
- `### Words used here`: every term a reader outside the field needs, one line each.
- Sections are `## n. Name`.
- If the project has a settings cell (theme, display options), copy it in as the second cell.
- The last cell is a numbered summary, each finding with its number.

## Code cells
- Short. One step per cell, ending in the table or number it produced, so the output shows it.
- One plot call per cell, to a function in the project's plots module.
- The maths lives in the modules' comments, not in the notebook.
- A model written from scratch gets a cell that runs the library's version with no comments, then a table comparing
  the two.
- Runs top to bottom on a fresh kernel. Downloads happen once and are saved to disk. A rerun reads them, or picks up
  where it stopped.
- A list picked by hand gets a comment saying how it was picked.

## Markdown cells
- Under each output, short `###` lines in plain words saying what it shows, with the numbers. First person is fine
  ("I will drop it").
- Every number in a markdown cell is visible in an output above it.
- Before a hard step, one or two lines on what it does and why, then the code.
- A cell that comments on an output ends with a blank line and `---`. Section headers and cells that introduce the
  next code cell don't.
- No em dashes, no LaTeX, no metaphors, no lead-in or wrap-up sentences.

See `examples/notebook_cells.md`.
