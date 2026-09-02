# What prototype 2 closed

## `why` became optional

`goto`'s `why` was required while `without_why` stripped it out of the history she reads back,
so every past call she could see was an example of omitting it — and she learned to omit it:
0 of 79 calls missing across four runs, then **16 of 21** in `runs/20260901-000753/`, each one a
`BAD_ARGS` that also cost a hop. Making it optional took that to **0 of 13** in
`runs/20260902-224413/`.

The price: she now supplies `why` twice in thirteen calls, both on the first turn, so the
reason-before-outcome trail in the pane is mostly gone.

## Reading the map: four models, one probe

30 questions over three worlds (17%, 62% and 77% explored), scored against the view block she was
actually shown rather than against the world. Unblocked arm, errors excluded.
`game/probe_map.py` asks, `game/probe_read.py` scores.

| | gemma4:e4b (4B, local) | gemma4:e4b (rerun) | gemma-4-31b-it | gemini-3.5-flash | gemini-3.7-flash |
|---|---|---|---|---|---|
| **cell** — what is at (x,y) | 28/63 · 44% | 17/36 · 47% | 39/60 · 65% | **21/21 · 100%** | **3/3** |
| **region** — count a 30-cell box | 0/42 · 0% | 0/24 · 0% | 0/41 · 0% | — | **1/1** |
| **row** — count a span | 0/21 · 0% | 0/12 · 0% | 0/19 · 0% | — | — |

Majority-class baseline on `cell` is 33–35%. The gemini runs are short because the free tier
allows 20 requests per day per model and failed requests count against it.

- **Scale inside the gemma family changes nothing.** Eight times the parameters, same family and
  tokenizer, the same zero on both counting questions.
- **The 31B's 65% is not a read.** open 20/20, unseen 19/19, rock **0/21** — it never emitted ROCK.
- **The picture is readable.** gemini-3.5-flash got every cell including rock; 3.7-flash also
  counted a 30-cell box exactly right. Counting into the grid is a gemma limitation, not an
  LLM one.

The four qualitative questions are excluded: `near_rock` generated 42 items all with truth
`rocky`, and `biggest_fog` has a baseline between 0.71 and 1.00 depending on the world. Neither
can be failed, so neither measures anything.

Tapes are in `runs/probe-*/`, which is gitignored.
