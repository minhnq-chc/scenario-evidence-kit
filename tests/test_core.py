"""Original tests for the documented bounded offline interface."""
import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET

import pytest

from scenario_evidence.cli import main
from scenario_evidence.core import (
    build_report,
    export_xosc,
    fingerprint,
    generate,
    import_xosc,
    preview,
    validate,
)
from scenario_evidence.reporting import render_html


@pytest.fixture
def scenario():
    return generate("A car cuts in during rain", count=1)[0]


@pytest.mark.parametrize("description,kind,weather", [
    ("Xe cắt ngang khi trời mưa", "cut_in", "rain"),
    ("Xe trước phanh gấp trong sương mù", "lead_brake", "fog"),
    ("Người đi bộ băng qua đường ban đêm", "pedestrian_crossing", "night"),
    ("Lead vehicle braking", "lead_brake", "clear"),
    ("Pedestrian crossing in rain", "pedestrian_crossing", "rain"),
])
def test_keywords_and_determinism(description, kind, weather):
    first = generate(description, seed=981, count=3)
    assert first == generate(description, seed=981, count=3)
    assert first != generate(description, seed=982, count=3)
    assert len({s["id"] for s in first}) == 3
    assert all(s["kind"] == kind and s["weather"] == weather and validate(s)["status"] == "PASS" for s in first)


@pytest.mark.parametrize("options", [
    {"count": True}, {"count": 0}, {"count": 21}, {"seed": -1}, {"seed": 2**32},
    {"description": ""}, {"description": "a" * 4001}, {"kind": "invalid"},
    {"map_name": "../../private"}, {"map_name": []},
])
def test_generation_bounds(options):
    with pytest.raises(ValueError):
        generate(**({"description": "cut in"} | options))


@pytest.mark.parametrize("key,value", [
    ("duration_s", True), ("duration_s", 121), ("duration_s", float("nan")),
    ("ego_speed_mps", float("inf")), ("ego_speed_mps", -1), ("seed", "42"),
    ("actors", []), ("actors", ["actor"]), ("parameters", None), ("id", "ego<script>"),
    ("description", "bad\x00input"), ("description", "bad\ud800input"),
])
def test_invalid_inputs_fail(scenario, key, value):
    scenario[key] = value
    assert validate(scenario)["status"] == "FAIL"
    with pytest.raises(ValueError):
        export_xosc(scenario)


def test_invalid_actor_reference_and_unknown_parameters(scenario):
    scenario["parameters"]["actor_ref"] = "missing"
    assert validate(scenario)["status"] == "FAIL"
    scenario["parameters"].pop("actor_ref")
    scenario["parameters"]["python"] = "__import__('os')"
    assert validate(scenario)["status"] == "UNSUPPORTED"
    scenario["parameters"].pop("python")
    scenario["actors"][0]["id"] = "ego"
    assert validate(scenario)["status"] == "FAIL"


def test_unknown_fields_not_dropped(scenario):
    scenario["additional_behavior"] = "run command"
    assert validate(scenario)["status"] == "UNSUPPORTED"
    with pytest.raises(ValueError):
        export_xosc(scenario)


def test_hash_canonical_order_and_mutation(scenario):
    assert fingerprint(scenario) == fingerprint(dict(reversed(list(scenario.items()))))
    changed = copy.deepcopy(scenario)
    changed["ego_speed_mps"] += 1
    assert fingerprint(changed) != fingerprint(scenario)


def test_cyclic_deep_and_oversized():
    cyclic = {}
    cyclic["self"] = cyclic
    assert validate(cyclic)["status"] == "FAIL"
    assert validate({"large": "a" * 64001})["status"] == "FAIL"
    assert validate({"k" * 64001: 1})["status"] == "FAIL"
    assert validate([1, 2])["status"] == "FAIL"
    with pytest.raises(ValueError):
        fingerprint({"a": math.nan})


@pytest.mark.parametrize("kind", ["cut_in", "lead_brake", "pedestrian_crossing"])
def test_roundtrip_and_xml_invariants(kind):
    s = generate('An original <scenario> & "quoted" description', count=1, kind=kind)[0]
    s["title"] = "<script>alert(1)</script>"
    xml = export_xosc(s)
    assert xml == export_xosc(s)
    assert import_xosc(xml) == s
    root = ET.fromstring(xml)
    assert root.find("FileHeader").attrib["revMinor"] == "0"
    assert len(root.findall("./Entities/ScenarioObject")) == 2
    refs = {e.get("entityRef") for e in root.iter() if "entityRef" in e.attrib}
    assert refs == {"ego", s["actors"][0]["id"]}
    assert len(root.findall(".//Vertex")) == len(preview(s))
    assert root.find(".//StopTrigger/ConditionGroup/Condition/ByValueCondition/SimulationTimeCondition") is not None
    # XML whitespace and attribute order do not alter supported semantics.
    for element in root.iter():
        element.attrib = dict(reversed(list(element.attrib.items())))
    assert import_xosc(ET.tostring(root, encoding="unicode")) == s


