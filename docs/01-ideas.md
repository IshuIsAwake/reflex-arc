# LLM + RL in Hollow Knight — consolidated ideas

Distilled from the ideation session of 2026-08-17. Raw conversation preserved in
[`00-raw-transcript.md`](00-raw-transcript.md).

This document is a **superset of raw ideas**, not a scope. Scope comes next, in a separate document.
Nothing here is committed to; things marked ❌ were considered and rejected, and the reasoning is
kept so we don't rediscover them later.

---

## 1. Thesis

> The LLM doesn't waste its weights on learning movements.
> The RL doesn't waste its weights on making informed decisions.

An LLM has encyclopaedic knowledge of Hollow Knight and no ability to press a button.
RL policies have frame-perfect motor control and no idea what a Hallownest Seal is or why
they'd want one. Bolt them together and each covers the other's hole.

**Technical framing:** an LLM acting as the *gating function* over a library of conditioned expert
policies. Mixture-of-experts, except the gate isn't a learned linear layer — it's a reasoning model
with the entire playerbase's knowledge in it. Experts stay frozen; no gradients at composition time.

**Brain and spine.** Accurate down to the biology — reflexes genuinely don't route through the brain.

**Explicitly not Voyager.** Voyager generates *code*, in a domain where scripted actions suffice
because Minecraft never demands frame-level reaction. Here the skills cannot be written, only learned,
and the LLM never touches them — it only decides. That distinction is the contribution and should lead,
not be buried.

---

## 2. Architecture

```
          ┌──────────────────────────────────────────┐
          │  LLM planner (local: Gemma / Nemotron)   │   seconds
          │  + RAG over wiki  + competence table     │
          └───────────────┬──────────────────────────┘
                          │  goto(x,y) · kill(target) · style/risk dial
          ┌───────────────┴──────────────────────────┐
          │   frozen conditioned expert policies     │   60 Hz
          │   combat module   ·   traversal module   │
          └───────────────┬──────────────────────────┘
                          │  MAPI / Harmony mod layer
                    Hollow Knight
```

### Combat module — "the killer"
- **Target-conditioned**: `π(a | s, target_features, style)`. One network, *not* one per boss.
- Encode targets by **observable features** — hitbox size, HP, position/velocity, aerial vs grounded,
  FSM state, projectile presence. **Never a one-hot enemy ID**, which cannot generalise.
  Doing it right makes "kills a boss it has never seen" an available headline result.
- **Style dial** replaces training N separate personalities: nail spammer / quick-slash abuser,
  spell + descending-dark abuser, hit-and-run, parry god, dodge-heavy.
  Condition the policy on the reward-weight vector → one network, a slider at inference.
  *Precision point:* this is not reward shaping. Shaping preserves the optimal policy;
  this deliberately changes the objective. Say it that way to the ML instructor.
- **City of Tears guards and regular enemies are underrated** — they're the combat equivalent of
  procgen rooms. Huge variety, natural difficulty ramp below bosses, dense training distribution.

### Traversal module — "the parkourist"
- **Goal-conditioned**: `π(a | s, goal_vector, risk)`. Baritone-analogous. Reach arbitrary coordinates.
- **Goal-conditioned RL + Hindsight Experience Replay is the unlock.** Every failed traversal is a
  successful demonstration of reaching wherever you actually landed. Turns a sparse-reward problem
  dense for free. Critical when 99% of early episodes are "fell in the spikes."
- **Keep the low-level policy short-horizon (1–3 s).** Planner routes over waypoints — plain A* on a
  discretised room is fine, it needn't be learned. Path of Pain then isn't one 2-minute goal, it's
  ~40 short ones. All learning lives in the movement primitives.
- **Local occupancy grid is what buys generalisation.** ~32×32 tiles centred on the knight, channels
  for solid / spike / platform / enemy / moving hazard, plus goal as a relative vector.
  Rasterise straight from Unity colliders. The policy then *cannot* memorise a room because it never
  sees one — only local geometry and a direction. That constraint is the mechanism; it beats hoping
  regularisation saves you.
