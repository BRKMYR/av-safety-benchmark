"""Assemble the HTML report + PNGs (spec 5.7, 5.5, 9, 11)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from avsb.regmap.loader import load_mapping
from avsb.report.plots import bev_plot, leaderboard_bars, metric_hist, ttc_curve
from avsb.schema.io import read_json
from avsb.schema.result import ScenarioResult, SuiteSummary
from avsb.schema.scenario import ScenarioDefinition, load_suite
from avsb.schema.trajectory import TrajectoryLog


FAMILIES = ("cut_in", "ped_occluded", "weather_ramp", "hard_brake")
_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_summary(runs_root: Path, suite: str) -> tuple[SuiteSummary, list[ScenarioResult]]:
    """Read every result.json under runs_root/{suite}/*/*.result.json."""
    root = runs_root / suite
    results: list[ScenarioResult] = []
    if root.is_dir():
        for planner_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            for jf in sorted(planner_dir.glob("*.result.json")):
                results.append(read_json(jf, ScenarioResult))
    from avsb.scoring.score import summarize

    summary = summarize(results)
    return summary, results


def _worst_case(
    results: list[ScenarioResult], family: str, planner: str
) -> ScenarioResult | None:
    subset = [r for r in results if r.family == family and r.planner == planner]
    if not subset:
        return None
    return min(subset, key=lambda r: (r.score, r.scenario_id))


def build_report(
    suite: str,
    runs_root: Path | str = "runs",
    scenarios_root: Path | str = "scenarios",
    out_dir: Path | str = "reports/core",
    screenshots_dir: Path | str = "docs/screenshots",
) -> Path:
    """Render index.html + supporting PNGs. Returns path to index.html."""
    runs_root = Path(runs_root)
    scenarios_root = Path(scenarios_root)
    out_dir = Path(out_dir)
    screenshots_dir = Path(screenshots_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    summary, results = _load_summary(runs_root, suite)

    # Write summary.json.
    with (out_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary.model_dump(mode="json"), fh, sort_keys=True, indent=2)

    # Scenario definitions for BEV plots.
    scenarios_by_id: dict[str, ScenarioDefinition] = {
        s.scenario_id: s for s in load_suite(scenarios_root / suite)
    }

    # Leaderboard image.
    leaderboard_png = leaderboard_bars(summary, plots_dir / "leaderboard.png")

    # Worst-case gallery: worst (family, planner) pair.
    worst_cases = []
    worst_cutin_idm_bev: Path | None = None
    worst_cutin_idm_ttc: Path | None = None
    for family in FAMILIES:
        for planner in summary.planners.keys():
            worst = _worst_case(results, family, planner)
            if worst is None:
                continue
            scen = scenarios_by_id.get(worst.scenario_id)
            if scen is None:
                continue
            log = TrajectoryLog.read(runs_root / suite / planner / f"{worst.scenario_id}.jsonl")
            bev_name = f"bev_{family}_{planner}_{worst.scenario_id}.png"
            ttc_name = f"ttc_{family}_{planner}_{worst.scenario_id}.png"
            bev_path = bev_plot(log, scen, plots_dir / bev_name)
            ttc_path = ttc_curve(log, scen, plots_dir / ttc_name)
            worst_cases.append(
                {
                    "family": family,
                    "planner": planner,
                    "scenario_id": worst.scenario_id,
                    "score": worst.score,
                    "severity_tier": worst.severity_tier,
                    "bev_png": f"plots/{bev_name}",
                    "ttc_png": f"plots/{ttc_name}",
                }
            )
            if family == "cut_in" and planner == "idm":
                worst_cutin_idm_bev = bev_path
                worst_cutin_idm_ttc = ttc_path

    # Distribution plots.
    dist_pngs = []
    for field in ("ttc_min_s", "d_min_m", "hard_brake_fraction"):
        p = metric_hist(results, field, plots_dir / f"dist_{field}.png")
        dist_pngs.append(f"plots/{p.name}")

    # Load regulatory mapping.
    regmap = load_mapping()

    # Render index.html.
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Leaderboard rows: rank order by composite desc.
    leaderboard_rows = []
    ranking = sorted(
        summary.planners.items(), key=lambda kv: (-kv[1].composite, kv[0])
    )
    for planner, ps in ranking:
        leaderboard_rows.append(
            {
                "planner": planner,
                "composite": ps.composite,
                "family_scores": {fam: ps.families.get(fam).score if ps.families.get(fam) else 0.0 for fam in FAMILIES},
                "collisions": sum(fs.collisions for fs in ps.families.values()),
            }
        )
    family_rows = []
    for planner, ps in ranking:
        for fam in FAMILIES:
            fs = ps.families.get(fam)
            if fs is None:
                continue
            family_rows.append(
                {
                    "planner": planner,
                    "family": fam,
                    "score": fs.score,
                    "n": fs.n,
                    "collisions": fs.collisions,
                    "worst_scenario_id": fs.worst_scenario_id,
                }
            )

    tpl = env.get_template("index.html.j2")
    html = tpl.render(
        suite=suite,
        families=FAMILIES,
        leaderboard=leaderboard_rows,
        family_rows=family_rows,
        worst_cases=worst_cases,
        distributions=dist_pngs,
        regmap=regmap,
    )
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # Copy 3 fixed screenshots.
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(leaderboard_png, screenshots_dir / "leaderboard.png")
    if worst_cutin_idm_bev is not None:
        shutil.copyfile(worst_cutin_idm_bev, screenshots_dir / "worst_cutin_bev.png")
    if worst_cutin_idm_ttc is not None:
        shutil.copyfile(worst_cutin_idm_ttc, screenshots_dir / "worst_cutin_ttc.png")

    return index_path
