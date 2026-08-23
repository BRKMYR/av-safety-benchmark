"""Surrogate safety metrics (spec 5.6). All formulas are pure functions over
TrajectoryLog + ScenarioDefinition."""

from avsb.metrics.collision import collision_metrics, min_distance
from avsb.metrics.comfort import hard_brake
from avsb.metrics.compute import compute_metrics
from avsb.metrics.geometry import closing_speed, pairwise_separation
from avsb.metrics.pet import pet_min
from avsb.metrics.ttc import ttc_min

__all__ = [
    "closing_speed",
    "collision_metrics",
    "compute_metrics",
    "hard_brake",
    "min_distance",
    "pairwise_separation",
    "pet_min",
    "ttc_min",
]