- Use **room/world coordinates, not screen coordinates**. Camera moves and the goal is usually off-screen.
- Skills it must acquire: pogo chains over spikes and enemies, Mantis Claw wall-cling and chains,
  Monarch Wings, Shade Cloak dashes, crumbling platforms, timed hazards.
  Speedrun tech (wall-cling storage, iframe phase-through, damage boosting) should **emerge**, not be
  hand-coded — see §4.

### LLM planner
- Local open-weights model on the college H200s. Zero API cost, full reproducibility, no version drift
  breaking results six months later. Worth more than a better closed model for anything publishable.
- **RAG over the wiki** is core, not optional. It's what separates "the model reasoned" from "the model
  memorised," it makes the Silksong transfer honest, and it gives auditability for free — log which page
  was retrieved before each decision and you have an interpretable reasoning trace (good figure, good demo).
- **Competence table** — see §4, this is the most important addition.

---

## 3. Roadmap (Ishan's, verbatim structure)

```
RL to beat bosses: False Knight → Failed Champion, Troupe Master Grimm → NKG
Different personalities; transfer-learning experiments
─────────────────────────────────────────────────────── MVP
Separate into two modules: killer and parkourist
Train on many enemies and custom maps
Integrate an LLM to think and make informed decisions
LLM ↔ RL bot interaction
RAG system
Gemma / Nemotron beating Hollow Knight by themselves
─────────────────────────────────────────────────────── Current scope
Proving LLM–RL integration works generally
Dummy Mars rover POC
etc.
```

**Sequencing note:** a vision this good has one specific failure mode — nothing ships. Bank the shallow
version early. PPO beating False Knight locks in full marks for AI and ML; get it done first precisely
*because* it isn't the goal, so the deadline can't hurt you afterwards.

---

## 4. Design decisions and corrections

Things that changed during ideation, with reasons.

| # | Decision | Why |
|---|---|---|
| 1 | ❌ **Don't inherit combat weights into traversal** | A No Eyes policy learned "stay near boss, dodge, attack" — a bad prior for goal-seeking, and the boss network has no goal input to condition on. Demoted from architecture to *ablation*: "does boss-pretraining help traversal?" is a fine result either way. Procgen pretraining will dominate it. |
| 2 | ❌ **Don't reward pogo-ing** | Reward a skill and the agent does it when it shouldn't. Instead **shape the task distribution**: generate rooms where pogo is the only solution, keep reward purely goal-based. Let the curriculum teach the skill. |
| 3 | ❌ **Don't use Euclidean distance-to-goal reward** | Platformer geometry is non-convex — the goal is often straight up and the route is down-and-sideways to a claw wall. Distance reward *punishes the correct action* → agent jitters at the nearest point below the goal, permanent local optimum. Use **sparse reached-goal + HER**, or dense **geodesic** distance over a tile graph, potential-based so the optimal policy provably doesn't change. |
| 4 | ⚠️ **Infinite HP creates a degenerate optimum** | HK-specific: hits grant iframes. If damage is free, optimal traversal is to walk *through* spikes tanking hits — real speedrun cheese, and your agent will find it fast. Keep a damage penalty, or reset position on hazard contact. |
| 5 | ✅ **No Eyes chase is a debugging harness, not a curriculum** | Her reposition set is small and confined to one room → low-diversity goals, overfitting. But once the tile graph exists (needed anyway for geodesic shaping), *sampling a random reachable point* is ~50 lines and gives far better coverage. Use the boss chase as milestone 1, then delete it. |
| 6 | ✅ **Abs Rad climb: test case, not training env** | One authored sequence → memorisation risk. Excellent held-out eval though: "trained only on procgen, clears the ascent zero-shot." |
| 7 | ⚠️ **Ability loadout is environment config** | A policy with Wings + Claw + Shade Cloak is a *different agent* from one without. Version this from day one or you'll have runs you can't compare. |
| 8 | ⚠️ **Module handoff during committed actions** | Switching modules mid-nail-swing hands the traversal policy a state it never trained on — locked animation, no control authority, unchosen momentum. Shows up as unexplainable flakiness in month three. Fix: switch only at neutral states (simple, costs responsiveness) **or** train both policies with random animation-recovery initial states (harder, robust). Put the choice in the skill API contract. |
| 9 | ✅ **The planner needs a model of its own body** | The LLM's knowledge is about the game *as humans play it*, not what these policies can do. Human folklore may be badly miscalibrated for these actuators. Build an empirical **competence table** — every style × every boss, measured win rate and clear time — and put it in the LLM's context. This is literally SayCan's affordance function, arrived at independently. |
| 10 | ✅ **Precompute Pantheon plans** | Boss order is known in advance → plan the whole run offline, invoke the LLM only for *replanning* on failure. LLM latency stops mattering for the headline demo. |

