# av-safety-benchmark — Implementation Specification (v1, One-Shot)

**Status:** Binding implementation spec. A single agent run implements this document end-to-end without asking questions. Where this spec and the README disagree, this spec wins.

---

## 1. Context & Positioning

This repository exists to demonstrate, with running code, the claim behind its owner's one-liner: *"I build the software, data, and validation platforms that let machines operate safely in the physical world."* av-safety-benchmark is the validation-platform artifact in that story — an AI assurance and simulation project aimed at the hardest unsolved problem in autonomous driving: not building the stack, but *proving* it is safe with quantifiable, reproducible, standards-aligned evidence. The intended reviewer is a hiring manager at an AV-validation or assurance company (scenario-based testing, simulation, homologation support). That reviewer should be able to clone the repo, run three commands, and within two minutes see a leaderboard, near-miss trajectory plots, and a regulatory traceability table — and recognize that the person who built it understands scenario-based safety assessment, surrogate safety metrics, and the standards landscape (ISO 26262, ISO 21448/SOTIF, UL 4600, EU AI Act).

The README envisions CARLA as the execution backend. **This spec explicitly replaces CARLA with a lightweight, deterministic kinematic scenario engine plus log replay.** The justification is already in the README itself: *"Any system that can interface with CARLA or produce trajectory logs in a supported format can be evaluated."* That second clause is the wedge. If the product's core claim is system-agnostic evaluation of trajectory logs, then the data contracts — a scenario definition schema and a trajectory log format — are the product, and the simulator is merely one producer of conforming logs. A 2D kinematic engine at 10 Hz produces those logs deterministically, in seconds, on a laptop, with zero GPU, zero network, and zero multi-gigabyte simulator install. CARLA adds photorealism and sensor simulation, which matter for perception testing but are irrelevant to trajectory-level surrogate safety metrics (TTC, PET, distance margins). Dropping CARLA converts a quarter-long integration project into a one-shot, fully reproducible benchmark — and the CARLA adapter remains a cleanly-specified v2 extension point (§12).

What the reviewer sees at the end: a pip-installable Python package `avsb` that procedurally generates a suite of ~60 parameterized safety-critical scenarios across four families (cut-in, occluded pedestrian, weather-degradation ramp, lead-vehicle hard brake), runs three baseline planners against them in a deterministic kinematic simulator, computes a mathematically-defined safety metrics suite from the trajectory logs, aggregates scores into a leaderboard where the cautious planner demonstrably beats the naive one, renders a static HTML report with bird's-eye-view near-miss plots, exports a subset of scenarios to simplified OpenSCENARIO XML, and ships a machine-readable (explicitly informative-only) mapping from every metric and scenario family to clauses of the four safety standards. Everything runs offline, end-to-end, in under two minutes.

---

## 2. One-Shot Scope Statement

Build the Python package `src/avsb/` containing exactly:

- **`schema/`** — Pydantic v2 models that ARE the data contracts: (a) scenario definition YAML (actors, initial 2D pose + velocity, triggers, recorded parameter values); (b) trajectory log format (JSONL of timestamped 2D poses/velocities per actor); (c) per-scenario result JSON; (d) regulatory mapping schema. These two first schemas carry the product's core claim: system-agnostic evaluation.
- **`generation/`** — Seeded procedural generators for 4 scenario families: **cut-in**, **occluded pedestrian emergence**, **weather-degradation ramp** (visibility/friction ramp), **lead-vehicle hard brake**. Random parameter sweep per family → suite `core` = **60 concrete scenarios** (16 + 16 + 14 + 14), byte-identical for a given seed.
- **`engine/`** — Fixed-timestep (**10 Hz**, `dt = 0.1 s`) kinematic simulator: scripted adversary actors executing their scenario definitions, plus a pluggable ego planner interface `Planner.step(obs) -> Action(accel, steer)` with an exactly-specified `Observation` dataclass. Ego dynamics: **kinematic bicycle model** (justified in §4).
- **`planners/`** — 3 baselines that populate the leaderboard: `constant_velocity` (naive, never reacts), `idm` (IDM-based reactive with MOBIL-style cut-in awareness), `cautious_idm` (same controller, larger headway/standstill gap, lower target speed). Required emergent ordering: **cautious_idm > idm > constant_velocity** — this is what makes the leaderboard meaningful, and it is an acceptance criterion (§8, AC-7).
- **`metrics/`** — TTC, PET, minimum distance margin, collision flag + delta-v severity index, hard-braking/intervention proxy. Each defined by an explicit formula in §5.6 so implementation is unambiguous. Metrics are computed **from trajectory logs only** (never from engine internals) — this enforces the system-agnostic claim.
- **`scoring/`** — per-scenario score → per-family score → composite safety profile; severity tiers (nominal / near-miss / critical).
- **`regmap/`** — machine-readable `regulatory_mapping.yaml`: each metric and scenario family → ISO 26262 / ISO 21448 (SOTIF) / UL 4600 / EU AI Act clause references, rendered into the HTML report. **Informative only; no certification, conformance, or ASIL determination claims anywhere.**
- **`report/`** — static HTML report via Jinja2 + matplotlib (**Agg backend, headless**): leaderboard table, BEV trajectory plots of worst-case scenarios, TTC-over-time curve, metric distributions, regulatory mapping table. Output `reports/core/index.html` + PNGs; copies 3 key PNGs to `docs/screenshots/`.
- **`export/`** — simplified OpenSCENARIO export (`avsb export-xosc`) for the `cut_in` and `hard_brake` families only. Export-only, simplified OSC-1.x-style XML via stdlib `xml.etree`. No OSC 2.0, no round-trip parsing.
- **CLI** (stdlib `argparse`; entry point `avsb`):
  - `avsb generate --suite core --seed 42`
  - `avsb run --suite core --planner all`
  - `avsb report --suite core --out reports/core/`
  - `avsb plots --suite core --out reports/core/plots_all/` (BEV PNG per (scenario, planner) pair; `--scenarios-filter id1,id2` restricts it)
  - `avsb export-xosc --suite core --family cut_in --out exports/xosc/`
- **`tests/`** — pytest suite per §10.
- Packaging: `pyproject.toml` (setuptools, `src/` layout), `README` untouched.

**Environment constraints (hard):**

- Python **3.11+**, macOS ARM (must also run on Linux CI), **no GPU**, **zero network at runtime** (network allowed only for the initial `pip install`).
- Runtime dependencies: `pydantic`, `numpy`, `pyyaml`, `jinja2`, `matplotlib` — nothing else at runtime (`typer` explicitly NOT used; argparse chosen to keep the dependency set minimal). Dev dependency: `pytest`.
- `avsb generate && avsb run --planner all && avsb report` completes in **< 2 minutes** on a laptop (target < 60 s; see §11).
- No CARLA, no nuScenes/Waymo downloads, no Docker requirement, no external assets or fonts.

---

## 3. Non-Goals

