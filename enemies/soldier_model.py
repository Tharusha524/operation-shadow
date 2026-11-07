"""Procedural, animated soldier model (placeholder for a real rigged character).

Hierarchy (pivots marked *):
  root* (feet, heading)
    pelvis* (hip height)
      torso* (bends for aiming)
        head
        rig  (arms + rifle, aims up/down)
          muzzle (empty node at the rifle tip)
      thigh_L* -> shin_L*      thigh_R* -> shin_R*

Animations: idle breathing, walk/run cycles, crouch, aim pitch, death fall.
Geometry is built once per team and shared between all soldiers (instancing).

To use a real character later, replace build_templates() with a loaded, rigged model
(see assets/models/README.txt) and drive its joints from SoldierModel.update().
"""
from __future__ import annotations

import math

from panda3d.core import NodePath, TextNode

from environments.geometry import MeshBuilder

TEAM_LOOKS = {
    "enemy": {   # Varn Directorate
        "uniform": (0.25, 0.27, 0.29), "vest": (0.14, 0.15, 0.16), "head": (0.07, 0.07, 0.08),
        "helmet": (0.16, 0.17, 0.18), "band": (0.62, 0.1, 0.08), "boots": (0.06, 0.06, 0.06),
    },
    "friendly": {  # Kareth Republic Army
        "uniform": (0.42, 0.43, 0.31), "vest": (0.47, 0.42, 0.31), "head": (0.70, 0.54, 0.43),
        "helmet": (0.36, 0.39, 0.26), "band": (0.22, 0.42, 0.75), "boots": (0.18, 0.14, 0.1),
    },
}
RIFLE = (0.14, 0.15, 0.16)
HIP_Z = 0.95
_templates = {}


def _build_part(materials, name, builder):
    mb = MeshBuilder(materials.uv_scales())
    builder(mb)
    return mb.build(NodePath(name), materials, name=name)


def build_templates(materials, team):
    if team in _templates:
        return _templates[team]
    c = TEAM_LOOKS[team]
    t = {}

    def pelvis(mb):
        mb.box("fabric", 0, 0, -0.1, 0.34, 0.21, 0.2, c["uniform"])
        mb.box("fabric", 0, 0, 0.06, 0.36, 0.23, 0.05, (0.1, 0.1, 0.1))           # belt

    def torso(mb):
        mb.box("fabric", 0, 0, 0.0, 0.38, 0.22, 0.52, c["uniform"])
        mb.box("fabric", 0, 0.0, 0.12, 0.42, 0.28, 0.36, c["vest"])
        for x in (-0.12, 0.0, 0.12):
            mb.box("fabric", x, 0.15, 0.14, 0.09, 0.05, 0.12, c["vest"])           # magazine pouches
        mb.box("fabric", 0, -0.18, 0.12, 0.3, 0.12, 0.34, c["vest"])               # backpack
        mb.cylinder("fabric", 0, 0, 0.5, 0.055, 0.08, c["head"], segments=8)       # neck
        for sx in (-1, 1):
            mb.ellipsoid("fabric", sx * 0.21, 0, 0.45, 0.075, 0.075, 0.07, c["uniform"], rings=4, segments=8)
        mb.box("paint", -0.215, 0, 0.32, 0.03, 0.11, 0.06, c["band"])              # armband (left)

    def head(mb):
        mb.ellipsoid("paint", 0, 0.0, 0.0, 0.095, 0.105, 0.12, c["head"], rings=6, segments=10)
        mb.ellipsoid("metal", 0, -0.01, 0.05, 0.135, 0.145, 0.105, c["helmet"], rings=5, segments=12)
        mb.box("metal", 0, 0.08, 0.04, 0.17, 0.05, 0.035, (0.05, 0.05, 0.05))     # goggles strap / visor
        if team == "enemy":
            mb.box("paint", 0, 0.09, -0.04, 0.12, 0.03, 0.03, (0.35, 0.05, 0.04))  # red visor slit

    def rig(mb):
        # Arms in an aiming pose holding a rifle along +Y. Origin = shoulder height.
        u = c["uniform"]
        mb.cylinder_between("fabric", (0.21, 0, 0), (0.24, 0.16, -0.24), 0.055, u, segments=6)
        mb.cylinder_between("fabric", (0.24, 0.16, -0.24), (0.09, 0.32, -0.12), 0.048, u, segments=6)
        mb.cylinder_between("fabric", (-0.21, 0, 0), (-0.18, 0.24, -0.22), 0.055, u, segments=6)
        mb.cylinder_between("fabric", (-0.18, 0.24, -0.22), (0.05, 0.52, -0.08), 0.048, u, segments=6)
        for hx, hy, hz in ((0.09, 0.33, -0.12), (0.05, 0.53, -0.08)):
            mb.box("fabric", hx, hy, hz - 0.03, 0.06, 0.08, 0.06, (0.08, 0.08, 0.08))
        mb.box("metal", 0.07, 0.15, -0.07, 0.05, 0.28, 0.06, RIFLE)               # stock + receiver
        mb.box("metal", 0.07, 0.4, -0.06, 0.055, 0.32, 0.07, RIFLE)
        mb.box("metal", 0.07, 0.38, -0.15, 0.035, 0.07, 0.12, RIFLE)              # magazine
        mb.cylinder_between("metal", (0.07, 0.56, -0.03), (0.07, 0.86, -0.03), 0.012, RIFLE, segments=6)

    def thigh(mb):
        mb.cylinder_between("fabric", (0, 0, 0.03), (0, 0, -0.46), 0.088, c["uniform"], segments=8, radius_end=0.07)
        mb.box("fabric", 0, 0.07, -0.42, 0.11, 0.05, 0.1, c["vest"])               # knee pad

    def shin(mb):
        mb.cylinder_between("fabric", (0, 0, 0), (0, 0, -0.38), 0.068, c["uniform"], segments=8, radius_end=0.055)
        mb.box("fabric", 0, 0.035, -0.49, 0.11, 0.27, 0.11, c["boots"])

    for name, fn in (("pelvis", pelvis), ("torso", torso), ("head", head), ("rig", rig),
                     ("thigh", thigh), ("shin", shin)):
        t[name] = _build_part(materials, f"{team}_{name}", fn)
    _templates[team] = t
    return t