### Where I was wrong / pushed back on
- **"RL will be easier here than TrackMania."** The reward is easier to *specify*; credit assignment is
  *harder*. TrackMania has a dense per-frame progress signal (distance along centreline). HK's is spiky
  and delayed — you get hit at frame *t* because you committed to a swing at *t−40*. Expect this to be
  the real difficulty and the reason vanilla PPO plateaus.
- **Healing is a ~0.85 s uninterrupted hold** — a temporally-extended action with hard commitment cost.
  Exactly what flat action spaces handle badly. Budget for macro-actions/options.
- **Don't start with pixels.** Structured state vector trains 1–2 orders of magnitude faster.
  Pixels become an *ablation chapter*, which is a better use of them anyway.

---

## 5. Why Hollow Knight (the properties that actually matter)

Not "a game." **A simulator with unusually good properties** — and that reframe is the one that defuses
the "you're just playing games" attack.

1. **Designer-authored difficulty ladder.** Attuned → Ascended → Radiant is the same dynamics with
   monotonically increasing risk sensitivity, hand-tuned by professionals. Radiant is a one-hit-death
   variant of *every* task. You cannot buy this.
2. **Privileged ground truth about the opponent.** Bosses are PlayMaker FSMs — read current state name
   and time-in-state via Harmony. Ground-truth labels for "which attack, and when the telegraph started."
3. **Near-instant traversal-free resets.** Hall of Gods removes the walk-back tax. Check whether
   DebugMod savestates work in Godhome — mid-fight resets unlock phase-specific curricula.
4. **Enormous public human-expert distribution.** Hitless and speedrun communities give a real upper
   baseline, not "better than random."

MuJoCo and Isaac give you contact dynamics but no adversary, no precision timing requirement,
no authored curriculum, and no human baseline. Hollow Knight has all four.

---

## 6. Experiments

### 6.1 The one that proves the thesis
Pantheons, because the boss order is known, each boss has a known counter-strategy, and per-boss style
selection is exactly where a single generalist policy must compromise.

- **A** — one RL policy trained across the whole pantheon (honest "just do RL" baseline)
- **B** — the modules, style/target chosen at random or fixed
- **C** — the modules, LLM chooses per boss

**C vs. B is the money result.** Same policies, same weights, same environment; the only difference is
who's choosing. Yields a number attached to "world knowledge is worth X% more bosses cleared."

### 6.2 Knowledge ablation
No retrieval → retrieval → retrieval + competence table. Directly measures what knowledge is worth.
Secondary question: *does grounding the planner in measured self-competence beat reasoning from game
knowledge alone?* Probably yes, substantially — and that's more interesting than the base system working.

### 6.3 Transfer matrix
Original plan: 5M FK → 5M FC vs 10M FC vs 10M FK → 5M FC.
Revisions: FK → Failed Champion is nearly same-task (same moveset, more HP/speed) so positive transfer
is uninteresting — **add FK → Mantis Lords** (aerial, multi-entity, different rhythm). Add a cheap
**catastrophic-forgetting check**: re-eval on FK after fine-tuning on FC. Minimum 3 seeds or the result
is noise.

### 6.4 Held-out protocol at three levels
This is the structure that makes the whole project cohere:

