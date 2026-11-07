"""Procedural 3D props for the military environments.

Every builder has the signature  build_xxx(mb, rng, **params)  and draws into a
MeshBuilder (environments/geometry.py) in LOCAL coordinates:
  origin = base centre on the ground, +Y = front of vehicles, Z = up, metres.
Builders also register their collision shapes.

These are temporary procedural models. To use a real model instead, see
assets/models/README.txt - the collision shapes defined here are kept.
"""
from __future__ import annotations

import math

# ----------------------------------------------------------------------------- palette
CONCRETE = (0.66, 0.65, 0.62)
CONCRETE_DARK = (0.50, 0.50, 0.48)
PALE_WALL = (0.74, 0.71, 0.63)
ROOF_TAR = (0.27, 0.27, 0.26)
OLIVE = (0.37, 0.40, 0.26)
OLIVE_DARK = (0.25, 0.28, 0.18)
TAN = (0.66, 0.58, 0.44)
SAND = (0.72, 0.64, 0.48)
STEEL = (0.52, 0.54, 0.55)
DARK_STEEL = (0.22, 0.23, 0.24)
RUBBER = (0.08, 0.08, 0.08)
WOOD = (0.60, 0.47, 0.33)
WOOD_DARK = (0.40, 0.31, 0.21)
WHITE_PAINT = (0.88, 0.88, 0.84)
YELLOW_PAINT = (0.86, 0.68, 0.14)
RED_PAINT = (0.62, 0.14, 0.11)
GLASS = (0.10, 0.13, 0.15)
LENS = (0.80, 0.80, 0.74)
LAMP_RED = (1.0, 0.18, 0.12)
LAMP_GREEN = (0.3, 1.0, 0.4)
LAMP_WARM = (1.0, 0.86, 0.58)
BARK = (0.42, 0.34, 0.26)
LEAF_GREEN = (0.36, 0.44, 0.23)
PINE_GREEN = (0.22, 0.31, 0.18)
ROCK_GREY = (0.56, 0.54, 0.51)
CHARRED = (0.14, 0.13, 0.12)
DARK = (0.05, 0.05, 0.05)

NAMED_COLORS = {
    "olive": OLIVE, "olive_dark": OLIVE_DARK, "tan": TAN, "sand": SAND, "steel": STEEL,
    "rust": (0.55, 0.27, 0.16), "blue": (0.22, 0.33, 0.45), "green": (0.24, 0.38, 0.27),
    "grey": (0.52, 0.52, 0.52), "white": WHITE_PAINT, "red": RED_PAINT, "concrete": CONCRETE,
}


