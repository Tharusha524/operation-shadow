"""Visual effects: particles, bullet holes, tracers, muzzle flashes and explosions.

Everything is pooled (created once, reused) so firing never allocates new scene nodes.
"""
from __future__ import annotations

import math
import random

import numpy as np
from panda3d.core import (BitMask32, ColorBlendAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, LineSegs, NodePath, TransparencyAttrib, Vec3)

from config import constants as C
from environments.materials import array_to_texture

_rng = random.Random(99)


def _quad_node(name, plane="xz"):
    vdata = GeomVertexData(name, GeomVertexFormat.get_v3t2(), Geom.UH_static)
    vw = GeomVertexWriter(vdata, "vertex")
    tw = GeomVertexWriter(vdata, "texcoord")
    for (u, v) in ((0, 0), (1, 0), (1, 1), (0, 1)):
        if plane == "xz":
            vw.add_data3(u - 0.5, 0, v - 0.5)      # faces -Y (towards a billboard's viewer)
        else:
            vw.add_data3(u - 0.5, 0, v - 0.5)
        tw.add_data2(u, v)
    prim = GeomTriangles(Geom.UH_static)
    prim.add_vertices(0, 1, 2)
    prim.add_vertices(0, 2, 3)
    geom = Geom(vdata)
    geom.add_primitive(prim)
    node = GeomNode(name)
    node.add_geom(geom)
    return node


