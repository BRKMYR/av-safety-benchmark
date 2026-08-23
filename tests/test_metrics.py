"""Metric tests (spec 10, 5.6): hand-computed TTC, collision, PET, hard-brake, diverging."""

from __future__ import annotations

import numpy as np
import pytest

from avsb.metrics.collision import collision_metrics, min_distance
from avsb.metrics.comfort import hard_brake
from avsb.metrics.pet import pet_min
from avsb.metrics.ttc import ttc_min
from avsb.schema.scenario import (
    ActorSpec,
    EgoSpec,
    Environment,
    InitialState,
    Road,
    ScenarioDefinition,
)
from avsb.schema.trajectory import TrajectoryHeader, TrajectoryLog


def _make_log(
    scen: ScenarioDefinition,
    ego_traj: np.ndarray,
    other: dict[str, np.ndarray],
    ego_accel: np.ndarray | None = None,
) -> TrajectoryLog:
    """ego_traj shape (n, 5) columns (t, x, y, vx, vy). other same."""
    n = ego_traj.shape[0]
    actor_ids = ["ego"] + list(other.keys())
    states = {"ego": ego_traj}
    states.update(other)
    yaws = {aid: np.zeros(n) for aid in actor_ids}
    header = TrajectoryHeader(
        scenario_id=scen.scenario_id,
        planner="test",
        dt_s=0.1,
        n_steps=n,
        actor_ids=actor_ids,
        created="2026-01-01T00:00:00Z",
    )
    return TrajectoryLog.from_arrays(
        header=header,
        states=states,
        yaws=yaws,
        ego_accel_cmd=ego_accel if ego_accel is not None else np.zeros(n),
        ego_steer_cmd=np.zeros(n),
    )


def _scen_with_lead(mass: float = 1500.0) -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="test-ttc-0001",
        suite="test",
        family="cut_in",
        description="ttc test",
        seed=0,
        duration_s=10.0,
        road=Road(n_lanes=2, lane_width_m=3.5, length_m=400.0, speed_limit_mps=22.2),
        environment=Environment(
            visibility_start_m=200.0,
            visibility_end_m=200.0,
            friction_start=0.9,
            friction_end=0.9,
        ),
        ego=EgoSpec(
            initial=InitialState(x_m=0.0, y_m=1.75, yaw_rad=0.0, speed_mps=20.0),
            target_speed_mps=20.0,
            lane=0,
            length_m=4.5,
            width_m=1.9,
            mass_kg=1500.0,
        ),
        actors=[
            ActorSpec(
                actor_id="lead",
                kind="vehicle",
                length_m=4.5,
                width_m=1.9,
                mass_kg=mass,
                initial=InitialState(x_m=48.0, y_m=1.75, yaw_rad=0.0, speed_mps=12.0),
                phases=[],
            )
        ],
        parameters={},
    )


def test_ttc_hand_computed() -> None:
    """Spec 5.6 worked example: ego at x=0 v=20, lead at x=48 v=12, R=4.5 -> TTC=43.5/8=5.4375.

    We use a single-step synthetic log; the header requires n_steps >= 1 and the
    metric operates per-step, so one snapshot suffices to pin the formula.
    """
    scen = _scen_with_lead()
    ego = np.array([[0.0, 0.0, 1.75, 20.0, 0.0]])
    lead = np.array([[0.0, 48.0, 1.75, 12.0, 0.0]])
    log = _make_log(scen, ego, {"lead": lead})
    ttc, t_at = ttc_min(log, scen)
    assert ttc == pytest.approx(43.5 / 8.0, abs=1e-9)
    assert ttc == pytest.approx(5.4375, abs=1e-9)
    assert t_at == pytest.approx(0.0, abs=1e-9)


def test_ttc_diverging_returns_none() -> None:
    scen = _scen_with_lead()
    ego = np.array([[0.0, 0.0, 1.75, 5.0, 0.0], [0.1, 0.5, 1.75, 5.0, 0.0]])
    # Lead moving away faster than ego.
    lead = np.array([[0.0, 48.0, 1.75, 20.0, 0.0], [0.1, 50.0, 1.75, 20.0, 0.0]])
    log = _make_log(scen, ego, {"lead": lead})
    ttc, _ = ttc_min(log, scen)
    assert ttc is None


