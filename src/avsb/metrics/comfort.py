"""Hard-braking / intervention proxy (M5, spec 5.6)."""

from __future__ import annotations

import numpy as np

from avsb.schema.trajectory import TrajectoryLog


def hard_brake(log: TrajectoryLog, threshold: float = -4.0) -> tuple[float, int]:
    """Return (fraction_of_steps_below_threshold, number_of_events).

    Events = number of maximal contiguous runs where accel_cmd <= threshold.
    """
    a = log.accel_cmd()
    if a.size == 0:
        return 0.0, 0
    mask = a <= threshold
    fraction = float(np.mean(mask))
    # Count runs of True.
    events = 0
    prev = False
    for v in mask:
        if v and not prev:
            events += 1
        prev = bool(v)
    return fraction, events
