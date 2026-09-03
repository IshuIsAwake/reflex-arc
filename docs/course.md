# Hollow Knight — the coursework track

The design, the experiments, and what it takes to implement them. This is the whole coursework
track in one file; the rover track is separate and reads on its own in
[`../ROVER.md`](../ROVER.md).

Deliverable is PRJ-1, submitted as [`phase1-problem-statement.md`](phase1-problem-statement.md).
Separately staffed from the hackathon team, and retrieval is covered. The raw ideation of
2026-08-17 and 2026-08-18 is in [`00-raw-transcript.md`](00-raw-transcript.md). Rejected ideas keep
their reasoning so they don't get rediscovered.

**The reactive-opponent claim lives here and nowhere else.** Terrain does not fight back, so the
rover cannot make it; this track is the only place it can be measured.

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
hours of unbroken execution ([`02-critique-response.md`](02-critique-response.md) §1). Every
comparable system in the literature runs for minutes, or for short episodes with resets between.
Completing this game takes hours in which one mistimed input ends the attempt.

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
architecture there. *Now built — [`../ROVER.md`](../ROVER.md).*

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

## 9. The mod layer — at zero, and the critical path

Nothing downstream starts until these are answered. Five questions, in order of how badly a "no"
hurts:

1. Can we read game state — position, velocity, health, enemy state?
2. Can we inject inputs through the game's own input handling?
3. Can we reset a fight quickly? Without this there is no training budget.
4. Can we run faster than real time, and does behaviour change when we do?
5. Can we run more than one instance at once?

A "no" on 1 or 2 means Hollow Knight is not the training environment this window. On 3, training is
slow but possible. On 4 or 5, survivable — OC-STORM ran this game at 9 FPS control, clearing several
bosses on ~100k samples (~3.1 hours of gameplay). Compute was never the constraint.

**Write the answers down, including the ugly ones.** Not done yet.

## 10. Scope for this window

**Worth building whatever else changes.** The skill interface first and blocking — its failure codes
are the schema of the experience log. Then scripted stubs: a `goto()` that cheats and a `kill()` that
runs a dumb attack loop, so the planner gets built alongside training rather than after it. And
**the Any% route** — which bosses, what order, which abilities — because it defines the demo
boundary.

**Not in this window.** Path of Pain, White Palace, the Pantheons, any hard boss; procgen rooms; the
competence table; the style dial and reward-weight knobs; charm selection; Silksong; retrieval over
the full wiki.

## 11. Design decisions and corrections

| | decision | why |
|---|---|---|
| ❌ | Don't inherit combat weights into traversal | A boss policy learned "stay near boss, dodge, attack" — a bad prior for goal-seeking, and it has no goal input to condition on. Demoted to an ablation. |
| ❌ | Don't reward pogo-ing | Reward a skill and the agent does it when it shouldn't. Shape the *task distribution* instead — rooms where pogo is the only solution — and keep reward goal-based. |
| ❌ | Don't use Euclidean distance-to-goal | Platformer geometry is non-convex; the goal is often straight up and the route is down and sideways. Distance reward punishes the correct action and the agent jitters at the nearest point below the goal. Use sparse reached-goal + HER, or geodesic distance over a tile graph. |
| ⚠️ | Infinite HP creates a degenerate optimum | Hits grant iframes, so with free damage the optimal traversal is walking through spikes. Keep a damage penalty. |
| ✅ | No Eyes chase is a debugging harness, not a curriculum | One room, low goal diversity. Once the tile graph exists, sampling random reachable points is ~50 lines and covers far more. |
| ✅ | Abs Rad climb is a test case, not a training env | One authored sequence memorises. Excellent held-out eval. |
| ⚠️ | Ability loadout is environment config | A policy with Wings + Claw is a different agent. Version it from day one or runs become incomparable. |
| ⚠️ | Module handoff during committed actions | Switching mid-swing hands traversal a state it never trained on. Switch at neutral states, or train with random animation-recovery starts. Put the choice in the skill API. |
| ✅ | The planner needs a model of its own body | Human folklore is miscalibrated for these actuators. Measure a **competence table** — style × boss, win rate and clear time — and put it in context. SayCan's affordance function, arrived at independently. |
| ✅ | Precompute Pantheon plans | Boss order is known, so plan offline and invoke the LLM only for replanning. Latency stops mattering. |

**Corrections to earlier assumptions.** RL here is not easier than TrackMania — the reward is easier
to *specify* but credit assignment is harder, since TrackMania has a dense per-frame progress signal
and HK's is spiky and delayed. Healing is a 0.85 s uninterrupted hold, a temporally-extended action
that flat action spaces handle badly. Don't start with pixels; a structured state vector trains 1–2
orders of magnitude faster, and pixels become an ablation.

