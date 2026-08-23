"""Shared geometric arrays: separation and closing speed per non-static actor."""

from __future__ import annotations

import numpy as np

from avsb.engine.observation import actor_radius
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


EGO_RADIUS_M = 4.5 / 2.0


def _ego_radius(scen: ScenarioDefinition) -> float:
    return scen.ego.length_m / 2.0


def _actor_radius_from_spec(spec) -> float:
    return actor_radius(spec.kind, spec.length_m)


def _actor_by_id(scen: ScenarioDefinition, actor_id: str):
    for a in scen.actors:
        if a.actor_id == actor_id:
            return a
    return None


def pairwise_separation(
    log: TrajectoryLog, scen: ScenarioDefinition
) -> dict[str, np.ndarray]:
    """Return {actor_id: d_a(k)} for every non-static actor.

    d_a(k) = || p_a(k) - p_e(k) ||_2 - (r_ego + r_a). May be negative (overlap).
    """
    ego = log.states("ego")
    r_e = _ego_radius(scen)
    out: dict[str, np.ndarray] = {}
    for spec in scen.actors:
        if spec.kind == "static":
            continue
        st = log.states(spec.actor_id)
        dx = st[:, 1] - ego[:, 1]
        dy = st[:, 2] - ego[:, 2]
        dist = np.sqrt(dx * dx + dy * dy)
        r_a = _actor_radius_from_spec(spec)
        out[spec.actor_id] = dist - (r_e + r_a)
    return out


def closing_speed(
    log: TrajectoryLog, scen: ScenarioDefinition, actor_id: str
) -> np.ndarray:
    """Closing speed along the ego-to-actor line of sight per step (m/s).

    c(k) = -(r . v_rel)/||r|| where r = p_a - p_e, v_rel = v_a - v_e.
    Positive when the two are approaching, negative when separating.
    """
    ego = log.states("ego")
    st = log.states(actor_id)
    rx = st[:, 1] - ego[:, 1]
    ry = st[:, 2] - ego[:, 2]
    dist = np.sqrt(rx * rx + ry * ry)
    vrx = st[:, 3] - ego[:, 3]
    vry = st[:, 4] - ego[:, 4]
    with np.errstate(divide="ignore", invalid="ignore"):
        c = -((rx * vrx + ry * vry) / np.where(dist > 1e-9, dist, 1.0))
    c = np.where(dist > 1e-9, c, 0.0)
    return c
