"""Generation tests (spec 10): determinism, ranges, counts, validation."""

from __future__ import annotations

from pathlib import Path

from avsb.generation.suite import generate_suite
from avsb.schema.scenario import load_scenario, load_suite


COUNTS = {"cut_in": 16, "ped_occluded": 16, "weather_ramp": 14, "hard_brake": 14}


def _tree_signature(root: Path) -> list[tuple[str, str]]:
    """Return (relative_path, sha_of_content) sorted list; SHA is content bytes."""
    import hashlib

    files = sorted(root.rglob("*.yaml"))
    sigs = []
    for p in files:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        sigs.append((str(p.relative_to(root)), h))
    return sigs


def test_generate_determinism(tmp_path: Path) -> None:
    a = tmp_path / "A"
    b = tmp_path / "B"
    generate_suite("core", 42, a)
    generate_suite("core", 42, b)
    assert _tree_signature(a) == _tree_signature(b)


def test_generate_seed_sensitivity(tmp_path: Path) -> None:
    a = tmp_path / "A"
    b = tmp_path / "B"
    generate_suite("core", 42, a)
    generate_suite("core", 43, b)
    assert _tree_signature(a) != _tree_signature(b)


def test_family_counts(tmp_path: Path) -> None:
    generate_suite("core", 42, tmp_path)
    for family, count in COUNTS.items():
        fam_dir = tmp_path / "core" / family
        assert fam_dir.is_dir(), fam_dir
        files = sorted(fam_dir.glob("*.yaml"))
        assert len(files) == count, f"{family}: {len(files)} != {count}"


def test_every_file_validates(tmp_path: Path) -> None:
    generate_suite("core", 42, tmp_path)
    scenarios = load_suite(tmp_path / "core")
    assert len(scenarios) == sum(COUNTS.values())
    for s in scenarios:
        load_scenario(tmp_path / "core" / s.family / f"{s.scenario_id}.yaml")


def _in_range(x: float, lo: float, hi: float, tol: float = 1e-3) -> bool:
    return lo - tol <= x <= hi + tol


def test_sampled_parameters_in_range(tmp_path: Path) -> None:
    generate_suite("core", 42, tmp_path)
    scenarios = load_suite(tmp_path / "core")
    for s in scenarios:
        p = s.parameters
        if s.family == "cut_in":
            assert _in_range(p["ego_speed_mps"], 15.0, 22.0)
            assert _in_range(p["initial_gap_m"], 15.0, 30.0)
            assert _in_range(p["speed_delta_mps"], -5.0, 1.0)
            assert _in_range(p["trigger_gap_m"], 5.0, 18.0)
            assert _in_range(p["lateral_speed_mps"], 0.6, 1.5)
        elif s.family == "ped_occluded":
            assert _in_range(p["ego_speed_mps"], 8.0, 14.0)
            assert _in_range(p["occluder_x_m"], 40.0, 70.0)
            assert _in_range(p["ped_speed_mps"], 1.0, 2.5)
            assert _in_range(p["trigger_offset_m"], 12.0, 30.0)
        elif s.family == "weather_ramp":
            assert _in_range(p["ego_speed_mps"], 14.0, 20.0)
            assert _in_range(p["initial_gap_m"], 45.0, 70.0)
            assert _in_range(p["lead_speed_mps"], 8.0, 12.0)
            assert _in_range(p["visibility_end_m"], 15.0, 45.0)
            assert _in_range(p["friction_end"], 0.25, 0.5)
        elif s.family == "hard_brake":
            assert _in_range(p["ego_speed_mps"], 15.0, 22.0)
            assert _in_range(p["initial_gap_m"], 12.0, 35.0)
            assert _in_range(p["lead_speed_delta_mps"], 0.0, 3.0)
            assert _in_range(p["brake_decel_mps2"], -8.0, -3.5)
            assert _in_range(p["brake_trigger_time_s"], 2.0, 5.0)
