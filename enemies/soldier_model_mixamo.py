"""Realistic soldiers: rigged Mixamo characters with motion-captured animations.

Same interface as enemies/soldier_model.SoldierModel (the old block soldier), so the rest of the game
does not care which one is used. Models come from tools/convert_soldiers.py:
  assets/models/soldier_enemy.bam   (enemies)
  assets/models/soldier_friend.bam  (the player's squad and allies)

The rifle sits in the right hand and points at the left hand while both hands hold it, so it follows
every animation without hand-tuned offsets.
"""
from __future__ import annotations

import math

from direct.actor.Actor import Actor
from panda3d.core import Filename, LVector3, NodePath, TextNode

from core.paths import ASSETS_DIR

MODEL_FILES = {"enemy": "soldier_enemy.bam", "friendly": "soldier_friend.bam"}
FADE = 0.18                       # seconds to blend from one animation to the next
LOOPS = ("idle", "aim", "fire", "walk", "run", "crouch_idle", "crouch_walk", "walk_back", "strafe_left",
         "strafe_right")
_gun_template = None


def available(team):
    return (ASSETS_DIR / "models" / MODEL_FILES["enemy" if team == "enemy" else "friendly"]).is_file()


def _rifle(materials):
    """A small NPC rifle (grip at the origin, barrel along +Y)."""
    global _gun_template
    if _gun_template is None:
        from environments.geometry import MeshBuilder
        mb = MeshBuilder(materials.uv_scales())
        metal, poly = (0.12, 0.12, 0.13), (0.07, 0.07, 0.07)
        mb.box("metal", 0, 0.09, 0.07, 0.045, 0.30, 0.07, metal)                    # receiver
        mb.box("metal", 0, 0.34, 0.08, 0.05, 0.22, 0.055, poly)                     # handguard
        mb.cylinder_between("metal", (0, 0.45, 0.105), (0, 0.72, 0.105), 0.01, metal, segments=6)
        mb.box("metal", 0, 0.16, -0.06, 0.03, 0.075, 0.13, metal)                   # magazine
        mb.box("metal", 0, 0.0, -0.03, 0.03, 0.045, 0.1, poly)                      # grip
        mb.box("metal", 0, -0.17, 0.06, 0.04, 0.22, 0.075, poly)                    # stock
        mb.box("metal", 0, 0.1, 0.11, 0.025, 0.06, 0.03, metal)                     # sight
        _gun_template = mb.build(NodePath("npc_rifle"), materials, name="npc_rifle")
    return _gun_template


