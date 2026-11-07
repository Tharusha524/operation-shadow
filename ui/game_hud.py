"""In-game HUD: crosshair, ammo, health, hit markers, damage indicators, scope,
objectives, interaction prompts, subtitles and the F3 debug overlay."""
from __future__ import annotations

import math

import numpy as np
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import ClockObject, TextNode, TransparencyAttrib

from environments.materials import array_to_texture

HINT_TEXT = ("WASD move  |  Shift sprint  |  Space jump  |  Ctrl/C crouch  |  LMB fire  |  RMB aim  |  "
             "R reload  |  1-4 / wheel weapons  |  G grenade  |  E interact  |  V takedown  |  Esc pause")
TEXT = (0.92, 0.9, 0.82, 1)
ACCENT = (0.95, 0.78, 0.35, 1)
SHADOW = (0, 0, 0, 0.85)


def _vignette_texture(size=256):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    r = np.sqrt(((x - c) / c) ** 2 + ((y - c) / c) ** 2)
    a = np.clip((r - 0.45) / 0.75, 0, 1) ** 1.5
    rgb = np.zeros((size, size, 3), np.float32)
    rgb[..., 0] = 0.55
    return array_to_texture("vignette", np.concatenate([rgb, a[..., None]], -1))


def _arc_texture(size=128):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    dx, dy = (x - c) / c, (c - y) / c
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.degrees(np.arctan2(dx, dy))                 # 0 = up
    a = np.clip(1 - np.abs(r - 0.85) / 0.08, 0, 1) * np.clip(1 - np.abs(ang) / 28, 0, 1)
    rgb = np.zeros((size, size, 3), np.float32)
    rgb[..., 0] = 0.9
    rgb[..., 1] = 0.1
    return array_to_texture("damage_arc", np.concatenate([rgb, a[..., None]], -1))


def _scope_texture(size=512):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    dx, dy = (x - c) / c, (y - c) / c
    r = np.sqrt(dx * dx + dy * dy)
    a = np.clip((r - 0.94) / 0.03, 0, 1)
    line = ((np.abs(dx) < 0.004) | (np.abs(dy) < 0.004)) & (r < 0.94)
    gap = r < 0.03
    a = np.where(line & ~gap, 0.95, a)
    shade = np.clip((r - 0.7) / 0.25, 0, 1) * 0.35
    a = np.maximum(a, shade * (r < 0.94))
    rgb = np.zeros((size, size, 3), np.float32)
    return array_to_texture("scope", np.concatenate([rgb, a[..., None]], -1))


class Crosshair:
    """Four bars and a centre dot. The gap widens with weapon spread."""

    LENGTH = 8.0
    THICKNESS = 2.0

    def __init__(self, parent):
        self.root = parent.attach_new_node("crosshair")
        self._bars = []
        for _ in range(4):
            shadow = DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.55))
            bar = DirectFrame(parent=self.root, frameColor=(0.95, 0.95, 0.92, 0.92))
            self._bars.append((shadow, bar))
        self._dot_shadow = DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.55))
        self._dot = DirectFrame(parent=self.root, frameColor=(0.95, 0.95, 0.92, 0.92))
        self._px = 2.0 / 720.0
        self._gap = 6.0
        self.set_window_height(720)

    def set_window_height(self, height):
        self._px = p = 2.0 / max(1, height)
        half_len, half_th, o = self.LENGTH * p / 2, self.THICKNESS * p / 2, p
        for i, (shadow, bar) in enumerate(self._bars):
            if i < 2:
                bar["frameSize"] = (-half_th, half_th, -half_len, half_len)
                shadow["frameSize"] = (-half_th - o, half_th + o, -half_len - o, half_len + o)
            else:
                bar["frameSize"] = (-half_len, half_len, -half_th, half_th)
                shadow["frameSize"] = (-half_len - o, half_len + o, -half_th - o, half_th + o)
        self._dot["frameSize"] = (-p, p, -p, p)
        self._dot_shadow["frameSize"] = (-2 * p, 2 * p, -2 * p, 2 * p)
        self.set_gap(self._gap)

    def set_gap(self, gap_px):
        self._gap = gap_px
        offset = (gap_px + self.LENGTH / 2) * self._px
        for (shadow, bar), (x, z) in zip(self._bars, ((0, offset), (0, -offset), (-offset, 0), (offset, 0))):
            shadow.set_pos(x, 0, z)
            bar.set_pos(x, 0, z)

    @property
    def gap(self):
        return self._gap

    @property
    def pixel(self):
        return self._px


