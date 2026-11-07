"""Procedural vehicle models (placeholders until real models are added).

Every builder returns a dict of NodePaths: "root" plus moving parts such as "rotor",
"tail_rotor", "turret" or "rotor1".."rotor4". Front of every vehicle = local +Y.
"""
from __future__ import annotations

import math

from panda3d.core import NodePath

from environments.geometry import MeshBuilder

DARK_GREY = (0.2, 0.21, 0.22)
OLIVE = (0.33, 0.36, 0.24)
GLASS = (0.06, 0.08, 0.1)
BLACK = (0.05, 0.05, 0.05)
STEEL = (0.45, 0.46, 0.47)
RED_LIGHT = (1.0, 0.1, 0.08)
BOAT_GREY = (0.32, 0.34, 0.36)
TUBE = (0.12, 0.12, 0.13)


def _part(parent, materials, name, fn):
    mb = MeshBuilder(materials.uv_scales())
    fn(mb)
    return mb.build(parent, materials, name=name)


def build_helicopter(materials, attack=True):
    root = NodePath("helicopter")
    body = DARK_GREY if attack else OLIVE
    s = 1.0 if attack else 1.3

    def hull(mb):
        mb.ellipsoid("metal", 0, 0, 1.3 * s, 1.0 * s, 3.0 * s, 1.1 * s, body, rings=8, segments=14)
        mb.ellipsoid("paint", 0, 1.8 * s, 1.6 * s, 0.75 * s, 1.2 * s, 0.7 * s, GLASS, rings=6, segments=12)
        mb.cylinder_between("metal", (0, -2.5 * s, 1.5 * s), (0, -8.0 * s, 1.9 * s), 0.38 * s, body,
                            radius_end=0.16 * s, segments=10)
        mb.box("metal", 0, -8.0 * s, 1.7 * s, 0.1, 1.0 * s, 1.7 * s, body)
        mb.box("metal", 0, -7.7 * s, 1.95 * s, 2.0 * s, 0.6 * s, 0.08, body)            # stabiliser
        mb.box("metal", 0, -0.4 * s, 2.2 * s, 1.0 * s, 2.4 * s, 0.6 * s, body)           # engine housing
        mb.cylinder("metal", 0, -0.2 * s, 2.75 * s, 0.18, 0.4, BLACK, segments=8)           # rotor mast
        for sx in (-1, 1):
            mb.cylinder_between("metal", (sx * 0.9 * s, -1.8 * s, 0.05), (sx * 0.9 * s, 2.0 * s, 0.05), 0.06, BLACK,
                                segments=6, caps=True)
            for y in (-1.0, 1.0):
                mb.cylinder_between("metal", (sx * 0.9 * s, y * s, 0.05), (sx * 0.55 * s, y * s, 0.6 * s), 0.05, BLACK,
                                    segments=5)
        if attack:
            mb.box("metal", 0, -0.3, 1.25, 4.2, 0.8, 0.12, body)                            # stub wings
            for sx in (-1, 1):
                mb.cylinder_between("metal", (sx * 1.7, -0.9, 0.95), (sx * 1.7, 0.6, 0.95), 0.22, BLACK,
                                    segments=10, caps=True)
            mb.cylinder_between("metal", (0, 2.8, 0.55), (0, 3.9, 0.55), 0.05, BLACK, segments=6)
            mb.ellipsoid("metal", 0, 2.75, 0.62, 0.22, 0.22, 0.2, BLACK, rings=4, segments=8)
        else:
            for sx in (-1, 1):
                mb.box("paint", sx * 1.27 * s, 0.2, 1.2 * s, 0.04, 2.0, 1.1, GLASS)         # side door openings
        mb.ellipsoid("emissive", 0, -8.3 * s, 2.7 * s, 0.07, 0.07, 0.07, RED_LIGHT, rings=3, segments=5)

    _part(root, materials, "heli_hull", hull)
    rotor = root.attach_new_node("rotor")
    rotor.set_pos(0, -0.2 * s, 3.05 * s)

    def blades(mb):
        mb.cylinder("metal", 0, 0, 0, 0.25, 0.18, BLACK, segments=8)
        for a in (0, 90, 180, 270) if attack else (0, 72, 144, 216, 288):
            with mb.place(0, 0, 0.08, a):
                mb.box("metal", 0, 3.6 * s, 0, 0.32, 7.0 * s, 0.05, BLACK)

    _part(rotor, materials, "blades", blades)
    tail = root.attach_new_node("tail_rotor")
    tail.set_pos(0.22, -8.0 * s, 2.3 * s)

    def tail_blades(mb):
        mb.box("metal", 0, 0, -0.7 * s, 0.04, 0.16, 1.4 * s, BLACK)          # vertical blade
        mb.box("metal", 0, 0, -0.08, 0.04, 1.4 * s, 0.16, BLACK)             # horizontal blade

    _part(tail, materials, "tail_blades", tail_blades)
    return {"root": root, "rotor": rotor, "tail_rotor": tail}