| Non-goal | Reason |
|---|---|
| CARLA integration | Requires a multi-GB install, GPU, and non-deterministic sensor/physics loops; contributes nothing to trajectory-level surrogate metrics. The trajectory-log contract (§5.2) is the adapter seam; CARLA becomes one log producer in v2. |
| nuScenes / Waymo dataset adapters | Multi-GB licensed downloads violate the zero-network, <2-min constraints. The adapter `Protocol` is specified as a **stub interface only** (§5.8) so the seam is visible without the payload. |
| OpenSCENARIO 2.0 parsing | OSC 2.0 is a full DSL; a conformant parser is a project in itself. We do **export-only, simplified OSC-1.x-style XML** for two families — enough to demonstrate standards literacy honestly, without claiming conformance. |
| ML perception / ML planning | No PyTorch, no trained models. Baselines are analytic (IDM-family) so results are deterministic, explainable, and reproducible on any machine. ML planners plug in later via the `Planner` protocol. |
| 3D visualization | BEV (2D) matplotlib plots communicate near-misses better in a static report and keep the dependency set to matplotlib. No plotly, no three.js. |
| Public leaderboard hosting | Static HTML checked into `reports/` is sufficient for the demo; hosting adds infra with zero evaluation-methodology value. |
| ASIL determination / certification claims | Legally and technically out of scope. `regmap/` is labeled informative-only, and the report renders a mandatory disclaimer (§5.7). Making this explicit is itself a signal of standards literacy. |
| Sensor models, noise, latency simulation | Weather degradation is modeled at the *information* level (visibility radius filters observations; friction caps deceleration). Physical sensor models are v2. |
| Multi-lane road networks / maps | One straight multi-lane road segment per scenario. All four families are expressible on it; map handling is orthogonal complexity. |

---

## 4. System Overview

```
                       avsb generate                 avsb run                     avsb report
                     ┌───────────────┐          ┌─────────────────┐          ┌─────────────────┐
 family params  ───► │  generation/  │  YAML    │     engine/     │  JSONL   │    metrics/     │
 + seed              │  (4 families, │ ───────► │  10 Hz kinematic│ ───────► │  TTC PET dmin   │
                     │   seeded RNG) │ scenario │  sim + scripted │ traj     │  Δv  hard-brake │
                     └───────────────┘  defs    │  actors         │ logs     └────────┬────────┘
                                                │        ▲        │                   │ result JSON
                                                │        │ Action │          ┌────────▼────────┐
                                                │  ┌─────┴──────┐ │          │    scoring/     │
                                                │  │ planners/  │ │          │ scenario→family │
                                                │  │ (3 base-   │ │          │ →composite      │
                                                │  │  lines)    │ │          └────────┬────────┘
                                                │  └────────────┘ │                   │
                                                └─────────────────┘          ┌────────▼────────┐
                                                        │                    │    report/      │
                                                        └── export/ ──►.xosc │ Jinja2 + mpl    │
                                                                             │ + regmap/ table │
                                                                             └─────────────────┘
                                                                              reports/core/index.html
```

**`schema/`** holds every Pydantic model in the system. Nothing else defines data shapes; generation writes `ScenarioDefinition`s, the engine writes `TrajectoryLog` records, metrics read `TrajectoryLog` and write `ScenarioResult`, scoring reads `ScenarioResult`s. Because metrics consume only the JSONL trajectory contract, any external system that emits conforming JSONL can be scored — the system-agnostic wedge made structural.

**`generation/`** contains one generator per family. Each generator owns a parameter-range table (documented constants), draws N parameter vectors from `numpy.random.default_rng(seed + family_offset)`, and materializes each vector into a complete `ScenarioDefinition` (road, ego initial state, scripted actor phases, triggers). Serialization is canonical (sorted keys, floats rounded to 4 decimals) so identical seeds give byte-identical YAML.

**`engine/`** is a fixed-timestep loop: build the ego's `Observation` (visibility-filtered), call `planner.step`, clamp the `Action` (friction-aware), integrate the ego with a **kinematic bicycle model**, advance scripted actors along their phase scripts, append one JSONL record. *Model choice — bicycle over point-mass:* the cut-in and lane-keeping behaviors require heading and lateral motion to be kinematically coupled to speed and steering; a point-mass allows physically impossible sideways teleports that would corrupt TTC/PET geometry. The kinematic bicycle (4 states, 2 inputs, one `tan`) adds essentially zero cost over point-mass while keeping every logged trajectory drivable. Tire dynamics are irrelevant at ≤ 20 m/s benchmark speeds.

**`planners/`** implements the `Planner` protocol three times. `constant_velocity` applies zero acceleration and zero steering — it is the falsifiable null hypothesis and *must* crash in hard-brake and cut-in scenarios. `idm` is the Intelligent Driver Model for longitudinal control with a MOBIL-style leader-selection rule (a laterally encroaching vehicle is adopted as leader before it fully enters the lane) plus a P-controller for lane keeping. `cautious_idm` is the same code with a more conservative parameter set. The leaderboard ordering emerges from physics, not from hand-tuned scores.

**`metrics/`** is pure functions over `TrajectoryLog` + `ScenarioDefinition` (needed for actor dimensions/masses). All five metrics are defined by the formulas in §5.6.

**`scoring/`** maps metric vectors to a 0–100 per-scenario score, assigns severity tiers, aggregates to per-family means and an equal-weighted composite per planner.

**`regmap/`** ships a hand-authored `regulatory_mapping.yaml` validated by a Pydantic model and rendered as a traceability table in the report, wrapped in an explicit informative-only disclaimer.

**`report/`** renders `reports/core/index.html` from Jinja2 templates with matplotlib-Agg PNGs: leaderboard, per-family score bars, metric distributions, BEV plots of the worst scenarios, TTC-over-time for the worst cut-in, regulatory table. Copies three named PNGs into `docs/screenshots/`.

**`export/`** walks `cut_in` and `hard_brake` scenario definitions and emits simplified `.xosc` XML (Storyboard → Story → Act → LaneChangeAction / SpeedAction) using `xml.etree.ElementTree` only.

---

## 5. Data Contracts (hallucination firewall)

Everything in this section is normative. Field names, types, units, and formulas below are exact; implement them verbatim.

### 5.0 Global conventions

- **Frame:** 2D world frame per scenario. `x` [m] forward along the (straight) road, `y` [m] lateral, +y is left. `yaw` [rad], 0 = +x direction, CCW positive. Lane `i` (0-indexed, rightmost = 0) has centerline `y = (i + 0.5) * lane_width_m`.
- **Units:** meters, seconds, m/s, m/s², radians, kilograms. No exceptions, no km/h anywhere in code or schemas.
- **Time:** `t` [s] from scenario start; step `k` has `t = k * dt_s` with `dt_s = 0.1`.
- **Footprints:** every actor is a disc of radius `radius_m` for all metric/collision computation. Vehicles: `radius_m = length_m / 2` (deliberately conservative — a safety benchmark should over-flag, not under-flag; documented in report footer). Pedestrians: `radius_m = 0.3`. Static occluders keep their rectangle **only** for occlusion ray-tests; for distance metrics they are ignored (they are roadside parked vehicles, not conflict partners).
- **IDs:** ego actor id is always the literal string `"ego"`.

### 5.1 Scenario definition YAML (`schema/scenario.py`)

Pydantic model tree (all models `frozen=True` where practical; `extra="forbid"` everywhere):

