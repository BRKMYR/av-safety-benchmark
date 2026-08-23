"""Visibility / occlusion tests (spec 5.3).

An actor is visible iff (a) it is within the ego's sensing radius AND (b)
no static occluder's axis-aligned rectangle intersects the segment from
ego center to actor center. Rectangle intersection uses the Liang-Barsky
slab test.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def segment_intersects_rect(
    p0: tuple[float, float],
    p1: tuple[float, float],
    cx: float,
    cy: float,
    half_l: float,
    half_w: float,
) -> bool:
    """Return True iff the segment p0->p1 intersects the axis-aligned rectangle
    centered at (cx, cy) with half-length half_l (x) and half-width half_w (y).

    Uses the Liang-Barsky slab test with inclusive bounds. Endpoints inside
    the rectangle count as intersecting.
    """
    x0, y0 = p0
    x1, y1 = p1
    xmin = cx - half_l
    xmax = cx + half_l
    ymin = cy - half_w
    ymax = cy + half_w

    dx = x1 - x0
    dy = y1 - y0

    t_enter = 0.0
    t_exit = 1.0

    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if p == 0.0:
            if q < 0.0:
                return False  # segment is parallel and outside this slab
            # else: parallel and inside; no constraint contribution
            continue
        t = q / p
        if p < 0.0:
            if t > t_exit:
                return False
            if t > t_enter:
                t_enter = t
        else:
            if t < t_enter:
                return False
            if t < t_exit:
                t_exit = t

    return t_enter <= t_exit


def visible_actors(
    ego_xy: tuple[float, float],
    actors_state: Sequence[tuple[str, str, float, float, float, float]],
    statics: Sequence[tuple[float, float, float, float]],
    visibility_m: float,
) -> list[int]:
    """Return indices (into actors_state) of visible non-static actors.

    - actors_state entries: (actor_id, kind, x, y, half_l, half_w). Static
      actors are silently filtered out (they never appear in obs.actors).
    - statics entries: (cx, cy, half_l, half_w).
    """
    ex, ey = ego_xy
    ex_arr = np.array([ex, ey])
    visible: list[int] = []
    for i, (_aid, kind, x, y, _hl, _hw) in enumerate(actors_state):
        if kind == "static":
            continue
        d = float(np.linalg.norm(np.array([x, y]) - ex_arr))
        if d > visibility_m:
            continue
        blocked = False
        for cx, cy, hl, hw in statics:
            if segment_intersects_rect((ex, ey), (x, y), cx, cy, hl, hw):
                blocked = True
                break
        if not blocked:
            visible.append(i)
    return visible
