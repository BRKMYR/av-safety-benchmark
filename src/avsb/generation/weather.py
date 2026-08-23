"""Weather-degradation ramp scenario generator (spec 5.9 row 3). 14 scenarios."""

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


class WeatherRampGenerator(FamilyGenerator):
    family: ClassVar[str] = "weather_ramp"
    count: ClassVar[int] = 14
    offset: ClassVar[int] = 3

    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        return {
            "ego_speed_mps": uniform(rng, 14.0, 20.0),
            "initial_gap_m": uniform(rng, 45.0, 70.0),
            "lead_speed_mps": uniform(rng, 8.0, 12.0),
            "visibility_end_m": uniform(rng, 15.0, 45.0),
            "friction_end": uniform(rng, 0.25, 0.5),
        }

    def build(
        self, params: dict[str, float], idx: int, seed: int
    ) -> ScenarioDefinition:
        lane_width = 3.5
        ego_lane = 1  # middle lane on 3-lane road
        ego_y = (ego_lane + 0.5) * lane_width
        ego_speed = params["ego_speed_mps"]
        lead_speed = params["lead_speed_mps"]
        initial_gap = params["initial_gap_m"]

        road = Road(
            n_lanes=3,
            lane_width_m=lane_width,
            length_m=400.0,
            speed_limit_mps=22.2,
        )
        env = Environment(
            visibility_start_m=200.0,
            visibility_end_m=params["visibility_end_m"],
            friction_start=0.9,
            friction_end=params["friction_end"],
        )
        ego = EgoSpec(
            initial=InitialState(x_m=0.0, y_m=ego_y, yaw_rad=0.0, speed_mps=ego_speed),
            target_speed_mps=ego_speed,
            lane=ego_lane,
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
            ],
        )
        return ScenarioDefinition(
            scenario_id=_scenario_id("core", self.family, idx),
            suite="core",
            family="weather_ramp",
            description=(
                f"Lead vehicle at {lead_speed:.1f} m/s while visibility ramps "
                f"200 -> {params['visibility_end_m']:.1f} m and friction "
                f"0.9 -> {params['friction_end']:.2f} over 20 s."
            ),
            seed=seed,
            duration_s=20.0,
            road=road,
            environment=env,
            ego=ego,
            actors=[lead],
            parameters={
                "ego_speed_mps": ego_speed,
                "initial_gap_m": initial_gap,
                "lead_speed_mps": lead_speed,
                "visibility_end_m": params["visibility_end_m"],
                "friction_end": params["friction_end"],
            },
        )