```
ScenarioDefinition
├─ schema_version: Literal["1.0"]
├─ scenario_id: str                  # "core-cutin-0001" — {suite}-{family_slug}-{4-digit index}
├─ suite: str                        # "core"
├─ family: Literal["cut_in","ped_occluded","weather_ramp","hard_brake"]
├─ description: str
├─ seed: int                         # suite seed used at generation time (provenance)
├─ duration_s: float                 # simulation horizon, ∈ [8.0, 30.0]
├─ dt_s: Literal[0.1]
├─ road: Road
│   ├─ n_lanes: int                  # ≥ 1; core suite uses 2 or 3
│   ├─ lane_width_m: float           # 3.5
│   ├─ length_m: float               # 400.0
│   └─ speed_limit_mps: float        # e.g. 13.9 (≈50 km/h) or 22.2 (≈80 km/h)
├─ environment: Environment          # linear ramp; constant if start == end
│   ├─ visibility_start_m: float     # sensing radius at t=0
│   ├─ visibility_end_m: float       # sensing radius at t=duration_s
│   ├─ friction_start: float         # μ ∈ (0, 1]
│   └─ friction_end: float
├─ ego: EgoSpec
│   ├─ initial: InitialState
│   │   ├─ x_m: float, y_m: float, yaw_rad: float, speed_mps: float
│   ├─ target_speed_mps: float       # planner set-speed hint (≤ speed_limit)
│   ├─ lane: int                     # initial/intended lane index
│   ├─ length_m: float               # 4.5
│   ├─ width_m: float                # 1.9
│   └─ mass_kg: float                # 1500.0
├─ actors: list[ActorSpec]           # scripted, non-ego; may be empty
│   └─ ActorSpec
│       ├─ actor_id: str             # unique, != "ego"
│       ├─ kind: Literal["vehicle","pedestrian","static"]
│       ├─ length_m: float, width_m: float, mass_kg: float
│       ├─ initial: InitialState     # same fields as ego initial
│       └─ phases: list[Phase]       # executed in order; empty for kind="static"
│           └─ Phase
│               ├─ trigger: Trigger  # phase STARTS when its trigger fires
│               │   ├─ type: Literal["time","ego_gap","ego_x"]
│               │   ├─ at_time_s: float | None        # type="time": t >= at_time_s
│               │   ├─ gap_m: float | None            # type="ego_gap": (self.x - ego.x) <= gap_m
│               │   └─ ego_x_m: float | None          # type="ego_x": ego.x >= ego_x_m
│               ├─ accel_mps2: float                  # longitudinal accel along own heading
│               ├─ target_speed_mps: float | None     # accel applies until reached, then hold
│               ├─ target_y_m: float | None           # lateral goal (lane-change / crossing)
│               └─ lateral_speed_mps: float           # |dy/dt| toward target_y_m; 0 = none
└─ parameters: dict[str, float]      # the sampled family parameters (provenance/reporting)
```

Phase semantics (engine, normative): the first phase whose trigger has fired and which has not been superseded by a later-listed fired phase is active (i.e., phases are checked in list order each step; the **last** phase whose trigger condition is/was satisfied is active; once fired, a trigger stays fired). Within the active phase, actor speed integrates `accel_mps2` clamped so it never crosses `target_speed_mps` (if set) and never goes below 0; `y` moves toward `target_y_m` at `lateral_speed_mps` (m/s, straight-line in y) and stops there; actor heading for logging is `atan2(dy, dx)` of its actual displacement (vehicles), pedestrians keep `yaw = ±π/2` while crossing. Scripted actors are kinematic scripts, not planners — they never react to the ego except through their declared triggers.

**Complete example scenario** (this exact document must validate against the schema; also used as the fixture in `tests/data/example_cut_in.yaml`):

```yaml
schema_version: "1.0"
scenario_id: core-cutin-0001
suite: core
family: cut_in
description: "Adjacent-lane vehicle cuts in ahead of ego with 14.0 m gap, closing 3.0 m/s"
seed: 42
duration_s: 15.0
dt_s: 0.1
road:
  n_lanes: 2
  lane_width_m: 3.5
  length_m: 400.0
  speed_limit_mps: 22.2
environment:
  visibility_start_m: 200.0
  visibility_end_m: 200.0
  friction_start: 0.9
  friction_end: 0.9
ego:
  initial: {x_m: 0.0, y_m: 1.75, yaw_rad: 0.0, speed_mps: 20.0}
  target_speed_mps: 20.0
  lane: 0
  length_m: 4.5
  width_m: 1.9
  mass_kg: 1500.0
actors:
  - actor_id: cutter
    kind: vehicle
    length_m: 4.5
    width_m: 1.9
    mass_kg: 1500.0
    initial: {x_m: 22.0, y_m: 5.25, yaw_rad: 0.0, speed_mps: 17.0}
    phases:
      - trigger: {type: time, at_time_s: 0.0}
        accel_mps2: 0.0
        target_speed_mps: 17.0
        target_y_m: null
        lateral_speed_mps: 0.0
      - trigger: {type: ego_gap, gap_m: 14.0}
        accel_mps2: 0.0
        target_speed_mps: 17.0
        target_y_m: 1.75
        lateral_speed_mps: 1.2
parameters:
  initial_gap_m: 22.0
  trigger_gap_m: 14.0
  speed_delta_mps: -3.0
  lateral_speed_mps: 1.2
```

Canonical serialization (normative, required for byte-identical determinism): `yaml.safe_dump(model.model_dump(mode="json"), sort_keys=True, default_flow_style=False)` after rounding every float to 4 decimals via a recursive helper `round_floats(obj, ndigits=4)` in `schema/io.py`. All YAML written by `avsb` goes through the single function `schema.io.write_yaml(path, model)`.

### 5.2 Trajectory log format — JSONL (`schema/trajectory.py`)

One file per (scenario, planner) run: `runs/{suite}/{planner}/{scenario_id}.jsonl`. Line 1 is a header record; every subsequent line is one actor-state record. **This file format is the system-agnostic evaluation contract** — the metrics layer accepts any conforming file.

Header record (`TrajectoryHeader`):

```json
{"record": "header", "schema_version": "1.0", "scenario_id": "core-cutin-0001", "planner": "idm", "dt_s": 0.1, "n_steps": 150, "actor_ids": ["ego", "cutter"], "created": "2026-07-12T00:00:00Z"}
```

State record (`TrajectoryRecord`) — one per actor per step, ego first, then actors in `actor_ids` order:

```json
{"record": "state", "t": 0.0, "actor_id": "ego", "x": 0.0, "y": 1.75, "yaw": 0.0, "vx": 20.0, "vy": 0.0, "accel_cmd": -0.31, "steer_cmd": 0.0}
{"record": "state", "t": 0.0, "actor_id": "cutter", "x": 22.0, "y": 5.25, "yaw": 0.0, "vx": 17.0, "vy": 0.0, "accel_cmd": null, "steer_cmd": null}
```

Fields: `t` [s], `x,y` [m], `yaw` [rad], `vx,vy` [m/s world frame], `accel_cmd` [m/s², post-clamp commanded, ego only], `steer_cmd` [rad, ego only]; scripted actors log `null` for both commands. `schema/trajectory.py` provides `TrajectoryLog.read(path) -> TrajectoryLog` and `TrajectoryLog.states(actor_id) -> np.ndarray` of shape `(n_steps, 5)` columns `(t, x, y, vx, vy)` plus `.yaw(actor_id)`, `.accel_cmd()` arrays. Floats in JSONL are rounded to 4 decimals at write time (same `round_floats` helper) for cross-run byte-identity.

### 5.3 Observation & Action — the planner interface (`engine/observation.py`, `planners/base.py`)

