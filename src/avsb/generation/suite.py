"""Suite assembly: bind family generators into named suites (spec 5.9)."""

from __future__ import annotations

from pathlib import Path

from avsb.generation.base import FamilyGenerator, generate_family
from avsb.generation.cut_in import CutInGenerator
from avsb.generation.hard_brake import HardBrakeGenerator
from avsb.generation.pedestrian import PedOccludedGenerator
from avsb.generation.weather import WeatherRampGenerator

SUITES: dict[str, list[FamilyGenerator]] = {
    "core": [
        CutInGenerator(),
        PedOccludedGenerator(),
        WeatherRampGenerator(),
        HardBrakeGenerator(),
    ],
}


def generate_suite(
    suite: str, seed: int, root: Path | str
) -> list[Path]:
    """Run every family generator for a suite; return sorted list of YAML paths."""
    if suite not in SUITES:
        raise KeyError(f"unknown suite {suite!r}; known: {list(SUITES)}")
    all_paths: list[Path] = []
    for gen in SUITES[suite]:
        all_paths.extend(generate_family(gen, suite, seed, root))
    return sorted(all_paths)
