"""Scenario definition schema (spec section 5.1).

Every field name, type, and unit here is normative. See docs/ARCHITECTURE.md.
Models are frozen where practical and reject unknown fields (extra='forbid').
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from avsb.schema.io import read_yaml

FAMILIES = ("cut_in", "ped_occluded", "weather_ramp", "hard_brake")
FamilyLit = Literal["cut_in", "ped_occluded", "weather_ramp", "hard_brake"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InitialState(_Frozen):
    x_m: float
    y_m: float
    yaw_rad: float
    speed_mps: float = Field(ge=0.0)


class Road(_Frozen):
    n_lanes: int = Field(ge=1)
    lane_width_m: float = Field(gt=0.0)
    length_m: float = Field(gt=0.0)
    speed_limit_mps: float = Field(gt=0.0)


class Environment(_Frozen):
    visibility_start_m: float = Field(gt=0.0)
    visibility_end_m: float = Field(gt=0.0)
    friction_start: float = Field(gt=0.0, le=1.0)
    friction_end: float = Field(gt=0.0, le=1.0)


class Trigger(_Frozen):
    type: Literal["time", "ego_gap", "ego_x"]
    at_time_s: float | None = None
    gap_m: float | None = None
    ego_x_m: float | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "Trigger":
        if self.type == "time":
            if self.at_time_s is None:
                raise ValueError("trigger.type='time' requires at_time_s")
        elif self.type == "ego_gap":
            if self.gap_m is None:
                raise ValueError("trigger.type='ego_gap' requires gap_m")
        elif self.type == "ego_x":
            if self.ego_x_m is None:
                raise ValueError("trigger.type='ego_x' requires ego_x_m")
        return self


class Phase(_Frozen):
    trigger: Trigger
    accel_mps2: float
    target_speed_mps: float | None = None
    target_y_m: float | None = None
    lateral_speed_mps: float = Field(ge=0.0, default=0.0)


class EgoSpec(_Frozen):
    initial: InitialState
    target_speed_mps: float = Field(gt=0.0)
    lane: int = Field(ge=0)
    length_m: float = Field(gt=0.0)
    width_m: float = Field(gt=0.0)
    mass_kg: float = Field(gt=0.0)


class ActorSpec(_Frozen):
    actor_id: str
    kind: Literal["vehicle", "pedestrian", "static"]
    length_m: float = Field(gt=0.0)
    width_m: float = Field(gt=0.0)
    mass_kg: float = Field(gt=0.0)
    initial: InitialState
    phases: list[Phase] = Field(default_factory=list)

    @field_validator("actor_id")
    @classmethod
    def _not_ego(cls, v: str) -> str:
        if v == "ego":
            raise ValueError("actor_id 'ego' is reserved for the ego vehicle")
        return v


class ScenarioDefinition(BaseModel):
    """Complete scenario definition; models a single simulation episode."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    suite: str
    family: FamilyLit
    description: str
    seed: int
    duration_s: float = Field(ge=8.0, le=30.0)
    dt_s: Literal[0.1] = 0.1
    road: Road
    environment: Environment
    ego: EgoSpec
    actors: list[ActorSpec] = Field(default_factory=list)
    parameters: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _unique_actor_ids(self) -> "ScenarioDefinition":
        seen: set[str] = set()
        for a in self.actors:
            if a.actor_id in seen:
                raise ValueError(f"duplicate actor_id: {a.actor_id}")
            seen.add(a.actor_id)
        if self.ego.lane >= self.road.n_lanes:
            raise ValueError(
                f"ego.lane {self.ego.lane} >= road.n_lanes {self.road.n_lanes}"
            )
        return self

    @property
    def n_steps(self) -> int:
        # 10 Hz, inclusive of t=0 and t=duration_s. Use rounding to guard against
        # float drift when duration is e.g. 15.0 / 0.1.
        return int(round(self.duration_s / self.dt_s)) + 1


def load_scenario(path: str | Path) -> ScenarioDefinition:
    """Load and validate a single scenario YAML."""
    return read_yaml(path, ScenarioDefinition)


def load_suite(suite_dir: str | Path) -> list[ScenarioDefinition]:
    """Load every scenario under suite_dir/**/*.yaml, sorted by scenario_id."""
    root = Path(suite_dir)
    files = sorted(root.rglob("*.yaml"))
    scenarios = [load_scenario(p) for p in files]
    scenarios.sort(key=lambda s: s.scenario_id)
    return scenarios
