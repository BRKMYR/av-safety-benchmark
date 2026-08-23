"""Engine tests (spec 10): bicycle integration, trigger latching, friction clamp, occlusion."""

from __future__ import annotations

import math

import pytest

from avsb.engine.observation import Action
from avsb.engine.occlusion import segment_intersects_rect, visible_actors
from avsb.engine.simulator import EGO_WHEELBASE, run_scenario
from avsb.schema.scenario import (
    ActorSpec,
    EgoSpec,
    Environment,
    InitialState,
    Phase,
    Road,
    ScenarioDefinition,
    Trigger,
)


def _bare_scenario(**overrides) -> ScenarioDefinition:
    kw = dict(
        scenario_id="test-scen-0001",
        suite="test",
        family="cut_in",
        description="test",
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
            initial=InitialState(x_m=0.0, y_m=1.75, yaw_rad=0.0, speed_mps=10.0),
            target_speed_mps=10.0,
            lane=0,
            length_m=4.5,
            width_m=1.9,
            mass_kg=1500.0,
        ),
        actors=[],
        parameters={},
    )
    kw.update(overrides)
    return ScenarioDefinition(**kw)


class _FixedPlanner:
    name = "fixed"

    def __init__(self, accel: float, steer: float) -> None:
        self._accel = accel
        self._steer = steer

    def reset(self, scenario) -> None:
        return None

    def step(self, obs) -> Action:
        return Action(accel=self._accel, steer=self._steer)


def test_bicycle_zero_accel_zero_steer() -> None:
    scen = _bare_scenario(duration_s=8.0)  # 81 steps at 10 Hz
    log = run_scenario(scen, _FixedPlanner(0.0, 0.0))
    ego = log.states("ego")
    # After 80 dt at v=10: x should be 10 * 0.1 * 80 = 80.0. Log records
    # pre-integration state so ego[80] is the state at t=8.0 after 80 integrations.
    assert ego[-1, 1] == pytest.approx(80.0, abs=1e-9)
    assert ego[-1, 2] == pytest.approx(1.75, abs=1e-9)


def test_bicycle_constant_steer_yaw_matches_euler_sum() -> None:
    scen = _bare_scenario(duration_s=8.0)
    steer = 0.1
    log = run_scenario(scen, _FixedPlanner(0.0, steer))
    yaws = log.yaw("ego")
    # Closed-form Euler: yaw_{k+1} = yaw_k + (v/L) * tan(steer) * dt, v = 10.
    dt = 0.1
    v = 10.0
    expected = 0.0
    for _ in range(len(yaws) - 1):
        expected += (v / EGO_WHEELBASE) * math.tan(steer) * dt
    assert yaws[-1] == pytest.approx(expected, abs=1e-9)


def test_trigger_latching_ego_gap() -> None:
    # Cutter starts behind (positive x offset from ego), triggers on ego_gap<=X.
    scen = _bare_scenario(
        actors=[
            ActorSpec(
                actor_id="mover",
                kind="vehicle",
                length_m=4.5,
                width_m=1.9,
                mass_kg=1500.0,
                initial=InitialState(x_m=5.0, y_m=1.75, yaw_rad=0.0, speed_mps=0.0),
                phases=[
                    Phase(
                        trigger=Trigger(type="time", at_time_s=0.0),
                        accel_mps2=0.0,
                        target_speed_mps=0.0,
                        target_y_m=None,
                        lateral_speed_mps=0.0,
                    ),
                    Phase(
                        trigger=Trigger(type="ego_gap", gap_m=1.0),
                        accel_mps2=2.0,
                        target_speed_mps=10.0,
                        target_y_m=None,
                        lateral_speed_mps=0.0,
                    ),
                ],
            )
        ]
    )
    log = run_scenario(scen, _FixedPlanner(0.0, 0.0))
    mover = log.states("mover")
    # Ego closes at v=10 m/s starting 5 m behind: (self.x - ego.x)=5, then 4, ...
    # Trigger fires when 5 - 10*t <= 1 -> t >= 0.4 s (step 4).
    # After trigger, mover accelerates to 10; check that final vx is not zero.
    assert mover[-1, 3] > 0.5


def test_friction_clamp_saturates_deceleration() -> None:
    # Set friction to 0.3; commanded accel = -8 should clamp to -0.3 * 9.81.
    scen = _bare_scenario(
        environment=Environment(
            visibility_start_m=200.0,
            visibility_end_m=200.0,
            friction_start=0.3,
            friction_end=0.3,
        ),
        duration_s=8.0,
    )
    log = run_scenario(scen, _FixedPlanner(-8.0, 0.0))
    assert log.accel_cmd()[0] == pytest.approx(-0.3 * 9.81, abs=1e-9)


def test_occlusion_hides_actor_behind_static_rect() -> None:
    ego_xy = (0.0, 0.0)
    actors = [
        ("mover", "vehicle", 20.0, 0.0, 2.25, 0.95),
    ]
    statics = [(10.0, 0.0, 3.0, 2.0)]
    # Should be blocked by rect at (10, 0).
    visible = visible_actors(ego_xy, actors, statics, visibility_m=100.0)
    assert visible == []
    # Move mover to be off to the side; segment no longer intersects rect.
    actors2 = [("mover", "vehicle", 20.0, 10.0, 2.25, 0.95)]
    visible2 = visible_actors(ego_xy, actors2, statics, visibility_m=100.0)
    assert visible2 == [0]


def test_segment_intersects_rect_edge_cases() -> None:
    assert segment_intersects_rect((0, 0), (10, 0), 5, 0, 1, 1) is True
    assert segment_intersects_rect((0, 5), (10, 5), 5, 0, 1, 1) is False
    # Endpoint inside.
    assert segment_intersects_rect((5, 0), (5, 0), 5, 0, 1, 1) is True
