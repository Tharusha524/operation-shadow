"""Generates data/maps/port_calder.json (Mission 5 map: a rainy harbour at dusk).

Run:  .venv\\Scripts\\python.exe tools\\make_port_calder.py
"""
import json
import sys

WATER_Z = -1.3
QUAY_Y = -33.0
PIERS = (90.0, -100.0)


def prop(t, x, y, h=0, z=None, pid=None, hidden=False, **params):
    d = {"type": t, "pos": [x, y] if z is None else [x, y, z], "heading": h}
    if params:
        d["params"] = params
    if pid:
        d["id"] = pid
    if hidden:
        d["hidden"] = True
    return d


props = []
# --- quay wall, water edge and piers ------------------------------------------------------------
for i in range(22):
    props.append(prop("embankment", -420 + i * 40, QUAY_Y, 180, length=40, depth=4))
edges = [-440.0]
for px in sorted(PIERS):
    edges += [px - 2.7, px + 2.7]
edges.append(440.0)
for a, b in zip(edges[0::2], edges[1::2]):
    props.append(prop("invisible_wall", (a + b) / 2, QUAY_Y - 0.6, 0, length=b - a, height=6))
for px in PIERS:
    props.append(prop("pier", px, QUAY_Y, 180, length=40, width=6))
props.append(prop("concrete_pad", -10, -18, 0, width=260, depth=30))

# --- ship, cranes, quay clutter --------------------------------------------------------------
props += [
    prop("cargo_ship", -10, -49, 90, length=96, beam=16, color="blue"),
    prop("gantry_crane", -100, -26, 0),
    prop("gantry_crane", 32, -26, 0),
    prop("jeep", -32, -12, 0),
    prop("truck", -40, -16, 90),
    prop("crate", -25, -19.5, 0, size=1.0),                 # intel: officer's ID card
    prop("jersey_barrier", -30, -10, 0),
    prop("jersey_barrier", -4, -10, 0),
    prop("barrel_group", 4, -22, 0, count=4, color="blue"),
    prop("pallet", 10, -20, 30),
    prop("tire_stack", 14, -24, 0),
]
for x in range(-120, 121, 30):
    props.append(prop("lamp_post", x, -30.5, 0))
# Container yard (east of the officers, west of the piers) and a western yard.
colors = ["rust", "blue", "green", "grey", "red", "rust"]
k = 0
for x in (46, 54, 62):
    for y in (-22, -14, -6):
        props.append(prop("container", x, y, 90, color=colors[k % 6]))
        if (x + y) % 3 != 0:
            props.append(prop("container", x, y, 90, z=2.6, color=colors[(k + 2) % 6]))
        k += 1
for x in (-112, -118):
    for y in (-20, -10, 0):
        props.append(prop("container", x, y, 0, color=colors[k % 6]))
        k += 1

# --- overlook: the harbour master's building (rooftop with stairs) -----------------------------
props.append(prop("barracks", -70, -8, 0, width=12, depth=8, windows=3, roof_stairs=True, interior="none",
                  wall_color="white"))

# --- fish market (dead drop) ---------------------------------------------------------------------
for i, x in enumerate((-104, -96, -88, -80, -72)):
    for j, y in enumerate((24, 34)):
        props.append(prop("market_stall", x, y, 0 if j == 0 else 180))
props += [
    prop("locker_row", -100, 46.5, 0, count=6),
    prop("crate", -80, 40, 0, size=1.0),                    # intel: patrol rota
    prop("barrel_group", -110, 40, 0, count=3),
    prop("tent", -64, 44, 90, color="white"),
    prop("lamp_post", -92, 29, 0),
    prop("lamp_post", -76, 29, 0),
    prop("fence", -86, 52, 0, length=50, barbed=False),
]

# --- harbour office (download terminal, cameras) -------------------------------------------------
props += [
    prop("barracks", 15, 38, 0, width=16, depth=9, windows=4, interior="none", wall_color="concrete"),
    prop("terminal_desk", 19, 41.3, 0),
    prop("locker_row", 10, 41.8, 0, count=4),
    prop("crate_stack", 21.5, 36.0, 0, count=2),
    prop("generator", 27, 40, 90),
    prop("light_pole", 15, 28, 0),
]