def _color(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        return NAMED_COLORS.get(value, default)
    return tuple(value[:3])


def _vary(color, rng, amount=0.06):
    f = 1.0 + rng.uniform(-amount, amount)
    return tuple(min(1.0, max(0.0, c * f)) for c in color[:3])


def _scale(color, f):
    return tuple(min(1.0, max(0.0, c * f)) for c in color[:3])


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


# ============================================================================= helpers
def wall_x(mb, x0, x1, y, z0, height, thickness, material, color, openings=(), frame_color=None,
           collide=True):
    """Wall along local X from x0 to x1 (centre line at y) with rectangular openings.

    openings: (centre_x, width, bottom, top) - bottom/top measured from z0.
    """
    def piece(a, b, zb, zt):
        if b - a < 0.01 or zt - zb < 0.01:
            return
        mb.box(material, (a + b) / 2, y, z0 + zb, b - a, thickness, zt - zb, color,
               bottom=zb > 0, collide=collide)

    cursor = x0
    for cx, w, bottom, top in sorted(openings):
        a, b = cx - w / 2, cx + w / 2
        piece(cursor, a, 0.0, height)
        piece(a, b, 0.0, bottom)
        piece(a, b, top, height)
        if frame_color is not None:
            ft, fd = 0.07, thickness + 0.06
            for fx in (a + ft / 2, b - ft / 2):
                mb.box("wood", fx, y, z0 + bottom, ft, fd, top - bottom, frame_color)
            mb.box("wood", (a + b) / 2, y, z0 + top - ft, w, fd, ft, frame_color, bottom=True)
            if bottom > 0:
                mb.box("concrete", (a + b) / 2, y, z0 + bottom - 0.05, w + 0.12, thickness + 0.12, 0.05,
                       _scale(color, 0.85))
                mb.box("wood", (a + b) / 2, y, z0 + bottom, 0.05, 0.04, top - bottom, frame_color)
        cursor = b
    piece(cursor, x1, 0.0, height)


def stairs(mb, x, y_start, width, total_height, *, run=0.30, rise=0.25, material="concrete",
           color=CONCRETE_DARK, rng=None, direction=1):
    """Solid straight stairs rising along local +Y (direction=1) or -Y, starting at y_start."""
    n = max(1, math.ceil(total_height / rise - 1e-6))
    step_rise = total_height / n
    for i in range(1, n + 1):
        y0 = y_start + direction * (i - 1) * run
        y1 = y0 + direction * run
        col = _vary(color, rng, 0.03) if rng else color
        mb.box(material, x, (y0 + y1) / 2, 0.0, width, run, i * step_rise, col, collide=True)
    return y_start + direction * n * run


# ============================================================================= buildings
def build_barracks(mb, rng, width=16.0, depth=8.0, height=3.2, windows=4, interior="bunks",
                   roof_stairs=False, antenna=False, wall_color=None, roof_color=None, door_width=1.4,
                   wall_material="block"):
    """Single-storey concrete-block building that the player can enter."""
    t, fh = 0.25, 0.25
    hw, hd = width / 2, depth / 2
    wc = _vary(_color(wall_color, PALE_WALL), rng)
    rc = _vary(_color(roof_color, ROOF_TAR), rng)
    trim = _vary(WOOD_DARK, rng)
    mb.box("concrete", 0, 0, 0, width + 0.6, depth + 0.6, fh, _vary(CONCRETE_DARK, rng), collide=True)
    z0 = fh

    def window_xs(span, n, avoid=None):
        xs = [-span / 2 + (i + 1) * span / (n + 1) for i in range(n)]
        return [x for x in xs if avoid is None or abs(x - avoid) > 1.9]

    door = (0.0, door_width, 0.0, 2.3)
    front = [door] + [(x, 1.3, 1.0, 2.2) for x in window_xs(width, windows, 0.0)]
    back = [(x, 1.3, 1.0, 2.2) for x in window_xs(width, windows)]
    side_n = max(1, int(depth // 4))
    side = [(y, 1.2, 1.0, 2.2) for y in window_xs(depth - 2 * t, side_n)]
    wall_x(mb, -hw, hw, -hd + t / 2, z0, height, t, wall_material, wc, front, frame_color=trim)
    wall_x(mb, -hw, hw, hd - t / 2, z0, height, t, wall_material, wc, back, frame_color=trim)
    for sx in (-1, 1):
        with mb.place(sx * (hw - t / 2), 0, 0, 90):
            wall_x(mb, -hd + t, hd - t, 0, z0, height, t, wall_material, wc, side, frame_color=trim)

    # Roof slab and parapet.
    rz = z0 + height
    roof_top = rz + 0.22
    mb.box("concrete", 0, 0, rz, width + 0.6, depth + 0.6, 0.22, rc, bottom=True, collide=True)
    ph = 0.9 if roof_stairs else 0.25
    pc = _scale(wc, 0.92)
    ex, ey = hw + 0.3, hd + 0.3
    mb.box("concrete", 0, -ey + 0.1, roof_top, width + 0.6, 0.2, ph, pc, collide=True)
    mb.box("concrete", 0, ey - 0.1, roof_top, width + 0.6, 0.2, ph, pc, collide=True)
    mb.box("concrete", -ex + 0.1, 0, roof_top, 0.2, depth + 0.2, ph, pc, collide=True)
    if roof_stairs:
        gap0, gap1 = hd - 1.9, hd - 0.4         # gap in the +X parapet where the stairs arrive
        mb.box("concrete", ex - 0.1, (-ey + 0.2 + gap0) / 2, roof_top, 0.2, gap0 + ey - 0.2, ph, pc, collide=True)
        if ey - 0.2 > gap1:
            mb.box("concrete", ex - 0.1, (gap1 + ey - 0.2) / 2, roof_top, 0.2, ey - 0.2 - gap1, ph, pc, collide=True)
        # Exterior stairs along the +X side, rising toward +Y, with a landing at the top.
        sx = ex + 0.65
        landing = 1.5
        n = math.ceil(roof_top / 0.25 - 1e-6)
        start = gap1 - landing - n * 0.30
        stairs(mb, sx, start, 1.2, roof_top, rng=rng)
        mb.box("concrete", sx, gap1 - landing / 2, 0, 1.2, landing, roof_top, _vary(CONCRETE_DARK, rng),
               collide=True)
        mb.box("concrete", sx, gap1 + 0.1, 0, 1.2, 0.2, roof_top + ph, pc, collide=True)   # end wall of landing
        for yy in (start, gap1):
            mb.cylinder("metal", sx + 0.58, yy, 0, 0.03, roof_top + 1.0, STEEL, segments=5)
        mb.cylinder_between("metal", (sx + 0.58, start, 1.0), (sx + 0.58, gap1 - landing, roof_top + 1.0),
                            0.025, STEEL, segments=5)
    else:
        mb.box("concrete", ex - 0.1, 0, roof_top, 0.2, depth + 0.2, ph, pc, collide=True)

    # Roof equipment.
    with mb.place(-hw * 0.5, hd * 0.2, roof_top):
        mb.box("metal", 0, 0, 0, 1.2, 0.9, 0.8, _vary(STEEL, rng), collide=True)
        mb.box("metal", 0, -0.46, 0.15, 0.9, 0.04, 0.5, DARK_STEEL)
    mb.cylinder("metal", hw * 0.4, -hd * 0.3, roof_top, 0.18, 0.6, DARK_STEEL, segments=8)
    if antenna:
        mb.cylinder("metal", hw * 0.7, hd * 0.4, roof_top, 0.05, 6.0, STEEL, segments=6, radius_top=0.02)
        mb.cylinder_between("metal", (hw * 0.2, hd * 0.4, roof_top + 1.6), (hw * 0.2 + 0.25, hd * 0.4, roof_top + 1.05),
                            0.6, _vary(WHITE_PAINT, rng), segments=14, radius_end=0.05)
        mb.cylinder("metal", hw * 0.2, hd * 0.4, roof_top, 0.05, 1.2, DARK_STEEL, segments=6)

    # Entrance details.
    mb.box("concrete", 0, -hd - 0.3 - 0.4, 0, 1.9, 0.8, 0.12, _vary(CONCRETE, rng), collide=True)
    mb.box("wood", door_width / 2 + 0.66, -hd - 0.06, z0, 1.3, 0.05, 2.25, _vary(OLIVE_DARK, rng), collide=True)
    mb.box("metal", 0, -hd - 0.15, z0 + 2.45, 0.9, 0.25, 0.08, DARK_STEEL, bottom=True)
    mb.box("paint", 0, -hd - 0.12, z0 + 2.53, 2.2, 0.05, 0.45, _vary(OLIVE_DARK, rng))
    # Drain pipes and an AC unit.
    for cx in (-hw - 0.05, hw + 0.05):
        mb.cylinder("metal", cx, -hd - 0.05, 0, 0.05, rz + 0.2, DARK_STEEL, segments=6)
    mb.box("metal", hw + 0.38, hd * 0.3, z0 + 1.7, 0.45, 0.9, 0.6, _vary(STEEL, rng), bottom=True)

    if interior == "bunks":
        _bunk_interior(mb, rng, hw, hd, t, z0)
    elif interior == "office":
        _office_interior(mb, rng, hw, hd, t, z0)
    elif interior == "home":
        _home_interior(mb, rng, hw, hd, t, z0)
    elif interior == "booth":
        mb.box("wood", 0, hd - t - 0.35, z0, 1.6, 0.6, 0.8, _vary(WOOD, rng), collide=True)
        mb.box("metal", 0.4, hd - t - 0.35, z0 + 0.8, 0.4, 0.3, 0.25, DARK_STEEL)


def _bunk_interior(mb, rng, hw, hd, t, z0):
    n = max(1, int((hw * 2 - 2.0) // 3.0))
    frame = _vary(OLIVE_DARK, rng)
    for i in range(n):
        x = -hw + 1.6 + i * ((hw * 2 - 3.2) / max(1, n - 1)) if n > 1 else 0.0
        y = hd - t - 0.55
        with mb.place(x, y, z0):
            for px in (-0.95, 0.95):
                for py in (-0.42, 0.42):
                    mb.box("metal", px, py, 0, 0.05, 0.05, 1.75, frame)
            for z in (0.4, 1.4):
                mb.box("metal", 0, 0, z, 2.0, 0.9, 0.06, frame)
                mb.box("fabric", 0, 0, z + 0.06, 1.9, 0.82, 0.14, _vary((0.42, 0.44, 0.36), rng))
            mb.collider_box(0, 0, 0, 2.0, 0.95, 1.75)
    # Lockers on the left wall.
    for j in range(4):
        y = -hd + t + 0.6 + j * 0.55
        mb.box("metal", -hw + t + 0.28, y, z0, 0.5, 0.52, 1.9, _vary((0.36, 0.42, 0.34), rng, 0.05), collide=True)
    # Table and stools.
    mb.box("wood", 1.5, -0.6, z0 + 0.72, 1.6, 0.9, 0.05, _vary(WOOD, rng))
    for px in (0.85, 2.15):
        for py in (-0.95, -0.25):
            mb.box("wood", px, py, z0, 0.06, 0.06, 0.72, WOOD_DARK)
    mb.collider_box(1.5, -0.6, z0, 1.6, 0.9, 0.77)
    mb.box("metal", 1.5, -1.45, z0, 0.4, 0.4, 0.45, DARK_STEEL, collide=True)


def _home_interior(mb, rng, hw, hd, t, z0):
    wood = _vary(WOOD, rng, 0.1)
    mb.box("wood", -hw * 0.35, 0.2, z0 + 0.72, 1.4, 0.9, 0.06, wood)                       # kitchen table
    for px in (-hw * 0.35 - 0.6, -hw * 0.35 + 0.6):
        for py in (-0.2, 0.6):
            mb.box("wood", px, py, z0, 0.05, 0.05, 0.72, _scale(wood, 0.7))
    mb.collider_box(-hw * 0.35, 0.2, z0, 1.4, 0.9, 0.78)
    for py in (-0.55, 0.95):
        mb.box("wood", -hw * 0.35, py, z0, 0.45, 0.45, 0.45, _scale(wood, 0.8), collide=True)  # chairs
    mb.box("fabric", hw - t - 1.1, hd - t - 0.5, z0, 2.0, 0.95, 0.5, _vary((0.5, 0.42, 0.4), rng), collide=True)  # bed
    mb.box("fabric", hw - t - 0.35, hd - t - 0.5, z0 + 0.5, 0.4, 0.8, 0.15, (0.85, 0.83, 0.78))
    mb.box("wood", -hw + t + 0.25, hd - t - 1.2, z0, 0.4, 1.6, 1.9, _scale(wood, 0.75), collide=True)  # shelf
    for z in (0.5, 1.0, 1.5):
        mb.box("paint", -hw + t + 0.3, hd - t - 1.2, z0 + z, 0.3, 1.3, 0.25,
               rng.choice([(0.5, 0.2, 0.15), (0.2, 0.3, 0.45), (0.6, 0.55, 0.4)]))
    mb.box("fabric", hw - t - 1.3, -hd + t + 0.6, z0, 2.0, 0.85, 0.75, _vary((0.35, 0.3, 0.4), rng),
           collide=True)                                                                     # sofa (clear of the door)


def _office_interior(mb, rng, hw, hd, t, z0):
    desk = _vary(OLIVE_DARK, rng)
    for i, x in enumerate((-hw + 2.0, -hw + 4.5, hw - 4.5)):
        y = hd - t - 0.6
        mb.box("metal", x, y, z0, 1.8, 0.8, 0.75, desk, collide=True)
        mb.box("metal", x - 0.3, y + 0.15, z0 + 0.75, 0.5, 0.35, 0.35, DARK_STEEL)        # radio set
        mb.box("emissive", x - 0.3, y - 0.03, z0 + 0.95, 0.3, 0.01, 0.06, LAMP_GREEN)
        mb.box("paint", x + 0.4, y, z0 + 0.75, 0.6, 0.45, 0.01, WHITE_PAINT)               # papers
    # Map table in the middle.
    mb.box("wood", 0, 0, z0, 2.4, 1.4, 0.85, _vary(WOOD_DARK, rng), collide=True)
    mb.box("paint", 0, 0, z0 + 0.85, 2.0, 1.1, 0.01, (0.62, 0.66, 0.52))
    # Filing cabinets.
    for j in range(3):
        mb.box("metal", hw - t - 0.3, -hd + t + 0.6 + j * 0.55, z0, 0.5, 0.5, 1.3, _vary(STEEL, rng), collide=True)


def build_guard_booth(mb, rng, **kw):
    params = dict(width=2.8, depth=2.8, height=2.5, windows=1, interior="booth")
    params.update(kw)
    build_barracks(mb, rng, **params)


def build_ruined_building(mb, rng, width=14.0, depth=9.0, height=3.4):
    """Bombed-out shell: jagged walls, no roof, rubble inside."""
    t, fh = 0.3, 0.25
    hw, hd = width / 2, depth / 2
    mb.box("concrete", 0, 0, 0, width + 0.6, depth + 0.6, fh, _vary(CONCRETE_DARK, rng), collide=True)
    wall_col = _vary(PALE_WALL, rng)

    def broken_wall(length):
        seg = 1.0
        n = int(length // seg)
        for i in range(n):
            x = -length / 2 + seg * (i + 0.5)
            roll = rng.random()
            if roll < 0.45:
                h = height
            elif roll < 0.85:
                h = rng.uniform(0.9, height * 0.85)
            else:
                h = 0.3
            col = _mix(wall_col, CHARRED, rng.uniform(0.0, 0.45))
            if h >= height and i % 3 == 1:
                mb.box("block", x, 0, fh, seg, t, 1.0, col, collide=True)
                mb.box("block", x, 0, fh + 2.2, seg, t, h - 2.2, col, bottom=True, collide=True)
            else:
                mb.box("block", x, 0, fh, seg, t, h, col, collide=True)

    with mb.place(0, -hd + t / 2):
        broken_wall(width)
    with mb.place(0, hd - t / 2):
        broken_wall(width)
    for sx in (-1, 1):
        with mb.place(sx * (hw - t / 2), 0, 0, 90):
            broken_wall(depth - 2 * t)
    # Collapsed roof slab and rubble.
    mb.box("concrete", rng.uniform(-2, 2), rng.uniform(-1, 1), fh, 4.0, 2.6, 0.22, _vary(ROOF_TAR, rng),
           yaw=rng.uniform(-30, 30), collide=True)
    for _ in range(3):
        with mb.place(rng.uniform(-hw + 2, hw - 2), rng.uniform(-hd + 2, hd - 2), fh):
            build_rubble(mb, rng, size=1.6, count=7)


def build_hangar(mb, rng, length=24.0, radius=8.0, segments=16, door_width=10.0, door_height=6.0):
    """Quonset-style arched hangar. Open front faces local -Y."""
    shell = _vary((0.58, 0.59, 0.55), rng)
    hl = length / 2
    mb.box("concrete", 0, 0, 0, 2 * radius + 0.4, length + 0.4, 0.1, _vary(CONCRETE_DARK, rng), collide=True)
    arc = [(radius * math.cos(math.pi * i / segments), radius * math.sin(math.pi * i / segments))
           for i in range(segments + 1)]
    with mb.place(0, 0, 0, 90):            # local X now runs along the hangar length
        # Outer and inner skin 8 cm apart (a zero-thickness double-sided skin shadows itself = "acne").
        mb.extrude_x("corrugated", arc, -hl, hl, shell, closed=False, caps=False)
        inner = [(x * (radius - 0.08) / radius, z * (radius - 0.08) / radius) for x, z in reversed(arc)]
        mb.extrude_x("corrugated", inner, -hl, hl, _scale(shell, 0.8), closed=False, caps=False)
        rib = [(x * 1.008, z * 1.008) for x, z in arc]
        rib_col = _scale(shell, 0.7)
        n_ribs = int(length // 4)
        for i in range(n_ribs + 1):
            xr = -hl + i * (length / n_ribs)
            mb.extrude_x("metal", rib, xr - 0.08, xr + 0.08, rib_col, closed=False, caps=False)
        # Shell collision: boxes around the low arc segments.
        for i in range(segments):
            (y0, z0), (y1, z1) = arc[i], arc[i + 1]
            zlo, zhi = min(z0, z1), max(z0, z1)
            if zlo > 3.5:
                continue
            ylo, yhi = min(y0, y1), max(y0, y1)
            mb.collider_box(0, (ylo + yhi) / 2, zlo, length, (yhi - ylo) + 0.15, zhi - zlo)
        # Thin roof strip under the top of the arch (lets rain, flares etc. know this is indoors).
        mb.collider_box(0, 0, radius * 0.95, length, radius * 1.6, 0.2)
        # Back wall (closed semicircle).
        back_col = _vary(STEEL, rng)
        mb.polygon_x("corrugated", hl + 0.04, arc, back_col, facing=1)
        mb.polygon_x("corrugated", hl - 0.04, arc, back_col, facing=-1)
        mb.collider_box(hl, 0, 0, 0.3, 2 * radius, radius * 0.95)
        # Front wall pieces around the door opening.
        dh, dw2 = door_height, door_width / 2
        yi = math.sqrt(max(0.0, radius * radius - dh * dh))
        top_poly = [(yi, dh)] + [(y, z) for y, z in arc if z > dh] + [(-yi, dh)]
        mb.polygon_x("corrugated", -hl - 0.04, top_poly, back_col, facing=-1)
        mb.polygon_x("corrugated", -hl + 0.04, top_poly, back_col, facing=1)
        for s in (1, -1):
            pts = [(s * dw2, 0.0), (s * radius, 0.0)]
            pts += [(y, z) for y, z in arc if 0 < z < dh and y * s > 0]
            pts += [(s * yi, dh), (s * dw2, dh)]
            if s < 0:
                pts.reverse()
            mb.polygon_x("corrugated", -hl - 0.04, pts, back_col, facing=-1)
            mb.polygon_x("corrugated", -hl + 0.04, pts, back_col, facing=1)
            mb.collider_box(-hl, s * (dw2 + (radius - dw2) / 2), 0, 0.3, radius - dw2, dh)
            mb.box("metal", -hl, s * dw2, 0, 0.3, 0.3, dh, DARK_STEEL, collide=True)
        mb.box("metal", -hl, 0, dh, 0.35, door_width + 0.3, 0.35, DARK_STEEL, bottom=True)
        # Half-open sliding door on one side.
        mb.box("corrugated", -hl - 0.3, dw2 - 1.75, 0, 0.1, 3.5, dh - 0.1, _vary(OLIVE, rng), collide=True)
        # Hanging lamps.
        for i in range(3):
            xl = -hl + length * (i + 1) / 4
            zl = radius * 0.82
            mb.cylinder_between("metal", (xl, 0, radius), (xl, 0, zl + 0.3), 0.01, DARK, segments=3)
            with mb.place(xl, 0, zl):
                mb.cylinder("metal", 0, 0, 0, 0.45, 0.3, DARK_STEEL, radius_top=0.12, segments=10, top=True)
                mb.cylinder("emissive", 0, 0, -0.02, 0.38, 0.02, LAMP_WARM, segments=10, top=False, bottom=True)
    # Interior: workbench, shelves, drums (in hangar-local coords; length along Y).
    with mb.place(radius - 1.4, hl - 6.0):
        mb.box("wood", 0, 0, 0, 0.9, 3.0, 0.9, _vary(WOOD_DARK, rng), collide=True)
        mb.box("metal", 0, 0.8, 0.9, 0.5, 0.4, 0.3, RED_PAINT)
        mb.box("metal", 0.3, 0, 0.9, 0.05, 2.8, 1.2, _vary(STEEL, rng))
    with mb.place(-radius + 1.6, hl - 3.0):
        for z in (0.0, 0.9, 1.8):
            mb.box("metal", 0, 0, z, 1.0, 3.0, 0.05, DARK_STEEL)
            for j in range(3):
                mb.box("wood", 0, -1.0 + j, z + 0.05, 0.6, 0.6, 0.45, _vary(OLIVE, rng, 0.1))
        for py in (-1.5, 1.5):
            for px in (-0.5, 0.5):
                mb.box("metal", px, py, 0, 0.05, 0.05, 2.4, DARK_STEEL)
        mb.collider_box(0, 0, 0, 1.0, 3.0, 2.4)


def build_watchtower(mb, rng, height=4.0, size=3.2):
    """Wooden guard tower with stairs rising from the local -Y side."""
    hs = size / 2
    post = 0.22
    wood = _vary(WOOD_DARK, rng)
    roof_z = height + 2.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box("wood", sx * (hs - post / 2), sy * (hs - post / 2), 0, post, post, roof_z, wood, collide=True)
    for sx in (-1, 1):
        x = sx * (hs - post / 2)
        mb.cylinder_between("wood", (x, -hs + 0.15, 0.3), (x, hs - 0.15, height - 0.3), 0.06, wood, segments=5)
        mb.cylinder_between("wood", (x, hs - 0.15, 0.3), (x, -hs + 0.15, height - 0.3), 0.06, wood, segments=5)
    mb.cylinder_between("wood", (-hs + 0.15, hs - 0.11, 0.3), (hs - 0.15, hs - 0.11, height - 0.3), 0.06, wood, segments=5)
    mb.box("wood", 0, 0, height - 0.18, size + 0.2, size + 0.2, 0.18, _vary(WOOD, rng), bottom=True, collide=True)
    rail_h, t = 1.05, 0.08
    plank = _vary(WOOD, rng, 0.08)
    mb.box("wood", 0, hs + 0.06, height, size + 0.2, t, rail_h, plank, collide=True)
    for sx in (-1, 1):
        mb.box("wood", sx * (hs + 0.06), 0, height, t, size + 0.2, rail_h, plank, collide=True)
    gap = 1.3
    seg = (size + 0.2 - gap) / 2
    for sx in (-1, 1):
        mb.box("wood", sx * (gap / 2 + seg / 2), -hs - 0.06, height, seg, t, rail_h, plank, collide=True)
    # Sandbags along the front rail.
    for i in range(4):
        mb.ellipsoid("fabric", -1.1 + i * 0.73, hs - 0.2, height + 0.12, 0.36, 0.2, 0.12, _vary(SAND, rng, 0.08),
                     rings=4, segments=8, noise=0.05, rng=rng)
    mb.box("corrugated", 0, 0, roof_z, size + 0.8, size + 0.8, 0.1, _vary(STEEL, rng), bottom=True, collide=True)
    # Searchlight.
    with mb.place(hs - 0.35, hs - 0.15, height + rail_h):
        mb.cylinder("metal", 0, 0, 0, 0.05, 0.3, DARK_STEEL, segments=6)
        mb.cylinder_between("metal", (0, 0.15, 0.45), (0, -0.25, 0.45), 0.22, DARK_STEEL, segments=10, caps=True)
        mb.cylinder_between("paint", (0, -0.251, 0.45), (0, -0.26, 0.45), 0.18, LENS, segments=10, caps=True)
    # Stairs.
    n_steps = math.ceil(height / 0.25 - 1e-6)
    end = -hs - 0.1 - n_steps * 0.30                 # bottom of the stairs (far from the tower)
    stairs(mb, 0, end, 1.2, height, material="wood", color=WOOD, rng=rng, direction=1)
    for sx in (-0.62, 0.62):
        mb.cylinder_between("wood", (sx, end, 1.0), (sx, -hs - 0.1, height + 1.0), 0.035, wood, segments=4)
        mb.cylinder("wood", sx, end, 0, 0.04, 1.0, wood, segments=4)


# ============================================================================= barriers
def build_t_wall_row(mb, rng, length=20.0, height=3.6):
    """Row of tall concrete T-wall blast barriers along local X."""
    panel = 1.52
    n = max(1, int(length // panel))
    actual = n * panel
    start = -actual / 2 + panel / 2
    for i in range(n):
        x = start + i * panel
        col = _vary(CONCRETE, rng, 0.07)
        mb.box("concrete", x, 0, 0, panel - 0.04, 1.0, 0.35, col)
        mb.box("concrete", x, 0, 0.35, panel - 0.04, 0.3, height - 0.35, col)
        for lx in (-0.35, 0.35):
            mb.cylinder_between("metal", (x + lx, -0.05, height), (x + lx, 0.05, height + 0.12), 0.03, DARK_STEEL, segments=4)
        if rng.random() < 0.18:
            mb.box("paint", x, -0.152, 1.2, 0.9, 0.004, 0.5, _vary(YELLOW_PAINT, rng, 0.1))
    mb.collider_box(0, 0, 0, actual, 1.0, 0.35)
    mb.collider_box(0, 0, 0, actual, 0.3, height)


def build_fence(mb, rng, length=20.0, height=2.4, spacing=3.0, barbed=True):
    """Chain-link fence along local X with posts and barbed wire."""
    n = max(1, round(length / spacing))
    step = length / n
    post = _vary(STEEL, rng)
    hl = length / 2
    for i in range(n + 1):
        x = -hl + i * step
        mb.cylinder("concrete", x, 0, -0.05, 0.13, 0.15, CONCRETE_DARK, segments=8)
        mb.cylinder("metal", x, 0, 0, 0.045, height + 0.05, post, segments=6)
        if barbed:
            mb.cylinder_between("metal", (x, 0, height), (x, -0.38, height + 0.42), 0.025, post, segments=4)
    mb.cylinder_between("metal", (-hl, 0, height - 0.05), (hl, 0, height - 0.05), 0.03, post, segments=5)
    mb.cylinder_between("metal", (-hl, 0, 0.08), (hl, 0, 0.08), 0.012, post, segments=3)
    mb.quad("chainlink", (-hl, 0, 0.03), (hl, 0, 0.03), (hl, 0, height), (-hl, 0, height),
            (0.78, 0.80, 0.80), double_sided=True)
    if barbed:
        for k in range(3):
            off = 0.12 * (k + 1)
            mb.cylinder_between("metal", (-hl, -off, height + off * 1.1), (hl, -off, height + off * 1.1),
                                0.008, DARK_STEEL, segments=3)
    mb.collider_box(0, 0, 0, length, 0.2, height + 0.45)


def build_main_gate(mb, rng, width=14.0, height=2.6):
    """Closed double gate between two concrete pillars (spans local X)."""
    pillar = 0.7
    for sx in (-1, 1):
        x = sx * (width / 2 + pillar / 2)
        col = _vary(CONCRETE, rng)
        mb.box("concrete", x, 0, 0, pillar, pillar, height + 0.6, col, collide=True)
        mb.box("concrete", x, 0, height + 0.6, pillar + 0.12, pillar + 0.12, 0.15, _scale(col, 0.85))
        mb.cylinder("emissive", x, 0, height + 0.75, 0.08, 0.12, LAMP_RED, segments=8)
    frame = _vary(OLIVE_DARK, rng)
    hw = width / 2
    for side in (-1, 1):
        x0, x1 = (0.03, hw) if side > 0 else (-hw, -0.03)
        cx = (x0 + x1) / 2
        w = x1 - x0
        for z in (0.1, height / 2, height - 0.1):
            mb.box("metal", cx, 0, z - 0.05, w, 0.08, 0.1, frame)
        for x in (x0 + 0.05, x1 - 0.05):
            mb.box("metal", x, 0, 0.05, 0.1, 0.1, height - 0.05, frame)
        nbars = int(w / 0.22)
        for i in range(1, nbars):
            bx = x0 + i * w / nbars
            mb.cylinder("metal", bx, 0, 0.1, 0.018, height - 0.2, frame, segments=4, top=False)
        mb.cylinder_between("metal", (x0 + 0.1, 0, 0.15), (x1 - 0.1, 0, height - 0.15), 0.035, frame, segments=4)
        mb.box("paint", cx, -0.06, height * 0.55, 1.4, 0.02, 0.7, RED_PAINT)
        mb.box("paint", cx, -0.075, height * 0.55 + 0.25, 1.1, 0.01, 0.1, WHITE_PAINT)
    mb.collider_box(0, 0, 0, width, 0.25, height)


def build_jersey_barrier(mb, rng, length=3.4, color=None):
    profile = [(0.30, 0.0), (0.27, 0.08), (0.10, 0.30), (0.08, 0.81), (-0.08, 0.81),
               (-0.10, 0.30), (-0.27, 0.08), (-0.30, 0.0)]
    n = max(1, round(length / 1.5))
    if mb.model_budget.get("road_barrier", 0) >= n:
        for i in range(n):
            mb.use_model("road_barrier", -length / 2 + length * (i + 0.5) / n, 0, 0, 0, length / n / 1.5)
        mb.collider_box(0, 0, 0, length, 0.56, 0.81)
        return
    col = _vary(_color(color, CONCRETE), rng, 0.07)
    mb.extrude_x("concrete", profile, -length / 2, length / 2, col)
    for x in (-length * 0.3, length * 0.3):
        mb.box("paint", x, 0, 0.0, 0.35, 0.62, 0.12, DARK)
    mb.collider_box(0, 0, 0, length, 0.56, 0.81)


def build_sandbag_wall(mb, rng, length=4.0, rows=4, color=None):
    base = _color(color, SAND)
    bag_l, bag_h = 0.6, 0.19
    n = max(1, round(length / bag_l))
    for r in range(rows):
        count = n if r % 2 == 0 else max(1, n - 1)
        start = -(count - 1) * bag_l / 2
        z = r * bag_h * 0.92 + bag_h * 0.5
        for i in range(count):
            mb.ellipsoid("fabric", start + i * bag_l + rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), z,
                         bag_l * 0.53, 0.30, bag_h * 0.62, _vary(base, rng, 0.08),
                         rings=4, segments=8, noise=0.05, rng=rng)
    mb.collider_box(0, 0, 0, n * bag_l, 0.62, rows * bag_h * 0.92 + 0.05)


def build_sandbag_bunker(mb, rng, width=4.2, depth=3.2, rows=5):
    """U-shaped sandbag position, open toward local +Y."""
    with mb.place(0, -depth / 2):
        build_sandbag_wall(mb, rng, width, rows)
    for sx in (-1, 1):
        with mb.place(sx * (width / 2 - 0.3), 0.3, 0, 90):
            build_sandbag_wall(mb, rng, depth - 0.6, rows)
    with mb.place(0.8, -0.6, 0, 10):
        build_crate(mb, rng, size=0.7)


def build_hesco(mb, rng, count=4):
    unit, h = 1.1, 1.35
    for i in range(count):
        x = (i - (count - 1) / 2) * (unit + 0.02)
        mb.box("hesco", x, 0, 0, unit, unit, h, _vary(SAND, rng, 0.05), top=False)
        mb.box("dirt", x, 0, h - 0.12, unit - 0.05, unit - 0.05, 0.1, (0.8, 0.72, 0.6))
    mb.collider_box(0, 0, 0, count * (unit + 0.02), unit, h)


# ============================================================================= small props
def build_crate(mb, rng, size=1.0, color=None):
    sx, sy, sz = size, size * 0.65, size * 0.6
    col = _vary(_color(color, OLIVE), rng, 0.08)
    trim = _scale(col, 0.75)
    mb.box("wood", 0, 0, 0, sx, sy, sz, col, collide=True)
    for x in (-sx / 2 + 0.05, sx / 2 - 0.05):
        mb.box("wood", x, 0, 0, 0.08, sy + 0.02, sz + 0.01, trim)
    mb.box("paint", 0, -sy / 2 - 0.006, sz * 0.35, sx * 0.4, 0.004, sz * 0.25, _scale((0.9, 0.86, 0.6), 0.9))
    for x in (-sx / 2 - 0.02, sx / 2 + 0.02):
        mb.box("metal", x, 0, sz * 0.55, 0.03, 0.18, 0.05, DARK_STEEL)


def build_crate_stack(mb, rng, count=5, color=None):
    base_n = min(3, count)
    placed = 0
    # Small real-model details next to the stack (ammo box on the ground, a jerrycan).
    mb.use_model("ammo_box", base_n * 0.55 + 0.3, -0.25, 0, rng.uniform(-30, 30))
    mb.use_model("jerrycan", -base_n * 0.55 - 0.3, 0.1, 0, rng.uniform(0, 360))
    for i in range(base_n):
        x = (i - (base_n - 1) / 2) * 1.08
        with mb.place(x + rng.uniform(-0.04, 0.04), rng.uniform(-0.05, 0.05), 0, rng.uniform(-5, 5)):
            build_crate(mb, rng, 1.0, color)
        placed += 1
    for i in range(min(count - placed, 2)):
        x = (i - 0.5) * 1.08 if count - placed > 1 else 0.0
        with mb.place(x + rng.uniform(-0.05, 0.05), rng.uniform(-0.04, 0.04), 0.61, rng.uniform(-8, 8)):
            build_crate(mb, rng, 1.0, color)


def build_barrel(mb, rng, color=None):
    r, h = 0.29, 0.88
    if mb.use_model("barrel", yaw=rng.uniform(0, 360)):
        mb.collider_cylinder(0, 0, 0, r, h)
        return
    col = _vary(_color(color, OLIVE), rng, 0.1)
    rib = _scale(col, 0.75)
    mb.cylinder("metal", 0, 0, 0, r, h, col, segments=14, collide=True)
    for z in (0.28, 0.6):
        mb.cylinder("metal", 0, 0, z, r + 0.012, 0.03, rib, segments=14, bottom=True)
    mb.cylinder("metal", 0, 0, h, r + 0.004, 0.025, rib, segments=14)
    mb.cylinder("metal", r * 0.5, 0, h, 0.035, 0.035, DARK_STEEL, segments=6)


def build_barrel_group(mb, rng, count=4, color=None):
    spots = [(0, 0), (0.62, 0), (0.31, 0.54), (-0.31, 0.54), (-0.62, 0), (-0.31, -0.54), (0.31, -0.54)]
    colours = [OLIVE, (0.55, 0.27, 0.16), (0.22, 0.33, 0.45), (0.25, 0.25, 0.24)]
    for i in range(min(count, len(spots))):
        x, y = spots[i]
        c = rng.choice(colours) if color == "mixed" else _color(color, OLIVE)
        with mb.place(x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02), 0, rng.uniform(0, 360)):
            build_barrel(mb, rng, c)


def build_pallet(mb, rng, load=None):
    col = _vary(WOOD, rng, 0.1)
    for y in (-0.42, 0.0, 0.42):
        mb.box("wood", 0, y, 0, 1.2, 0.1, 0.1, _scale(col, 0.85))
    for i in range(5):
        mb.box("wood", -0.5 + i * 0.25, 0, 0.1, 0.18, 1.0, 0.03, col)
    mb.collider_box(0, 0, 0, 1.2, 1.0, 0.13)
    if load == "sandbags":
        for i in range(3):
            for j in range(2):
                mb.ellipsoid("fabric", -0.3 + j * 0.6, -0.3 + i * 0.3, 0.22, 0.3, 0.15, 0.09, _vary(SAND, rng, 0.08),
                             rings=4, segments=8, noise=0.05, rng=rng)
        mb.collider_box(0, 0, 0.13, 1.2, 1.0, 0.2)
    elif load == "crate":
        with mb.place(0, 0, 0.13):
            build_crate(mb, rng, 1.0)


def build_tire_stack(mb, rng, count=4):
    for i in range(count):
        x, y = rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)
        mb.cylinder("paint", x, y, i * 0.24, 0.42, 0.22, RUBBER, segments=16)
        if i == count - 1:
            mb.cylinder("paint", x, y, i * 0.24 + 0.221, 0.24, 0.002, DARK, segments=12)
    mb.collider_cylinder(0, 0, 0, 0.45, count * 0.24)


def build_generator(mb, rng, color=None):
    col = _vary(_color(color, OLIVE), rng)
    mb.box("metal", 0, 0, 0, 1.4, 2.6, 0.15, DARK_STEEL)
    mb.box("metal", 0, 0, 0.15, 1.2, 2.2, 1.25, col)
    for sx in (-1, 1):
        for i in range(5):
            mb.box("metal", sx * 0.605, -0.6 + i * 0.12, 0.6, 0.02, 0.06, 0.55, _scale(col, 0.5))
    mb.box("metal", 0, 1.12, 0.6, 0.7, 0.06, 0.5, DARK_STEEL)
    mb.box("emissive", -0.2, 1.155, 0.95, 0.06, 0.01, 0.06, LAMP_GREEN)
    mb.cylinder("metal", 0.3, -0.7, 1.4, 0.07, 0.6, DARK, segments=8)
    mb.cylinder_between("paint", (-0.6, 0.8, 0.3), (-1.5, 1.6, 0.02), 0.03, DARK, segments=4)
    mb.collider_box(0, 0, 0, 1.4, 2.6, 1.4)


def build_fuel_tank(mb, rng, length=7.0, radius=1.3, color=None):
    col = _vary(_color(color, (0.70, 0.70, 0.66)), rng)
    for y in (-length * 0.3, 0.0, length * 0.3):
        mb.box("concrete", 0, y, 0, radius * 1.7, 0.5, 0.75, _vary(CONCRETE_DARK, rng))
    zc = radius + 0.35
    mb.cylinder_between("metal", (0, -length / 2, zc), (0, length / 2, zc), radius, col, segments=18)
    for sy in (-1, 1):
        mb.ellipsoid("metal", 0, sy * length / 2, zc, radius, 0.45, radius, col, rings=6, segments=18)
    for y in (-length * 0.33, length * 0.33):
        mb.cylinder_between("metal", (0, y - 0.05, zc), (0, y + 0.05, zc), radius + 0.02, _scale(col, 0.8), segments=18)
    mb.box("metal", 0, 0, zc + radius - 0.02, 0.6, length * 0.6, 0.05, DARK_STEEL)
    mb.box("paint", radius * 0.98, 0, zc, 0.02, 0.8, 0.8, RED_PAINT)
    mb.cylinder_between("metal", (0, length / 2 + 0.3, 0.5), (0, length / 2 + 1.4, 0.5), 0.08, DARK_STEEL, segments=6)
    mb.box("metal", 0, length / 2 + 1.5, 0, 0.4, 0.3, 0.7, RED_PAINT)
    mb.collider_box(0, 0, 0, radius * 2, length + 0.9, zc + radius)


def build_light_pole(mb, rng, height=7.5, arm=1.6):
    mb.cylinder("concrete", 0, 0, 0, 0.25, 0.35, CONCRETE_DARK, segments=8)
    mb.cylinder("metal", 0, 0, 0.35, 0.09, height - 0.35, STEEL, segments=8, radius_top=0.06)
    mb.cylinder_between("metal", (0, 0, height - 0.25), (0, arm, height), 0.045, STEEL, segments=6)
    mb.box("metal", 0, arm + 0.15, height - 0.12, 0.35, 0.6, 0.18, DARK_STEEL)
    mb.box("paint", 0, arm + 0.15, height - 0.14, 0.28, 0.5, 0.02, LENS, top=False, bottom=True)
    mb.collider_cylinder(0, 0, 0, 0.25, height)


def build_radio_mast(mb, rng, height=20.0):
    mb.box("concrete", 0, 0, 0, 3.2, 3.2, 0.2, _vary(CONCRETE_DARK, rng), collide=True)
    sections = 8
    base_r, top_r = 1.3, 0.35

    def leg(i, t):
        a = math.radians(90 + 120 * i)
        r = base_r + (top_r - base_r) * t
        return r * math.cos(a), r * math.sin(a), 0.2 + t * height

    for s in range(sections):
        t0, t1 = s / sections, (s + 1) / sections
        col = _vary(RED_PAINT if s % 2 == 0 else WHITE_PAINT, rng, 0.05)
        for i in range(3):
            j = (i + 1) % 3
            mb.cylinder_between("metal", leg(i, t0), leg(i, t1), 0.06, col, segments=5)
            mb.cylinder_between("metal", leg(i, t0), leg(j, t1), 0.025, DARK_STEEL, segments=4)
            mb.cylinder_between("metal", leg(i, t0), leg(j, t0), 0.025, DARK_STEEL, segments=4)
    top = 0.2 + height
    mb.cylinder("metal", 0, 0, top, 0.05, 3.0, STEEL, segments=6, radius_top=0.02)
    mb.ellipsoid("emissive", 0, 0, top + 3.05, 0.12, 0.12, 0.12, LAMP_RED, rings=4, segments=6)
    for i, z in enumerate((height * 0.62, height * 0.8)):
        a = math.radians(30 + 140 * i)
        dx, dy = math.cos(a), math.sin(a)
        mb.cylinder_between("metal", (dx * 0.5, dy * 0.5, z), (dx * 0.95, dy * 0.95, z), 0.05, WHITE_PAINT,
                            radius_end=0.65, segments=14, caps=True)
    mb.box("metal", 1.9, 0, 0.2, 0.8, 1.2, 1.7, _vary(OLIVE, rng), collide=True)
    mb.collider_box(0, 0, 0, 2.8, 2.8, height)


def build_tent(mb, rng, length=5.0, width=4.0, height=2.6, color=None):
    col = _vary(_color(color, OLIVE), rng, 0.06)
    hw = width / 2
    profile = [(hw, 0.0), (hw, 1.2), (0.0, height), (-hw, 1.2), (-hw, 0.0)]
    mb.extrude_x("fabric", profile, -length / 2, length / 2, col)
    mb.polygon_x("paint", -length / 2 - 0.01, [(0.6, 0.0), (0.6, 1.8), (-0.6, 1.8), (-0.6, 0.0)], DARK, facing=-1)
    for sx in (-1, 1):
        x = sx * (length / 2)
        mb.cylinder("wood", x + sx * 0.02, 0, 0, 0.04, height + 0.15, WOOD_DARK, segments=5)
        for sy in (-1, 1):
            mb.cylinder_between("paint", (x, sy * hw, 1.15), (x + sx * 0.8, sy * (hw + 1.0), 0.0), 0.008,
                                (0.75, 0.7, 0.55), segments=3)
    mb.collider_box(0, 0, 0, length, width, height * 0.8)


def build_container(mb, rng, length=6.06, color="rust"):
    """20 ft shipping container along local X; doors at the +X end."""
    w, h = 2.44, 2.59
    col = _vary(_color(color, NAMED_COLORS["rust"]), rng, 0.07)
    frame = _scale(col, 0.6)
    mb.box("corrugated", 0, 0, 0, length, w, h, col, collide=True)
    hl, hw = length / 2, w / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box("metal", sx * (hl - 0.08), sy * (hw - 0.08), 0, 0.18, 0.18, h + 0.01, frame)
    for z in (0.0, h - 0.12):
        for sy in (-1, 1):
            mb.box("metal", 0, sy * (hw + 0.005), z, length - 0.3, 0.04, 0.13, frame)
    mb.box("metal", hl + 0.01, 0, 0.05, 0.02, 0.03, h - 0.15, DARK)
    for y in (-0.8, -0.35, 0.35, 0.8):
        mb.cylinder("metal", hl + 0.04, y, 0.15, 0.025, h - 0.3, DARK_STEEL, segments=5)
    mb.box("paint", -hl * 0.4, -hw - 0.006, h * 0.62, 1.4, 0.004, 0.32, _scale(WHITE_PAINT, 0.85))


# ============================================================================= vehicles
def _wheel(mb, x, y, r, width, rim_color, missing=False):
    if missing:
        return
    mb.cylinder_between("paint", (x - width / 2, y, r), (x + width / 2, y, r), r, RUBBER, segments=14, caps=True)
    side = 1 if x > 0 else -1
    mb.cylinder_between("metal", (x + side * width / 2, y, r), (x + side * (width / 2 + 0.02), y, r), r * 0.55,
                        rim_color, segments=10, caps=True)


def build_jeep(mb, rng, color=None, burnt=False, windscreen=True):
    body = CHARRED if burnt else _vary(_color(color, OLIVE), rng)
    if burnt:
        body = _mix(body, (0.35, 0.18, 0.1), rng.uniform(0.1, 0.35))
    dark = (0.12, 0.12, 0.11)
    lift = -0.12 if burnt else 0.0
    for sx in (-1, 1):
        for wy in (-1.25, 1.3):
            _wheel(mb, sx * 0.83, wy, 0.38, 0.3, _scale(body, 0.8), missing=burnt and sx == 1 and wy < 0)
    z = lift
    mb.box("metal", 0, 0, z + 0.35, 1.5, 3.5, 0.25, dark)
    mb.box("metal", 0, -0.55, z + 0.55, 1.72, 2.8, 0.6, body)
    mb.box("metal", 0, 1.35, z + 0.55, 1.55, 1.0, 0.5, body)
    mb.box("metal", 0, 1.9, z + 0.5, 1.4, 0.1, 0.5, dark)
    for i in range(5):
        mb.box("metal", -0.4 + i * 0.2, 1.96, z + 0.58, 0.05, 0.03, 0.34, _scale(body, 0.6))
    for sx in (-1, 1):
        mb.box("metal", sx * 0.83, 1.32, z + 1.0, 0.45, 0.85, 0.05, body)
        mb.box("metal", sx * 0.83, -1.25, z + 1.15, 0.45, 0.8, 0.05, body)
    mb.box("metal", 0, 2.0, z + 0.42, 1.8, 0.12, 0.16, dark)
    if not burnt:
        for sx in (-0.55, 0.55):
            mb.cylinder_between("paint", (sx, 1.85, z + 0.85), (sx, 1.92, z + 0.85), 0.09, LENS, segments=8, caps=True)
        if windscreen:
            mb.box("paint", 0, 0.85, z + 1.12, 1.45, 0.03, 0.6, GLASS)
    if windscreen:
        for sx in (-0.75, 0.75):
            mb.box("metal", sx, 0.85, z + 1.05, 0.06, 0.06, 0.75, dark)
        mb.box("metal", 0, 0.85, z + 1.76, 1.56, 0.06, 0.06, dark, bottom=True)
    seat = (0.2, 0.2, 0.17) if burnt else (0.28, 0.3, 0.22)
    for sx in (-0.42, 0.42):
        mb.box("fabric", sx, 0.1, z + 1.15, 0.5, 0.5, 0.15, seat)
        mb.box("fabric", sx, -0.15, z + 1.15, 0.5, 0.12, 0.55, seat)
    mb.box("fabric", 0, -1.0, z + 1.15, 1.4, 0.5, 0.15, seat)
    mb.cylinder_between("metal", (-0.42, 0.55, z + 1.25), (-0.42, 0.5, z + 1.32), 0.17, dark, segments=10, caps=True)
    for sx in (-0.8, 0.8):
        mb.cylinder_between("metal", (sx, -0.6, z + 1.15), (sx, -0.6, z + 1.9), 0.035, dark, segments=6)
    mb.cylinder_between("metal", (-0.8, -0.6, z + 1.9), (0.8, -0.6, z + 1.9), 0.035, dark, segments=6)
    if not burnt:
        mb.cylinder_between("paint", (0, -1.97, z + 0.95), (0, -2.17, z + 0.95), 0.36, RUBBER, segments=14, caps=True)
        mb.box("metal", 0.55, -1.75, z + 1.15, 0.2, 0.35, 0.45, _scale(body, 0.85))
        mb.cylinder("metal", -0.75, -1.85, z + 1.15, 0.012, 2.2, DARK_STEEL, segments=3)
    mb.collider_box(0, 0, 0, 1.8, 3.95, 1.15 + lift)


def build_truck(mb, rng, color=None, covered=True, burnt=False, cargo=True):
    body = CHARRED if burnt else _vary(_color(color, OLIVE), rng)
    if burnt:
        body = _mix(body, (0.35, 0.18, 0.1), rng.uniform(0.1, 0.3))
    dark = (0.12, 0.12, 0.11)
    for sx in (-1, 1):
        for i, wy in enumerate((2.45, -1.55, -2.75)):
            _wheel(mb, sx * 1.0, wy, 0.52, 0.38, _scale(body, 0.8), missing=burnt and i == 1 and sx < 0)
    mb.box("metal", 0, -0.2, 0.55, 1.1, 6.6, 0.3, dark)
    mb.box("metal", 0, 3.6, 0.45, 2.3, 0.15, 0.3, dark)
    mb.box("metal", 0, 3.0, 0.85, 1.9, 1.0, 0.85, body)
    mb.box("metal", 0, 3.52, 0.9, 1.5, 0.06, 0.7, dark)
    for sx in (-1, 1):
        mb.box("metal", sx * 1.0, 2.45, 1.08, 0.55, 1.1, 0.06, body)
        mb.box("metal", sx * 1.25, 2.45, 0.6, 0.06, 1.1, 0.48, body)
        if not burnt:
            mb.cylinder_between("paint", (sx * 0.7, 3.5, 1.35), (sx * 0.7, 3.56, 1.35), 0.12, LENS, segments=8, caps=True)
    mb.box("metal", 0, 1.85, 0.95, 2.3, 1.3, 1.75, body)
    mb.box("metal", 0, 1.85, 2.7, 2.36, 1.42, 0.06, _scale(body, 0.85), bottom=True)
    glass = DARK if burnt else GLASS
    mb.box("paint", 0, 2.51, 1.85, 1.9, 0.03, 0.7, glass)
    for sx in (-1, 1):
        mb.box("paint", sx * 1.155, 2.0, 1.85, 0.03, 0.8, 0.6, glass)
        mb.box("metal", sx * 1.2, 1.3, 0.35, 0.3, 0.5, 0.06, dark)
    mb.cylinder_between("metal", (1.1, 0.25, 0.8), (1.1, 1.1, 0.8), 0.25, _scale(body, 0.9), segments=10, caps=True)
    mb.cylinder("metal", -1.05, 1.15, 1.2, 0.06, 2.0, dark, segments=6)
    mb.box("metal", 0, -1.15, 1.05, 2.4, 4.7, 0.15, body)
    for sx in (-1, 1):
        mb.box("wood", sx * 1.17, -1.15, 1.2, 0.06, 4.7, 0.5, _scale(body, 0.9))
    mb.box("wood", 0, -3.47, 1.2, 2.4, 0.06, 0.5, _scale(body, 0.9))
    bed_h = 1.7
    if covered and not burnt:
        canvas = _vary((0.40, 0.42, 0.30), rng)
        profile = [(1.2, 1.2), (1.2, 2.45), (0.85, 2.95), (0.0, 3.1), (-0.85, 2.95), (-1.2, 2.45), (-1.2, 1.2)]
        with mb.place(0, 0, 0, 90):
            mb.extrude_x("fabric", profile, -3.5, 1.15, canvas)
            inner = [(y * 0.85, 1.2 + (z - 1.2) * 0.85) for y, z in profile]
            mb.polygon_x("paint", -3.51, inner, DARK, facing=-1)
        bed_h = 3.1
    elif burnt:
        for y in (-3.2, -2.0, -0.8, 0.4):
            mb.cylinder_between("metal", (-1.15, y, 1.3), (-1.15, y, 2.4), 0.03, dark, segments=4)
            mb.cylinder_between("metal", (-1.15, y, 2.4), (1.15, y, 2.4), 0.03, dark, segments=4)
            mb.cylinder_between("metal", (1.15, y, 2.4), (1.15, y, 1.3), 0.03, dark, segments=4)
    elif cargo:
        for i, y in enumerate((-2.6, -1.4, -0.2)):
            with mb.place(rng.uniform(-0.3, 0.3), y, 1.2, rng.uniform(-6, 6)):
                build_crate(mb, rng, 1.0)
        bed_h = 1.85
    mb.collider_box(0, 2.35, 0, 2.4, 2.5, 2.7)
    mb.collider_box(0, -1.15, 0, 2.45, 4.7, bed_h)


# ============================================================================= nature
def build_tree_pine(mb, rng, height=11.0):
    h = height
    trunk_r = 0.12 + h * 0.012
    mb.cylinder("bark", 0, 0, 0, trunk_r, h * 0.55, _vary(BARK, rng), segments=7, radius_top=trunk_r * 0.6, top=False)
    mb.collider_cylinder(0, 0, 0, trunk_r + 0.05, h * 0.5)
    layers = 5 if h > 12 else 4
    green = _vary(PINE_GREEN, rng, 0.14)
    for i in range(layers):
        t = i / layers
        base_z = h * (0.22 + 0.68 * t)
        radius = h * (0.30 - 0.21 * t)
        cone_h = h * (0.36 - 0.12 * t)
        mb.cylinder("foliage", rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), base_z, radius, cone_h,
                    _scale(green, 0.82 + 0.3 * t), segments=9, radius_top=0.0, top=False, bottom=True,
                    radial_noise=0.18, rng=rng)


def build_tree_broadleaf(mb, rng, height=9.0):
    h = height
    trunk_r = 0.14 + h * 0.015
    bark = _vary(BARK, rng)
    mb.cylinder("bark", 0, 0, 0, trunk_r, h * 0.55, bark, segments=7, radius_top=trunk_r * 0.7, top=False)
    mb.collider_cylinder(0, 0, 0, trunk_r + 0.05, h * 0.5)
    for _ in range(3):
        a = rng.uniform(0, 2 * math.pi)
        z0 = h * rng.uniform(0.35, 0.5)
        mb.cylinder_between("bark", (0, 0, z0), (math.cos(a) * h * 0.2, math.sin(a) * h * 0.2, h * 0.66),
                            trunk_r * 0.45, bark, segments=5, radius_end=trunk_r * 0.2)
    base = _vary(LEAF_GREEN, rng, 0.12)
    for _ in range(rng.randint(4, 6)):
        col = _mix(_scale(base, rng.uniform(0.85, 1.12)), (0.55, 0.52, 0.28), rng.uniform(0.0, 0.25))
        mb.ellipsoid("foliage", rng.uniform(-h * 0.18, h * 0.18), rng.uniform(-h * 0.18, h * 0.18),
                     h * rng.uniform(0.62, 0.8), h * rng.uniform(0.2, 0.28), h * rng.uniform(0.2, 0.28),
                     h * rng.uniform(0.15, 0.22), col, rings=5, segments=9, noise=0.18, rng=rng)


def build_tree_dead(mb, rng, height=8.0):
    h = height
    r = 0.12 + h * 0.012
    col = _vary((0.40, 0.36, 0.31), rng)
    mb.cylinder("bark", 0, 0, 0, r, h * 0.75, col, segments=6, radius_top=r * 0.35, top=False)
    mb.collider_cylinder(0, 0, 0, r + 0.05, h * 0.6)
    for _ in range(rng.randint(4, 6)):
        a = rng.uniform(0, 2 * math.pi)
        z0 = h * rng.uniform(0.35, 0.7)
        length = h * rng.uniform(0.18, 0.32)
        mb.cylinder_between("bark", (0, 0, z0), (math.cos(a) * length, math.sin(a) * length, z0 + length * 0.7),
                            r * 0.35, col, segments=4, radius_end=r * 0.08)


def build_bush(mb, rng, size=1.0):
    base = _vary(LEAF_GREEN, rng, 0.15)
    for _ in range(rng.randint(2, 3)):
        mb.ellipsoid("foliage", rng.uniform(-0.3, 0.3) * size, rng.uniform(-0.3, 0.3) * size, size * 0.3,
                     size * rng.uniform(0.45, 0.65), size * rng.uniform(0.45, 0.65), size * rng.uniform(0.38, 0.52),
                     _scale(base, rng.uniform(0.8, 1.1)), rings=4, segments=8, noise=0.2, rng=rng)


def build_rock(mb, rng, size=1.2):
    rx = size * rng.uniform(0.8, 1.3)
    ry = size * rng.uniform(0.7, 1.2)
    rz = size * rng.uniform(0.45, 0.8)
    if size >= 1.0 and mb.use_model("boulder", 0, 0, -rz * 0.25, rng.uniform(0, 360), rz * 1.2):
        mb.collider_cylinder(0, 0, 0, min(rx, ry) * 0.8, rz * 1.15)
        return
    col = _mix(_vary(ROCK_GREY, rng, 0.1), (0.52, 0.45, 0.36), rng.uniform(0, 0.4))
    mb.ellipsoid("rock", 0, 0, rz * 0.25, rx, ry, rz, col, rings=5, segments=8, noise=0.22, rng=rng, flat=True)
    if rz * 1.25 > 0.3:
        mb.collider_cylinder(0, 0, 0, min(rx, ry) * 0.8, rz * 1.15)


def build_hill(mb, rng, radius=60.0, height=25.0):
    col = _mix((0.62, 0.62, 0.48), (0.58, 0.52, 0.42), rng.uniform(0, 1))
    mb.ellipsoid("dirt", 0, 0, -height * 0.35, radius, radius * rng.uniform(0.7, 1.0), height, col,
                 rings=7, segments=14, noise=0.12, rng=rng)


def build_rubble(mb, rng, size=2.0, count=10):
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, size * 0.6)
        s = rng.uniform(0.15, 0.45)
        col = rng.choice([_vary(CONCRETE, rng, 0.1), _vary(PALE_WALL, rng, 0.1), _vary((0.55, 0.32, 0.25), rng, 0.1)])
        mb.ellipsoid("concrete", math.cos(a) * d, math.sin(a) * d, s * 0.2, s * 1.2, s, s * 0.7, col,
                     rings=3, segments=5, noise=0.3, rng=rng, flat=True)
    for _ in range(2):
        mb.box("concrete", rng.uniform(-size * 0.4, size * 0.4), rng.uniform(-size * 0.4, size * 0.4), 0,
               rng.uniform(0.6, 1.2), rng.uniform(0.4, 0.8), rng.uniform(0.08, 0.18), _vary(CONCRETE, rng, 0.1),
               yaw=rng.uniform(0, 180))
    mb.collider_cylinder(0, 0, 0, size * 0.75, 0.3)


# ============================================================================= ground features
def build_road(mb, rng, length=50.0, width=8.0, gaps=()):
    hl, hw = length / 2, width / 2
    mb.flat_rect("dirt", -hl, -hw - 0.8, hl, hw + 0.8, 0.012, (0.82, 0.8, 0.76), world_uv=True)
    mb.flat_rect("asphalt", -hl, -hw, hl, hw, 0.02, (0.95, 0.95, 0.95), world_uv=True)

    def segments(a, b):
        parts = [(a, b)]
        for g0, g1 in gaps:
            nxt = []
            for s, e in parts:
                if e <= g0 or s >= g1:
                    nxt.append((s, e))
                else:
                    if s < g0:
                        nxt.append((s, g0))
                    if e > g1:
                        nxt.append((g1, e))
            parts = nxt
        return parts

    paint = (0.82, 0.82, 0.78)
    for y in (-hw + 0.25, hw - 0.25):
        for s, e in segments(-hl + 0.3, hl - 0.3):
            mb.flat_rect("paint", s, y - 0.07, e, y + 0.07, 0.03, paint)
    x = -hl + 1.0
    while x + 3.0 < hl:
        if rng.random() > 0.15:
            for s, e in segments(x, x + 3.0):
                mb.flat_rect("paint", s, -0.07, e, 0.07, 0.03, YELLOW_PAINT)
        x += 6.0
    for _ in range(max(1, int(length / 12))):
        px = rng.uniform(-hl + 2, hl - 4)
        py = rng.uniform(-hw + 0.6, hw - 2.0)
        mb.flat_rect("asphalt", px, py, px + rng.uniform(1.0, 3.0), py + rng.uniform(0.6, 1.6), 0.025,
                     (0.72, 0.72, 0.72), world_uv=True)


def build_concrete_pad(mb, rng, width=10.0, depth=10.0):
    hw, hd = width / 2, depth / 2
    mb.flat_rect("concrete", -hw, -hd, hw, hd, 0.03, _vary(CONCRETE_DARK, rng, 0.04), world_uv=True)
    joint = (0.25, 0.25, 0.24)
    x = -hw + 4.0
    while x < hw - 0.5:
        mb.flat_rect("paint", x - 0.03, -hd, x + 0.03, hd, 0.033, joint)
        x += 4.0
    y = -hd + 4.0
    while y < hd - 0.5:
        mb.flat_rect("paint", -hw, y - 0.03, hw, y + 0.03, 0.033, joint)
        y += 4.0


def build_helipad(mb, rng, size=18.0):
    mb.box("concrete", 0, 0, 0, size, size, 0.08, _vary(CONCRETE, rng), collide=True)
    z = 0.083
    r_out, r_in, n = 6.6, 6.2, 36
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        mb.quad("paint", (r_in * math.cos(a0), r_in * math.sin(a0), z), (r_out * math.cos(a0), r_out * math.sin(a0), z),
                (r_out * math.cos(a1), r_out * math.sin(a1), z), (r_in * math.cos(a1), r_in * math.sin(a1), z),
                YELLOW_PAINT)
    for x0, y0, x1, y1 in ((-2.0, -2.6, -1.2, 2.6), (1.2, -2.6, 2.0, 2.6), (-1.2, -0.4, 1.2, 0.4)):
        mb.flat_rect("paint", x0, y0, x1, y1, z + 0.001, WHITE_PAINT)
    hs = size / 2 - 0.3
    for i in range(8):
        a = 2 * math.pi * i / 8
        d = hs / max(abs(math.cos(a)), abs(math.sin(a)))
        mb.cylinder("emissive", d * math.cos(a), d * math.sin(a), 0.08, 0.1, 0.06, (1.0, 0.75, 0.2), segments=8)


# ============================================================================= trench warfare
EARTH = (0.47, 0.40, 0.31)
EARTH_DARK = (0.34, 0.29, 0.23)


def build_trench(mb, rng, length=20.0, width=2.2, front=True, rear=True, front_height=1.55, rear_height=1.2,
                 sandbags=True):
    """Trench section along local X. The front parapet faces local +Y (towards the enemy).

    The trench floor is at ground level; earth parapets on both sides make the walls.
    A firing step along the front wall lets the player shoot over the parapet.
    """
    hl, hw = length / 2, width / 2
    earth = _vary(EARTH, rng, 0.06)
    plank = _vary(WOOD_DARK, rng, 0.08)
    mb.box("wood", 0, 0, 0, length, 1.0, 0.05, _vary(WOOD, rng, 0.06))                 # duckboards
    for x in [-hl + 0.6 + i * 1.2 for i in range(int(length / 1.2))]:
        mb.box("wood", x, 0, 0.05, 0.06, 1.0, 0.004, (0.2, 0.16, 0.12))

    def wall(side, height, depth):
        s = 1 if side > 0 else -1
        y_in = s * hw
        # Earth bank profile (y, z), counter-clockwise seen from +X.
        if s > 0:
            profile = [(hw, 0.0), (hw + depth, 0.0), (hw + depth * 0.62, height * 0.58), (hw + 0.9, height),
                       (hw, height)]
        else:
            profile = [(-hw - depth, 0.0), (-hw, 0.0), (-hw, height), (-hw - 0.9, height),
                       (-hw - depth * 0.62, height * 0.58)]
        mb.extrude_x("dirt", profile, -hl, hl, earth)
        mb.box("wood", 0, y_in + s * 0.04, 0, length, 0.08, height, plank)               # revetment
        for x in [-hl + 0.3 + i * 2.0 for i in range(int(length / 2.0) + 1)]:
            if x <= hl:
                mb.box("wood", x, y_in - s * 0.02, 0, 0.12, 0.1, height + 0.12, _scale(plank, 0.7))
        # Stepped colliders approximating the bank.
        mb.collider_box(0, s * (hw + 0.75), 0, length, 1.5, height)
        mb.collider_box(0, s * (hw + 1.5 + (depth - 1.5) * 0.35), 0, length, (depth - 1.5) * 0.7, height * 0.58)
        mb.collider_box(0, s * (hw + depth - (depth - 1.5) * 0.15), 0, length, (depth - 1.5) * 0.3, 0.3)
        if sandbags and s > 0:
            with mb.place(0, s * (hw + 0.45), height - 0.08):
                build_sandbag_wall(mb, rng, length - 0.4, rows=1)

    if front:
        wall(1, front_height, 3.2)
        mb.box("wood", 0, hw - 0.28, 0, length, 0.5, 0.4, _vary(WOOD, rng), collide=True)  # firing step
    if rear:
        wall(-1, rear_height, 2.8)


def build_crater(mb, rng, radius=3.0):
    """Shell crater: a ring of churned earth (gaps let soldiers in) around a scorched centre."""
    n = 8
    mb.flat_rect("paint", -radius * 0.7, -radius * 0.7, radius * 0.7, radius * 0.7, 0.015, (0.16, 0.14, 0.12))
    for i in range(n):
        if i in (2, 6):                       # two gaps
            continue
        a = 2 * math.pi * i / n + rng.uniform(-0.1, 0.1)
        x, y = math.cos(a) * radius, math.sin(a) * radius
        h = rng.uniform(0.6, 0.95)
        mb.ellipsoid("dirt", x, y, 0.0, radius * 0.42, radius * 0.42, h, _vary(EARTH, rng, 0.1),
                     rings=4, segments=8, noise=0.2, rng=rng)
        mb.collider_cylinder(x, y, 0, radius * 0.3, h * 0.92)
    for _ in range(4):
        a = rng.uniform(0, 2 * math.pi)
        mb.ellipsoid("rock", math.cos(a) * radius * 0.4, math.sin(a) * radius * 0.4, 0.05, 0.2, 0.15, 0.1,
                     _vary(ROCK_GREY, rng), rings=3, segments=5, noise=0.3, rng=rng, flat=True)


def build_hedgehog(mb, rng):
    """Czech hedgehog anti-tank obstacle: three crossed steel beams."""
    col = _vary((0.3, 0.24, 0.2), rng, 0.15)
    r = 0.75
    for a in (0, 60, 120):
        rad = math.radians(a)
        dx, dy = math.cos(rad) * r, math.sin(rad) * r
        mb.cylinder_between("metal", (-dx, -dy, 0.0), (dx, dy, 1.35), 0.07, col, segments=4)
    mb.collider_cylinder(0, 0, 0, 0.6, 1.2)


def build_wire_line(mb, rng, length=12.0):
    """Barbed-wire entanglement on X-shaped wooden posts."""
    n = max(1, int(length / 2.5))
    step = length / n
    post = _vary(WOOD_DARK, rng)
    for i in range(n + 1):
        x = -length / 2 + i * step
        for s in (-1, 1):
            mb.cylinder_between("wood", (x - 0.25 * s, -0.35, 0.0), (x + 0.25 * s, 0.35, 1.0), 0.04, post, segments=4)
    for z in (0.25, 0.55, 0.85):
        for y in (-0.25, 0.25):
            mb.cylinder_between("metal", (-length / 2, y, z), (length / 2, y, z + rng.uniform(-0.05, 0.05)), 0.008,
                                DARK_STEEL, segments=3)
    for i in range(int(length / 0.6)):
        x = -length / 2 + i * 0.6
        mb.cylinder_between("metal", (x, -0.3, 0.2), (x + 0.6, 0.3, 0.9), 0.006, DARK_STEEL, segments=3)
    mb.collider_box(0, 0, 0, length, 0.8, 0.95)


def build_tank(mb, rng, burnt=True, color=None):
    """Main battle tank (wrecked by default). Front faces local +Y."""
    body = _mix(_vary(_color(color, OLIVE_DARK), rng), CHARRED, 0.65 if burnt else 0.0)
    dark = _scale(body, 0.6)
    mb.box("metal", 0, 0, 0.45, 3.2, 7.0, 1.1, body)                                    # hull
    mb.box("metal", 0, 3.2, 0.6, 3.0, 1.0, 0.8, body)                                   # glacis
    for s in (-1, 1):
        mb.box("metal", s * 1.75, 0, 0.0, 0.7, 7.2, 0.95, dark)                         # tracks
        for i in range(7):
            mb.cylinder_between("metal", (s * 1.42, -2.9 + i * 0.97, 0.42), (s * 2.12, -2.9 + i * 0.97, 0.42), 0.38,
                                _scale(dark, 0.8), segments=10, caps=True)
        mb.box("metal", s * 1.75, 0, 0.95, 0.85, 7.2, 0.06, body)                       # fenders
    with mb.place(0, -0.4, 1.55, rng.uniform(-40, 40) if burnt else 0):
        mb.cylinder("metal", 0, 0, 0, 1.55, 0.75, body, segments=12, radius_top=1.25)
        mb.box("metal", 0, 0.9, 0.15, 1.2, 1.4, 0.5, body)
        mb.cylinder_between("metal", (0, 1.4, 0.4), (0, 5.4, 0.48 if not burnt else 0.1), 0.09, dark, segments=8, caps=True)
        mb.cylinder("metal", 0.5, -0.4, 0.75, 0.3, 0.25, dark, segments=8)              # hatch
    mb.collider_box(0, 0, 0, 3.6, 7.4, 2.3)


def build_bunker(mb, rng, width=6.0, depth=5.0, height=2.3):
    """Concrete command bunker: firing slit towards local +Y, door at the back (-Y)."""
    t = 0.45
    hw, hd = width / 2, depth / 2
    col = _vary(CONCRETE_DARK, rng)
    wall_x(mb, -hw, hw, hd - t / 2, 0, height, t, "concrete", col, [(0.0, 2.2, 1.3, 1.7)])
    wall_x(mb, -hw, hw, -hd + t / 2, 0, height, t, "concrete", col, [(-1.2, 1.1, 0.0, 2.0)])
    for s in (-1, 1):
        with mb.place(s * (hw - t / 2), 0, 0, 90):
            wall_x(mb, -hd + t, hd - t, 0, 0, height, t, "concrete", col)
    mb.box("concrete", 0, 0, height, width + 0.4, depth + 0.4, 0.4, _scale(col, 0.9), bottom=True, collide=True)
    mb.ellipsoid("dirt", 0, 0, height + 0.3, hw + 0.6, hd + 0.6, 0.6, _vary(EARTH, rng), rings=4, segments=10,
                 noise=0.12, rng=rng)
    with mb.place(0, hd + 0.2, height + 0.4):
        build_sandbag_wall(mb, rng, width, rows=2)
    mb.box("wood", 1.2, 0.6, 0, 1.6, 0.9, 0.78, _vary(WOOD, rng), collide=True)          # map table
    mb.box("paint", 1.2, 0.6, 0.78, 1.3, 0.7, 0.01, (0.62, 0.66, 0.52))
    mb.box("metal", -1.6, 1.4, 0, 0.6, 0.45, 0.9, _vary(OLIVE, rng), collide=True)       # radio set
    mb.box("emissive", -1.6, 1.17, 0.7, 0.3, 0.01, 0.05, LAMP_GREEN)
    mb.cylinder("emissive", 0, 0, height - 0.12, 0.12, 0.1, LAMP_WARM, segments=8, bottom=True)


def build_mortar_pit(mb, rng, radius=2.4):
    """Sandbag ring (open at the back) with a mortar tube and ammunition."""
    for i in range(7):
        a = math.radians(-60 + i * 40)
        with mb.place(math.sin(a) * radius, math.cos(a) * radius, 0, -math.degrees(a)):
            build_sandbag_wall(mb, rng, 1.6, rows=3)
    tube = (0.15, 0.17, 0.13)
    mb.cylinder("metal", 0, 0, 0, 0.35, 0.05, DARK_STEEL, segments=10)
    mb.cylinder_between("metal", (0, 0, 0.05), (0, 0.55, 1.2), 0.05, tube, segments=8, caps=True)
    for s in (-1, 1):
        mb.cylinder_between("metal", (0, 0.35, 0.8), (s * 0.3, 0.55, 0.0), 0.015, tube, segments=4)
    with mb.place(-0.9, -1.0, 0, 20):
        build_crate(mb, rng, 0.7)
    mb.collider_cylinder(0, 0.2, 0, 0.35, 1.2)


def build_mg_nest(mb, rng):
    """Sandbagged machine-gun position. The gun points over the front wall (local -Y); open at the back."""
    build_sandbag_bunker(mb, rng, width=3.6, depth=2.6, rows=4)
    gun = (0.1, 0.1, 0.1)
    with mb.place(0, -0.75, 0.78):
        for a in (0, 120, 240):
            r = math.radians(a)
            mb.cylinder_between("metal", (0, 0, 0.1), (math.sin(r) * 0.35, math.cos(r) * 0.35, -0.78), 0.015, gun,
                                segments=4)
        mb.box("metal", 0, 0.1, 0.1, 0.12, 0.7, 0.14, gun)                                  # receiver + stock
        mb.cylinder_between("metal", (0, -0.25, 0.17), (0, -1.0, 0.17), 0.02, gun, segments=6)  # barrel
        mb.box("metal", 0.1, 0.05, 0.05, 0.08, 0.15, 0.1, (0.25, 0.27, 0.18))              # ammo box


# ============================================================================= town
PLASTER_COLORS = [(0.78, 0.72, 0.60), (0.70, 0.62, 0.50), (0.74, 0.66, 0.58), (0.62, 0.60, 0.55),
                  (0.80, 0.76, 0.66), (0.66, 0.55, 0.45), (0.58, 0.62, 0.60)]
ROOF_TILE = (0.45, 0.25, 0.18)
WINDOW_DARK = (0.06, 0.06, 0.07)
WINDOW_LIT = (1.0, 0.75, 0.42)


def _pitched_roof(mb, width, depth, z, color, overhang=0.35, pitch=0.45):
    """Gable roof along local X (ridge along X), sitting at height z."""
    hw = depth / 2 + overhang
    ridge = hw * pitch * 2
    profile_ccw = [(-hw, 0.0), (hw, 0.0), (0.0, ridge)]
    with mb.place(0, 0, z):
        mb.extrude_x("roof", profile_ccw, -width / 2 - overhang, width / 2 + overhang, color)
    return ridge


def _facade_windows(mb, x0, x1, y, z_floors, color_frame, rng, lit_chance=0.15, side=-1, skip=None):
    """Recessed windows on a facade plane (y), one row per floor height in z_floors."""
    n = max(1, int((x1 - x0) / 2.2))
    step = (x1 - x0) / n
    for z in z_floors:
        for i in range(n):
            cx = x0 + step * (i + 0.5)
            if skip and skip(cx, z):
                continue
            lit = rng.random() < lit_chance
            mat, col = ("emissive", _scale(WINDOW_LIT, rng.uniform(0.7, 1.0))) if lit else ("paint", WINDOW_DARK)
            mb.box(mat, cx, y + side * 0.01, z, 1.0, 0.04, 1.35, col)
            mb.box("wood", cx, y + side * 0.03, z - 0.08, 1.2, 0.06, 0.08, color_frame)       # sill
            mb.box("wood", cx, y + side * 0.03, z + 1.35, 1.2, 0.06, 0.1, color_frame)        # lintel
            if rng.random() < 0.6:                                                           # shutters
                for s in (-1, 1):
                    mb.box("wood", cx + s * 0.78, y + side * 0.04, z, 0.45, 0.04, 1.35,
                           _scale(color_frame, rng.uniform(0.8, 1.2)))


def build_house(mb, rng, width=9.0, depth=8.0, height=3.0, windows=2, wall_color=None, interior="home"):
    """Enterable single-storey town house with a pitched tile roof. Front door faces local -Y."""
    wc = _color(wall_color, rng.choice(PLASTER_COLORS))
    build_barracks(mb, rng, width=width, depth=depth, height=height, windows=windows, interior=interior,
                   wall_color=wc, roof_color=ROOF_TILE, door_width=1.6, wall_material="plaster")
    _pitched_roof(mb, width + 0.6, depth + 0.6, 0.25 + height + 0.22, _vary(ROOF_TILE, rng, 0.1))
    mb.box("block", width * 0.3, depth * 0.1, 0.25 + height + 0.5, 0.6, 0.6, 2.2, _vary((0.5, 0.42, 0.36), rng))


def build_townhouse_row(mb, rng, length=30.0, depth=8.0, burnt=0.2):
    """A row of 2-3 storey terraced houses (solid, not enterable). Facades face local -Y."""
    x = -length / 2
    hd = depth / 2
    while x < length / 2 - 3.0:
        w = min(rng.uniform(6.0, 9.0), length / 2 - x)
        floors = rng.choice((2, 2, 3))
        h = floors * 3.1 + 0.4
        cx = x + w / 2
        col = rng.choice(PLASTER_COLORS)
        charred = rng.random() < burnt
        if charred:
            col = _mix(col, CHARRED, 0.55)
            h = h * rng.uniform(0.55, 0.85)
        frame = _vary((0.32, 0.26, 0.2), rng, 0.2)
        mb.box("plaster", cx, 0, 0, w - 0.05, depth, h, _vary(col, rng, 0.04), collide=True)
        mb.box("concrete", cx, -hd - 0.08, 0, w, 0.18, 0.6, _scale(col, 0.75))                 # plinth
        mb.box("concrete", cx, -hd - 0.06, h - 0.35, w, 0.25, 0.25, _scale(col, 0.85))         # cornice
        door_x = cx + rng.uniform(-w / 4, w / 4)
        mb.box("wood", door_x, -hd - 0.02, 0, 1.2, 0.06, 2.3, _vary(WOOD_DARK, rng))
        mb.box("concrete", door_x, -hd - 0.3, 0, 1.6, 0.5, 0.15, _scale(col, 0.7), collide=True)
        floors_z = [0.9 + 3.1 * f for f in range(floors) if 0.9 + 3.1 * f + 1.4 < h - 0.3]
        _facade_windows(mb, x + 0.3, x + w - 0.3, -hd, floors_z, frame, rng,
                        lit_chance=0.0 if charred else 0.18,
                        skip=lambda wx, wz: wz < 2.5 and abs(wx - door_x) < 1.3)
        if not charred:
            if rng.random() < 0.6:
                with mb.place(cx, 0, h):
                    _pitched_roof(mb, w, depth, 0, _vary(ROOF_TILE, rng, 0.12), overhang=0.25)
            else:
                mb.box("concrete", cx, 0, h, w, depth, 0.5, _scale(col, 0.85))
            mb.box("block", cx + w * 0.25, hd * 0.3, h, 0.7, 0.7, 2.6, _vary((0.5, 0.42, 0.36), rng))
            if rng.random() < 0.35:                                                             # shop awning
                mb.box("fabric", cx, -hd - 0.8, 2.5, w - 1.0, 1.6, 0.08,
                       rng.choice([(0.55, 0.15, 0.12), (0.2, 0.35, 0.25), (0.25, 0.3, 0.5)]), bottom=True)
        else:
            for _ in range(2):
                with mb.place(cx + rng.uniform(-w / 3, w / 3), -hd - 1.4, 0):
                    build_rubble(mb, rng, size=1.4, count=6)
        x += w


def build_church(mb, rng, width=12.0, depth=18.0):
    """Stone church with a bell tower. Entrance faces local -Y. Solid (not enterable)."""
    stone = _vary((0.70, 0.67, 0.60), rng)
    nave_h = 8.5
    hw, hd = width / 2, depth / 2
    mb.box("stone", 0, 0, 0, width, depth, nave_h, stone, collide=True)
    with mb.place(0, 0, nave_h, 90):
        _pitched_roof(mb, depth, width, 0, _vary((0.30, 0.30, 0.32), rng), overhang=0.4, pitch=0.7)
    for y in [-hd + 3 + i * 3.2 for i in range(4)]:
        for s in (-1, 1):
            mb.box("emissive", s * (hw + 0.01), y, 3.0, 0.04, 1.2, 3.6, _scale((0.9, 0.55, 0.3), rng.uniform(0.6, 1.0)))
    tw = 4.4
    mb.box("stone", 0, -hd - tw / 2 + 0.5, 0, tw, tw, 21.0, _scale(stone, 0.95), collide=True)
    mb.cylinder("concrete", 0, -hd - tw / 2 + 0.5, 21.0, tw * 0.75, 6.0, (0.26, 0.27, 0.29), segments=4,
                radius_top=0.0)
    mb.box("paint", 0, -hd - tw + 0.49, 15.0, 1.4, 0.04, 2.4, WINDOW_DARK)                       # belfry opening
    mb.box("wood", 0, -hd - tw + 0.47, 0, 2.2, 0.08, 3.6, _vary(WOOD_DARK, rng))                 # doors
    mb.box("block", 0, -hd - tw + 0.4, 3.6, 3.0, 0.3, 0.4, _scale(stone, 0.8))
    for s in (-1, 1):
        mb.box("block", s * (hw + 0.3), 0, 0, 0.6, depth - 1, 1.0, _scale(stone, 0.85))         # buttress base
    mb.box("concrete", 0, -hd - tw - 1.2, 0, 6.0, 2.4, 0.3, _scale(stone, 0.8), collide=True)    # steps


def build_fountain(mb, rng, radius=2.4):
    stone = _vary((0.66, 0.64, 0.6), rng)
    mb.cylinder("concrete", 0, 0, 0, radius, 0.7, stone, segments=16)
    mb.cylinder("paint", 0, 0, 0.55, radius - 0.25, 0.1, (0.16, 0.2, 0.22), segments=16)        # dark water
    mb.cylinder("concrete", 0, 0, 0.6, 0.35, 1.6, stone, segments=10, radius_top=0.25)
    mb.cylinder("concrete", 0, 0, 2.2, 0.9, 0.25, stone, segments=12, radius_top=0.6)
    mb.collider_cylinder(0, 0, 0, radius, 0.7)
    mb.collider_cylinder(0, 0, 0.7, 0.4, 1.8)


def build_lamp_post(mb, rng, lit=True):
    if mb.use_model("street_lamp", yaw=rng.choice((0, 90, 180, 270))):
        if lit:
            mb.box("emissive", 0, 0, 3.6, 0.2, 0.2, 0.3, LAMP_WARM)      # glowing bulb inside the lantern
        mb.collider_cylinder(0, 0, 0, 0.14, 4.0)
        return
    iron = (0.12, 0.12, 0.13)
    mb.cylinder("metal", 0, 0, 0, 0.12, 0.4, iron, segments=8)
    mb.cylinder("metal", 0, 0, 0.4, 0.06, 3.4, iron, segments=6, radius_top=0.045)
    mb.box("metal", 0, 0, 3.8, 0.34, 0.34, 0.06, iron)
    mb.box("emissive" if lit else "paint", 0, 0, 3.86, 0.26, 0.26, 0.4, LAMP_WARM if lit else WINDOW_DARK)
    mb.cylinder("metal", 0, 0, 4.26, 0.24, 0.22, iron, segments=4, radius_top=0.02)
    mb.collider_cylinder(0, 0, 0, 0.14, 4.0)


def build_medical_tent(mb, rng, length=6.0, width=4.4):
    build_tent(mb, rng, length=length, width=width, height=2.8, color=(0.82, 0.82, 0.78))
    for s in (-1, 1):
        with mb.place(0, s * 0.01, 0):
            mb.polygon_x("paint", s * (length / 2 + 0.02), [(-0.6, 1.25), (0.6, 1.25), (0.6, 1.55), (-0.6, 1.55)],
                         RED_PAINT, facing=s)
            mb.polygon_x("paint", s * (length / 2 + 0.02), [(-0.15, 0.8), (0.15, 0.8), (0.15, 2.0), (-0.15, 2.0)],
                         RED_PAINT, facing=s)


# ============================================================================= river & bridge
def build_embankment(mb, rng, length=40.0, depth=4.0):
    """Concrete river wall along local X. The water side is local +Y."""
    col = _vary(CONCRETE_DARK, rng, 0.05)
    mb.box("concrete", 0, 0.4, -depth, length, 0.8, depth + 0.15, col, top=True)
    mb.box("concrete", 0, 0.1, 0.0, length, 0.6, 0.25, _scale(col, 1.1))                      # kerb
    n = max(1, int(length / 6))
    for i in range(n):
        x = -length / 2 + (i + 0.5) * length / n
        mb.cylinder_between("metal", (x, 0.82, -0.4), (x, 0.82, -2.2), 0.04, DARK_STEEL, segments=4)  # ladder rails
    mb.collider_box(0, 0.1, 0, length, 0.6, 0.25)


def build_bridge_span(mb, rng, length=20.0, width=10.0):
    """Road bridge deck section along local Y, with railings and lamps. Deck top at z = 0.25."""
    col = _vary(CONCRETE, rng, 0.05)
    hw = width / 2
    mb.box("concrete", 0, 0, -0.9, width, length, 1.15, col, bottom=True, collide=True)
    mb.flat_rect("asphalt", -hw + 0.8, -length / 2, hw - 0.8, length / 2, 0.26, (0.95, 0.95, 0.95), world_uv=True)
    mb.flat_rect("paint", -0.08, -length / 2, 0.08, length / 2, 0.27, YELLOW_PAINT)
    for sx in (-1, 1):
        mb.box("concrete", sx * (hw - 0.4), 0, 0.25, 0.8, length, 0.2, _scale(col, 0.9), collide=True)  # walkway
        n = int(length / 2.5)
        for i in range(n + 1):
            y = -length / 2 + i * length / n
            mb.box("metal", sx * (hw - 0.08), y, 0.45, 0.08, 0.08, 1.0, DARK_STEEL)
        for z in (0.95, 1.4):
            mb.box("metal", sx * (hw - 0.08), 0, 0.45 + z - 0.45, 0.06, length, 0.06, STEEL)
        mb.collider_box(sx * (hw - 0.08), 0, 0.45, 0.2, length, 1.0)
        mb.box("metal", sx * (hw + 0.05), 0, -1.2, 0.3, length, 0.4, _scale(col, 0.7))          # edge beam
    if length >= 15:
        with mb.place(-hw + 0.3, 0, 0.45):
            build_lamp_post(mb, rng)


def build_bridge_pillar(mb, rng, height=9.0, width=8.0):
    col = _vary(CONCRETE_DARK, rng, 0.05)
    mb.box("concrete", 0, 0, -height, width * 0.35, 3.0, height - 1.0, col)
    mb.box("concrete", 0, 0, -1.1, width + 1.0, 3.4, 0.25, _scale(col, 1.1), bottom=True)
    mb.cylinder("concrete", 0, 0, -height, 2.2, 1.0, _scale(col, 0.8), segments=10)


def build_bridge_ruin(mb, rng, length=20.0, width=10.0):
    """What is left of a destroyed span: broken stubs and a slab lying in the river."""
    col = _mix(_vary(CONCRETE, rng, 0.05), CHARRED, 0.35)
    for sy in (-1, 1):
        stub = rng.uniform(2.0, 4.0)
        mb.box("concrete", rng.uniform(-0.5, 0.5), sy * (length / 2 - stub / 2), -0.9, width * rng.uniform(0.6, 0.9),
               stub, 1.15, col, bottom=True, collide=True)
        for _ in range(3):
            mb.cylinder_between("metal", (rng.uniform(-3, 3), sy * (length / 2 - stub), -0.3),
                                (rng.uniform(-3, 3), sy * (length / 2 - stub - rng.uniform(0.6, 1.5)), rng.uniform(-1.2, 0.5)),
                                0.03, DARK_STEEL, segments=4)                           # bent rebar
    mb.box("concrete", rng.uniform(-1, 1), 0, -3.2, width * 0.8, length * 0.55, 0.9, _scale(col, 0.8),
           yaw=rng.uniform(-15, 15))
    for _ in range(4):
        with mb.place(rng.uniform(-3, 3), rng.uniform(-length / 3, length / 3), -2.4):
            build_rubble(mb, rng, size=2.0, count=5)


def build_aa_gun(mb, rng):
    """Twin-barrel anti-aircraft gun in a sandbag ring."""
    for i in range(6):
        a = math.radians(i * 60 + 30)
        with mb.place(math.sin(a) * 3.0, math.cos(a) * 3.0, 0, -math.degrees(a)):
            build_sandbag_wall(mb, rng, 2.6, rows=3)
    gun = _vary(OLIVE_DARK, rng)
    mb.cylinder("metal", 0, 0, 0, 1.2, 0.5, DARK_STEEL, segments=12)
    mb.box("metal", 0, 0, 0.5, 1.4, 1.6, 0.9, gun, collide=True)
    for sx in (-0.3, 0.3):
        mb.cylinder_between("metal", (sx, 0.4, 1.1), (sx, 3.6, 3.0), 0.07, DARK_STEEL, segments=8)
        mb.cylinder_between("metal", (sx, 3.4, 2.9), (sx, 3.7, 3.08), 0.1, DARK_STEEL, segments=8)
    mb.box("metal", 0, -0.6, 1.2, 0.6, 0.3, 0.6, gun)
    mb.collider_cylinder(0, 0, 0, 1.3, 1.5)


def build_searchlight_tower(mb, rng, height=7.0, beam_heading=0.0, beam_pitch=-20.0, beam_length=60.0):
    build_watchtower(mb, rng, height=height, size=3.0)
    top = height + 1.05
    with mb.place(0, 0, top, beam_heading):
        mb.cylinder("metal", 0, 0, 0, 0.1, 0.4, DARK_STEEL, segments=6)
        p = math.radians(beam_pitch)
        d = (0.0, math.cos(p), math.sin(p))
        start = (0.0, 0.0, 0.55)
        mb.cylinder_between("metal", (0, -0.35 * d[1], 0.55 - 0.35 * d[2]), (0, 0.15 * d[1], 0.55 + 0.15 * d[2]),
                            0.3, DARK_STEEL, segments=12, caps=True)
        mb.cylinder_between("emissive", (0, 0.16 * d[1], 0.55 + 0.16 * d[2]), (0, 0.17 * d[1], 0.55 + 0.17 * d[2]),
                            0.27, (1.0, 0.96, 0.85), segments=12, caps=True)
        end = (0.0, start[1] + d[1] * beam_length, start[2] + d[2] * beam_length)
        mb.cylinder_between("beam", (0, 0.2 * d[1], 0.55 + 0.2 * d[2]), end, 0.3, (1.0, 0.95, 0.8, 0.07),
                            radius_end=beam_length * 0.09, segments=14)


def build_slipway(mb, rng, length=12.0, width=6.0, drop=1.6):
    """Concrete boat ramp from the bank (local y=0) down into the water (local +Y)."""
    col = _vary(CONCRETE_DARK, rng)
    steps = 8
    for i in range(steps):
        y = (i + 0.5) * length / steps
        z = -drop * (i + 1) / steps
        mb.box("concrete", 0, y, z - 0.3, width, length / steps + 0.02, 0.3, col)
    for sx in (-1, 1):
        mb.box("concrete", sx * (width / 2 + 0.2), length / 2, -drop - 0.5, 0.4, length, drop + 0.7, _scale(col, 0.9))


# ============================================================================= harbour
def build_pier(mb, rng, length=40.0, width=6.0):
    """Wooden jetty on posts, running out over the water along local +Y. Deck top at z = 0.25."""
    deck = _vary(WOOD_DARK, rng, 0.05)
    mb.box("wood", 0, length / 2, 0.0, width, length, 0.25, deck, collide=True)
    for i in range(int(length / 4) + 1):
        y = i * length / int(length / 4)
        for sx in (-1, 1):
            mb.cylinder("wood", sx * (width / 2 - 0.2), y, -4.0, 0.2, 4.0, _scale(deck, 0.7), segments=6)
        if i % 2 == 0:
            for sx in (-1, 1):
                mb.cylinder("metal", sx * (width / 2 - 0.35), y, 0.25, 0.14, 0.45, DARK_STEEL, segments=8)   # bollard
    for sx in (-1, 1):
        mb.collider_box(sx * (width / 2 + 0.1), length / 2, 0.25, 0.2, length, 1.4)     # don't fall in
    mb.collider_box(0, length + 0.1, 0.25, width, 0.2, 1.4)
    with mb.place(width / 2 - 0.5, length - 2.0, 0.25):
        build_lamp_post(mb, rng)


def build_cargo_ship(mb, rng, length=96.0, beam=16.0, color=None):
    """Moored container ship along local +Y (bow at +Y). Hull bottom is under water; deck at z = 7."""
    hull = _vary(_color(color, (0.18, 0.22, 0.3)), rng, 0.04)
    hl, hb = length / 2, beam / 2
    mb.box("metal", 0, 0, -6.0, beam, length - 10, 13.0, hull, collide=True)
    mb.box("paint", 0, 0, -1.2, beam + 0.05, length - 10.05, 0.6, RED_PAINT)            # waterline stripe
    for sy, s in ((1, 1.0), (-1, 0.7)):                                                # bow and stern
        y0 = sy * (hl - 5)
        mb.box("metal", 0, y0 + sy * 2.5, -6.0 + (1 - s) * 2, beam * s * 0.8, 5.0, 13.0 - (1 - s) * 2, hull,
               collide=True)
    mb.box("metal", 0, 0, 7.0, beam - 0.6, length - 12, 0.1, (0.42, 0.18, 0.14))      # deck
    for sx in (-1, 1):
        mb.box("metal", sx * (hb - 0.1), 0, 7.0, 0.1, length - 12, 1.1, (0.8, 0.8, 0.78))  # rail
    # Superstructure at the stern.
    sy = -hl + 14
    white = _vary(WHITE_PAINT, rng, 0.03)
    mb.box("block", 0, sy, 7.0, beam - 2, 10, 12.0, white, collide=True)
    for level in range(4):
        z = 8.4 + level * 2.8
        for x in (-4.5, -1.5, 1.5, 4.5):
            mb.box("emissive" if rng.random() < 0.35 else "paint", x, sy + 5.03, z, 1.4, 0.05, 1.1,
                   LAMP_WARM if rng.random() < 0.35 else GLASS)
    mb.box("block", 0, sy, 19.0, beam + 2, 6, 2.5, white)                                 # bridge wings
    mb.cylinder("metal", 0, sy - 2, 21.5, 1.2, 5.0, (0.15, 0.15, 0.16), segments=10)      # funnel
    mb.box("paint", 0, sy - 2, 24.0, 2.5, 2.5, 0.8, RED_PAINT)
    mb.box("emissive", 0, hl - 4, 9.0, 0.3, 0.3, 0.3, LAMP_GREEN)
    # Containers on deck.
    colors = ["rust", "blue", "green", "grey", "red"]
    for row in range(6):
        y = sy + 10 + row * 7.0
        if y > hl - 10:
            break
        for col in range(-2, 3):
            for tier in range(rng.randint(1, 3)):
                c = _vary(NAMED_COLORS[rng.choice(colors)], rng, 0.08)
                mb.box("corrugated", col * 2.6, y, 7.1 + tier * 2.6, 2.44, 6.06, 2.59, c, collide=tier == 0)
    # Deck cranes.
    for y in (sy + 17, sy + 38):
        mb.cylinder("metal", hb - 2, y, 7.0, 0.5, 9.0, YELLOW_PAINT, segments=8)
        mb.cylinder_between("metal", (hb - 2, y, 15.5), (hb - 14, y + 6, 12.0), 0.25, YELLOW_PAINT, segments=6)


def build_gantry_crane(mb, rng, span=16.0, height=26.0, boom=34.0):
    """Ship-to-shore container crane on the quay; the boom reaches out over the water (local -Y)."""
    col = _vary((0.75, 0.42, 0.12), rng, 0.04)
    hs = span / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * hs, sy * 6.0
            mb.box("metal", x, y, 0.0, 1.0, 1.0, height, col, collide=True)
            mb.box("metal", x, y, 0.0, 1.6, 2.2, 1.0, DARK_STEEL)                     # wheel bogie
        mb.box("metal", sx * hs, 0, height * 0.45, 0.8, 12.0, 0.8, col)                # side ties
        mb.cylinder_between("metal", (sx * hs, -6, 1.0), (sx * hs, 6, height * 0.45), 0.25, col, segments=6)
    for y in (-6.0, 6.0):
        mb.box("metal", 0, y, height, span + 1.0, 1.2, 1.5, col)
    mb.box("metal", 0, -boom / 2 + 6, height + 1.5, 3.0, boom + 12, 1.6, col)          # boom over the water
    mb.box("metal", 0, 9.0, height + 3.1, 6.0, 6.0, 3.5, _scale(col, 0.85))            # machinery house
    mb.box("paint", 0, -2.0, height - 1.8, 2.4, 2.4, 2.0, GLASS)                        # driver cab
    for i in range(3):
        y = -boom + 10 + i * 10
        mb.cylinder_between("metal", (0, 4.0, height + 9.0), (0, y, height + 3.0), 0.12, DARK_STEEL, segments=4)
    mb.cylinder_between("metal", (0, 4.0, height + 3.0), (0, 4.0, height + 9.0), 0.4, col, segments=6)
    mb.box("emissive", 0, -boom + 7, height + 3.2, 0.3, 0.3, 0.3, LAMP_RED)


def build_locker_row(mb, rng, count=5, color=None):
    """Row of steel lockers against a wall (local -Y is the front)."""
    col = _vary(_color(color, (0.36, 0.42, 0.46)), rng, 0.04)
    w = 0.5
    for i in range(count):
        x = (i - (count - 1) / 2) * w
        mb.box("metal", x, 0, 0, w - 0.02, 0.5, 1.9, col)
        mb.box("metal", x + 0.15, -0.255, 1.0, 0.03, 0.02, 0.12, DARK_STEEL)          # handle
        for z in (1.6, 1.68, 1.76):
            mb.box("metal", x, -0.255, z, 0.3, 0.01, 0.03, _scale(col, 0.6))           # vents
    mb.collider_box(0, 0, 0, count * w, 0.5, 1.9)


def build_market_stall(mb, rng, width=3.0, depth=2.0, color=None):
    """Fish-market stall: counter, crates and a striped canvas roof."""
    wood = _vary(WOOD, rng)
    canvas = _vary(_color(color, rng.choice([(0.6, 0.2, 0.15), (0.2, 0.35, 0.55), (0.75, 0.68, 0.5)])), rng)
    mb.box("wood", 0, 0, 0, width, depth * 0.5, 0.95, wood, collide=True)               # counter
    mb.box("paint", 0, 0, 0.95, width, depth * 0.5, 0.04, (0.8, 0.82, 0.84))           # ice tray
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.cylinder("wood", sx * (width / 2 - 0.05), sy * depth / 2, 0, 0.04, 2.4, wood, segments=5)
    mb.box("fabric", 0, 0, 2.4, width + 0.4, depth + 0.6, 0.05, canvas)
    for i in range(2):
        with mb.place(rng.uniform(-1, 1), depth * 0.7, 0, rng.uniform(-20, 20)):
            build_crate(mb, rng, size=0.6, color="blue")


def build_terminal_desk(mb, rng):
    """Desk with a computer: the operator stands on the local -Y side."""
    wood = _vary(WOOD_DARK, rng)
    mb.box("wood", 0, 0, 0.72, 1.6, 0.8, 0.05, wood)
    for sx in (-1, 1):
        mb.box("wood", sx * 0.75, 0, 0, 0.06, 0.76, 0.72, wood)
    mb.collider_box(0, 0, 0, 1.6, 0.8, 0.77)
    mb.box("metal", 0, 0.2, 0.77, 0.25, 0.18, 0.05, DARK_STEEL)                       # monitor stand
    mb.box("metal", 0, 0.22, 0.82, 0.62, 0.05, 0.4, DARK)                             # monitor
    mb.box("emissive", 0, 0.193, 0.85, 0.56, 0.01, 0.34, (0.25, 0.55, 0.9))           # screen
    mb.box("metal", 0, -0.12, 0.77, 0.45, 0.16, 0.025, (0.15, 0.15, 0.15))            # keyboard
    mb.box("metal", 0.6, 0.1, 0.0, 0.2, 0.45, 0.45, (0.2, 0.2, 0.22))                 # tower PC
    mb.box("emissive", 0.6, -0.126, 0.38, 0.03, 0.01, 0.02, (0.3, 1.0, 0.4))


def build_invisible_wall(mb, rng, length=50.0, height=6.0):
    """Collision only - keeps players and soldiers inside the playable area."""
    mb.collider_box(0, 0, 0, length, 1.0, height)


# ============================================================================= registry
PROP_BUILDERS = {
    "invisible_wall": build_invisible_wall,
    "pier": build_pier,
    "terminal_desk": build_terminal_desk,
    "cargo_ship": build_cargo_ship,
    "gantry_crane": build_gantry_crane,
    "locker_row": build_locker_row,
    "market_stall": build_market_stall,
    "embankment": build_embankment,
    "bridge_span": build_bridge_span,
    "bridge_pillar": build_bridge_pillar,
    "bridge_ruin": build_bridge_ruin,
    "aa_gun": build_aa_gun,
    "searchlight_tower": build_searchlight_tower,
    "slipway": build_slipway,
    "house": build_house,
    "townhouse_row": build_townhouse_row,
    "church": build_church,
    "fountain": build_fountain,
    "lamp_post": build_lamp_post,
    "medical_tent": build_medical_tent,
    "trench": build_trench,
    "crater": build_crater,
    "hedgehog": build_hedgehog,
    "wire_line": build_wire_line,
    "tank": build_tank,
    "bunker": build_bunker,
    "mortar_pit": build_mortar_pit,
    "mg_nest": build_mg_nest,
    "barracks": build_barracks,
    "guard_booth": build_guard_booth,
    "ruined_building": build_ruined_building,
    "hangar": build_hangar,
    "watchtower": build_watchtower,
    "t_wall_row": build_t_wall_row,
    "fence": build_fence,
    "main_gate": build_main_gate,
    "jersey_barrier": build_jersey_barrier,
    "sandbag_wall": build_sandbag_wall,
    "sandbag_bunker": build_sandbag_bunker,
    "hesco": build_hesco,
    "crate": build_crate,
    "crate_stack": build_crate_stack,
    "barrel": build_barrel,
    "barrel_group": build_barrel_group,
    "pallet": build_pallet,
    "tire_stack": build_tire_stack,
    "generator": build_generator,
    "fuel_tank": build_fuel_tank,
    "light_pole": build_light_pole,
    "radio_mast": build_radio_mast,
    "tent": build_tent,
    "container": build_container,
    "jeep": build_jeep,
    "truck": build_truck,
    "tree_pine": build_tree_pine,
    "tree_broadleaf": build_tree_broadleaf,
    "tree_dead": build_tree_dead,
    "bush": build_bush,
    "rock": build_rock,
    "hill": build_hill,
    "rubble": build_rubble,
    "road": build_road,
    "concrete_pad": build_concrete_pad,
    "helipad": build_helipad,
}
