"""matplotlib (Agg) PNGs for the HTML report (spec 5.7, 11)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from avsb.engine.observation import actor_radius  # noqa: E402
from avsb.metrics.geometry import pairwise_separation  # noqa: E402
from avsb.metrics.ttc import ttc_min  # noqa: E402
from avsb.schema.result import ScenarioResult, SuiteSummary  # noqa: E402
from avsb.schema.scenario import ScenarioDefinition  # noqa: E402
from avsb.schema.trajectory import TrajectoryLog  # noqa: E402


_DPI = 120


def _actor_color(kind: str, actor_id: str) -> str:
    if actor_id == "ego":
        return "#1f77b4"
    if kind == "pedestrian":
        return "#2ca02c"
    if kind == "static":
        return "#888888"
    return "#d62728"


def bev_plot(
    log: TrajectoryLog, scen: ScenarioDefinition, out_png: str | Path
) -> Path:
    """Bird's-eye trajectory plot with disc footprints at the moment of d_min."""
    fig, ax = plt.subplots(figsize=(9, 4))
    # Road boundary sketch.
    n_lanes = scen.road.n_lanes
    lw = scen.road.lane_width_m
    for i in range(n_lanes + 1):
        y = i * lw
        ax.axhline(y=y, color="#cccccc", linewidth=0.6, linestyle="--")
    # Ego trajectory.
    ego = log.states("ego")
    ax.plot(ego[:, 1], ego[:, 2], color=_actor_color("vehicle", "ego"), label="ego", linewidth=2.0)

    # Locate d_min instant.
    seps = pairwise_separation(log, scen)
    dmin_k = None
    dmin_aid = None
    dmin_val = float("inf")
    for aid, arr in seps.items():
        i = int(np.argmin(arr))
        if float(arr[i]) < dmin_val:
            dmin_val = float(arr[i])
            dmin_k = i
            dmin_aid = aid

    for spec in scen.actors:
        st = log.states(spec.actor_id)
        c = _actor_color(spec.kind, spec.actor_id)
        if spec.kind == "static":
            # Rectangle for the occluder.
            hl = spec.length_m / 2.0
            hw = spec.width_m / 2.0
            rect = plt.Rectangle(
                (st[0, 1] - hl, st[0, 2] - hw),
                spec.length_m,
                spec.width_m,
                facecolor=c,
                edgecolor="black",
                alpha=0.4,
                label=f"{spec.actor_id} (occluder)",
            )
            ax.add_patch(rect)
        else:
            ax.plot(st[:, 1], st[:, 2], color=c, linewidth=1.5, label=spec.actor_id)

    if dmin_k is not None and dmin_aid is not None:
        # Draw ego and partner discs at the closest-approach instant.
        er = scen.ego.length_m / 2.0
        ax.add_patch(
            plt.Circle(
                (ego[dmin_k, 1], ego[dmin_k, 2]),
                er,
                fill=False,
                edgecolor="#1f77b4",
                linewidth=1.5,
                linestyle=":",
            )
        )
        spec = next(a for a in scen.actors if a.actor_id == dmin_aid)
        ar = actor_radius(spec.kind, spec.length_m)
        st = log.states(dmin_aid)
        ax.add_patch(
            plt.Circle(
                (st[dmin_k, 1], st[dmin_k, 2]),
                ar,
                fill=False,
                edgecolor=_actor_color(spec.kind, dmin_aid),
                linewidth=1.5,
                linestyle=":",
            )
        )
        ax.annotate(
            f"d_min = {dmin_val:.2f} m",
            xy=(ego[dmin_k, 1], ego[dmin_k, 2]),
            xytext=(6, 8),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(f"BEV: {scen.scenario_id}  planner={log.header.planner}")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = Path(out_png)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=_DPI)
    plt.close(fig)
    return p


def ttc_curve(
    log: TrajectoryLog, scen: ScenarioDefinition, out_png: str | Path
) -> Path:
    """Time series of min-over-actors TTC per step."""
    ego = log.states("ego")
    n = log.n_steps
    ts = ego[:, 0]
    # per-actor TTC(k) then min.
    from avsb.metrics.geometry import closing_speed

    seps = pairwise_separation(log, scen)
    if not seps:
        curve = np.full(n, np.nan)
    else:
        all_ttc = np.full((len(seps), n), np.inf)
        for i, (aid, d) in enumerate(seps.items()):
            c = closing_speed(log, scen, aid)
            mask = (c > 0.1) & (d > 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                ttc = np.where(mask, d / np.maximum(c, 1e-6), np.inf)
            all_ttc[i] = ttc
        curve = np.min(all_ttc, axis=0)
    fig, ax = plt.subplots(figsize=(9, 3.2))
    display = np.where(np.isfinite(curve), curve, np.nan)
    ax.plot(ts, display, color="#d62728", linewidth=1.6)
    ax.axhline(1.0, color="#888", linewidth=0.6, linestyle="--")
    ax.axhline(3.0, color="#bbb", linewidth=0.6, linestyle=":")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("TTC [s]")
    ax.set_ylim(0.0, 8.0)
    ttc_val, ttc_t = ttc_min(log, scen)
    title = f"TTC(t): {scen.scenario_id} planner={log.header.planner}"
    if ttc_val is not None:
        title += f"  min={ttc_val:.2f} s @ t={ttc_t:.2f} s"
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = Path(out_png)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=_DPI)
    plt.close(fig)
    return p


def metric_hist(
    results: Iterable[ScenarioResult], field: str, out_png: str | Path
) -> Path:
    """Histogram of a metric across scenarios, grouped by planner."""
    results = list(results)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    planners = sorted({r.planner for r in results})
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i, planner in enumerate(planners):
        vals = []
        for r in results:
            if r.planner != planner:
                continue
            v = getattr(r.metrics, field)
            if v is None:
                continue
            vals.append(float(v))
        if vals:
            ax.hist(vals, bins=12, alpha=0.55, label=planner, color=colors[i % len(colors)])
    ax.set_xlabel(field)
    ax.set_ylabel("count")
    ax.set_title(f"Distribution of {field}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p = Path(out_png)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=_DPI)
    plt.close(fig)
    return p


def leaderboard_bars(summary: SuiteSummary, out_png: str | Path) -> Path:
    """Composite + per-family score bar chart for the leaderboard image."""
    planners = list(summary.planners.keys())
    families = ["cut_in", "ped_occluded", "weather_ramp", "hard_brake"]
    fig, ax = plt.subplots(figsize=(9, 4.0))
    ind = np.arange(len(planners))
    w = 0.16
    colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]
    for i, fam in enumerate(families):
        vals = []
        for p in planners:
            fs = summary.planners[p].families.get(fam)
            vals.append(fs.score if fs is not None else 0.0)
        ax.bar(ind + (i - 1.5) * w, vals, w, label=fam, color=colors[i])
    composites = [summary.planners[p].composite for p in planners]
    ax.plot(ind, composites, color="black", marker="o", linewidth=1.6, label="composite")
    ax.set_xticks(ind)
    ax.set_xticklabels(planners)
    ax.set_ylabel("score (0-100)")
    ax.set_ylim(0.0, 100.0)
    ax.set_title("Leaderboard: composite + per-family scores")
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    p = Path(out_png)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=_DPI)
    plt.close(fig)
    return p