# --- warehouses (warehouse 4 = the hostage) ---------------------------------------------------------
props += [
    prop("hangar", 80, 20, 0, length=24, radius=8),
    prop("hangar", 104, 20, 0, length=24, radius=7),
    prop("hangar", 56, 30, 0, length=20, radius=7),
    prop("crate_stack", 75, 28, 0, count=4),
    prop("crate", 86, 28, 0, size=1.0),                     # intel: cargo manifest page
    prop("pallet", 84, 16, 20),
    prop("barrel_group", 74, 12, 0, count=3),
    prop("truck", 92, 0, 160),
    prop("light_pole", 70, 4, 0),
]

# --- town edge to the north (start) ----------------------------------------------------------------
props += [
    prop("road", 0, 64, 0, length=280, width=8),
    prop("road", -40, 20, 90, length=80, width=7),
    prop("townhouse_row", -60, 92, 0),
    prop("townhouse_row", -10, 92, 0),
    prop("townhouse_row", 40, 92, 0),
    prop("house", 85, 90, 0),
    prop("house", -110, 88, 0),
    prop("church", 0, 125, 0),
    prop("jeep", 30, 70, 100),
    prop("truck", -20, 58, 0, covered=True),
    prop("fence", -130, 30, 90, length=120, barbed=False),
    prop("fence", 125, 30, 90, length=120, barbed=False),
]
for x in range(-120, 121, 40):
    props.append(prop("lamp_post", x, 69, 0))

scatter = [
    {"type": "bush", "count": 40, "area": [-130, 60, 130, 140], "min_spacing": 6,
     "exclude": [[-130, 58, 130, 72], [-80, 80, 100, 135]], "params": {"size": [0.8, 1.4]}},
    {"type": "tree_broadleaf", "count": 30, "area": [-300, 140, 300, 400], "min_spacing": 12},
    {"type": "tree_pine", "count": 60, "area": [-430, -30, 430, 430], "min_spacing": 10,
     "exclude": [[-140, -33, 140, 160]], "params": {"height": [9, 14]}},
]

data = {
    "id": "port_calder",
    "name": "Port Calder - Harbour",
    "seed": 5309,
    "player_spawn": {"pos": [-118, 100, 0.0], "heading": -150},
    "atmosphere": {
        "sun_heading": 250, "sun_pitch": 8,
        "sun_color": [0.55, 0.55, 0.62],
        "ambient_color": [0.3, 0.32, 0.38],
        "fill_color": [0.12, 0.13, 0.17],
        "sky_zenith": [0.12, 0.14, 0.18],
        "sky_horizon": [0.36, 0.37, 0.4],
        "fog_color": [0.3, 0.32, 0.36],
        "fog_density": 0.0145,
        "clouds": 0.85,
        "rain": 0.85,
        "grading": {"exposure": 1.55, "saturation": 0.72, "contrast": 1.06, "tint": [0.94, 0.98, 1.06],
                    "shadow_tint": [0.88, 0.94, 1.12], "lift": 0.03, "bloom": 0.7, "bloom_threshold": 0.7,
                    "vignette": 0.5},
    },
    "terrain": {
        "size": 880, "divisions": 80, "play_area": 140,
        "nav_bounds": [-132, -76, 122, 132],
        "floor_z": -40.0,
        "holes": [[-440, -440, 440, QUAY_Y]],
        "land": [[-440, QUAY_Y, 440, 440]],
        "water": {"rect": [-440, -440, 440, QUAY_Y], "z": WATER_Z, "color": [0.3, 0.36, 0.4]},
        "worn_color": [0.62, 0.61, 0.58], "grass_color": [0.5, 0.55, 0.42], "dark_color": [0.4, 0.4, 0.38],
    },
    "points": {
        "view_quay": {"pos": [-70, -8, 3.67], "heading": -110, "pitch": -4},
        "view_market": {"pos": [-90, 10, 0.0], "heading": 10, "pitch": 2},
        "view_office": {"pos": [14, 20, 0.0], "heading": 0, "pitch": 3},
        "view_warehouse": {"pos": [80, -8, 0.0], "heading": 0, "pitch": 4},
        "view_pier": {"pos": [70, -28, 0.0], "heading": -150, "pitch": 0},
    },
    "fires": [],
    "props": props,
    "scatter": scatter,
}
out = sys.argv[1] if len(sys.argv) > 1 else "data/maps/port_calder.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)
print(len(props), "props")
