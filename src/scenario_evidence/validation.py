"""Bounded JSON model validation; PASS is only the workbench's offline subset."""
import hashlib
import json
import math
import re

KINDS = ("cut_in", "lead_brake", "pedestrian_crossing")
WEATHER = ("clear", "rain", "fog", "night")
MAX_JSON_BYTES = 64_000
FIELDS = {"id", "title", "description", "map_name", "kind", "seed", "duration_s",
          "weather", "ego_speed_mps", "actors", "parameters"}
ACTOR_FIELDS = {"id", "kind", "speed_mps", "start_x_m", "start_y_m"}
PARAMETERS = {"trigger_s", "lane_width_m", "maneuver_duration_s", "deceleration_mps2", "actor_ref"}


def canonical(value):
    """Reject deep/cyclic/non-JSON objects before serialization and hashing."""
    budget = [0, 0]

    def walk(item, depth=0):
        budget[0] += 1
        if depth > 12 or budget[0] > 4000:
            raise ValueError("JSON nesting or item limit exceeded")
        if type(item) is dict:
            if any(type(k) is not str for k in item):
                raise ValueError("JSON object keys must be strings")
            for key, v in item.items():
                walk(key, depth + 1)
                walk(v, depth + 1)
        elif type(item) is list:
            for v in item:
                walk(v, depth + 1)
        elif type(item) is str:
            if len(item) > 16_000 or any(ord(c) < 32 and c not in "\t\r\n" for c in item):
                raise ValueError("String length or control character limit exceeded")
            if any(0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in item):
                raise ValueError("String contains invalid Unicode/XML characters")
            budget[1] += len(item.encode("utf-8"))
            if budget[1] > MAX_JSON_BYTES:
                raise ValueError("JSON text budget exceeded")
        elif item is None or type(item) is bool or type(item) is int:
            if type(item) is int and item.bit_length() > 128:
                raise ValueError("Integer too large")
        elif type(item) is float and math.isfinite(item):
            pass
        else:
            raise ValueError("Only finite JSON values are supported")

    walk(value)
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds 64000 bytes")
    return encoded


def fingerprint(scenario: dict) -> str:
    return hashlib.sha256(canonical(scenario).encode("utf-8")).hexdigest()


def validate(scenario: dict) -> dict:
    checks = []

    def check(name, ok, message, unsupported=False):
        checks.append({"name": name, "status": "PASS" if ok else "UNSUPPORTED" if unsupported else "FAIL",
                       "message": message})

    def number(value, low, high):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high

    def text(value, size, identifier=False):
        return (type(value) is str and 0 < len(value.strip()) <= size
                and (not identifier or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", value) is not None))

    try:
        digest = fingerprint(scenario)
    except (ValueError, TypeError, RecursionError):
        return {"status": "FAIL", "checks": [{"name": "json", "status": "FAIL",
                "message": "Input must be bounded finite JSON"}], "fingerprint": ""}
    if type(scenario) is not dict:
        return {"status": "FAIL", "checks": [{"name": "structure", "status": "FAIL",
                "message": "Scenario must be an object"}], "fingerprint": digest}
    s = scenario
    check("fields", FIELDS <= s.keys(), "All scenario fields required")
    check("supported_fields", not s.keys() - FIELDS, "Unknown scenario fields are unsupported", True)
    for key, size, identifier in [("id", 80, True), ("title", 200, False),
                                  ("description", 4000, False), ("map_name", 80, True)]:
        check(key, text(s.get(key), size, identifier), f"{key}: nonempty bounded string")
    check("kind", s.get("kind") in KINDS, "Supported maneuver kind", True)
    check("weather", s.get("weather") in WEATHER, "Supported weather label", True)
    check("seed", type(s.get("seed")) is int and 0 <= s["seed"] <= 2**32 - 1, "32-bit unsigned seed")
    duration = s.get("duration_s")
    check("duration_s", number(duration, 2, 120), "Duration between 2 and 120 seconds")
    check("ego_speed_mps", number(s.get("ego_speed_mps"), 0, 60), "Ego speed between 0 and 60 m/s")
    actors = s.get("actors")
    # Single challenger is deliberate: preview/export never silently omit actors.
    check("actors", type(actors) is list and len(actors) == 1, "Exactly one challenger supported")
    actor = actors[0] if type(actors) is list and len(actors) == 1 and type(actors[0]) is dict else {}
    check("actor_fields", actor.keys() == ACTOR_FIELDS, "Exact challenger field set")
    check("actor_id", text(actor.get("id"), 80, True) and actor.get("id") != "ego", "Unique actor ID, excluding ego")
    check("actor_kind", actor.get("kind") in ("car", "motorcycle", "pedestrian"), "Supported actor kind", True)
    check("actor_speed", number(actor.get("speed_mps"), 0, 60), "Actor speed between 0 and 60 m/s")
    for key in ("start_x_m", "start_y_m"):
        check(key, number(actor.get(key), -1000, 1000), f"{key} between -1000 and 1000 metres")
    p = s.get("parameters")
    check("parameters", type(p) is dict, "Parameters must be an object")
    p = p if type(p) is dict else {}
    check("parameter_fields", not p.keys() - PARAMETERS, "Unknown maneuver parameters unsupported", True)
    check("trigger_s", number(p.get("trigger_s"), 0, duration if number(duration, 2, 120) else 0),
          "Trigger within scenario duration")
    check("lane_width_m", number(p.get("lane_width_m"), 2, 5), "Lane width between 2 and 5 metres")
    check("actor_ref", p.get("actor_ref", actor.get("id")) == actor.get("id"), "Actor reference resolves")
    move = p.get("maneuver_duration_s", 3)
    check("maneuver_duration_s", number(move, 1, 20), "Maneuver duration between 1 and 20 seconds")
    if number(duration, 2, 120) and number(p.get("trigger_s"), 0, 120) and number(move, 1, 20):
        check("maneuver_window", p["trigger_s"] + move <= duration, "Maneuver fits scenario duration")
    check("deceleration_mps2", number(p.get("deceleration_mps2", 3), 0.1, 10), "Deceleration between 0.1 and 10 m/s²")
    if s.get("kind") == "pedestrian_crossing":
        check("pedestrian", actor.get("kind") == "pedestrian" and number(actor.get("speed_mps"), 0.1, 3),
              "Crossing requires a walking pedestrian at 0.1 to 3 m/s")
    elif s.get("kind") in ("cut_in", "lead_brake"):
        check("vehicle", actor.get("kind") in ("car", "motorcycle"), "Vehicle maneuver requires vehicle")
    statuses = {c["status"] for c in checks}
    status = "FAIL" if "FAIL" in statuses else "UNSUPPORTED" if "UNSUPPORTED" in statuses else "PASS"
    return {"status": status, "checks": checks, "fingerprint": digest}


def require_valid(scenario):
    result = validate(scenario)
    if result["status"] != "PASS":
        raise ValueError("Invalid or unsupported scenario: " + "; ".join(
            c["message"] for c in result["checks"] if c["status"] != "PASS"))
    return result
