"""Recon drone: the player flies a small camera drone and tags enemies for the squad.

While the drone is up, the player's body stays where it is (protected), the view switches to
a thermal-style camera, and left click tags the target under the reticle. Tagged enemies keep
a red marker on the HUD until they die.
"""
from __future__ import annotations

import math

from player.camera import LookAngles

DRONE_GRADING = {"exposure": 3.6, "saturation": 0.0, "contrast": 1.3, "tint": [0.92, 1.0, 0.96], "grain": 0.07,
                 "vignette": 0.75, "lift": 0.03, "bloom": 0.7, "bloom_threshold": 0.7}
TAG_RANGE = 260.0


def angle_to(origin, forward, point):
    d = [point[i] - origin[i] for i in range(3)]
    dist = math.sqrt(sum(v * v for v in d)) or 1e-6
    cosang = sum(d[i] * forward[i] for i in range(3)) / dist
    return math.degrees(math.acos(max(-1.0, min(1.0, cosang)))), dist


def pick_target(origin, forward, candidates, line_of_sight, max_range=TAG_RANGE):
    """Return the candidate closest to the reticle (needs a clear line of sight), or None."""
    best, best_score = None, None
    for c in candidates:
        if not c.alive:
            continue
        ang, dist = angle_to(origin, forward, c.center())
        if dist > max_range:
            continue
        allowed = max(1.5, math.degrees(math.atan2(1.6, dist)))
        if ang > allowed:
            continue
        if not line_of_sight(origin, c.center()):
            continue
        score = ang / allowed
        if best_score is None or score < best_score:
            best, best_score = c, score
    return best


class DroneController:
    SPEED = 14.0
    VERTICAL_SPEED = 7.0

    def __init__(self, game, pos, heading=0.0, max_range=200.0, min_alt=10.0, max_alt=55.0):
        self.game = game
        self.origin = (pos[0], pos[1])
        self.pos = [float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 25.0]
        self.look = LookAngles(heading, -25.0)
        self.max_range = max_range
        self.min_alt, self.max_alt = min_alt, max_alt
        self.vel = [0.0, 0.0, 0.0]
        self.time = 0.0
        g = game
        g.player.control_enabled = False
        self._was_invulnerable = g.player.invulnerable
        g.player.invulnerable = True                  # the body waits safely while the drone is up
        g.weapons.viewmodel.set_visible(False)
        g.player.camera.detach_for_cinematic(fov=70.0)
        g.postfx.set_override(DRONE_GRADING)
        self._thermal(True)
        g.audio.start_loop("drone_loop", 0.25)
        self._sync()

    # ------------------------------------------------------------------ helpers
    def _thermal(self, on):
        for s in self.game.soldiers.soldiers:
            m = s.model
            if m is None:
                continue
            if on and s.team == "enemy":
                m.root.set_light_off(100)                 # thermal: bodies glow white-hot
                m.root.set_color_scale(4.0, 4.0, 4.0, 1.0, 100)
            else:
                m.root.clear_light()
                m.root.clear_color_scale()

    def forward(self):
        h, p = math.radians(self.look.yaw), math.radians(self.look.pitch)
        return -math.sin(h) * math.cos(p), math.cos(h) * math.cos(p), math.sin(p)

    def _sync(self):
        cam = self.game.camera
        cam.set_pos(*self.pos)
        cam.set_hpr(self.look.yaw, self.look.pitch, 0.0)

    # ------------------------------------------------------------------ update
    def update(self, dt, inp):
        g = self.game
        self.time += dt
        if int(self.time * 2) != int((self.time - dt) * 2):
            self._thermal(True)                       # enemies that arrived since the last check
        self.look.apply_mouse(inp.mouse_dx, inp.mouse_dy, g.settings.mouse_sensitivity, g.settings.invert_mouse_y)
        self.look.pitch = max(-85.0, min(10.0, self.look.pitch))
        fwd = inp.axis("move_forward", "move_backward")
        right = inp.axis("move_right", "move_left")
        up = (1.0 if inp.is_down("drone_up") else 0.0) - (1.0 if inp.is_down("drone_down") else 0.0)
        h = math.radians(self.look.yaw)
        want = [(-math.sin(h) * fwd + math.cos(h) * right) * self.SPEED,
                (math.cos(h) * fwd + math.sin(h) * right) * self.SPEED,
                up * self.VERTICAL_SPEED]
        for i in range(3):
            self.vel[i] += (want[i] - self.vel[i]) * min(1.0, dt * 3.0)
            self.pos[i] += self.vel[i] * dt
        # Stay inside the control range and altitude band.
        dx, dy = self.pos[0] - self.origin[0], self.pos[1] - self.origin[1]
        d = math.hypot(dx, dy)
        if d > self.max_range:
            self.pos[0] = self.origin[0] + dx / d * self.max_range
            self.pos[1] = self.origin[1] + dy / d * self.max_range
        ground = g.collision_world.ground_height(self.pos[0], self.pos[1], 0.5, 200.0)
        self.pos[2] = max(max(ground, 0.0) + self.min_alt, min(self.max_alt, self.pos[2]))
        self._sync()
        if inp.was_pressed("fire"):
            self.try_tag()
        tagged = sum(1 for t in g.tagged if t.alive)
        g.hud.set_drone_overlay(
            f"RECON DRONE   ALT {self.pos[2]:4.0f} m   RANGE {d:4.0f}/{self.max_range:.0f} m   TAGGED {tagged}",
            "[MOUSE] look   [W A S D] fly   [SPACE / C] up / down   [LEFT CLICK] tag target")

    def candidates(self):
        g = self.game
        out = [s for s in g.soldiers.soldiers if s.team == "enemy" and s.alive]
        out += [v for v in g.vehicles.vehicles if v.team == "enemy" and v.alive]
        return out

    def try_tag(self):
        g = self.game
        target = pick_target(tuple(self.pos), self.forward(), [c for c in self.candidates() if c not in g.tagged],
                             g.collision_world.line_of_sight)
        if target is None:
            g.audio.play("dry_fire", 0.4)
            return None
        g.tagged.append(target)
        g.audio.play("tag_beep", 0.5)
        g.hud.show_notice("TARGET TAGGED", 1.2)
        return target

    def end(self):
        g = self.game
        self._thermal(False)
        g.postfx.set_override(g.nvg_grading() if g.nvg_on else None)
        g.audio.stop_loop("drone_loop")
        g.player.control_enabled = True
        g.player.invulnerable = self._was_invulnerable
        g.hud.set_drone_overlay(None)
        if g.state in ("playing", "sandbox"):
            g.weapons.viewmodel.set_visible(True)
            g.player.camera.reattach()
