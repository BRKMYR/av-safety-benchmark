"""`avsb plots`: one BEV PNG per (scenario, planner) pair, byte-deterministic."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tiny_suite(monkeypatch):
    """Shrink every family to a single scenario = 4 scenarios."""
    from avsb.generation import cut_in as m_cutin
    from avsb.generation import hard_brake as m_hb
    from avsb.generation import pedestrian as m_ped
    from avsb.generation import weather as m_wr

    monkeypatch.setattr(m_cutin.CutInGenerator, "count", 1)
    monkeypatch.setattr(m_ped.PedOccludedGenerator, "count", 1)
    monkeypatch.setattr(m_wr.WeatherRampGenerator, "count", 1)
    monkeypatch.setattr(m_hb.HardBrakeGenerator, "count", 1)


def test_plots_are_deterministic(tiny_suite, tmp_path: Path) -> None:
    from avsb.cli import main
    from avsb.schema.scenario import load_suite

    scen_root = tmp_path / "scenarios"
    runs_root = tmp_path / "runs"

    assert main(["generate", "--suite", "core", "--seed", "42", "--out", str(scen_root)]) == 0
    assert main(
        ["run", "--suite", "core", "--planner", "idm", "--scenarios", str(scen_root),
         "--out", str(runs_root)]
    ) == 0

    scenarios = sorted(load_suite(scen_root / "core"), key=lambda s: s.scenario_id)
    two = scenarios[:2]
    ids = ",".join(s.scenario_id for s in two)
    expected = [f"bev_{s.family}_idm_{s.scenario_id}.png" for s in two]

    outs = []
    for i in (1, 2):
        out_dir = tmp_path / f"plots_all_{i}"
        assert main(
            ["plots", "--suite", "core", "--runs", str(runs_root), "--scenarios",
             str(scen_root), "--out", str(out_dir), "--scenarios-filter", ids]
        ) == 0
        assert sorted(p.name for p in out_dir.glob("*.png")) == sorted(expected)
        outs.append(out_dir)

    for name in expected:
        a = (outs[0] / name).read_bytes()
        b = (outs[1] / name).read_bytes()
        assert a == b, f"{name} is not byte identical across runs"
        assert len(a) > 0


def test_plots_rejects_unknown_scenario_id(tiny_suite, tmp_path: Path) -> None:
    from avsb.cli import main

    scen_root = tmp_path / "scenarios"
    runs_root = tmp_path / "runs"
    assert main(["generate", "--suite", "core", "--seed", "42", "--out", str(scen_root)]) == 0
    assert main(
        ["run", "--suite", "core", "--planner", "idm", "--scenarios", str(scen_root),
         "--out", str(runs_root)]
    ) == 0
    assert main(
        ["plots", "--suite", "core", "--runs", str(runs_root), "--scenarios", str(scen_root),
         "--out", str(tmp_path / "o"), "--scenarios-filter", "nope-0001"]
    ) == 2
