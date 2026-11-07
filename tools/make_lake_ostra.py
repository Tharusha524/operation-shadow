"""Generates data/maps/lake_ostra.json (Mission 6 map: Mira Sol's villa above a mountain lake).

Run:  .venv\\Scripts\\python.exe tools\\make_lake_ostra.py
"""
import json
import sys

WATER_Z = -1.3
SHORE_Y = -66.0
ROAD_Y = -50.0
PIER_X = -380.0


def prop(t, x, y, h=0, z=None, pid=None, **params):
    d = {"type": t, "pos": [x, y] if z is None else [x, y, z], "heading": h}
    if params:
        d["params"] = params
    if pid:
        d["id"] = pid
    return d


props = []
# --- lake shore ----------------------------------------------------------------------------------
for i in range(22):
    props.append(prop("embankment", -420 + i * 40, SHORE_Y, 180, length=40, depth=4))
for a, b in ((-440.0, PIER_X - 2.7), (PIER_X + 2.7, 440.0)):
    props.append(prop("invisible_wall", (a + b) / 2, SHORE_Y - 0.6, 0, length=b - a, height=6))
props += [
    prop("pier", PIER_X, SHORE_Y, 180, length=30, width=6),
    prop("cargo_ship", -392, -92, 0, length=44, beam=11, color="white"),      # the lake ferry
]

# --- roads ---------------------------------------------------------------------------------------
props += [
    prop("road", 200, 112, 90, length=54, width=6),
    prop("road", 200, 17.5, 90, length=135, width=8),
    prop("road", -90.5, ROAD_Y, 0, length=589, width=8),
]
for x in range(-360, 200, 50):
    props.append(prop("lamp_post", x, ROAD_Y - 6, 0))

# --- the villa estate ------------------------------------------------------------------------------
for x, length in ((172.5, 45), (227.5, 45)):
    props.append(prop("fence", x, 85, 0, length=length, barbed=False))        # south wall with the gate
props += [
    prop("fence", 200, 190, 0, length=100, barbed=False),
    prop("fence", 150, 137.5, 90, length=105, barbed=False),
    prop("fence", 250, 127.5, 90, length=85, barbed=False),                   # gap at y 170-180 (garden gate)
    prop("fence", 250, 185, 90, length=10, barbed=False),
    prop("guard_booth", 190, 80, 0),
    prop("house", 200, 150, 0, width=18, depth=11, height=3.4, windows=3, wall_color="white", interior="home"),
    prop("house", 222, 152, 0, width=9, depth=8, height=3.2, windows=2, wall_color="white", interior="none"),
    prop("barracks", 232, 140, 0, width=8, depth=6, windows=1, door_width=3.0, interior="none", wall_color="white"),
    prop("concrete_pad", 200, 136, 0, width=26, depth=12),
    prop("fountain", 200, 118, 0, radius=2.6),
    prop("crate_stack", 186, 136, 0, count=4),                                # armoury crates
    prop("crate", 212, 134, 0, size=1.0),
    prop("jersey_barrier", 192, 128, 0),
    prop("jersey_barrier", 208, 128, 0),
    prop("sandbag_wall", 190, 92, 0, length=5),
    prop("sandbag_wall", 210, 92, 0, length=5),
    prop("sandbag_wall", 200, 108, 0, length=6),
    prop("lamp_post", 188, 118, 0),
    prop("lamp_post", 212, 118, 0),
    prop("jeep", 172, 128, 40),
    prop("tree_broadleaf", 170, 110, 0),
    prop("tree_broadleaf", 226, 104, 0),
    prop("tree_broadleaf", 168, 170, 0),
    prop("tree_broadleaf", 236, 176, 0),
]
for i in range(9):
    props.append(prop("bush", 182 + i * 4.5, 126.5, 0, size=0.8))

# --- mortar position on the eastern slope -------------------------------------------------------
props += [
    prop("mortar_pit", 320, 230, 200),
    prop("sandbag_wall", 312, 224, 30, length=5),
    prop("sandbag_wall", 328, 222, -30, length=5),
    prop("crate_stack", 326, 236, 0, count=3),
    prop("crate", 326, 232, 0, size=1.0),                     # intel: Harrow's orders
    prop("tent", 334, 240, 30),
    prop("rock", 300, 214, 0, size=2.2),
    prop("rock", 288, 200, 0, size=1.8),
]

