"""MeshBuilder - creates optimised static 3D geometry from simple shape calls.

Prop builders (environments/props.py) call methods such as box(), cylinder(),
ellipsoid() or extrude_x(). The builder:
  * applies the current placement transform (position + rotation around Z),
  * batches all triangles by (map chunk, material) so the whole level renders in a
    small number of draw calls (important for laptop GPUs),
  * records collision shapes in world space for the CollisionWorld.

Local prop convention: origin at the base centre, +Y is the "front/forward" of
vehicles, Z up, metres.
"""
from __future__ import annotations

import math
from contextlib import contextmanager

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, InternalName)

from config import constants as C
from systems.collision_system import BoxCollider, CylinderCollider


def _make_format():
    """Position, normal, colour, UV + tangent/binormal (needed for normal-mapped surfaces)."""
    arr = GeomVertexArrayFormat()
    arr.add_column(InternalName.get_vertex(), 3, Geom.NT_float32, Geom.C_point)
    arr.add_column(InternalName.get_normal(), 3, Geom.NT_float32, Geom.C_normal)
    arr.add_column(InternalName.get_color(), 4, Geom.NT_float32, Geom.C_color)
    arr.add_column(InternalName.get_texcoord(), 2, Geom.NT_float32, Geom.C_texcoord)
    arr.add_column(InternalName.get_tangent(), 3, Geom.NT_float32, Geom.C_vector)
    arr.add_column(InternalName.get_binormal(), 3, Geom.NT_float32, Geom.C_vector)
    return GeomVertexFormat.register_format(GeomVertexFormat(arr))


VERTEX_FORMAT = _make_format()


class _Part:
    __slots__ = ("vdata", "vw", "nw", "cw", "tw", "tanw", "binw", "prim", "count")

    def __init__(self, name):
        self.vdata = GeomVertexData(name, VERTEX_FORMAT, Geom.UH_static)
        self.vw = GeomVertexWriter(self.vdata, "vertex")
        self.nw = GeomVertexWriter(self.vdata, "normal")
        self.cw = GeomVertexWriter(self.vdata, "color")
        self.tw = GeomVertexWriter(self.vdata, "texcoord")
        self.tanw = GeomVertexWriter(self.vdata, "tangent")
        self.binw = GeomVertexWriter(self.vdata, "binormal")
        self.prim = GeomTriangles(Geom.UH_static)
        self.count = 0


def _tangents(positions, normals, uvs, indices):
    """Per-vertex tangent (U direction) and binormal (V direction) for normal mapping."""
    n = len(positions)
    tan = [[0.0, 0.0, 0.0] for _ in range(n)]
    bit = [[0.0, 0.0, 0.0] for _ in range(n)]
    for k in range(0, len(indices), 3):
        i0, i1, i2 = indices[k], indices[k + 1], indices[k + 2]
        p0, p1, p2 = positions[i0], positions[i1], positions[i2]
        u0, u1, u2 = uvs[i0], uvs[i1], uvs[i2]
        e1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        e2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        du1, dv1 = u1[0] - u0[0], u1[1] - u0[1]
        du2, dv2 = u2[0] - u0[0], u2[1] - u0[1]
        r = du1 * dv2 - du2 * dv1
        if abs(r) < 1e-12:
            continue
        r = 1.0 / r
        t = ((e1[0] * dv2 - e2[0] * dv1) * r, (e1[1] * dv2 - e2[1] * dv1) * r, (e1[2] * dv2 - e2[2] * dv1) * r)
        b = ((e2[0] * du1 - e1[0] * du2) * r, (e2[1] * du1 - e1[1] * du2) * r, (e2[2] * du1 - e1[2] * du2) * r)
        for i in (i0, i1, i2):
            ti, bi = tan[i], bit[i]
            ti[0] += t[0]; ti[1] += t[1]; ti[2] += t[2]
            bi[0] += b[0]; bi[1] += b[1]; bi[2] += b[2]
    out_t, out_b = [], []
    for i in range(n):
        nx, ny, nz = normals[i]
        tx, ty, tz = tan[i]
        d = nx * tx + ny * ty + nz * tz
        tx, ty, tz = tx - nx * d, ty - ny * d, tz - nz * d          # make it perpendicular to the normal
        length = math.sqrt(tx * tx + ty * ty + tz * tz)
        if length < 1e-9:                                           # no usable UVs: any perpendicular axis
            tx, ty, tz = (1.0, 0.0, 0.0) if abs(nx) < 0.9 else (0.0, 1.0, 0.0)
            d = nx * tx + ny * ty + nz * tz
            tx, ty, tz = tx - nx * d, ty - ny * d, tz - nz * d
            length = math.sqrt(tx * tx + ty * ty + tz * tz)
        tx, ty, tz = tx / length, ty / length, tz / length
        bx, by, bz = ny * tz - nz * ty, nz * tx - nx * tz, nx * ty - ny * tx
        b = bit[i]
        if bx * b[0] + by * b[1] + bz * b[2] < 0.0:                # mirrored UVs
            bx, by, bz = -bx, -by, -bz
        out_t.append((tx, ty, tz))
        out_b.append((bx, by, bz))
    return out_t, out_b


