"""argparse CLI (spec section 2, 6 row 34, AC-1/2/5/8/9)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from avsb import __version__


def _cmd_generate(args: argparse.Namespace) -> int:
    from avsb.generation.suite import generate_suite

    paths = generate_suite(args.suite, args.seed, Path(args.out))
    print(
        f"generate: wrote {len(paths)} scenarios into "
        f"{Path(args.out) / args.suite} (seed={args.seed})"
    )
    return 0


def _write_run_manifest(out_root: Path, suite: str, seed: int | None) -> Path:
    """Write `manifest.json` for one suite: when it ran, from which seed, with which version.

    The assurance gate reads this file, so the timestamp is UTC with a `Z`.
    """
    import json
    from datetime import datetime, timezone

    manifest = {
        "schema_version": "1.1",
        "suite": suite,
        "seed": seed,
        "avsb_version": __version__,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = out_root / suite / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _cmd_run(args: argparse.Namespace) -> int:
    from avsb.engine.simulator import run_scenario
    from avsb.metrics.compute import compute_metrics
    from avsb.planners.base import get_planners
    from avsb.schema.io import write_json
    from avsb.schema.result import ScenarioResult
    from avsb.schema.scenario import load_suite
    from avsb.scoring.score import score_scenario

    suite_dir = Path(args.scenarios) / args.suite
    scenarios = load_suite(suite_dir)
    planners = get_planners(args.planner)
    out_root = Path(args.out)
    n_pairs = 0
    for scen in scenarios:
        for planner_name, planner in planners.items():
            log = run_scenario(scen, planner)
            log_path = out_root / scen.suite / planner_name / f"{scen.scenario_id}.jsonl"
            log.write(log_path)
            metrics = compute_metrics(log, scen)
            score, tier = score_scenario(metrics)
            # Store the trajectory log path as given (absolute or relative to CWD as constructed).
            rel_log = str(log_path)
            result = ScenarioResult(
                scenario_id=scen.scenario_id,
                suite=scen.suite,
                family=scen.family,
                planner=planner_name,
                n_steps=scen.n_steps,
                duration_s=scen.duration_s,
                trajectory_log=rel_log,
                metrics=metrics,
                score=float(score),
                severity_tier=tier,
            )
            result_path = log_path.with_suffix(".result.json")
            write_json(result_path, result)
            n_pairs += 1
    seed = scenarios[0].seed if scenarios else None
    manifest_path = _write_run_manifest(out_root, args.suite, seed)
    print(f"run: executed {n_pairs} (scenario, planner) pairs into {out_root}")
    print(f"run: wrote {manifest_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from avsb.report.render import build_report

    p = build_report(
        suite=args.suite,
        runs_root=Path(args.runs),
        scenarios_root=Path(args.scenarios),
        out_dir=Path(args.out),
        screenshots_dir=Path(args.screenshots),
    )
    print(f"report: wrote {p}")
    return 0


def _cmd_plots(args: argparse.Namespace) -> int:
    from avsb.report.render import build_all_bev_plots

    ids: list[str] | None = None
    if args.scenarios_filter:
        ids = [sid.strip() for sid in args.scenarios_filter.split(",") if sid.strip()]
    try:
        paths = build_all_bev_plots(
            suite=args.suite,
            runs_root=Path(args.runs),
            scenarios_root=Path(args.scenarios),
            out_dir=Path(args.out),
            scenario_ids=ids,
        )
    except ValueError as e:
        print(f"plots: {e}", file=sys.stderr)
        return 2
    print(f"plots: wrote {len(paths)} BEV plots into {args.out}")
    return 0


def _cmd_export_xosc(args: argparse.Namespace) -> int:
    from avsb.export.xosc import UnsupportedFamilyError, export_suite

    try:
        paths = export_suite(
            Path(args.scenarios) / args.suite, args.family, Path(args.out)
        )
    except UnsupportedFamilyError as e:
        print(f"export-xosc: family not supported for export ({e})", file=sys.stderr)
        return 2
    print(f"export-xosc: wrote {len(paths)} .xosc files into {args.out}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avsb",
        description="av-safety-benchmark CLI: generate, run, report, plots, export-xosc.",
    )
    p.add_argument("--version", action="version", version=f"avsb {__version__}")
    subs = p.add_subparsers(dest="cmd", required=True)

    gp = subs.add_parser("generate", help="Generate a scenario suite")
    gp.add_argument("--suite", default="core")
    gp.add_argument("--seed", type=int, default=42)
    gp.add_argument("--out", default="scenarios", help="Output root directory")
    gp.set_defaults(func=_cmd_generate)

    rp = subs.add_parser("run", help="Run planners over a suite")
    rp.add_argument("--suite", default="core")
    rp.add_argument("--planner", default="all")
    rp.add_argument("--scenarios", default="scenarios")
    rp.add_argument("--out", default="runs")
    rp.set_defaults(func=_cmd_run)

    rep = subs.add_parser("report", help="Render the HTML report")
    rep.add_argument("--suite", default="core")
    rep.add_argument("--runs", default="runs")
    rep.add_argument("--scenarios", default="scenarios")
    rep.add_argument("--out", default="reports/core")
    rep.add_argument("--screenshots", default="docs/screenshots")
    rep.set_defaults(func=_cmd_report)

    pp = subs.add_parser(
        "plots", help="Render a BEV plot for every (scenario, planner) pair"
    )
    pp.add_argument("--suite", default="core")
    pp.add_argument("--runs", default="runs")
    pp.add_argument("--scenarios", default="scenarios")
    pp.add_argument("--out", default="reports/plots_all")
    pp.add_argument(
        "--scenarios-filter",
        default=None,
        help="Comma separated list of scenario ids to restrict rendering to",
    )
    pp.set_defaults(func=_cmd_plots)

    ep = subs.add_parser("export-xosc", help="Export scenarios to OpenSCENARIO XML")
    ep.add_argument("--suite", default="core")
    ep.add_argument("--family", required=True)
    ep.add_argument("--scenarios", default="scenarios")
    ep.add_argument("--out", default="exports/xosc")
    ep.set_defaults(func=_cmd_export_xosc)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
