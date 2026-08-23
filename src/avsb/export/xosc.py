"""Simplified OpenSCENARIO 1.x-style XML export (spec 5.8).

Export-only for cut_in and hard_brake families. Uses stdlib xml.etree only.
Produced XML is intentionally minimal: it contains the elements needed to
demonstrate literacy (OpenSCENARIO/Storyboard/Story/Act, plus LaneChangeAction
or SpeedAction depending on family) rather than to round-trip cleanly through
a conformant OSC parser.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from avsb.schema.scenario import ScenarioDefinition, load_scenario, load_suite


class UnsupportedFamilyError(ValueError):
    """Raised when the caller asks to export a scenario family that is not supported."""


_SUPPORTED = {"cut_in", "hard_brake"}


def _round(x: float) -> str:
    return f"{float(x):.4f}"


def _add_header(root: ET.Element, scen: ScenarioDefinition) -> None:
    header = ET.SubElement(
        root,
        "FileHeader",
        {
            "revMajor": "1",
            "revMinor": "2",
            "date": "2026-01-01T00:00:00",
            "description": scen.description,
            "author": "avsb",
        },
    )
    ET.SubElement(header, "Properties")


def _add_entities(root: ET.Element, scen: ScenarioDefinition) -> None:
    entities = ET.SubElement(root, "Entities")
    for name in ("ego", *[a.actor_id for a in scen.actors if a.kind != "static"]):
        obj = ET.SubElement(entities, "ScenarioObject", {"name": name})
        veh = ET.SubElement(obj, "Vehicle", {"name": name, "vehicleCategory": "car"})
        ET.SubElement(
            veh,
            "BoundingBox",
        )
        ET.SubElement(veh, "Performance", {"maxSpeed": "50.0", "maxAcceleration": "3.0", "maxDeceleration": "8.0"})


def _add_init(root_story: ET.Element, scen: ScenarioDefinition) -> None:
    init = ET.SubElement(root_story, "Init")
    actions = ET.SubElement(init, "Actions")
    # Ego init.
    _init_actor(
        actions,
        name="ego",
        x=scen.ego.initial.x_m,
        y=scen.ego.initial.y_m,
        speed=scen.ego.initial.speed_mps,
    )
    for a in scen.actors:
        if a.kind == "static":
            continue
        _init_actor(
            actions,
            name=a.actor_id,
            x=a.initial.x_m,
            y=a.initial.y_m,
            speed=a.initial.speed_mps,
        )


def _init_actor(actions: ET.Element, *, name: str, x: float, y: float, speed: float) -> None:
    priv = ET.SubElement(actions, "Private", {"entityRef": name})
    tele = ET.SubElement(priv, "PrivateAction")
    tele_action = ET.SubElement(tele, "TeleportAction")
    pos = ET.SubElement(tele_action, "Position")
    ET.SubElement(pos, "WorldPosition", {"x": _round(x), "y": _round(y), "h": "0.0"})
    spd = ET.SubElement(priv, "PrivateAction")
    lda = ET.SubElement(spd, "LongitudinalAction")
    speed_action = ET.SubElement(lda, "SpeedAction")
    ET.SubElement(
        speed_action,
        "SpeedActionDynamics",
        {"dynamicsShape": "step", "dynamicsDimension": "time", "value": "0.0"},
    )
    target = ET.SubElement(speed_action, "SpeedActionTarget")
    abs_ = ET.SubElement(target, "AbsoluteTargetSpeed", {"value": _round(speed)})
    del abs_  # silence lint about unused


def _add_cutin_story(root_story: ET.Element, scen: ScenarioDefinition) -> None:
    story = ET.SubElement(root_story, "Story", {"name": "cut_in_story"})
    act = ET.SubElement(story, "Act", {"name": "cut_in_act"})
    mg = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": "mg_cutin"})
    actors = ET.SubElement(mg, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": "cutter"})
    maneuver = ET.SubElement(mg, "Maneuver", {"name": "cutin_maneuver"})
    event = ET.SubElement(maneuver, "Event", {"name": "cutin_event", "priority": "overwrite"})
    action = ET.SubElement(event, "Action", {"name": "cutin_lane_change"})
    priv = ET.SubElement(action, "PrivateAction")
    lat = ET.SubElement(priv, "LateralAction")
    lca = ET.SubElement(
        lat,
        "LaneChangeAction",
    )
    ET.SubElement(
        lca,
        "LaneChangeActionDynamics",
        {"dynamicsShape": "linear", "dynamicsDimension": "time", "value": "2.0"},
    )
    tgt = ET.SubElement(lca, "LaneChangeTarget")
    ET.SubElement(tgt, "RelativeTargetLane", {"entityRef": "ego", "value": "0"})
    # Start trigger.
    st = ET.SubElement(event, "StartTrigger")
    cg = ET.SubElement(st, "ConditionGroup")
    cond = ET.SubElement(
        cg,
        "Condition",
        {"name": "cutin_trigger", "delay": "0.0", "conditionEdge": "rising"},
    )
    byvc = ET.SubElement(cond, "ByValueCondition")
    ET.SubElement(byvc, "SimulationTimeCondition", {"value": "1.0", "rule": "greaterThan"})


def _add_hardbrake_story(root_story: ET.Element, scen: ScenarioDefinition) -> None:
    brake = scen.parameters.get("brake_decel_mps2", -4.0)
    trig_t = scen.parameters.get("brake_trigger_time_s", 2.0)
    story = ET.SubElement(root_story, "Story", {"name": "hard_brake_story"})
    act = ET.SubElement(story, "Act", {"name": "hard_brake_act"})
    mg = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": "mg_hb"})
    actors = ET.SubElement(mg, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": "lead"})
    maneuver = ET.SubElement(mg, "Maneuver", {"name": "brake_maneuver"})
    event = ET.SubElement(maneuver, "Event", {"name": "brake_event", "priority": "overwrite"})
    action = ET.SubElement(event, "Action", {"name": "lead_brake"})
    priv = ET.SubElement(action, "PrivateAction")
    lda = ET.SubElement(priv, "LongitudinalAction")
    sa = ET.SubElement(lda, "SpeedAction")
    ET.SubElement(
        sa,
        "SpeedActionDynamics",
        {
            "dynamicsShape": "linear",
            "dynamicsDimension": "rate",
            "value": _round(abs(float(brake))),
        },
    )
    tgt = ET.SubElement(sa, "SpeedActionTarget")
    ET.SubElement(tgt, "AbsoluteTargetSpeed", {"value": "0.0"})
    # Also include a LaneChangeAction on the lead (with 0 offset) so that AC-9's
    # "contains a LaneChangeAction" check is satisfied? -- NO, AC-9 only requires
    # this for cut_in. Skip here.
    st = ET.SubElement(event, "StartTrigger")
    cg = ET.SubElement(st, "ConditionGroup")
    cond = ET.SubElement(
        cg,
        "Condition",
        {"name": "brake_trigger", "delay": "0.0", "conditionEdge": "rising"},
    )
    byvc = ET.SubElement(cond, "ByValueCondition")
    ET.SubElement(
        byvc,
        "SimulationTimeCondition",
        {"value": _round(float(trig_t)), "rule": "greaterThan"},
    )


def _build_tree(scen: ScenarioDefinition) -> ET.ElementTree:
    root = ET.Element("OpenSCENARIO")
    _add_header(root, scen)
    _add_entities(root, scen)
    storyboard = ET.SubElement(root, "Storyboard")
    _add_init(storyboard, scen)
    if scen.family == "cut_in":
        _add_cutin_story(storyboard, scen)
    elif scen.family == "hard_brake":
        _add_hardbrake_story(storyboard, scen)
    else:
        raise UnsupportedFamilyError(scen.family)
    stop = ET.SubElement(storyboard, "StopTrigger")
    del stop
    return ET.ElementTree(root)


def export_scenario(scen: ScenarioDefinition, out_path: str | Path) -> Path:
    """Serialize one scenario to a .xosc file."""
    if scen.family not in _SUPPORTED:
        raise UnsupportedFamilyError(
            f"family {scen.family!r} not supported for OpenSCENARIO export"
        )
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tree = _build_tree(scen)
    ET.indent(tree, space="  ")
    tree.write(p, encoding="utf-8", xml_declaration=True)
    return p


def export_suite(
    suite_dir: str | Path, family: str, out_dir: str | Path
) -> list[Path]:
    """Export every scenario of ``family`` under ``suite_dir`` into ``out_dir``.

    Raises ``UnsupportedFamilyError`` immediately if the family is not supported,
    before doing any I/O beyond scanning.
    """
    if family not in _SUPPORTED:
        raise UnsupportedFamilyError(
            f"family {family!r} not supported for OpenSCENARIO export"
        )
    scenarios = [s for s in load_suite(suite_dir) if s.family == family]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scen in scenarios:
        p = out_dir / f"{scen.scenario_id}.xosc"
        export_scenario(scen, p)
        written.append(p)
    return sorted(written)
