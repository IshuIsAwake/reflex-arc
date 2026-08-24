# Hollow Knight — the coursework implementation

The design and the experiments. The idea itself is in [`../README.md`](../README.md), the
implementation-level half in [`technicalities.md`](technicalities.md), and the raw ideation of
2026-08-17 and 2026-08-18 in [`00-raw-transcript.md`](00-raw-transcript.md). Rejected ideas keep
their reasoning so they don't get rediscovered.

Section numbers run continuously into `technicalities.md`, which starts at §9.

---

## 1. Thesis

An LLM knows everything about Hollow Knight and cannot press a button. RL policies have
frame-perfect motor control and no idea what a Hallownest Seal is.

**That first clause is not hypothetical, and the demonstration is worth keeping.**
[`00-raw-transcript.md`](00-raw-transcript.md) lines 262–345: asked for a one-time geo source in
King's Station, the model retrieved the Seal's location from the wiki *and* derived a bench-reset
farm the wiki never stated — then, told to go and collect it, checked for a running process and
reported it had no hands. `goto(x, y)` and `kill(target)` were written down in the next paragraph.
The architecture was diagnosed, not designed. Show this rather than argue it.

- Technically: an LLM as the **gating function** over a library of conditioned expert policies.
  Mixture-of-experts, except the gate is a reasoning model instead of a learned linear layer.
- **Not Voyager.** Voyager generates *code*, in a domain where scripted actions suffice because
  Minecraft never demands frame-level reaction. Here the skills can only be learned.

## 2. What we are claiming

The architecture is not the contribution; the regime is — precision timing, a reactive opponent,
hours of unbroken execution ([`02-critique-response.md`](02-critique-response.md) §1).

**Recovery beats perfection in a demo.** A system that misjudges a jump, dies, walks back,
retrieves its shade and re-plans is more convincing than one that never slips — and much harder to
accuse of being a TAS.

## 3. Architecture

```
          ┌──────────────────────────────────────────┐
          │  LLM planner (local: Gemma / Nemotron)   │   seconds
          │  + RAG over wiki  + experience log       │
          └───────────────┬──────────────────────────┘
                          │  goto(x,y) · kill(target) · style/risk dial
          ┌───────────────┴──────────────────────────┐
          │   frozen conditioned expert policies     │   60 Hz
          │   combat module   ·   traversal module   │
          └───────────────┬──────────────────────────┘
                          │  MAPI / Harmony mod layer
                    Hollow Knight
```

**Combat module.** Target-conditioned: `π(a | s, target_features, style)` — one network, not one per
boss. Encode targets by **observable features** (hitbox, HP, velocity, aerial or grounded, FSM
state, projectiles), **never a one-hot enemy ID**; doing this right makes "kills a boss it has never
seen" an available result. A **style dial** replaces training N personalities: condition on the
reward-weight vector, get a slider at inference. Not reward shaping — shaping preserves the optimal
policy, this deliberately changes the objective.

**Traversal module.** Goal-conditioned: `π(a | s, goal_vector, risk)`.

- **HER is the unlock.** Every failed traversal is a successful demonstration of reaching wherever
  it actually landed. Sparse reward becomes dense for free.
- **Short-horizon, 1–3 seconds.** The planner routes waypoints with plain A\* on a discretised room,
  so Path of Pain becomes ~40 short goals and all learning lives in the movement primitives.
- **A local occupancy grid buys the generalisation.** ~32×32 tiles centred on the knight, channels
  for solid, spike, platform, enemy and moving hazard, goal as a relative vector, rasterised from
  Unity colliders. The policy cannot memorise a room because it never sees one.
- **World coordinates**, since the camera moves and the goal is usually off-screen. Speedrun tech
  should **emerge**, not be hand-coded.

**Planner.** Local open-weights model: zero API cost, reproducible, no version drift breaking
results six months later. **RAG over the wiki is core** — it separates "the model reasoned" from
"the model memorised", and logging which page was retrieved before each decision gives an
interpretable trace for free.

## 4. Memory — three kinds, and the missing one

| kind | what it holds | where it lives | who reads it |
|---|---|---|---|
| **Semantic** | "there's a Seal above the stag platform" | wiki / RAG store | LLM |
| **Procedural** | how to time a pogo | policy weights | nobody |
| **Episodic** | "attempted that pogo 6× at 2 masks, worked once" | *was missing* | LLM |

The real axis is **what the LLM reads versus what it writes.** With only a read path it is
structurally lookup, and better retrieval does not fix that.

**Decision: add the write path.** Every skill invocation returns its outcome, appended to a store
the planner retrieves from alongside wiki pages. No fine-tuning, no gradients, no added latency.
**The model does not learn. The system does.** This closes the best objection against the design —
the loop where the planner repeatedly walks into a wall exists only because nothing recorded that
the wall was tried.

**The trap: log conditions, not just outcomes.** `"failed pogo at room X"` is worse than useless;
the model over-generalises it into "pogo doesn't work". Every entry needs the state it was attempted
from — masks, soul, ability loadout, style vector, primitive, failure code. Consequence: **the
structured failure codes are the schema of the system's memory**, not error handling.

## 5. RAG, not fine-tuning — settled

**Rule of thumb:** if a human could learn it by reading a log, it is retrieval. If a human could
only learn it by practising, it belongs in the policy weights.

**Gradients stay off during play**, for five reasons: no loss function, since a playthrough produces
an outcome hours later rather than a next token; sample counts 3–4 orders of magnitude short; credit
assignment across hours unsolved; Adam needs 12–16 bytes per parameter against inference's 2; and
drifting weights make a demo irreproducible.

