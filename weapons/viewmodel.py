"""First-person weapon models ("viewmodels") with hands and animations.

The viewmodel is drawn by a second camera on top of the world (with its depth buffer
cleared), so the gun never pokes through walls - the standard FPS technique.

Models are procedural placeholders. Local model space: barrel along +Y, and the iron-sight
line passes through x=0, z=0, so aiming down sights puts it exactly on the screen centre.
"""
from __future__ import annotations

import math

from panda3d.core import (AmbientLight, Camera, DirectionalLight, NodePath, PerspectiveLens, Vec3)

from environments.geometry import MeshBuilder

GUNMETAL = (0.24, 0.25, 0.26)
POLYMER = (0.32, 0.34, 0.26)
RED_DOT = (1.0, 0.12, 0.08)
OLIVE = (0.33, 0.36, 0.24)
WOOD = (0.45, 0.30, 0.18)
GLOVE = (0.12, 0.11, 0.10)
SLEEVE = (0.34, 0.36, 0.26)
SIGHT = (0.05, 0.05, 0.05)
LENS = (0.15, 0.25, 0.30)


# Smooth painted finishes ("paint" = untextured, slightly glossy) read as machined metal and polymer.
ANODIZED = (0.19, 0.195, 0.205)       # black anodised aluminium
PARKERIZED = (0.3, 0.305, 0.31)       # steel parts
RAIL = (0.14, 0.145, 0.15)
FDE = (0.47, 0.40, 0.29)               # flat dark earth polymer
RUBBER = (0.13, 0.13, 0.13)
BRASS = (0.78, 0.62, 0.30)
TUBE_GREEN = (0.22, 0.25, 0.15)


def _blk(mb, mat, x0, x1, y0, y1, z0, z1, color):
    """Axis-aligned box from its bounds (all six faces)."""
    mb.box(mat, (x0 + x1) / 2, (y0 + y1) / 2, z0, x1 - x0, y1 - y0, z1 - z0, color, bottom=True)


def _side(mb, mat, profile, width, color, x=0.0):
    """Side silhouette [(y, z), ...] (convex) extruded across the gun's width."""
    mb.extrude_x(mat, profile, x - width / 2, x + width / 2, color, double_sided=True)


def _rail(mb, y0, y1, z, width=0.022):
    """Picatinny rail: a base strip with cross slots."""
    _blk(mb, "paint", -width / 2, width / 2, y0, y1, z, z + 0.006, RAIL)
    y = y0 + 0.004
    while y < y1 - 0.004:
        _blk(mb, "paint", -width / 2 - 0.001, width / 2 + 0.001, y, y + 0.0055, z + 0.006, z + 0.0095, RAIL)
        y += 0.010


def _hand(mb, x, y, z, side):
    """Gloved hand closed around a grip: palm, four fingers and a thumb."""
    s = 1 if side == "right" else -1
    mb.ellipsoid("fabric", x - s * 0.006, y - 0.012, z, 0.026, 0.03, 0.04, GLOVE, rings=5, segments=8)
    for i in range(4):                                     # fingers wrap the front of the grip
        fz = z + 0.022 - i * 0.017
        mb.cylinder_between("fabric", (x - s * 0.022, y + 0.004, fz), (x + s * 0.024, y + 0.022, fz - 0.004),
                            0.0085, GLOVE, segments=6, caps=True)
    mb.cylinder_between("fabric", (x - s * 0.02, y - 0.01, z + 0.03), (x - s * 0.026, y + 0.03, z + 0.036),
                        0.009, GLOVE, segments=6, caps=True)     # thumb


def _sleeve(mb, wrist, elbow):
    cuff = (wrist[0], wrist[1] - 0.035, wrist[2] - 0.012)
    mb.cylinder_between("fabric", cuff, (cuff[0], cuff[1] - 0.025, cuff[2] - 0.01), 0.036, GLOVE, segments=10)
    mb.cylinder_between("fabric", cuff, elbow, 0.038, SLEEVE, segments=10, radius_end=0.05)


