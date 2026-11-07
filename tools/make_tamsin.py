"""Generates data/maps/tamsin_river.json (Mission 4 map)."""
import json
import sys

WATER_Z = -1.3
BRIDGE_X = 200.0
GAP = (195.3, 204.7)


def prop(t, x, y, h=0, z=None, pid=None, **params):
    d = {"type": t, "pos": [x, y] if z is None else [x, y, z], "heading": h}
    if params:
        d["params"] = params
    if pid:
        d["id"] = pid
    return d


props = []
# --- river banks --------------------------------------------------------------------------------
for i in range(22):
    x = -420 + i * 40
    props.append(prop("embankment", x, 22, 180, length=40, depth=4))
    props.append(prop("embankment", x, -22, 0, length=40, depth=4))
for y in (22.6, -22.6):
    props.append(prop("invisible_wall", (-440 + GAP[0]) / 2, y, 0, length=GAP[0] + 440, height=6))
    props.append(prop("invisible_wall", (GAP[1] + 440) / 2, y, 0, length=440 - GAP[1], height=6))
# Shown when the bridge falls, so nobody walks off the broken end.
props.append(prop("invisible_wall", BRIDGE_X, 31.0, 0, pid="bridge_end_wall", length=12, height=6, hidden=True))

# --- the bridge ---------------------------------------------------------------------------------
for pid, y in (("span_s", -20), ("span_m", 0), ("span_n", 20)):
    props.append(prop("bridge_span", BRIDGE_X, y, 0, pid=pid, length=20, width=10))
    props.append(prop("bridge_ruin", BRIDGE_X, y, 0, pid=pid.replace("span", "ruin"), length=20, width=10, hidden=True))
for y in (-10, 10):
    props.append(prop("bridge_pillar", BRIDGE_X, y, 0, height=9, width=8))
props.append(prop("road", BRIDGE_X, 145, 90, length=230, width=8))
props.append(prop("road", BRIDGE_X, -185, 90, length=310, width=8))
props.append(prop("road", 150, 150, 0, length=100, width=6))

# --- north bank compound (x 130..270, y 25..130) ------------------------------------------------
props += [
    prop("searchlight_tower", 184, 28, 0, height=5, beam_heading=165, beam_pitch=-18, beam_length=55),
    prop("searchlight_tower", 228, 28, 0, height=5, beam_heading=200, beam_pitch=-18, beam_length=55),
    prop("sandbag_wall", 190.5, 37, 0, length=5),
    prop("sandbag_wall", 209.5, 37, 0, length=5),
    prop("jersey_barrier", 197.5, 40, 0),
    prop("jersey_barrier", 202.5, 42, 0),
    prop("guard_booth", 212, 44, 90),
    prop("sandbag_bunker", 184, 44, 180),          # detonator position
    prop("crate", 182.5, 45.5, 0, size=0.9),
    prop("barracks", 160, 72, 0, width=16, depth=8, windows=4),
    prop("barracks", 245, 62, 90, width=14, depth=8, windows=3),
    prop("container", 172, 50, 0, color="green"),
    prop("container", 172, 52.6, 0, color="rust"),
    prop("container", 224, 48, 90, color="blue"),
    prop("container", 150, 42, 30, color="rust"),
    prop("aa_gun", 228, 96, 0, pid="aa_gun"),
    prop("tent", 182, 110, 0),
    prop("tent", 252, 104, 90),
    prop("radio_mast", 208, 122, 0, height=18),
    prop("generator", 236, 82, 0),
    prop("fuel_tank", 150, 100, 90, length=7),
    prop("watchtower", 140, 112, 45, height=4),
    prop("crate_stack", 192, 60, 0, count=5),
    prop("crate_stack", 214, 70, 90, count=4),
    prop("crate", 226, 52.5, 0, size=1.0),          # intel 2
    prop("crate", 236, 99, 0, size=1.0),            # intel 3
    prop("crate", 196, 52, 0, size=1.2),            # launcher cache
    prop("crate", 196, 53.4, 0, size=1.0),
    prop("barrel_group", 168, 58, 0, count=4),
    prop("barrel_group", 232, 74, 0, count=3),
    prop("truck", 186, 86, 90),
    prop("jeep", 222, 112, 20),
    prop("light_pole", 200, 50, 0),
    prop("light_pole", 160, 92, 0),
    prop("fence", 130, 80, 90, length=100),
    prop("fence", 270, 80, 90, length=100),
    prop("fence", 165, 132, 0, length=70),
    prop("fence", 235, 132, 0, length=70),
    prop("helipad", 214, 196, 0, size=18),
    prop("sandbag_wall", 205, 182, 0, length=4),
    prop("sandbag_wall", 224, 184, 0, length=4),
]
# --- slipway / drone launch point --------------------------------------------------------------
props += [
    prop("slipway", 110, 22, 180, length=12, width=6),
    prop("crate", 104, 34, 0, size=1.0),             # intel 1
    prop("crate_stack", 116, 36, 0, count=3),
    prop("container", 100, 42, 90, color="green"),
    prop("tree_pine", 122, 44, 0, height=12),
]
# --- the route up-river (bank outposts seen from the boat) -------------------------------------
props += [
    prop("sandbag_wall", -224, 30, 180, length=5),
    prop("sandbag_wall", -216, 30, 180, length=5),
    prop("watchtower", -232, 36, 180, height=4),
    prop("mg_nest", -220, 34, 180),
    prop("tent", -214, 44, 0),
    prop("searchlight_tower", -120, -28, 180, height=5, beam_heading=180, beam_pitch=-15, beam_length=55),
    prop("sandbag_wall", -112, -29, 0, length=5),
    prop("barracks", -110, -44, 0, width=12, depth=7, windows=3),
    prop("searchlight_tower", -20, 28, 0, height=5, beam_heading=200, beam_pitch=-16, beam_length=55),
    prop("sandbag_wall", -28, 30, 180, length=5),
    prop("container", -12, 34, 0, color="rust"),
]
# --- south bank staging area (enemy armour column comes from here) ----------------------------
props += [
    prop("sandbag_wall", 190, -44, 0, length=5),
    prop("sandbag_wall", 210, -44, 0, length=5),
    prop("truck", 220, -70, 0),
    prop("truck", 178, -82, 0),
    prop("tent", 228, -96, 90),
    prop("container", 168, -60, 90, color="blue"),
    prop("house", 150, -110, 0),
    prop("house", 250, -120, 90),
]

