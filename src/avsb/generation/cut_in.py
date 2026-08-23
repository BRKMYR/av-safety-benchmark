"""Cut-in scenario generator (spec 5.9 row 1). 16 scenarios."""

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


class CutInGenerator(FamilyGenerator):
    family: ClassVar[str] = "cut_in"
    count: ClassVar[int] = 16
    offset: ClassVar[int] = 1

    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        return {
            "ego_speed_mps": uniform(rng, 15.0, 22.0),
            "initial_gap_m": uniform(rng, 15.0, 30.0),
            "speed_delta_mps": uniform(rng, -5.0, 1.0),
            "trigger_gap_m": uniform(rng, 8.0, 18.0),
            "lateral_speed_mps": uniform(rng, 0.6, 1.5),
        }

    def build(
        self, params: dict[str, float], idx: int, seed: int
    ) -> ScenarioDefinition:
        lane_width = 3.5
        ego_y = 0.5 * lane_width  # lane 0
        cutter_y = 1.5 * lane_width  # lane 1
        ego_speed = params["ego_speed_mps"]
        cutter_speed = max(0.0, ego_speed + params["speed_delta_mps"])
        initial_gap = params["initial_gap_m"]
        trigger_gap = min(params["trigger_gap_m"], initial_gap - 1.0)
        trigger_gap = round(max(trigger_gap, 5.0), 4)
        lateral_speed = params["lateral_speed_mps"]

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
        cutter = ActorSpec(
            actor_id="cutter",
            kind="vehicle",
            length_m=4.5,
            width_m=1.9,
            mass_kg=1500.0,
            initial=InitialState(
                x_m=initial_gap,
                y_m=cutter_y,
                yaw_rad=0.0,
                speed_mps=cutter_speed,
            ),
            phases=[
                Phase(
                    trigger=Trigger(type="time", at_time_s=0.0),
                    accel_mps2=0.0,
                    target_speed_mps=cutter_speed,
                    target_y_m=None,
                    lateral_speed_mps=0.0,
                ),
                Phase(
                    trigger=Trigger(type="ego_gap", gap_m=trigger_gap),
                    accel_mps2=0.0,
                    target_speed_mps=cutter_speed,
                    target_y_m=ego_y,
                    lateral_speed_mps=lateral_speed,
                ),
            ],
        )
        return ScenarioDefinition(
            scenario_id=_scenario_id("core", self.family, idx),
            suite="core",
            family="cut_in",
            description=(
                f"Adjacent-lane vehicle cuts in ahead of ego with "
                f"{initial_gap:.1f} m initial gap; trigger at gap<={trigger_gap:.1f} m; "
                f"lateral speed {lateral_speed:.2f} m/s."
            ),
            seed=seed,
            duration_s=15.0,
            road=road,
            environment=env,
            ego=ego,
            actors=[cutter],
            parameters={
                "ego_speed_mps": ego_speed,
                "initial_gap_m": initial_gap,
                "speed_delta_mps": params["speed_delta_mps"],
                "trigger_gap_m": trigger_gap,
                "lateral_speed_mps": lateral_speed,
            },
        )
