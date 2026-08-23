"""Time-to-Collision (M3, spec 5.6)."""

from __future__ import annotations

import numpy as np

from avsb.metrics.geometry import closing_speed, pairwise_separation
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


def ttc_min(
    log: TrajectoryLog, scen: ScenarioDefinition
) -> tuple[float | None, float | None]:
    """Return (ttc_min_s, t_of_min). None if no finite conflict ever occurred."""
    seps = pairwise_separation(log, scen)
    if not seps:
        return None, None

    ego = log.states("ego")
    times = ego[:, 0]

    best_ttc: float | None = None
    best_t: float | None = None
    for aid, d in seps.items():
        c = closing_speed(log, scen, aid)
        # Valid where closing speed > 0.1 and separation > 0.
        mask = (c > 0.1) & (d > 0.0)
        if not np.any(mask):
            continue
        ttc = np.where(mask, d / np.maximum(c, 1e-6), np.inf)
        i = int(np.argmin(ttc))
        val = float(ttc[i])
        if not np.isfinite(val):
            continue
        if best_ttc is None or val < best_ttc:
            best_ttc = val
            best_t = float(times[i])
    if best_ttc is None:
        return None, None
    return best_ttc, best_t
