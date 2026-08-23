"""Hard-brake lead-vehicle scenario generator (spec 5.9 row 4). 14 scenarios."""

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


class HardBrakeGenerator(FamilyGenerator):
    family: ClassVar[str] = "hard_brake"
    count: ClassVar[int] = 14
    offset: ClassVar[int] = 4

    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        return {
            "ego_speed_mps": uniform(rng, 15.0, 22.0),
            "initial_gap_m": uniform(rng, 12.0, 35.0),
            "lead_speed_delta_mps": uniform(rng, 0.0, 3.0),  # subtracted from ego
            "brake_decel_mps2": uniform(rng, -8.0, -3.5),
            "brake_trigger_time_s": uniform(rng, 2.0, 5.0),
        }

    def build(
        self, params: dict[str, float], idx: int, seed: int
    ) -> ScenarioDefinition:
        lane_width = 3.5
        ego_y = 0.5 * lane_width  # lane 0
        ego_speed = params["ego_speed_mps"]
        lead_speed = max(0.0, ego_speed - params["lead_speed_delta_mps"])
        initial_gap = params["initial_gap_m"]
        brake_decel = params["brake_decel_mps2"]
        brake_time = params["brake_trigger_time_s"]

        road = Road(
            n_lanes=2,
            lane_width_m=lane_width,
            length_m=400.0,
            speed_limit_mps=22.2,
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
        lead = ActorSpec(
            actor_id="lead",
            kind="vehicle",
            length_m=4.5,
            width_m=1.9,
            mass_kg=1500.0,
            initial=InitialState(
                x_m=initial_gap, y_m=ego_y, yaw_rad=0.0, speed_mps=lead_speed
            ),
            phases=[
                Phase(
                    trigger=Trigger(type="time", at_time_s=0.0),
                    accel_mps2=0.0,
                    target_speed_mps=lead_speed,
                    target_y_m=None,
                    lateral_speed_mps=0.0,
                ),
                Phase(
                    trigger=Trigger(type="time", at_time_s=brake_time),
                    accel_mps2=brake_decel,
                    target_speed_mps=0.0,
                    target_y_m=None,
                    lateral_speed_mps=0.0,
                ),
            ],
        )
        return ScenarioDefinition(
            scenario_id=_scenario_id("core", self.family, idx),
            suite="core",
            family="hard_brake",
            description=(
                f"Lead vehicle at {lead_speed:.1f} m/s, initial gap "
                f"{initial_gap:.1f} m; brakes at {brake_decel:.2f} m/s^2 starting "
                f"t={brake_time:.1f} s."
            ),
            seed=seed,
            duration_s=15.0,
            road=road,
            environment=env,
            ego=ego,
            actors=[lead],
            parameters={
                "ego_speed_mps": ego_speed,
                "initial_gap_m": initial_gap,
                "lead_speed_delta_mps": params["lead_speed_delta_mps"],
                "brake_decel_mps2": brake_decel,
                "brake_trigger_time_s": brake_time,
            },
        )
