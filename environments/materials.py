"""Materials (textures + render flags) for the procedural environments.

Every material gets a seamless tiling texture that is GENERATED IN CODE with numpy
(concrete, asphalt, dirt, metal, wood, ...). Vertex colours tint these textures, so
one concrete texture can look like pale walls or dark slabs.

REPLACING WITH REAL TEXTURES
----------------------------
Drop an image named after the material into assets/textures/, for example:
    assets/textures/concrete.png      assets/textures/dirt.jpg
It is used automatically instead of the generated one. Use seamless (tileable)
images. The "uv" value below is how many metres one repeat of the image covers.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
from panda3d.core import BitMask32, Filename, Material, SamplerState, Texture, TextureStage, TransparencyAttrib

from config import constants as C

log = logging.getLogger(__name__)

TEXTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tga", ".dds")


# =============================================================================
# Seamless noise helpers
# =============================================================================
def value_noise(size, cells_x, cells_y, rng):
    """Smooth, seamlessly tiling value noise in [0, 1] with shape (size, size)."""
    cells_x = max(1, min(size, int(cells_x)))
    cells_y = max(1, min(size, int(cells_y)))
    grid = rng.random((cells_y, cells_x)).astype(np.float32)

    def axis(cells):
        t = np.arange(size, dtype=np.float32) * (cells / size)
        i0 = t.astype(np.int32)
        f = t - i0
        f = f * f * (3.0 - 2.0 * f)
        return i0 % cells, (i0 + 1) % cells, f

    x0, x1, fx = axis(cells_x)
    y0, y1, fy = axis(cells_y)
    a = grid[np.ix_(y0, x0)]
    b = grid[np.ix_(y0, x1)]
    c = grid[np.ix_(y1, x0)]
    d = grid[np.ix_(y1, x1)]
    fx = fx[None, :]
    fy = fy[:, None]
    top = a + (b - a) * fx
    bottom = c + (d - c) * fx
    return top + (bottom - top) * fy


def fbm(size, cells, octaves, rng, persistence=0.5, stretch=(1.0, 1.0)):
    """Fractal (multi-octave) seamless noise in [0, 1]."""
    total = np.zeros((size, size), np.float32)
    amp, norm, c = 1.0, 0.0, float(cells)
    for _ in range(octaves):
        total += value_noise(size, c * stretch[0], c * stretch[1], rng) * amp
        norm += amp
        amp *= persistence
        c *= 2
    return total / norm


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _rgb(lum, tint=(1.0, 1.0, 1.0)):
    return np.stack([lum * tint[0], lum * tint[1], lum * tint[2]], axis=-1)


def _coords(size):
    y = np.arange(size, dtype=np.float32)[:, None]
    x = np.arange(size, dtype=np.float32)[None, :]
    return x, y


# =============================================================================
# Texture generators. Each returns float32 (size, size, 3 or 4) in [0, 1].
# =============================================================================
def gen_concrete(size, rng):
    lum = 0.72 + (fbm(size, 4, 5, rng) - 0.5) * 0.28
    lum += (value_noise(size, size // 4, size // 4, rng) - 0.5) * 0.10
    stains = fbm(size, 3, 3, rng)
    lum -= np.clip(stains - 0.56, 0, None) * 0.8
    lum -= (rng.random((size, size)) > 0.992) * 0.15
    return _rgb(lum, (1.0, 0.985, 0.95))


def gen_blocks(size, rng):
    """Cinder-block wall: texture covers 4 courses x 2 blocks."""
    x, y = _coords(size)
    rows, cols = 4, 2
    row_h, col_w = size // rows, size // cols
    row = (y // row_h).astype(np.int32)
    xo = (x + (row % 2) * (col_w // 2)) % size
    block_id = row * cols + (xo // col_w).astype(np.int32)
    variation = rng.uniform(-0.06, 0.06, rows * cols).astype(np.float32)
    lum = 0.74 + (fbm(size, 4, 4, rng) - 0.5) * 0.18
    lum = lum + (value_noise(size, size // 4, size // 4, rng) - 0.5) * 0.12
    lum = lum + variation[block_id]
    mortar = ((y % row_h) < 3) | ((xo % col_w) < 3)
    lum = np.where(mortar, lum * 0.6, lum)
    return _rgb(lum, (1.0, 0.98, 0.94))


def gen_asphalt(size, rng):
    lum = 0.31 + (fbm(size, 4, 4, rng) - 0.5) * 0.10
    lum += (value_noise(size, size // 2, size // 2, rng) - 0.5) * 0.16
    lum += (rng.random((size, size)) > 0.97) * 0.14
    return _rgb(lum, (1.0, 1.0, 1.02))


def gen_dirt(size, rng):
    soil = np.array([0.50, 0.43, 0.33], np.float32)
    dark = np.array([0.36, 0.31, 0.25], np.float32)
    grass = np.array([0.47, 0.47, 0.30], np.float32)
    m_grass = _smoothstep(0.45, 0.68, fbm(size, 6, 4, rng))[..., None]
    m_dark = (_smoothstep(0.5, 0.72, fbm(size, 4, 5, rng)) * 0.7)[..., None]
    col = soil * (1 - m_grass) + grass * m_grass
    col = col * (1 - m_dark) + dark * m_dark
    fine = (value_noise(size, size // 2, size // 2, rng) - 0.5) * 0.16
    col = col * (1.0 + fine[..., None])
    pebbles = (rng.random((size, size)) > 0.988)[..., None]
    col = np.where(pebbles, col * 1.35, col)
    return col * 1.45


def gen_metal(size, rng):
    x, y = _coords(size)
    brushed = value_noise(size, 6, size // 2, rng)
    lum = 0.66 + (fbm(size, 3, 4, rng) - 0.5) * 0.22 + (brushed - 0.5) * 0.08
    seam = (y % (size // 2)) < 2
    lum = np.where(seam, lum * 0.55, lum)
    rivet_y = (y % (size // 2) - 6) ** 2
    rivet_x = ((x % (size // 8)) - size // 16) ** 2
    rivets = (rivet_x + rivet_y) < 5
    lum = np.where(rivets, lum * 1.18, lum)
    grime = fbm(size, 2, 3, rng)
    lum -= np.clip(grime - 0.55, 0, None) * 0.6
    return _rgb(lum)


def gen_corrugated(size, rng):
    x, _ = _coords(size)
    ridge = 0.5 + 0.5 * np.sin(x * (2 * math.pi * 6 / size))
    lum = 0.62 + ridge * 0.2 + (fbm(size, 4, 3, rng) - 0.5) * 0.16
    lum = np.broadcast_to(lum, (size, size)).astype(np.float32)
    streak = value_noise(size, 24, 3, rng) * fbm(size, 3, 3, rng)
    rust = np.clip((streak - 0.30) * 3.5, 0, 1)[..., None]
    base = _rgb(lum)
    rust_col = np.array([0.62, 0.38, 0.24], np.float32) * lum[..., None]
    return base * (1 - rust) + rust_col * rust


def gen_wood(size, rng):
    x, y = _coords(size)
    planks = 4
    plank_h = size // planks
    plank = (y // plank_h).astype(np.int32)
    variation = rng.uniform(-0.08, 0.08, planks).astype(np.float32)
    grain = value_noise(size, 3, size // 3, rng)
    lum = 0.66 + (grain - 0.5) * 0.28 + (fbm(size, 4, 3, rng) - 0.5) * 0.14
    lum = lum + variation[plank]
    gap = (y % plank_h) < 2
    lum = np.where(gap, 0.22, lum)
    return _rgb(np.broadcast_to(lum, (size, size)), (1.0, 0.86, 0.68))


def gen_fabric(size, rng):
    x, y = _coords(size)
    weave = 0.5 + 0.5 * np.sin(x * (2 * math.pi / 4)) * np.sin(y * (2 * math.pi / 4))
    lum = 0.74 + (weave - 0.5) * 0.12 + (fbm(size, 4, 4, rng) - 0.5) * 0.22
    return _rgb(lum, (1.0, 0.97, 0.9))


def gen_bark(size, rng):
    streak = value_noise(size, size // 6, 3, rng)
    lum = 0.55 + (streak - 0.5) * 0.55 + (fbm(size, 4, 3, rng) - 0.5) * 0.2
    lum = np.where(streak < 0.3, lum * 0.6, lum)
    return _rgb(lum, (1.0, 0.9, 0.78))


def gen_foliage(size, rng):
    clumps = fbm(size, 8, 4, rng)
    leaves = value_noise(size, size // 4, size // 4, rng)
    lum = 0.62 + (clumps - 0.5) * 0.6 + (leaves - 0.5) * 0.35
    return _rgb(lum, (0.95, 1.0, 0.85))


def gen_rock(size, rng):
    _, y = _coords(size)
    base = fbm(size, 3, 5, rng)
    strata = 0.5 + 0.5 * np.sin(y * (2 * math.pi * 5 / size) + base * 6.0)
    lum = 0.66 + (base - 0.5) * 0.35 + (strata - 0.5) * 0.12
    lum += (value_noise(size, size // 4, size // 4, rng) - 0.5) * 0.10
    return _rgb(lum, (1.0, 0.98, 0.94))


def gen_hesco(size, rng):
    x, y = _coords(size)
    fabric = gen_fabric(size, rng)
    cell = size // 4
    wire = ((x % cell) < 2) | ((y % cell) < 2)
    return np.where(wire[..., None], fabric * 0.45, fabric)


def gen_chainlink(size, rng):
    x, y = _coords(size)
    period = size // 4
    d1 = (x + y) % period
    d2 = (x - y) % period
    wire = (d1 < 3) | (d2 < 3)
    lum = np.where(wire, 0.85, 0.0).astype(np.float32)
    alpha = wire.astype(np.float32)
    rgb = _rgb(lum)
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


def gen_water(size, rng):
    """Dark, slightly rippled water. Most of the look comes from its normal map and shine."""
    ripples = fbm(size, 8, 4, rng, persistence=0.6)
    lum = 0.55 + (ripples - 0.5) * 0.25
    return _rgb(lum, (0.75, 0.9, 1.0))


# name -> (generator or None, texture size, metres per repeat, flags)
MATERIALS = {
    "concrete": (gen_concrete, 512, 3.0, ()),
    "block": (gen_blocks, 512, 1.6, ()),
    "asphalt": (gen_asphalt, 256, 4.0, ()),
    "dirt": (gen_dirt, 512, 6.0, ()),
    "metal": (gen_metal, 256, 2.0, ()),
    "corrugated": (gen_corrugated, 256, 2.0, ()),
    "wood": (gen_wood, 256, 1.6, ()),
    "fabric": (gen_fabric, 128, 0.8, ()),
    "bark": (gen_bark, 128, 1.2, ()),
    "foliage": (gen_foliage, 128, 1.5, ()),
    "rock": (gen_rock, 256, 2.5, ()),
    "hesco": (gen_hesco, 128, 1.1, ()),
    "plaster": (gen_concrete, 256, 2.5, ()),
    "water": (gen_water, 256, 8.0, ()),
    "beam": (None, 4, 1.0, ("unlit", "additive", "two_sided", "no_shadow")),
    "roof": (gen_blocks, 256, 2.0, ()),
    "stone": (gen_blocks, 256, 2.2, ()),
    "chainlink": (gen_chainlink, 64, 0.2, ("alpha", "two_sided", "no_shadow")),
    "paint": (None, 4, 1.0, ()),
    "emissive": (None, 4, 1.0, ("unlit",)),
}


# name -> (normal-map bump strength, specular brightness, shininess). 0 strength = flat surface.
SURFACE = {
    "concrete": (2.5, 0.10, 12), "block": (5.0, 0.07, 10), "asphalt": (2.0, 0.06, 8),
    "dirt": (3.0, 0.03, 6), "metal": (1.6, 0.55, 45), "corrugated": (5.0, 0.40, 35),
    "wood": (3.5, 0.10, 14), "fabric": (2.5, 0.02, 5), "bark": (6.0, 0.03, 6),
    "foliage": (3.0, 0.10, 12), "rock": (5.0, 0.12, 18), "hesco": (3.5, 0.05, 8),
    "chainlink": (0.0, 0.5, 40), "paint": (0.0, 0.25, 30),
    "water": (6.0, 0.9, 60), "plaster": (2.0, 0.06, 8), "roof": (4.0, 0.12, 14), "stone": (5.0, 0.08, 10),
}


def height_to_normal_map(height, strength):
    """Tangent-space normal map (RGB) from a seamless height field in [0, 1]."""
    # Image row 0 ends up at the TOP of the texture (high V), so +row means -V.
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    nx, ny = -dx * strength, dy * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / length, ny / length, nz / length], axis=-1)
    return n * 0.5 + 0.5


def array_to_texture(name, arr):
    data = (np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    h, w, channels = data.shape
    tex = Texture(name)
    fmt = Texture.F_rgba8 if channels == 4 else Texture.F_rgb8
    tex.setup_2d_texture(w, h, Texture.T_unsigned_byte, fmt)
    # Panda3D stores images bottom row first.
    tex.set_ram_image_as(np.ascontiguousarray(data[::-1]).tobytes(), "RGBA" if channels == 4 else "RGB")
    return tex


class MaterialLibrary:
    def __init__(self, loader, override_dir: Path, anisotropy=4, seed=1977, normal_maps=True):
        self._loader = loader
        self.normal_maps = normal_maps
        self._override_dir = Path(override_dir)
        self._anisotropy = max(1, int(anisotropy))
        self._seed = seed
        self._textures = {}
        self._normals = {}
        self._materials = {}
        self.overridden = []
        self._normal_stage = TextureStage("normal")
        self._normal_stage.set_mode(TextureStage.M_normal)

    @staticmethod
    def uv_scales():
        return {name: spec[2] for name, spec in MATERIALS.items()}

    def texture(self, name) -> Texture:
        if name in self._textures:
            return self._textures[name]
        gen, size, _, _ = MATERIALS.get(name, MATERIALS["paint"])
        tex = self._load_override(name)
        if tex is None:
            if gen is None:
                arr = np.ones((size, size, 3), np.float32)
            else:
                rng = np.random.default_rng(self._seed + sum(map(ord, name)) * 7919)
                arr = gen(size, rng)
            tex = array_to_texture(name, arr)
            strength = SURFACE.get(name, (0.0, 0, 0))[0]
            if strength > 0 and name not in self._normals:
                height = arr[..., :3].mean(axis=-1)
                self._normals[name] = self._finish(array_to_texture(f"{name}_normal",
                                                                    height_to_normal_map(height, strength)))
        self._textures[name] = self._finish(tex)
        override_normal = self._load_override(f"{name}_normal")
        if override_normal is not None:
            self._normals[name] = self._finish(override_normal)
        return tex

    def _finish(self, tex):
        tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)
        tex.set_magfilter(SamplerState.FT_linear)
        tex.set_anisotropic_degree(self._anisotropy)
        tex.set_wrap_u(SamplerState.WM_repeat)
        tex.set_wrap_v(SamplerState.WM_repeat)
        return tex

    def material(self, name):
        """Shine of the surface. Colour still comes from the vertex colours."""
        if name not in self._materials:
            _, spec, shininess = SURFACE.get(name, (0.0, 0.1, 10))
            mat = Material(f"{name}_mat")
            mat.set_specular((spec, spec, spec, 1.0))
            mat.set_shininess(shininess)
            self._materials[name] = mat
        return self._materials[name]

    def _load_override(self, name):
        for ext in TEXTURE_EXTENSIONS:
            path = self._override_dir / f"{name}{ext}"
            if path.is_file():
                try:
                    tex = self._loader.load_texture(Filename.from_os_specific(str(path)))
                    self.overridden.append(path.name)
                    log.info("Using texture override %s", path)
                    return tex
                except Exception as exc:  # a broken image must not crash the game
                    log.error("Could not load texture %s: %s", path, exc)
        return None

    def apply(self, nodepath, name):
        flags = MATERIALS.get(name, MATERIALS["paint"])[3]
        nodepath.set_texture(self.texture(name), 1)
        if "unlit" not in flags:
            nodepath.set_material(self.material(name), 1)
            if self.normal_maps and name in self._normals:
                nodepath.set_texture(self._normal_stage, self._normals[name], 1)
        if "alpha" in flags:
            nodepath.set_transparency(TransparencyAttrib.M_alpha)
        if "two_sided" in flags:
            nodepath.set_two_sided(True)
        if "no_shadow" in flags:
            nodepath.hide(BitMask32.bit(C.SHADOW_CAMERA_MASK_BIT))
        if "unlit" in flags:
            nodepath.set_light_off(1)
        if "additive" in flags:
            from panda3d.core import ColorBlendAttrib
            nodepath.set_transparency(TransparencyAttrib.M_alpha)
            nodepath.set_attrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                      ColorBlendAttrib.O_one))
            nodepath.set_depth_write(False)
            nodepath.set_bin("transparent", 20)
