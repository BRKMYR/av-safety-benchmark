"""Load and validate the packaged regulatory_mapping.yaml (spec 5.5)."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from avsb.schema.regmap import RegulatoryMapping


def _load_from_text(text: str) -> RegulatoryMapping:
    data = yaml.safe_load(text)
    return RegulatoryMapping.model_validate(data)


def load_mapping(path: str | Path | None = None) -> RegulatoryMapping:
    """Load regulatory_mapping.yaml (packaged) or from an explicit path."""
    if path is not None:
        with Path(path).open("r", encoding="utf-8") as fh:
            return _load_from_text(fh.read())
    with resources.files("avsb.regmap").joinpath(
        "regulatory_mapping.yaml"
    ).open("r", encoding="utf-8") as fh:
        return _load_from_text(fh.read())
