# Ideas, round 2 — what changed

Outcome of the session of 2026-08-18, after digesting two adversarial critiques
(see [`02-critique-response.md`](02-critique-response.md)) and working through the memory
and learning questions.

Supersedes parts of [`01-ideas.md`](01-ideas.md); that document is still the superset of raw
ideas and its §2 architecture, §5 domain properties, and §9–10 constraints stand unchanged.

**Still not scope.** Scope waits for team headcount and commitment levels.

---

## 1. The framing changed

**We are not writing a paper.** The goal is a system that plays Hollow Knight autonomously,
built from scratch, understood end to end. The reason is explainability and learning, not
publication.

**The architecture is not the contribution.** "LLM plans, RL executes" is a published
baseline (five instantiations, §1 of the critique response). Nobody will be impressed by the
structure. What is unoccupied is the *regime* and the *measurement*.

**The claim to make is about duration and recovery, not novelty.** Every comparable system
runs for minutes, or for many short episodes with resets. A multi-hour unbroken autonomous
run is a harder thing to state than anything in that literature.

**Demo framing: recovery beats perfection.** A system that misjudges a jump, dies, walks back,
retrieves its shade, and re-plans is more convincing than one that never slips — and much
harder to accuse of being a TAS. Perfection reads as scripted. Recovery reads as intelligence.
Do not aim for a flawless run.

## 2. The one thing kept from the "paper" version

**Find out whether the LLM earns its place.**

Not to publish. Because otherwise months go into a planner layer that a twenty-line lookup
table would match, and nobody would ever find out. In the closest prior work (Hösch et al.),
LLM+RL scored 46.4% against a hand-crafted behavior tree's 51.5%, p = 0.103 — a tie.

The A/B/C design in `01-ideas.md` §6.1 is therefore missing a condition:

- **A** — one RL policy trained across everything (honest "just do RL" baseline)
- **B** — the modules, style/target fixed or random
- **C** — the modules, LLM chooses
- **D** — the modules, **hard-coded lookup table** chooses per target ← *new, and the one that matters*

If C beats B but ties D, the finding is "world knowledge helps, and so does a dictionary."

## 3. Two regimes, not one — and the compounding math

The critique applied multiplicative failure (0.95⁴⁰ ≈ 13%) to the whole game. That is wrong
for most of Hollow Knight and right for one part. The split is the most useful structural fact
about the domain:

**Overworld (Any%, 112% collection) is recoverable.** Death → last bench, lose geo, walk back,
retrieve shade. Progress is *persistent*. A 3-hour run is not a chain of 150 rooms that must
all succeed; it is a random walk with net forward drift plus a recovery loop. The question is
not "can it avoid failure for three hours" but "does it recover and re-plan" — which is
precisely what the critique itself identified as the hard problem in real deployment.

**P5 is genuinely all-or-nothing.** 42 bosses, no checkpoint, ~45–60 min continuous:

| per-boss survival | P5 clear rate |
|---|---|
| 90% | 1.2% |
| 95% | 11.6% |
| 99% | 65.6% |
| 99.9% | 95.9% |

This is why a human needs 40–80 hours to first-clear it. **P5 is an asymptote to report a
number against, not a target to promise.** 50% game completion is a real and honest milestone.

## 4. Three kinds of memory — the missing one

The confusion about "can the LLM experience the game" dissolves once these are separated:

| kind | what it holds | where it lives | who can read it |
|---|---|---|---|
| **Semantic** | "There's a Seal above the stag platform" | wiki / RAG store | LLM |
| **Procedural** | how to actually time a pogo | policy weights | nobody — not even the LLM |
| **Episodic** | "attempted that pogo 6× at 2 masks; worked once" | *missing* | LLM |

`01-ideas.md` designed the first, has the second, and has **no third**. "Experience" =
episodic memory. The competence table is a crude, static, aggregated version of it.

### The read path vs. the write path

