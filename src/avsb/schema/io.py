"""Canonical (byte-identical) serialization for schema models.

Every YAML and JSON writer in avsb goes through this module. Determinism
requirements (see spec section 5.1 and AC-3/AC-6):

- Floats are rounded to 4 decimals before serialization.
- YAML output uses sort_keys=True and default_flow_style=False.
- JSON output uses sort_keys=True and (",", ": ") separators.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

_M = TypeVar("_M", bound=BaseModel)


def round_floats(obj: Any, ndigits: int = 4) -> Any:
    """Recursively round floats in a JSON-compatible structure.

    Handles dicts, lists, tuples, and scalars. Booleans are left alone
    (bool is a subclass of int in Python; we explicitly guard against that).
    NaN and infinity are not expected in serialized outputs; if present they
    pass through unchanged (yaml.safe_dump will refuse them, surfacing the bug).
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, ndigits) for v in obj]
    return obj


def _dump(model: BaseModel, ndigits: int = 4) -> Any:
    """model.model_dump(mode='json') with all floats rounded."""
    return round_floats(model.model_dump(mode="json"), ndigits)


def write_yaml(path: str | Path, model: BaseModel, ndigits: int = 4) -> Path:
    """Write a model as canonical YAML. Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _dump(model, ndigits)
    text = yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)
    p.write_text(text, encoding="utf-8")
    return p


def read_yaml(path: str | Path, model_cls: type[_M]) -> _M:
    """Read a YAML file and validate against a Pydantic model class."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return model_cls.model_validate(data)


def write_json(path: str | Path, model: BaseModel, ndigits: int = 4) -> Path:
    """Write a model as canonical JSON. Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _dump(model, ndigits)
    text = json.dumps(payload, sort_keys=True, indent=2)
    p.write_text(text, encoding="utf-8")
    return p


def read_json(path: str | Path, model_cls: type[_M]) -> _M:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return model_cls.model_validate(data)
