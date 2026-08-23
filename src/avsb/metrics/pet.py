"""Post-Encroachment Time (M4, spec 5.6): grid-cell PET."""

from __future__ import annotations

import math

import numpy as np

from avsb.engine.observation import actor_radius
from avsb.schema.scenario import ScenarioDefinition
from avsb.schema.trajectory import TrajectoryLog


def _disc_cells(
    x: float, y: float, r: float, cell: float
) -> set[tuple[int, int]]:
    """Return set of (ix, iy) cell indices whose center lies inside the disc."""
    ix_min = int(math.floor((x - r) / cell))
    ix_max = int(math.floor((x + r) / cell))
    iy_min = int(math.floor((y - r) / cell))
    iy_max = int(math.floor((y + r) / cell))
    r2 = r * r
    out: set[tuple[int, int]] = set()
    for ix in range(ix_min, ix_max + 1):
        cx = (ix + 0.5) * cell
        for iy in range(iy_min, iy_max + 1):
            cy = (iy + 0.5) * cell
            if (cx - x) ** 2 + (cy - y) ** 2 <= r2:
                out.add((ix, iy))
    return out


def pet_min(
    log: TrajectoryLog, scen: ScenarioDefinition, cell: float = 0.5
) -> float | None:
    """Grid-cell PET (spec 5.6 M4). None if no cell is shared with disjoint intervals."""
    dt = log.dt_s
    ego = log.states("ego")
    ego_r = scen.ego.length_m / 2.0
    n = log.n_steps

    # occupancy: {(actor_id, cell): (first_step, last_step)}
    # We keep per-actor cell intervals; a cell that is re-entered later would
    # ideally split into multiple intervals, but PET is a min so we conservatively
    # use (first_step, last_step) of contiguous occupancy by tracking gaps.
    per_actor_cells: dict[str, dict[tuple[int, int], list[tuple[int, int]]]] = {}

    def add_intervals(actor_id: str, k: int, cells: set[tuple[int, int]]) -> None:
        d = per_actor_cells.setdefault(actor_id, {})
        for c in cells:
            runs = d.get(c)
            if runs is None:
                d[c] = [(k, k)]
            else:
                last_start, last_end = runs[-1]
                if k == last_end + 1:
                    runs[-1] = (last_start, k)
                else:
                    runs.append((k, k))

    for k in range(n):
        cells = _disc_cells(ego[k, 1], ego[k, 2], ego_r, cell)
        add_intervals("ego", k, cells)
        for spec in scen.actors:
            if spec.kind == "static":
                continue
            st = log.states(spec.actor_id)
            r_a = actor_radius(spec.kind, spec.length_m)
            cells_a = _disc_cells(st[k, 1], st[k, 2], r_a, cell)
            add_intervals(spec.actor_id, k, cells_a)

    ego_map = per_actor_cells.get("ego", {})
    best: float | None = None
    for aid, cells_map in per_actor_cells.items():
        if aid == "ego":
            continue
        for c, runs_a in cells_map.items():
            runs_e = ego_map.get(c)
            if not runs_e:
                continue
            for ea_s, ea_e in runs_e:
                for aa_s, aa_e in runs_a:
                    # ego first, then actor.
                    if aa_s > ea_e:
                        gap = (aa_s - ea_e) * dt
                        if best is None or gap < best:
                            best = gap
                    # actor first, then ego.
                    if ea_s > aa_e:
                        gap = (ea_s - aa_e) * dt
                        if best is None or gap < best:
                            best = gap
    return best