def _arms(mb, right_hand, left_hand):
    """Gloved hands + sleeves reaching back toward the bottom corners of the screen."""
    rx, ry, rz = right_hand
    _hand(mb, rx, ry, rz, "right")
    _sleeve(mb, (rx + 0.005, ry, rz - 0.01), (rx + 0.1, ry - 0.38, rz - 0.22))
    if left_hand is None:
        return
    lx, ly, lz = left_hand
    _hand(mb, lx, ly, lz, "left")
    _sleeve(mb, (lx - 0.01, ly, lz - 0.01), (lx - 0.17, ly - 0.44, lz - 0.2))


def build_rifle(mb):
    """AR-pattern carbine: flat-top upper, free-float rail handguard, curved polymer magazine."""
    # Upper receiver with a slimmer top deck (fake bevel), ejection port and forward assist.
    _side(mb, "paint", [(-0.075, -0.088), (0.16, -0.088), (0.16, -0.05), (-0.075, -0.05)], 0.036, ANODIZED)
    _side(mb, "paint", [(-0.075, -0.05), (0.16, -0.05), (0.16, -0.044), (-0.075, -0.044)], 0.026, ANODIZED)
    _rail(mb, -0.075, 0.16, -0.044)
    _blk(mb, "paint", 0.0175, 0.0195, 0.0, 0.065, -0.077, -0.058, RUBBER)              # ejection port
    _blk(mb, "paint", 0.018, 0.0205, 0.004, 0.06, -0.08, -0.077, PARKERIZED)          # dust cover hinge
    mb.cylinder_between("paint", (0.019, -0.03, -0.062), (0.029, -0.05, -0.062), 0.0075, ANODIZED, segments=10,
                        caps=True)                                                       # forward assist
    _blk(mb, "paint", -0.016, 0.016, -0.095, -0.075, -0.052, -0.044, ANODIZED)         # charging handle
    _blk(mb, "paint", -0.024, -0.016, -0.093, -0.082, -0.052, -0.044, ANODIZED)        # its latch
    # Lower receiver, magazine well, trigger group.
    _side(mb, "paint", [(-0.065, -0.115), (-0.065, -0.088), (0.125, -0.088), (0.125, -0.112), (0.085, -0.13),
                        (0.0, -0.13)], 0.034, ANODIZED)
    _side(mb, "paint", [(0.06, -0.13), (0.06, -0.112), (0.125, -0.112), (0.125, -0.142), (0.064, -0.142)],
          0.03, ANODIZED)                                                                # magazine well
    mb.cylinder_between("paint", (0.0175, 0.075, -0.104), (0.023, 0.075, -0.104), 0.006, PARKERIZED, segments=8,
                        caps=True)                                                       # mag release
    mb.cylinder_between("paint", (-0.0175, -0.045, -0.098), (-0.024, -0.045, -0.098), 0.008, PARKERIZED,
                        segments=8, caps=True)                                           # selector
    _blk(mb, "paint", -0.004, 0.004, -0.005, 0.07, -0.16, -0.154, ANODIZED)              # trigger guard
    _blk(mb, "paint", -0.004, 0.004, 0.062, 0.07, -0.154, -0.13, ANODIZED)
    _side(mb, "paint", [(0.02, -0.13), (0.03, -0.13), (0.028, -0.148), (0.022, -0.15)], 0.006, PARKERIZED)
    # Pistol grip (raked back) and buttstock on a buffer tube.
    _side(mb, "paint", [(-0.04, -0.13), (0.0, -0.13), (-0.03, -0.23), (-0.07, -0.23)], 0.03, RUBBER)
    _side(mb, "paint", [(-0.075, -0.225), (-0.026, -0.225), (-0.028, -0.236), (-0.072, -0.236)], 0.032, RUBBER)
    mb.cylinder_between("paint", (0, -0.065, -0.07), (0, -0.26, -0.07), 0.0145, ANODIZED, segments=12, caps=True)
    _blk(mb, "paint", -0.006, 0.006, -0.08, -0.065, -0.09, -0.05, ANODIZED)              # castle nut
    _side(mb, "paint", [(-0.17, -0.045), (-0.17, -0.098), (-0.215, -0.13), (-0.36, -0.162), (-0.36, -0.045)],
          0.038, RUBBER)
    _side(mb, "paint", [(-0.36, -0.04), (-0.36, -0.168), (-0.375, -0.168), (-0.375, -0.04)], 0.042, RUBBER)
    _side(mb, "paint", [(-0.2, -0.04), (-0.2, -0.05), (-0.33, -0.05), (-0.33, -0.04)], 0.03, RUBBER)  # cheek rest
    # Curved magazine: slanted segments with ribs and a base plate.
    ya, yb, z = 0.066, 0.12, -0.142
    for i in range(4):
        d = 0.009 + i * 0.003
        _side(mb, "paint", [(ya, z), (yb, z), (yb + d, z - 0.032), (ya + d, z - 0.032)], 0.026, FDE)
        _blk(mb, "paint", -0.0135, 0.0135, ya + d * 0.5 + 0.01, ya + d * 0.5 + 0.03, z - 0.02, z - 0.012, FDE)
        ya, yb, z = ya + d, yb + d, z - 0.032
    _side(mb, "paint", [(ya - 0.004, z), (yb + 0.004, z), (yb + 0.004, z - 0.01), (ya - 0.004, z - 0.01)],
          0.03, FDE)
    # Free-float handguard with slots and a top rail.
    _side(mb, "paint", [(0.16, -0.098), (0.43, -0.098), (0.43, -0.046), (0.16, -0.046)], 0.046, ANODIZED)
    _rail(mb, 0.16, 0.43, -0.046)
    for sx in (-1, 1):
        for row in (-0.085, -0.066):
            for k in range(6):
                y = 0.19 + k * 0.04
                _blk(mb, "paint", sx * 0.0232 - 0.0005, sx * 0.0232 + 0.0005, y, y + 0.024, row, row + 0.008,
                     RUBBER)
    _blk(mb, "paint", -0.026, 0.026, 0.155, 0.165, -0.1, -0.044, PARKERIZED)            # barrel nut ring
    # Barrel, gas block, muzzle brake, folded front sight.
    mb.cylinder_between("paint", (0, 0.43, -0.07), (0, 0.6, -0.07), 0.0085, PARKERIZED, segments=12)
    _blk(mb, "paint", -0.011, 0.011, 0.47, 0.49, -0.084, -0.058, PARKERIZED)
    mb.cylinder_between("paint", (0, 0.6, -0.07), (0, 0.665, -0.07), 0.0125, ANODIZED, segments=12, caps=True)
    for k in range(3):
        y = 0.612 + k * 0.016
        for sx in (-1, 1):
            _blk(mb, "paint", sx * 0.0125 - 0.001, sx * 0.0125 + 0.001, y, y + 0.009, -0.075, -0.065, RUBBER)
    _side(mb, "paint", [(0.4, -0.04), (0.425, -0.04), (0.425, -0.032), (0.4, -0.036)], 0.02, ANODIZED)
    # Vertical foregrip and a weapon light on the right rail.
    mb.cylinder_between("paint", (0, 0.31, -0.098), (0, 0.32, -0.172), 0.0135, RUBBER, segments=12, caps=True)
    mb.cylinder_between("paint", (0.03, 0.35, -0.072), (0.03, 0.41, -0.072), 0.011, ANODIZED, segments=12, caps=True)
    mb.cylinder_between("paint", (0.03, 0.41, -0.072), (0.03, 0.412, -0.072), 0.009, (0.85, 0.88, 0.9),
                        segments=12, caps=True)
    _blk(mb, "paint", 0.022, 0.026, 0.36, 0.4, -0.074, -0.068, ANODIZED)
    _reflex_sight(mb, 0.06)
    _arms(mb, (0.0, -0.045, -0.165), (0.0, 0.312, -0.135))
    return (0.0, 0.67, -0.07)


