# The problem statement issue

SIH 2026 opened on 21 August with 226 problem statements. We went looking for where Reflex Arc
fits. We found it. Then we found something else, and now there are two ways in.

They are not comparable on any single axis. That is the problem.

---

## 1. Where Reflex Arc lands

**Student Innovation is not a separate track.** It is 34 of the 226 statements — PS 26193–26209
(software) and 26210–26226 (hardware), one per theme, issued by AICTE. You select one like any
other statement. For the rover that means the **Hardware / Space Technology** slot.

Four ministry statements looked close and are not:

| PS | why not |
|---|---|
| 26126 — Vision-based autonomous navigation for UGV (BEL) | wants visual SLAM and GPS-denied localisation — the exact thing [`ROVER.md`](../ROVER.md) cut as "would eat the project" |
| 26177 — Autonomous SAR drone (Qualcomm) | needs a real drone with onboard compute; ours has neither |
| 26039 — Mine rescue rover (Jharkhand) | a sensing rover, not a deciding one |
| 26098 — Artillery guidance (MoD) | terminal guidance, no deliberation layer at all |

**One is genuinely close.** PS 26055, *Smart Scan Strategy for Electronic Warfare* (DRDO), is our
thesis in another domain — search a spectrum you cannot cover all at once, with no prior
intelligence, against emitters that move. DRDO even names our baseline:

> "Hitherto strategies based on pre mission data / prior data (Open loop) are used... may lose
> time to nonthreatening emitters by not giving time to new or threatening ones."

That is our hardcoded-table comparison, written by the customer. It is software-only, though, and
the statement never asks for the LLM — a good pure-RL scheduler answers it completely.

**On crowding:** ISRO issued 11 statements and **none is a rover**. The space theme is less
contested than we were told.

## 2. Then the remote sensing four

Four statements from two agencies, all reducing to one primitive — *getting observations from
different sensors, different resolutions and different times into one coordinate frame*:

- **26166** (ISRO) — image correspondence across Chandrayaan-2's OHRC (0.25 m), TMC-2 (5 m) and
  IIRS (80 m, infrared spectrometer). A 320× resolution spread across three sensing modalities.
- **26167** (ISRO) — **SatQuery AI**, a vision-language assistant for multimodal remote sensing.
- **26142** (NTRO) — super-resolution mapping from medium-resolution imagery.
- **26143** (NTRO) — oil spill detection from SAR, attributed to a vessel via AIS tracks.

26166 is the sub-problem of the other three. And the data problem that normally kills a hackathon
ML project does not exist here — 26167 names BigEarthNet, VRSBench, RSVQA and CDVQA outright,
Chandrayaan-2 data is public, oil spills are Sentinel-1.

## 3. The reveal

**We already built the hard part of this.** GHOST — Ishan wrote the framework, Abhishek built the
site and trained the models. It is live on PyPI as `ghost-hsi`, runs on Python 3.9–3.12 across
three operating systems, and has been benchmarked on Indian Pines, Pavia, Salinas, a lung
histopathology set, and **Mars CRISM**.

Read ISRO's background for 26167 next to GHOST's own thesis:

> **ISRO:** "most existing remote-sensing AI solutions are developed as isolated applications for
> a single predefined task... These systems often require users to understand satellite-data
> characteristics, GIS workflows, model selection, and task-specific parameters."
>
> **GHOST:** "point it at a hyperspectral image and get a segmentation map without writing
> dataset-specific code."

The same sentence, written independently by two parties. And CRISM (0.362–3.92 μm) is the same
class of instrument as Chandrayaan-2's IIRS (0.8–5.0 μm) — we have already run on another
agency's planetary imaging spectrometer.

---

## 4. Why this is a problem and not a gift

**Team work division.** Reflex Arc gives six people work — planner, interface, simulator, arena,
hardware, RL. GHOST is two people's expertise, and Ishan and Abhishek are the two. On the GHOST
track Koushik and a hardware fourth have nothing obvious to hold. SIH requires six members
including at least one female member, and five people carrying air is visible from the front of
a room.

Against that: the rover chain is serial anyway — the arena waits on the terrain model, which
waits on measuring a rover that does not exist yet. Headcount does not accelerate it.

**GHOST is not finished for this.** It covers a fraction of what 26167 asks for. Details in §5,
and the fraction is smaller than it feels.

**And personally — Ishan.** I want to build something new from scratch. GHOST was months of
sleepless nights and it is *done*; entering it feels like turning up with homework I finished last
term. [`CLAUDE.md`](../CLAUDE.md) already says learning outranks using the best available method, and
that rule was written before we knew we might hold a winning hand. Whether it survives that
discovery is a real question and not a rhetorical one.

## 5. How much GHOST actually lacks

