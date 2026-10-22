"""Illustrative straight-road 2D motion. No collision/safety/simulator verdict."""
import math

from .validation import require_valid


def preview(scenario: dict) -> list[dict]:
    require_valid(scenario)
    a, p = scenario["actors"][0], scenario["parameters"]
    duration = scenario["duration_s"]
    steps = math.ceil(duration * 5)
    samples = []
    for index in range(steps + 1):
        t = duration * index / steps
        elapsed = max(0, t - p["trigger_s"])
        x = a["start_x_m"] + a["speed_mps"] * t
        y = a["start_y_m"]
        if scenario["kind"] == "cut_in":
            u = min(1, elapsed / p.get("maneuver_duration_s", 3))
            # Quintic smoothstep has continuous zero endpoint velocity and acceleration.
            y *= 1 - (10 * u**3 - 15 * u**4 + 6 * u**5)
        elif scenario["kind"] == "lead_brake":
            deceleration = p.get("deceleration_mps2", 3)
            braking_time = min(elapsed, a["speed_mps"] / deceleration)
            x = (a["start_x_m"] + a["speed_mps"] * min(t, p["trigger_s"])
                 + a["speed_mps"] * braking_time - 0.5 * deceleration * braking_time**2)
        else:
            # Pedestrian waits, accelerates over one second, then walks across +y.
            ramp = min(elapsed, 1)
            x = a["start_x_m"]
            y += a["speed_mps"] * (0.5 * ramp**2 + max(0, elapsed - 1))
        samples.append({"t": round(t, 6), "ego_x": round(scenario["ego_speed_mps"] * t, 6),
                        "ego_y": 0, "actor_x": round(x, 6), "actor_y": round(y, 6)})
    return samples
