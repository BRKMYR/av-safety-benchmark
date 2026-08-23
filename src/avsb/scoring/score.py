"""Per-scenario scoring, severity tier assignment, suite summarization (spec 5.7)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable

from avsb.schema.result import (
    FamilySummary,
    MetricSet,
    PlannerSummary,
    ScenarioResult,
    SuiteSummary,
)


def _clip(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _inf_if_none(x: float | None) -> float:
    return math.inf if x is None else float(x)


def severity_tier(m: MetricSet) -> str:
    """critical | near_miss | nominal per spec 5.7."""
    ttc = _inf_if_none(m.ttc_min_s)
    pet = _inf_if_none(m.pet_min_s)
    d = float(m.d_min_m)
    if m.collision or ttc < 0.5 or d < 0.25:
        return "critical"
    if ttc < 1.5 or d < 0.75 or pet < 1.0:
        return "near_miss"
    return "nominal"


def score_scenario(m: MetricSet) -> tuple[float, str]:
    """Return (score, severity_tier). Score in [0, 100]."""
    tier = severity_tier(m)
    if m.collision:
        s = 10.0 if int(m.severity_index) == 1 else 0.0
        return float(s), tier

    ttc = _inf_if_none(m.ttc_min_s)
    pet = _inf_if_none(m.pet_min_s)
    d = max(0.0, float(m.d_min_m))
    h = float(m.hard_brake_fraction)

    f_ttc = _clip(ttc / 3.0, 0.0, 1.0)
    f_dist = _clip(d / 2.0, 0.0, 1.0)
    f_pet = _clip(pet / 2.0, 0.0, 1.0)
    f_comf = 1.0 - _clip(h / 0.25, 0.0, 1.0)
    s = 100.0 * (0.40 * f_ttc + 0.25 * f_dist + 0.20 * f_pet + 0.15 * f_comf)
    return float(s), tier


FAMILY_KEYS = ("cut_in", "ped_occluded", "weather_ramp", "hard_brake")


def summarize(results: Iterable[ScenarioResult]) -> SuiteSummary:
    """Aggregate ScenarioResults into a SuiteSummary."""
    results = list(results)
    if not results:
        return SuiteSummary(suite="", planners={}, results=[])

    suite = results[0].suite
    # planner -> family -> [ScenarioResult]
    grouped: dict[str, dict[str, list[ScenarioResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        grouped[r.planner][r.family].append(r)

    planners: dict[str, PlannerSummary] = {}
    for planner, families in grouped.items():
        fam_summaries: dict[str, FamilySummary] = {}
        for fam, rs in families.items():
            scores = [r.score for r in rs]
            collisions = sum(1 for r in rs if r.metrics.collision)
            # Worst = lowest score; ties broken by scenario_id (deterministic).
            worst = min(rs, key=lambda r: (r.score, r.scenario_id))
            fam_summaries[fam] = FamilySummary(
                score=float(sum(scores) / len(scores)),
                n=len(rs),
                collisions=int(collisions),
                worst_scenario_id=worst.scenario_id,
            )
        # Composite = unweighted mean over the families PRESENT for this planner.
        # (In the full suite all 4 are present; guards against sparse test runs.)
        fam_scores = [fs.score for fs in fam_summaries.values()]
        composite = float(sum(fam_scores) / len(fam_scores)) if fam_scores else 0.0
        planners[planner] = PlannerSummary(composite=composite, families=fam_summaries)

    # Deterministic order: sort results by (scenario_id, planner).
    results_sorted = sorted(results, key=lambda r: (r.scenario_id, r.planner))
    return SuiteSummary(suite=suite, planners=planners, results=results_sorted)
