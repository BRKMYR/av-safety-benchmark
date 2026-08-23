"""Occluded pedestrian scenario generator (spec 5.9 row 2). 16 scenarios."""

from __future__ import annotations

from typing import ClassVar

import numpy as np

from avsb.generation.base import FamilyGenerator, _scenario_id, uniform
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


class PedOccludedGenerator(FamilyGenerator):
    family: ClassVar[str] = "ped_occluded"
    count: ClassVar[int] = 16
    offset: ClassVar[int] = 2

    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        return {
            "ego_speed_mps": uniform(rng, 8.0, 14.0),
            "occluder_x_m": uniform(rng, 40.0, 70.0),
            "ped_speed_mps": uniform(rng, 1.0, 2.5),
            "trigger_offset_m": uniform(rng, 12.0, 30.0),
        }

    def build(
        self, params: dict[str, float], idx: int, seed: int
    ) -> ScenarioDefinition:
        lane_width = 3.5
        ego_y = 0.5 * lane_width  # lane 0
        ego_speed = params["ego_speed_mps"]
        occ_x = params["occluder_x_m"]
        ped_speed = params["ped_speed_mps"]
        trigger_offset = params["trigger_offset_m"]
        trigger_ego_x = round(max(0.0, occ_x - trigger_offset), 4)

        road = Road(
            n_lanes=2,
            lane_width_m=lane_width,
            length_m=400.0,
            speed_limit_mps=13.9,
        )
        env = Environment(
            visibility_start_m=200.0,
            visibility_end_m=200.0,
            friction_start=0.9,
            friction_end=0.9,
        )
        ego = EgoSpec(
            initial=InitialState(x_m=0.0, y_m=ego_y, yaw_rad=0.0, speed_mps=ego_speed),
            target_speed_mps=ego_speed,
            lane=0,
            length_m=4.5,
            width_m=1.9,
            mass_kg=1500.0,
        )
        occluder = ActorSpec(
            actor_id="occluder",
            kind="static",
            length_m=6.0,
            width_m=2.0,
            mass_kg=1800.0,
            initial=InitialState(x_m=occ_x, y_m=-1.2, yaw_rad=0.0, speed_mps=0.0),
            phases=[],
        )
        pedestrian = ActorSpec(
            actor_id="pedestrian",
            kind="pedestrian",
            length_m=0.6,
            width_m=0.6,
            mass_kg=75.0,
            initial=InitialState(
                x_m=occ_x, y_m=-2.5, yaw_rad=1.5708, speed_mps=0.0
            ),
            phases=[
                Phase(
                    trigger=Trigger(type="time", at_time_s=0.0),
                    accel_mps2=0.0,
                    target_speed_mps=0.0,
                    target_y_m=None,
                    lateral_speed_mps=0.0,
                ),
                Phase(
                    trigger=Trigger(type="ego_x", ego_x_m=trigger_ego_x),
                    accel_mps2=0.0,
                    target_speed_mps=0.0,
                    target_y_m=6.0,
                    lateral_speed_mps=ped_speed,
                ),
            ],
        )
        return ScenarioDefinition(
            scenario_id=_scenario_id("core", self.family, idx),
            suite="core",
            family="ped_occluded",
            description=(
                f"Pedestrian occluded by parked vehicle at x={occ_x:.1f} m; "
                f"begins crossing at speed {ped_speed:.2f} m/s when ego reaches "
                f"x={trigger_ego_x:.1f} m."
            ),
            seed=seed,
            duration_s=15.0,
            road=road,
            environment=env,
            ego=ego,
            actors=[occluder, pedestrian],
            parameters={
                "ego_speed_mps": ego_speed,
                "occluder_x_m": occ_x,
                "ped_speed_mps": ped_speed,
                "trigger_offset_m": trigger_offset,
                "trigger_ego_x_m": trigger_ego_x,
            },
        )