def _reflex_sight(mb, y):
    """Holographic sight: boxy housing, hooded window on the sight line and a glowing dot."""
    _blk(mb, "paint", -0.014, 0.014, y - 0.03, y + 0.05, -0.0345, -0.022, ANODIZED)        # mount + base
    _blk(mb, "paint", -0.017, 0.017, y - 0.02, y + 0.045, -0.022, -0.012, ANODIZED)       # battery housing
    for b in (-0.0165, 0.0165):                                                         # hood sides
        _blk(mb, "paint", b - 0.002, b + 0.002, y - 0.005, y + 0.045, -0.012, 0.024, ANODIZED)
    _blk(mb, "paint", -0.0185, 0.0185, y - 0.005, y + 0.045, 0.024, 0.028, ANODIZED)    # hood top
    _blk(mb, "paint", -0.006, 0.006, y + 0.01, y + 0.03, 0.028, 0.032, RUBBER)          # buttons
    mb.ellipsoid("emissive", 0, y + 0.041, 0, 0.0011, 0.0005, 0.0011, RED_DOT, rings=3, segments=6)


def build_pistol(mb, gun=True):
    if not gun:                                   # a real pistol model is used - hands only
        _arms(mb, (0.0, -0.035, -0.13), (-0.012, -0.025, -0.15))
        return (0.0, 0.11, -0.03)
    mb.box("metal", 0, 0.05, -0.05, 0.03, 0.17, 0.035, GUNMETAL)                     # slide
    mb.box("metal", 0, 0.04, -0.075, 0.028, 0.15, 0.025, POLYMER)                    # frame
    mb.box("metal", 0, -0.025, -0.15, 0.028, 0.048, 0.11, POLYMER)                   # grip
    mb.box("metal", 0, 0.01, -0.105, 0.006, 0.035, 0.022, GUNMETAL)                  # trigger guard
    for sx in (-1, 1):
        mb.box("metal", sx * 0.007, -0.03, -0.035, 0.006, 0.008, 0.03, SIGHT)
    mb.box("metal", 0, 0.125, -0.035, 0.004, 0.006, 0.03, SIGHT)
    mb.cylinder_between("metal", (0, 0.135, -0.05), (0, 0.14, -0.05), 0.006, SIGHT, segments=6, caps=True)
    _arms(mb, (0.0, -0.025, -0.13), (-0.012, -0.015, -0.15))
    return (0.0, 0.145, -0.05)


