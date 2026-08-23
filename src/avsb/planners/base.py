"""Planner protocol and registry (spec 5.10)."""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from avsb.engine.observation import Action, Observation
from avsb.schema.scenario import ScenarioDefinition


@runtime_checkable
class Planner(Protocol):
    """Minimal planner interface. Every planner has a ``name`` attribute."""

    name: str

    def reset(self, scenario: ScenarioDefinition) -> None: ...

    def step(self, obs: Observation) -> Action: ...


def _make_constant_velocity() -> Planner:
    from avsb.planners.constant_velocity import ConstantVelocityPlanner

    return ConstantVelocityPlanner()


def _make_idm() -> Planner:
    from avsb.planners.idm import IdmPlanner

    return IdmPlanner(
        name="idm", T=1.2, s0=2.0, a=2.0, b=2.5, v0_factor=1.0
    )


def _make_cautious_idm() -> Planner:
    from avsb.planners.idm import IdmPlanner

    return IdmPlanner(
        name="cautious_idm", T=2.2, s0=4.0, a=1.5, b=2.0, v0_factor=0.85
    )


REGISTRY: dict[str, Callable[[], Planner]] = {
    "constant_velocity": _make_constant_velocity,
    "idm": _make_idm,
    "cautious_idm": _make_cautious_idm,
}


def get_planners(name: str) -> dict[str, Planner]:
    """Return {name: planner_instance}. ``all`` expands to every registered planner."""
    if name == "all":
        return {k: v() for k, v in REGISTRY.items()}
    if name not in REGISTRY:
        raise KeyError(f"unknown planner {name!r}; known: {list(REGISTRY)}")
    return {name: REGISTRY[name]()}