class MixamoSoldierModel:
    def __init__(self, parent, materials, team, name=None, show_name=False):
        key = "enemy" if team == "enemy" else "friendly"
        path = Filename.from_os_specific(str(ASSETS_DIR / "models" / MODEL_FILES[key]))
        self.root = parent.attach_new_node("soldier")
        self.actor = Actor(path)
        self.actor.reparent_to(self.root)
        self.actor.set_h(180)                       # Mixamo characters face -Y; the game uses +Y
        boost = 1.35 if key == "enemy" else 1.15         # a little brighter, so dark uniforms read in shade
        self.actor.set_color_scale(boost, boost, boost, 1.0)
        self.actor.enableBlend()
        self.actor.setLODAnimation(80, 30, 0.15)    # far soldiers animate less often (cheaper)
        self.anims = set(self.actor.getAnimNames())
        self._weights = {}
        self._current = None
        self._dead = False
        self._last_shots = 0
        self._fire_t = 0.0
        self.right_hand = self.actor.exposeJoint(None, "modelRoot", "mixamorig:RightHand")
        self.left_hand = self.actor.exposeJoint(None, "modelRoot", "mixamorig:LeftHand")
        self.gun = self.root.attach_new_node("gun")
        _rifle(materials).instance_to(self.gun)
        self.muzzle = self.gun.attach_new_node("muzzle")
        self.muzzle.set_pos(0, 0.74, 0.105)
        self._gun_rel = None                        # gun transform relative to the right hand (fallback)
        self.label = None
        if show_name and name:
            tn = TextNode("name")
            tn.set_text(name)
            tn.set_align(TextNode.A_center)
            tn.set_text_color(0.55, 0.85, 1.0, 1)
            tn.set_shadow(0.05, 0.05)
            tn.set_shadow_color(0, 0, 0, 1)
            self.label = self.root.attach_new_node(tn)
            self.label.set_z(2.1)
            self.label.set_scale(0.11)
            self.label.set_billboard_point_eye()
            self.label.set_light_off(1)
            self.label.set_shader_off(1)
            self.label.set_depth_test(False)
            self.label.set_depth_write(False)
            self.label.set_bin("fixed", 40)
        self._play("idle", fade=False)

    # ------------------------------------------------------------------ animation blending
    def _play(self, anim, fade=True):
        if anim not in self.anims:
            anim = "idle"
        if anim == self._current:
            return
        self._current = anim
        if anim not in self._weights:
            self._weights[anim] = 0.0
        if anim == "death":
            self.actor.play("death")
        elif not self.actor.getAnimControl(anim).isPlaying():
            self.actor.loop(anim)
        if not fade:
            for a in list(self._weights):
                self._weights[a] = 1.0 if a == anim else 0.0
            self._apply_weights()

    def _apply_weights(self):
        total = sum(self._weights.values()) or 1.0
        for a, w in list(self._weights.items()):
            self.actor.setControlEffect(a, w / total)
            if w <= 0.0 and a != self._current:
                self.actor.stop(a)
                del self._weights[a]

    def _blend(self, dt):
        step = dt / FADE
        for a in list(self._weights):
            target = 1.0 if a == self._current else 0.0
            w = self._weights[a]
            self._weights[a] = min(target, w + step) if target > w else max(target, w - step)
        self._apply_weights()

    # ------------------------------------------------------------------ interface used by Soldier
    def remove(self):
        self.actor.cleanup()
        self.root.remove_node()

    def reset_pose(self):
        self._dead = False
        self._current = None
        self._weights.clear()
        self.actor.stop()
        self._play("idle", fade=False)
        if self.label is not None:
            self.label.show()

    def start_death(self, forward=True):
        self._dead = True
        self._play("death", fade=False)
        if self.label is not None:
            self.label.hide()

    def choose(self, move_speed, crouch, aiming, firing, reloading, vel, heading):
        """Pick the animation for what the soldier is doing."""
        if crouch:
            return "crouch_walk" if move_speed > 0.4 else "crouch_idle"
        if move_speed > 0.4:
            if move_speed > 3.6:
                return "run"
            fx, fy = -math.sin(math.radians(heading)), math.cos(math.radians(heading))
            vx, vy = vel
            forward = (vx * fx + vy * fy) / max(move_speed, 1e-3)
            side = (vx * fy - vy * fx) / max(move_speed, 1e-3)          # + = to the soldier's right
            if forward < -0.6:
                return "walk_back"
            if abs(side) > 0.75:
                return "strafe_right" if side > 0 else "strafe_left"
            return "walk"
        if reloading:
            return "reload"
        if firing:
            return "fire"
        return "aim" if aiming else "idle"

    def update(self, dt, *, x, y, z, heading, move_phase, move_speed, crouch, aim_pitch, aiming,
               reloading=False, shots=0, vel=(0.0, 0.0)):
        self.root.set_pos(x, y, z)
        self.root.set_h(heading)
        if not self._dead:
            if shots != self._last_shots:
                self._last_shots = shots
                self._fire_t = 0.5
            self._fire_t = max(0.0, self._fire_t - dt)
            anim = self.choose(move_speed, crouch, aiming, self._fire_t > 0.0, reloading, vel, heading)
            self._play(anim)
            if anim in ("walk", "run", "crouch_walk", "walk_back", "strafe_left", "strafe_right"):
                base = {"walk": 1.4, "run": 3.8, "crouch_walk": 1.2}.get(anim, 1.3)
                self.actor.setPlayRate(max(0.6, min(1.6, move_speed / base)), anim)
        self._blend(dt)
        self._place_gun()

    def _place_gun(self):
        """Grip in the right hand, barrel towards the left hand while both hands are on the rifle."""
        r = self.right_hand.get_pos(self.root)
        lh = self.left_hand.get_pos(self.root)
        span = (lh - r).length()
        if 0.15 < span < 0.75 and not self._dead and self._current not in ("reload", "throw"):
            self.gun.set_pos(r)
            self.gun.look_at(lh, LVector3(0, 0, 1))
            self._gun_rel = self.gun.get_transform(self.right_hand)
        elif self._gun_rel is not None:
            self.gun.set_transform(self.right_hand, self._gun_rel)
        else:
            self.gun.set_pos(r)
            self.gun.set_hpr(0, 0, 0)