class SoldierModel:
    def __init__(self, parent, materials, team, name=None, show_name=False):
        t = build_templates(materials, team)
        self.root = parent.attach_new_node("soldier")
        self.pelvis = self.root.attach_new_node("pelvis")
        self.pelvis.set_z(HIP_Z)
        t["pelvis"].instance_to(self.pelvis)
        self.torso = self.pelvis.attach_new_node("torso")
        self.torso.set_z(0.08)
        t["torso"].instance_to(self.torso)
        self.head = self.torso.attach_new_node("head")
        self.head.set_z(0.66)
        t["head"].instance_to(self.head)
        self.rig = self.torso.attach_new_node("rig")
        self.rig.set_z(0.45)
        t["rig"].instance_to(self.rig)
        self.muzzle = self.rig.attach_new_node("muzzle")
        self.muzzle.set_pos(0.07, 0.88, -0.03)
        self.thighs, self.shins = [], []
        for sx in (-1, 1):
            th = self.pelvis.attach_new_node("thigh")
            th.set_pos(sx * 0.1, 0, -0.08)
            t["thigh"].instance_to(th)
            sh = th.attach_new_node("shin")
            sh.set_z(-0.46)
            t["shin"].instance_to(sh)
            self.thighs.append(th)
            self.shins.append(sh)
        self.label = None
        if show_name and name:
            tn = TextNode("name")
            tn.set_text(name)
            tn.set_align(TextNode.A_center)
            tn.set_text_color(0.55, 0.85, 1.0, 1)
            tn.set_shadow(0.05, 0.05)
            tn.set_shadow_color(0, 0, 0, 1)
            self.label = self.root.attach_new_node(tn)
            self.label.set_z(2.05)
            self.label.set_scale(0.11)
            self.label.set_billboard_point_eye()
            self.label.set_light_off(1)
            self.label.set_shader_off(1)
            self.label.set_depth_test(False)
            self.label.set_depth_write(False)
            self.label.set_bin("fixed", 40)
        self._time = 0.0
        self._crouch = 0.0
        self._death_t = -1.0
        self._death_dir = 1.0
        self._aim_raise = 0.0

    def remove(self):
        self.root.remove_node()

    def reset_pose(self):
        self._death_t = -1.0
        self.root.set_hpr(0, 0, 0)
        self.rig.set_p(0)
        self.head.set_p(0)
        if self.label is not None:
            self.label.show()

    def start_death(self, forward=True):
        self._death_t = 0.0
        self._death_dir = 1.0 if forward else -1.0
        if self.label is not None:
            self.label.hide()

    def update(self, dt, *, x, y, z, heading, move_phase, move_speed, crouch, aim_pitch, aiming, **_extra):
        self._time += dt
        self.root.set_pos(x, y, z)
        self.root.set_h(heading)
        self._crouch += ((1.0 if crouch else 0.0) - self._crouch) * min(1.0, dt * 8.0)
        self._aim_raise += ((1.0 if aiming else 0.0) - self._aim_raise) * min(1.0, dt * 6.0)

        if self._death_t >= 0.0:
            self._death_t = min(1.0, self._death_t + dt / 0.7)
            k = self._death_t
            ease = 1 - (1 - k) ** 3
            self.root.set_p(-88 * ease * self._death_dir)
            self.root.set_z(z + 0.12 * ease)
            self.pelvis.set_z(HIP_Z - 0.25 * ease)
            for i, th in enumerate(self.thighs):
                th.set_p(20 * ease * (1 if i else -0.5))
                self.shins[i].set_p(-30 * ease)
            self.rig.set_p(-50 * ease)
            self.head.set_p(-25 * ease)
            return

        c = self._crouch
        stride = min(1.0, move_speed / 2.0)
        run = min(1.0, max(0.0, (move_speed - 2.5) / 2.0))
        swing = (24 + 18 * run) * stride * (1 - 0.5 * c)
        s = math.sin(move_phase)
        bounce = abs(math.sin(move_phase)) * 0.04 * stride
        breathe = math.sin(self._time * 1.8) * 0.008
        self.pelvis.set_z(HIP_Z - 0.38 * c + bounce + breathe)
        for i, (th, sh) in enumerate(zip(self.thighs, self.shins)):
            side = 1 if i else -1
            leg = s * side
            th.set_p(leg * swing + 60 * c)
            knee = -max(0.0, -leg) * (30 + 35 * run) * stride
            sh.set_p(knee - 100 * c)
        self.torso.set_p(min(25, max(-25, aim_pitch * 0.4)) * self._aim_raise - (8 * run * stride))
        self.torso.set_r(math.sin(move_phase) * 2.0 * stride)
        rig_pitch = aim_pitch * 0.6 * self._aim_raise - 35 * (1 - self._aim_raise)
        self.rig.set_p(rig_pitch)
        self.rig.set_h(-25 * (1 - self._aim_raise))
        self.head.set_p(aim_pitch * 0.3)
