# Notes on the example decks

## The model: the ADS project idea deck
`ads_project_idea.pdf`, 8 slides in Canva, pitching a course project (pairs trading) to a class and a professor.
What makes it work:
- The title slide has the project's name, a line saying what it does ("A mean reversion strategy to support trading
  decisions") and the authors.
- The audience is new to trading, so it builds up one concept per slide before the problem: trading, quant trading,
  discretionary against quant, algo trading, then mean reversion and pairs trading.
- Each heading is the question the slide answers: "What is trading?", "What is quant trading?".
- It says which part of the background is theirs: "Equities (shares): ownership in companies (Apple, Reliance) - this
  is our focus".
- Points are short, about 15 words or fewer, and each holds one fact.
- A comparison is a five-row table of short contrasts: decisions, basis, consistency, testable, scale.
- A concept gets one concrete example: "e.g., Coca-Cola & Pepsi, Exxon & Chevron".
- A process is a chain of arrows: "Our pipeline: Data → Model → Signal → Automated order".
- A labelled diagram explains mean reversion: the mean, the gap opening (divergence), the gap closing, profit and loss.
- The problem is in the client's terms (client, decision, KPIs, constraints), with three testable hypotheses beside it.
- The plan, with no results yet: the data sources with what each is for, the approach as five numbered steps, and the
  deliverables.
- One look throughout, taken from the field: a dark background of price tickers, candlestick charts and red and
  green arrows, one picture per slide, text on one side and the picture on the other.

## The SIH 2026 decks: `angaraka_sih_deck.pdf` and `ghost_sih_deck.pdf`
Two 6-slide Canva decks on the official SIH template, submitted 30 Sept 2026. The structure, proof and look are
good. Some text blocks are wordy.

### Keep
- The template's headings in order: title, problem and solution, technical approach, feasibility and viability,
  impact and benefits, research and references.
- Every image has a subheading saying its role: "Scenario 1: remote human control" is the problem, "Scenario 2:
  onboard AI control" is the proposed solution.
- The idea, not the demo: Angaraka is pitched as a rover on Mars. The simulation and the real rover appear only as
  screenshots and video links.
- Proof that it is real (GHOST): a terminal running `pip install ghost-hsi`, `ghost --version` and `ghost demo`; the
  same code on farmland, Mars and lung tissue in one picture; a benchmark table; the demo video on a fresh Colab
  notebook; the website.
- Short points that each carry one fact: "Ready today: pip install ghost-hsi, then run. No setup, no code changes."
- A chart whose title is the finding: "GHOST has run on 61 to ~400 bands. ISRO's cameras fit right in."
- An estimate marked as one: the "One sol with and without Angaraka" timeline says "proportions illustrative, not to
  scale".
- The audience named: "Mission teams at ISRO, NASA and ESA".
- A gap turned into a plan: "v0.2.0 reads each pixel's own spectrum only. It is already in production and scores 87%
  on Indian Pines without any neighbours."
- A short closing claim: "Any sensor. Any world. Zero code changes."
- References grouped as the problem, the method and ours, with the repo, package, website and video links last.
- A look per deck: Angaraka dark with Mars images, GHOST black and white like its website.

### Cut
- **The problem text on Angaraka's slide 2** is five sentences in one centred block. As points:
  - Every sol is planned on Earth, 3 to 22 light-minutes away.
  - Rovers avoid obstacles on their own, but Earth still picks the goals.
  - Something new turns up? The rover follows yesterday's plan, or waits a sol.
- **Feasibility points that run to three or four lines.** "Tried and tested - by giving the SLM tools like a
  scratchpad and a memory document, it is able to carry forward context cheaply across multiple days without ever
  poisoning its context." becomes "Tested: a scratchpad and a memory file carry context across sols."
- **Challenges and strategies as paragraphs.** Each packs the problem, a number and the fix into one block. A small
  table reads faster:

  | Challenge | Strategy |
  |---|---|
  | Today's rover computer (RAD750, 200 MHz, 256 MB) is too small for a language model | NASA's HPSC chip: over 100× the computing, built for onboard AI |
  | Told to go to (3,4), the rover stops at (3,3) | LiDAR re-measures after every leg, and the plan restarts from there |

- **GHOST's methodology paragraph** packs four steps into one block. The flowchart next to it already shows them, so
  the text needs one line per step.
