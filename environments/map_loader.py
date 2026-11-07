"""Loads level layouts from JSON (data/maps/*.json).

A map file lists props (type, position, heading, params) plus "scatter" rules that
place many props randomly (forests, rocks). The same seed always gives the same map.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


class MapLoadError(Exception):
    """Raised with a readable message when a map file is missing or invalid."""


@dataclass
class PropSpec:
    type: str
    x: float
    y: float
    z: float = 0.0
    heading: float = 0.0
    params: dict = field(default_factory=dict)
    id: str | None = None          # props with an id can be destroyed/restored by missions
    hidden: bool = False           # starts invisible; a mission can show it (e.g. bridge ruins)


@dataclass
class Placement:
    x: float
    y: float
    z: float = 0.0
    heading: float = 0.0
    pitch: float = 0.0


DEFAULT_ATMOSPHERE = {
    "sun_heading": -35.0,
    "sun_pitch": -35.0,
    "sun_color": [1.35, 1.2, 0.98],
    "ambient_color": [0.36, 0.38, 0.44],
    "fill_color": [0.14, 0.16, 0.22],
    "sky_zenith": [0.30, 0.46, 0.68],
    "sky_horizon": [0.80, 0.77, 0.70],
    "fog_color": [0.74, 0.73, 0.68],
    "fog_density": 0.0052,
}

DEFAULT_TERRAIN = {"size": 900.0, "divisions": 90, "play_area": 72.0}


@dataclass
class MapData:
    id: str
    name: str
    seed: int
    player_spawn: Placement
    props: list
    atmosphere: dict
    terrain: dict
    points: dict
    fires: list = field(default_factory=list)      # [(x, y, z, size)] burning cars / buildings


def load_map(path) -> MapData:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MapLoadError(f"Map file not found: {path}") from None
    except (OSError, ValueError) as exc:
        raise MapLoadError(f"Map file {path.name} is not valid JSON: {exc}") from None
    return parse_map(data, source=path.name)


def parse_map(data, source="<map>") -> MapData:
    if not isinstance(data, dict):
        raise MapLoadError(f"{source}: top level must be a JSON object")
    try:
        seed = int(data.get("seed", 1))
        spawn = _placement(data["player_spawn"])
        props = [_prop(p) for p in data.get("props", [])]
        rng = random.Random(seed)
        for rule in data.get("scatter", []):
            props.extend(expand_scatter(rule, rng))
        points = {name: _placement(p) for name, p in data.get("points", {}).items()}
        fires = []
        for f in data.get("fires", []):
            pos = f["pos"]
            fires.append((float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0,
                          float(f.get("size", 1.0))))
    except KeyError as exc:
        raise MapLoadError(f"{source}: missing required field {exc}") from None
    except (TypeError, ValueError) as exc:
        raise MapLoadError(f"{source}: invalid value ({exc})") from None
    atmosphere = dict(DEFAULT_ATMOSPHERE)
    atmosphere.update(data.get("atmosphere", {}))
    terrain = dict(DEFAULT_TERRAIN)
    terrain.update(data.get("terrain", {}))
    return MapData(
        id=str(data.get("id", "unnamed")),
        name=str(data.get("name", "Unnamed Area")),
        seed=seed,
        player_spawn=spawn,
        props=props,
        atmosphere=atmosphere,
        terrain=terrain,
        points=points,
        fires=fires,
    )


def _placement(p) -> Placement:
    pos = p["pos"]
    return Placement(float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0,
                     float(p.get("heading", 0.0)), float(p.get("pitch", 0.0)))


def _prop(p) -> PropSpec:
    pos = p["pos"]
    params = p.get("params", {})
    if not isinstance(params, dict):
        raise TypeError("params must be an object")
    params = dict(params)
    hidden = bool(p.get("hidden", params.pop("hidden", False)))
    return PropSpec(str(p["type"]), float(pos[0]), float(pos[1]),
                    float(p.get("z", pos[2] if len(pos) > 2 else 0.0)), float(p.get("heading", 0.0)), params,
                    p.get("id"), hidden)


def _inside(x, y, rect):
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def expand_scatter(rule, rng) -> list:
    """Place `count` props randomly inside `area`, avoiding `exclude` rectangles and keeping spacing."""
    ptype = str(rule["type"])
    count = int(rule["count"])
    area = [float(v) for v in rule["area"]]
    excludes = [[float(v) for v in r] for r in rule.get("exclude", [])]
    spacing = float(rule.get("min_spacing", 0.0))
    params_spec = rule.get("params", {})
    placed = []
    cell = max(spacing, 1.0)
    grid = {}
    attempts = 0
    while len(placed) < count and attempts < count * 40:
        attempts += 1
        x = rng.uniform(area[0], area[2])
        y = rng.uniform(area[1], area[3])
        if any(_inside(x, y, r) for r in excludes):
            continue
        if spacing > 0:
            gx, gy = int(x // cell), int(y // cell)
            too_close = False
            for ix in range(gx - 1, gx + 2):
                for iy in range(gy - 1, gy + 2):
                    for (ox, oy) in grid.get((ix, iy), ()):
                        if (ox - x) ** 2 + (oy - y) ** 2 < spacing * spacing:
                            too_close = True
                            break
            if too_close:
                continue
            grid.setdefault((gx, gy), []).append((x, y))
        params = {}
        for key, value in params_spec.items():
            if isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
                params[key] = rng.uniform(float(value[0]), float(value[1]))
            else:
                params[key] = value
        placed.append(PropSpec(ptype, x, y, 0.0, rng.uniform(0.0, 360.0), params))
    return placed
