# AV Safety Benchmark

A deterministic safety scorecard for the planning software of an autonomous vehicle.
Sixty scenarios, three reference planners, one composite score per planner, and a
mapping to safety standards that is marked informative on every line.

**Shipped v1** · 60 scenarios · 4 families · 3 planners · 180 runs · 33 tests

## Why

AV companies publish safety claims on scenarios and metrics they chose themselves, so
no two numbers compare. The public benchmarks the field cites most, nuScenes and the
Waymo Open Motion Dataset, score how well a model predicts where other road users will
go. They say nothing about whether a planner kept a safe distance, and they carry no
link to the standards a safety case is written against.

This benchmark fixes the scenarios, the metrics and the log format. Anyone can rerun it
and get the same numbers.

## What it does

One seed in, 60 scenarios, 180 scored runs out.

- **Generates** 60 scenarios from one seed in four families: 16 cut in, 16 occluded
  pedestrian, 14 weather ramp (visibility and grip pushed past the operational design
  domain) and 14 lead vehicle hard brake. Identical on repeat, different on another seed.
- **Simulates** the ego vehicle as a kinematic bicycle at 10 Hz with scripted
  adversaries, latching triggers, a friction clamp on deceleration and line of sight
  occlusion. Everything runs offline on a laptop, no GPU.
- **Scores** each run from its trajectory log alone on six surrogate safety metrics:
  minimum time to collision (TTC), minimum post encroachment time (PET), minimum distance
  margin, a collision flag with a delta-v severity index, hard brake fraction and mean
  speed ratio. Each run gets a score from 0 to 100 and a severity tier (nominal, near
  miss, critical).
- **Ranks** planners by the mean of their four family scores and names the worst
  scenario per family.
- **Reports** a static HTML page with the leaderboard, bird's eye view and TTC plots,
  metric histograms and the standards table, and exports cut in and hard brake scenarios
  as simplified OpenSCENARIO XML.

## Quickstart

Requires Python 3.11 or newer.

```bash
pip install -e ".[dev]"

avsb generate --suite core --seed 42      # 60 scenario YAMLs in scenarios/core/
avsb run --suite core --planner all       # 180 JSONL trajectory logs in runs/core/
avsb report --suite core                  # reports/core/index.html
avsb plots --suite core                   # bird's eye view per scenario and planner
avsb export-xosc --suite core --family cut_in

pytest -q
```

A second suite, `holdout`, is drawn from the same generators with a different seed. It
is meant for pre-registered release gates, so the core leaderboard cannot be tuned to
them.

## Results (core suite, seed 42)

| Rank | Planner | Composite | cut_in | ped_occluded | weather_ramp | hard_brake | Collisions |
|---:|:---|---:|---:|---:|---:|---:|---:|
| 1 | `cautious_idm` | 74.17 | 88.66 | 24.75 | 99.55 | 83.73 | 11 |
| 2 | `idm` | 64.88 | 82.91 | 14.91 | 95.99 | 65.71 | 14 |
| 3 | `constant_velocity` | 12.50 | 36.44 | 12.86 | 0.00 | 0.71 | 52 |

The three planners are a cautious Intelligent Driver Model (wider headway, lower target
speed), the textbook IDM, and a null baseline that never brakes. The specification
required them to land in that order, and they do: 61.7 points separate the leader from
the null baseline. The occluded pedestrian family caps every planner below 25, so it is
the family to fix first.

## Scoring your own planner

The metrics read only the trajectory log, so any stack that writes the same format can
be scored on the same 60 scenarios. One JSONL file per scenario and planner:

```
runs/{suite}/{planner}/{scenario_id}.jsonl
```

Line 1 is a header record (schema version, scenario id, planner, time step, number of
steps, actor ids). Every following line is one actor state, ego first at each step. The
schema is defined in `src/avsb/schema/trajectory.py`, and
`src/avsb/adapters/protocol.py` holds the interface for log producers such as a driving
simulator or recorded vehicle data. No such adapter ships yet.

## Standards mapping

`src/avsb/regmap/regulatory_mapping.yaml` points every scored metric and scenario family
at clauses of ISO 26262, ISO 21448 (SOTIF), UL 4600 and the EU AI Act, and the report
renders it as a table. Every entry is tagged **informative**: it shows where an artifact
is relevant to a standard's subject matter. It is not a conformity assessment, a
certification, an ASIL classification or legal advice, and it quotes no standard text.

## What this is not

- **Not a physics simulator.** A 2D kinematic model replaces the CARLA simulator the
  original plan named. That keeps the suite fast and reproducible and leaves out sensor
  physics, vehicle dynamics and perception.
- **Not trained or tuned on real driving data.** Scenarios are procedurally generated;
  no nuScenes, Waymo or other dataset is used or included.
- **Not a statement about any real vehicle.** The three planners are reference
  baselines that make the discrimination range visible.

## Layout

```
src/avsb/
  generation/   scenario families and suites (core, holdout)
  engine/       kinematic simulator, scripted adversaries, occlusion
  planners/     constant_velocity, idm, cautious_idm
  metrics/      TTC, PET, distance margin, collision and delta-v, comfort, speed
  scoring/      per-run score, severity tier, family and planner aggregates
  report/       HTML report and plots
  export/       OpenSCENARIO XML export
  regmap/       informative standards mapping
  schema/       pydantic models for scenarios, trajectories and results
  adapters/     interface for external trajectory producers
docs/ARCHITECTURE.md   the implementation specification
```

## License

MIT, see [LICENSE](LICENSE). The standards named above are referenced by clause number
only; their text belongs to their publishers.
