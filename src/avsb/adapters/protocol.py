"""v2 external-log adapter Protocol (spec 5.8). No implementations."""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


@runtime_checkable
class TrajectorySource(Protocol):
    """v2 seam.

    Anything that yields conforming ``TrajectoryLog``s (a CARLA bridge, a
    nuScenes / Waymo converter, real-vehicle CAN exports, ...) can be scored
    by ``avsb.metrics`` without touching the engine. Implementations must
    guarantee that the returned logs conform to the JSONL contract in
    ``schema/trajectory.py``; this Protocol is the seam, not a base class.
    """

    def scenarios(self) -> Iterable[ScenarioDefinition]: ...

    def log_for(self, scenario_id: str) -> TrajectoryLog: ...