scatter = [
    {"type": "tree_pine", "count": 140, "area": [-430, 26, 430, 420], "min_spacing": 7,
     "exclude": [[125, 22, 275, 140], [192, 22, 208, 420], [140, 140, 290, 230], [-245, 25, -200, 55],
                 [-35, 25, 0, 45], [90, 22, 128, 50]], "params": {"height": [9, 15]}},
    {"type": "tree_pine", "count": 140, "area": [-430, -420, 430, -26], "min_spacing": 7,
     "exclude": [[140, -140, 270, -26], [192, -420, 208, -26], [-130, -55, -95, -26]],
     "params": {"height": [9, 15]}},
    {"type": "bush", "count": 120, "area": [-430, 26, 430, 300], "min_spacing": 3,
     "exclude": [[125, 22, 275, 140], [192, 22, 208, 300], [140, 140, 290, 230]], "params": {"size": [0.8, 1.6]}},
    {"type": "bush", "count": 80, "area": [-430, -300, 430, -26], "min_spacing": 3,
     "exclude": [[140, -140, 270, -26], [192, -300, 208, -26]], "params": {"size": [0.8, 1.6]}},
    {"type": "rock", "count": 30, "area": [-430, 30, 430, 300], "min_spacing": 8,
     "exclude": [[125, 22, 275, 230], [90, 22, 128, 50]], "params": {"size": [0.6, 1.6]}},
]

data = {
    "id": "tamsin_river",
    "name": "Tamsin River - Varn Crossing",
    "seed": 4471,
    "player_spawn": {"pos": [110, 30, 0.0], "heading": -90},
    "atmosphere": {
        "sun_heading": 210, "sun_pitch": 38,
        "sun_color": [0.6, 0.68, 0.92],
        "ambient_color": [0.2, 0.22, 0.32],
        "fill_color": [0.07, 0.08, 0.13],
        "sky_zenith": [0.02, 0.03, 0.07],
        "sky_horizon": [0.1, 0.12, 0.2],
        "fog_color": [0.07, 0.085, 0.13],
        "fog_density": 0.009,
        "clouds": 0.35,
        "grading": {"exposure": 2.1, "saturation": 0.8, "contrast": 1.08, "tint": [0.9, 0.96, 1.12],
                    "shadow_tint": [0.85, 0.92, 1.2], "lift": 0.035, "bloom": 0.85, "bloom_threshold": 0.55,
                    "vignette": 0.55},
    },
    "terrain": {
        "size": 880, "divisions": 80, "play_area": 120,
        "nav_bounds": [95, -70, 285, 215],
        "floor_z": -40.0,
        "holes": [[-440, -22, 440, 22]],
        "land": [[-440, 22, 440, 440], [-440, -440, 440, -22]],
        "water": {"rect": [-440, -22, 440, 22], "z": WATER_Z, "color": [0.34, 0.42, 0.5]},
        "worn_color": [0.5, 0.5, 0.42], "grass_color": [0.42, 0.5, 0.34], "dark_color": [0.3, 0.3, 0.26],
    },
    "points": {
        "view_river": {"pos": [-250, 30, 1.0], "heading": -100, "pitch": -4},
        "view_bridge": {"pos": [150, 30, 0.0], "heading": -110, "pitch": 2},
        "view_compound": {"pos": [180, 40, 0.0], "heading": -40, "pitch": 3},
        "view_lz": {"pos": [214, 160, 0.0], "heading": 0, "pitch": 2},
    },
    "fires": [
        {"pos": [204, 46, 0.9], "size": 0.7},
        {"pos": [166, 60, 0.9], "size": 0.7},
        {"pos": [-218, 40, 0.9], "size": 0.7},
        {"pos": [-104, -36, 0.9], "size": 0.7},
    ],
    "props": props,
    "scatter": scatter,
}
out = sys.argv[1] if len(sys.argv) > 1 else "data/maps/tamsin_river.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
print(len(props), "props")