The real axis is not *how much the LLM does* — it is **what the LLM reads vs. what it writes.**
Currently only the read path exists (wiki in, decision out), which is why it feels like lookup:
structurally it *is* lookup, and better retrieval does not fix it.

**Decision: add the write path.** Every skill invocation returns its outcome; the outcome is
appended to a store the planner retrieves from alongside wiki pages.

- No fine-tuning, no gradients, no added latency — writes are an append; reads happen at
  planning time (seconds), never in the control loop.
- **The model does not learn; the system does.** Weights are frozen, behavior changes because
  retrieval changes. Stating it exactly that way is honest and unattackable.
- This also closes the critique's best remaining objection — the "hallucination loop where the
  LLM repeatedly commands the agent to walk into a wall." That loop only exists because nothing
  records that the wall was already tried.

### The trap: log conditions, not just outcomes

`"failed pogo at room X"` is **worse than useless** — the LLM will over-generalize it into
"pogo doesn't work" and route around something that failed only because it was attempted at
2 masks with the wrong style dial. Every entry needs the state it was attempted from: masks,
soul, ability loadout, style vector, which primitive, structured failure code.

Consequence: **the structured failure codes in the skill API are not error handling — they are
the schema of the system's memory.** That raises their importance considerably.

## 5. RAG vs. fine-tuning — settled

**RAG:** weights frozen, knowledge retrieved into context at inference. Lives in files.
Updating = editing a file. Auditable — you can log exactly what was retrieved before each
decision.

**Fine-tuning:** gradient descent on weights. Knowledge baked in. Updating = another training
run. Not auditable.

**Rule of thumb adopted:** *if a human could learn it by reading a log, it is retrieval. If a
human could only learn it by practicing, it belongs in the RL policy weights, not the LLM.*
Corollary — fine-tuning is bad at teaching facts and good at teaching form.

### Decision: gradients stay off during play

1. **There is no loss function.** Gradient descent needs a scalar target. A playthrough
   produces an *outcome* hours later, not a next token. Turning outcomes into gradients means
   RL on the LLM itself — a separate and much heavier machine.
2. **Sample count is off by 3–4 orders of magnitude.** A run yields ~500–1000 planner
   decisions; meaningful post-training needs thousands to millions, in large batches.
3. **Credit assignment across hours.** Run fails at hour two — which of 800 decisions was wrong?
4. **Memory.** Inference ≈ 2 bytes/param; Adam training ≈ 12–16 (weights + grads + two moments).
   A model that runs comfortably may not train at all, let alone alongside N game instances.
5. **Reproducibility.** Weights drifting mid-demo means improvements cannot be attributed to
   knowledge rather than drift.

**"Can it learn that primal aspids aren't worth fighting?"** Yes — and with zero gradients.
That is a fact about outcomes: `primal_aspid | 14 encounters | mean 22 s | mean 1.8 masks lost
| 0 required for progression`. Any competent model reads that and disengages. Same for "don't
grab every mask shard" — that is opportunity cost, which is also a table.

**Both things we want it to learn are data, not weights. Data is retrievable, deletable, and
readable.**

Where fine-tuning would genuinely help *later*: output-format reliability, terser domain
vocabulary (shorter prompts → lower latency), distilling a large model's decisions into a small
fast one. All optimizations of a working system; none of them learning mechanisms.

## 6. Skips and the traversal competence table

**It will not discover skips on its own.** Finding something like the Blue Lake skip requires
either exhaustive long-horizon exploration (what RL is worst at) or grounded physics reasoning
the LLM cannot do from a room table. Do not plan for emergent skip discovery — same overreach
as frame-perfect glitch execution, already ruled out in `01-ideas.md` §8.

**Run it backwards instead.** There are ~20-odd *documented* skips. The system attempts each and
records whether its own actuators can execute it:

> "Of 23 documented speedrun skips, the agent determined 7 were within its own capability and
> routed around the rest."