class GameHUD:
    def __init__(self, base, settings):
        self.base = base
        self.root = base.aspect2d.attach_new_node("hud")
        self.overlay = base.render2d.attach_new_node("hud_overlay")
        # Every HUD element lives under one of these, so hiding the HUD hides everything.
        self.corners = {name: getattr(base, attr).attach_new_node(f"hud_{name}") for name, attr in (
            ("br", "a2dBottomRight"), ("bl", "a2dBottomLeft"), ("tr", "a2dTopRight"),
            ("tl", "a2dTopLeft"), ("bc", "a2dBottomCenter"))}
        self.crosshair = Crosshair(self.root)

        self.white = DirectFrame(parent=self.overlay, frameColor=(1, 1, 1, 1), frameSize=(-1, 1, -1, 1))
        self.white.set_transparency(TransparencyAttrib.M_alpha)
        self.white.set_alpha_scale(0)
        self.white.hide()
        self._white = 0.0
        self.vignette = OnscreenImage(image=_vignette_texture(), parent=self.overlay, scale=(1, 1, 1))
        self.vignette.set_transparency(TransparencyAttrib.M_alpha)
        self.vignette.set_alpha_scale(0)

        self.scope_root = base.aspect2d.attach_new_node("scope")
        OnscreenImage(image=_scope_texture(), parent=self.scope_root, scale=(1, 1, 1)).set_transparency(
            TransparencyAttrib.M_alpha)
        for x0, x1 in ((-4, -0.999), (0.999, 4)):
            DirectFrame(parent=self.scope_root, frameColor=(0, 0, 0, 1), frameSize=(x0, x1, -1.5, 1.5))
        self.scope_root.hide()

        arc_tex = _arc_texture()
        self._arcs = []
        for _ in range(4):
            img = OnscreenImage(image=arc_tex, parent=self.root, scale=0.32)
            img.set_transparency(TransparencyAttrib.M_alpha)
            img.hide()
            self._arcs.append([img, 0.0, 0.0])   # node, timer, world yaw towards source

        self._hit_lines = []
        for angle in (45, 135, 225, 315):
            f = DirectFrame(parent=self.root, frameColor=(1, 1, 1, 0.95), frameSize=(-0.0025, 0.0025, 0.012, 0.03))
            f.set_r(angle)
            self._hit_lines.append(f)
        self._hit_timer = 0.0
        self._show_hit(False)

        # Bottom-right: weapon + ammo.
        br = self.corners["br"]
        self.weapon_name = OnscreenText(parent=br, text="", pos=(-0.08, 0.2), scale=0.042, fg=TEXT, shadow=SHADOW,
                                        align=TextNode.A_right, mayChange=True)
        self.ammo = OnscreenText(parent=br, text="", pos=(-0.2, 0.09), scale=0.09, fg=TEXT, shadow=SHADOW,
                                 align=TextNode.A_right, mayChange=True)
        self.reserve = OnscreenText(parent=br, text="", pos=(-0.08, 0.09), scale=0.05, fg=(0.75, 0.73, 0.66, 1),
                                    shadow=SHADOW, align=TextNode.A_right, mayChange=True)
        self.grenades = OnscreenText(parent=br, text="", pos=(-0.08, 0.035), scale=0.036, fg=TEXT, shadow=SHADOW,
                                     align=TextNode.A_right, mayChange=True)
        # Bottom-left: health bar.
        bl = self.corners["bl"]
        DirectFrame(parent=bl, frameColor=(0, 0, 0, 0.45), frameSize=(0.06, 0.56, 0.06, 0.1))
        self.health_bar = DirectFrame(parent=bl, frameColor=(0.85, 0.85, 0.8, 0.9), frameSize=(0.065, 0.555, 0.065, 0.095))
        self.health_text = OnscreenText(parent=bl, text="100", pos=(0.06, 0.12), scale=0.04, fg=TEXT, shadow=SHADOW,
                                        align=TextNode.A_left, mayChange=True)
        # Top-right: kills.
        self.kills = OnscreenText(parent=self.corners["tr"], text="", pos=(-0.06, -0.08), scale=0.045, fg=TEXT,
                                  shadow=SHADOW, align=TextNode.A_right, mayChange=True)
        # Top-left: objectives.
        self.objective_title = OnscreenText(parent=self.corners["tl"], text="", pos=(0.06, -0.09), scale=0.04,
                                            fg=ACCENT, shadow=SHADOW, align=TextNode.A_left, mayChange=True)
        self.objective_text = OnscreenText(parent=self.corners["tl"], text="", pos=(0.06, -0.145), scale=0.036,
                                           fg=TEXT, shadow=SHADOW, align=TextNode.A_left, mayChange=True, wordwrap=26)
        # Centre: interaction prompt, warnings, notifications.
        self.prompt = OnscreenText(parent=self.root, text="", pos=(0, -0.18), scale=0.045, fg=TEXT, shadow=SHADOW,
                                   mayChange=True)
        self.prompt_bar_bg = DirectFrame(parent=self.root, frameColor=(0, 0, 0, 0.5), frameSize=(-0.2, 0.2, -0.235, -0.22))
        self.prompt_bar = DirectFrame(parent=self.root, frameColor=ACCENT, frameSize=(-0.2, -0.2, -0.235, -0.22))
        self.warning = OnscreenText(parent=self.root, text="", pos=(0, -0.3), scale=0.05, fg=(1, 0.75, 0.3, 1),
                                    shadow=SHADOW, mayChange=True)
        self.notice = OnscreenText(parent=self.root, text="", pos=(0, 0.42), scale=0.06, fg=ACCENT, shadow=SHADOW,
                                   mayChange=True)
        self._notice_timer = 0.0
        # Bottom: subtitles.
        self.subtitle_bg = DirectFrame(parent=self.corners["bc"], frameColor=(0, 0, 0, 0.5),
                                       frameSize=(-0.9, 0.9, 0.2, 0.36))
        self.subtitle = OnscreenText(parent=self.corners["bc"], text="", pos=(0, 0.3), scale=0.04, fg=TEXT,
                                     shadow=SHADOW, mayChange=True, wordwrap=40)
        self._subtitle_timer = 0.0
        self.subtitle_bg.hide()
        # Objective marker.
        self.marker_root = self.root.attach_new_node("marker")
        icon = DirectFrame(parent=self.marker_root, frameColor=ACCENT, frameSize=(-0.014, 0.014, -0.014, 0.014))
        icon.set_r(45)
        self.marker = OnscreenText(parent=self.marker_root, text="", pos=(0, -0.06), scale=0.035, fg=ACCENT,
                                   shadow=SHADOW, mayChange=True)
        self.marker_root.hide()
        self.marker_world = None

        # Context action hint ([V] takedown, intel pickup).
        self.action_hint = OnscreenText(parent=self.root, text="", pos=(0, -0.26), scale=0.04, fg=TEXT,
                                        shadow=SHADOW, mayChange=True)
        # Night vision indicator.
        self.nvg_label = OnscreenText(parent=self.corners["tr"], text="", pos=(-0.06, -0.14), scale=0.035,
                                      fg=(0.55, 1.0, 0.55, 1), shadow=SHADOW, align=TextNode.A_right, mayChange=True)
        # Drone camera overlay (lives outside self.root so it shows while the normal HUD is hidden).
        self.drone_root = base.aspect2d.attach_new_node("drone_overlay")
        self.drone_text = OnscreenText(parent=self.drone_root, text="", pos=(0, 0.88), scale=0.042,
                                       fg=(0.9, 1.0, 0.9, 1), shadow=SHADOW, mayChange=True)
        self.drone_help = OnscreenText(parent=self.drone_root, text="", pos=(0, -0.9), scale=0.034,
                                       fg=(0.9, 1.0, 0.9, 0.9), shadow=SHADOW, mayChange=True)
        for x, y, r in ((-1, 1, 0), (1, 1, 90), (1, -1, 180), (-1, -1, 270)):     # reticle corner brackets
            corner = self.drone_root.attach_new_node("corner")
            corner.set_pos(x * 0.06, 0, y * 0.06)
            corner.set_r(r)
            DirectFrame(parent=corner, frameColor=(0.9, 1.0, 0.9, 0.9), frameSize=(0, 0.035, -0.003, 0.0))
            DirectFrame(parent=corner, frameColor=(0.9, 1.0, 0.9, 0.9), frameSize=(0, 0.003, -0.035, 0.0))
        self.drone_root.hide()
        # Red markers over enemies tagged by the recon drone.
        self._tag_nodes = []

        self.hint = OnscreenText(parent=self.corners["bc"], text=HINT_TEXT, pos=(0, 0.42), scale=0.03,
                                 fg=(0.92, 0.9, 0.82, 0.9), shadow=SHADOW)
        self._hint_timer = 14.0
        self.debug = OnscreenText(parent=self.corners["tl"], text="", pos=(0.06, -0.32), scale=0.032,
                                  fg=(0.75, 0.95, 0.7, 1), shadow=SHADOW, align=TextNode.A_left, mayChange=True)
        self.debug_visible = settings.show_fps
        self.debug.show() if self.debug_visible else self.debug.hide()
        self._debug_timer = 0.0
        self._damage_flash = 0.0
        self.set_prompt(None)
        if base.win is not None:
            self.on_window_resized(base.win.get_y_size())

    # ------------------------------------------------------------------ public API
    def on_window_resized(self, height):
        self.crosshair.set_window_height(height)

    def toggle_debug(self):
        self.debug_visible = not self.debug_visible
        self.debug.show() if self.debug_visible else self.debug.hide()

    def set_visible(self, visible):
        for node in [self.root, self.overlay, *self.corners.values()]:
            node.show() if visible else node.hide()
        if not visible:
            self.scope_root.hide()

    def hit_marker(self, killed=False, headshot=False):
        color = (1.0, 0.2, 0.15, 1) if killed else ((1.0, 0.85, 0.3, 1) if headshot else (1, 1, 1, 0.95))
        for f in self._hit_lines:
            f["frameColor"] = color
        self._hit_timer = 0.25 if killed else 0.14
        self._show_hit(True)

    def _show_hit(self, visible):
        for f in self._hit_lines:
            f.show() if visible else f.hide()

    def damage_from(self, world_yaw):
        """Show a red arc pointing towards where the damage came from."""
        slot = min(self._arcs, key=lambda a: a[1])
        slot[1], slot[2] = 1.6, world_yaw
        slot[0].show()
        self._damage_flash = 1.0

    def set_objectives(self, title, lines):
        self.objective_title.setText(title or "")
        self.objective_text.setText("\n".join(lines))

    def set_prompt(self, text, progress=None):
        self.prompt.setText(text or "")
        if progress is None or text is None:
            self.prompt_bar.hide()
            self.prompt_bar_bg.hide()
        else:
            self.prompt_bar.show()
            self.prompt_bar_bg.show()
            self.prompt_bar["frameSize"] = (-0.2, -0.2 + 0.4 * max(0.0, min(1.0, progress)), -0.235, -0.22)

    def show_notice(self, text, seconds=3.0):
        self.notice.setText(text)
        self._notice_timer = seconds

    def show_subtitle(self, speaker, text, seconds=4.0):
        self.subtitle.setText(f"{speaker}:  {text}" if speaker else text)
        self.subtitle_bg.show()
        self._subtitle_timer = seconds

    def set_marker(self, world_pos):
        self.marker_world = world_pos
        self.marker_root.show() if world_pos is not None else self.marker_root.hide()

    def flash_white(self, amount):
        """Flashbang: the screen goes white and fades back over a few seconds."""
        self._white = max(self._white, min(3.5, amount))
        self.white.show()

    def set_action_hint(self, text):
        if self.action_hint.getText() != (text or ""):
            self.action_hint.setText(text or "")

    def set_nvg(self, on, available=False):
        self.nvg_label.setText("NVG ON  [N]" if on else ("NVG  [N]" if available else ""))

    def set_drone_overlay(self, text, help_text=""):
        if text is None:
            if not self.drone_root.is_hidden():
                self.drone_root.hide()
                self.crosshair.root.show()
                self.corners["br"].show()
            return
        if self.drone_root.is_hidden():
            self.drone_root.show()
            self.crosshair.root.hide()
            self.corners["br"].hide()
        self.drone_text.setText(text)
        self.drone_help.setText(help_text)

    def update_tags(self, tagged):
        """Draw a small red diamond above every living tagged enemy that is in front of the camera."""
        from panda3d.core import Point2, Point3
        alive = [t for t in tagged if t.alive]
        while len(self._tag_nodes) < len(alive):
            n = self.base.aspect2d.attach_new_node("tag")
            f = DirectFrame(parent=n, frameColor=(1.0, 0.25, 0.2, 0.9), frameSize=(-0.011, 0.011, -0.011, 0.011))
            f.set_r(45)
            self._tag_nodes.append(n)
        cam = self.base.cam
        aspect = self.base.getAspectRatio()
        for i, n in enumerate(self._tag_nodes):
            if i >= len(alive) or self.root.is_hidden() and self.drone_root.is_hidden():
                n.hide()
                continue
            x, y, z = alive[i].center()
            p3 = cam.get_relative_point(self.base.render, Point3(x, y, z + 1.4))
            p2 = Point2()
            if p3.y > 0 and self.base.camLens.project(p3, p2):
                n.set_pos(p2.x * aspect, 0, p2.y)
                n.show()
            else:
                n.hide()

    # ------------------------------------------------------------------ update
    def update(self, dt, player, weapons=None, kills=0, extra_lines=()):
        motor = player.motor
        ads = weapons.ads if weapons else 0.0
        if weapons:
            w = weapons.current
            spread = w.spread(ads, min(1.0, motor.horizontal_speed / motor.cfg.walk_speed), not motor.grounded)
            fov = self.base.camLens.get_fov()[0]
            target = 4.0 + spread / max(1.0, fov) * self.base.win.get_x_size() * 0.9
        else:
            target = 6.0
        gap = self.crosshair.gap + (target - self.crosshair.gap) * min(1.0, dt * 14.0)
        self.crosshair.set_gap(gap)
        self.crosshair.root.set_alpha_scale(0.0 if getattr(self.base, "driving", False)
                                            else max(0.0, 1.0 - ads * 2.5))
        if weapons:
            self.scope_root.show() if weapons.scoped else self.scope_root.hide()
            w = weapons.current
            self.weapon_name.setText(w.stats.name.upper())
            self.ammo.setText(str(w.mag))
            self.reserve.setText(f"/ {w.reserve}")
            names = {"frag": "FRAG", "smoke": "SMOKE", "flash": "FLASHBANG"}
            kind = getattr(weapons, "grenade_type", "frag")
            extra = "  [T]" if any(getattr(weapons, "special", {}).values()) else ""
            self.grenades.setText(f"{names[kind]}  x{weapons.grenade_count(kind)}{extra}")
            low = w.mag <= max(1, w.stats.magazine // 4)
            self.ammo["fg"] = (1.0, 0.45, 0.3, 1) if low else TEXT
            if w.reloading:
                self.warning.setText("RELOADING")
            elif w.mag == 0 and w.reserve == 0:
                self.warning.setText("NO AMMO - WALK OVER AN AMMO PACK OR SWITCH WEAPON")
            elif low and w.reserve > 0:
                self.warning.setText("[R] RELOAD")
            else:
                self.warning.setText("")
        self.kills.setText(f"KILLS  {kills}")

        hp = player.health.fraction
        self.health_bar["frameSize"] = (0.065, 0.065 + 0.49 * hp, 0.065, 0.095)
        self.health_bar["frameColor"] = (0.85, 0.85, 0.8, 0.9) if hp > 0.4 else (0.9, 0.25, 0.2, 0.95)
        self.health_text.setText(f"{int(math.ceil(player.health.current))}")
        self._damage_flash = max(0.0, self._damage_flash - dt * 1.5)
        self.vignette.set_alpha_scale(min(1.0, (1.0 - hp) * 1.1 + self._damage_flash * 0.35))

        view_yaw = player.camera.look.yaw
        for arc in self._arcs:
            if arc[1] <= 0:
                continue
            arc[1] -= dt
            if arc[1] <= 0:
                arc[0].hide()
                continue
            rel = arc[2] - view_yaw
            arc[0].set_r(-rel)
            arc[0].set_alpha_scale(min(1.0, arc[1]))

        if self._hit_timer > 0:
            self._hit_timer -= dt
            if self._hit_timer <= 0:
                self._show_hit(False)

        if self._notice_timer > 0:
            self._notice_timer -= dt
            if self._notice_timer <= 0:
                self.notice.setText("")
        if self._subtitle_timer > 0:
            self._subtitle_timer -= dt
            if self._subtitle_timer <= 0:
                self.subtitle.setText("")
                self.subtitle_bg.hide()

        self._update_marker()
        if self._white > 0.0:
            self._white = max(0.0, self._white - dt)
            self.white.set_alpha_scale(min(1.0, self._white))
            if self._white <= 0.0:
                self.white.hide()

        if self._hint_timer > 0:
            self._hint_timer -= dt
            self.hint.set_alpha_scale(max(0.0, min(1.0, self._hint_timer / 2.0)))
            if self._hint_timer <= 0:
                self.hint.hide()

        if self.debug_visible:
            self._debug_timer -= dt
            if self._debug_timer <= 0:
                self._debug_timer = 0.2
                fps = ClockObject.get_global_clock().get_average_frame_rate()
                state = "ground" if motor.grounded else "air"
                if motor.crouching:
                    state += " / crouch"
                if motor.sprinting:
                    state += " / sprint"
                self.debug.setText("\n".join([
                    f"FPS {fps:5.1f}",
                    f"pos  {motor.x:7.2f} {motor.y:7.2f} {motor.z:6.2f}",
                    f"speed {motor.horizontal_speed:4.2f} m/s   {state}",
                    *extra_lines,
                ]))

    def _update_marker(self):
        if self.marker_world is None:
            return
        from panda3d.core import Point2, Point3
        cam = self.base.cam
        p3 = cam.get_relative_point(self.base.render, Point3(*self.marker_world))
        p2 = Point2()
        dist = (self.base.camera.get_pos(self.base.render) - Point3(*self.marker_world)).length()
        aspect = self.base.getAspectRatio()
        if p3.y > 0 and self.base.camLens.project(p3, p2):
            self.marker_root.set_pos(p2.x * aspect, 0, p2.y + 0.03)
        else:
            # Behind or off-screen: stick to the screen edge on the correct side.
            side = 1 if p3.x >= 0 else -1
            self.marker_root.set_pos(side * (aspect - 0.15), 0, 0)
        self.marker.setText(f"{dist:.0f} m")
