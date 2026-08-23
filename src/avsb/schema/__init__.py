"""Pydantic v2 data contracts.

Nothing else in the codebase defines data shapes. The schemas here are the
product: generation writes ScenarioDefinition, the engine writes TrajectoryLog,
metrics read TrajectoryLog and write ScenarioResult, scoring reads
ScenarioResult and writes SuiteSummary. Any external system that emits
conforming JSONL trajectory logs can be scored by avsb.metrics.
"""

from avsb.schema.regmap import RegEntry, RegReference, RegulatoryMapping
from avsb.schema.result import (
    FamilySummary,
    MetricSet,
    PlannerSummary,
    ScenarioResult,
    SuiteSummary,
)
from avsb.schema.scenario import (
    ActorSpec,
    EgoSpec,
    Environment,
    InitialState,
    Phase,
    Road,
    ScenarioDefinition,
    Trigger,
    load_scenario,
    load_suite,
)
from avsb.schema.trajectory import TrajectoryHeader, TrajectoryLog, TrajectoryRecord

__all__ = [
    "ActorSpec",
    "EgoSpec",
    "Environment",
    "FamilySummary",
    "InitialState",
    "MetricSet",
    "Phase",
    "PlannerSummary",
    "RegEntry",
    "RegReference",
    "RegulatoryMapping",
    "Road",
    "ScenarioDefinition",
    "ScenarioResult",
    "SuiteSummary",
    "TrajectoryHeader",
    "TrajectoryLog",
    "TrajectoryRecord",
    "Trigger",
    "load_scenario",
    "load_suite",
]
