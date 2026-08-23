# Ideas

The full idea in one place. Merged from the ideation sessions of 2026-08-17 and 2026-08-18; the
raw conversation is in [`00-raw-transcript.md`](00-raw-transcript.md).

Vision first, technicalities after. Rejected ideas are kept with their reasoning so they do not
get rediscovered.

---

## 1. Thesis

> The LLM doesn't waste its weights on learning movements.
> The RL doesn't waste its weights on making informed decisions.

- An LLM knows everything about Hollow Knight and cannot press a button. RL policies have
  frame-perfect motor control and no idea what a Hallownest Seal is. Bolt them together.
- **Reflex arc.** The project's name, and accurate down to the biology — a reflex arc runs
  sense → spinal cord → muscle and never routes through the brain.
- Technically: an LLM as the **gating function** over a library of conditioned expert policies.
  Mixture-of-experts, except the gate is a reasoning model instead of a learned linear layer.
  Experts stay frozen, no gradients at composition time.
- **Not Voyager.** Voyager generates *code*, in a domain where scripted actions suffice because
  Minecraft never demands frame-level reaction. Here the skills can only be learned, and the LLM
  never touches them.

## 2. What we are claiming

- **This is not a paper.** The goal is a system that plays Hollow Knight autonomously, built from
  scratch and understood end to end.
- **The architecture is not the contribution.** "LLM plans, RL executes" has five published
  instantiations ([`02-critique-response.md`](02-critique-response.md) §1). What is unoccupied is
  the *regime* — precision timing, a reactive opponent, hours of unbroken execution — and the
  measurement of what knowledge is worth there.
- **The claim is duration and recovery.** Every comparable system runs for minutes, or for many
  short episodes with resets between them.
- **Recovery beats perfection in a demo.** A system that misjudges a jump, dies, walks back,
  retrieves its shade and re-plans is more convincing than one that never slips, and much harder
  to accuse of being a TAS. Do not aim for a flawless run.
- **The research question:** how far does world knowledge get you with frozen experts and no
  additional training?

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

**Combat module — the killer**

- **Target-conditioned:** `π(a | s, target_features, style)`. One network, not one per boss.
- Encode targets by **observable features** — hitbox size, HP, position, velocity, aerial or
  grounded, FSM state, projectiles. **Never a one-hot enemy ID.** Doing this right makes "kills a
  boss it has never seen" an available result.
- **Style dial** instead of training N personalities: nail spammer, spell abuser, hit-and-run,
  parry, dodge-heavy. Condition on the reward-weight vector, get a slider at inference. This is
  not reward shaping — shaping preserves the optimal policy, this deliberately changes the
  objective.
- **City of Tears guards are underrated** — the combat equivalent of procgen rooms. Huge variety,
  natural difficulty ramp, dense training distribution.

**Traversal module — the parkourist**

- **Goal-conditioned:** `π(a | s, goal_vector, risk)`. Reaches arbitrary coordinates.
- **Goal-conditioned RL + Hindsight Experience Replay is the unlock.** Every failed traversal is a
  successful demonstration of reaching wherever it actually landed. Turns a sparse-reward problem
  dense for free.
- **Keep the policy short-horizon, 1–3 seconds.** The planner routes over waypoints with plain A\*
  on a discretised room. Path of Pain becomes ~40 short goals. All learning lives in the movement
  primitives.
- **A local occupancy grid buys the generalisation.** ~32×32 tiles centred on the knight, channels
  for solid, spike, platform, enemy and moving hazard, plus the goal as a relative vector.
  Rasterise from Unity colliders. The policy then cannot memorise a room because it never sees one.
- Use **world coordinates**, since the camera moves and the goal is usually off-screen.
- Speedrun tech should **emerge** rather than be hand-coded.

**Planner**

- Local open-weights model. Zero API cost, full reproducibility, no version drift breaking results
  six months later.
- **RAG over the wiki is core.** It separates "the model reasoned" from "the model memorised", and
  logging which page was retrieved before each decision gives an interpretable trace for free.

