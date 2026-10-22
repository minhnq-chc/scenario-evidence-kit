"""Original, deliberately narrow OpenSCENARIO XML 1.0 writer/reader.

Subset: two inline entities (ego vehicle and challenger), world coordinates,
initial speeds/positions, one timed polyline following action for challenger,
fixed environment presets and simulation-time stop. Metadata is a string
ParameterDeclaration holding the bounded scenario JSON. Import accepts ONLY this
writer's semantic tree (formatting/attribute order may differ); it regenerates
and compares every node/attribute so no unknown behavior can be dropped.

No XSD validator is run, catalogs/maps are not resolved, and no simulator
compatibility is claimed. Trajectories are 5 Hz piecewise linear approximations.
Public reference: https://releases.asam.net/OpenSCENARIO/1.0.0/Model-Documentation/
RenderedXsdOutput.html (consulted 2026-10-22; no schema copied or bundled).
"""
import json
import math
import xml.etree.ElementTree as ET

from .kinematics import preview
from .validation import canonical, require_valid

MAX_XML_BYTES = 512_000


def node(parent, tag, **attributes):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attributes.items()})


def position(parent, x, y, heading=0):
    pos = node(parent, "Position")
    node(pos, "WorldPosition", x=x, y=y, z=0, h=heading, p=0, r=0)


def bounding_box(parent, pedestrian=False):
    box = node(parent, "BoundingBox")
    node(box, "Center", x=0, y=0, z=0.9)
    node(box, "Dimensions", width=0.6 if pedestrian else 1.8,
         length=0.6 if pedestrian else 4.5, height=1.8 if pedestrian else 1.5)


def entity(parent, name, kind):
    obj = node(parent, "ScenarioObject", name=name)
    if kind == "pedestrian":
        model = node(obj, "Pedestrian", name="generic-pedestrian", model="generic", mass=75,
                     pedestrianCategory="pedestrian")
        bounding_box(model, True)
    else:
        model = node(obj, "Vehicle", name=f"generic-{kind}", vehicleCategory=kind)
        bounding_box(model)
        node(model, "Performance", maxSpeed=60, maxAcceleration=5, maxDeceleration=10)
        axles = node(model, "Axles")
        for tag, x in (("FrontAxle", 2.7), ("RearAxle", 0)):
            node(axles, tag, maxSteering=0.5, wheelDiameter=0.6, trackWidth=1.6, positionX=x, positionZ=0.3)
    node(model, "Properties")


def trigger(parent, tag, time):
    group = node(node(parent, tag), "ConditionGroup")
    condition = node(group, "Condition", name=f"{tag}-time", delay=0, conditionEdge="none")
    node(node(condition, "ByValueCondition"), "SimulationTimeCondition", value=time, rule="greaterThan")


