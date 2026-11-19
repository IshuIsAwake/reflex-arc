# Notes on the two example documents

## The model: the pairs trading project summary
`Pairs_Trading_Project_Summary_Group1.pdf`, 2 pages, a project plan for a course. Near perfect. What makes it work:
- A title, then one line with the course, the university and the group.
- The problem in plain words, with the key term explained in the same sentence: "pairs trading: buy one stock and
  sell a closely related one, so that market-wide moves largely cancel out and profit comes only from the gap
  between them closing."
- The goals as three short labelled questions: "Goal 1: Find the pairs. Which stocks genuinely move together?"
- An honest line about the team: "We are new to quantitative finance: in this project we are building, testing and
  learning at the same time."
- Tables carry most of the content: research questions with their hypothesis and how each is tested, data sources
  with what each adds and how it joins, formulas with what each tells us.
- The stakeholder's own question next to the formal one: "Does business logic matter?"
- A formula table in simple form, with a plain column: "Half-life, h = ln 2 / θ, days for a gap to close halfway".
- Bullets that open with a bold label: "**Time split:** pairs and rules are fixed on 2020–23 and judged only on
  2024–25."
- Each deliverable mapped to the decision it supports.
- Detail kept elsewhere and pointed to: "Terms (OHLC, VWAP, open interest …) are explained in our Glossary sheet;
  download code is in our Data Sources notebook."
- Two compact pages: bold header rows, numbered section headings, nothing decorative.

## Needs corrections: the ADS assignment report
`ads_assignment_report.pdf`, 5 pages, results for two analyses.

### Keep
- The first line says it is a summary and links the repo with the full code and results.
- The sections follow the assignment brief's headings, in its order.
- A finding leads with its number: "Website ads get a higher CTR than app ads: 19.8% against 12.0%."
- A chart described by the steps that made it: "we took the raw output of logistic regression, its predicted CTR,
  for every ad in the test set, sorted the ads by it and split them into 10 equal bins."
- The baseline explained, with how it was picked, before any model is compared with it.
- Bold questions answered with numbers: "Was the lottery fair?", "Does each group gain? Yes."
- Each section says who its numbers are about: "Every number in this section compares everyone offered training
  with everyone not offered."
- An "In simple words" column in the model table.
- A plain translation for the reader who has to act: "For policymakers: on average, an applicant offered training
  earns about ₹9,000 more at 30 months."
- "Not done yet" for the parts that aren't done.
- Recommendations as a table: question, answer, why.

### Fix
- **Clumped blocks.** "Our sample" in section 2, "Was the lottery fair?" and "How we test it" each pack four to six
  facts into one paragraph or bullet. The content is right; the layout makes it read as wordy. Keep the words and
  split the block: a bold label with the main point, then one fact per sub-bullet, and numbers that compare go in a
  small table. Rewritten that way:

  **Our sample:** every 40th row of each split, about 1 million rows, because that is what fits in our graphics
  card's memory.
  - All 40 million rows come later, with batching (training in small chunks) and a neural network written from
    scratch.
  - The sample still looks like the full data. Hourly CTRs differ only as much as chance would.

    |               | Full data | Sample |
    |---------------|-----------|--------|
    | Quietest hour | 11,877    | 298    |
    | Busiest hour  | 358,731   | 8,967  |

  **Was the lottery fair?** If it was, those offered and not offered should differ only by chance. We compared them
  on 14 background facts (past earnings, schooling, age, caste and so on).
  - The largest gap is the SC share: 18.3% against 17.4%, or 0.025 standard deviations. It is the only p value below
    0.05 (p = 0.017).
  - At a 5% false positive rate, 14 tests are expected to give 14 × 0.05 = 0.7 false positives, so one is not
    surprising.
  - With the Bonferroni correction the cut-off becomes 0.05 / 14 = 0.00357, and 0.017 is clearly above it.
  - In every state, exactly 2 in 3 applicants were offered training.

  The lottery looks fair.

  **How we test it:** we want to see whether zero, meaning no effect, lies outside the 95% confidence interval (CI)
  of the difference in means.
  - CI = difference ± 1.96 standard errors.
  - The standard error says how much the difference would move by chance from one sample to the next. It comes from
    Welch's t-test, which does not assume both groups vary equally.
  - 1.96 is the 95% value of the t distribution, which is effectively normal with this many people.
  - If we repeated the study 100 times, about 95 of the CIs would contain the true effect.
- **Jargon the reader doesn't need:** "its standard errors are heteroskedasticity-robust".
- **Numbers said twice:** the baseline paragraph repeats "ROC-AUC 0.5" and "F1 0" from the table just above it.
