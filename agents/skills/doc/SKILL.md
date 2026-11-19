---
name: doc
description: Drafts documents (reports, project summaries, READMEs, design docs, updates for a manager or client) for a reader who isn't technical. Plain words, every claim with its number, no filler. Drafts once the content is settled. Use when drafting or rewriting a document.
argument-hint: "[what to write, and for whom]"
---

# Doc

Write for a reader who isn't technical, unless the user names another reader. They should follow every sentence on the
first read and be able to repeat the main findings without the document in front of them.

## Before writing
- Read the project's CLAUDE.md, HANDOFF.md and memory, and the brief the document answers. Where the project
  disagrees with this file, the project wins.
- This skill drafts. What the document should say is worked out in conversation first. If that isn't settled yet,
  say so instead of drafting.
- Before drafting, give a short summary in the chat: the reader, the sections, what each one says, and the numbers
  it uses. Draft only after the user's go-ahead.
- Every number comes from an output, a table or a file you can point to. If a notebook doesn't show it yet, add it
  there first.

## Shape
- The first line says what the document is. For a report: "This report is only a summary of what was done and what
  was found. All the code and detailed results are at: <repo link>"
- Sections follow the brief's headings, in its order. Without a brief: the conclusion, then the reasoning, then what
  it means, then references.
- Start with the content. No boxes of key points, no abstract that repeats the body, no contents page for a short
  document.
- Short. About a page per part for anything outward-facing. The detail lives in the repo and gets a link. Cut
  whatever the reader wouldn't miss.
- Say plainly what isn't done or decided: "Not done yet: ...". Never present a gap as a choice.
- Stop when the content ends. No closing paragraph that repeats the body.

## Sentences
- One idea per sentence, in plain words. A bullet holds one point, in three sentences at most.
- A block that packs several facts reads as wordy even when every word is needed. Split it: a bold label with the
  main point, one fact per sub-bullet, and numbers that compare in a small table.
- Exact, not vague: "within websites and within apps", not "among the larger categories".
- Lead with the finding and its number: "The hour barely matters for CTR, even though traffic varies from 2% to 6% of
  ads from hour to hour."
- Say each number once. Don't repeat in prose what a table already shows; add only what the table can't say.
- Call things what the reader will see: the column name, the file name, the label on the chart.
- No lead-in sentences ("In this section we will..."), no wrap-up sentences ("Overall, this shows..."), and no
  scaffolding such as "this and only this", or "not X but Y" when nobody would have picked X.
- No metaphors. Say what happened.
- No em dashes, no words in capitals for emphasis, no LaTeX in prose.

## Explaining
- A term the reader may not know gets a plain explanation the first time it appears: "batching (training in small
  chunks)". Terms used in several places go in a short "Words used here" list near the top.
- A chart is described by the steps that made it, then what it shows.
- Say what the baseline is, and how it was picked, before comparing anything with it.
- A statistic is built up from its formula, then what it means, then what it decides, in words the user could say
  to an examiner or a reviewer. For a confidence interval: the difference ± 1.96 standard errors; if we repeated the
  study 100 times, about 95 of these ranges would contain the true effect; so if zero is outside the range, the
  effect is unlikely to be chance.
- Say who a number is about: offered or enrolled, the sample or the full data, test rows or training rows.
- A number gets its comparison: against the baseline, against chance, or against the other group.
- An action is written as steps someone could follow: "Run each ad through the model, multiply its predicted CTR by
  the price per click, sort, and give the top ads the most budget."
- A pattern is not a cause. When something else could explain it, say so, and say what would settle it.
- A reader who has to act gets a plain translation: "For policymakers: ...", "For the clinic: ...".

## Tables and charts
- Plain tables: black text, a grey header row, no colours in the cells. A table comparing methods gets an "In simple
  words" column.
- A chart's title states its finding, not its axes: "Website ads get more clicks than app ads".
- Only the charts the argument needs, usually one or two per part.
- Every number in the text appears in a table or chart in the document, or in the repo it links to.

## Reports as PDF
- The title line names the document and the author details the brief asks for, like "<Course> Assignment Report -
  <name> - <class> - <roll number>".
- A4, one body font, part headings in one colour, page numbers.
- A report with results is built by a script that reads the project's saved results, so rerunning the notebooks and
  then the script rebuilds the PDF. The example report was built this way, with reportlab for the pages and
  matplotlib for the charts. A plan or summary with no results can be a document file
  exported to PDF.
- Look at the rendered pages before handing over.

## Checking and handing over
- Before showing the result, go through `checklist.md` against the document and fix what it finds. If your tool can
  start a fresh subagent, give the checklist to one, so the writing isn't checked by the session that wrote it.
- Hand over: what was written and where, where the numbers came from, and anything not done or still open.

## Examples
Two university documents written this way. They show a style, not a template: take what helps.
- `examples/Pairs_Trading_Project_Summary_Group1.pdf`, a two-page project plan, is the model. It is near perfect.
- `examples/ads_assignment_report.pdf` shows how to write up results, but needs corrections, mostly in layout.
- `examples/notes.md` lists what works in each, and what to fix in the second.