*"Can it learn that primal aspids aren't worth fighting?"* Yes, with zero gradients — that is a fact
about outcomes and it goes in a table. Fine-tuning is an optimisation of a working system, not a
starting point.

## 6. Why Hollow Knight

1. **A difficulty ladder authored by professionals.** Attuned → Ascended → Radiant is the same
   dynamics with monotonically increasing risk sensitivity. You cannot buy this.
2. **Ground truth about the opponent.** Bosses are PlayMaker FSMs — read the state name and
   time-in-state through Harmony and you have labels for which attack and when the telegraph began.
3. **Near-instant resets.** Hall of Gods removes the walk-back tax.
4. **An enormous population of expert humans** to measure against.

MuJoCo and Isaac give contact dynamics with no adversary, no precision timing, no authored
curriculum and no human baseline.

**Two regimes, and the split is the most useful structural fact about the domain.** The overworld is
recoverable — death costs a walk back, progress persists. P5 is all-or-nothing: 42 bosses, no
checkpoint, 45–60 minutes.

| per-boss survival | P5 clear rate |
|---|---|
| 90% | 1.2% |
| 95% | 11.6% |
| 99% | 65.6% |
| 99.9% | 95.9% |

**P5 is an asymptote to report against, not a target to promise.** 50% completion is honest.

## 7. Experiments

**The one that proves the thesis.** Pantheons, where boss order is known and per-boss style
selection is exactly where a generalist policy must compromise.

- **A** — one RL policy across the whole pantheon (honest "just do RL" baseline)
- **B** — the modules, style and target fixed or random
- **C** — the modules, LLM chooses
- **D** — the modules, **hard-coded lookup table** chooses per target

**C versus B is the money result** — same weights, same environment, only the chooser differs.
**C versus D matters most.** In the closest published comparison, LLM+RL scored 46.4% against a
hand-crafted behaviour tree's 51.5%, p = 0.103. A tie. If we cannot beat a lookup table we have
learned something important and unflattering, and early is better than late.

**Knowledge ablation.** No retrieval → retrieval → retrieval plus experience log.

**Held-out protocol at three levels** — the structure that makes the project cohere.

| layer | trained on | held-out test |
|---|---|---|
| traversal | procgen rooms | White Palace / Path of Pain |
| combat | subset of enemies | unseen bosses |
| planner | HK1 knowledge | Silksong |

Define a grammar of traversal primitives (spike gap → pogo, vertical shaft → claw chain), compose
them into generated rooms, train on a subset and hold out the real game. Then: *"trained only on
procedurally generated geometry, X% zero-shot on unseen human-authored levels."* Nobody can call
that a TAS. **Path of Pain is the stretch goal, not the success criterion.**

**Skips: run it backwards.** It will not discover skips on its own. Instead take the ~20 documented
ones, attempt each, and record which its actuators can execute: *"of 23 documented skips, the agent
determined 7 were within its capability and routed around the rest."* Novel measurement, same
pattern as the competence table.

**Transfer matrix.** FK → Failed Champion is nearly the same task, so add **FK → Mantis Lords**
(aerial, multi-entity, different rhythm). Catastrophic-forgetting check. Minimum 3 seeds.

## 8. Implications

**Mars, the strong one.** Earth–Mars one-way light time is 3–22 minutes, so ground-in-the-loop
reactive control is physically impossible — the reflex arc forced by the speed of light.
Perseverance already runs AutoNav onboard, so the spine is flight-proven and the brain is missing.
In space you also cannot learn on hardware: one rover, billions of dollars, cannot fall in a pit
twice. Train in sim, freeze, deploy, adapt at runtime without gradients is the only admissible
architecture there. *Now built — [`ROVER.md`](../ROVER.md).*

**Surgery, rejected as execution.** ❌ Surgical execution has no reward function — "dealt damage" is
measurable, "made a good incision" is not, which is why da Vinci is teleoperation. ✅ The salvageable
version was **approach planning**: `goto(x,y,z)` with a hazard map. *Since dropped entirely —
[`02-critique-response.md`](02-critique-response.md) §7.*

**Pitch discipline.**

- **Never lead with Hollow Knight.** Lead with the problem — planners emit plans their body cannot
  execute — then, one slide later, we found a testbed. *(About the first slide, never about where
  the work happens.)*
- **Use one implication.** Mars survives a hostile question; surgery-as-execution does not.
- **Claim architectural transfer, not sim-to-real.** Nobody will believe an HK-trained policy moves
  a robot. The pattern is what is defensible.

| this system | robotics |
|---|---|
| LLM planner, seconds | semantic task planner (SayCan, RT-2) |
| `goto(x,y)` + hazard avoidance | goal-conditioned navigation |
| `kill(target)` with style modes | manipulation policies |
| competence table | affordance grounding — literally SayCan's "Can" |
| structured failure → replan | the hard problem in real deployment |

**Three attacks and the answers.** *"Deterministic and fully observable"* — correct, and we hold
perception constant to isolate the composition layer, then show graceful degradation in the pixel
ablation. *"You can die ten million times"* — that is the definition of a simulator, and the real
question is whether it is a good one. *"It's a game"* — framing, not substance.

---

**That is the design.** Design decisions and their reasoning, engineering constraints, process, the
deferred list, failure modes, open questions and vocabulary are in
[`technicalities.md`](technicalities.md). Read that when you are implementing, not when you are
trying to understand what this is.
