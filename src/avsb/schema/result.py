"""Per-scenario result and suite summary schemas (spec section 5.4).

MetricSet holds the 11 metric fields defined in section 5.6. ScenarioResult
is written as JSON per (scenario, planner) run. SuiteSummary aggregates
results per planner and family; it is the payload that the report renders.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from avsb.schema.scenario import FamilyLit


class MetricSet(BaseModel):
    """Exactly the 11 metric fields from spec 5.4.

    `ttc_min_s` and `pet_min_s` may be `None`, meaning "no closing conflict"
    and "no shared conflict zone" respectively. Scoring treats both as +inf.
    """

    model_config = ConfigDict(extra="forbid")

    ttc_min_s: float | None = None
    ttc_min_t_s: float | None = None
    pet_min_s: float | None = None
    d_min_m: float
    d_min_t_s: float | None = None
    collision: bool = False
    collision_t_s: float | None = None
    delta_v_mps: float | None = None
    severity_index: int = Field(ge=0, le=3, default=0)
    hard_brake_fraction: float = Field(ge=0.0, le=1.0, default=0.0)
    hard_brake_events: int = Field(ge=0, default=0)


class ScenarioResult(BaseModel):
    """One result per (scenario, planner)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    suite: str
    family: FamilyLit
    planner: str
    n_steps: int = Field(ge=1)
    duration_s: float = Field(gt=0.0)
    trajectory_log: str
    metrics: MetricSet
    score: float = Field(ge=0.0, le=100.0)
    severity_tier: Literal["nominal", "near_miss", "critical"]


class FamilySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float
    n: int
    collisions: int
    worst_scenario_id: str


class PlannerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    composite: float
    families: dict[str, FamilySummary]


class SuiteSummary(BaseModel):
    """Aggregation across planners and families."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    suite: str
    planners: dict[str, PlannerSummary]
    results: list[ScenarioResult] = Field(default_factory=list)