| layer | trained on | held-out test |
|---|---|---|
| traversal | procgen rooms | White Palace / Path of Pain |
| combat | subset of enemies | unseen bosses |
| planner | HK1 knowledge | Silksong |

Define a **grammar of traversal primitives** (spike gap → pogo; vertical shaft → claw chain; timed
sawblade → dash window; crumbling platform → commit), generate rooms by composing them, train on a
subset of compositions, and hold out the real game entirely. Then:
*"trained only on procedurally generated geometry, zero-shot success rate of X% on unseen
human-authored levels."* Nobody can call that a TAS. Graceful failure mode too — even if Path of Pain
doesn't fall, per-room zero-shot numbers on White Palace stand alone. **PoP is the headline stretch
goal, not the success criterion.**

---

## 7. Silksong (deferred, not dropped)

- **HK1 being solved is an asset.** One dominant build (Quick Slash, Unbreakable Strength, Shaman Stone,
  Steady Body, Flukenest, Fury of the Fallen) beats everything → build selection isn't a live decision,
  but there *is* a known optimal ceiling to measure against. HK1 = calibration domain.
- **Silksong has three genuinely distinct optima** with rock-paper-scissors matchups:
  - Architect + Pimpillo + Volt Vessels Bolas + Cogflies — phase-skipper "cheese," highest burst DPS,
    struggles vs flying
  - Wanderers + saw-tooth circlet + cross stitch — highest skill ceiling, highest sustained DPS,
    melts flyers and large bosses, struggles vs small (Lost Lace, Seth)
  - Shaman + volt filament + weavelight + thread storm + pale nails — AFK/camping killer, infinite
    uptime, no downsides but lower damage

  → build selection becomes a real decision problem, so the planner's knowledge is load-bearing.
- **Stronger than it looks as a test**: Silksong is ~1 year old, so the model's training data on it is
  thin and partly stale. Success there **cannot be memorisation** — it has to be transferable
  Metroidvania reasoning.
- ⚠️ **The risk is the modding layer, not the ML.** The whole env depends on a mature mod API
  (Harmony, FSM introspection, input injection, savestates). HK1 has eight years of that; Silksong may
  not. **Action: have the Unity friend spend a day auditing what exists before committing Silksong.**

---

## 8. Implications (the "why should anyone care")

### Mars / planetary robotics — the strong one
Not far-fetched; it's the best argument available.
- Earth–Mars one-way light time is ~3–22 min depending on orbital geometry. Ground-in-the-loop reactive
  control is **physically impossible**, not merely inconvenient. Reflexes must be local, deliberation
  remote and slow. That's the brain/spine split *forced by the speed of light*.
- Not hypothetical: Perseverance already runs **AutoNav** — onboard path planning and hazard avoidance,
  no human in the loop. The spine exists and is flight-proven. The **brain** is what's missing.
- In space you *cannot* learn on hardware — one rover, billions of dollars, can't fall in a pit twice.
  "Train primitives in sim, freeze, deploy, let a planner adapt at runtime with no gradient updates"
  isn't a compromise there, it's the only admissible architecture. **The design fits space better than
  it fits Earth robotics.**
- Vignette: LLM reads drone/orbital imagery → reasons about an incoming dust storm → issues new
  coordinates → traversal module (which has crossed rocky Martian regolith 10,000 times in sim) executes.
  Then: instruct the hyperspectral module, then the digger module, to prospect an asteroid.

### Surgical planning — the weaker one, with a fix
- Pipeline is fine: U-Net on NIfTI → marching cubes → 3D mesh. Standard, works.
- ❌ **Surgical *execution* has no reward function.** "Dealt damage" is measurable; "made a good incision"
  is not. That absence is exactly why da Vinci is master-slave teleoperation where the surgeon drives.
  Plus soft tissue is deformable/viscoelastic/bleeding — nothing like rigid game physics, and an adequate
  tissue simulator is its own decade-long programme. Plus regulatory: an LLM proposing surgical actions
  is a medical device. Plus if the doctor is practising, the doctor's hands are on the controls and the
  RL module isn't doing anything.