## 4. Memory — three kinds, and the missing one

| kind | what it holds | where it lives | who reads it |
|---|---|---|---|
| **Semantic** | "there's a Seal above the stag platform" | wiki / RAG store | LLM |
| **Procedural** | how to time a pogo | policy weights | nobody |
| **Episodic** | "attempted that pogo 6× at 2 masks, worked once" | *was missing* | LLM |

- The real axis is **what the LLM reads versus what it writes.** With only a read path it is
  structurally lookup, and better retrieval does not fix that.
- **Decision: add the write path.** Every skill invocation returns its outcome, appended to a store
  the planner retrieves from alongside wiki pages. No fine-tuning, no gradients, no added latency.
- **The model does not learn. The system does.** Weights are frozen; behaviour changes because
  retrieval changes. Knowledge in a file can be inspected, corrected and deleted.
- This closes the best objection against the design — the loop where the planner repeatedly walks
  into a wall. That loop exists only because nothing recorded that the wall was tried.
- **The trap: log conditions, not just outcomes.** `"failed pogo at room X"` is worse than useless;
  the model over-generalises it into "pogo doesn't work". Every entry needs the state it was
  attempted from — masks, soul, ability loadout, style vector, primitive, failure code.
- Consequence: **the structured failure codes are the schema of the system's memory**, not error
  handling.

## 5. RAG, not fine-tuning — settled

- **Rule of thumb:** if a human could learn it by reading a log, it is retrieval. If a human could
  only learn it by practising, it belongs in the policy weights.
- **Gradients stay off during play**, for five reasons: there is no loss function, since a
  playthrough produces an outcome hours later rather than a next token; sample counts are 3–4
  orders of magnitude short; credit assignment across hours is unsolved; Adam training needs
  12–16 bytes per parameter against inference's 2; and drifting weights make a demo
  irreproducible.
- *"Can it learn that primal aspids aren't worth fighting?"* Yes, with zero gradients — that is a
  fact about outcomes and it goes in a table. Both things we want it to learn are data.
- Fine-tuning would help later with output-format reliability, terser prompts, and distilling a
  large model into a fast one. All optimisations of a working system.

## 6. Why Hollow Knight

A simulator with unusually good properties.

1. **A difficulty ladder authored by professionals.** Attuned → Ascended → Radiant is the same
   dynamics with monotonically increasing risk sensitivity. You cannot buy this.
2. **Ground truth about the opponent.** Bosses are PlayMaker FSMs — read the state name and
   time-in-state through Harmony, and you have labels for which attack and when the telegraph
   started.
3. **Near-instant resets.** Hall of Gods removes the walk-back tax.
4. **An enormous population of expert humans** to measure against.

MuJoCo and Isaac give contact dynamics with no adversary, no precision timing, no authored
curriculum and no human baseline.

**Two regimes, and the split is the most useful structural fact about the domain.** The overworld
is recoverable — death costs a walk back, progress persists, so a 3-hour run is a random walk with
forward drift plus a recovery loop. P5 is all-or-nothing: 42 bosses, no checkpoint, 45–60 minutes.

| per-boss survival | P5 clear rate |
|---|---|
| 90% | 1.2% |
| 95% | 11.6% |
| 99% | 65.6% |
| 99.9% | 95.9% |

**P5 is an asymptote to report against, not a target to promise.** 50% completion is an honest
milestone.

## 7. Experiments

**The one that proves the thesis.** Pantheons, where boss order is known and per-boss style
selection is exactly where a generalist policy must compromise.

- **A** — one RL policy across the whole pantheon (honest "just do RL" baseline)
- **B** — the modules, style and target fixed or random
- **C** — the modules, LLM chooses
- **D** — the modules, **hard-coded lookup table** chooses per target

**C versus B is the money result** — same weights, same environment, only the chooser differs.
**C versus D is the one that matters most.** In the closest published comparison, LLM+RL scored
46.4% against a hand-crafted behaviour tree's 51.5%, p = 0.103. A tie. If we cannot beat a lookup
table we have learned something important and unflattering, and early is better than late.