def build_sniper(mb, gun=True):
    if not gun:                                   # a real rifle model is used - hands only
        _arms(mb, (0.0, -0.08, -0.13), (0.0, 0.3, -0.1))
        return (0.0, 0.85, -0.05)
    mb.box("metal", 0, 0.02, -0.1, 0.045, 0.32, 0.065, GUNMETAL)
    mb.box("wood", 0, 0.32, -0.11, 0.055, 0.32, 0.06, OLIVE)
    mb.cylinder_between("metal", (0, 0.45, -0.085), (0, 0.95, -0.085), 0.011, GUNMETAL, segments=8)
    mb.cylinder_between("metal", (0, 0.90, -0.085), (0, 0.97, -0.085), 0.017, SIGHT, segments=8, caps=True)
    mb.box("wood", 0, -0.2, -0.13, 0.045, 0.3, 0.09, OLIVE)
    mb.box("metal", 0, 0.08, -0.17, 0.028, 0.06, 0.06, GUNMETAL)
    mb.box("wood", 0, -0.05, -0.18, 0.03, 0.045, 0.09, OLIVE)
    mb.cylinder_between("metal", (0, -0.1, -0.012), (0, 0.22, -0.012), 0.02, GUNMETAL, segments=10)  # scope
    mb.cylinder_between("metal", (0, 0.2, -0.012), (0, 0.27, -0.012), 0.026, GUNMETAL, segments=10, caps=True)
    mb.cylinder_between("metal", (0, -0.16, -0.012), (0, -0.09, -0.012), 0.024, GUNMETAL, segments=10, caps=True)
    mb.cylinder_between("paint", (0, 0.271, -0.012), (0, 0.272, -0.012), 0.022, LENS, segments=10, caps=True)
    for y in (0.0, 0.14):
        mb.box("metal", 0, y, -0.05, 0.02, 0.02, 0.03, GUNMETAL)
    mb.cylinder_between("metal", (0.025, -0.02, -0.08), (0.075, -0.03, -0.09), 0.006, GUNMETAL, segments=6)
    mb.ellipsoid("metal", 0.078, -0.03, -0.09, 0.011, 0.011, 0.011, GUNMETAL, rings=4, segments=6)
    _arms(mb, (0.0, -0.05, -0.17), (0.0, 0.32, -0.15))
    return (0.0, 0.98, -0.085)


