"""Security cameras: they sweep left and right, and raise the alarm if they watch the player for too long.

A camera can be shot out (one hit). Its view cone is drawn as a faint red beam so the player can
plan a route around it.
"""
from __future__ import annotations

import math

DETECT_TIME = 1.1          # seconds of continuous sight before the alarm goes off


def _angle_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def _heading_to(dx, dy):
    return math.degrees(math.atan2(-dx, dy))


class SecurityCamera:
    team = "enemy"
    name = "Camera"

    def __init__(self, cid, pos, heading=0.0, sweep=40.0, period=8.0, view_range=22.0, fov=50.0, pitch=-25.0):
        self.id = cid
        self.pos = tuple(pos)
        self.base_heading = heading
        self.sweep = sweep
        self.period = max(1.0, period)
        self.range = view_range
        self.fov = fov
        self.pitch = pitch
        self.heading = heading
        self.t = 0.0
        self.alive = True
        self.suspicion = 0.0
        self.spotted = False
        self.parts = {}

    # ------------------------------------------------------------------ combat interface
    @property
    def position(self):
        return self.pos

    def center(self):
        return self.pos

    def eye_position(self):
        return self.pos

    def hitboxes(self):
        x, y, z = self.pos
        return (("body", "sphere", (x, y, z, 0.32)),)

    def take_damage(self, amount, source, zone, direction):
        if not self.alive or amount <= 0:
            return False
        self.alive = False
        self.suspicion = 0.0
        return True

    # ------------------------------------------------------------------ logic
    def sees(self, target_pos, line_of_sight):
        x, y, z = self.pos
        tx, ty, tz = target_pos
        d = math.dist((x, y, z), (tx, ty, tz))
        if d > self.range or d < 0.5:
            return False
        if abs(_angle_diff(_heading_to(tx - x, ty - y), self.heading)) > self.fov / 2:
            return False
        down = math.degrees(math.atan2(tz - z, math.hypot(tx - x, ty - y)))
        if abs(down - self.pitch) > self.fov / 2 + 10:
            return False
        return line_of_sight((x, y, z), target_pos)

    def update(self, dt, target_pos, line_of_sight):
        """Returns 'spotted' the moment the alarm should go off, 'watching' while it is filling, else None."""
        if not self.alive:
            return None
        self.t += dt
        self.heading = self.base_heading + self.sweep * math.sin(2 * math.pi * self.t / self.period)
        if target_pos is not None and self.sees(target_pos, line_of_sight):
            self.suspicion += dt / DETECT_TIME
            if self.suspicion >= 1.0 and not self.spotted:
                self.spotted = True
                return "spotted"
            return "watching"
        self.suspicion = max(0.0, self.suspicion - dt * 0.5)
        return None


class SecurityManager:
    def __init__(self, world, combat, game=None):
        self.world = world
        self.combat = combat
        self.game = game
        self.cameras = []
        self._beep = 0.0

    @property
    def spotted(self):
        return any(c.spotted for c in self.cameras)

    def spawn(self, cid, pos, **params):
        cam = SecurityCamera(cid, pos, **params)
        self.cameras.append(cam)
        self.combat.register(cam)
        if self.game is not None:
            self._build_model(cam)
        return cam

    def find(self, cid):
        return next((c for c in self.cameras if c.id == cid), None)

    def remove_all(self):
        for c in self.cameras:
            self.combat.unregister(c)
            for np_ in c.parts.values():
                if not np_.is_empty():
                    np_.remove_node()
        self.cameras = []

    def _build_model(self, cam):
        from panda3d.core import NodePath
        from environments.geometry import MeshBuilder
        g = self.game
        mats = g.environment.materials

        def make(name, build):
            mb = MeshBuilder(mats.uv_scales())
            build(mb)
            return mb.build(NodePath(name), mats, name=name)

        root = NodePath("security_camera")
        root.reparent_to(g.render)
        root.set_pos(*cam.pos)
        bracket = make("cam_bracket", lambda mb: (
            mb.box("metal", 0, 0, 0.12, 0.08, 0.08, 0.25, (0.2, 0.2, 0.2)),
            mb.box("metal", 0, 0, 0.3, 0.2, 0.2, 0.04, (0.2, 0.2, 0.2))))
        bracket.reparent_to(root)
        head = root.attach_new_node("cam_head")
        body = make("cam_body", lambda mb: (
            mb.box("metal", 0, 0.05, -0.1, 0.18, 0.34, 0.18, (0.82, 0.82, 0.8)),
            mb.box("metal", 0, 0.08, 0.08, 0.24, 0.42, 0.03, (0.75, 0.75, 0.72)),                 # sun hood
            mb.cylinder_between("metal", (0, 0.22, -0.01), (0, 0.24, -0.01), 0.06, (0.05, 0.05, 0.06),
                                segments=10, caps=True)))
        body.reparent_to(head)
        led = make("cam_led", lambda mb: mb.box("emissive", 0.06, 0.18, 0.03, 0.03, 0.03, 0.03, (1.0, 0.1, 0.05)))
        led.reparent_to(head)
        length = cam.range
        cone = make("cam_cone", lambda mb: mb.cylinder_between(
            "beam", (0, 0.25, 0), (0, length, 0), 0.08, (1.0, 0.2, 0.15, 0.035),
            radius_end=length * math.tan(math.radians(cam.fov / 2)) * 0.55, segments=12))
        cone.reparent_to(head)
        head.set_hpr(cam.heading, cam.pitch, 0)
        cam.parts = {"root": root, "head": head, "led": led, "cone": cone}

    def update(self, dt, player):
        target = None
        if player is not None and player.alive:
            target = player.center()
        watching = False
        for cam in self.cameras:
            was_alive = cam.alive
            soldiers = getattr(self.game, "soldiers", None)
            result = cam.update(dt, target, soldiers.clear_view if soldiers is not None else self.world.line_of_sight)
            watching = watching or result == "watching"
            g = self.game
            if g is None:
                continue
            head = cam.parts.get("head")
            if head is not None:
                if cam.alive:
                    head.set_hpr(cam.heading, cam.pitch, 0)
                    blink = result is not None and int(cam.t * 8) % 2 == 0
                    cam.parts["led"].show() if (blink or result is None) else cam.parts["led"].hide()
                elif was_alive or not cam.parts["cone"].is_hidden():
                    cam.parts["cone"].hide()
                    cam.parts["led"].hide()
                    head.set_hpr(cam.heading, -60, 25)              # shot out: hangs off its bracket
                    g.effects.spawn("fire", cam.pos, life=0.2, size=(0.4, 0.1), texture="soft", blend="add",
                                    color=(1.0, 0.8, 0.4))
                    g.audio.play_at("impact_hard", cam.pos, 0.8)
                    self.combat.unregister(cam)
            if result == "spotted":
                g.audio.play_at("camera_alert", cam.pos, 1.0, min_distance=8.0)
                g.hud.show_notice("CAMERA ALARM!", 2.5)
        if self.game is not None:
            self._beep -= dt
            if watching and self._beep <= 0.0:
                self._beep = 0.6
                self.game.audio.play("tag_beep", 0.35)
                self.game.hud.show_notice("CAMERA IS WATCHING YOU", 0.7)