def build_tank(materials, color=OLIVE):
    root = NodePath("tank")
    dark = tuple(c * 0.6 for c in color)

    def hull(mb):
        mb.box("metal", 0, 0, 0.45, 3.2, 7.0, 1.1, color)
        mb.box("metal", 0, 3.2, 0.6, 3.0, 1.0, 0.8, color)
        for sx in (-1, 1):
            mb.box("metal", sx * 1.75, 0, 0.0, 0.7, 7.2, 0.95, dark)
            for i in range(7):
                mb.cylinder_between("metal", (sx * 1.42, -2.9 + i * 0.97, 0.42), (sx * 2.12, -2.9 + i * 0.97, 0.42),
                                    0.38, tuple(c * 0.8 for c in dark), segments=10, caps=True)
            mb.box("metal", sx * 1.75, 0, 0.95, 0.85, 7.2, 0.06, color)
        mb.box("metal", 0, -3.4, 1.0, 2.4, 0.3, 0.35, dark)                                # engine deck
        for sx in (-0.9, 0.9):
            mb.box("emissive", sx, 3.72, 1.0, 0.25, 0.05, 0.15, (1.0, 0.85, 0.55))         # headlights

    _part(root, materials, "tank_hull", hull)
    turret = root.attach_new_node("turret")
    turret.set_pos(0, -0.4, 1.55)

    def turret_fn(mb):
        mb.cylinder("metal", 0, 0, 0, 1.55, 0.75, color, segments=14, radius_top=1.25)
        mb.box("metal", 0, 0.9, 0.15, 1.2, 1.4, 0.5, color)
        mb.cylinder_between("metal", (0, 1.4, 0.4), (0, 5.6, 0.46), 0.09, dark, segments=10, caps=True)
        mb.cylinder_between("metal", (0, 5.0, 0.45), (0, 5.6, 0.46), 0.13, dark, segments=10, caps=True)
        mb.cylinder("metal", 0.5, -0.4, 0.75, 0.3, 0.25, dark, segments=8)
        mb.cylinder_between("metal", (-0.5, -0.2, 1.0), (-0.5, 0.4, 1.0), 0.04, BLACK, segments=5)  # MG

    _part(turret, materials, "tank_turret", turret_fn)
    return {"root": root, "turret": turret}


