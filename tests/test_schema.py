"""Schema round-trip, forbidden-extras, and float-rounding tests (spec 10)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from avsb.schema.io import round_floats, write_yaml
from avsb.schema.scenario import ScenarioDefinition, load_scenario


FIXTURE = Path(__file__).parent / "data" / "example_cut_in.yaml"


def test_fixture_loads_and_round_trips(tmp_path: Path) -> None:
    scen = load_scenario(FIXTURE)
    assert scen.family == "cut_in"
    assert scen.scenario_id == "core-cutin-0001"
    # Round-trip.
    out = tmp_path / "roundtrip.yaml"
    write_yaml(out, scen)
    scen2 = load_scenario(out)
    assert scen2 == scen


def test_extra_field_rejected(tmp_path: Path) -> None:
    text = FIXTURE.read_text()
    data = yaml.safe_load(text)
    data["extra_bogus"] = 1
    p = tmp_path / "extra.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=True))
    with pytest.raises(ValidationError):
        load_scenario(p)


def test_bad_type_rejected(tmp_path: Path) -> None:
    text = FIXTURE.read_text()
    data = yaml.safe_load(text)
    data["ego"]["initial"]["speed_mps"] = "fast"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=True))
    with pytest.raises(ValidationError):
        load_scenario(p)


def test_round_floats_idempotent() -> None:
    obj = {"a": 1.234567, "b": [2.987654, {"c": 3.14159}], "d": True, "e": "x"}
    rounded = round_floats(obj, 4)
    rounded2 = round_floats(rounded, 4)
    assert rounded == rounded2
    assert rounded["a"] == 1.2346
    assert rounded["d"] is True
    assert rounded["e"] == "x"


def test_actor_id_ego_forbidden(tmp_path: Path) -> None:
    text = FIXTURE.read_text()
    data = yaml.safe_load(text)
    data["actors"][0]["actor_id"] = "ego"
    p = tmp_path / "ego_actor.yaml"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError):
        load_scenario(p)
