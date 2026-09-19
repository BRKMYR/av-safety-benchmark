"""Mean speed ratio (M12): how much of its target speed the ego actually kept.

An availability metric rather than a safety metric. A planner that never moves
is perfectly safe and useless, so the assurance gate reads this one as the
counterweight to the collision and TTC gates.
"""

from __future__ import annotations

import numpy as np

from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


def mean_speed_ratio(log: TrajectoryLog, scen: ScenarioDefinition) -> float | None:
    """Return mean ego speed over the run divided by `ego.target_speed_mps`.

    Returns None when the target speed is zero, since the ratio is undefined.
    Speed is the norm of the logged velocity, so a lateral component counts.
    """
    target = float(scen.ego.target_speed_mps)
    if target <= 0.0:
        return None
    states = log.states("ego")
    if states.size == 0:
        return None
    speeds = np.hypot(states[:, 3], states[:, 4])
    return float(np.mean(speeds) / target)
