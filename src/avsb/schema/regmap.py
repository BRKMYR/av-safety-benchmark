"""Regulatory mapping schema (spec section 5.5).

The `relation` field is Literal["informative"] on purpose: the type system
itself forbids stronger claims. The mapping is loaded from a hand-authored
YAML file bundled with the package and rendered into the report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard: str
    clause: str
    relation: Literal["informative"] = "informative"
    note: str = ""


class RegEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["metric", "family"]
    target: str  # metric field name or family slug
    title: str
    references: list[RegReference] = Field(min_length=1)


class RegulatoryMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    disclaimer: str
    entries: list[RegEntry] = Field(min_length=1)