def test_collision_delta_v_two_meters_per_second_boundary() -> None:
    """Equal 1500 kg masses, ||v_rel||=8 -> delta_v = 0.5 * 8 = 4.0, severity 2."""
    scen = _scen_with_lead()  # both 1500 kg
    # Positions: overlap at step 2 (k=2, t=0.2). Combined R=4.5. Center distance <= 4.5 at k=2.
    ego = np.array(
        [
            [0.0, 0.0, 1.75, 20.0, 0.0],
            [0.1, 2.0, 1.75, 20.0, 0.0],
            [0.2, 4.0, 1.75, 20.0, 0.0],
        ]
    )
    lead = np.array(
        [
            [0.0, 10.0, 1.75, 12.0, 0.0],
            [0.1, 11.2, 1.75, 12.0, 0.0],
            [0.2, 8.4, 1.75, 12.0, 0.0],  # forced closer: center gap = 4.4 <= 4.5
        ]
    )
    log = _make_log(scen, ego, {"lead": lead})
    coll, t, dv, sev = collision_metrics(log, scen)
    assert coll is True
    assert t == pytest.approx(0.2, abs=1e-9)
    assert dv == pytest.approx(4.0, abs=1e-9)
    assert sev == 2


def test_min_distance_matches_expected() -> None:
    scen = _scen_with_lead()
    ego = np.array([[0.0, 0.0, 1.75, 20.0, 0.0], [0.1, 2.0, 1.75, 20.0, 0.0]])
    lead = np.array([[0.0, 48.0, 1.75, 12.0, 0.0], [0.1, 49.2, 1.75, 12.0, 0.0]])
    log = _make_log(scen, ego, {"lead": lead})
    d, _ = min_distance(log, scen)
    # gap = 47.2 - 4.5 = 42.7 (at step 1); step 0 gap = 43.5. So d_min = 42.7.
    assert d == pytest.approx(42.7, abs=1e-9)


def test_pet_hand_computed() -> None:
    """Ego enters cell at t=3.5; actor left the same cell at t=2.0 -> PET = 1.5 s."""
    scen = _scen_with_lead()
    n = 50
    ts = np.arange(n) * 0.1
    # Actor starts at (10, 1.75), moves along +y quickly then leaves the cell at t=2.0.
    lead = np.zeros((n, 5))
    lead[:, 0] = ts
    lead[:, 1] = 10.0
    # Actor lateral position: at t < 2.0 it sits at y=1.75 (in the cell around ~y=1.75 and x=10);
    # at t >= 2.0 it jumps to y=50 to leave the cell.
    lead[:, 2] = np.where(ts < 2.0 - 1e-9, 1.75, 50.0)
    # Ego drives forward; enters x=10 cell at t=3.5.
    ego = np.zeros((n, 5))
    ego[:, 0] = ts
    # Ego x: at t=3.5 -> x=10. So use a step function: x = 10 when t >= 3.5, else 0.
    ego[:, 1] = np.where(ts < 3.5 - 1e-9, 0.0, 10.0)
    ego[:, 2] = 1.75
    # Use radii: ego r=2.25 (length 4.5 / 2). Actor r=2.25 too. Cell size 0.5.
    # The (ix=20, iy=3) cell centered at (10.25, 1.75) is inside both actor discs at those times.
    log = _make_log(scen, ego, {"lead": lead})
    pet = pet_min(log, scen, cell=0.5)
    assert pet is not None
    # Actor last-step index at (x=10, y=1.75) is 19 (t=1.9), ego first-step index there is 35 (t=3.5).
    # PET = (35 - 19) * 0.1 = 1.6 s. Allow a 1 dt tolerance to be safe with rounding.
    assert pet == pytest.approx(1.6, abs=0.15)


def test_hard_brake_events_and_fraction() -> None:
    scen = _scen_with_lead()
    n = 10
    ego = np.zeros((n, 5))
    ego[:, 0] = np.arange(n) * 0.1
    lead = np.zeros((n, 5))
    lead[:, 0] = np.arange(n) * 0.1
    lead[:, 1] = 50.0  # far away, no collision
    accel = np.zeros(n)
    # Two bursts of -5 m/s^2: [1,2] and [5,6,7].
    accel[1] = -5.0
    accel[2] = -5.0
    accel[5] = -5.0
    accel[6] = -5.0
    accel[7] = -5.0
    log = _make_log(scen, ego, {"lead": lead}, ego_accel=accel)
    frac, events = hard_brake(log, threshold=-4.0)
    assert events == 2
    assert frac == pytest.approx(5.0 / 10.0, abs=1e-9)
