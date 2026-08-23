"""Constant-velocity null baseline (spec 5.10): always returns Action(0, 0)."""

from __future__ import annotations

from avsb.engine.observation import Action, Observation
from avsb.schema.scenario import ScenarioDefinition


class ConstantVelocityPlanner:
    """Never brakes, never steers. Falsifiable null hypothesis."""

    name: str = "constant_velocity"

    def reset(self, scenario: ScenarioDefinition) -> None:
        return None

    def step(self, obs: Observation) -> Action:
        return Action(accel=0.0, steer=0.0)