**Knowledge ablation.** No retrieval → retrieval → retrieval plus experience log.

**Held-out protocol at three levels** — the structure that makes the project cohere.

| layer | trained on | held-out test |
|---|---|---|
| traversal | procgen rooms | White Palace / Path of Pain |
| combat | subset of enemies | unseen bosses |
| planner | HK1 knowledge | Silksong |

Define a grammar of traversal primitives (spike gap → pogo, vertical shaft → claw chain, sawblade
→ dash window), generate rooms by composing them, train on a subset and hold out the real game.
Then: *"trained only on procedurally generated geometry, X% zero-shot on unseen human-authored
levels."* Nobody can call that a TAS. **Path of Pain is the stretch goal, not the success
criterion.**

**Skips: run it backwards.** It will not discover skips on its own — that needs either exhaustive
exploration or grounded physics reasoning. Instead, take the ~20 documented skips, attempt each,
and record which its own actuators can execute: *"of 23 documented skips, the agent determined 7
were within its capability and routed around the rest."* Novel measurement, and the same pattern
as the competence table.

**Transfer matrix.** FK → Failed Champion is nearly the same task, so add **FK → Mantis Lords**
(aerial, multi-entity, different rhythm). Include a catastrophic-forgetting check. Minimum 3 seeds.

## 8. Implications

**Mars, the strong one.** Earth–Mars one-way light time is 3–22 minutes, so ground-in-the-loop
reactive control is physically impossible. Reflexes must be local and deliberation remote — the
reflex arc forced by the speed of light. Perseverance already runs AutoNav onboard, so the
spine is flight-proven and the brain is what is missing. In space you also cannot learn on
hardware: one rover, billions of dollars, cannot fall in a pit twice. Train in sim, freeze, deploy,
adapt at runtime without gradients is the only admissible architecture there.

**Surgery, rejected as execution.** ❌ Surgical execution has no reward function — "dealt damage"
is measurable, "made a good incision" is not, which is why da Vinci is teleoperation. ✅ The
salvageable version is **approach planning**: segment tumour, reconstruct mesh, plan the entry
corridor maximising distance from vessels. That is `goto(x,y,z)` with a hazard map, with real
measurable reward.

**Pitch discipline.**

- **Never lead with Hollow Knight.** Lead with the problem: planners emit plans their body cannot
  execute, and measuring that needs a testbed with precision dynamics, an adversary and a
  ground-truth difficulty ladder. Then, one slide later: we found one. *(This is about the first
  slide, never about where the work happens.)*
- **Use one implication.** Mars survives a hostile question; surgery-as-execution does not.
- **Claim architectural transfer, not sim-to-real.** Nobody will believe an HK-trained policy moves
  a robot. What is defensible is the pattern.

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

# Technicalities

## 9. Design decisions and corrections

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
| ✅ | The planner needs a model of its own body | Human folklore is miscalibrated for these actuators. Measure a **competence table** — style × boss, win rate and clear time — and put it in context. This is SayCan's affordance function, arrived at independently. |
| ✅ | Precompute Pantheon plans | Boss order is known, so plan offline and invoke the LLM only for replanning. Latency stops mattering. |

**Corrections to earlier assumptions.** RL here is not easier than TrackMania — the reward is
easier to *specify* but credit assignment is harder, since TrackMania has a dense per-frame
progress signal and HK's is spiky and delayed. Healing is a 0.85 s uninterrupted hold, a
temporally-extended action that flat action spaces handle badly. Don't start with pixels; a
structured state vector trains 1–2 orders of magnitude faster, and pixels become an ablation.

## 10. Engineering constraints

- **Throughput is the spine of the project.** 4 conditions × 3 seeds × 10M steps ≈ 550 hours
  serial at 60 Hz. That budget does not exist. Use `Time.timeScale` acceleration **and scale the
  fixed timestep**; run N instances under Xvfb; **design experiments around 2–5M steps** and treat
  10M as a stretch.
