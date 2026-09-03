# Reading list

**Temporary.** A place to keep papers so nobody hunts for the same link twice. Grouped by why
you would read it, not by topic. This is not a literature review and makes no argument — for
what we actually concluded about prior art, read
[`novelty.md`](novelty.md).

**Verification.** Every link below was opened and the title checked against the source. Where a
paper has no stable link yet, that is stated rather than guessed at — see
[`../CLAUDE.md`](../CLAUDE.md) on citations. Do not add a row you have not opened.

---

## 1. The pattern we are building on

Read at least the first three. The point of this section is that a language model directing
learned control policies is **an established pattern, not our idea**, and we cite it rather than
claim it.

| paper | why |
|---|---|
| [Do As I Can, Not As I Say (SayCan)](https://arxiv.org/abs/2204.01691) — Ahn et al. | The original. Language model proposes, a learned value function says whether the robot *can*. Our "competence table" is this, arrived at independently. Start here. |
| [Plan4MC](https://arxiv.org/abs/2303.16563) — Yuan et al. | Skills learned with RL, then a language model builds a skill graph **offline** and execution-time planning is plain graph search. Effectively our condition D, published and working. Read it as the strongest argument against us. |
| [Voyager](https://arxiv.org/abs/2305.16291) — Wang et al. | The famous one. Writes its own skills as *code*, which is why it does not transfer to domains needing reflexes. Know the difference well enough to state it. |
| [Hösch et al.](https://arxiv.org/abs/2606.20014) | Closest prior work. Contains the number that should worry us: LLM+RL 46.4% vs a hand-written behaviour tree's 51.5%, p = 0.103. |
| [LARAP](https://www.nature.com/articles/s41598-025-20653-y) | Robotic manipulation; language model over parameterised action primitives. |
| [LGRL](https://www.mdpi.com/2227-7390/13/12/1932) | Subgoal generation with a modular RL executor. |
| [LLM-SOARL](https://arxiv.org/abs/2603.01488) | Semantic option discovery. |
| [SCALAR](https://arxiv.org/abs/2603.09036) | Proposes skills with preconditions; trajectory analysis corrects the spec. |

## 2. Learning without touching the weights

This is our experience log, and it already exists in the literature. Read both before writing
anything that claims the write path is new.

| paper | why |
|---|---|
| [ExpeL](https://arxiv.org/abs/2308.10144) — Zhao et al., AAAI-24 | Gathers its own experience, extracts insights in natural language, retrieves at inference, **no weight updates**. This is [`course.md` §4](course.md) with a citation attached. |
| [Reflexion](https://arxiv.org/abs/2303.11366) — Shinn et al. | Verbal reinforcement learning — reflect on failure, keep the reflection in episodic memory. The mechanism, in its simplest form. |

## 3. Foundations — the things we actually have to implement

| paper | why |
|---|---|
| [Proximal Policy Optimization](https://arxiv.org/abs/1707.06347) — Schulman et al. | The algorithm we will write from scratch. Non-negotiable reading. |
| [Hindsight Experience Replay](https://arxiv.org/abs/1707.01495) — Andrychowicz et al. | Turns "failed to reach the goal" into "successfully reached somewhere else." The unlock for goal-conditioned traversal, where almost every early episode fails. |
| [Leveraging Procedural Generation to Benchmark RL (Procgen)](https://arxiv.org/abs/1912.01588) — Cobbe et al. | Why training on generated content and holding out authored content is the honest way to claim generalisation. |
| [Dynamic Weights in Multi-Objective Deep RL](https://arxiv.org/abs/1809.07803) — Abels et al. | Conditioning one network on a preference vector and varying it during training. The method behind the "style dial," if we build it. |
| [Eureka](https://arxiv.org/abs/2310.12931) — Ma et al. | Language models writing reward functions. Relevant only later, and each iteration costs a full training run — scope to a handful of refinements, not hundreds. |
| Universal Value Function Approximators — Schaul et al., ICML 2015 | The mechanism behind every "conditioned policy" in this project. **No stable link recorded yet** — find the PMLR entry and add it. |
| Policy Invariance Under Reward Transformations — Ng, Harada & Russell, ICML 1999 | Potential-based shaping: how to add a dense reward signal without changing what the optimal policy is. **No stable link recorded yet.** |

## 4. Simulation to reality — for the robot track

Added when the physical robot entered scope. Thin on purpose; fill it in as the track firms up.
Design in [`ROVER.md`](../ROVER.md).

| paper | why |
|---|---|
| [Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World](https://arxiv.org/abs/1703.06907) — Tobin et al. | The standard answer to the reality gap: randomise the simulator hard enough that reality looks like one more variation. Directly applicable if we train in a hand-written sim and deploy to hardware. |
| [MLNav](https://arxiv.org/abs/2203.04563) — JPL, IEEE RA-L 2022 | A *learned* proposer ranking candidate paths with a deterministic safety checker verifying only the top few. 10× fewer collision checks on real Martian terrain. This is a better architecture than the one we originally wrote down, and it is flight-adjacent rather than hypothetical. |

**Still to find:** a current sim-to-real survey, and something specific on differential-drive or
wheeled-robot transfer. Search rather than guess, and add the link once opened.

## 5. The domain

| paper | why |
|---|---|
| [OC-STORM](https://arxiv.org/abs/2501.16443) | Hollow Knight as a published RL benchmark, with per-boss win rates we can compare against. Also the source of the number that de-risks us most: **9 FPS control, ~100k samples ≈ 3.1 hours of gameplay**, and several bosses cleared. |
| [Long-Horizon-Terminal-Bench](https://arxiv.org/html/2607.08964v1) | Useful for showing that "long-horizon" in this literature means *many discrete decisions*, not long continuous execution. 85.1 minutes per task — across 228 separate episodes. |

## 6. Checked, and does not say what it was claimed to say

Kept so the same wrong citation does not come back. Full reasoning in
[`novelty.md` §3](novelty.md).

| paper | the claim it was cited for | what it actually is |
|---|---|---|
| [ARISE](https://www.alphaxiv.org/overview/2603.16060v1) | that the field has moved past frozen skill libraries | hierarchical RL for **mathematical reasoning in language models**. No motor policy, no embodied agent anywhere in it. |
| [HKRL](https://github.com/AdityaJain1030/HKRL) | evidence that model-free RL plateaus in Hollow Knight | an abandoned 18-star repo, 26 commits, no metrics in the README. Demonstrates nothing either way. |