def build_boat(materials, patrol=False):
    root = NodePath("boat")
    hull_col = (0.18, 0.19, 0.2) if patrol else BOAT_GREY

    def hull(mb):
        profile = [(1.1, 0.25), (0.6, -0.35), (-0.6, -0.35), (-1.1, 0.25), (-1.0, 0.6), (1.0, 0.6)]
        profile = [(-p[0], p[1]) for p in profile]
        with mb.place(0, 0, 0, 90):                        # local X of the extrusion -> boat +Y (bow)
            mb.extrude_x("metal", profile, -3.4, 2.6, hull_col)
        mb.ellipsoid("metal", 0, 2.7, 0.15, 1.0, 1.2, 0.45, hull_col, rings=5, segments=10)  # bow
        for sx in (-1, 1):
            mb.cylinder_between("fabric", (sx * 1.15, -3.3, 0.6), (sx * 1.15, 2.6, 0.6), 0.33, TUBE, segments=10,
                                caps=True)
        mb.ellipsoid("fabric", 0, 2.9, 0.6, 1.2, 0.6, 0.33, TUBE, rings=5, segments=10)
        mb.box("metal", 0, 0.2, 0.6, 0.8, 0.7, 0.9, DARK_GREY)                            # console
        mb.box("paint", 0, 0.58, 1.5, 0.9, 0.04, 0.45, GLASS)
        mb.box("metal", 0, -3.6, 0.3, 0.5, 0.45, 1.0, BLACK)                              # outboard engine
        mb.box("fabric", 0, -1.4, 0.6, 1.4, 0.8, 0.4, (0.15, 0.15, 0.14))                 # bench
        if patrol:
            mb.cylinder("metal", 0, 2.0, 0.6, 0.06, 0.8, BLACK, segments=6)
            mb.box("metal", 0, 2.2, 1.35, 0.15, 0.9, 0.18, BLACK)
            mb.cylinder_between("metal", (0, 2.6, 1.42), (0, 3.4, 1.42), 0.03, BLACK, segments=6)
            mb.box("emissive", 0, -3.6, 1.35, 0.1, 0.1, 0.1, RED_LIGHT)

    _part(root, materials, "boat_hull", hull)
    return {"root": root}


def build_drone(materials, kamikaze=True):
    root = NodePath("drone")
    body = (0.15, 0.15, 0.16) if kamikaze else (0.3, 0.32, 0.28)

    def frame(mb):
        mb.box("metal", 0, 0, -0.08, 0.28, 0.4, 0.16, body)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.cylinder_between("metal", (0, 0, 0), (sx * 0.32, sy * 0.32, 0.02), 0.025, body, segments=5)
                mb.cylinder("metal", sx * 0.32, sy * 0.32, -0.02, 0.03, 0.06, BLACK, segments=6)
        mb.ellipsoid("emissive", 0, 0.21, -0.05, 0.03, 0.03, 0.03, RED_LIGHT if kamikaze else (0.3, 1.0, 0.4),
                     rings=3, segments=5)
        if kamikaze:
            mb.cylinder_between("metal", (0, -0.1, -0.2), (0, 0.25, -0.2), 0.06, OLIVE, segments=8, caps=True)  # charge
        else:
            mb.ellipsoid("paint", 0, 0.15, -0.2, 0.06, 0.06, 0.06, GLASS, rings=4, segments=6)                 # camera

    _part(root, materials, "drone_frame", frame)
    parts = {"root": root}
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1)), start=1):
        rotor = root.attach_new_node(f"rotor{i}")
        rotor.set_pos(sx * 0.32, sy * 0.32, 0.05)

        def blade(mb):
            mb.box("metal", 0, 0, 0, 0.3, 0.03, 0.01, BLACK)

        _part(rotor, materials, f"blade{i}", blade)
        parts[f"rotor{i}"] = rotor
    return parts


def build_jeep(materials, enemy=False):
    """The same 4x4 as the map prop, as a moving model."""
    import random
    from environments.props import build_jeep as prop_jeep
    root = NodePath("jeep")

    def body(mb):
        prop_jeep(mb, random.Random(7 if enemy else 3), color=(0.3, 0.3, 0.28) if enemy else "olive",
                  windscreen=enemy)
        if enemy:
            mb.cylinder("metal", 0, -1.0, 1.3, 0.05, 0.8, (0.1, 0.1, 0.1), segments=6)        # gun mount
            mb.box("metal", 0, -0.75, 2.05, 0.12, 0.9, 0.14, (0.1, 0.1, 0.1))

    _part(root, materials, "jeep_body", body)
    return {"root": root}