```python
@dataclass(frozen=True)
class ActorObs:
    actor_id: str
    kind: str            # "vehicle" | "pedestrian"
    x: float; y: float   # [m] world frame
    yaw: float           # [rad]
    vx: float; vy: float # [m/s] world frame
    length: float; width: float; radius: float  # [m]

@dataclass(frozen=True)
class EgoObs:
    x: float; y: float; yaw: float
    speed: float                  # [m/s] scalar body-frame forward speed
    accel_prev: float             # last commanded accel (post-clamp), 0.0 at k=0

@dataclass(frozen=True)
class Observation:
    t: float
    dt: float                     # 0.1
    ego: EgoObs
    actors: tuple[ActorObs, ...]  # ONLY visible actors (see visibility rule)
    lane_width: float
    n_lanes: int
    ego_lane_center_y: float      # centerline of the ego's *intended* lane (ScenarioDefinition.ego.lane)
    speed_limit: float            # [m/s]
    target_speed: float           # [m/s] from ScenarioDefinition.ego.target_speed_mps
    visibility_m: float           # current sensing radius (ramped)
    friction: float               # current μ (ramped)

@dataclass(frozen=True)
class Action:
    accel: float                  # [m/s²] longitudinal; engine clamps to [a_min_eff, A_MAX]
    steer: float                  # [rad] front wheel angle; engine clamps to [-STEER_MAX, +STEER_MAX]

class Planner(Protocol):
    name: str
    def reset(self, scenario: ScenarioDefinition) -> None: ...
    def step(self, obs: Observation) -> Action: ...
```

**Visibility rule (normative):** an actor appears in `obs.actors` iff (a) Euclidean center distance to ego ≤ `visibility_m(t)`, AND (b) the segment from ego center to actor center does not intersect any `kind="static"` actor's rectangle footprint (axis-aligned, centered at its pose; segment–rectangle intersection via the Liang–Barsky/slab test in `engine/occlusion.py`). Occluded or out-of-range actors are simply absent — planners cannot cheat. `kind="static"` actors are never themselves listed in `obs.actors`.

**Ramping (normative):** `visibility_m(t) = lerp(visibility_start_m, visibility_end_m, t / duration_s)`, same for `friction(t)`.

**Clamps (engine constants in `engine/simulator.py`):** `A_MAX = +3.0` m/s², `A_MIN = -8.0` m/s², effective braking floor `a_min_eff = max(A_MIN, -friction(t) * 9.81)` (weather bites here), `STEER_MAX = 0.5` rad. Ego speed is clamped ≥ 0 (no reverse).

**Ego integration (kinematic bicycle, explicit Euler, normative):** wheelbase `L = 2.8` m;

```
v_{k+1}   = clip(v_k + a·dt, 0, ∞)
yaw_{k+1} = yaw_k + (v_k / L) · tan(steer) · dt
x_{k+1}   = x_k + v_k · cos(yaw_k) · dt
y_{k+1}   = y_k + v_k · sin(yaw_k) · dt
```

Logged ego `vx = v·cos(yaw)`, `vy = v·sin(yaw)`.

### 5.4 Per-scenario result JSON (`schema/result.py`) — the RouteValidationReport-equivalent

Written to `runs/{suite}/{planner}/{scenario_id}.result.json`:

```json
{
  "schema_version": "1.0",
  "scenario_id": "core-cutin-0001",
  "suite": "core",
  "family": "cut_in",
  "planner": "idm",
  "n_steps": 150,
  "duration_s": 15.0,
  "trajectory_log": "runs/core/idm/core-cutin-0001.jsonl",
  "metrics": {
    "ttc_min_s": 2.31,
    "ttc_min_t_s": 6.4,
    "pet_min_s": 1.85,
    "d_min_m": 1.42,
    "d_min_t_s": 6.9,
    "collision": false,
    "collision_t_s": null,
    "delta_v_mps": null,
    "severity_index": 0,
    "hard_brake_fraction": 0.067,
    "hard_brake_events": 1
  },
  "score": 71.4,
  "severity_tier": "near_miss"
}
```

Pydantic models: `MetricSet` (exactly the 11 metric fields above, `ttc_min_s`/`pet_min_s` may be `null` meaning "no closing conflict / no shared zone" and are treated as +∞ by scoring) and `ScenarioResult`. Aggregation output `reports/{suite}/summary.json` = `SuiteSummary`: `{planner: {composite: float, families: {family: {score: float, n: int, collisions: int, worst_scenario_id: str}}}}` plus a flat `results: [ScenarioResult…]` echo.

### 5.5 `regulatory_mapping.yaml` structure (`regmap/`)

```yaml
schema_version: "1.0"
disclaimer: >
  Informative traceability only. Nothing in this mapping constitutes a
  conformity assessment, certification, ASIL/SOTIF classification, or legal
  advice. Clause references identify where each artifact is *relevant* to a
  standard's subject matter, not evidence of compliance with it.
entries:
  - id: map-ttc
    kind: metric                # "metric" | "family"
    target: ttc_min_s           # metric field name or family slug
    title: "Time-to-Collision (minimum)"
    references:
      - standard: "ISO 21448:2022 (SOTIF)"
        clause: "Clause 7; Annex C.2"
        relation: informative
        note: "Surrogate indicator for evaluation of known hazardous scenarios."
      - standard: "UL 4600:2023"
        clause: "Section 8 (Risk Assessment), 16 (Metrics & SPIs)"
        relation: informative
        note: "Candidate safety performance indicator (SPI) with defined threshold."
      - standard: "EU AI Act (Reg. 2024/1689)"
        clause: "Art. 9 (risk management), Art. 15 (accuracy & robustness)"
        relation: informative
        note: "Quantitative evidence usable in a risk-management file."
  - id: map-family-cutin
    kind: family
    target: cut_in
    title: "Aggressive cut-in scenario family"
    references:
      - standard: "ISO 21448:2022 (SOTIF)"
        clause: "Clause 7.2; Annex F"
        relation: informative
        note: "Known potentially hazardous scenario class; parameterized coverage."
      - standard: "ISO 26262-3:2018"
        clause: "Clause 6 (HARA inputs)"
        relation: informative
        note: "Situation catalog input to hazard analysis. No ASIL is derived here."
```

Author one `metric` entry per metric (5) and one `family` entry per family (4) — 9 entries total, each with 2–4 references drawn from: ISO 26262-3/-4:2018, ISO 21448:2022 Clauses 6/7/Annexes C/F, UL 4600:2023 Sections 8/16/17, EU AI Act Art. 9/10/15 + Annex III. `regmap/loader.py` validates against `schema/regmap.py` models (`RegEntry`, `RegReference`, `relation: Literal["informative"]` — the type system itself forbids stronger claims). The report renders `disclaimer` verbatim above the table.

### 5.6 Metric definitions (normative formulas)

All metrics are computed offline from a `TrajectoryLog` + `ScenarioDefinition` (for radii/masses). Conflict partners = every non-static actor. Let ego position `p_e(k)`, velocity `v_e(k)` (world-frame 2D from `vx,vy`), other actor `a`: `p_a(k)`, `v_a(k)`; combined radius `R_a = r_ego + r_a`.

**Separation:** `d_a(k) = ‖p_a(k) − p_e(k)‖₂ − R_a`  (may be negative = overlap).

**(M1) Minimum distance margin:** `d_min = min_k min_a d_a(k)`; `d_min_t_s` = time of the minimum. Reported clipped at ≥ −R (unclipped internally).

**(M2) Collision flag & delta-v severity:** `collision = ∃k,a : d_a(k) ≤ 0`. At the first such step `k*` with partner `a*`, using a perfectly-inelastic (plastic) closing-speed model:

