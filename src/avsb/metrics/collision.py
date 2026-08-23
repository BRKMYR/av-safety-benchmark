"""Minimum-distance (M1) and collision + delta-v severity (M2). Spec 5.6."""

from __future__ import annotations

import math

import numpy as np

from avsb.metrics.geometry import pairwise_separation
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


def min_distance(
    log: TrajectoryLog, scen: ScenarioDefinition
) -> tuple[float, float | None]:
    """Return (d_min_m, t_at_min). If no non-static actors, returns (+inf, None)."""
    seps = pairwise_separation(log, scen)
    if not seps:
        return float("inf"), None
    ego = log.states("ego")
    times = ego[:, 0]
    best_val: float | None = None
    best_t: float | None = None
    for aid, d in seps.items():
        i = int(np.argmin(d))
        v = float(d[i])
        if best_val is None or v < best_val:
            best_val = v
            best_t = float(times[i])
    assert best_val is not None
    return best_val, best_t


def _mass_by_id(scen: ScenarioDefinition, actor_id: str) -> float:
    for a in scen.actors:
        if a.actor_id == actor_id:
            return float(a.mass_kg)
    return 0.0


def collision_metrics(
    log: TrajectoryLog, scen: ScenarioDefinition
) -> tuple[bool, float | None, float | None, int]:
    """Return (collision, t_collide, delta_v, severity_index).

    delta_v uses a perfectly-plastic model:
        delta_v = m_a/(m_e+m_a) * ||v_e(k*) - v_a(k*)||_2
    Severity tiers (benchmark-internal, NOT ISO 26262 S-classes):
        0 no collision, 1 <2, 2 in [2,6), 3 >=6.
    """
    seps = pairwise_separation(log, scen)
    if not seps:
        return False, None, None, 0
    ego = log.states("ego")
    times = ego[:, 0]
    # find earliest step with any d <= 0.
    first_k: int | None = None
    first_aid: str | None = None
    for aid, d in seps.items():
        idxs = np.where(d <= 0.0)[0]
        if idxs.size == 0:
            continue
        k = int(idxs[0])
        if first_k is None or k < first_k:
            first_k = k
            first_aid = aid
    if first_k is None:
        return False, None, None, 0
    assert first_aid is not None
    m_e = float(scen.ego.mass_kg)
    m_a = _mass_by_id(scen, first_aid)
    denom = max(1e-9, m_e + m_a)
    v_e = ego[first_k, 3:5]
    v_a = log.states(first_aid)[first_k, 3:5]
    rel = float(math.hypot(v_e[0] - v_a[0], v_e[1] - v_a[1]))
    delta_v = (m_a / denom) * rel
    if delta_v < 2.0:
        sev = 1
    elif delta_v < 6.0:
        sev = 2
    else:
        sev = 3
    return True, float(times[first_k]), float(delta_v), sev