That is the competence table extended from combat styles to **traversal tech**, it is a genuinely
novel measurement, and it is exactly the MLNav pattern — wiki proposes, execution verifies,
memory records.

## 7. The door-game dry run

A toy that is the whole architecture in miniature and runs on a laptop. Gemma 4 E4B is already
set up locally via Ollama in `Projects/Playground/okdriver-voice-bot`.

**The game:** a matrix of doors (rows × columns). Some lead to a puddle (restart); others lead to
a minigame (tic-tac-toe, Connect 4, card swipe, number guessing). Beat it, advance a row. **Door
layout is static per instance.**

| door game | Hollow Knight |
|---|---|
| which door to open | planner routing decision |
| minigame behind it | skill module (`kill`, `goto`) |
| puddle → restart | death → bench |
| static door layout | static room layout |
| per-executor minigame reliability | competence table |

### Conditions and predictions (written before running)

- **Case 1 — RAG, read-only** (task knowledge + per-row heuristics). *Prediction: flat.* Attempt
  50 looks like attempt 1. Nothing persists across deaths, so it re-enters the same puddle door.
  **This is where the HK design currently sits.** Watch for the trap: with good heuristics it can
  look excellent on run #1 and never improve.
- **Case 2 — RAG with write access.** *Prediction: fast monotonic improvement.* Each death
  permanently eliminates one door; worst case ≈ R×(C−1) deaths. Tabular Q-learning would need
  many visits per door to lower its estimate confidently; the LLM eliminates a door in **one
  observation**, because it reasons rather than averages. Metric shifts from pass/fail to
  **deaths-to-clear** — the same metric as HK.
- **Case 3 — gradients on.** *Prediction: worse than Case 2, and may not get off the ground.*
  No loss without manufacturing one; behavior-cloning needs Case 2 working first to generate
  data; a few hundred decisions degrades output formatting before it improves play. Decisive
  point: **fine-tuned knowledge cannot be deleted.** Regenerate the maze — Case 2 is
  `rm log.json`; Case 3 now holds confidently wrong beliefs in its weights and performs *worse
  than Case 1*, which at least had no false beliefs. Negative transfer, cheaply demonstrated.

### The extension that carries the most value

Give the executors **deliberately uneven, hidden reliabilities** (tic-tac-toe 95%, Connect 4 60%,
card swipe 99%, number guessing 40%) and do not tell the LLM. It must then discover which
minigames its own body is good at and route toward them. That splits Case 2:

- **2a** — log door outcomes only → learns the maze
- **2b** — log door *and* executor outcomes → learns the maze **and its own limits**

If 2b beats 2a, the value of self-competence grounding has been measured on a laptop before a
line of Unity code exists. That is `01-ideas.md` §6.2 for free.

**Method note:** predictions above were written before running. If Gemma surprises us, that is
the finding — and it is only visible because we committed first.

## 8. Failure modes to watch (from this session)

- **Under-specified memory entries** — poisons the log, makes the system dumber than no memory.
- **Over-generalization from 2 samples** — "even doors are safe," "that enemy class isn't worth
  fighting." LLMs do this readily.
- **Log growth → context bloat → retrieval degradation.** Needs structure or summarization.
- **The flat-but-impressive first run** — a read-only system can demo well and never improve.
  Always measure across repeated attempts, never a single run.

## 9. Open questions added this round

- [ ] Does the LLM layer beat condition **D** (hard-coded per-target lookup)? *Highest priority.*
- [ ] Schema for episodic memory entries — what state must accompany every outcome?
- [ ] How does the experience log stay small enough to retrieve well over a 3-hour run?
- [ ] Does 2b beat 2a in the door game? (Proxy for whether the competence table is worth building.)
- [ ] What is the actual decision frequency needed? OC-STORM used 9 FPS, not 60 Hz — "60 Hz
      reflexes" is a claim to test, not assume.