def build_shotgun(mb):
    """Pump-action 12 gauge: steel receiver, barrel over a magazine tube, walnut stock."""
    _side(mb, "paint", [(-0.06, -0.12), (-0.06, -0.06), (-0.04, -0.048), (0.15, -0.048), (0.15, -0.12)],
          0.044, PARKERIZED)                                                             # receiver
    _blk(mb, "paint", 0.0215, 0.0235, 0.02, 0.1, -0.085, -0.06, RUBBER)                 # ejection port
    _blk(mb, "paint", -0.004, 0.004, -0.02, 0.07, -0.152, -0.146, PARKERIZED)            # trigger guard
    _blk(mb, "paint", -0.004, 0.004, 0.064, 0.07, -0.146, -0.12, PARKERIZED)
    _side(mb, "paint", [(0.02, -0.12), (0.03, -0.12), (0.028, -0.14), (0.022, -0.142)], 0.006, PARKERIZED)
    mb.cylinder_between("paint", (0, 0.15, -0.068), (0, 0.68, -0.068), 0.0125, PARKERIZED, segments=14, caps=True)
    mb.cylinder_between("paint", (0, 0.15, -0.098), (0, 0.6, -0.098), 0.0115, PARKERIZED, segments=12, caps=True)
    _blk(mb, "paint", -0.012, 0.012, 0.58, 0.6, -0.11, -0.06, PARKERIZED)                # barrel clamp
    _blk(mb, "paint", -0.003, 0.003, 0.15, 0.66, -0.0565, -0.0535, PARKERIZED)          # vent rib
    mb.ellipsoid("paint", 0, 0.668, -0.05, 0.0035, 0.0035, 0.0035, BRASS, rings=3, segments=6)   # bead sight
    _blk(mb, "paint", -0.006, 0.006, -0.03, -0.012, -0.052, -0.044, PARKERIZED)          # rear notch
    # Walnut stock with a pistol-grip wrist and a rubber butt pad.
    _side(mb, "wood", [(-0.06, -0.06), (-0.06, -0.125), (-0.11, -0.175), (-0.38, -0.2), (-0.38, -0.075),
                       (-0.13, -0.062)], 0.042, WOOD)
    _side(mb, "paint", [(-0.38, -0.07), (-0.38, -0.205), (-0.395, -0.205), (-0.395, -0.07)], 0.046, RUBBER)
    _side(mb, "wood", [(-0.06, -0.12), (-0.02, -0.12), (-0.045, -0.2), (-0.085, -0.19)], 0.034, WOOD)
    _arms(mb, (0.0, -0.045, -0.155), None)        # left hand is on the pump (see build_pump)
    return (0.0, 0.69, -0.068)