- ✅ **The fix: approach planning, not execution.** Segment tumour → reconstruct mesh → plan the *entry
  corridor* maximising distance from vessels and eloquent cortex. That is `goto(x,y,z)` with a hazard map
  — **literally the traversal module in 3D, with spikes replaced by arteries**. Real measurable reward:
  path length, minimum clearance to critical structures, volume of healthy tissue traversed. Stereotactic
  neurosurgical planning already uses computational trajectory optimisation, so this isn't a stretch.

### Pitch discipline
- **Never lead with Hollow Knight.** Lead with the problem: *LLM planners can reason about tasks but have
  no model of what their body can physically do, so they emit plans that fail. Measuring and fixing that
  needs a testbed with precision-critical dynamics, an adversary, and a ground-truth difficulty ladder —
  which nothing in standard robotics simulation provides.* Then, one slide later: *we found one.*
- Keep the game→robotics mapping table as a literal slide. It does more work than a demo video.
- **Use one implication, not both.** Two speculative claims dilute each other. Pick by which survives a
  hostile question: Mars survives (latency argument is unanswerable, flight heritage backs the lower
  stack). Surgery-as-execution does not.
- **Claim architectural transfer, not sim-to-real.** Nobody will believe an HK-trained policy moves a
  robot, and they'd be right. What's defensible: a *design pattern* — frozen conditioned experts +
  competence-grounded LLM gating + structured failure/replanning — measurably beats the alternatives in
  a hard domain. Let the audience make the robotics leap themselves; it lands harder.

### The mapping table
| this system | robotics |
|---|---|
| LLM planner, seconds-timescale | semantic task planner (SayCan, RT-2, Helix) |
| `goto(x,y)` + hazard avoidance | goal-conditioned navigation / legged locomotion |
| `kill(target)` with style modes | manipulation policies, strategy varying by object |
| competence table | **affordance grounding** — literally SayCan's "Can" |
| risk / aggression dial | operating near humans vs. operating alone |
| structured failure → replan | the actual hard problem in real deployment |
| handoff mid-animation | skill chaining during committed motion |

### The three attacks, and the answers
1. *"Deterministic and fully observable — real physics isn't."* Correct, don't dodge. You're testing the
   **composition layer**, holding perception constant so the variable is isolated. Then strengthen
   empirically with the pixel ablation: show graceful degradation when ground-truth state is replaced by
   an estimator.
2. *"You can die ten million times; a robot can't."* That's the definition of a simulator, which is where
   all robot policies are trained. The real question is whether it's a *good* one — see §5.
3. *"It's a game."* Framing, not substance. See pitch discipline.

---

## 9. Engineering constraints

### Throughput is the spine of the project, not a side quest
4 conditions × 3 seeds × 10M steps = 120M env steps ≈ **550 hours** at 60 Hz real-time serial.
That budget does not exist. Therefore:
- `Time.timeScale` acceleration — **and scale the fixed timestep too**. Measure whether physics/FSM
  behaviour drifts; if it does, that's a finding *and* it caps the speedup.
- N parallel instances under **Xvfb** at minimum resolution. Proper headless (`-nographics`) probably
  won't work for a Unity game like this; Xvfb is the realistic path.
- **Inject inputs by patching InControl / hero action polling — not xdotool.** OS-level key events are
  laggy, nondeterministic, and don't survive multi-instance.
- **Design experiments around 2–5M steps per run.** Treat 10M as a stretch. Decide now, because it
  determines whether the transfer matrix is 4 cells or 2.

### Buy the GOG DRM-free build
Steam wants a client, an auth, and effectively one active session. GOG is a binary you can copy into a
container and run N times. **This one decision saves weeks.** Sort out concurrent-instance licensing
with whoever's paying, but the technical friction vanishes.

### The H200s are mostly the wrong resource
This workload is wall-clock-bound by game simulation and CPU-bound by instance count. A small MLP over a
structured state vector leaves 8× H200 at single-digit utilisation. What you actually want from the
college is **cores and the ability to run a graphical Unity binary**, which HPC clusters are often bad at:
no display server, no root, Slurm time limits, Apptainer/Singularity rather than Docker, possibly no
outbound network on compute nodes.