def _rgba(color):
    if len(color) == 4:
        return tuple(color)
    return color[0], color[1], color[2], 1.0


def _normalize(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-12:
        return 0.0, 0.0, 1.0
    return v[0] / length, v[1] / length, v[2] / length


def _cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


class MeshBuilder:
    def __init__(self, uv_scales=None, chunk_size=C.CHUNK_SIZE):
        self._uv_scales = dict(uv_scales or {})
        self._chunk_size = chunk_size
        self._parts = {}
        self.colliders = []
        self._tx = self._ty = self._tz = 0.0
        self._yaw = 0.0
        self._cos, self._sin = 1.0, 0.0
        self._depth = 0
        self._chunk = (0, 0)
        self._chunk_override = None
        self._geometry_enabled = True
        self.vertex_count = 0
        self.triangle_count = 0
        # Real 3D models (assets/models/*.bam) placed instead of procedural geometry.
        self.model_budget = {}          # model key -> how many more copies may be used
        self.model_requests = []        # (key, x, y, z, heading, scale) in world space

    # ------------------------------------------------------------------ transforms
    def _set_transform(self, tx, ty, tz, yaw):
        self._tx, self._ty, self._tz, self._yaw = tx, ty, tz, yaw
        rad = math.radians(yaw)
        self._cos, self._sin = math.cos(rad), math.sin(rad)

    def to_world(self, x, y, z=0.0):
        c, s = self._cos, self._sin
        return self._tx + x * c - y * s, self._ty + x * s + y * c, self._tz + z

    @contextmanager
    def place(self, x, y, z=0.0, yaw=0.0):
        """Nest a local frame: everything inside is moved by (x, y, z) and rotated by yaw degrees."""
        saved = (self._tx, self._ty, self._tz, self._yaw, self._chunk)
        wx, wy, wz = self.to_world(x, y, z)
        if self._depth == 0:
            self._chunk = (math.floor(wx / self._chunk_size), math.floor(wy / self._chunk_size))
        self._set_transform(wx, wy, wz, self._yaw + yaw)
        self._depth += 1
        try:
            yield self
        finally:
            self._depth -= 1
            self._set_transform(*saved[:4])
            self._chunk = saved[4]

    @contextmanager
    def chunk(self, key):
        """Force geometry into a named chunk (used for the big terrain mesh)."""
        saved = self._chunk_override
        self._chunk_override = key
        try:
            yield self
        finally:
            self._chunk_override = saved

    @contextmanager
    def colliders_only(self):
        """Record collision shapes but skip visual geometry (used when a real model replaces a prop)."""
        saved = self._geometry_enabled
        self._geometry_enabled = False
        try:
            yield self
        finally:
            self._geometry_enabled = saved

    # ------------------------------------------------------------------ real models
    def use_model(self, key, x=0.0, y=0.0, z=0.0, yaw=0.0, scale=1.0):
        """Place a copy of a real model here if one is available (and within budget).

        Returns True when the model will be used - the caller then skips its procedural
        geometry (but still adds its colliders).
        """
        if not self._geometry_enabled or self.model_budget.get(key, 0) <= 0:
            return False
        self.model_budget[key] -= 1
        wx, wy, wz = self.to_world(x, y, z)
        self.model_requests.append((key, wx, wy, wz, self._yaw + yaw, scale))
        return True

    # ------------------------------------------------------------------ colliders
    def collider_box(self, x, y, z, sx, sy, sz, yaw=0.0, tag="static"):
        """Solid box in local space: (x, y) centre, z = bottom, sizes sx/sy/sz."""
        wx, wy, wz = self.to_world(x, y, z)
        self.colliders.append(BoxCollider(wx, wy, wz, wz + sz, sx / 2.0, sy / 2.0, self._yaw + yaw, tag))

    def collider_cylinder(self, x, y, z, radius, height, tag="static"):
        wx, wy, wz = self.to_world(x, y, z)
        self.colliders.append(CylinderCollider(wx, wy, wz, wz + height, radius, tag))

    # ------------------------------------------------------------------ low-level emit
    def _uv_k(self, material, uv_scale=None):
        return 1.0 / (uv_scale or self._uv_scales.get(material, 2.0))

    def _part(self, material):
        key = (self._chunk_override if self._chunk_override is not None else self._chunk, material)
        part = self._parts.get(key)
        if part is None:
            part = self._parts[key] = _Part(f"{key[0]}_{material}")
        return part

    def _emit(self, material, positions, normals, uvs, color, indices, colors=None):
        if not self._geometry_enabled:
            return
        part = self._part(material)
        vw, nw, cw, tw = part.vw, part.nw, part.cw, part.tw
        tanw, binw = part.tanw, part.binw
        tangents, binormals = _tangents(positions, normals, uvs, indices)
        c, s = self._cos, self._sin
        tx, ty, tz = self._tx, self._ty, self._tz
        r, g, b, a = _rgba(color)
        for i, (px, py, pz) in enumerate(positions):
            vw.add_data3(tx + px * c - py * s, ty + px * s + py * c, tz + pz)
            nx, ny, nz = normals[i]
            nw.add_data3(nx * c - ny * s, nx * s + ny * c, nz)
            if colors is not None:
                cw.add_data4(*_rgba(colors[i]))
            else:
                cw.add_data4(r, g, b, a)
            tw.add_data2(uvs[i][0], uvs[i][1])
            ax, ay, az = tangents[i]
            tanw.add_data3(ax * c - ay * s, ax * s + ay * c, az)
            ax, ay, az = binormals[i]
            binw.add_data3(ax * c - ay * s, ax * s + ay * c, az)
        base = part.count
        prim = part.prim
        for k in range(0, len(indices), 3):
            prim.add_vertices(base + indices[k], base + indices[k + 1], base + indices[k + 2])
        part.count += len(positions)
        self.vertex_count += len(positions)
        self.triangle_count += len(indices) // 3

    def _quad(self, material, pts, normal, uvs, color, double_sided=False):
        self._emit(material, pts, [normal] * 4, uvs, color, (0, 1, 2, 0, 2, 3))
        if double_sided:
            back = (-normal[0], -normal[1], -normal[2])
            self._emit(material, pts, [back] * 4, uvs, color, (0, 2, 1, 0, 3, 2))

    # ------------------------------------------------------------------ primitives
    def quad(self, material, p0, p1, p2, p3, color, *, double_sided=False, uv_scale=None):
        """Planar quad, points counter-clockwise seen from the front. UVs are projected automatically."""
        n = _normalize(_cross(_sub(p1, p0), _sub(p2, p0)))
        k = self._uv_k(material, uv_scale)
        ax, ay, az = abs(n[0]), abs(n[1]), abs(n[2])
        if az >= ax and az >= ay:
            uvs = [(p[0] * k, p[1] * k) for p in (p0, p1, p2, p3)]
        elif ax >= ay:
            uvs = [(p[1] * k, p[2] * k) for p in (p0, p1, p2, p3)]
        else:
            uvs = [(p[0] * k, p[2] * k) for p in (p0, p1, p2, p3)]
        self._quad(material, [p0, p1, p2, p3], n, uvs, color, double_sided)

    def flat_rect(self, material, x0, y0, x1, y1, z, color, *, world_uv=False, uv_scale=None):
        """Horizontal rectangle facing up (roads, markings, pads)."""
        k = self._uv_k(material, uv_scale)
        pts = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
        if world_uv:
            uvs = []
            for p in pts:
                wx, wy, _ = self.to_world(*p)
                uvs.append((wx * k, wy * k))
        else:
            uvs = [(p[0] * k, p[1] * k) for p in pts]
        self._quad(material, pts, (0.0, 0.0, 1.0), uvs, color)

    def box(self, material, x, y, z, sx, sy, sz, color, *, yaw=0.0, top=True, bottom=False,
            collide=False, uv_scale=None):
        """Box with (x, y) = centre and z = bottom."""
        if yaw:
            with self.place(x, y, 0.0, yaw):
                self.box(material, 0.0, 0.0, z, sx, sy, sz, color, top=top, bottom=bottom,
                         collide=collide, uv_scale=uv_scale)
            return
        k = self._uv_k(material, uv_scale)
        x0, x1 = x - sx / 2.0, x + sx / 2.0
        y0, y1 = y - sy / 2.0, y + sy / 2.0
        z0, z1 = z, z + sz
        q = self._quad
        q(material, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0),
          [(y0 * k, z0 * k), (y1 * k, z0 * k), (y1 * k, z1 * k), (y0 * k, z1 * k)], color)
        q(material, [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], (-1, 0, 0),
          [(-y1 * k, z0 * k), (-y0 * k, z0 * k), (-y0 * k, z1 * k), (-y1 * k, z1 * k)], color)
        q(material, [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], (0, 1, 0),
          [(-x1 * k, z0 * k), (-x0 * k, z0 * k), (-x0 * k, z1 * k), (-x1 * k, z1 * k)], color)
        q(material, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0),
          [(x0 * k, z0 * k), (x1 * k, z0 * k), (x1 * k, z1 * k), (x0 * k, z1 * k)], color)
        if top:
            q(material, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1),
              [(x0 * k, y0 * k), (x1 * k, y0 * k), (x1 * k, y1 * k), (x0 * k, y1 * k)], color)
        if bottom:
            q(material, [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], (0, 0, -1),
              [(x1 * k, y0 * k), (x0 * k, y0 * k), (x0 * k, y1 * k), (x1 * k, y1 * k)], color)
        if collide:
            self.collider_box(x, y, z, sx, sy, sz)

    def cylinder(self, material, x, y, z, radius, height, color, *, segments=10, radius_top=None,
                 top=True, bottom=False, radial_noise=0.0, rng=None, collide=False, uv_scale=None):
        """Upright cylinder / cone / frustum with its base centre at (x, y, z)."""
        rt = radius if radius_top is None else radius_top
        k = self._uv_k(material, uv_scale)
        noise = [1.0] * segments
        if radial_noise and rng is not None:
            noise = [1.0 + rng.uniform(-radial_noise, radial_noise) for _ in range(segments)]
        circumference = math.pi * (radius + rt)
        positions, normals, uvs, idx = [], [], [], []
        slope = radius - rt
        for i in range(segments + 1):
            a = 2.0 * math.pi * i / segments
            ca, sa = math.cos(a), math.sin(a)
            m = noise[i % segments]
            n = _normalize((ca * height, sa * height, slope))
            u = circumference * i / segments * k
            positions += [(x + radius * m * ca, y + radius * m * sa, z), (x + rt * m * ca, y + rt * m * sa, z + height)]
            normals += [n, n]
            uvs += [(u, z * k), (u, (z + height) * k)]
        for i in range(segments):
            b0, t0, b1, t1 = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
            idx += [b0, b1, t1, b0, t1, t0]
        self._emit(material, positions, normals, uvs, color, idx)
        if top and rt > 1e-6:
            self._disc(material, x, y, z + height, rt, segments, color, up=True, noise=noise, k=k)
        if bottom and radius > 1e-6:
            self._disc(material, x, y, z, radius, segments, color, up=False, noise=noise, k=k)
        if collide:
            self.collider_cylinder(x, y, z, max(radius, rt), height)

    def _disc(self, material, x, y, z, radius, segments, color, *, up, noise, k):
        positions = [(x, y, z)]
        uvs = [(x * k, y * k)]
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            px, py = x + radius * noise[i] * math.cos(a), y + radius * noise[i] * math.sin(a)
            positions.append((px, py, z))
            uvs.append((px * k, py * k))
        n = (0.0, 0.0, 1.0 if up else -1.0)
        idx = []
        for i in range(segments):
            a, b = 1 + i, 1 + (i + 1) % segments
            idx += [0, a, b] if up else [0, b, a]
        self._emit(material, positions, [n] * len(positions), uvs, color, idx)

    def cylinder_between(self, material, p0, p1, radius, color, *, segments=8, caps=False,
                         radius_end=None, uv_scale=None):
        """Cylinder (or cone when radius_end differs) along an arbitrary axis from p0 to p1."""
        r1 = radius if radius_end is None else radius_end
        axis = _sub(p1, p0)
        length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
        if length < 1e-9:
            return
        a = (axis[0] / length, axis[1] / length, axis[2] / length)
        helper = (0.0, 0.0, 1.0) if abs(a[2]) < 0.9 else (1.0, 0.0, 0.0)
        u = _normalize(_cross(a, helper))
        v = _cross(a, u)
        k = self._uv_k(material, uv_scale)
        slope = radius - r1
        positions, normals, uvs, idx = [], [], [], []
        for i in range(segments + 1):
            ang = 2.0 * math.pi * i / segments
            ca, sa = math.cos(ang), math.sin(ang)
            d = (u[0] * ca + v[0] * sa, u[1] * ca + v[1] * sa, u[2] * ca + v[2] * sa)
            n = _normalize((d[0] * length + a[0] * slope, d[1] * length + a[1] * slope, d[2] * length + a[2] * slope))
            positions += [(p0[0] + d[0] * radius, p0[1] + d[1] * radius, p0[2] + d[2] * radius),
                          (p1[0] + d[0] * r1, p1[1] + d[1] * r1, p1[2] + d[2] * r1)]
            normals += [n, n]
            uu = math.pi * (radius + r1) * i / segments * k
            uvs += [(uu, 0.0), (uu, length * k)]
        for i in range(segments):
            b0, t0, b1, t1 = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
            idx += [b0, b1, t1, b0, t1, t0]
        self._emit(material, positions, normals, uvs, color, idx)
        if caps:
            for centre, rad, sign in ((p1, r1, 1.0), (p0, radius, -1.0)):
                if rad <= 1e-6:
                    continue
                cap_pos = [centre]
                for i in range(segments):
                    ang = 2.0 * math.pi * i / segments
                    ca, sa = math.cos(ang), math.sin(ang)
                    cap_pos.append((centre[0] + (u[0] * ca + v[0] * sa) * rad,
                                    centre[1] + (u[1] * ca + v[1] * sa) * rad,
                                    centre[2] + (u[2] * ca + v[2] * sa) * rad))
                n = (a[0] * sign, a[1] * sign, a[2] * sign)
                cap_idx = []
                for i in range(segments):
                    p, q = 1 + i, 1 + (i + 1) % segments
                    cap_idx += [0, p, q] if sign > 0 else [0, q, p]
                cap_uvs = [((pp[0] + pp[1]) * k, pp[2] * k) for pp in cap_pos]
                self._emit(material, cap_pos, [n] * len(cap_pos), cap_uvs, color, cap_idx)

    def ellipsoid(self, material, x, y, z, rx, ry, rz, color, *, rings=6, segments=10, noise=0.0,
                  rng=None, flat=False, uv_scale=None):
        """Ellipsoid centred at (x, y, z). noise > 0 makes it lumpy (rocks, foliage, sandbags)."""
        k = self._uv_k(material, uv_scale)
        offsets = {}

        def jitter(ri, si):
            if noise <= 0.0 or rng is None:
                return 1.0
            key = (ri, 0) if ri in (0, rings) else (ri, si % segments)
            if key not in offsets:
                offsets[key] = 1.0 + rng.uniform(-noise, noise)
            return offsets[key]

        grid = []
        for ri in range(rings + 1):
            lat = -math.pi / 2.0 + math.pi * ri / rings
            cl, sl = math.cos(lat), math.sin(lat)
            row = []
            for si in range(segments + 1):
                lon = 2.0 * math.pi * si / segments
                m = jitter(ri, si)
                px = x + rx * cl * math.cos(lon) * m
                py = y + ry * cl * math.sin(lon) * m
                pz = z + rz * sl * m
                n = _normalize((cl * math.cos(lon) / max(rx, 1e-6), cl * math.sin(lon) / max(ry, 1e-6), sl / max(rz, 1e-6)))
                uv = (lon * (rx + ry) * 0.5 * k, (lat + math.pi / 2) * rz * k)
                row.append(((px, py, pz), n, uv))
            grid.append(row)

        if flat:
            for ri in range(rings):
                for si in range(segments):
                    a, b = grid[ri][si], grid[ri][si + 1]
                    c, d = grid[ri + 1][si + 1], grid[ri + 1][si]
                    for tri in ((a, b, c), (a, c, d)):
                        p0, p1, p2 = tri[0][0], tri[1][0], tri[2][0]
                        n = _cross(_sub(p1, p0), _sub(p2, p0))
                        if n[0] * n[0] + n[1] * n[1] + n[2] * n[2] < 1e-14:
                            continue
                        n = _normalize(n)
                        self._emit(material, [p0, p1, p2], [n, n, n], [tri[0][2], tri[1][2], tri[2][2]], color, (0, 1, 2))
            return

        positions, normals, uvs, idx = [], [], [], []
        width = segments + 1
        for row in grid:
            for p, n, uv in row:
                positions.append(p)
                normals.append(n)
                uvs.append(uv)
        for ri in range(rings):
            for si in range(segments):
                a = ri * width + si
                b = a + 1
                c = a + width + 1
                d = a + width
                idx += [a, b, c, a, c, d]
        self._emit(material, positions, normals, uvs, color, idx)

    def polygon_x(self, material, x, points, color, *, facing=1, double_sided=False, uv_scale=None):
        """Convex polygon lying in the plane local-X = x. points are (y, z), counter-clockwise seen from +X."""
        k = self._uv_k(material, uv_scale)
        positions = [(x, py, pz) for py, pz in points]
        uvs = [(py * k, pz * k) for py, pz in points]
        idx = []
        for i in range(1, len(points) - 1):
            idx += [0, i, i + 1] if facing > 0 else [0, i + 1, i]
        n = (1.0 if facing > 0 else -1.0, 0.0, 0.0)
        self._emit(material, positions, [n] * len(positions), uvs, color, idx)
        if double_sided:
            self.polygon_x(material, x, points, color, facing=-facing, uv_scale=uv_scale)

    def extrude_x(self, material, profile, x0, x1, color, *, closed=True, caps=True,
                  double_sided=False, uv_scale=None):
        """Extrude a 2D profile [(y, z), ...] (counter-clockwise seen from +X) along local X."""
        k = self._uv_k(material, uv_scale)
        n_pts = len(profile)
        edges = range(n_pts) if closed else range(n_pts - 1)
        perimeter = 0.0
        for i in edges:
            ya, za = profile[i]
            yb, zb = profile[(i + 1) % n_pts]
            dy, dz = yb - ya, zb - za
            length = math.hypot(dy, dz)
            if length < 1e-9:
                continue
            n = (0.0, dz / length, -dy / length)
            pts = [(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)]
            uvs = [(x0 * k, perimeter * k), (x0 * k, (perimeter + length) * k),
                   (x1 * k, (perimeter + length) * k), (x1 * k, perimeter * k)]
            self._quad(material, pts, n, uvs, color, double_sided)
            perimeter += length
        if caps and closed:
            self.polygon_x(material, x1, profile, color, facing=1, double_sided=double_sided, uv_scale=uv_scale)
            self.polygon_x(material, x0, profile, color, facing=-1, double_sided=double_sided, uv_scale=uv_scale)

    def terrain(self, material, size, divisions, colors, holes=()):
        """Flat ground grid centred on the origin. colors[j][i] gives the colour of vertex (i, j).

        holes: rectangles (x0, y0, x1, y1) - grid cells whose centre lies inside are left out
        (rivers, pits). Choose size/divisions so the cell edges line up with the holes.
        """
        k = self._uv_k(material)
        half = size / 2.0
        step = size / divisions
        width = divisions + 1
        positions, normals, uvs, cols, idx = [], [], [], [], []
        for j in range(width):
            for i in range(width):
                px, py = -half + i * step, -half + j * step
                positions.append((px, py, 0.0))
                normals.append((0.0, 0.0, 1.0))
                uvs.append((px * k, py * k))
                cols.append(colors[j][i])
        for j in range(divisions):
            for i in range(divisions):
                cx, cy = -half + (i + 0.5) * step, -half + (j + 0.5) * step
                if any(h[0] <= cx <= h[2] and h[1] <= cy <= h[3] for h in holes):
                    continue
                a = j * width + i
                idx += [a, a + 1, a + width + 1, a, a + width + 1, a + width]
        self._emit(material, positions, normals, uvs, (1, 1, 1, 1), idx, colors=cols)

    # ------------------------------------------------------------------ output
    def build(self, parent, materials, name="static_world"):
        """Turn everything recorded so far into GeomNodes under `parent`."""
        root = parent.attach_new_node(name)
        chunk_nodes = {}
        for (chunk_key, material), part in sorted(self._parts.items(), key=lambda kv: str(kv[0])):
            if part.count == 0:
                continue
            geom = Geom(part.vdata)
            geom.add_primitive(part.prim)
            node = GeomNode(material)
            node.add_geom(geom)
            chunk_np = chunk_nodes.get(chunk_key)
            if chunk_np is None:
                chunk_np = chunk_nodes[chunk_key] = root.attach_new_node(f"chunk_{chunk_key}")
            np_ = chunk_np.attach_new_node(node)
            materials.apply(np_, material)
        self._parts.clear()
        return root
