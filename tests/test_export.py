"""OpenSCENARIO export tests (spec 10, 5.8)."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from avsb.export.xosc import UnsupportedFamilyError, export_scenario
from avsb.schema.scenario import load_scenario


FIXTURE = Path(__file__).parent / "data" / "example_cut_in.yaml"


def test_export_cut_in_parses(tmp_path: Path) -> None:
    scen = load_scenario(FIXTURE)
    out = tmp_path / "out.xosc"
    export_scenario(scen, out)
    tree = ET.parse(out)
    root = tree.getroot()
    assert root.tag == "OpenSCENARIO"
    # Storyboard present.
    sb = root.find("Storyboard")
    assert sb is not None
    # LaneChangeAction present.
    lca = root.findall(".//LaneChangeAction")
    assert len(lca) >= 1


def test_unsupported_family_raises(tmp_path: Path) -> None:
    scen = load_scenario(FIXTURE).model_copy(update={"family": "ped_occluded"})
    with pytest.raises(UnsupportedFamilyError):
        export_scenario(scen, tmp_path / "bad.xosc")
