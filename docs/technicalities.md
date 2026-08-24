# Technicalities

The implementation-level half of [`hollow-knight.md`](hollow-knight.md), split out on 2026-08-23 so
the design itself reads short. Section numbers continue from `hollow-knight.md`, which ends at §8.

---

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
| ✅ | The planner needs a model of its own body | Human folklore is miscalibrated for these actuators. Measure a **competence table** — style × boss, win rate and clear time — and put it in context. SayCan's affordance function, arrived at independently. |
| ✅ | Precompute Pantheon plans | Boss order is known, so plan offline and invoke the LLM only for replanning. Latency stops mattering. |

**Corrections to earlier assumptions.** RL here is not easier than TrackMania — the reward is easier
to *specify* but credit assignment is harder, since TrackMania has a dense per-frame progress signal
and HK's is spiky and delayed. Healing is a 0.85 s uninterrupted hold, a temporally-extended action
that flat action spaces handle badly. Don't start with pixels; a structured state vector trains 1–2
orders of magnitude faster, and pixels become an ablation.

## 10. Engineering constraints

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

## 11. Process

- **Freeze the skill API before either ML team starts.** Signatures, preconditions, return values,
  failure codes. The single most important artifact in the project. At six-plus people across three
  layers, integration is the dominant risk.
- **Stub both modules immediately.** A scripted `goto()` that cheats and a `kill()` that runs a dumb
  attack loop. Build the planning layer against the stubs while RL trains, or the planner team is
  blocked for a semester and discovers in month five that the interface was wrong.
- Point the Unity-fluent friend at **ILSpy/dnSpy on `Assembly-CSharp.dll`** in week one. FSM state
  names and hitbox layout are sitting right there.

## 12. Deferred, not dropped

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

## 15. Vocabulary

Terms that give the work a home in existing literature: mixture of experts / learned gating ·
goal-conditioned RL, UVFA, Hindsight Experience Replay · hierarchical RL / options ·
potential-based reward shaping (Ng et al. 1999) · preference-conditioned RL · affordance grounding
(SayCan) · LLM-designed reward functions (Eureka) · procedural generation / domain randomisation ·
zero-shot compositional generalisation.
