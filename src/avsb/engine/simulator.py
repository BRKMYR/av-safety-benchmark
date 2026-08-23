"""Main simulation loop (spec 5.3, 4).

Kinematic bicycle ego (explicit Euler), scripted actors, visibility filter,
friction-aware acceleration clamp. Writes one canonical JSONL log per run.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from avsb.engine.observation import Action, build_observation
from avsb.engine.scripted import ScriptedActor
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryHeader, TrajectoryLog

EGO_WHEELBASE = 2.8
A_MAX = 3.0
A_MIN = -8.0
STEER_MAX = 0.5
_G = 9.81


def _clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _ramped(scen: ScenarioDefinition, t: float) -> tuple[float, float]:
    """Return (visibility_m, friction) linearly ramped over the scenario."""
    if scen.duration_s <= 0.0:
        u = 0.0
    else:
        u = _clamp(t / scen.duration_s, 0.0, 1.0)
    vis = _lerp(
        scen.environment.visibility_start_m, scen.environment.visibility_end_m, u
    )
    fri = _lerp(scen.environment.friction_start, scen.environment.friction_end, u)
    return vis, fri


def _friction_a_min(friction: float) -> float:
    return max(A_MIN, -friction * _G)


class _EgoState:
    __slots__ = ("x", "y", "yaw", "speed", "accel_prev")

    def __init__(self, x: float, y: float, yaw: float, speed: float) -> None:
        self.x = x
        self.y = y
        self.yaw = yaw
        self.speed = speed
        self.accel_prev = 0.0

    def integrate(
        self, action: Action, friction: float, dt: float
    ) -> tuple[float, float]:
        a_min = _friction_a_min(friction)
        a = _clamp(float(action.accel), a_min, A_MAX)
        s = _clamp(float(action.steer), -STEER_MAX, STEER_MAX)
        v = self.speed
        # Kinematic bicycle, explicit Euler.
        new_v = max(0.0, v + a * dt)
        new_yaw = self.yaw + (v / EGO_WHEELBASE) * math.tan(s) * dt
        new_x = self.x + v * math.cos(self.yaw) * dt
        new_y = self.y + v * math.sin(self.yaw) * dt
        self.x = new_x
        self.y = new_y
        self.yaw = new_yaw
        self.speed = new_v
        self.accel_prev = a
        return a, s


def run_scenario(scenario: ScenarioDefinition, planner) -> TrajectoryLog:
    """Run one scenario against one planner; return an in-memory TrajectoryLog."""
    dt = float(scenario.dt_s)
    n = scenario.n_steps
    actor_ids = ["ego"] + [a.actor_id for a in scenario.actors]

    states: dict[str, np.ndarray] = {
        aid: np.zeros((n, 5), dtype=float) for aid in actor_ids
    }
    yaws: dict[str, np.ndarray] = {aid: np.zeros(n, dtype=float) for aid in actor_ids}
    ego_accel = np.zeros(n, dtype=float)
    ego_steer = np.zeros(n, dtype=float)

    scripted = [ScriptedActor(a) for a in scenario.actors]
    ego = _EgoState(
        x=scenario.ego.initial.x_m,
        y=scenario.ego.initial.y_m,
        yaw=scenario.ego.initial.yaw_rad,
        speed=scenario.ego.initial.speed_mps,
    )
    planner.reset(scenario)

    lane_width = scenario.road.lane_width_m
    ego_lane_center_y = (scenario.ego.lane + 0.5) * lane_width

    for k in range(n):
        t = round(k * dt, 6)
        visibility, friction = _ramped(scenario, t)

        # Log current state at step k (before integration).
        states["ego"][k, 0] = t
        states["ego"][k, 1] = ego.x
        states["ego"][k, 2] = ego.y
        states["ego"][k, 3] = ego.speed * math.cos(ego.yaw)
        states["ego"][k, 4] = ego.speed * math.sin(ego.yaw)
        yaws["ego"][k] = ego.yaw
        for a in scripted:
            states[a.actor_id][k, 0] = t
            states[a.actor_id][k, 1] = a.x
            states[a.actor_id][k, 2] = a.y
            states[a.actor_id][k, 3] = a.vx
            states[a.actor_id][k, 4] = a.vy
            yaws[a.actor_id][k] = a.yaw

        # Build observation.
        actor_records = []
        static_rects = []
        for a in scripted:
            actor_records.append(
                (
                    a.actor_id,
                    a.kind,
                    a.x,
                    a.y,
                    a.yaw,
                    a.vx,
                    a.vy,
                    a.length,
                    a.width,
                )
            )
            if a.kind == "static":
                static_rects.append((a.x, a.y, a.length / 2.0, a.width / 2.0))

        obs = build_observation(
            t=t,
            dt=dt,
            ego_state=(ego.x, ego.y, ego.yaw, ego.speed, ego.accel_prev),
            actor_records=actor_records,
            static_rects=static_rects,
            lane_width=lane_width,
            n_lanes=scenario.road.n_lanes,
            ego_lane_center_y=ego_lane_center_y,
            speed_limit=scenario.road.speed_limit_mps,
            target_speed=scenario.ego.target_speed_mps,
            visibility_m=visibility,
            friction=friction,
        )

        action = planner.step(obs)
        if not isinstance(action, Action):
            action = Action(accel=float(action.accel), steer=float(action.steer))

        a_used, s_used = ego.integrate(action, friction, dt)
        ego_accel[k] = a_used
        ego_steer[k] = s_used

        # Advance scripted actors to state at t+dt. Use time t (start of step)
        # for trigger evaluation (spec 5.1: "phase STARTS when its trigger fires")
        # and post-integration ego.x so triggers see the freshest ego position.
        for a in scripted:
            a.step(dt, t, ego.x)

    header = TrajectoryHeader(
        scenario_id=scenario.scenario_id,
        planner=getattr(planner, "name", "unknown"),
        dt_s=dt,
        n_steps=n,
        actor_ids=actor_ids,
        created="2026-01-01T00:00:00Z",  # constant timestamp: byte-identity across runs
    )
    return TrajectoryLog.from_arrays(
        header=header,
        states=states,
        yaws=yaws,
        ego_accel_cmd=ego_accel,
        ego_steer_cmd=ego_steer,
    )


def run_suite(
    suite_dir: Path | str,
    planners: dict[str, object],
    out_root: Path | str,
) -> list[tuple[ScenarioDefinition, str, Path]]:
    """Run every scenario under suite_dir against every planner; write JSONL logs.

    Returns list of (scenario, planner_name, log_path). Iterates scenarios in
    scenario_id order.
    """
    from avsb.schema.scenario import load_suite as _load_suite

    scenarios = _load_suite(suite_dir)
    out_root = Path(out_root)
    results: list[tuple[ScenarioDefinition, str, Path]] = []
    for scen in scenarios:
        for name, planner in planners.items():
            log = run_scenario(scen, planner)
            log_path = out_root / scen.suite / name / f"{scen.scenario_id}.jsonl"
            log.write(log_path)
            results.append((scen, name, log_path))
    return results
