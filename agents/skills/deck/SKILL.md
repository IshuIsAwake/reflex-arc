---
name: deck
description: Builds slide decks (idea pitches for hackathons and grants, project and course presentations) in Canva, Google Slides or PowerPoint. The idea before the demo, one idea per slide, little text, real proof, and a look of its own for each deck. Builds once the content is settled. Use when making or rewriting a presentation.
argument-hint: "[what the deck is for, who sees it, and the link or template]"
---

# Deck

A panel sees each slide for a minute while listening to the speaker. They should get the idea from the pictures and
headings, and the points should back up what is said, not repeat it.

## Before building
- Read the project's CLAUDE.md, HANDOFF.md and memory, the brief or official template, and any earlier deck or
  written submission for the same idea. Where the project disagrees with this file, the project wins.
- This skill builds. What to pitch, and the research behind it, is worked out in conversation first. If that isn't
  settled yet, say so instead of building.
- Before building, give a slide-by-slide outline in the chat: each slide's heading, each image with its subheading and
  what it shows, and the points. Build only after the user's go-ahead.
- Every number comes from an output, a table, a file or a source you can point to.

## What to say
- Pitch the idea, not the demo. Describe the real thing (a rover on Mars, a published package) and use the demo as
  evidence: screenshots, the video, links. Feasibility says why the idea can work in its real setting, not why the
  demo works.
- Open with the vision and the problem. Hold back the term that starts the "why?" questions until the questions
  part: "a rover that works on its own", not "a language model on Mars".
- For an audience new to the field, build up to the problem one concept per slide, each heading a question the slide
  answers: "What is trading?", "What is quant trading?". Say which part is yours: "Equities (shares) - this is our
  focus". The background stays short; it is there so the problem makes sense.
- Put the problem in the client's terms (who the client is, the decision they face, the measures of success, the
  constraints) and the hypotheses beside it as statements that can be tested.
- Show that the problem exists with real cases and their numbers: incidents, failures, hours lost. Mark an estimate as
  an estimate, and a diagram that isn't to scale as "illustrative, not to scale".
- Show that it is real: an install command, a published package, a benchmark table, a demo video, a website, the
  repo. Present a tool the way you would present a product. A plan with no results yet shows the data sources with
  what each gives, the approach as numbered steps, and the deliverables.
- Spend the space on what is new, such as an architecture of your own. "Technologies used" is one line of names.
- The strongest true version: the most favourable honest framing and the best measured numbers. Never a number that
  wasn't measured, and never "first" or "only"; write "among the papers we found". Where the demo falls short of the
  real system, say so in the demo part.
- Nothing the panel won't follow: no jargon, no method detail they can't judge. Explain a term in a few words or
  leave it out.
- For an academic panel, a link to the course helps: a concept or algorithm they taught.

## Slide text
- One idea per slide. Pictures before words, and text backs up the picture next to it.
- A point fits in two lines, about 15 words. Text under an image is three short sentences at most. A block packing
  several facts becomes points, or a small table, such as challenge and strategy side by side.
- A comparison is a small table of short contrasts, one row per way they differ, as in "Discretionary vs Quant".
- A concept gets one concrete example: "e.g., Coca-Cola & Pepsi". A process is a chain of arrows: "Data → Model →
  Signal → Automated order".
- Points, not a script. Cut words that only work spoken: "So", "Now", "As you can see". Write a spoken script, in
  speaker notes or a separate file, only when the user asks.
- Every image gets a subheading that says its role: "The problem", "Proposed solution", "Technologies used".
- Headings follow the official template, in its order. The title slide has the name, a line saying what it does, and
  the authors: "A mean reversion strategy to support trading decisions".
- Each number once per slide. A short closing line is fine when it is the claim: "Any sensor. Any world. Zero code
  changes."
- References grouped by what they support: the problem, the method, ours (repo, package, website, video). A link
  under an image says what is behind it.
- Plain words, exact over vague, no em dashes, no capitals for emphasis.

## Look
- Each deck gets its own look, taken from its field: candlestick charts in red and green for a trading project, Mars
  images for a rover, a project website's colours. Never reuse another deck's colours or copy its slides one to one.
  The effort should show.
- Use the project's own images: photos of the hardware, screenshots, model outputs, a terminal running the real
  commands.
- A concept is easier as a labelled diagram: the mean, the gap opening, the gap closing.
- A chart only where it beats points. Its title states the finding: "GHOST has run on 61 to ~400 bands. ISRO's
  cameras fit right in."
- Text must be readable from the back of the room. If it doesn't fit, cut words instead of shrinking the font.

## Working in a slide tool
- If the deck already exists, copy it first and work on the copy. Never edit the user's original.
- When the user has laid out the visuals and left instruction boxes, keep the layout and replace only those boxes.
- Show the changes (thumbnails or the new slide text) before saving them.
- Never put a link that lets someone edit the deck in a file git tracks.
- For a submission or a backup, export to PDF.

## Checking and handing over
- Look at every slide as rendered: nothing cut off, overlapping or too small to read.
- Go through `checklist.md` against the slide text and fix what it finds. If your tool can start a fresh subagent,
  give the checklist to one, so the slides aren't checked by the session that wrote them.
- Hand over: the deck's link or file, where each number came from, and anything not done or still open.

## Examples
Three decks made this way: a course project pitch and two hackathon decks, with team details blacked out. They show a
style, not a template: take what helps.
- `examples/ads_project_idea.pdf`, an 8-slide course project pitch, is the model.
- `examples/angaraka_sih_deck.pdf` and `examples/ghost_sih_deck.pdf` show proof, a template followed in order, and a
  look per deck, but are wordy in places.
- `examples/notes.md` lists what works in each, and what to cut from the hackathon decks.
