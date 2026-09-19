"""Suite assembly: bind family generators into named suites (spec 5.9)."""

from __future__ import annotations

from pathlib import Path

from avsb.generation.base import FamilyGenerator, generate_family
from avsb.generation.cut_in import CutInGenerator
from avsb.generation.hard_brake import HardBrakeGenerator
from avsb.generation.pedestrian import PedOccludedGenerator
from avsb.generation.weather import WeatherRampGenerator


def _families() -> list[FamilyGenerator]:
    """The four families of spec 5.9, with their binding counts 16, 16, 14, 14."""
    return [
        CutInGenerator(),
        PedOccludedGenerator(),
        WeatherRampGenerator(),
        HardBrakeGenerator(),
    ]


#: Named suites. A suite name is a label for the output directory and the
#: scenario id prefix; every suite draws the same four families, so a holdout
#: suite differs from `core` only by its seed.
SUITES: dict[str, list[FamilyGenerator]] = {
    "core": _families(),
    "holdout": _families(),
}


def generate_suite(
    suite: str, seed: int, root: Path | str
) -> list[Path]:
    """Run every family generator for a suite; return sorted list of YAML paths."""
    if not suite or "/" in suite:
        raise KeyError(f"invalid suite name {suite!r}")
    generators = SUITES.get(suite) or _families()
    all_paths: list[Path] = []
    for gen in generators:
        all_paths.extend(generate_family(gen, suite, seed, root))
    return sorted(all_paths)