Shipped version is v0.1.7. Last commit **3 April 2026** — dormant five months. Its own README
states the limits:

> Spatial dependence: models don't reliably transfer across scenes · No transfer learning · Single-scene constraint

**The generalisability gimmick is the roadmap, not the shipped state.** The design-goals table
marks scene-to-scene transfer as *in progress (v0.2.x)*, and v2 is designed but uncoded. What
ships today is *code*-agnostic — retrain on anything without touching source — which is real, and
is a different claim from what the name promises.

Against 26167's deliverables:

| ISRO asks for | GHOST today |
|---|---|
| Natural-language query interface | ✗ |
| Vision-language model / image–text alignment | ✗ |
| Visual question answering, captioning, grounding | ✗ |
| Change detection, multitemporal | ✗ |
| SAR, co-registered optical–SAR pairs | ✗ |
| Land-cover classification / segmentation | ✓ **and differentiated** |
| "may employ multiple specialised models" | ✓ the door we walk through |
| BigEarthNet / VRSBench / RSVQA / CDVQA | ✗ — we are on Indian Pines, Pavia, Salinas, LUSC, CRISM |

**GHOST is roughly 15–20% of that deliverable.** The whole language half — the name of the
problem statement — is unbuilt. Nobody should walk into the room saying we are 60–70% done.

The accurate version is stronger anyway: *we own a benchmarked spectral backbone that already runs
on planetary spectrometer data, and we would build the language layer on top of it.* Every other
team on 26167 will fine-tune a CLIP or LLaVA variant. None of them will have that backbone.

**Which means the GHOST track is also a from-scratch build.** The v2 rewrite is specced and
uncoded — universal loader, 1D dilated ResNet, three-tier continuum removal, multi-scene protocol
— and the entire vision-language layer is bare ground. The choice is not "build new" versus "reuse
old." It is *which* new thing we build, and whether we stand on our own foundation or on nothing.

## 6. How the two compare

| | Reflex Arc (rover) | GHOST → 26167 |
|---|---|---|
| entry | Student Innovation, we define the problem | ministry statement, ISRO defines it |
| ready for internal hackathon (Sept–Oct) | no — chain starts at hardware we don't have | yes — it runs today |
| team fit | six roles | two people's expertise |
| what's unbuilt | almost everything | the language half, and v2 |
| novelty risk | real — closest published system tied a hand-written behaviour tree, 46.4% vs 51.5%, p = 0.103 | low — the backbone works and is measured |
| what a judge sees | a robot crossing a room | a segmentation map |
| motivation | very high | mixed |

## 7. The judges, which is the part that actually matters

We have already run this experiment. GHOST went to a university hackathon last semester. We spent
**half our slot explaining what hyperspectral imaging is** — because nobody had asked us to solve
a hyperspectral problem. One judge was electrified, pitched real applications, and connected on
LinkedIn afterwards. The other nearly fell asleep, understood none of it, and cut our marks for
running over time — time the first judge's questions had consumed.

We concluded then that this fits a research paper rather than a hackathon.

**That conclusion was right about the event and wrong about GHOST.** The failure was carrying the
burden of proof for an entire field before we could reach our own contribution. And a ministry
problem statement removes exactly that: ISRO wrote the background, established why it matters, and
named the benchmarks. A judge assigned to 26167 has read that and self-selected into caring.

Now flip it. **Reflex Arc under Student Innovation puts us back in the configuration that failed.**
We propose the problem, so we carry 100% of the explanation, to judges who did not ask. The rover
moves, which buys attention — but what a judge sees when it moves is a robot crossing a room. Our
own document calls that a Roomba. The novel part is the fogged planning and the latency tolerance,
and those are exactly as invisible as a spectral cube.

That is the real asymmetry, and it is not about which project is better.

---

## What is not decided

- Which statement we enter, or whether we enter both. **A team may submit two ideas** — so this
  need not be either/or at submission, only at build.
- What the other four people do on the GHOST track.
- Whether the internal hackathon in Sept–Oct is a selection signal we should use rather than
  predict.

**Deadline: registration closes 6 September.** The decision about what to *build* does not have to
be made on the same day as the decision about what to *submit*.

## Verify before relying on any of this

- The PS-ID ↔ theme mapping. The circulating PS PDF has **scrambled theme labels** — onion grading
  filed under "Fitness & Sports," the robotics slot labelled "MedTech." Descriptions are correct;
  labels are not. Check on sih.gov.in directly.
- Team size (6, ≥1 female) and the two-idea cap are confirmed from the official SIH FAQ. The FAQ
  says **nothing** about pre-existing work.
- GHOST's licence is currently `Proprietary. All rights reserved.` — deliberate choice needed
  before anyone else builds on it.