- **Inject inputs by patching InControl / hero action polling, not xdotool.** OS-level key events
  are laggy, nondeterministic and do not survive multi-instance.
- **Buy the GOG DRM-free build.** Steam wants a client, an auth and effectively one session. GOG is
  a binary you can copy into a container N times. This one decision saves weeks.
- **The H200s are mostly the wrong resource.** This workload is wall-clock-bound by game simulation
  and CPU-bound by instance count; a small MLP leaves 8× H200 at single-digit utilisation. What we
  need from the college is cores and the ability to run a graphical Unity binary. The H200s earn
  their keep once the planner is in the loop.
- **Observation design.** Structured state vector, framestacked: knight (position, velocity, HP,
  soul, grounded, iframes, action state, cooldowns), target (position, velocity, HP, FSM one-hot,
  time-in-state), hazards (nearest-K fixed size, or a small set-transformer). Note that iframes and
  cooldowns are hidden state, so including them is a design choice worth ablating.

## 11. Process

- **Freeze the skill API before either ML team starts.** Signatures, preconditions, return values,
  failure codes. The single most important artifact in the project. At six-plus people across
  three layers, integration is the dominant risk.
- **Stub both modules immediately.** A scripted `goto()` that cheats and a `kill()` that runs a
  dumb attack loop. Build the whole planning layer against the stubs while RL trains. Otherwise
  the planner team is blocked for a semester and discovers in month five that the interface was
  wrong.
- Point the Unity-fluent friend at **ILSpy/dnSpy on `Assembly-CSharp.dll`** in week one. FSM state
  names and hitbox layout are sitting right there.
- Faculty have approved the same work across AI, ML and Prj-1/2.

## 12. Deferred, not dropped

**The door game.** A matrix of doors, some leading to a puddle (restart) and some to a minigame;
beat it and advance a row. The whole architecture in miniature, running on a laptop. Read-only RAG
should be flat — attempt 50 looks like attempt 1 — while RAG with write access should improve
monotonically, because the LLM eliminates a door in *one* observation where tabular Q-learning
needs many visits. Give the executors hidden, uneven reliabilities and it also measures whether
self-competence grounding is worth building. *Largely absorbed by the rover simulator in
[`rover-expedition.md`](rover-expedition.md), which does the same job with a body.*

**Silksong.** Three genuinely distinct build optima with rock-paper-scissors matchups, so build
selection becomes a real decision problem. Stronger than it looks as a test — the game is new
enough that the model's training data on it is thin, so success cannot be memorisation. ⚠️ The risk
is the modding layer, not the ML.

**Ability progression.** A per-ability availability flag with input blocked when off. Agreed in
principle, deferred because real robots launch with a fixed toolset.

**Knobs.** Position reached: a dial is for what the planner knows and the policy cannot see, not
for what the policy has not learned yet. That collapses four proposed axes to roughly two, and it
is what a per-boss lookup table cannot replicate.

## 13. Failure modes to watch

- **Under-specified memory entries** poison the log and make the system dumber than no memory.
- **Over-generalisation from two samples.** LLMs do this readily.
- **Log growth → context bloat → retrieval degradation.**
- **The flat-but-impressive first run.** A read-only system demos well and never improves. Always
  measure across repeated attempts.

## 14. Open questions

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
- [ ] `Plan4MC` and `ExpeL` belong in the prior-art section and are not there yet. ExpeL matters
      most — it is the experience log, published, and §4 above currently reads as though we
      invented it.

## 15. Vocabulary

Terms that give the work a home in existing literature: mixture of experts / learned gating ·
goal-conditioned RL, UVFA, Hindsight Experience Replay · hierarchical RL / options ·
potential-based reward shaping (Ng et al. 1999) · preference-conditioned RL · affordance grounding
(SayCan) · LLM-designed reward functions (Eureka) · procedural generation / domain randomisation ·
zero-shot compositional generalisation.