def build_pump(mb):
    """Separate node so the ribbed forend can slide when pumping."""
    _side(mb, "wood", [(0.28, -0.122), (0.44, -0.122), (0.44, -0.082), (0.28, -0.082)], 0.05, WOOD)
    for k in range(7):
        y = 0.295 + k * 0.02
        for sx in (-1, 1):
            _blk(mb, "paint", sx * 0.025 - 0.0008, sx * 0.025 + 0.0008, y, y + 0.006, -0.118, -0.086, RUBBER)
    _hand(mb, 0.0, 0.36, -0.13, "left")
    _sleeve(mb, (-0.01, 0.36, -0.14), (-0.17, -0.06, -0.33))


def build_launcher(mb, gun=True):
    """Shoulder-fired rocket launcher: olive tube, flared venturi, optic, grips and a loaded warhead."""
    mb.cylinder_between("paint", (0, -0.42, -0.095), (0, 0.5, -0.095), 0.056, TUBE_GREEN, segments=18)
    for y in (0.12, 0.3, 0.46):                                                 # reinforcing bands
        mb.cylinder_between("paint", (0, y, -0.095), (0, y + 0.025, -0.095), 0.059, ANODIZED, segments=18)
    mb.cylinder_between("paint", (0, -0.42, -0.095), (0, -0.52, -0.095), 0.056, ANODIZED, segments=18,
                        radius_end=0.075)                                                 # venturi flare
    mb.cylinder_between("paint", (0, 0.5, -0.095), (0, 0.56, -0.095), 0.064, ANODIZED, segments=18, caps=True)
    mb.cylinder_between("paint", (0, 0.56, -0.095), (0, 0.66, -0.095), 0.045, TUBE_GREEN, segments=16)  # warhead
    mb.cylinder_between("paint", (0, 0.66, -0.095), (0, 0.76, -0.095), 0.045, TUBE_GREEN, segments=16,
                        radius_end=0.008)
    _blk(mb, "paint", -0.004, 0.004, 0.05, 0.3, -0.04, -0.034, ANODIZED)                # sight rail
    _side(mb, "paint", [(0.0, -0.15), (0.06, -0.15), (0.04, -0.23), (-0.01, -0.23)], 0.03, RUBBER)   # grip
    _side(mb, "paint", [(0.24, -0.15), (0.28, -0.15), (0.275, -0.22), (0.245, -0.22)], 0.03, RUBBER)
    _blk(mb, "paint", -0.012, 0.012, -0.02, 0.07, -0.155, -0.145, ANODIZED)
    _blk(mb, "paint", 0.07, 0.094, 0.0, 0.12, -0.06, -0.025, ANODIZED)                  # optic body
    mb.cylinder_between("paint", (0.082, 0.0, -0.042), (0.082, -0.04, -0.042), 0.016, RUBBER, segments=12,
                        caps=True)                                                       # eye cup
    _blk(mb, "paint", -0.002, 0.002, 0.3, 0.306, -0.034, 0.0, RED_DOT)                 # front sight blade
    _arms(mb, (0.0, 0.03, -0.19), (0.0, 0.26, -0.185))
    return (0.0, 0.76, -0.095)


SUPPRESSOR = (0.07, 0.07, 0.075)


def _suppressor(mb, muzzle, length, radius):
    x, y, z = muzzle
    mb.cylinder_between("metal", (x, y - 0.01, z), (x, y + length, z), radius, SUPPRESSOR, segments=10, caps=True)
    return (x, y + length, z)


def build_rifle_suppressed(mb):
    return _suppressor(mb, build_rifle(mb), 0.17, 0.02)


def build_pistol_suppressed(mb, gun=True):
    return _suppressor(mb, build_pistol(mb, gun), 0.12, 0.015)


# Real gun models: model key and where to put it (y = centre of the gun, z = top of the gun).
REAL_GUNS = {
    "pistol": ("pistol_model", (0.0, 0.01, -0.022)),
    "pistol_suppressed": ("pistol_model", (0.0, 0.01, -0.022)),
    "sniper": ("rifle_model", (0.0, 0.3, -0.012)),
}