**The H200s become justified only once the LLM planner is in the loop.** That's where they earn their keep.

Build and validate locally; treat the cluster as scale-out **contingent** on the container working, and
don't design experiments that assume it.

### Hardware
- Ishan: 13th-gen i5, 32 GB RAM, RTX 3050 6 GB → ~4–8 concurrent instances before cores/RAM cap.
  Fine as the dev box. 3050 is fine for MLP policies and a small CNN.
- College: 8× H200 (+ presumably ~120 cores).

### Observation design
Structured state vector, framestacked:
- knight — x, y, vx, vy, HP, soul, grounded, iframes, current action state, cooldown timers
- boss/target — x, y, vx, vy, HP, FSM state one-hot, time-in-state
- hazards/projectiles — nearest-K fixed size, or DeepSets / small set-transformer for variable length

Note **iframes and cooldowns are hidden state** — including them is a design choice worth ablating
(MDP vs POMDP).

---

## 10. Team and process

~6–10 people, including a **Unity-fluent friend** — worth more than the cluster. The bottleneck was never
RL; it's the environment layer: MAPI mod, Harmony patches, PlayMaker FSM reads, input injection,
timeScale, savestates. Point him at **ILSpy/dnSpy on `Assembly-CSharp.dll`** in week one — FSM state names
and hitbox layout are all sitting right there, and having that map early changes what's feasible.

**Sub-teams:** killers, parkourists, planner — plus a tiny **platform team** (Unity friend + one) that owns
the env contract. Both ML teams consume it.

### The two process decisions that matter most
1. **Freeze the skill API before either ML team starts.** Signatures, preconditions, return values,
   failure codes. It is now the single most important artifact in the project — more than the RL.
   At 6–10 people across three layers, integration is the dominant risk.
2. **Stub both modules immediately.** A scripted `goto()` that cheats (teleport, or hand-authored path)
   and a scripted `kill()` that runs a dumb attack loop. Build and test the entire LLM planning layer
   against the stubs, in parallel, while RL is still training. Swap in real policies when ready.
   Otherwise the planner team is blocked for a semester and you discover in month five that the
   interface was wrong.

### Coursework
Faculty have approved the same work across AI, ML, and Prj-1/2. (Earlier advice to split deliverables per
course is therefore moot — but worth still telling each instructor there's a shared substrate rather than
letting it be discovered.)

---

## 11. Open questions

- [ ] Do DebugMod savestates work inside Godhome? (Unlocks mid-fight resets → phase curricula.)
- [ ] Does the college cluster permit Apptainer + Xvfb + a graphical binary, and how many cores per node?
- [ ] Concurrent-instance licensing for the GOG build — who pays, how many copies?
- [ ] Silksong modding-API maturity audit.
- [ ] Measured `Time.timeScale` ceiling before physics/FSM behaviour drifts.
- [ ] Skill API contract — the actual signatures. **Blocking everything else.**
- [ ] Which LLM: Gemma vs Nemotron vs other, and does it fit the H200 allocation alongside training?
- [ ] Module handoff policy: neutral-state-only switching, or animation-recovery training?

---

## 12. Vocabulary for writing this up

Terms that give the work a home in existing literature:
**mixture of experts / learned gating** · **goal-conditioned RL**, **UVFA**, **Hindsight Experience
Replay** · **hierarchical RL / options** · **potential-based reward shaping** (Ng et al. 1999) ·
**multi-objective / preference-conditioned RL** · **affordance grounding** (SayCan) ·
**LLM-designed reward functions** (Eureka — real precedent, but each iteration costs a full training run,
so scope to ~5–10 refinements, not hundreds) · **procedural generation / domain randomisation** (Procgen) ·
**zero-shot compositional generalisation**.

The research question nobody has stated yet, and probably the best one available:
**how far does world knowledge get you with frozen experts and no additional training?**
Pure composition at inference — no LLM fine-tuning, no policy retraining. Clean, cheap, and real.
