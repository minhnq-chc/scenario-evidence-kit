"""Original deterministic keyword templates; no model service is called."""
import random
import unicodedata

from .validation import KINDS, require_valid

VERSION = "0.1.0-template-1"


def generate(description: str, count: int = 3, seed: int = 42,
             map_name: str = "DemoStraight", kind: str | None = None) -> list[dict]:
    if type(description) is not str or not 1 <= len(description.strip()) <= 4000:
        raise ValueError("Description must contain 1 to 4000 characters")
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("Count must be between 1 and 20")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be an unsigned 32-bit integer")
    if kind is not None and kind not in KINDS:
        raise ValueError("Unsupported maneuver kind")
    words = "".join(c for c in unicodedata.normalize("NFD", description.lower())
                    if unicodedata.category(c) != "Mn").replace("đ", "d")
    inferred = "cut_in"
    if any(w in words for w in ("pedestrian", "cross", "nguoi di bo", "bang qua", "qua duong")):
        inferred = "pedestrian_crossing"
    elif any(w in words for w in ("brak", "phanh", "thang gap", "giam toc")):
        inferred = "lead_brake"
    weather = next((v for v, keys in [("rain", ("rain", "mua")), ("fog", ("fog", "suong")),
                                     ("night", ("night", "ban dem"))] if any(k in words for k in keys)), "clear")
    rng = random.Random(seed)
    results = []
    for index in range(count):
        chosen = kind or inferred
        pedestrian = chosen == "pedestrian_crossing"
        child_seed = seed if index == 0 else rng.randrange(2**32)
        actor = {"id": "challenger", "kind": "pedestrian" if pedestrian else "car",
                 "speed_mps": round(rng.uniform(1, 1.8) if pedestrian else rng.uniform(7, 12), 3),
                 "start_x_m": round(rng.uniform(18, 35), 3),
                 "start_y_m": -3.5 if pedestrian else 3.5 if chosen == "cut_in" else 0}
        s = {"id": f"case-{seed}-{index + 1}-{chosen}", "title": f"{chosen.replace('_', ' ').title()} {index + 1}",
             "description": description, "map_name": map_name, "kind": chosen, "seed": child_seed,
             "duration_s": 12, "weather": weather, "ego_speed_mps": round(rng.uniform(10, 15), 3),
             "actors": [actor], "parameters": {"trigger_s": 3, "lane_width_m": 3.5,
                                             "maneuver_duration_s": 3, "deceleration_mps2": 3}}
        require_valid(s)
        results.append(s)
    return results
