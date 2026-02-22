# AV Safety Benchmark

**Status: Planned — Q3 2026**

An AI safety evaluation framework for autonomous driving. It provides structured benchmark datasets, adversarial scenario generators, and a standardized safety metrics suite to evaluate how well autonomous driving systems handle safety-critical situations — from routine edge cases to [redacted] boundary violations.

## Why This Matters

The autonomous vehicle industry has no standardized safety benchmark. Every developer tests differently, using proprietary scenarios, internal metrics, and ad-hoc evaluation pipelines. This creates three concrete problems:

1. **No apples-to-apples comparison.** There is no shared framework to evaluate whether System A is safer than System B under equivalent conditions. Fleet operators, insurers, and regulators are flying blind.

2. **Safety evaluation is the deployment bottleneck.** The engineering to build an AV stack is well understood. What remains unsolved is proving — with quantifiable evidence — that the system is safe enough to operate on public roads. Regulators will not approve what they cannot measure.

3. **Current eval approaches do not scale.** Most safety evaluation is scenario-by-scenario, manually curated, and not reproducible. As AV operational domains expand (new geographies, weather conditions, road types), evaluation must be systematic, not artisanal.

This project exists to close that gap: a rigorous, open, reproducible safety evaluation framework that maps directly to the standards regulators actually use.

## What This Project Does

av-safety-benchmark is structured as a pipeline with four stages:

```
Scenario Generation --> Simulation Execution --> Metric Computation --> Benchmark Scoring
```

**Scenario Generation** produces parameterized, adversarial driving scenarios using procedural generation and scenario description languages. These scenarios are executed against an AV stack under test inside a physics-based simulator (CARLA). During execution, the **Metrics Suite** computes a battery of safety-relevant measurements (time-to-collision, post-encroachment time, minimum clearances, intervention rates). Finally, the **Benchmark Scorer** aggregates results into a standardized safety profile aligned with ISO 26262, SOTIF, and UL 4600 requirements.

The framework is AV-stack-agnostic. Any system that can interface with CARLA or produce trajectory logs in a supported format can be evaluated.

## Key Components

### 1. Adversarial Scenario Generation

Procedurally generated edge cases designed to stress-test perception, prediction, and planning. Scenario categories include:

- Aggressive cut-ins with minimal time-to-collision margins
- Occluded pedestrians emerging from behind parked vehicles
- Adverse weather (heavy rain, fog, low-sun glare) with corresponding sensor degradation
- Unusual road users (scooters, construction vehicles, wheelchair users, animals)
- Compounding failures (sensor dropout during a pedestrian crossing event)

Scenarios are parameterized for reproducibility and defined in OpenSCENARIO format.

### 2. [redacted] Boundary Testing

Systematic evaluation of [redacted] boundaries. Rather than testing only within the designed operating envelope, this component deliberately probes what happens at and beyond [redacted] limits:

- Speed boundaries, lighting transitions (tunnel entry/exit), and road type changes
- Gradual weather degradation from within-[redacted] to out-of-[redacted] conditions
- Map data staleness and construction zone handling
- Graceful degradation behavior: does the system achieve a minimal risk condition, or does it fail unpredictably?

### 3. Safety Metrics Suite

A standardized set of safety-relevant metrics computed from trajectory and sensor data:

| Metric | Description |
|---|---|
| Time-to-Collision (TTC) | Time remaining before a collision at current velocities |
| Post-Encroachment Time (PET) | Temporal gap between two road users occupying the same space |
| Minimum Distance Margin | Closest approach distance to any road user or obstacle |
| Intervention Rate | Frequency of safety driver or fallback system interventions |
| Disengagement Analysis | Categorized reasons and conditions for autonomy disengagements |
| Collision Severity Index | Estimated severity based on delta-v and impact configuration |

### 4. Eval Dataset Curation

Curated evaluation datasets with ground truth annotations for safety-critical scenarios. Each scenario is labeled with:

- Scenario type and severity tier (near-miss, minor, critical)
- Expected safe behavior (ground truth reference trajectory)
- Environmental conditions and [redacted] classification
- Source dataset provenance (nuScenes, Waymo Open Dataset, synthetic)

### 5. Benchmark Leaderboard

Standardized scoring that enables direct comparison across different AV stacks. The leaderboard aggregates per-scenario metric results into composite safety scores, broken down by:

- Scenario category (cut-in, pedestrian, weather, [redacted] boundary)
- Severity tier
- [redacted] condition (nominal, boundary, out-of-domain)

### 6. Regulatory Alignment

Every metric and test procedure maps to requirements in established safety standards:

- **ISO 26262** — Functional safety (ASIL classification of test scenarios)
- **ISO 21448 (SOTIF)** — Safety of the intended functionality, including unknown unsafe scenarios
- **UL 4600** — Safety case framework for autonomous products
- **EU AI Act** — High-risk AI system evaluation requirements for transportation

This mapping ensures that benchmark results are directly usable in safety cases and regulatory submissions.

## Planned Tech Stack

| Layer | Technology |
|---|---|
| Core framework | Python 3.10+ |
| Scenario execution | CARLA Simulator |
| Scenario description | OpenSCENARIO 2.0 |
| Motion planning baselines | CommonRoad |
| Eval datasets | nuScenes, Waymo Open Dataset |
| Metric computation | NumPy, SciPy |
| ML components | PyTorch |
| Visualization | Matplotlib, Plotly |
| CI / reproducibility | Docker, pytest |

## Project Roadmap

### Phase 1 — Foundation

- Repository structure, data loading pipelines, and CARLA integration
- Define scenario schema and metric interfaces
- Initial eval dataset curation (nuScenes safety-critical subset)

### Phase 2 — Scenario Generation

- Implement procedural scenario generators for core categories (cut-ins, occlusions, weather)
- OpenSCENARIO export pipeline
- [redacted] boundary scenario templates

### Phase 3 — Metrics and Evaluation

- Full safety metrics suite implementation
- Regulatory standard mapping documentation
- Baseline AV stack evaluation (CARLA autopilot, CommonRoad planner)

### Phase 4 — Benchmarking

- Leaderboard scoring system
- Cross-stack comparison tooling
- Reproducibility validation (same scenarios, same metrics, different runs)

## References

### Standards

- ISO 26262:2018 — Road vehicles, Functional safety
- ISO 21448:2022 — Road vehicles, Safety of the intended functionality (SOTIF)
- UL 4600:2020 — Standard for Safety for the Evaluation of Autonomous Products
- EU AI Act (Regulation 2024/1689) — Annex III, High-risk AI systems

### Key Papers

- Riedmaier, S. et al. (2020). "Survey of Scenario-Based Safety Assessment of Automated Vehicles." IEEE Access.
- Sun, P. et al. (2020). "Scalability in Perception for Autonomous Driving: Waymo Open Dataset." CVPR.
- Caesar, H. et al. (2020). "nuScenes: A Multimodal Dataset for Autonomous Driving." CVPR.
- Althoff, M. et al. (2017). "CommonRoad: Composable Benchmarks for Motion Planning on Roads." IEEE IV.
- Koopman, P. & Wagner, M. (2019). "How Safe is Safe Enough for Autonomous Vehicles?" AAAI Spring Symposium.

---

Built by [BRKMYR](https://github.com/BRKMYR)