def export_xosc(scenario: dict) -> str:
    require_valid(scenario)
    root = ET.Element("OpenSCENARIO")
    node(root, "FileHeader", revMajor=1, revMinor=0, date="2026-01-01T00:00:00Z",
         description=scenario["title"], author="scenario-evidence-kit")
    declarations = node(root, "ParameterDeclarations")
    node(declarations, "ParameterDeclaration", name="sek_scenario_v1", parameterType="string",
         value=canonical(scenario))
    node(root, "CatalogLocations")
    node(root, "RoadNetwork")
    # A synthetic name is metadata, not a verified OpenDRIVE file.
    # No LogicFile is emitted: resolving an actual map is a simulator integration task.
    entities = node(root, "Entities")
    actor = scenario["actors"][0]
    entity(entities, "ego", "car")
    entity(entities, actor["id"], actor["kind"])
    board = node(root, "Storyboard")
    actions = node(node(board, "Init"), "Actions")
    environment = node(node(node(actions, "GlobalAction"), "EnvironmentAction"), "Environment", name="preset")
    weather = scenario["weather"]
    node(environment, "TimeOfDay", animation="false",
         dateTime="2026-01-01T23:00:00Z" if weather == "night" else "2026-01-01T12:00:00Z")
    atmosphere = node(environment, "Weather", cloudState="rainy" if weather == "rain" else "free")
    node(atmosphere, "Sun", intensity=0 if weather == "night" else 0.8, azimuth=0,
         elevation=-0.2 if weather == "night" else 1.0)
    node(atmosphere, "Fog", visualRange=80 if weather == "fog" else 100000)
    node(atmosphere, "Precipitation", precipitationType="rain" if weather == "rain" else "dry",
         intensity=0.5 if weather == "rain" else 0)
    node(environment, "RoadCondition", frictionScaleFactor=0.7 if weather == "rain" else 1)
    pedestrian = scenario["kind"] == "pedestrian_crossing"
    for name, x, y, speed, heading in [
        ("ego", 0, 0, scenario["ego_speed_mps"], 0),
        (actor["id"], actor["start_x_m"], actor["start_y_m"],
         0 if pedestrian else actor["speed_mps"], math.pi / 2 if pedestrian else 0),
    ]:
        private = node(actions, "Private", entityRef=name)
        position(node(node(private, "PrivateAction"), "TeleportAction"), x, y, heading)
        speed_action = node(node(node(private, "PrivateAction"), "LongitudinalAction"), "SpeedAction")
        node(speed_action, "SpeedActionDynamics", dynamicsDimension="time", dynamicsShape="step", value=0)
        node(node(speed_action, "SpeedActionTarget"), "AbsoluteTargetSpeed", value=speed)
    story = node(board, "Story", name="illustrative-maneuver")
    act = node(story, "Act", name="maneuver")
    group = node(act, "ManeuverGroup", name="challenger-motion", maximumExecutionCount=1)
    node(node(group, "Actors", selectTriggeringEntities="false"), "EntityRef", entityRef=actor["id"])
    maneuver = node(group, "Maneuver", name=scenario["kind"])
    event = node(maneuver, "Event", name="trajectory", priority="overwrite", maximumExecutionCount=1)
    follow = node(node(node(node(event, "Action", name="follow"), "PrivateAction"), "RoutingAction"),
                  "FollowTrajectoryAction")
    trajectory = node(follow, "Trajectory", name="kinematic-preview", closed="false")
    polyline = node(node(trajectory, "Shape"), "Polyline")
    samples = preview(scenario)
    for index, sample in enumerate(samples):
        other = samples[min(index + 1, len(samples) - 1)]
        dx, dy = other["actor_x"] - sample["actor_x"], other["actor_y"] - sample["actor_y"]
        heading = math.atan2(dy, dx) if dx or dy else math.pi / 2 if pedestrian else 0
        position(node(polyline, "Vertex", time=sample["t"]), sample["actor_x"], sample["actor_y"], heading)
    node(node(follow, "TimeReference"), "Timing", domainAbsoluteRelative="absolute", scale=1, offset=0)
    node(follow, "TrajectoryFollowingMode", followingMode="position")
    trigger(event, "StartTrigger", 0)
    trigger(act, "StartTrigger", 0)
    node(act, "StopTrigger")
    trigger(board, "StopTrigger", scenario["duration_s"])
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def import_xosc(xml: str) -> dict:
    if type(xml) is not str:
        raise ValueError("XML must be text")
    try:
        size = len(xml.encode("utf-8"))
    except UnicodeError as exc:
        raise ValueError("Invalid XML Unicode") from exc
    if size > MAX_XML_BYTES or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DTD/entities prohibited or XML size limit exceeded")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError("Malformed XML") from exc
    # Iterative bounds prevent recursion/resource abuse during tree comparison.
    pending, count = [(root, 0)], 0
    while pending:
        element, depth = pending.pop()
        count += 1
        if count > 5000 or depth > 30:
            raise ValueError("XML element/depth limit exceeded")
        pending.extend((child, depth + 1) for child in element)
    metadata = root.findall("./ParameterDeclarations/ParameterDeclaration")
    if root.tag != "OpenSCENARIO" or len(metadata) != 1 or metadata[0].get("name") != "sek_scenario_v1":
        raise ValueError("Unsupported XML: only SEK v1 exported subset can be imported")
    try:
        s = json.loads(metadata[0].get("value", ""))
        require_valid(s)
        expected = ET.fromstring(export_xosc(s))
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Invalid scenario metadata") from exc

    def signature(element):
        return (element.tag, sorted(element.attrib.items()), (element.text or "").strip(),
                (element.tail or "").strip(), tuple(signature(child) for child in element))

    if signature(root) != signature(expected):
        raise ValueError("Unsupported or modified XML feature; no elements/attributes may be discarded")
    return s