# --- the lake road: obstacles, ambushes and the roadblock ------------------------------------------
props += [
    prop("jersey_barrier", 120, ROAD_Y + 2.4, 0),
    prop("jersey_barrier", 60, ROAD_Y - 2.4, 0),
    prop("jeep", 10, ROAD_Y + 7, 90, burnt=True),
    prop("sandbag_wall", -60, ROAD_Y + 9, 0, length=5),
    prop("sandbag_wall", -150, ROAD_Y + 9, 0, length=5),
    prop("truck", -180, ROAD_Y + 8, 95),
    # Roadblock: ram it at speed.
    prop("jersey_barrier", -260, ROAD_Y - 2.4, 90, pid="roadblock_a"),
    prop("jersey_barrier", -260, ROAD_Y + 1.0, 90, pid="roadblock_b"),
    prop("jersey_barrier", -260, ROAD_Y + 4.4, 90, pid="roadblock_c"),
    prop("truck", -263, ROAD_Y + 9, 0),
    prop("truck", -263, ROAD_Y - 8.5, 0),
    prop("rock", -262, ROAD_Y + 14, 0, size=3.0),
]
# Solid rock face along the north side of the road near the roadblock.
for i in range(14):
    props.append(prop("rock", -330 + i * 24, ROAD_Y + 24, 0, size=2.4))

# --- ferry village ------------------------------------------------------------------------------------
props += [
    prop("house", -340, -24, 180),
    prop("house", -400, -22, 180),
    prop("house", -370, -14, 180),
    prop("market_stall", -358, -42, 0),
    prop("barrel_group", -392, -42, 0, count=3),
]

# --- mountains around the lake (scenery) ------------------------------------------------------------
for x, y, r, h in ((-300, 320, 150, 90), (-40, 360, 170, 110), (240, 400, 180, 120), (420, 240, 140, 100),
                   (-420, 160, 130, 80), (-260, -420, 170, 90), (60, -430, 190, 110), (340, -400, 170, 100)):
    props.append(prop("hill", x, y, 0, radius=r, height=h))

scatter = [
    {"type": "tree_pine", "count": 220, "area": [-430, -36, 430, 280], "min_spacing": 8,
     "exclude": [[140, 75, 262, 200], [190, -60, 210, 90], [-440, -60, 440, -38], [280, 190, 350, 255],
                 [-420, -46, -330, 0]], "params": {"height": [10, 16]}},
    {"type": "bush", "count": 90, "area": [-430, -36, 430, 200], "min_spacing": 4,
     "exclude": [[140, 75, 262, 200], [190, -60, 210, 90], [-440, -60, 440, -38]], "params": {"size": [0.8, 1.5]}},
    {"type": "rock", "count": 40, "area": [-430, -30, 430, 200], "min_spacing": 12,
     "exclude": [[140, 75, 262, 200], [190, -60, 210, 90], [280, 190, 350, 255]], "params": {"size": [0.8, 1.8]}},
]

data = {
    "id": "lake_ostra",
    "name": "Lake Ostra - The Sol Villa",
    "seed": 6151,
    "player_spawn": {"pos": [200, 70, 0.0], "heading": 0},
    "atmosphere": {
        "sun_heading": 215, "sun_pitch": 28,
        "sun_color": [1.5, 1.28, 0.98],
        "ambient_color": [0.42, 0.45, 0.52],
        "fill_color": [0.16, 0.18, 0.24],
        "sky_zenith": [0.2, 0.38, 0.68],
        "sky_horizon": [0.8, 0.8, 0.76],
        "fog_color": [0.68, 0.72, 0.76],
        "fog_density": 0.0028,
        "clouds": 0.35,
        "grading": {"exposure": 1.1, "saturation": 1.14, "contrast": 1.06, "tint": [1.03, 1.0, 0.96],
                    "bloom": 0.4, "bloom_threshold": 0.95, "vignette": 0.3},
    },
    "terrain": {
        "size": 880, "divisions": 80, "play_area": 90,
        "nav_bounds": [140, 70, 345, 250],
        "floor_z": -40.0,
        "holes": [[-440, -440, 440, SHORE_Y]],
        "land": [[-440, SHORE_Y, 440, 440]],
        "water": {"rect": [-440, -440, 440, SHORE_Y], "z": WATER_Z, "color": [0.36, 0.56, 0.62]},
        "worn_color": [0.74, 0.7, 0.58], "grass_color": [0.5, 0.62, 0.36], "dark_color": [0.42, 0.46, 0.32],
    },
    "points": {
        "view_villa": {"pos": [200, 100, 0.0], "heading": 0, "pitch": 3},
        "view_terrace": {"pos": [186, 128, 0.0], "heading": -30, "pitch": 2},
        "view_road": {"pos": [40, -44, 0.0], "heading": 90, "pitch": 0},
        "view_roadblock": {"pos": [-225, -50, 0.0], "heading": 90, "pitch": 0},
        "view_ferry": {"pos": [-345, -52, 0.0], "heading": 110, "pitch": 2},
    },
    "fires": [],
    "props": props,
    "scatter": scatter,
}
out = sys.argv[1] if len(sys.argv) > 1 else "data/maps/lake_ostra.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
print(len(props), "props")
