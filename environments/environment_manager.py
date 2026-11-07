"""Builds a level: terrain, props, colliders, sky, sun, shadows and fog."""
from __future__ import annotations

import logging
import math
import random
import time

import numpy as np
from panda3d.core import (AmbientLight, BitMask32, CullFaceAttrib, DirectionalLight, Filename, Fog, LPoint3, Texture,
                          TextureStage,
                          RenderState)

from config import constants as C
from config.settings import SHADOW_FILM_SIZES, SHADOW_MAP_SIZES
from core.paths import ASSETS_DIR
from environments.geometry import MeshBuilder
from environments.materials import MaterialLibrary, fbm
from environments.props import PROP_BUILDERS
from environments.sky import build_sky, scroll_clouds

log = logging.getLogger(__name__)

MODEL_EXTENSIONS = (".bam", ".egg", ".egg.pz")

# How many copies of each real (downloaded) model a map may use, per graphics quality.
# Beyond the budget the procedural version is used, which keeps laptops fast.
MODEL_BUDGETS = {
    "low": {},
    "medium": {"barrel": 40, "road_barrier": 10, "street_lamp": 12, "boulder": 4, "ammo_box": 12, "jerrycan": 12},
    "high": {"barrel": 70, "road_barrier": 18, "street_lamp": 18, "boulder": 8, "ammo_box": 24, "jerrycan": 24},
}


