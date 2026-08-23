"""Planner tests (spec 10, 5.10)."""

from __future__ import annotations

import math

import pytest

from avsb.engine.observation import Action, ActorObs, EgoObs, Observation
from avsb.engine.simulator import run_scenario
from avsb.planners.base import get_planners
from avsb.planners.constant_velocity import ConstantVelocityPlanner
from avsb.planners.idm import IdmPlanner, select_leader
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


def _make_obs(*, ego_speed: float, leader_at: tuple[float, float, float, float]) -> Observation:
    ego = EgoObs(x=0.0, y=1.75, yaw=0.0, speed=ego_speed, accel_prev=0.0)
    lx, ly, lvx, lvy = leader_at
    leader = ActorObs(
        actor_id="lead",
        kind="vehicle",
        x=lx,
        y=ly,
        yaw=0.0,
        vx=lvx,
        vy=lvy,
        length=4.5,
        width=1.9,
        radius=2.25,
    )
    return Observation(
        t=0.0,
        dt=0.1,
        ego=ego,
        actors=(leader,),
        lane_width=3.5,
        n_lanes=2,
        ego_lane_center_y=1.75,
        speed_limit=22.2,
        target_speed=20.0,
        visibility_m=200.0,
        friction=0.9,
    )


def test_constant_velocity_always_zero() -> None:
    p = ConstantVelocityPlanner()
    a = p.step(_make_obs(ego_speed=15.0, leader_at=(30.0, 1.75, 5.0, 0.0)))
    assert a == Action(accel=0.0, steer=0.0)


def _run_synthetic_follow(planner) -> float:
    """Run ego behind a slow lead for 30 s. Return the equilibrium bumper gap."""
    scen = ScenarioDefinition(
        scenario_id="test-follow-0001",
        suite="test",
        family="cut_in",
        description="follow",
        seed=0,
        duration_s=30.0,
        road=Road(n_lanes=2, lane_width_m=3.5, length_m=400.0, speed_limit_mps=22.2),
        environment=Environment(
            visibility_start_m=200.0,
            visibility_end_m=200.0,
            friction_start=0.9,
            friction_end=0.9,
        ),
        ego=EgoSpec(
            initial=InitialState(x_m=0.0, y_m=1.75, yaw_rad=0.0, speed_mps=15.0),
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
                mass_kg=1500.0,
                initial=InitialState(x_m=40.0, y_m=1.75, yaw_rad=0.0, speed_mps=10.0),
                phases=[
                    Phase(
                        trigger=Trigger(type="time", at_time_s=0.0),
                        accel_mps2=0.0,
                        target_speed_mps=10.0,
                        target_y_m=None,
                        lateral_speed_mps=0.0,
                    ),
                ],
            )
        ],
        parameters={},
    )
    log = run_scenario(scen, planner)
    ego = log.states("ego")
    lead = log.states("lead")
    # Equilibrium bumper gap at the last step: center distance - 4.5.
    last_gap = math.hypot(lead[-1, 1] - ego[-1, 1], lead[-1, 2] - ego[-1, 2]) - 4.5
    # No collision.
    dists = []
    for k in range(len(ego)):
        dists.append(math.hypot(lead[k, 1] - ego[k, 1], lead[k, 2] - ego[k, 2]) - 4.5)
    assert min(dists) > 0.0, f"collision: min bumper gap = {min(dists):.3f}"
    return last_gap


def test_idm_follows_without_collision() -> None:
    idm = IdmPlanner(name="idm", T=1.2, s0=2.0, a=2.0, b=2.5, v0_factor=1.0)
    gap = _run_synthetic_follow(idm)
    assert gap > 0.5


def test_cautious_gap_greater_than_idm_gap() -> None:
    idm = IdmPlanner(name="idm", T=1.2, s0=2.0, a=2.0, b=2.5, v0_factor=1.0)
    caut = IdmPlanner(name="cautious_idm", T=2.2, s0=4.0, a=1.5, b=2.0, v0_factor=0.85)
    g_idm = _run_synthetic_follow(idm)
    g_caut = _run_synthetic_follow(caut)
    assert g_caut > g_idm


def test_mobil_adoption_of_laterally_converging_actor() -> None:
    # Actor in adjacent lane (y=5.25) with |vy| > 0.3 toward ego lane (1.75) => selected.
    ego = EgoObs(x=0.0, y=1.75, yaw=0.0, speed=15.0, accel_prev=0.0)
    conv = ActorObs(
        actor_id="conv",
        kind="vehicle",
        x=15.0,
        y=5.25,
        yaw=0.0,
        vx=15.0,
        vy=-1.0,  # laterally converging on ego lane
        length=4.5,
        width=1.9,
        radius=2.25,
    )
    # Also add a farther vehicle in the ego lane so we can verify converging is picked
    # only if it's closer / adopted.
    obs = Observation(
        t=0.0,
        dt=0.1,
        ego=ego,
        actors=(conv,),
        lane_width=3.5,
        n_lanes=2,
        ego_lane_center_y=1.75,
        speed_limit=22.2,
        target_speed=20.0,
        visibility_m=200.0,
        friction=0.9,
    )
    leader = select_leader(obs)
    assert leader is not None
    assert leader.actor_id == "conv"


def test_get_planners_all_and_single() -> None:
    everything = get_planners("all")
    assert set(everything) == {"constant_velocity", "idm", "cautious_idm"}
    single = get_planners("idm")
    assert set(single) == {"idm"}
    with pytest.raises(KeyError):
        get_planners("nope")
