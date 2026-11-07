"""Procedural sky dome with a sun disc. Follows the camera so it always surrounds the player."""
from __future__ import annotations

import math

from panda3d.core import (BitMask32, CompassEffect, Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, TransparencyAttrib)

from config import constants as C


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def build_sky(base, zenith, horizon, sun_direction, radius=250.0, rings=12, segments=24, clouds=0.45,
              cloud_color=(1.0, 1.0, 1.0)):
    """Create the sky under base.camera. sun_direction = direction the sunlight travels."""
    ground = _lerp(horizon, (0.35, 0.33, 0.30), 0.5)
    vdata = GeomVertexData("sky", GeomVertexFormat.get_v3c4(), Geom.UH_static)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    lat_min = math.radians(-25)
    for r in range(rings + 1):
        lat = lat_min + (math.pi / 2 - lat_min) * r / rings
        if lat >= 0:
            t = (lat / (math.pi / 2)) ** 0.55
            col = _lerp(horizon, zenith, t)
        else:
            col = _lerp(horizon, ground, min(1.0, -lat / math.radians(10)))
        for s in range(segments + 1):
            lon = 2 * math.pi * s / segments
            vw.add_data3(radius * math.cos(lat) * math.cos(lon), radius * math.cos(lat) * math.sin(lon),
                         radius * math.sin(lat))
            cw.add_data4(col[0], col[1], col[2], 1.0)
    prim = GeomTriangles(Geom.UH_static)
    w = segments + 1
    for r in range(rings):
        for s in range(segments):
            a = r * w + s
            # Wound to face inward (we look at the dome from inside).
            prim.add_vertices(a, a + w + 1, a + 1)
            prim.add_vertices(a, a + w, a + w + 1)
    geom = Geom(vdata)
    geom.add_primitive(prim)
    node = GeomNode("sky_dome")
    node.add_geom(geom)

    sky = base.camera.attach_new_node("sky")
    sky.set_effect(CompassEffect.make(base.render))   # follow camera position, ignore its rotation
    dome = sky.attach_new_node(node)

    # Sun disc + soft glow, placed opposite to the light travel direction.
    sx, sy, sz = (-sun_direction[0], -sun_direction[1], -sun_direction[2])
    sun = sky.attach_new_node(_disc("sun", 1.0, (1.0, 0.95, 0.82, 1.0), (1.0, 0.95, 0.82, 1.0)))
    glow = sky.attach_new_node(_disc("sun_glow", 1.0, (1.0, 0.9, 0.7, 0.55), (1.0, 0.85, 0.65, 0.0)))
    for np_, size in ((sun, radius * 0.018), (glow, radius * 0.13)):
        np_.set_pos(sx * radius * 0.92, sy * radius * 0.92, sz * radius * 0.92)
        np_.look_at(0, 0, 0)
        np_.set_scale(size)
        np_.set_transparency(TransparencyAttrib.M_alpha)
    glow.set_depth_write(False)

    if clouds > 0:
        _build_clouds(sky, radius, clouds, cloud_color, horizon)
    sky.set_bin("background", 0)
    sky.set_depth_write(False)
    sky.set_depth_test(False)
    sky.set_light_off(1)
    sky.set_fog_off(1)
    sky.set_shader_off(1)
    sky.hide(BitMask32.bit(C.SHADOW_CAMERA_MASK_BIT))
    return sky


def _cloud_texture(coverage, size=256, seed=11):
    import numpy as np
    from environments.materials import array_to_texture, fbm
    rng = np.random.default_rng(seed)
    n = fbm(size, 4, 6, rng, persistence=0.55)
    detail = fbm(size, 16, 3, rng)
    d = n * 0.8 + detail * 0.2
    lo = 0.62 - coverage * 0.3
    alpha = np.clip((d - lo) / 0.22, 0.0, 1.0) ** 1.4
    shade = 0.78 + 0.22 * np.clip((d - lo) / 0.4, 0.0, 1.0)          # thicker = brighter tops
    rgb = np.stack([shade, shade, shade * 1.02], axis=-1)
    return array_to_texture("clouds", np.concatenate([rgb, alpha[..., None] * 0.92], axis=-1))


def _build_clouds(sky, radius, coverage, color, horizon):
    """A wide flat cloud layer above the player that fades out towards the horizon."""
    from panda3d.core import GeomVertexFormat as F, SamplerState
    size, height, n = radius * 3.0, radius * 0.28, 16
    vdata = GeomVertexData("clouds", F.get_v3c4t2(), Geom.UH_static)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    tw = GeomVertexWriter(vdata, "texcoord")
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = -size / 2 + size * i / n, -size / 2 + size * j / n
            r = math.hypot(x, y) / (size / 2)
            fade = max(0.0, 1.0 - r) ** 0.8
            vw.add_data3(x, y, height - r * r * height * 0.9)            # curves down towards the horizon
            c = tuple(color[k] * (1 - r * 0.4) + horizon[k] * r * 0.4 for k in range(3))
            cw.add_data4(c[0], c[1], c[2], fade)
            tw.add_data2(x / (radius * 0.9), y / (radius * 0.9))
    prim = GeomTriangles(Geom.UH_static)
    w = n + 1
    for j in range(n):
        for i in range(n):
            a = j * w + i
            prim.add_vertices(a, a + 1, a + w + 1)
            prim.add_vertices(a, a + w + 1, a + w)
            prim.add_vertices(a, a + w + 1, a + 1)          # visible from below too
            prim.add_vertices(a, a + w, a + w + 1)
    geom = Geom(vdata)
    geom.add_primitive(prim)
    node = GeomNode("cloud_layer")
    node.add_geom(geom)
    np_ = sky.attach_new_node(node)
    tex = _cloud_texture(coverage)
    tex.set_wrap_u(SamplerState.WM_repeat)
    tex.set_wrap_v(SamplerState.WM_repeat)
    tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)
    np_.set_texture(tex, 1)
    np_.set_transparency(TransparencyAttrib.M_alpha)
    np_.set_bin("background", 5)
    np_.set_depth_write(False)
    sky.set_python_tag("clouds", np_)
    return np_


def scroll_clouds(sky, dt, speed=(0.004, 0.0015)):
    from panda3d.core import TextureStage
    clouds = sky.get_python_tag("clouds") if sky is not None else None
    if clouds is None:
        return
    off = clouds.get_tex_offset(TextureStage.get_default())
    clouds.set_tex_offset(TextureStage.get_default(), (off.x + speed[0] * dt) % 1.0, (off.y + speed[1] * dt) % 1.0)


def _disc(name, radius, centre_color, edge_color, segments=24):
    vdata = GeomVertexData(name, GeomVertexFormat.get_v3c4(), Geom.UH_static)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    vw.add_data3(0, 0, 0)
    cw.add_data4(*centre_color)
    for i in range(segments):
        a = 2 * math.pi * i / segments
        vw.add_data3(radius * math.cos(a), 0, radius * math.sin(a))
        cw.add_data4(*edge_color)
    prim = GeomTriangles(Geom.UH_static)
    for i in range(segments):
        a, b = 1 + i, 1 + (i + 1) % segments
        prim.add_vertices(0, a, b)
        prim.add_vertices(0, b, a)
    geom = Geom(vdata)
    geom.add_primitive(prim)
    node = GeomNode(name)
    node.add_geom(geom)
    return node