class EnvironmentManager:
    def __init__(self, base, collision_world, settings):
        self.base = base
        self.world = collision_world
        self.settings = settings
        self.root = base.render.attach_new_node("environment")
        self.materials = MaterialLibrary(base.loader, ASSETS_DIR / "textures",
                                         anisotropy=settings.preset["anisotropy"],
                                         normal_maps=settings.graphics_quality != "low")
        self.map = None
        self.sky = None
        self.sun_np = None
        self._lights = []
        self._shadow_texel = 0.0
        self.stats = {}
        self.dynamic = {}          # prop id -> {"node": NodePath, "colliders": [...], "bounds": rect, "destroyed": bool}
        self.atmosphere = None

    # ------------------------------------------------------------------ loading
    def load(self, map_data, atmosphere_override=None):
        self.unload()
        started = time.perf_counter()
        self.map = map_data
        builder = MeshBuilder(self.materials.uv_scales())
        budget = {k: v for k, v in MODEL_BUDGETS[self.settings.graphics_quality].items()
                  if (ASSETS_DIR / "models" / f"{k}.bam").is_file()}
        builder.model_budget = budget
        self._build_terrain(builder, map_data)
        skipped = 0
        model_props = 0
        for i, prop in enumerate(map_data.props):
            fn = PROP_BUILDERS.get(prop.type)
            if fn is None:
                log.warning("Unknown prop type '%s' - skipped", prop.type)
                skipped += 1
                continue
            rng = random.Random(map_data.seed * 1000003 + i)
            model_path = self._model_override(prop.type)
            # Props with an id get their own builder so a mission can destroy/restore them.
            target = MeshBuilder(self.materials.uv_scales()) if prop.id else builder
            if target is not builder:
                target.model_budget = builder.model_budget
            params = prop.params
            try:
                with target.place(prop.x, prop.y, prop.z, prop.heading):
                    if model_path is not None:
                        with target.colliders_only():
                            fn(target, rng, **params)
                        self._place_model(model_path, prop)
                        model_props += 1
                    else:
                        fn(target, rng, **params)
            except TypeError as exc:
                log.error("Prop '%s' at (%.1f, %.1f) has bad params: %s", prop.type, prop.x, prop.y, exc)
                skipped += 1
                continue
            if prop.id:
                for c in target.colliders:
                    c.tag = prop.id
                node = target.build(self.root, self.materials, name=f"prop_{prop.id}")
                xs = [c.bounds[0] for c in target.colliders] + [c.bounds[2] for c in target.colliders]
                ys = [c.bounds[1] for c in target.colliders] + [c.bounds[3] for c in target.colliders]
                bounds = (min(xs), min(ys), max(xs), max(ys)) if xs else (prop.x, prop.y, prop.x, prop.y)
                self.dynamic[prop.id] = {"node": node, "colliders": list(target.colliders), "bounds": bounds,
                                         "destroyed": False, "pos": (prop.x, prop.y, prop.z),
                                         "start_hidden": prop.hidden}
                self.world.add_many(target.colliders)
                if self.dynamic[prop.id]["start_hidden"]:
                    self.destroy_prop(prop.id)
        builder.build(self.root, self.materials)
        self.world.add_many(builder.colliders)
        placed_models = self._place_model_instances(builder.model_requests)
        atm = dict(map_data.atmosphere)
        atm.update(atmosphere_override or {})
        self.atmosphere = atm
        self._setup_atmosphere(atm)
        self.stats = {
            "props": len(map_data.props) - skipped,
            "colliders": len(builder.colliders),
            "triangles": builder.triangle_count,
            "model_overrides": model_props,
            "real_models": placed_models,
            "load_seconds": time.perf_counter() - started,
        }
        log.info("Loaded map '%s': %s", map_data.name, self.stats)

    def unload(self):
        self._clear_atmosphere()
        self.root.get_children().detach()
        self.dynamic.clear()
        self.world.clear()
        self.map = None

    def _clear_atmosphere(self):
        for light_np in self._lights:
            self.base.render.clear_light(light_np)
            light_np.remove_node()
        self._lights.clear()
        if self.sky is not None:
            self.sky.remove_node()
            self.sky = None
        self.sun_np = None

    def refresh_lighting(self):
        """Rebuild lights/shadows with the current settings (after the shadow option changes)."""
        if self.map is not None:
            self._clear_atmosphere()
            self._setup_atmosphere(self.atmosphere)

    def set_atmosphere(self, override=None):
        """Re-light the already loaded map (e.g. dawn for a mission, default for the menu)."""
        atm = dict(self.map.atmosphere)
        atm.update(override or {})
        self.atmosphere = atm
        self._clear_atmosphere()
        self._setup_atmosphere(atm)

    # ------------------------------------------------------------------ destructible props
    def destroy_prop(self, prop_id):
        entry = self.dynamic.get(prop_id)
        if entry is None or entry["destroyed"]:
            return None
        entry["node"].hide()
        self.world.remove_tag(prop_id)
        entry["destroyed"] = True
        return entry["bounds"]

    def restore_prop(self, prop_id):
        entry = self.dynamic.get(prop_id)
        if entry is None or not entry["destroyed"]:
            return None
        entry["node"].show()
        self.world.add_many(entry["colliders"])
        entry["destroyed"] = False
        return entry["bounds"]

    def reset_props(self):
        """Put every mission-changeable prop back to its starting state.

        Returns the areas that changed (for the navigation grid). Props marked "hidden" in the map
        (e.g. bridge ruins that appear after an explosion) go back to being hidden.
        """
        changed = []
        for pid, entry in self.dynamic.items():
            b = self.destroy_prop(pid) if entry.get("start_hidden") else self.restore_prop(pid)
            if b:
                changed.append(b)
        return changed

    def update_water(self, dt):
        """Slowly scroll the water texture so the river flows."""
        node = self.root.find("**/chunk_water*")
        if node.is_empty():
            return
        from panda3d.core import TextureStage
        self._water_t = getattr(self, "_water_t", 0.0) + dt
        for stage in node.find_all_texture_stages():
            node.set_tex_offset(stage, self._water_t * 0.03, self._water_t * 0.012)

    def _build_terrain(self, builder, map_data):
        terrain = map_data.terrain
        size = float(terrain["size"])
        div = int(terrain["divisions"])
        play = float(terrain["play_area"])
        rng = np.random.default_rng(map_data.seed)
        patches = fbm(div + 1, 6, 4, rng)
        grass = fbm(div + 1, 10, 3, rng)
        worn = tuple(terrain.get("worn_color", (0.95, 0.90, 0.82)))
        green = tuple(terrain.get("grass_color", (0.86, 0.92, 0.70)))
        dark = tuple(terrain.get("dark_color", (0.74, 0.71, 0.64)))
        colors = []
        step = size / div
        for j in range(div + 1):
            row = []
            y = -size / 2 + j * step
            for i in range(div + 1):
                x = -size / 2 + i * step
                inside = max(abs(x), abs(y)) < play
                g = float(grass[j, i]) * (0.35 if inside else 1.0)
                d = float(patches[j, i])
                c = tuple(worn[k] * (1 - g) + green[k] * g for k in range(3))
                t = max(0.0, d - 0.5) * 1.4
                row.append(tuple(c[k] * (1 - t) + dark[k] * t for k in range(3)) + (1.0,))
            colors.append(row)
        with builder.chunk("terrain"):
            builder.terrain("dirt", size, div, colors, holes=[tuple(h) for h in terrain.get("holes", [])])
        # A map with a river sets "floor_z" low and lists "land" rectangles: solid ground (top at z = 0)
        # everywhere except the river channel, so bullets, rockets and the player can go below z = 0 there.
        self.world.floor_z = float(terrain.get("floor_z", 0.0))
        for x0, y0, x1, y1 in terrain.get("land", []):
            builder.collider_box((x0 + x1) / 2, (y0 + y1) / 2, -30.0, x1 - x0, y1 - y0, 30.0, tag="ground")
        water = terrain.get("water")
        if water:
            x0, y0, x1, y1 = water["rect"]
            z = float(water.get("z", -1.5))
            with builder.chunk("water"):
                builder.flat_rect("water", x0, y0, x1, y1, z, tuple(water.get("color", (0.35, 0.45, 0.5))),
                                  world_uv=True)
                builder.flat_rect("paint", x0, y0, x1, y1, z - 5.0, (0.05, 0.06, 0.05))      # river bed

    def _load_asset_model(self, key):
        path = ASSETS_DIR / "models" / f"{key}.bam"
        try:
            model = self.base.loader.load_model(Filename.from_os_specific(str(path)))
        except Exception as exc:
            log.error("Could not load model %s: %s", path, exc)
            return None
        # Keep only the colour texture: glTF normal / metal-roughness / emission layers need vertex data
        # (binormals) that Panda3D's automatic shader expects but the files don't contain.
        for stage in model.find_all_texture_stages():
            if stage.get_mode() not in (TextureStage.M_modulate, TextureStage.M_replace):
                model.set_texture_off(stage, 1)
        # glTF colour textures are marked sRGB; this game works in display space, so read them as-is.
        for tex in model.find_all_textures():
            fmt = tex.get_format()
            if fmt in (Texture.F_srgb, Texture.F_srgb_alpha):
                tex.set_format(Texture.F_rgba8 if fmt == Texture.F_srgb_alpha else Texture.F_rgb8)
            tex.set_anisotropic_degree(self.settings.preset["anisotropy"])
        return model

    def _place_model_instances(self, requests):
        """Copy each requested real model into the level and merge copies for fast drawing."""
        by_key = {}
        for key, x, y, z, heading, scale in requests:
            by_key.setdefault(key, []).append((x, y, z, heading, scale))
        total = 0
        for key, items in by_key.items():
            model = self._load_asset_model(key)
            if model is None:
                continue
            group = self.root.attach_new_node(f"models_{key}")
            for x, y, z, heading, scale in items:
                copy = model.copy_to(group)
                copy.set_pos(x, y, z)
                copy.set_h(heading)
                copy.set_scale(scale)
            group.flatten_strong()
            total += len(items)
        return total

    def _model_override(self, prop_type):
        folder = ASSETS_DIR / "models"
        for ext in MODEL_EXTENSIONS:
            path = folder / f"{prop_type}{ext}"
            if path.is_file():
                return path
        return None

    def _place_model(self, path, prop):
        try:
            model = self.base.loader.load_model(Filename.from_os_specific(str(path)))
        except Exception as exc:
            log.error("Could not load model %s: %s", path, exc)
            return
        model.reparent_to(self.root)
        model.set_pos(prop.x, prop.y, prop.z)
        model.set_h(prop.heading)
        model.set_scale(float(prop.params.get("model_scale", 1.0)))

    # ------------------------------------------------------------------ lighting & atmosphere
    def _setup_atmosphere(self, atm):
        render = self.base.render
        preset = self.settings.preset

        ambient = AmbientLight("ambient")
        ambient.set_color((*atm["ambient_color"], 1.0))
        self._lights.append(render.attach_new_node(ambient))

        sun = DirectionalLight("sun")
        sun.set_color((*atm["sun_color"], 1.0))
        sun_np = render.attach_new_node(sun)
        sun_np.set_hpr(atm["sun_heading"], atm["sun_pitch"], 0)
        self._lights.append(sun_np)
        self.sun_np = sun_np

        fill = DirectionalLight("sky_fill")
        fill.set_color((*atm["fill_color"], 1.0))
        fill_np = render.attach_new_node(fill)
        fill_np.set_hpr(atm["sun_heading"] + 180, -50, 0)
        self._lights.append(fill_np)

        size = SHADOW_MAP_SIZES[self.settings.shadow_quality]
        if size:
            film = SHADOW_FILM_SIZES[self.settings.shadow_quality]
            sun.set_shadow_caster(True, size, size)
            sun.set_camera_mask(BitMask32.bit(C.SHADOW_CAMERA_MASK_BIT))
            lens = sun.get_lens()
            lens.set_film_size(film, film)
            lens.set_near_far(1.0, C.SUN_SHADOW_DISTANCE * 2.0)
            # Render back faces into the shadow map: removes most "shadow acne".
            sun.set_initial_state(RenderState.make(CullFaceAttrib.make_reverse()))
            self._shadow_texel = film / size
        else:
            self._shadow_texel = 0.0

        for light_np in self._lights:
            render.set_light(light_np)

        fog = Fog("fog")
        fog.set_color(*atm["fog_color"])
        fog.set_exp_density(float(atm["fog_density"]))
        fog.set_mode(Fog.M_exponential_squared)
        render.set_fog(fog)
        self.base.set_background_color(*atm["fog_color"], 1.0)

        direction = sun_np.get_quat(render).get_forward()
        sun = atm["sun_color"]
        peak = max(sun) or 1.0
        cloud_color = tuple(0.55 + 0.45 * c / peak for c in sun)          # clouds pick up the sunlight colour
        self.sky = build_sky(self.base, atm["sky_zenith"], atm["sky_horizon"],
                             (direction.x, direction.y, direction.z),
                             radius=min(250.0, preset["view_distance"] * 0.7),
                             clouds=float(atm.get("clouds", 0.45)), cloud_color=cloud_color)

    def update(self, focus, dt=0.0):
        """Keep the shadow camera centred on the player (snapped to texels to avoid shimmering)."""
        scroll_clouds(self.sky, dt)
        if self.sun_np is None or self._shadow_texel <= 0.0:
            return
        q = self.sun_np.get_quat(self.base.render)
        fwd, right, up = q.get_forward(), q.get_right(), q.get_up()
        target = LPoint3(focus)
        texel = self._shadow_texel
        r = math.floor(target.dot(right) / texel + 0.5) * texel
        u = math.floor(target.dot(up) / texel + 0.5) * texel
        f = target.dot(fwd)
        centre = right * r + up * u + fwd * f
        self.sun_np.set_pos(LPoint3(centre) - fwd * C.SUN_SHADOW_DISTANCE)