BUILDERS = {"rifle": build_rifle, "pistol": build_pistol, "sniper": build_sniper, "shotgun": build_shotgun,
            "launcher": build_launcher, "rifle_suppressed": build_rifle_suppressed,
            "pistol_suppressed": build_pistol_suppressed}

POSE = {
    #            hip offset               ads offset (sight on centre)    sprint drop
    "rifle":   ((0.13, 0.33, -0.105), (0.0, 0.26, 0.0)),
    "pistol":  ((0.12, 0.34, -0.07), (0.0, 0.34, 0.0)),
    "sniper":  ((0.15, 0.40, -0.12), (0.0, 0.18, 0.0)),
    "shotgun": ((0.13, 0.33, -0.105), (0.0, 0.30, 0.0)),
    "launcher": ((0.16, 0.34, -0.08), (0.0, 0.32, 0.0)),
}
POSE["rifle_suppressed"] = POSE["rifle"]
POSE["pistol_suppressed"] = POSE["pistol"]


class ViewModel:
    def __init__(self, base, materials, fov=58.0):
        self.base = base
        self.scene = NodePath("viewmodel_scene")
        self.scene.set_shader_auto()
        lens = PerspectiveLens()
        lens.set_fov(fov)
        lens.set_near_far(0.01, 5.0)
        self.lens = lens
        self.camera_np = self.scene.attach_new_node(Camera("viewmodel_cam", lens))
        # Draw into the HDR scene buffer when post-processing is on, so the gun gets the same look.
        postfx = getattr(base, "postfx", None)
        target = postfx.scene_buffer if postfx is not None and postfx.scene_buffer is not None else base.win
        self.region = target.make_display_region()
        self.region.set_sort(5)          # after the 3D world (0) but before the 2D HUD (10)
        self.region.set_clear_depth_active(True)
        self.region.set_camera(self.camera_np)
        amb = AmbientLight("vm_ambient")
        amb.set_color((0.6, 0.6, 0.64, 1))
        self.scene.set_light(self.scene.attach_new_node(amb))
        sun = DirectionalLight("vm_sun")
        sun.set_color((1.1, 1.0, 0.85, 1))
        self.sun_np = self.scene.attach_new_node(sun)
        self.scene.set_light(self.sun_np)
        fill = DirectionalLight("vm_fill")                       # fixed key light from above-right-behind,
        fill.set_color((0.55, 0.53, 0.5, 1))                     # so edges and parts always read
        fill_np = self.scene.attach_new_node(fill)
        fill_np.set_hpr(-30, -50, 0)
        self.scene.set_light(fill_np)
        self.anchor = self.scene.attach_new_node("anchor")        # bob/sway/ads live here
        self.models = {}
        self.muzzles = {}
        self.pump = None
        for name, builder in BUILDERS.items():
            mb = MeshBuilder(materials.uv_scales())
            real = self._load_real_gun(base, name)
            muzzle = builder(mb, gun=False) if real is not None else builder(mb)
            node = mb.build(self.anchor, materials, name=f"vm_{name}")
            if real is not None:
                real.reparent_to(node)
            node.hide()
            self.models[name] = node
            self.muzzles[name] = Vec3(*muzzle)
        mb = MeshBuilder(materials.uv_scales())
        build_pump(mb)
        self.pump = mb.build(self.models["shotgun"], materials, name="vm_pump")
        self.current = None
        self.flash = None
        # animation state
        self._sway = Vec3()
        self._kick = 0.0
        self._kick_rot = 0.0
        self._pump_t = 1.0
        self._bolt_t = 1.0

    @staticmethod
    def _load_real_gun(base, name):
        """Use a downloaded gun model (assets/models/<x>_model.bam) when available."""
        from core.paths import ASSETS_DIR
        from panda3d.core import Filename
        key, placement = REAL_GUNS.get(name, (None, None))
        path = ASSETS_DIR / "models" / f"{key}.bam" if key else None
        if path is None or not path.is_file():
            return None
        try:
            model = base.loader.load_model(Filename.from_os_specific(str(path)))
        except Exception:
            return None
        # Models are oriented barrel -> +Y with the top of the gun at z = 0 (see tools/fetch_assets.py).
        model.set_pos(*placement)
        return model

    def set_flash_node(self, node):
        self.flash = node
        node.reparent_to(self.anchor)
        node.hide()

    def show_model(self, name):
        for key, node in self.models.items():
            node.show() if key == name else node.hide()
        self.current = name

    def set_visible(self, visible):
        self.scene.show() if visible else self.scene.hide()
        self.region.set_active(visible)

    def muzzle_local(self):
        return self.muzzles.get(self.current, Vec3(0, 0.6, -0.06))

    def kick(self, amount=1.0):
        self._kick = min(1.5, self._kick + amount)
        self._kick_rot = min(10.0, self._kick_rot + 4.0 * amount)

    def cycle(self, kind):
        if kind == "pump":
            self._pump_t = 0.0
        elif kind == "bolt":
            self._bolt_t = 0.0

    def update(self, dt, *, ads, bob_phase, bob_weight, mouse_dx, mouse_dy, sprint, reload_progress,
               switch_lower, sun_quat, aspect):
        self.lens.set_aspect_ratio(aspect)
        self.sun_np.set_quat(sun_quat)
        if self.current is None:
            return
        hip, aim = POSE[self.current]
        hip, aim = Vec3(*hip), Vec3(*aim)
        pos = hip + (aim - hip) * ads
        h = p = r = 0.0

        # Sway follows mouse movement with a little lag.
        target = Vec3(-mouse_dx * 0.0004, 0, mouse_dy * 0.0004)
        self._sway += (target - self._sway) * min(1.0, dt * 10.0)
        sway_scale = 1.0 - 0.8 * ads
        pos += Vec3(max(-0.03, min(0.03, self._sway.x)), 0, max(-0.03, min(0.03, self._sway.z))) * sway_scale
        h += self._sway.x * 120 * sway_scale

        # Walk bob.
        bw = bob_weight * (1.0 - 0.85 * ads)
        pos += Vec3(math.sin(bob_phase) * 0.012 * bw, 0, -abs(math.sin(bob_phase)) * 0.012 * bw)

        # Sprint pose.
        if sprint > 0:
            pos += Vec3(-0.04, -0.04, -0.05) * sprint
            h += 28 * sprint
            r += -18 * sprint
            p += -8 * sprint

        # Recoil kick (spring back).
        self._kick += -self._kick * min(1.0, dt * 14.0)
        self._kick_rot += -self._kick_rot * min(1.0, dt * 12.0)
        pos += Vec3(0, -0.035 * self._kick, 0.008 * self._kick)
        p += self._kick_rot

        # Reload: dip and roll the weapon.
        if reload_progress > 0:
            k = math.sin(min(1.0, reload_progress) * math.pi)
            pos += Vec3(0, 0, -0.07 * k)
            r += 25 * k
            p += -12 * k

        # Weapon switch: lower out of view.
        pos += Vec3(0, 0, -0.35 * switch_lower)
        p += -30 * switch_lower

        # Pump / bolt cycling.
        if self._pump_t < 1.0:
            self._pump_t = min(1.0, self._pump_t + dt / 0.45)
            self.pump.set_y(-0.07 * math.sin(self._pump_t * math.pi))
        if self._bolt_t < 1.0:
            self._bolt_t = min(1.0, self._bolt_t + dt / 0.9)
            k = math.sin(self._bolt_t * math.pi)
            r += 14 * k
            pos += Vec3(0, -0.02 * k, -0.02 * k)

        self.anchor.set_pos(pos)
        self.anchor.set_hpr(h, p, r)
