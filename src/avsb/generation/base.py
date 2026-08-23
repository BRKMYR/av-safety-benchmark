"""Base classes and helpers shared by all family generators (spec section 5.9)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

import numpy as np

from avsb.schema.io import write_yaml
from avsb.schema.scenario import ScenarioDefinition


class FamilyGenerator(ABC):
    """Abstract base for scenario family generators.

    Subclasses set ``family``, ``count``, ``offset`` and implement ``sample``
    (draw one parameter vector uniformly from the family's ranges) and
    ``build`` (materialize a parameter vector into a ScenarioDefinition).
    """

    family: ClassVar[str]
    count: ClassVar[int]
    offset: ClassVar[int]

    @abstractmethod
    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        """Return one parameter dict drawn from the family's uniform ranges."""

    @abstractmethod
    def build(self, params: dict[str, float], idx: int, seed: int) -> ScenarioDefinition:
        """Materialize a parameter vector into a full ScenarioDefinition."""


def _scenario_id(suite: str, family: str, idx: int) -> str:
    """Canonical scenario id per spec 5.1: {suite}-{family_slug}-{4-digit index}."""
    slug = family.replace("_", "")
    if family == "ped_occluded":
        slug = "ped"
    elif family == "weather_ramp":
        slug = "weather"
    elif family == "hard_brake":
        slug = "hardbrake"
    elif family == "cut_in":
        slug = "cutin"
    return f"{suite}-{slug}-{idx:04d}"


def generate_family(
    gen: FamilyGenerator,
    suite: str,
    seed: int,
    out_dir: Path | str,
) -> list[Path]:
    """Generate all scenarios for one family; write YAMLs; return paths sorted."""
    rng = np.random.default_rng(seed * 1000 + gen.offset)
    root = Path(out_dir) / suite / gen.family
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(1, gen.count + 1):
        params = gen.sample(rng)
        scen = gen.build(params, i, seed)
        p = root / f"{scen.scenario_id}.yaml"
        write_yaml(p, scen)
        paths.append(p)
    return sorted(paths)


def uniform(rng: np.random.Generator, low: float, high: float) -> float:
    """Draw one uniform float in [low, high) and round to 4 decimals."""
    return float(round(rng.uniform(low, high), 4))


def uniform_int(rng: np.random.Generator, low: int, high: int) -> int:
    """Draw one integer in [low, high] inclusive."""
    return int(rng.integers(low, high + 1))
