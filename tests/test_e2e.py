"""End-to-end smoke test on a reduced suite (spec 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def reduced_suite(monkeypatch):
    """Monkeypatch the family counts down to 2 each = 8 scenarios."""
    from avsb.generation import cut_in as m_cutin
    from avsb.generation import hard_brake as m_hb
    from avsb.generation import pedestrian as m_ped
    from avsb.generation import weather as m_wr

    monkeypatch.setattr(m_cutin.CutInGenerator, "count", 2)
    monkeypatch.setattr(m_ped.PedOccludedGenerator, "count", 2)
    monkeypatch.setattr(m_wr.WeatherRampGenerator, "count", 2)
    monkeypatch.setattr(m_hb.HardBrakeGenerator, "count", 2)


def test_end_to_end(reduced_suite, tmp_path: Path) -> None:
    from avsb.cli import main

    # Isolate CWD-adjacent paths by using tmp_path for every output root.
    scen_root = tmp_path / "scenarios"
    runs_root = tmp_path / "runs"
    report_root = tmp_path / "reports" / "core"
    screenshots = tmp_path / "docs" / "screenshots"

    assert main(["generate", "--suite", "core", "--seed", "42", "--out", str(scen_root)]) == 0
    assert main(
        [
            "run",
            "--suite",
            "core",
            "--planner",
            "all",
            "--scenarios",
            str(scen_root),
            "--out",
            str(runs_root),
        ]
    ) == 0
    assert main(
        [
            "report",
            "--suite",
            "core",
            "--runs",
            str(runs_root),
            "--scenarios",
            str(scen_root),
            "--out",
            str(report_root),
            "--screenshots",
            str(screenshots),
        ]
    ) == 0

    # 8 scenarios * 3 planners = 24 log + 24 result files.
    logs = list((runs_root / "core").rglob("*.jsonl"))
    assert len(logs) == 24
    results = list((runs_root / "core").rglob("*.result.json"))
    assert len(results) == 24

    index_html = report_root / "index.html"
    assert index_html.is_file()
    text = index_html.read_text(encoding="utf-8")
    assert "cautious_idm" in text
    assert "constant_velocity" in text

    summary_path = report_root / "summary.json"
    assert summary_path.is_file()
    from avsb.schema.result import SuiteSummary

    summary = SuiteSummary.model_validate_json(summary_path.read_text())
    assert set(summary.planners.keys()) == {
        "constant_velocity",
        "idm",
        "cautious_idm",
    }
    # Reduced-suite ordering (spec 10): cautious_idm > constant_velocity.
    caut = summary.planners["cautious_idm"].composite
    cv = summary.planners["constant_velocity"].composite
    assert caut > cv, (caut, cv)

    # 3 fixed screenshots.
    for name in ("leaderboard.png", "worst_cutin_bev.png", "worst_cutin_ttc.png"):
        p = screenshots / name
        assert p.is_file(), name


def test_scenario_run_deterministic(reduced_suite, tmp_path: Path) -> None:
    """Re-running one (scenario, planner) pair twice yields byte-identical JSONL."""
    from avsb.engine.simulator import run_scenario
    from avsb.generation.suite import generate_suite
    from avsb.planners.base import get_planners
    from avsb.schema.scenario import load_suite

    generate_suite("core", 42, tmp_path)
    scen = load_suite(tmp_path / "core")[0]
    planner = get_planners("idm")["idm"]
    log1 = run_scenario(scen, planner)
    planner2 = get_planners("idm")["idm"]
    log2 = run_scenario(scen, planner2)
    p1 = tmp_path / "one.jsonl"
    p2 = tmp_path / "two.jsonl"
    log1.write(p1)
    log2.write(p2)
    assert p1.read_bytes() == p2.read_bytes()