@pytest.mark.parametrize("bad_xml", [
    '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///private">]><OpenSCENARIO>&x;</OpenSCENARIO>',
    '<!ENTITY x "bad"><OpenSCENARIO/>', '<OpenSCENARIO/>', '<OpenSCENARIO>',
    '<OpenSCENARIO>' + '<x>' * 40 + '</x>' * 40 + '</OpenSCENARIO>',
    '<OpenSCENARIO>' + 'x' * 512001 + '</OpenSCENARIO>',
], ids=["external-entity", "entity", "unsupported", "malformed", "deep", "oversized"])
def test_reject_unsupported_xml(bad_xml):
    with pytest.raises(ValueError):
        import_xosc(bad_xml)


@pytest.mark.parametrize("mutation", ["unknown", "attribute", "position", "reference", "version"])
def test_xml_modifications_not_silently_dropped(scenario, mutation):
    root = ET.fromstring(export_xosc(scenario))
    if mutation == "unknown":
        ET.SubElement(root, "CustomCommandAction").text = "execute anything"
    elif mutation == "attribute":
        root.set("extra", "unknown")
    elif mutation == "position":
        root.find(".//WorldPosition").set("x", "999")
    elif mutation == "reference":
        root.find(".//EntityRef").set("entityRef", "missing")
    else:
        root.find("FileHeader").set("revMinor", "2")
    with pytest.raises(ValueError):
        import_xosc(ET.tostring(root, encoding="unicode"))


def test_preview_motion_and_limits():
    for kind in ("cut_in", "lead_brake", "pedestrian_crossing"):
        s = generate("original motion", count=1, kind=kind)[0]
        points = preview(s)
        assert points == preview(s)
        assert points[0]["t"] == 0 and points[-1]["t"] == s["duration_s"]
        assert all(p["ego_x"] >= q["ego_x"] for q, p in zip(points, points[1:]))
        if kind == "cut_in":
            assert points[-1]["actor_y"] == 0
            assert points[0]["actor_y"] == s["actors"][0]["start_y_m"]
        elif kind == "lead_brake":
            assert points[-1]["actor_x"] == points[-2]["actor_x"]
            assert all(p["actor_x"] >= q["actor_x"] for q, p in zip(points, points[1:]))
        else:
            assert len({p["actor_x"] for p in points}) == 1
            assert points[-1]["actor_y"] > points[0]["actor_y"]


def test_evidence_no_fabricated_pass(scenario):
    report = build_report(scenario)
    assert report["input_hash"] == fingerprint(scenario)
    assert report["export_sha256"] == hashlib.sha256(export_xosc(scenario).encode()).hexdigest()
    assert report["subset"]["status"] == report["structural"]["status"] == "PASS"
    assert report["xsd"]["status"] == report["simulation"]["status"] == "NOT_RUN"
    claimed = build_report(scenario, {"status": "PASS", "simulator": "invented"})
    assert claimed["simulation"]["status"] == "NOT_RUN"
    assert claimed["execution_claim"]["status"] == "PASS"
    scenario["ego_speed_mps"] = -10
    invalid = build_report(scenario)
    assert invalid["structural"]["status"] == "FAIL" and invalid["export_sha256"] is None


def test_html_escapes_untrusted_claim(scenario):
    html = render_html(build_report(scenario, {"note": "<script>alert(1)</script>"}))
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_runner_evidence_envelope_and_error(scenario):
    execution = {"status": "PASS", "source": "ScenarioRunner JSON", "criteria": [],
                 "runner_report": "result.json", "runner": "scenario_runner.py", "elapsed_s": 1.2}
    assert build_report(scenario, execution)["simulation"]["status"] == "PASS"
    execution["status"] = "FAIL"
    assert build_report(scenario, execution)["simulation"]["status"] == "FAIL"
    del execution["runner"]
    assert build_report(scenario, execution)["simulation"]["status"] == "NOT_RUN"
    assert build_report(scenario, {"status": "ERROR", "message": "Runner unavailable"})["simulation"]["status"] == "ERROR"


def test_cli_json_and_exit_status(tmp_path, scenario, capsys):
    source, output = tmp_path / "scenario.json", tmp_path / "report.html"
    source.write_text(json.dumps(scenario), encoding="utf-8")
    assert main(["validate", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    assert main(["report", str(source), "--html", "--output", str(output)]) == 0
    assert "NOT_RUN" in output.read_text(encoding="utf-8")
    scenario["duration_s"] = -1
    source.write_text(json.dumps(scenario), encoding="utf-8")
    assert main(["validate", str(source)]) == 1
    with pytest.raises(SystemExit) as exc:
        main(["export", str(source)])
    assert exc.value.code == 2