```
delta_v = ( m_a / (m_e + m_a) ) · ‖ v_e(k*) − v_a(k*) ‖₂     [m/s, ego's Δv]
```

Severity index (benchmark-internal tiers — deliberately NOT ISO 26262 S-classes, state this in the docstring): `0` if no collision; `1` if `delta_v < 2.0`; `2` if `2.0 ≤ delta_v < 6.0`; `3` if `delta_v ≥ 6.0`. Simulation continues after collision (logs stay full-length) but metrics freeze `collision_t_s`, `delta_v` at first contact.

**(M3) Time-to-Collision (2D closing-speed TTC):** for each step `k` and actor `a`, let `r = p_a − p_e`, `v_rel = v_a − v_e`, closing speed `c = −(r · v_rel)/‖r‖`. Then

```
TTC_a(k) = d_a(k) / c        if c > 0.1 m/s and d_a(k) > 0,   else +∞
ttc_min  = min_{k,a} TTC_a(k)      (null in JSON if never finite)
```

The `c > 0.1` guard avoids numerical blow-ups at near-zero closing speed. If a collision occurred, `ttc_min` is still reported from pre-contact steps.

**Worked example (this exact case is the unit test `test_ttc_hand_computed`):** ego at `x=0`, `v=(20,0)`; lead vehicle at `x=48`, `v=(12,0)`; both length 4.5 m → `r_ego = r_lead = 2.25`, `R = 4.5`. Then `d = 48 − 4.5 = 43.5 m`, `c = −((48,0)·(−8,0))/48 = 8.0 m/s`, so **`TTC = 43.5 / 8.0 = 5.4375 s`**. Assert equality to 1e-9.

**(M4) Post-Encroachment Time (grid-cell PET):** discretize the road area into a grid of `0.5 m × 0.5 m` cells. Actor `a` occupies cell `c` at step `k` iff the cell center lies inside the actor's disc. For each cell occupied by both ego and some actor `a` at **disjoint** step sets, with intervals `[k₁ˢ,k₁ᵉ]` (first occupant) and `[k₂ˢ,k₂ᵉ]` (second occupant):

```
PET_cell = (k₂ˢ − k₁ᵉ) · dt      (only if k₂ˢ > k₁ᵉ)
pet_min  = min over all such cells and actor pairs
```

If ego and an actor occupy the same cell at the same step, that is captured by M1/M2, not PET. If no cell is ever shared, `pet_min = null` (∞). Implementation: quantize positions to cell indices with numpy, build `dict[(cell, actor)] -> (first_step, last_step)`; O(steps × actors × cells-per-disc), trivially fast at these sizes.

**(M5) Hard-braking / intervention proxy:** using the ego's logged `accel_cmd` series (post-clamp):

```
hard_brake_mask(k)  = accel_cmd(k) ≤ −4.0 m/s²
hard_brake_fraction = mean(hard_brake_mask)
hard_brake_events   = number of maximal contiguous True runs in hard_brake_mask
```

Interpretation (report footnote): a proxy for safety-driver-intervention-worthy events; −4 m/s² is a common comfort/emergency boundary in the naturalistic-driving literature.

### 5.7 Scoring (`scoring/score.py`, normative)

Per-scenario score `S ∈ [0, 100]`, with `TTC = ttc_min_s` (∞ if null), `PET = pet_min_s` (∞ if null), `D = max(d_min_m, 0)`, `H = hard_brake_fraction`:

```
if collision:
    S = 10.0 if severity_index == 1 else 0.0
else:
    f_ttc  = clip(TTC / 3.0, 0, 1)          # 3 s reference threshold
    f_dist = clip(D   / 2.0, 0, 1)          # 2 m reference margin
    f_pet  = clip(PET / 2.0, 0, 1)          # 2 s reference PET
    f_comf = 1 − clip(H / 0.25, 0, 1)
    S = 100 · (0.40·f_ttc + 0.25·f_dist + 0.20·f_pet + 0.15·f_comf)
```

Severity tier: `critical` if `collision or TTC < 0.5 or d_min_m < 0.25`; else `near_miss` if `TTC < 1.5 or d_min_m < 0.75 or PET < 1.0`; else `nominal`.

Aggregation: family score = arithmetic mean of `S` over the family's scenarios; **composite = unweighted mean of the 4 family scores**. Leaderboard = planners sorted by composite, descending; also shows per-family scores, collision counts, tier counts.

### 5.8 External-log adapter Protocol (stub only — v2 seam)

Define in `avsb/adapters/protocol.py`, with docstring but **no implementations**:

```python
class TrajectorySource(Protocol):
    """v2 seam: anything that yields conforming TrajectoryLogs (CARLA bridge,
    nuScenes/Waymo converters, real-vehicle CAN exports) can be scored by
    avsb.metrics without touching the engine."""
    def scenarios(self) -> Iterable[ScenarioDefinition]: ...
    def log_for(self, scenario_id: str) -> TrajectoryLog: ...
```

### 5.9 Generation parameter tables (normative ranges, drawn uniformly per scenario)

All draws from `numpy.random.default_rng(seed * 1000 + FAMILY_OFFSET)`; offsets: cut_in=1, ped_occluded=2, weather_ramp=3, hard_brake=4. Counts: 16/16/14/14 = 60 scenarios in suite `core`.

| Family | Parameter | Range | Notes |
|---|---|---|---|
| cut_in (16) | ego speed | 15–22 m/s | 2-lane road, ego lane 0, limit 22.2 |
| | initial_gap_m | 15–30 | cutter starts in lane 1, ahead of ego |
| | speed_delta_mps | −5 … +1 | cutter speed = ego speed + delta |
| | trigger_gap_m | 8–18 | cut begins when gap ≤ this |
| | lateral_speed_mps | 0.6–1.5 | duration 15 s |
| ped_occluded (16) | ego speed | 8–14 m/s | 2-lane road, limit 13.9 |
| | occluder_x_m | 40–70 | parked vehicle (`static`, 6×2 m) at `y = −1.2` |
| | ped_speed_mps | 1.0–2.5 | starts behind occluder at `y = −2.5`, crosses to `y = +6` |
| | trigger_ego_x offset | occluder_x − (12–30) | crossing starts via `ego_x` trigger |
| weather_ramp (14) | ego speed | 14–20 m/s | 3-lane, lead vehicle in ego lane, gap 45–70 m, lead speed 8–12 m/s |
| | visibility ramp | 200 → (15–45) m | linear over full duration (20 s) |
| | friction ramp | 0.9 → (0.25–0.5) | caps braking authority late in scenario |
| hard_brake (14) | ego speed | 15–22 m/s | 2-lane; lead in ego lane |
| | initial_gap_m | 12–35 | |
| | lead_speed_mps | ego speed − (0–3) | |
| | brake_decel_mps2 | −(3.5–8.0) | phase triggered at t = 2–5 s, lead brakes to 0 and holds |

The exact per-scenario draws land in `parameters:` for provenance. Ranges were chosen so that: constant_velocity collides in most hard_brake and many cut_in/ped scenarios; idm survives most but records near-misses; cautious_idm keeps larger margins (better TTC/D/PET factors). If ordering does not emerge, tune per §11-R3 — the ranges above are the starting point, and AC-7 is the gate.

### 5.10 Baseline planner parameters (normative)

