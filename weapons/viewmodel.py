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


def _arms(mb, right_hand, left_hand):
    """Gloved hands + sleeves reaching back toward the bottom corners of the screen."""
    rx, ry, rz = right_hand
    mb.box("fabric", rx, ry, rz - 0.035, 0.05, 0.07, 0.07, GLOVE)
    mb.cylinder_between("fabric", (rx + 0.005, ry - 0.03, rz - 0.03), (rx + 0.09, ry - 0.36, rz - 0.22), 0.034,
                        SLEEVE, segments=8, radius_end=0.045)
    if left_hand is None:
        return
    lx, ly, lz = left_hand
    mb.box("fabric", lx, ly, lz - 0.035, 0.06, 0.08, 0.06, GLOVE)
    mb.cylinder_between("fabric", (lx - 0.01, ly - 0.03, lz - 0.03), (lx - 0.16, ly - 0.42, lz - 0.2), 0.034,
                        SLEEVE, segments=8, radius_end=0.045)


def build_rifle(mb):
    mb.box("metal", 0, 0.05, -0.095, 0.045, 0.30, 0.07, GUNMETAL)                    # receiver
    mb.box("metal", 0, 0.30, -0.09, 0.052, 0.22, 0.06, POLYMER)                      # handguard
    for i in range(5):
        mb.box("metal", 0, 0.22 + i * 0.04, -0.06, 0.054, 0.012, 0.004, SIGHT)      # rail ribs
    mb.cylinder_between("metal", (0, 0.41, -0.068), (0, 0.66, -0.068), 0.0095, GUNMETAL, segments=8)
    mb.cylinder_between("metal", (0, 0.62, -0.068), (0, 0.68, -0.068), 0.015, SIGHT, segments=8, caps=True)
    mb.box("metal", 0, 0.12, -0.215, 0.03, 0.075, 0.13, GUNMETAL)                    # magazine
    mb.box("metal", 0, -0.04, -0.19, 0.03, 0.045, 0.1, POLYMER)                      # grip
    mb.box("metal", 0, -0.21, -0.11, 0.04, 0.2, 0.075, POLYMER)                      # stock
    mb.box("metal", 0, -0.32, -0.12, 0.045, 0.02, 0.1, SIGHT)
    mb.box("metal", 0, 0.05, -0.06, 0.02, 0.24, 0.01, SIGHT)                          # top rail
    _reflex_sight(mb, 0.08)
    _arms(mb, (0.0, -0.04, -0.15), (0.0, 0.30, -0.12))
    return (0.0, 0.69, -0.068)


def _reflex_sight(mb, y):
    """Compact red-dot sight: an open frame around the sight line with a glowing dot."""
    mb.box("metal", 0, y, -0.05, 0.03, 0.05, 0.022, GUNMETAL)                         # mount
    half, t = 0.02, 0.0035
    mb.box("metal", 0, y + 0.012, -half - t, 2 * half + 2 * t, 0.012, t, GUNMETAL)  # bottom
    mb.box("metal", 0, y + 0.012, half, 2 * half + 2 * t, 0.012, t, GUNMETAL)       # top
    for sx in (-1, 1):
        mb.box("metal", sx * (half + t / 2), y + 0.012, -half, t, 0.012, 2 * half, GUNMETAL)
    mb.ellipsoid("emissive", 0, y + 0.02, 0, 0.0011, 0.0005, 0.0011, RED_DOT, rings=3, segments=6)


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
    mb.box("metal", 0, 0.02, -0.09, 0.048, 0.24, 0.07, GUNMETAL)
    mb.cylinder_between("metal", (0, 0.13, -0.068), (0, 0.66, -0.068), 0.013, GUNMETAL, segments=8)
    mb.cylinder_between("metal", (0, 0.13, -0.098), (0, 0.6, -0.098), 0.012, GUNMETAL, segments=8, caps=True)
    mb.box("metal", 0, -0.04, -0.17, 0.03, 0.045, 0.1, WOOD)
    mb.box("wood", 0, -0.22, -0.12, 0.045, 0.26, 0.08, WOOD)
    mb.ellipsoid("metal", 0, 0.655, -0.052, 0.004, 0.004, 0.004, (0.9, 0.85, 0.6), rings=3, segments=5)
    mb.box("metal", 0, -0.02, -0.052, 0.022, 0.012, 0.01, SIGHT)
    _arms(mb, (0.0, -0.04, -0.14), None)        # left hand is on the pump (see build_pump)
    return (0.0, 0.67, -0.068)


def build_pump(mb):
    """Separate node so the forend can slide when pumping."""
    mb.box("wood", 0, 0.36, -0.115, 0.05, 0.16, 0.05, WOOD)
    mb.box("fabric", 0, 0.36, -0.15, 0.06, 0.08, 0.06, GLOVE)
    mb.cylinder_between("fabric", (-0.01, 0.33, -0.14), (-0.16, -0.06, -0.33), 0.034, SLEEVE, segments=8, radius_end=0.045)


def build_launcher(mb, gun=True):
    """Shoulder-fired rocket launcher: long tube, optic and grip."""
    tube = (0.30, 0.33, 0.22)
    mb.cylinder_between("metal", (0, -0.45, -0.06), (0, 0.55, -0.06), 0.058, tube, segments=14, caps=True)
    mb.cylinder_between("metal", (0, 0.5, -0.06), (0, 0.6, -0.06), 0.068, GUNMETAL, segments=14, caps=True)
    mb.cylinder_between("metal", (0, -0.5, -0.06), (0, -0.42, -0.06), 0.066, GUNMETAL, segments=14, caps=True)
    mb.box("metal", 0, 0.05, -0.12, 0.03, 0.06, 0.1, GUNMETAL)                       # grip
    mb.box("metal", 0, 0.25, -0.13, 0.03, 0.05, 0.08, GUNMETAL)                      # front grip
    mb.box("metal", 0.06, 0.0, -0.01, 0.03, 0.1, 0.04, GUNMETAL)                     # optic
    mb.box("paint", 0, 0.3, -0.005, 0.004, 0.004, 0.012, RED_DOT)                    # front sight blade
    _arms(mb, (0.0, 0.05, -0.12), (0.0, 0.25, -0.12))
    return (0.0, 0.62, -0.06)


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
    "rifle":   ((0.15, 0.40, -0.115), (0.0, 0.26, 0.0)),
    "pistol":  ((0.12, 0.34, -0.07), (0.0, 0.34, 0.0)),
    "sniper":  ((0.15, 0.40, -0.12), (0.0, 0.18, 0.0)),
    "shotgun": ((0.15, 0.40, -0.115), (0.0, 0.30, 0.0)),
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
