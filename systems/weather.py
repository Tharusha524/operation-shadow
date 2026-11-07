"""Rain: two textured cylinders of falling streaks around the camera, ground splashes and a rain sound.

Cheap on purpose (two meshes and a handful of particles). The rain fades out under a roof.
"""
from __future__ import annotations

import math

import numpy as np
from panda3d.core import (BitMask32, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, NodePath, SamplerState, Texture, TextureStage, TransparencyAttrib)

from config import constants as C

LAYERS = ((3.5, 12.0, 18, 3.0, 9.0), (8.0, 16.0, 36, 3.0, 7.0))   # radius, height, u repeats, v repeats, speed


def streak_texture(size=(128, 256), count=120, seed=5):
    """White vertical streaks with soft alpha (generated, no files needed)."""
    w, h = size
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 4), dtype=np.float32)
    img[..., :3] = 1.0
    for _ in range(count):
        x = rng.integers(0, w)
        y0 = rng.integers(0, h)
        length = rng.integers(h // 16, h // 7)
        alpha = rng.uniform(0.15, 0.45)
        ys = (y0 + np.arange(length)) % h
        fade = np.linspace(0.2, 1.0, length)
        img[ys, x, 3] = np.maximum(img[ys, x, 3], alpha * fade)
    tex = Texture("rain_streaks")
    tex.setup_2d_texture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
    data = (img[::-1] * 255).astype(np.uint8)[..., [2, 1, 0, 3]]        # Panda expects BGRA, bottom row first
    tex.set_ram_image(data.tobytes())
    tex.set_wrap_u(SamplerState.WM_repeat)
    tex.set_wrap_v(SamplerState.WM_repeat)
    tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)
    return tex


def cylinder_geom(radius, height, segments=24, u_repeat=6, v_repeat=2):
    vdata = GeomVertexData("rain", GeomVertexFormat.get_v3t2(), Geom.UH_static)
    vw, tw = GeomVertexWriter(vdata, "vertex"), GeomVertexWriter(vdata, "texcoord")
    for i in range(segments + 1):
        a = 2 * math.pi * i / segments
        x, y = math.cos(a) * radius, math.sin(a) * radius
        u = u_repeat * i / segments
        vw.add_data3(x, y, -height / 2)
        tw.add_data2(u, 0)
        vw.add_data3(x, y, height / 2)
        tw.add_data2(u, v_repeat)
    tris = GeomTriangles(Geom.UH_static)
    for i in range(segments):
        b = i * 2
        tris.add_vertices(b, b + 2, b + 1)
        tris.add_vertices(b + 1, b + 2, b + 3)
    geom = Geom(vdata)
    geom.add_primitive(tris)
    node = GeomNode("rain_layer")
    node.add_geom(geom)
    return node


class Rain:
    def __init__(self, game):
        self.game = game
        self.intensity = 0.0
        self.root = NodePath("rain")
        self.layers = []
        tex = streak_texture()
        for radius, height, u_rep, v_rep, speed in LAYERS:
            np_ = self.root.attach_new_node(cylinder_geom(radius, height, u_repeat=u_rep, v_repeat=v_rep))
            np_.set_texture(tex)
            self.layers.append([np_, speed, 0.0])
        self.root.set_transparency(TransparencyAttrib.M_alpha)
        self.root.set_depth_write(False)
        self.root.set_two_sided(True)
        self.root.set_light_off(1)
        self.root.set_fog_off(1)
        self.root.set_bin("transparent", 30)
        self.root.hide(BitMask32.bit(C.SHADOW_CAMERA_MASK_BIT))
        self.root.reparent_to(game.render)
        self.root.hide()
        self._splash = 0.0
        self._cover = 1.0
        self._sound = False

    def set_intensity(self, value):
        self.intensity = max(0.0, min(1.0, float(value or 0.0)))
        if self.intensity <= 0.0:
            self.root.hide()
            if self._sound:
                self.game.audio.stop_loop("rain_loop")
                self._sound = False
        else:
            self.root.show()

    def update(self, dt, cam_pos, active=True):
        if self.intensity <= 0.0:
            return
        g = self.game
        playing = "rain_loop" in getattr(g.audio, "_loops", {})
        if active and not playing:
            g.audio.start_loop("rain_loop", 0.35 * self.intensity)
        elif not active and playing:
            g.audio.stop_loop("rain_loop")
        self._sound = active
        x, y, z = cam_pos
        self.root.set_pos(x, y, z)
        roof = g.collision_world.ceiling_height(x, y, 0.3, z + 0.2) < z + 30.0
        target = 0.0 if roof else 1.0
        self._cover += (target - self._cover) * min(1.0, dt * 4.0)
        self.root.set_alpha_scale(0.32 * self.intensity * self._cover)
        for layer in self.layers:
            layer[2] = (layer[2] + dt * layer[1] / 4.0) % 1.0
            layer[0].set_tex_offset(TextureStage.get_default(), 0.0, layer[2])
        # Splashes on the ground around the player.
        if not active or self._cover < 0.5:
            return
        self._splash -= dt
        rng = g.vehicles.rng
        ground = g.player.position[2]
        while self._splash <= 0.0:
            self._splash += 0.05 / self.intensity
            a, r = rng.uniform(0, 2 * math.pi), rng.uniform(1.0, 9.0)
            g.effects.spawn("smoke", (x + math.cos(a) * r, y + math.sin(a) * r, ground + 0.05),
                            vel=(0, 0, 0.6), life=0.22, size=(0.04, 0.2), alpha=0.45, color=(0.8, 0.85, 0.9),
                            texture="soft")
