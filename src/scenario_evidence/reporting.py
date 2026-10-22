"""Evidence separates offline input checks from unperformed simulator/XSD work."""
import hashlib
import html
import json
import math

from .generation import VERSION
from .validation import canonical, validate
from .xmlio import export_xosc


def build_report(scenario: dict, execution: dict | None = None) -> dict:
    result = validate(scenario)
    digest = None
    if result["status"] == "PASS":
        digest = hashlib.sha256(export_xosc(scenario).encode("utf-8")).hexdigest()
    # Only the explicit local ScenarioRunner adapter evidence envelope is accepted.
    # The API owns actually launching/parsing the configured runner. This function
    # does not independently authenticate evidence; expose that provenance clearly.
    claimed = None
    simulation = {"status": "NOT_RUN", "message": "No verified simulator execution in offline core"}
    if execution is not None:
        if type(execution) is not dict:
            raise ValueError("Execution evidence must be an object")
        canonical(execution)
        claimed = execution
        if execution.get("status") == "ERROR":
            simulation = {"status": "ERROR", "message": str(execution.get("message", "Runner error"))}
        elif (execution.get("status") in ("PASS", "FAIL")
              and execution.get("source") == "ScenarioRunner JSON"
              and execution.get("runner") == "scenario_runner.py"
              and type(execution.get("criteria")) is list
              and type(execution.get("runner_report")) is str
              and bool(execution["runner_report"])
              and type(execution.get("elapsed_s")) in (float, int)
              and math.isfinite(execution["elapsed_s"]) and execution["elapsed_s"] >= 0):
            simulation = {"status": execution["status"], "source": execution["source"],
                          "message": "Reported by configured ScenarioRunner adapter; not independently verified by core",
                          "criteria": execution["criteria"], "runner_report": execution["runner_report"],
                          "elapsed_s": execution["elapsed_s"]}
    structural = "FAIL" if any(c["status"] == "FAIL" for c in result["checks"]) else "PASS"
    return {"input_hash": result["fingerprint"], "seed": scenario.get("seed") if type(scenario) is dict else None,
            "generator_version": VERSION, "validation": result, "checks": result["checks"],
            "structural": {"status": structural, "message": "Bounded JSON and scenario invariants"},
            "subset": {"status": result["status"], "message": "Offline SEK supported subset only"},
            "xsd": {"status": "NOT_RUN", "message": "No OpenSCENARIO XSD validation performed"},
            "simulation": simulation,
            "execution_claim": claimed, "export_sha256": digest,
            "limitations": ["Synthetic straight-road kinematics; no collision or ADS safety verdict",
                            "Map existence and simulator compatibility have not been checked",
                            "Only the explicit ScenarioRunner adapter envelope can report simulator PASS/FAIL; "
                            "core does not independently authenticate runner evidence"]}


def render_html(report):
    """A script-free standalone report, safe for untrusted scenario titles/text."""
    body = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Scenario evidence</title><style>body{font:16px system-ui;max-width:960px;'
            'margin:40px auto;padding:0 20px;color:#18202b}pre{white-space:pre-wrap;'
            'overflow-wrap:anywhere;background:#f1f4f8;padding:20px}</style>'
            '<h1>Scenario evidence</h1><p>Offline subset checks are separate from simulator evidence. '
            'XSD validation has not run. Runner evidence provenance is listed below.</p><pre>' + body + '</pre></html>')
