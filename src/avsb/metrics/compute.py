"""Aggregate every metric into a MetricSet."""

from __future__ import annotations

from avsb.metrics.collision import collision_metrics, min_distance
from avsb.metrics.comfort import hard_brake
from avsb.metrics.pet import pet_min
from avsb.metrics.ttc import ttc_min
from avsb.schema.result import MetricSet
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


def compute_metrics(log: TrajectoryLog, scen: ScenarioDefinition) -> MetricSet:
    """Return the MetricSet for one (scenario, planner) trajectory log."""
    ttc, ttc_t = ttc_min(log, scen)
    pet = pet_min(log, scen)
    d, d_t = min_distance(log, scen)
    coll, coll_t, delta_v, sev = collision_metrics(log, scen)
    hb_frac, hb_events = hard_brake(log)

    # Clip d_min at the negative combined radius floor per spec (report clipping
    # is at >= -R; unclipped internally, but we report the raw value here since
    # downstream scoring uses max(d, 0)).
    return MetricSet(
        ttc_min_s=(None if ttc is None else float(ttc)),
        ttc_min_t_s=(None if ttc_t is None else float(ttc_t)),
        pet_min_s=(None if pet is None else float(pet)),
        d_min_m=float(d) if d != float("inf") else 999.0,
        d_min_t_s=(None if d_t is None else float(d_t)),
        collision=bool(coll),
        collision_t_s=(None if coll_t is None else float(coll_t)),
        delta_v_mps=(None if delta_v is None else float(delta_v)),
        severity_index=int(sev),
        hard_brake_fraction=float(hb_frac),
        hard_brake_events=int(hb_events),
    )