## 12. Engineering constraints

- **Throughput is the spine of the project.** 4 conditions × 3 seeds × 10M steps ≈ 550 hours serial
  at 60 Hz. That budget does not exist. Use `Time.timeScale` acceleration **and scale the fixed
  timestep**; run N instances under Xvfb; **design experiments around 2–5M steps**.
- **Inject inputs by patching InControl / hero action polling, not xdotool.** OS-level key events
  are laggy, nondeterministic and do not survive multi-instance.
- **Buy the GOG DRM-free build.** Steam wants a client, an auth and effectively one session. GOG is
  a binary you can copy into a container N times. This one decision saves weeks.
- **The H200s are mostly the wrong resource.** This workload is wall-clock-bound by game simulation
  and CPU-bound by instance count; a small MLP leaves 8× H200 at single-digit utilisation. What we
  need from the college is cores and the ability to run a graphical Unity binary.
- **Observation design.** Structured state vector, framestacked: knight (position, velocity, HP,
  soul, grounded, iframes, action state, cooldowns), target (position, velocity, HP, FSM one-hot,
  time-in-state), hazards (nearest-K fixed size, or a small set-transformer). Iframes and cooldowns
  are hidden state, so including them is a design choice worth ablating.

## 13. Process

- **Freeze the skill API before either ML team starts.** Signatures, preconditions, return values,
  failure codes. The single most important artifact in the project. At six-plus people across three
  layers, integration is the dominant risk.
- **Stub both modules immediately.** A scripted `goto()` that cheats and a `kill()` that runs a dumb
  attack loop. Build the planning layer against the stubs while RL trains, or the planner team is
  blocked for a semester and discovers in month five that the interface was wrong.
- Point the Unity-fluent friend at **ILSpy/dnSpy on `Assembly-CSharp.dll`** in week one. FSM state
  names and hitbox layout are sitting right there.

## 14. Deferred, not dropped

**The door game.** A matrix of doors, some leading to a puddle (restart) and some to a minigame;
beat it and advance a row. The whole architecture in miniature, on a laptop. Read-only RAG should be
flat — attempt 50 looks like attempt 1 — while RAG with write access should improve monotonically,
because the LLM eliminates a door in *one* observation where tabular Q-learning needs many visits.
Give the executors hidden, uneven reliabilities and it also measures whether self-competence
grounding is worth building. *Largely absorbed by the rover simulator.*

**Silksong.** Three genuinely distinct build optima with rock-paper-scissors matchups, so build
selection becomes a real decision problem. Stronger than it looks — the game is new enough that the
model's training data on it is thin, so success cannot be memorisation. ⚠️ The risk is the modding
layer, not the ML.

**Ability progression.** A per-ability availability flag with input blocked when off. Deferred
because real robots launch with a fixed toolset.

**Knobs.** A dial is for what the planner knows and the policy cannot see, not for what the policy
has not learned yet. That collapses four proposed axes to roughly two, and it is what a per-boss
lookup table cannot replicate.

## 15. Failure modes to watch

- **Under-specified memory entries** poison the log and make the system dumber than no memory.
- **Over-generalisation from two samples.** LLMs do this readily.
- **Log growth → context bloat → retrieval degradation.**
- **The flat-but-impressive first run.** A read-only system demos well and never improves. Always
  measure across repeated attempts.

## 16. Open questions

- [ ] Does the LLM beat condition **D**, the hard-coded lookup table? *Highest priority.*
- [ ] What state must accompany every experience-log entry?
- [ ] How does the log stay small enough to retrieve well over a 3-hour run?
- [ ] Combat observations need local room geometry, which the current design lacks.
- [ ] What decision frequency is actually needed? OC-STORM used 9 FPS, so "60 Hz reflexes" is a
      claim to test rather than assume.
- [ ] Skill API contract — the actual signatures. **Blocking everything else.**
- [ ] Do DebugMod savestates work inside Godhome? Unlocks mid-fight phase curricula.
- [ ] Measured `Time.timeScale` ceiling before physics or FSM behaviour drifts.
- [ ] Concurrent-instance licensing for the GOG build.

## 17. Vocabulary

Terms that give the work a home in existing literature: mixture of experts / learned gating ·
goal-conditioned RL, UVFA, Hindsight Experience Replay · hierarchical RL / options ·
potential-based reward shaping (Ng et al. 1999) · preference-conditioned RL · affordance grounding
(SayCan) · LLM-designed reward functions (Eureka) · procedural generation / domain randomisation ·
zero-shot compositional generalisation.