IDM longitudinal law (both IDM variants), applied to the selected leader (nearest visible actor ahead with `|y_actor − y_ego| < lane_width·0.75` **or** any visible actor ahead whose `|vy| > 0.3` and lateral position is converging on ego's lane — the MOBIL-style cut-in adoption rule; pedestrians in the corridor count as leaders with speed = their `vx` component):

```
s* = s0 + v·T + v·Δv / (2·√(a·b));   accel = a · [ 1 − (v/v0)⁴ − (s*/s)² ]
```

where `s` = bumper gap (center gap − R), `Δv` = closing speed, `v0 = min(target_speed, speed_limit)`.

| Param | idm | cautious_idm |
|---|---|---|
| T (headway) | 1.2 s | 2.2 s |
| s0 (standstill gap) | 2.0 m | 4.0 m |
| a (max accel) | 2.0 m/s² | 1.5 m/s² |
| b (comfortable decel) | 2.5 m/s² | 2.0 m/s² |
| v0 factor | 1.0 × | 0.85 × |

Lateral control (both IDM variants): `steer = clip(0.15·(ego_lane_center_y − y) − 1.2·yaw, ±0.5)`. `constant_velocity`: `Action(accel=0.0, steer=0.0)` always.

---

## 6. Module Breakdown (file-level)

Repository layout: `pyproject.toml`, `src/avsb/…`, `tests/…`, `docs/`, generated outputs in `scenarios/`, `runs/`, `reports/`, `exports/` (all four gitignored). Implementation order = the `#` column; each file lists its public surface. LOC budgets are ceilings (total ≈ 2,900 src + 700 tests).

| # | File | Responsibility | Public surface (signatures) | Depends on | LOC |
|---|---|---|---|---|---|
| 1 | `pyproject.toml` | packaging, `avsb = avsb.cli:main` entry point, deps §7 | — | — | 40 |
| 2 | `src/avsb/schema/io.py` | canonical serialization | `round_floats(obj, ndigits=4)`, `write_yaml(path, model)`, `read_yaml(path, model_cls)`, `write_json(path, model)` | pydantic, yaml | 60 |
| 3 | `src/avsb/schema/scenario.py` | §5.1 models | `ScenarioDefinition`, `Road`, `Environment`, `EgoSpec`, `ActorSpec`, `Phase`, `Trigger`, `InitialState`; `load_scenario(path)`, `load_suite(suite_dir) -> list[ScenarioDefinition]` | io.py | 170 |
| 4 | `src/avsb/schema/trajectory.py` | §5.2 JSONL contract | `TrajectoryHeader`, `TrajectoryRecord`, `TrajectoryLog` (`.read(path)`, `.write(path)`, `.states(actor_id) -> np.ndarray`, `.yaw(actor_id)`, `.accel_cmd()`, `.actor_ids`) | numpy | 150 |
| 5 | `src/avsb/schema/result.py` | §5.4 models | `MetricSet`, `ScenarioResult`, `SuiteSummary` | io.py | 90 |
| 6 | `src/avsb/schema/regmap.py` | §5.5 models | `RegReference`, `RegEntry`, `RegulatoryMapping` | io.py | 50 |
| 7 | `src/avsb/generation/base.py` | shared generator scaffolding | `FamilyGenerator` (ABC: `family: str`, `count: int`, `offset: int`, `sample(rng) -> dict[str,float]`, `build(params, idx, seed) -> ScenarioDefinition`), `generate_family(gen, suite, seed, out_dir) -> list[Path]` | schema | 90 |
| 8 | `src/avsb/generation/cut_in.py` | §5.9 row 1 | `CutInGenerator(FamilyGenerator)` | base | 80 |
| 9 | `src/avsb/generation/pedestrian.py` | §5.9 row 2 (adds the static occluder actor) | `PedOccludedGenerator` | base | 90 |
| 10 | `src/avsb/generation/weather.py` | §5.9 row 3 | `WeatherRampGenerator` | base | 80 |
| 11 | `src/avsb/generation/hard_brake.py` | §5.9 row 4 | `HardBrakeGenerator` | base | 80 |
| 12 | `src/avsb/generation/suite.py` | suite assembly | `SUITES = {"core": [...gen instances...]}`, `generate_suite(suite, seed, root) -> list[Path]` | 8–11 | 60 |
| 13 | `src/avsb/engine/occlusion.py` | visibility | `segment_intersects_rect(p0, p1, cx, cy, half_l, half_w) -> bool`, `visible_actors(ego_xy, actors_state, statics, visibility_m) -> list[int]` | numpy | 80 |
| 14 | `src/avsb/engine/observation.py` | §5.3 dataclasses | `Observation`, `EgoObs`, `ActorObs`, `Action`; `build_observation(...) -> Observation` | occlusion | 110 |
| 15 | `src/avsb/engine/scripted.py` | phase-script execution | `ScriptedActor` (`.step(dt, t, ego_x)`, trigger latching per §5.1 semantics) | schema | 120 |
| 16 | `src/avsb/engine/simulator.py` | main loop | `EGO_WHEELBASE=2.8`, `A_MAX`, `A_MIN`, `STEER_MAX`; `run_scenario(scenario, planner) -> TrajectoryLog`; `run_suite(suite_dir, planners, out_root) -> list[tuple[ScenarioDefinition, str, Path]]` | 13–15, planners | 170 |
| 17 | `src/avsb/planners/base.py` | protocol + registry | `Planner` (Protocol), `Action` re-export, `REGISTRY: dict[str, Callable[[], Planner]]`, `get_planners(name: str) -> dict[str, Planner]` ("all" expands) | observation | 60 |
| 18 | `src/avsb/planners/constant_velocity.py` | null baseline | `ConstantVelocityPlanner` | base | 30 |
| 19 | `src/avsb/planners/idm.py` | both IDM variants (§5.10) | `IdmPlanner(T, s0, a, b, v0_factor, name)`, factory entries `idm`, `cautious_idm`; `select_leader(obs) -> ActorObs | None` | base | 140 |
| 20 | `src/avsb/metrics/geometry.py` | shared per-step arrays | `pairwise_separation(log, scen) -> dict[actor_id, np.ndarray]` (dₐ(k)), `closing_speed(log, scen, actor_id) -> np.ndarray` | trajectory | 90 |
| 21 | `src/avsb/metrics/ttc.py` | M3 | `ttc_min(log, scen) -> tuple[float | None, float | None]` | geometry | 60 |
| 22 | `src/avsb/metrics/pet.py` | M4 grid PET | `pet_min(log, scen, cell=0.5) -> float | None` | numpy | 90 |
| 23 | `src/avsb/metrics/collision.py` | M1, M2 | `min_distance(log, scen)`, `collision_metrics(log, scen) -> (collision, t, delta_v, severity)` | geometry | 80 |
| 24 | `src/avsb/metrics/comfort.py` | M5 | `hard_brake(log, threshold=-4.0) -> (fraction, events)` | trajectory | 40 |
| 25 | `src/avsb/metrics/compute.py` | orchestration | `compute_metrics(log, scen) -> MetricSet` | 21–24 | 60 |
| 26 | `src/avsb/scoring/score.py` | §5.7 | `score_scenario(m: MetricSet) -> tuple[float, str]`, `summarize(results) -> SuiteSummary` | result | 100 |
| 27 | `src/avsb/regmap/regulatory_mapping.yaml` | §5.5 content (9 entries) | data file (packaged via `importlib.resources`) | — | 160 |
| 28 | `src/avsb/regmap/loader.py` | load + validate | `load_mapping() -> RegulatoryMapping` | regmap schema | 30 |
| 29 | `src/avsb/report/plots.py` | matplotlib Agg PNGs | `bev_plot(log, scen, out_png)` (trajectories, disc footprints at d_min instant, occluder rects), `ttc_curve(log, scen, out_png)`, `metric_hist(results, field, out_png)`, `leaderboard_bars(summary, out_png)` — module sets `matplotlib.use("Agg")` before pyplot import | matplotlib | 220 |
| 30 | `src/avsb/report/templates/index.html.j2` | single-page report: leaderboard table, family breakdown, worst-case gallery, distributions, regmap table + disclaimer, methodology footer (metric formulas) | Jinja2 template, inline CSS, no external assets | — | 180 |
| 31 | `src/avsb/report/render.py` | build report | `build_report(suite, runs_root, out_dir, screenshots_dir="docs/screenshots") -> Path` (renders index.html, writes plots/, copies 3 key PNGs §9) | 26–30 | 160 |
| 32 | `src/avsb/export/xosc.py` | simplified OSC export | `export_scenario(scen, out_path)` (cut_in/hard_brake only, else `UnsupportedFamilyError`), `export_suite(suite_dir, family, out_dir) -> list[Path]` | xml.etree | 140 |
| 33 | `src/avsb/adapters/protocol.py` | §5.8 stub | `TrajectorySource` (Protocol, no impls) | schema | 25 |
| 34 | `src/avsb/cli.py` | argparse CLI | `main(argv=None) -> int`; subcommands `generate`, `run`, `report`, `export-xosc` per §2; prints one summary line per stage | all | 160 |
| 35 | `tests/…` (7 files, §10) | test plan | — | pytest | 700 |

Path conventions (used by CLI defaults, all relative to CWD): scenarios → `scenarios/{suite}/{family}/{scenario_id}.yaml`; logs/results → `runs/{suite}/{planner}/…`; report → `reports/{suite}/`; exports → `exports/xosc/`.

---

## 7. Dependencies (pinned, justified)

`pyproject.toml` `[project] requires-python = ">=3.11"`; runtime:

| Package | Pin | Justification |
|---|---|---|
| `pydantic` | `>=2.7,<3` | v2 API (`model_dump`, `model_validate`); the schemas are the product, so validation rigor is non-negotiable. `<3` guards API drift. |
| `numpy` | `>=1.26,<3` | vectorized metric computation; 1.26+ has py3.11 ARM wheels; `<3` allows numpy 2.x which is current on macOS ARM. |
| `PyYAML` | `>=6.0.1,<7` | scenario + regmap serialization via `safe_load`/`safe_dump` only. |
| `Jinja2` | `>=3.1.3,<4` | HTML templating; 3.1.3+ fixes known sandbox CVEs. |
| `matplotlib` | `>=3.8,<4` | BEV/curve/histogram PNGs; Agg backend is bundled, headless-safe. |

Dev extra `[project.optional-dependencies] dev = ["pytest>=8,<9"]`. Explicitly excluded: `typer`/`click` (argparse suffices — fewer deps beats nicer `--help`), `scipy` (nothing here needs it), `pandas` (plain dicts/numpy suffice), `plotly` (report must be dependency-free static HTML).

---

## 8. Acceptance Criteria

Each is `command → observable expected output`. All run from repo root in a fresh venv after `pip install -e ".[dev]"`, with no network available at runtime.

1. `pip install -e ".[dev]" && avsb --help` → exits 0; help lists exactly the subcommands `generate`, `run`, `report`, `export-xosc`.
2. `avsb generate --suite core --seed 42` → creates exactly **60** YAML files under `scenarios/core/` (16 `cut_in`, 16 `ped_occluded`, 14 `weather_ramp`, 14 `hard_brake`), prints the count, exits 0.
3. `avsb generate --suite core --seed 42` run **twice** into two directories → `diff -r` of the two trees is empty (**byte-identical** scenario files); with `--seed 43` → at least one file differs.
4. `python -c "from avsb.schema.scenario import load_suite; s=load_suite('scenarios/core'); print(len(s))"` → prints `60`, no validation errors; hand-corrupting one YAML field (e.g. `speed_mps: "fast"`) → `load_scenario` raises `pydantic.ValidationError` naming the field.
5. `avsb run --suite core --planner all` → produces 180 `.jsonl` logs + 180 `.result.json` files under `runs/core/{constant_velocity,idm,cautious_idm}/`; exits 0; wall time < 90 s.
6. Re-running `avsb run` for one (scenario, planner) pair twice → the two `.jsonl` files are byte-identical (deterministic engine).
7. **Leaderboard ordering (the meaningfulness gate):** in `reports/core/summary.json`, `composite(cautious_idm) > composite(idm) > composite(constant_velocity)`; `constant_velocity` has ≥ 1 collision in `hard_brake` and ≥ 1 in `cut_in`; `cautious_idm` total collisions < `constant_velocity` total collisions.
8. `avsb report --suite core --out reports/core/` → `reports/core/index.html` exists and contains the leaderboard table with `cautious_idm` ranked above `constant_velocity`, ≥ 6 PNGs in `reports/core/plots/`, the regulatory mapping table, and the verbatim informative-only disclaimer; `docs/screenshots/` contains the 3 named PNGs of §9.
9. `avsb export-xosc --suite core --family cut_in --out exports/xosc/` → 16 `.xosc` files; each parses with `xml.etree.ElementTree.parse` and contains `OpenSCENARIO`, `Storyboard`, and a `LaneChangeAction` element; `--family weather_ramp` → clean error message "family not supported for export", exit code 2.
10. `pytest -q` → all tests pass, including `test_ttc_hand_computed` asserting `TTC == 43.5/8.0 == 5.4375` for the §5.6 worked example.
11. `time (avsb generate --suite core --seed 42 && avsb run --suite core --planner all && avsb report --suite core --out reports/core/)` → total < **120 s** on a laptop, and no step attempts any network access (all code paths use only local files; verified by inspection — no `urllib`/`requests`/socket imports outside tests).

---

## 9. Demo Script

Exact commands (fresh clone, ~90 s wall time):

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
avsb generate --suite core --seed 42
avsb run --suite core --planner all
avsb report --suite core --out reports/core/
avsb export-xosc --suite core --family cut_in --out exports/xosc/
open reports/core/index.html
```

**60-second narration** (spoken while scrolling the report):

> "This is a system-agnostic AV safety benchmark — any stack that can produce trajectory logs in this JSONL format can be scored; the simulator is just one producer. *(Open leaderboard.)* Three baseline planners over 60 procedurally generated, seeded scenarios in four families. The ordering is the point: the cautious IDM planner beats standard IDM beats constant-velocity — the benchmark discriminates safety behavior, it isn't noise. *(Scroll to worst-case gallery, click/point at the worst cut-in.)* Here's the worst cut-in for the mid-tier planner: bird's-eye view, ego in blue, cutter in red, footprints drawn at the moment of closest approach — a 0.4-meter near-miss. *(Point at TTC curve.)* And the time-to-collision trace for the same run: it dips under one second right at the cut-in trigger, which is exactly what drives the score down. Every metric is computed from the logs with formulas documented in the report footer — TTC, PET, distance margin, delta-v severity, hard-braking rate. *(Scroll to regulatory table.)* Finally, every metric and scenario family maps — informatively, no certification claims — to ISO 26262, SOTIF, UL 4600, and the EU AI Act, from a machine-readable YAML. And it exports simplified OpenSCENARIO. All offline, deterministic, under two minutes."

**PNGs copied to `docs/screenshots/`** by `avsb report` (fixed names, overwritten each run):

1. `leaderboard.png` — composite + per-family bar chart (`leaderboard_bars`).
2. `worst_cutin_bev.png` — BEV plot of the lowest-scoring `cut_in` scenario for planner `idm`.
3. `worst_cutin_ttc.png` — TTC-over-time curve for that same run.

---

## 10. Test Plan

`tests/` layout (pytest, no network, `tmp_path` for all outputs; total ≈ 700 LOC):

- **`tests/data/example_cut_in.yaml`** — the verbatim §5.1 example (fixture).
- **`test_schema.py`** — round-trip: load fixture → dump → load → equal models; `extra="forbid"` rejects unknown fields; bad types raise `ValidationError`; `round_floats` idempotence.
- **`test_generation.py`** — (a) determinism: `generate_suite("core", 42, dirA)` and `dirB` → identical file lists and identical bytes per file; (b) seed sensitivity: seed 43 differs; (c) counts per family = 16/16/14/14; (d) every generated file validates and every sampled parameter lies inside its §5.9 range.
- **`test_engine.py`** — (a) bicycle integration: ego with `accel=0, steer=0, v=10` for 10 steps → `x == 10·0.1·10 = 10.0` (Euler, exact), `y == 0`; (b) constant `steer=0.1` → yaw after k steps equals the closed-form Euler sum; (c) trigger latching: an `ego_gap` phase fires once and stays active; (d) friction clamp: with `friction=0.3`, a commanded `accel=-8` logs `accel_cmd == -0.3·9.81` (±1e-9); (e) occlusion: pedestrian behind the occluder rect is absent from `obs.actors`, present once line-of-sight clears.
- **`test_metrics.py`** — (a) **hand-computed TTC** (§5.6 worked example): build a 2-record synthetic log, assert `ttc_min == 5.4375`; (b) diverging actors (`c < 0`) → `ttc_min is None`; (c) collision: two discs overlapping at step k → `collision=True`, `collision_t_s == k·0.1`, delta-v matches `(m_a/(m_e+m_a))·‖v_rel‖` hand value (equal 1500 kg masses, `‖v_rel‖=8` → `delta_v == 4.0`, severity 2); (d) PET: scripted crossing where actor leaves a cell at t=2.0 and ego enters it at t=3.5 → `pet_min == 1.5 ± dt`; (e) hard-brake: synthetic `accel_cmd` with two −5 m/s² bursts → `events == 2`, fraction exact.
- **`test_planners.py`** — (a) IDM behind a slow lead closes to a stable gap without collision in a 30 s synthetic run; (b) cautious_idm equilibrium gap > idm equilibrium gap at same speed; (c) constant_velocity always returns `Action(0.0, 0.0)`; (d) MOBIL-style adoption: a laterally converging actor with `|vy|>0.3` is selected as leader before entering ego's lane band.
- **`test_export.py`** — export the fixture → `ElementTree.parse` succeeds; root tag `OpenSCENARIO`; contains `LaneChangeAction`; unsupported family raises `UnsupportedFamilyError`.
- **`test_e2e.py`** — end-to-end smoke on a reduced suite (monkeypatch family counts to 2 each = 8 scenarios): `generate → run(all) → report` in `tmp_path`; assert `index.html` exists, `summary.json` parses as `SuiteSummary`, and composite ordering `cautious_idm > constant_velocity` holds even on the reduced suite (idm middle rank asserted only in the full-suite AC-7, since 8 scenarios may be noisy).

---

## 11. Risks & Fallbacks

- **R1 — matplotlib headless/CI failures.** Mitigation: `matplotlib.use("Agg")` is executed in `report/plots.py` **before** any `pyplot` import, unconditionally; no `plt.show()` anywhere; PNGs written with explicit `dpi=120`. This also keeps macOS-ARM runs GUI-free.
- **R2 — runtime budget (< 2 min).** Envelope: 60 scenarios × 3 planners × ≤ 300 steps × ≤ 4 actors ≈ 2×10⁵ engine steps — Python-loop-feasible in seconds. The real cost is matplotlib (~180 potential figures). Mitigation: render BEV/TTC plots **only** for the worst scenario per (family, planner) (12 + histograms + leaderboard ≈ 20 PNGs). Fallback if still slow: drop per-planner worst-cases to per-family (5 PNGs).
- **R3 — planner ordering does not emerge (AC-7 fails).** Diagnosis order: (1) constant_velocity not crashing → tighten `hard_brake` gaps (12–25 m) and raise `brake_decel` floor to −5; (2) idm ≈ cautious_idm → widen the headway spread (T: 1.0 vs 2.5 s) and lower cautious `v0_factor` to 0.8 so cautious buys margin at the cost of nothing the score measures; (3) cautious_idm scoring *below* idm via the comfort term → comfort weight is capped at 0.15 by design, but if needed reduce cautious `b` to 1.8 so it brakes earlier and softer. Scenario ranges in §5.9 and planner params in §5.10 are the tuning surface; the score formula §5.7 is frozen.
- **R4 — float nondeterminism across platforms breaking byte-identity.** Mitigation: all randomness flows through explicitly seeded `default_rng`; all serialized floats rounded to 4 decimals at write time; no dict-ordering dependence (`sort_keys=True`, actor order fixed by scenario definition). Byte-identity is claimed per-platform (AC-3/AC-6 run on one machine), not cross-platform — state this in the README section the implementer adds nowhere (do not touch README in v1).
- **R5 — PET grid cost or degeneracy.** 0.5 m cells over a 400×~10 m corridor is bounded by *occupied* cells only (dict-based, no dense grid). If PET is `null` too often to be meaningful in a family, that is acceptable — scoring already treats `null` as ∞ (`f_pet = 1`), and the report annotates "no shared conflict zone".
- **R6 — pydantic v2 / numpy 2 API drift.** Pins in §7 bound both; only stable APIs are used (`model_dump`, `model_validate`, `default_rng`).
- **R7 — occlusion geometry edge cases** (segment grazing rectangle corner). Mitigation: slab test with inclusive bounds; the unit test in `test_engine.py(e)` pins behavior; a false-positive occlusion only makes scenarios *harder*, which is safe for the benchmark's claims.

---

## 12. Deferred (v2)

- **CARLA adapter** — a `TrajectorySource` implementation (§5.8) that runs scenario definitions in CARLA and emits conforming JSONL; the metrics/scoring/report layers are reused unchanged.
- **Real-log adapters** — nuScenes / Waymo Open Dataset converters to the trajectory JSONL contract, plus map-frame alignment; enables scoring recorded drives, not just simulations.
- **OpenSCENARIO parsing / OSC 2.0** — import path (parse → `ScenarioDefinition`) and OSC 2.0 authoring; v1 remains export-only.
- **Hosted leaderboard** — static-site publication of `reports/` with submitted-log validation (schema check + replay verification) for third-party entries.
- **Additional families** — unusual road users, compounding failures (sensor dropout during crossing), condition ramps beyond the weather ramp (lighting transitions).
- **Richer dynamics & sensing** — dynamic bicycle/tire model above 20 m/s, probabilistic sensor/noise models, latency injection.
- **ML baselines** — a learned planner behind the same `Planner` protocol, demonstrating evaluation of a non-analytic stack.
