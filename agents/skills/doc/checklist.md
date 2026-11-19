# Doc checklist

Check a document, slide text or notebook markdown against `SKILL.md` and the repo's own rules. Report problems; don't
fix them while checking.

## What to read
1. What you were given: a markdown file, a PDF, a notebook's markdown cells, or slide text. If a script builds the
   document, check the rendered text and name the script line to change.
2. The repo's rules (`agents/repo_rules.md`, `agents/this_repo.md`), and the brief the document answers if there is
   one. Where they differ from `SKILL.md`, the repo wins.
3. `SKILL.md`.

## What to ask, in this order
1. Would a reader who isn't technical follow it? Undefined terms, jargon, a chart with no description of how it was
   made, a statistic with no plain explanation, a number with no comparison.
2. Is every number backed? A number with no table, chart, output or file behind it. Where the source is in the repo,
   check the number against it. A number whose group is unclear (sample or full data, offered or enrolled).
3. Filler: lead-in and wrap-up sentences, scaffolding such as "this and only this" or "not X but Y" when nobody would
   pick X, a closing paragraph that repeats the body, prose that repeats a table.
4. Wording and layout: vague phrases, metaphors, a sentence carrying more than one idea, a bullet longer than three
   sentences, a paragraph packing several facts that should be sub-bullets or a small table, em dashes, capitals for
   emphasis.
5. Shape: no opening line saying what the document is, sections out of the brief's order, boxes of key points, a gap
   presented as a choice, slide points that read like a script.

## Report
- Keep the order above. One line per problem: where it is (the section and the sentence's first few words, or
  `path:line`), what is wrong, then the plainer version.
- Mark a judgment call as one, and say why.
- End with the number of problems, or "Nothing found". No praise and no summary of the document.