def _radial_texture(name, size=64, power=1.6, noise=0.0, color=(1, 1, 1)):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2.0
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    alpha = np.clip(1.0 - r, 0.0, 1.0) ** power
    if noise:
        rng = np.random.default_rng(len(name))
        n = rng.random((size // 8, size // 8)).astype(np.float32)
        n = np.kron(n, np.ones((8, 8), np.float32))
        for _ in range(3):                                 # blur, so big puffs don't show square blocks
            for axis in (0, 1):
                n = sum(np.roll(n, k, axis=axis) for k in range(-4, 5)) / 9.0
        alpha *= 1.0 - noise + noise * n
    rgb = np.ones((size, size, 3), np.float32) * np.array(color, np.float32)
    return array_to_texture(name, np.concatenate([rgb, alpha[..., None]], axis=-1))


def _flash_texture(size=64):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2.0
    dx, dy = (x - c) / c, (y - c) / c
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    star = np.clip(1.0 - r / (0.35 + 0.65 * np.abs(np.cos(ang * 3)) ** 8), 0, 1)
    core = np.clip(1.0 - r * 2.2, 0, 1)
    alpha = np.clip(star * 0.8 + core, 0, 1)
    rgb = np.stack([np.ones_like(r), 0.75 + 0.25 * core, 0.35 + 0.6 * core], axis=-1)
    return array_to_texture("flash", np.concatenate([rgb, alpha[..., None]], axis=-1))


def _hole_texture(size=32):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2.0
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    alpha = np.clip(1.15 - r * 1.25, 0, 1) ** 0.7
    lum = np.clip(0.05 + r * 0.35, 0, 0.4)
    rgb = np.stack([lum, lum, lum], axis=-1)
    return array_to_texture("bullet_hole", np.concatenate([rgb, alpha[..., None]], axis=-1))


class _Particle:
    __slots__ = ("np", "vel", "age", "life", "s0", "s1", "a0", "gravity", "drag", "spin", "kind")


class Effects:
    MAX_PARTICLES = 1100
    MAX_DECALS = 90
    MAX_TRACERS = 40

    def __init__(self, base):
        self.base = base
        self.root = base.render.attach_new_node("effects")
        self.root.set_light_off(1)
        self.root.set_shader_off(1)
        self.root.hide(BitMask32.bit(C.SHADOW_CAMERA_MASK_BIT))
        self.textures = {
            "soft": _radial_texture("soft", power=1.8),
            "smoke": _radial_texture("smoke", power=1.2, noise=0.5),
            "spark": _radial_texture("spark", size=32, power=3.0, color=(1.0, 0.85, 0.5)),
            "flash": _flash_texture(),
        }
        self._quad = _quad_node("particle_quad")
        self._additive = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                               ColorBlendAttrib.O_one)
        self.particles = []
        self._free = {"alpha": [], "add": []}
        self._decals = []
        self._decal_index = 0
        self._hole_tex = _hole_texture()
        self._decal_quad = _quad_node("decal_quad")
        self._tracers = []
        self._tracer_index = 0
        self._build_tracers()
        self.lights = []

    # ------------------------------------------------------------------ pools
    def _build_tracers(self):
        segs = LineSegs("tracer")
        segs.set_thickness(2.0)
        segs.set_color(1.0, 0.85, 0.5, 1.0)
        segs.move_to(0, 0, 0)
        segs.draw_to(0, 1, 0)
        node = segs.create()
        for _ in range(self.MAX_TRACERS):
            np_ = self.root.attach_new_node(node.make_copy())
            np_.set_transparency(TransparencyAttrib.M_alpha)
            np_.set_attrib(self._additive)
            np_.set_depth_write(False)
            np_.hide()
            # node, age, life, start, direction, segment length, speed, total distance
            self._tracers.append([np_, 0.0, 0.0, Vec3(), Vec3(), 0.0, 0.0, 0.0])

    def _get_particle_np(self, blend):
        pool = self._free[blend]
        if pool:
            np_ = pool.pop()
            np_.show()
            return np_
        if len(self.particles) >= self.MAX_PARTICLES:
            oldest = self.particles.pop(0)
            self._release(oldest)
            return self._get_particle_np(blend)
        np_ = self.root.attach_new_node(self._quad.make_copy())
        np_.set_billboard_point_eye()
        np_.set_two_sided(True)
        np_.set_transparency(TransparencyAttrib.M_alpha)
        np_.set_depth_write(False)
        if blend == "add":
            np_.set_attrib(self._additive)
            np_.set_bin("fixed", 10)
        np_.set_python_tag("blend", blend)
        return np_

    def _release(self, p):
        p.np.hide()
        self._free[p.np.get_python_tag("blend")].append(p.np)

    def spawn(self, kind, pos, vel=(0, 0, 0), life=1.0, size=(0.2, 0.6), alpha=1.0, color=(1, 1, 1),
              gravity=0.0, drag=0.0, texture="soft", blend="alpha"):
        np_ = self._get_particle_np(blend)
        np_.set_texture(self.textures[texture], 1)
        np_.set_pos(*pos)
        np_.set_color_scale(color[0], color[1], color[2], alpha)
        np_.set_scale(size[0])
        np_.set_r(_rng.uniform(0, 360))
        p = _Particle()
        p.np, p.vel, p.age, p.life = np_, Vec3(*vel), 0.0, life
        p.s0, p.s1, p.a0, p.gravity, p.drag = size[0], size[1], alpha, gravity, drag
        p.spin = _rng.uniform(-60, 60)
        p.kind = kind
        self.particles.append(p)
        return p

    # ------------------------------------------------------------------ effects
    def muzzle_flash(self, pos, direction, scale=1.0):
        d = Vec3(*direction)
        self.spawn("flash", Vec3(*pos) + d * 0.1, life=0.05, size=(0.35 * scale, 0.45 * scale), texture="flash",
                   blend="add", color=(1.0, 0.85, 0.6))
        self.spawn("smoke", Vec3(*pos) + d * 0.2, vel=d * 1.5 + Vec3(0, 0, 0.4), life=0.8, size=(0.12, 0.6),
                   alpha=0.25, color=(0.7, 0.7, 0.68), texture="smoke", drag=2.0)

    def impact(self, point, normal, surface="world"):
        p, n = Vec3(*point), Vec3(*normal)
        if surface == "flesh":
            for _ in range(5):
                v = n * _rng.uniform(0.5, 2.0) + Vec3(_rng.uniform(-1, 1), _rng.uniform(-1, 1), _rng.uniform(0, 1))
                self.spawn("blood", p, vel=v, life=0.4, size=(0.08, 0.3), alpha=0.75, color=(0.45, 0.03, 0.02),
                           gravity=6.0, drag=3.0)
            return
        self.spawn("dust", p + n * 0.05, vel=n * 1.2 + Vec3(0, 0, 0.5), life=1.1, size=(0.12, 0.9), alpha=0.5,
                   color=(0.62, 0.58, 0.5), texture="smoke", drag=2.5)
        for _ in range(_rng.randint(3, 6)):
            v = n * _rng.uniform(2, 5) + Vec3(_rng.uniform(-2, 2), _rng.uniform(-2, 2), _rng.uniform(0, 3))
            self.spawn("spark", p, vel=v, life=_rng.uniform(0.15, 0.35), size=(0.04, 0.02), texture="spark",
                       blend="add", gravity=9.0)
        for _ in range(3):
            v = n * _rng.uniform(1, 3) + Vec3(_rng.uniform(-1.5, 1.5), _rng.uniform(-1.5, 1.5), _rng.uniform(1, 3))
            self.spawn("chip", p, vel=v, life=0.6, size=(0.03, 0.03), color=(0.25, 0.24, 0.22), gravity=12.0)
        self.decal(p, n)

    def decal(self, point, normal, size=0.09):
        if len(self._decals) < self.MAX_DECALS:
            np_ = self.root.attach_new_node(self._decal_quad.make_copy())
            np_.set_texture(self._hole_tex, 1)
            np_.set_transparency(TransparencyAttrib.M_alpha)
            np_.set_depth_offset(2)
            np_.set_depth_write(False)
            self._decals.append(np_)
        else:
            np_ = self._decals[self._decal_index]
            self._decal_index = (self._decal_index + 1) % self.MAX_DECALS
        n = Vec3(*normal)
        np_.set_pos(Vec3(*point) + n * 0.012)
        np_.look_at(Vec3(*point) - n)          # quad faces -Y, so -Y must point along +normal
        np_.set_r(_rng.uniform(0, 360))
        np_.set_scale(size * _rng.uniform(0.8, 1.2))

    def tracer(self, start, end, speed=350.0, length=3.5):
        s, e = Vec3(*start), Vec3(*end)
        d = e - s
        dist = d.length()
        if dist < 1.0:
            return
        d /= dist
        entry = self._tracers[self._tracer_index]
        self._tracer_index = (self._tracer_index + 1) % len(self._tracers)
        np_ = entry[0]
        np_.show()
        seg = min(length, dist)
        entry[1:] = [0.0, (dist - seg) / speed + 0.02, s, d, seg, speed, dist]
        np_.set_pos(s)
        np_.look_at(s + d)
        np_.set_sy(entry[5])

    def explosion(self, pos, scale=1.0):
        """Blast effect. scale 1 = grenade; 2-3 = mortar/artillery shell; 4+ = missile strike."""
        p = Vec3(*pos)
        k = max(0.6, scale) * (1.35 if scale >= 2.0 else 1.0)   # shells and missiles: extra big
        u = _rng.uniform
        # Flash and fireball.
        self.spawn("flash", p + Vec3(0, 0, 0.6 * k), life=0.12 + 0.04 * k, size=(3.5 * k, 6.0 * k), texture="flash",
                   blend="add", color=(1.0, 0.75, 0.4))
        self.spawn("flash", p + Vec3(0, 0, 0.2), life=0.35, size=(5.0 * k, 9.0 * k), texture="soft", blend="add",
                   color=(1.0, 0.55, 0.25), alpha=0.7)
        for _ in range(int(10 * k)):
            v = Vec3(u(-3, 3), u(-3, 3), u(1, 5)) * k ** 0.6
            self.spawn("fire", p + Vec3(u(-0.4, 0.4) * k, u(-0.4, 0.4) * k, 0.4), vel=v, life=u(0.35, 0.8) * k ** 0.4,
                       size=(0.8 * k, 2.2 * k), texture="soft", blend="add", color=(1.0, u(0.45, 0.65), 0.2), drag=2.5)
        # Black smoke that rises and hangs.
        for _ in range(int(16 * k ** 0.9)):
            r = u(0, 1.2) * k ** 0.7
            a_ = u(0, math.tau)
            off = Vec3(math.cos(a_) * r, math.sin(a_) * r, u(0.2, 1.5) * k ** 0.6)
            v = Vec3(math.cos(a_) * u(0.5, 3.0), math.sin(a_) * u(0.5, 3.0), u(0.5, 5.0)) * k ** 0.45
            g = u(0.12, 0.3)
            self.spawn("smoke", p + off, vel=v, life=u(3.0, 6.0) * k ** 0.5, size=(u(0.6, 1.2) * k ** 0.7,
                       u(2.5, 4.5) * k ** 0.75), alpha=u(0.3, 0.55), color=(g, g * 0.95, g * 0.88),
                       texture="smoke", drag=1.0, gravity=-u(0.1, 0.5))
        # Sparks and flying debris.
        for _ in range(int(18 * k ** 0.7)):
            v = Vec3(u(-9, 9), u(-9, 9), u(3, 11)) * k ** 0.5
            self.spawn("spark", p + Vec3(0, 0, 0.3), vel=v, life=u(0.4, 1.0), size=(0.07, 0.03),
                       texture="spark", blend="add", gravity=14.0)
        for _ in range(int(10 * k)):
            v = Vec3(u(-6, 6), u(-6, 6), u(3, 9)) * k ** 0.6
            sz = u(0.06, 0.12) * k ** 0.5
            self.spawn("debris", p + Vec3(0, 0, 0.3), vel=v, life=u(1.0, 2.0), size=(sz, sz),
                       color=(0.2, 0.18, 0.15), gravity=14.0)
        if scale >= 1.8:
            # Big shells: a column of earth thrown high, then raining back down.
            for _ in range(int(16 * k)):
                v = Vec3(u(-2.0, 2.0), u(-2.0, 2.0), u(8, 16)) * k ** 0.45
                self.spawn("dirt", p + Vec3(u(-0.5, 0.5), u(-0.5, 0.5), 0.2), vel=v, life=u(1.6, 2.6),
                           size=(0.6 * k ** 0.5, 2.0 * k ** 0.6), alpha=0.85, color=(0.33, 0.27, 0.2),
                           texture="smoke", gravity=9.0, drag=0.4)
            # Ground shockwave: a ring of dust racing outwards.
            for i in range(int(18 * k ** 0.5)):
                a = i / int(18 * k ** 0.5) * math.tau
                d = Vec3(math.cos(a), math.sin(a), 0)
                self.spawn("dust", p + d * 0.5 + Vec3(0, 0, 0.3), vel=d * u(9, 14) * k ** 0.5 + Vec3(0, 0, 0.6),
                           life=u(1.4, 2.4), size=(0.8 * k ** 0.5, 3.0 * k ** 0.6), alpha=0.5,
                           color=(0.55, 0.48, 0.38), texture="smoke", drag=2.2)
        self.decal(p + Vec3(0, 0, 0.02), (0, 0, 1), size=2.6 * k ** 0.8)

    def fire(self, pos, size=1.0):
        """One flame puff of a burning fire - call ~10 times per second per fire."""
        p = Vec3(*pos)
        r = 0.35 * size
        self.spawn("fire", p + Vec3(_rng.uniform(-r, r), _rng.uniform(-r, r), 0.1),
                   vel=Vec3(_rng.uniform(-0.2, 0.2), _rng.uniform(-0.2, 0.2), _rng.uniform(1.2, 2.2) * size),
                   life=_rng.uniform(0.45, 0.8), size=(0.45 * size, 0.9 * size), texture="soft", blend="add",
                   color=(1.0, _rng.uniform(0.45, 0.65), 0.18), alpha=0.9, drag=1.0)
        if _rng.random() < 0.25:
            self.spawn("smoke", p + Vec3(0, 0, 1.2 * size), vel=Vec3(_rng.uniform(-0.3, 0.3), _rng.uniform(-0.3, 0.3), 1.4),
                       life=3.5, size=(0.6 * size, 2.6 * size), alpha=0.4, color=(0.12, 0.11, 0.1), texture="smoke",
                       drag=0.3)

    def make_glow(self, pos, size=1.0, color=(1.0, 0.5, 0.18)):
        """Static orange light pool on the ground under a fire (fake light, very cheap)."""
        np_ = self.root.attach_new_node(self._decal_quad.make_copy())
        np_.set_texture(self.textures["soft"], 1)
        np_.set_transparency(TransparencyAttrib.M_alpha)
        np_.set_attrib(self._additive)
        np_.set_depth_write(False)
        np_.set_depth_offset(1)
        np_.set_pos(Vec3(*pos) + Vec3(0, 0, 0.05))
        np_.look_at(Vec3(*pos) + Vec3(0, 0, -1))
        np_.set_scale(5.0 * size)
        np_.set_color_scale(color[0], color[1], color[2], 0.55)
        return np_

    def smoke_plume(self, pos, rate_life=1.0):
        """One puff of a rising smoke column - call repeatedly for burning wrecks."""
        v = Vec3(_rng.uniform(-0.3, 0.3), _rng.uniform(-0.3, 0.3), _rng.uniform(1.0, 1.8))
        self.spawn("plume", Vec3(*pos), vel=v, life=6.0 * rate_life, size=(0.8, 4.0), alpha=0.45,
                   color=(0.18, 0.17, 0.16), texture="smoke", drag=0.2)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        keep = []
        for p in self.particles:
            p.age += dt
            if p.age >= p.life:
                self._release(p)
                continue
            t = p.age / p.life
            if p.drag:
                p.vel *= max(0.0, 1.0 - p.drag * dt)
            p.vel.z -= p.gravity * dt
            p.np.set_pos(p.np.get_pos() + p.vel * dt)
            p.np.set_scale(p.s0 + (p.s1 - p.s0) * t)
            p.np.set_alpha_scale(p.a0 * (1.0 - t) ** 1.3)
            p.np.set_r(p.np.get_r() + p.spin * dt)
            keep.append(p)
        self.particles = keep
        for entry in self._tracers:
            np_ = entry[0]
            if np_.is_hidden():
                continue
            entry[1] += dt
            if entry[1] >= entry[2]:
                np_.hide()
                continue
            travelled = min(entry[1] * entry[6], entry[7] - entry[5])
            np_.set_pos(entry[3] + entry[4] * travelled)

    def clear(self):
        for p in self.particles:
            self._release(p)
        self.particles = []
        for d in self._decals:
            d.remove_node()
        self._decals = []
        self._decal_index = 0
        for entry in self._tracers:
            entry[0].hide()
