"""Kinematic collision world.

The level is described by simple solid shapes:
  * BoxCollider      - a box that may be rotated around the vertical axis (yaw)
  * CylinderCollider - an upright cylinder (trees, barrels, poles)

The player (and later the enemies) is an upright cylinder that slides along walls,
steps up stairs and stands on top of objects.

Why a custom solver instead of Panda3D's collision traverser?
  * It is predictable (no tunnelling through thin walls), fast with a spatial grid,
    and it can be unit-tested without opening a game window.
  * Phase 2 will reuse the same data for bullet ray-casts.

Coordinates follow Panda3D: X right, Y forward, Z up, metres. Yaw is in degrees and
uses the same direction as NodePath.setH() (counter-clockwise seen from above).
"""
from __future__ import annotations

import math
from collections import defaultdict

_EPS = 1e-9


class BoxCollider:
    __slots__ = ("cx", "cy", "z_min", "z_max", "hx", "hy", "yaw", "tag", "_cos", "_sin", "bounds")

    def __init__(self, cx, cy, z_min, z_max, hx, hy, yaw=0.0, tag="static"):
        if z_max < z_min:
            z_min, z_max = z_max, z_min
        self.cx, self.cy = float(cx), float(cy)
        self.z_min, self.z_max = float(z_min), float(z_max)
        self.hx, self.hy = abs(float(hx)), abs(float(hy))
        self.yaw = float(yaw)
        self.tag = tag
        rad = math.radians(self.yaw)
        self._cos, self._sin = math.cos(rad), math.sin(rad)
        ex = abs(self._cos) * self.hx + abs(self._sin) * self.hy
        ey = abs(self._sin) * self.hx + abs(self._cos) * self.hy
        self.bounds = (self.cx - ex, self.cy - ey, self.cx + ex, self.cy + ey)

    def to_local(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        return dx * self._cos + dy * self._sin, -dx * self._sin + dy * self._cos

    def _closest_delta(self, x, y):
        lx, ly = self.to_local(x, y)
        qx = min(max(lx, -self.hx), self.hx)
        qy = min(max(ly, -self.hy), self.hy)
        return lx, ly, lx - qx, ly - qy

    def overlaps_circle(self, x, y, radius):
        _, _, dx, dy = self._closest_delta(x, y)
        return dx * dx + dy * dy < radius * radius

    def circle_push(self, x, y, radius):
        """World-space (px, py) that moves a circle out of this box, or None if not touching."""
        lx, ly, dx, dy = self._closest_delta(x, y)
        d2 = dx * dx + dy * dy
        if d2 >= radius * radius:
            return None
        if d2 > _EPS:
            d = math.sqrt(d2)
            k = (radius - d) / d
            px, py = dx * k, dy * k
        else:
            # Centre is inside the box: leave through the closest side.
            pen_x = self.hx - abs(lx)
            pen_y = self.hy - abs(ly)
            if pen_x < pen_y:
                px, py = math.copysign(pen_x + radius, lx if lx else 1.0), 0.0
            else:
                px, py = 0.0, math.copysign(pen_y + radius, ly if ly else 1.0)
        return px * self._cos - py * self._sin, px * self._sin + py * self._cos

    def contains_point(self, x, y, z):
        if not (self.z_min <= z <= self.z_max):
            return False
        lx, ly = self.to_local(x, y)
        return abs(lx) <= self.hx and abs(ly) <= self.hy

    def ray_hit(self, ox, oy, oz, dx, dy, dz, max_t):
        """Distance and world normal where the ray enters the box, or None."""
        lox, loy = self.to_local(ox, oy)
        c, s = self._cos, self._sin
        ldx, ldy = dx * c + dy * s, -dx * s + dy * c
        t0, t1 = 0.0, max_t
        axis_hit = None
        for o, d, lo, hi, axis in ((lox, ldx, -self.hx, self.hx, 0), (loy, ldy, -self.hy, self.hy, 1),
                                   (oz, dz, self.z_min, self.z_max, 2)):
            if abs(d) < 1e-12:
                if o < lo or o > hi:
                    return None
                continue
            inv = 1.0 / d
            ta, tb = (lo - o) * inv, (hi - o) * inv
            sign = -1.0
            if ta > tb:
                ta, tb = tb, ta
                sign = 1.0
            if ta > t0:
                t0 = ta
                axis_hit = (axis, sign)
            if tb < t1:
                t1 = tb
            if t0 > t1:
                return None
        if axis_hit is None:          # ray starts inside the box
            return 0.0, (-dx, -dy, -dz)
        axis, sign = axis_hit
        if axis == 2:
            return t0, (0.0, 0.0, sign)
        lnx, lny = (sign, 0.0) if axis == 0 else (0.0, sign)
        return t0, (lnx * c - lny * s, lnx * s + lny * c, 0.0)

    def __repr__(self):
        return (f"BoxCollider(c=({self.cx:.2f},{self.cy:.2f}) z=[{self.z_min:.2f},{self.z_max:.2f}] "
                f"half=({self.hx:.2f},{self.hy:.2f}) yaw={self.yaw:.1f})")


class CylinderCollider:
    __slots__ = ("cx", "cy", "z_min", "z_max", "radius", "tag", "bounds")

    def __init__(self, cx, cy, z_min, z_max, radius, tag="static"):
        if z_max < z_min:
            z_min, z_max = z_max, z_min
        self.cx, self.cy = float(cx), float(cy)
        self.z_min, self.z_max = float(z_min), float(z_max)
        self.radius = abs(float(radius))
        self.tag = tag
        r = self.radius
        self.bounds = (self.cx - r, self.cy - r, self.cx + r, self.cy + r)

    def overlaps_circle(self, x, y, radius):
        dx, dy = x - self.cx, y - self.cy
        rr = radius + self.radius
        return dx * dx + dy * dy < rr * rr

    def circle_push(self, x, y, radius):
        dx, dy = x - self.cx, y - self.cy
        rr = radius + self.radius
        d2 = dx * dx + dy * dy
        if d2 >= rr * rr:
            return None
        if d2 < _EPS:
            return rr, 0.0
        d = math.sqrt(d2)
        k = (rr - d) / d
        return dx * k, dy * k

    def contains_point(self, x, y, z):
        dx, dy = x - self.cx, y - self.cy
        return self.z_min <= z <= self.z_max and dx * dx + dy * dy <= self.radius * self.radius

    def ray_hit(self, ox, oy, oz, dx, dy, dz, max_t):
        return ray_vertical_cylinder(ox, oy, oz, dx, dy, dz, max_t, self.cx, self.cy, self.z_min, self.z_max,
                                     self.radius)

    def __repr__(self):
        return (f"CylinderCollider(c=({self.cx:.2f},{self.cy:.2f}) z=[{self.z_min:.2f},{self.z_max:.2f}] "
                f"r={self.radius:.2f})")


def ray_vertical_cylinder(ox, oy, oz, dx, dy, dz, max_t, cx, cy, z_min, z_max, radius):
    """Ray vs upright cylinder: (t, normal) of the first hit or None."""
    best = None
    px, py = ox - cx, oy - cy
    a = dx * dx + dy * dy
    r2 = radius * radius
    if a > 1e-12:
        b = 2.0 * (px * dx + py * dy)
        c = px * px + py * py - r2
        disc = b * b - 4 * a * c
        if disc >= 0.0:
            t = (-b - math.sqrt(disc)) / (2 * a)
            if 0.0 <= t <= max_t:
                z = oz + dz * t
                if z_min <= z <= z_max:
                    hx, hy = px + dx * t, py + dy * t
                    best = (t, (hx / radius, hy / radius, 0.0))
    if abs(dz) > 1e-12:
        for plane, nz in ((z_max, 1.0), (z_min, -1.0)):
            t = (plane - oz) / dz
            if 0.0 <= t <= max_t and (best is None or t < best[0]):
                hx, hy = px + dx * t, py + dy * t
                if hx * hx + hy * hy <= r2 and (dz < 0) == (nz > 0):
                    best = (t, (0.0, 0.0, nz))
    if best is None and px * px + py * py <= r2 and z_min <= oz <= z_max:
        return 0.0, (-dx, -dy, -dz)
    return best


def ray_sphere(ox, oy, oz, dx, dy, dz, max_t, cx, cy, cz, radius):
    px, py, pz = ox - cx, oy - cy, oz - cz
    b = px * dx + py * dy + pz * dz
    c = px * px + py * py + pz * pz - radius * radius
    disc = b * b - c
    if disc < 0.0:
        return None
    t = -b - math.sqrt(disc)
    if t < 0.0:
        t = 0.0 if c <= 0.0 else None
        if t is None:
            return None
    if t > max_t:
        return None
    hx, hy, hz = px + dx * t, py + dy * t, pz + dz * t
    return t, (hx / radius, hy / radius, hz / radius)


class RayHit:
    __slots__ = ("t", "point", "normal", "collider")

    def __init__(self, t, point, normal, collider):
        self.t, self.point, self.normal, self.collider = t, point, normal, collider

    def __repr__(self):
        return f"RayHit(t={self.t:.2f}, point={tuple(round(v, 2) for v in self.point)})"


class CollisionWorld:
    """All static colliders of the current level, indexed in a uniform 2D grid."""

    def __init__(self, cell_size=8.0, floor_z=0.0):
        self.cell_size = float(cell_size)
        self.floor_z = float(floor_z)
        self.colliders = []
        self._cells = defaultdict(list)

    def __len__(self):
        return len(self.colliders)

    def clear(self):
        self.colliders.clear()
        self._cells.clear()

    def add(self, collider):
        self.colliders.append(collider)
        x0, y0, x1, y1 = collider.bounds
        for cx in range(self._cell(x0), self._cell(x1) + 1):
            for cy in range(self._cell(y0), self._cell(y1) + 1):
                self._cells[(cx, cy)].append(collider)

    def add_many(self, colliders):
        for c in colliders:
            self.add(c)

    def remove_tag(self, tag):
        """Remove every collider with this tag (e.g. a fence section blown open). Returns how many."""
        removed = [c for c in self.colliders if c.tag == tag]
        if not removed:
            return 0
        ids = {id(c) for c in removed}
        self.colliders = [c for c in self.colliders if id(c) not in ids]
        for key in list(self._cells):
            bucket = [c for c in self._cells[key] if id(c) not in ids]
            if bucket:
                self._cells[key] = bucket
            else:
                del self._cells[key]
        return len(removed)

    def raycast(self, origin, direction, max_dist):
        """First hit of a ray against the level (colliders + floor). direction must be normalised."""
        ox, oy, oz = origin
        dx, dy, dz = direction
        best_t = max_dist
        best_n = None
        best_c = None
        if dz < -1e-12:
            t = (self.floor_z - oz) / dz
            if 0.0 <= t < best_t:
                best_t, best_n = t, (0.0, 0.0, 1.0)
        # Walk the grid cells along the ray (Amanatides & Woo) and test their colliders.
        size = self.cell_size
        cx, cy = self._cell(ox), self._cell(oy)
        step_x = 1 if dx > 0 else -1
        step_y = 1 if dy > 0 else -1
        if abs(dx) > 1e-12:
            next_x = ((cx + (1 if dx > 0 else 0)) * size - ox) / dx
            delta_x = size / abs(dx)
        else:
            next_x = delta_x = math.inf
        if abs(dy) > 1e-12:
            next_y = ((cy + (1 if dy > 0 else 0)) * size - oy) / dy
            delta_y = size / abs(dy)
        else:
            next_y = delta_y = math.inf
        tested = set()
        t_cell = 0.0
        while t_cell <= best_t:
            for col in self._cells.get((cx, cy), ()):
                key = id(col)
                if key in tested:
                    continue
                tested.add(key)
                hit = col.ray_hit(ox, oy, oz, dx, dy, dz, best_t)
                if hit is not None and hit[0] < best_t:
                    best_t, best_n, best_c = hit[0], hit[1], col
            if next_x < next_y:
                t_cell = next_x
                next_x += delta_x
                cx += step_x
            else:
                t_cell = next_y
                next_y += delta_y
                cy += step_y
        if best_n is None:
            return None
        return RayHit(best_t, (ox + dx * best_t, oy + dy * best_t, oz + dz * best_t), best_n, best_c)

    def line_of_sight(self, a, b):
        """True if nothing in the level blocks the straight line from point a to point b."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 1e-6:
            return True
        hit = self.raycast(a, (dx / dist, dy / dist, dz / dist), dist)
        return hit is None or hit.t >= dist - 1e-4

    def _cell(self, v):
        return int(math.floor(v / self.cell_size))

    def query_area(self, min_x, min_y, max_x, max_y):
        """Colliders whose bounding rectangle may touch the given rectangle (no duplicates)."""
        result = []
        seen = set()
        cells = self._cells
        for cx in range(self._cell(min_x), self._cell(max_x) + 1):
            for cy in range(self._cell(min_y), self._cell(max_y) + 1):
                bucket = cells.get((cx, cy))
                if not bucket:
                    continue
                for col in bucket:
                    key = id(col)
                    if key in seen:
                        continue
                    seen.add(key)
                    b = col.bounds
                    if b[0] <= max_x and b[2] >= min_x and b[1] <= max_y and b[3] >= min_y:
                        result.append(col)
        return result

    def query_circle(self, x, y, radius):
        return self.query_area(x - radius, y - radius, x + radius, y + radius)

    # ------------------------------------------------------------------ character queries
    def resolve_horizontal(self, x, y, radius, feet_z, head_z, step_height, iterations=4):
        """Push a character cylinder out of every collider that blocks it sideways.

        Colliders whose top is within `step_height` of the feet do NOT block - the
        character steps onto them instead (see ground_height).
        Returns (x, y, contact_normals).
        """
        normals = []
        step_top = feet_z + step_height
        for _ in range(iterations):
            moved = False
            for col in self.query_circle(x, y, radius):
                if col.z_max <= step_top or col.z_min >= head_z:
                    continue
                push = col.circle_push(x, y, radius)
                if push is None:
                    continue
                px, py = push
                length = math.hypot(px, py)
                if length < 1e-7:
                    continue
                x += px
                y += py
                normals.append((px / length, py / length))
                moved = True
            if not moved:
                break
        return x, y, normals

    def ground_height(self, x, y, radius, max_z):
        """Highest surface under the circle whose top is at or below max_z (never below the floor)."""
        best = self.floor_z
        for col in self.query_circle(x, y, radius):
            top = col.z_max
            if best < top <= max_z and col.overlaps_circle(x, y, radius):
                best = top
        return best

    def ceiling_height(self, x, y, radius, min_z):
        """Lowest collider underside above min_z that overlaps the circle (inf if none)."""
        best = math.inf
        for col in self.query_circle(x, y, radius):
            bottom = col.z_min
            if min_z <= bottom < best and col.overlaps_circle(x, y, radius):
                best = bottom
        return best

    def is_free(self, x, y, radius, z_min, z_max):
        """True if no collider overlaps the vertical cylinder [z_min, z_max] at (x, y)."""
        for col in self.query_circle(x, y, radius):
            if col.z_max <= z_min or col.z_min >= z_max:
                continue
            if col.overlaps_circle(x, y, radius):
                return False
        return True
