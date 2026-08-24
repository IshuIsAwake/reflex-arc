# Critique response — prior art and novelty

Response to two Gemini deep-research critiques of 2026-08-18, held locally in
[`critique/`](critique/) and not tracked in git.

**Idea-level only.** Both critiques spent most of their length on execution and methodology
(throughput, CPU vs GPU, Xvfb, IPC, handoff mechanics), which belongs to scope, not to the idea.
What is kept here is prior art, novelty, and the claims that determine whether the idea is worth
doing at all.

Every citation below was checked against the primary source. Claims that failed verification are
recorded as such, because the same critique will be regenerated later and the same errors will come
back.

---

## 1. The finding that matters

**"LLM as meta-controller over a library of learned RL skills" is a published baseline, not a
contribution.** Correct, well-supported, and the single largest update to the project. Five
independent instantiations, all verified:

| Work | Venue / date | Domain | LLM's role |
|---|---|---|---|
| [Hösch et al., arXiv 2606.20014](https://arxiv.org/abs/2606.20014) | Jun 2026 | 2v2 King of the Hill | Centralized meta-controller selecting among specialized RL skill policies |
| [LARAP](https://www.nature.com/articles/s41598-025-20653-y) | Scientific Reports, Oct 2025 | Robotic manipulation | Guides high-level policy over parameterized action primitives |
| [LGRL](https://www.mdpi.com/2227-7390/13/12/1932) | MDPI Mathematics 13(12):1932, 2025 | Interactive environments | Generates subgoals; modular RL executor realizes them |
| [LLM-SOARL, arXiv 2603.01488](https://arxiv.org/abs/2603.01488) | Mar 2026 | Office World, Montezuma's Revenge | Semantic option discovery and annotation |
| [SCALAR, arXiv 2603.09036](https://arxiv.org/html/2603.09036) | 2026 | Craftax | Proposes skills with preconditions; trajectory analysis corrects the spec |

**The architecture must be cited and beaten, not claimed.** The original framing — that there is "a
consistent gap in that literature" because skills are scripted rather than learned — is dead. LARAP
and Hösch both put genuinely learned RL policies under an LLM. That framing must not reappear in any
writeup or pitch.

## 2. The most dangerous single fact, which neither critique noticed

Inside Hösch et al. — the closest prior work — the headline result is:

> LLM + RL: **46.4%** win rate · hand-crafted behavior tree: **51.5%** · **p = 0.103**

Statistically indistinguishable from a hand-written behavior tree. It beat flat RL comfortably, and
60% of human study participants rated it most human-like (p = 0.027), but against a scripted
baseline it did not win.

Being derivative is survivable. **Being no better than a lookup table is not.** This is the live
risk to the project and it outranks the novelty question.

## 3. What failed verification

**ARISE is not about embodied control.** [arXiv 2603.16060](https://www.alphaxiv.org/overview/2603.16060v1)
(Li, Miao, Qi, Lan) is hierarchical RL for **mathematical reasoning in LLMs**. The "skills" are
reasoning skills; the RL operates on the language model itself. No motor policy, no embodied agent.
It was the load-bearing citation for the second critique's strongest section — that the field has
moved past frozen skill libraries — and it does not support that claim at all.

**Perseverance's AutoNav does not use D\* Lite.** ENav is a tree-based path planner using
Approximate Clearance Evaluation with two-stage path selection. Field D\* was the MER-era rovers
(Spirit/Opportunity). The critique sourced this to a hobbyist blog.

**The "aerospace forbids learning" claim is contradicted by JPL's own work.**
[MLNav](https://arxiv.org/abs/2203.04563) (IEEE RA-L, 2022) uses a *learned* search heuristic to
rank candidate paths and invokes the deterministic safety checker only on top scorers — 10× fewer
collision checks on real Martian terrain, succeeding where baseline ENav times out. The pattern is
**learned proposer + deterministic verifier**, a better argument for this project than the one
originally in `hollow-knight.md`.

**HKRL is not a baseline.** [AdityaJain1030/HKRL](https://github.com/AdityaJain1030/HKRL) is 18
stars, 26 commits, abandoned, no metrics, unfinished TODO list. Presented as established evidence
that model-free RL plateaus in Hollow Knight. It demonstrates nothing either way.

**OC-STORM was cherry-picked.** See §4.

**The novelty critique's framing is a prompt artifact.** It was asked to evaluate the concept
"divorced from any specific execution environment," then concluded the residue was derivative. Strip
the domain, the measurement and the claim from any systems paper and the same happens. The finding
in §1 still stands; the *degree* of the verdict does not.

**Two sections attack positions the project does not hold.** The traversal section argues
deterministic A\* beats RL, when `hollow-knight.md` §3 already uses A\* for waypoint routing and RL only for
1–3 s local motion. The Mars section attacks sim-to-real transfer, which `hollow-knight.md` §8 explicitly
disclaims in favour of architectural transfer.

**The two critiques contradict each other.** Doc 1: CPU-bound, wall-clock-limited, insufficient
compute. Doc 2: frozen libraries are obsolete, adopt co-evolutionary training loops — where each
iteration costs a full training run. Only one is actionable. Frozen experts are what the compute
budget admits, and what makes composition cheap to verify.

## 4. Hollow Knight is now a published RL benchmark

[OC-STORM (arXiv 2501.16443)](https://arxiv.org/abs/2501.16443) evaluates on Hollow Knight directly.
3 seeds, 64×64 pixel observations, 9 FPS control, 100k samples ≈ **3.1 hours of gameplay**.

| Boss | STORM | OC-STORM |
|---|---|---|
| Mawlek | 98.3% | 98.3% |
| Hornet Protector | 66.7% | **100.0%** |
| Mantis Lords | 71.7% | 83.3% |
| God Tamer | **70.0%** | 55.0% |
| Mage Lord | 5.0% | 48.0% |
| Pure Vessel | 0.0% | 0.0% |
| Pure Vessel (400k) | 6.7% | 13.3% |

The critique quoted only the Pure Vessel 100k cell. Note the baseline *beat* OC-STORM on God Tamer,
undercutting its own "object-centric representations are required" framing.

This is a **scoreboard we did not have to build**: named bosses, seed counts, published numbers. It
also reads pixels, where we read privileged state from the mod — a strictly easier perception
problem.

## 5. The horizon gap — verified, and currently unoccupied

In this literature **"long-horizon" means many discrete decisions, not long continuous execution.**
Every benchmark checked is turn-based or episodic with resets:

- OC-STORM: single boss fights, 30–90 s
- Hösch et al.: one King of the Hill match, minutes
- Craftax, Office World, Montezuma's: minutes, with resets
- [Long-Horizon-Terminal-Bench, arXiv 2607.08964](https://arxiv.org/html/2607.08964v1): 85.1 min per
  task — across **228 episodes**
- YC-Bench: "one-year horizon" — hundreds of *turns*
- Voyager: up to 4 refinement rounds per task

Nobody measures unbroken, unreset, real-time continuous execution where a single mistimed input ends
the attempt. A 3-hour autonomous playthrough is a *longer* claim than any of the five papers in §1
make, and it requires none of their apparatus to state.

## 6. What survives as defensible

1. **Precision-timing adversarial control.** Every domain in §1 is latency-tolerant. None punishes a
   200 ms stale directive.
2. **Continuous-execution horizon** (§5).
3. **The style dial as the LLM's output.** In all five papers the LLM's action space is *discrete
   selection* — pick skill k. Selection plus continuous parameterization appears unoccupied.
   Preference-conditioned policies (Panacea, PC-PPO) and MoE gating over frozen preference experts
   (MoPE) exist, but in **LLM alignment**, not motor control.
4. **Knowledge vs. measured self-competence as an isolated variable.** SayCan has affordances;
   nobody reports what world knowledge is worth with policies held fixed.
5. **The Attuned → Ascended → Radiant ladder** as a risk-sensitivity axis.

The claim shape changes accordingly: not "a new architecture," but *"the now-standard
LLM-over-RL-skills architecture taken into the one regime it has not been tested in, with a
measurement of what the LLM's knowledge is actually worth there."* Weaker on paper, much harder to
attack, and it survives a reviewer who has read all five papers — which must now be assumed.

## 7. Dropped

**The surgical implication.** RRT\* over a cost-weighted voxel grid genuinely does solve stereotactic
corridor planning, and adding stochasticity to it is a downgrade. `hollow-knight.md` §8 already preferred
Mars; this closes it.
