"""Story videos: the voiced, cinematic briefings shown before the campaign and before every mission.

A video (data/story/<name>.json) is a list of shots, each with narration lines:
  title      black screen, big title, a typed line under it
  region     a satellite-style relief map of the whole region with borders, places, arrows and unit markers
  satellite  a live top-down "satellite feed" of the real mission map with markers and arrows
  scene      a real 3D scene from the game (soldiers, vehicles, explosions) filmed with a moving camera,
             movie colours and a blurred background
  dossier    an intelligence file card on a person (name, rank, notes, a stamp)
Typed captions (date, time, place) appear bottom-left. Every line is spoken (systems/voice.py) and a
shot lasts until its narration is finished. Space / Enter / Esc skips the whole video.
"""
from __future__ import annotations

import json
import math

import numpy as np
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (BitMask32, LineSegs, NodePath, Point2, Point3, TextNode, TransparencyAttrib)

from core.paths import DATA_DIR
from environments.materials import array_to_texture, fbm
from environments.sets import SET_ORIGIN, Puppet, build_set

STORY_DIR = DATA_DIR / "story"
FILM_GRADE = {"exposure": 1.05, "contrast": 1.12, "saturation": 0.82, "tint": [1.04, 1.0, 0.94],
              "shadow_tint": [0.82, 0.94, 1.12], "vignette": 0.85, "grain": 0.045, "lift": 0.02, "bloom": 0.55}
SAT_GRADE = {"exposure": 1.25, "contrast": 1.25, "saturation": 0.25, "tint": [0.86, 1.0, 0.92],
             "shadow_tint": [1, 1, 1], "vignette": 0.9, "grain": 0.09, "lift": 0.03, "bloom": 0.3}
SAT_NIGHT_GRADE = dict(SAT_GRADE, exposure=7.5, saturation=0.0, lift=0.07, tint=[0.8, 1.0, 0.85])
COLORS = {"red": (0.95, 0.2, 0.15, 1), "blue": (0.35, 0.65, 1.0, 1), "yellow": (1.0, 0.82, 0.3, 1),
          "white": (0.95, 0.95, 0.9, 1), "green": (0.4, 1.0, 0.5, 1)}
WPM_SECONDS = 1 / 2.6          # fallback narration speed when a voice file is missing (words per second)
_region_tex = None


def load_story(name):
    path = STORY_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


# ---------------------------------------------------------------------------------------------- region map
def region_texture(region, size=(1024, 640)):
    """Satellite-style relief image of the fictional region (generated, no image files needed)."""
    global _region_tex
    if _region_tex is not None:
        return _region_tex
    w, h = size
    rng = np.random.default_rng(1977)
    n = 512
    base = fbm(n, 4, 6, rng)
    detail = fbm(n, 24, 3, rng)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = xs / (w - 1), 1.0 - ys / (h - 1)
    hgt = base[(v * (n - 1)).astype(int), (u * (n - 1)).astype(int)] * 0.8 + \
        detail[(v * (n - 1)).astype(int) % n, (u * (n - 1)).astype(int) % n] * 0.2
    # Mountains around Lake Ostra (south-west) and along the northern border; lowlands by the river.
    hgt += 0.35 * np.exp(-(((u - 0.26) / 0.16) ** 2 + ((v - 0.22) / 0.13) ** 2))
    hgt += 0.18 * np.exp(-(((v - 0.76) / 0.08) ** 2))
    coast = np.clip((u - region["coast_west"]) * 12, 0, 1) * np.clip((region["coast_east"] - u) * 12, 0, 1)
    coast *= 1.0 - 0.6 * np.clip((0.04 - v) * 30, 0, 1)
    land = coast * (0.5 + 0.5 * np.clip((hgt - 0.25) * 4, 0, 1)) > 0.45
    for lake in region["lakes"]:
        cx, cy = lake["center"]
        rx, ry = lake["radius"]
        land &= ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2 > 1.0
    gy, gx = np.gradient(hgt)
    shade = np.clip(0.75 - (gx - gy) * 140.0, 0.35, 1.25)
    low, mid, high = np.array([0.27, 0.33, 0.2]), np.array([0.42, 0.39, 0.29]), np.array([0.72, 0.71, 0.68])
    t = np.clip((hgt - 0.35) / 0.45, 0, 1)[..., None]
    col = np.where(t < 0.5, low + (mid - low) * (t * 2), mid + (high - mid) * ((t - 0.5) * 2))
    col = col * (0.88 + 0.24 * detail[(v * (n - 1)).astype(int) % n, (u * (n - 1)).astype(int) % n][..., None])
    col = col * shade[..., None]
    sea = np.array([0.04, 0.09, 0.15]) + 0.05 * base[(v * (n - 1)).astype(int), (u * (n - 1)).astype(int)][..., None]
    img = np.where(land[..., None], col, sea)
    _region_tex = array_to_texture("region_map", img.astype(np.float32))
    return _region_tex


class RegionMap:
    """Full-screen 2D map with a slow zoom; items are in map coordinates (0..1)."""

    ASPECT = 1024 / 640

    def __init__(self, game, region, shot):
        self.game = game
        self.region = region
        self.shot = shot
        self.root = game.aspect2d.attach_new_node("region_map")
        self.canvas = self.root.attach_new_node("canvas")
        img = OnscreenImage(image=region_texture(region), parent=self.canvas,
                            scale=(self.ASPECT, 1, 1), pos=(self.ASPECT, 0, 1))
        img.set_transparency(TransparencyAttrib.M_none)
        self.items = self.canvas.attach_new_node("items")
        self.items.set_bin("fixed", 20)
        self.items.set_depth_test(False)
        self.items.set_depth_write(False)
        self._static()
        self.dynamic = self.items.attach_new_node("dynamic")
        self.unit_nodes = []                     # NATO-style unit boxes, created once and blinked in
        for unit in shot.get("units", []):
            x, _, z = self.to_canvas(unit["pos"])
            col = COLORS.get(unit.get("color", "red"))
            node = self.items.attach_new_node("unit")
            node.set_pos(x, 0, z)
            DirectFrame(parent=node, frameColor=(col[0], col[1], col[2], 0.85), frameSize=(-0.022, 0.022, -0.014, 0.014))
            DirectFrame(parent=node, frameColor=(0, 0, 0, 0.9), frameSize=(-0.018, 0.018, -0.0015, 0.0015))
            node.hide()
            self.unit_nodes.append((unit, node))
        self.root.set_bin("fixed", 15)
        self.update(0.0, 0.0)

    def to_canvas(self, p):
        return 2 * self.ASPECT * p[0], 0, 2 * p[1]

    def _line(self, parent, points, color, thick=2.0):
        ls = LineSegs()
        ls.set_thickness(thick)
        ls.set_color(*color)
        for i, p in enumerate(points):
            x, _, z = self.to_canvas(p)
            (ls.move_to if i == 0 else ls.draw_to)(x, 0, z)
        return parent.attach_new_node(ls.create())

    def _label(self, text, p, color=(0.95, 0.95, 0.9, 1), scale=0.045, dot=True):
        x, _, z = self.to_canvas(p)
        if dot:
            DirectFrame(parent=self.items, frameColor=color, frameSize=(-0.008, 0.008, -0.008, 0.008),
                        pos=(x, 0, z)).set_r(45)
        OnscreenText(parent=self.items, text=text, pos=(x + 0.02, z + 0.012), scale=scale, fg=color,
                     shadow=(0, 0, 0, 1), align=TextNode.A_left)

    def _static(self):
        r = self.region
        self._line(self.items, r["border"], (0.95, 0.25, 0.2, 0.9), 3.0)
        for river in r["rivers"]:
            self._line(self.items, river["points"], (0.25, 0.45, 0.65, 1), 2.5)
        for c in r["countries"]:
            x, _, z = self.to_canvas(c["pos"])
            OnscreenText(parent=self.items, text=c["name"], pos=(x, z), scale=0.07, fg=COLORS[c["color"]][:3] + (0.6,),
                         shadow=(0, 0, 0, 0.8))
        show = self.shot.get("places")
        for key, p in r["places"].items():
            if show is None or key in show:
                self._label(p["name"].upper(), p["pos"], scale=0.036)

    def update(self, t, k):
        """t = seconds into the shot, k = 0..1 eased progress."""
        a = self.shot.get("view_from", [0.5, 0.5, 1.0])
        b = self.shot.get("view_to", a)
        cx, cy, zoom = _lerp(a, b, k)
        # Show map point (cx, cy) at the screen centre with the given zoom (1 = whole map height).
        self.canvas.set_scale(zoom)
        px, _, pz = self.to_canvas((cx, cy))
        self.canvas.set_pos(-px * zoom, 0, -pz * zoom)
        self.dynamic.node().remove_all_children()
        for arrow in self.shot.get("arrows", []):
            start, dur = arrow.get("t", 0.0), arrow.get("grow", 2.0)
            if t < start:
                continue
            f = _smooth((t - start) / dur)
            p0, p1 = arrow["from"], arrow["to"]
            end = _lerp(p0, p1, f)
            col = COLORS.get(arrow.get("color", "red"))
            self._line(self.dynamic, [p0, end], col, 6.0)
            if f > 0.95:
                ang = math.atan2(p1[1] - p0[1], (p1[0] - p0[0]) * self.ASPECT)
                for side in (-1, 1):
                    a2 = ang + math.pi + side * 0.5
                    tip = (end[0] + math.cos(a2) * 0.02 / self.ASPECT, end[1] + math.sin(a2) * 0.02)
                    self._line(self.dynamic, [end, tip], col, 6.0)
        for unit, node in self.unit_nodes:
            if t >= unit.get("t", 0.0):
                blink = (t - unit.get("t", 0.0)) > 0.6 or int(t * 8) % 2
                node.show() if blink else node.hide()
        for ping in self.shot.get("pings", []):
            if t >= ping.get("t", 0.0):
                x, _, z = self.to_canvas(ping["pos"])
                age = (t - ping.get("t", 0.0)) % 1.6
                ring = LineSegs()
                ring.set_thickness(2.0)
                col = COLORS.get(ping.get("color", "yellow"))
                ring.set_color(col[0], col[1], col[2], max(0.0, 1.0 - age / 1.6))
                rad = 0.01 + age * 0.03
                for i in range(25):
                    an = i / 24 * 2 * math.pi
                    (ring.move_to if i == 0 else ring.draw_to)(x + math.cos(an) * rad, 0, z + math.sin(an) * rad)
                self.dynamic.attach_new_node(ring.create())

    def remove(self):
        self.root.remove_node()


# ---------------------------------------------------------------------------------------------- the player
class StoryVideo:
    BAR = 0.12

    def __init__(self, game, spec, on_done):
        self.game = game
        self.spec = spec
        self.on_done = on_done
        self.shots = spec.get("shots", [])
        self.region = json.loads((STORY_DIR / "region.json").read_text(encoding="utf-8"))
        self.index = -1
        self._dt = 0.0
        self.offset = (0.0, 0.0, 0.0)
        self.t = 0.0
        self.duration = 0.0
        self.done = False
        self.lines = []
        self.line_i = 0
        self.line_wait = 0.0
        self.actors = []
        self.vehicles = []
        self.fires_before = len(game.fires)
        self.events = []
        self.region_map = None
        self.sat_overlay = None
        self.dossier = None
        self.title_nodes = []
        self.arrows3d = None
        self.markers = []
        self.set_node = None
        self.set_name = None
        self.puppets = []
        self._fog = game.render.get_fog() if game.render.has_fog() else None
        self._far = game.camLens.get_far()
        # Overlay: black backdrop (title / dossier), letterbox, captions, subtitles.
        self.ui = game.aspect2d.attach_new_node("story_ui")
        self.ui.set_bin("fixed", 50)
        self.black = DirectFrame(parent=game.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, 1))
        self.black.set_bin("fixed", 10)
        self.black.hide()
        self.bars = [DirectFrame(parent=game.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, 1 - self.BAR * 2, 1)),
                     DirectFrame(parent=game.render2d, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, -1 + self.BAR * 2))]
        for b in self.bars:
            b.set_bin("fixed", 60)
        self.caption = OnscreenText(parent=game.a2dBottomLeft, text="", pos=(0.08, 0.36), scale=0.042,
                                    fg=(0.95, 0.92, 0.82, 1), shadow=(0, 0, 0, 1), align=TextNode.A_left, mayChange=True)
        self.caption2 = OnscreenText(parent=game.a2dBottomLeft, text="", pos=(0.08, 0.3), scale=0.034,
                                     fg=(0.8, 0.78, 0.7, 1), shadow=(0, 0, 0, 1), align=TextNode.A_left, mayChange=True)
        self.subtitle = OnscreenText(parent=game.aspect2d, text="", pos=(0, -0.83), scale=0.045,
                                     fg=(0.95, 0.93, 0.86, 1), shadow=(0, 0, 0, 1), mayChange=True, wordwrap=40)
        self.skip_hint = OnscreenText(parent=game.a2dTopRight, text="[SPACE] skip", pos=(-0.08, -0.08), scale=0.03,
                                      fg=(0.7, 0.7, 0.65, 0.8), align=TextNode.A_right)
        for node in (self.caption, self.caption2, self.subtitle, self.skip_hint):
            node.set_bin("fixed", 70)
        self._typed = ("", "", 0.0)
        game.player.camera.detach_for_cinematic(fov=50.0)
        game.soldiers.player_hidden = True               # actors fight each other, not the (hidden) player
        self._next_shot()

    # ------------------------------------------------------------------ timing
    def _line_seconds(self, line):
        voice = getattr(self.game, "voice", None)
        d = voice.duration(line.get("speaker", "narrator"), line["text"]) if voice else 0.0
        return d if d > 0 else len(line["text"].split()) * WPM_SECONDS

    def _next_shot(self):
        self._end_shot()
        self.index += 1
        if self.index >= len(self.shots):
            self.finish()
            return
        shot = self.shots[self.index]
        self.t = 0.0
        self.lines = list(shot.get("lines", []))
        self.line_i = 0
        self.line_wait = shot.get("line_delay", 0.35)
        talk = sum(self._line_seconds(l) + 0.2 for l in self.lines) + self.line_wait + 0.3
        self.duration = max(float(shot.get("duration", 4.0)), talk)
        cap = shot.get("caption")
        if cap is not None:
            self._typed = (cap[0] if len(cap) > 0 else "", cap[1] if len(cap) > 1 else "", 0.0)
        getattr(self, f"_begin_{shot['type']}")(shot)

    # ------------------------------------------------------------------ shot types
    def _begin_title(self, shot):
        g = self.game
        self.black.show()
        self.black["frameColor"] = (0, 0, 0, 1)
        t1 = OnscreenText(parent=self.ui, text=shot.get("title", ""), pos=(0, 0.05), scale=shot.get("scale", 0.11),
                          fg=(0.93, 0.9, 0.82, 1), shadow=(0, 0, 0, 1), mayChange=True)
        t2 = OnscreenText(parent=self.ui, text="", pos=(0, -0.08), scale=0.045, fg=(0.85, 0.66, 0.3, 1),
                          shadow=(0, 0, 0, 1), mayChange=True)
        self.title_nodes = [t1, t2]
        g.postfx.set_override(FILM_GRADE)
        if shot.get("sound"):
            g.audio.play(shot["sound"], 0.8)

    def _update_title(self, shot, k):
        t1, t2 = self.title_nodes
        fade = min(1.0, self.t / 1.2, max(0.0, (self.duration - self.t) / 0.8))
        t1.set_alpha_scale(fade)
        sub = shot.get("subtitle", "")
        t2.setText(sub[:int(len(sub) * min(1.0, max(0.0, self.t - 0.8) / 1.5))])
        t2.set_alpha_scale(fade)

    def _begin_region(self, shot):
        self.black.show()
        self.region_map = RegionMap(self.game, self.region, shot)
        self.game.postfx.set_override(dict(FILM_GRADE, grain=0.06, vignette=0.7))

    def _update_region(self, shot, k):
        self.region_map.update(self.t, k)

    def _begin_satellite(self, shot):
        g = self.game
        night = shot.get("night", False)
        g.postfx.set_override(SAT_NIGHT_GRADE if night else SAT_GRADE)
        g.render.set_fog_off(1)
        g.camLens.set_far(1600.0)
        g.camLens.set_fov(shot.get("fov", 45.0))
        if g.weather is not None:
            g.weather.root.hide()
        self.arrows3d = g.render.attach_new_node("sat_arrows")
        self.arrows3d.set_light_off(1)
        self.arrows3d.set_fog_off(1)
        self.arrows3d.set_depth_test(False)
        self.arrows3d.set_bin("fixed", 5)
        self.arrows3d.hide(BitMask32.bit(1))
        self.markers = []
        for m in shot.get("markers", []):
            node = self.ui.attach_new_node("marker")
            col = COLORS.get(m.get("color", "yellow"))
            DirectFrame(parent=node, frameColor=col, frameSize=(-0.012, 0.012, -0.012, 0.012)).set_r(45)
            OnscreenText(parent=node, text=m.get("label", ""), pos=(0.025, -0.012), scale=0.032, fg=col,
                         shadow=(0, 0, 0, 1), align=TextNode.A_left)
            node.hide()
            self.markers.append((m, node))
        ov = self.ui.attach_new_node("sat_overlay")
        for x, y, r in ((-1, 1, 0), (1, 1, 90), (1, -1, 180), (-1, -1, 270)):
            c = ov.attach_new_node("corner")
            c.set_pos(x * 1.25, 0, y * 0.62)
            c.set_r(r)
            DirectFrame(parent=c, frameColor=(0.8, 1.0, 0.85, 0.7), frameSize=(0, 0.12, -0.004, 0))
            DirectFrame(parent=c, frameColor=(0.8, 1.0, 0.85, 0.7), frameSize=(0, 0.004, -0.12, 0))
        DirectFrame(parent=ov, frameColor=(0.8, 1.0, 0.85, 0.5), frameSize=(-0.04, 0.04, -0.001, 0.001))
        DirectFrame(parent=ov, frameColor=(0.8, 1.0, 0.85, 0.5), frameSize=(-0.001, 0.001, -0.04, 0.04))
        self.sat_text = OnscreenText(parent=ov, text="", pos=(-1.2, 0.66), scale=0.03, fg=(0.8, 1.0, 0.85, 0.9),
                                     align=TextNode.A_left, mayChange=True)
        self.sat_overlay = ov

    def _update_satellite(self, shot, k):
        g = self.game
        a, b = shot["from"], shot.get("to", shot["from"])
        x, y, h = _lerp(a, b, k)
        cam = g.camera
        cam.set_pos(x, y - h * 0.18, h)
        cam.look_at(x, y, 0)
        cam.set_r(shot.get("roll", 0.0) * k)
        lat, lon = 47.2 + y / 111000.0, 21.6 + x / 75000.0
        self.sat_text.setText(f"{shot.get('feed', 'KH-SAT 7')}  //  LIVE   ALT {h * 30:6.0f} M   "
                              f"{lat:.4f} N  {lon:.4f} E   T+{self.t:05.1f}")
        self.arrows3d.node().remove_all_children()
        for arrow in shot.get("arrows", []):
            start, dur = arrow.get("t", 0.0), arrow.get("grow", 2.0)
            if self.t < start:
                continue
            f = _smooth((self.t - start) / dur)
            p0, p1 = arrow["from"], arrow["to"]
            end = _lerp(p0, p1, f)
            col = COLORS.get(arrow.get("color", "red"))
            ls = LineSegs()
            ls.set_thickness(5.0)
            ls.set_color(*col)
            z = arrow.get("z", 1.0)
            ls.move_to(p0[0], p0[1], z)
            ls.draw_to(end[0], end[1], z)
            if f > 0.95:
                ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
                for side in (-1, 1):
                    a2 = ang + math.pi + side * 0.45
                    ls.move_to(end[0], end[1], z)
                    ls.draw_to(end[0] + math.cos(a2) * 8, end[1] + math.sin(a2) * 8, z)
            self.arrows3d.attach_new_node(ls.create())
        aspect = g.getAspectRatio()
        for m, node in self.markers:
            if self.t < m.get("t", 0.0):
                continue
            p3 = g.cam.get_relative_point(g.render, Point3(*m["pos"]))
            p2 = Point2()
            if p3.y > 0 and g.camLens.project(p3, p2):
                node.set_pos(p2.x * aspect, 0, p2.y)
                node.show()
                blink = (self.t - m.get("t", 0.0)) > 0.8 or int(self.t * 8) % 2
                node.set_alpha_scale(1.0 if blink else 0.2)
            else:
                node.hide()

    def _begin_scene(self, shot):
        g = self.game
        g.postfx.set_override(dict(FILM_GRADE, **shot.get("grade", {})))
        g.camLens.set_fov(shot.get("fov", 42.0))
        from environments.sets import _MaterialsProxy
        _MaterialsProxy.materials = g.environment.materials
        if "rain" in shot and g.weather is not None:                 # e.g. the rainy-night flashback
            self._rain_before = g.weather.intensity
            g.weather.set_intensity(shot["rain"])
        name = shot.get("set")
        if name != self.set_name:
            if self.set_node is not None:
                self.set_node.remove_node()
                self.set_node = None
            if name:
                self.set_node = build_set(name, g.environment.materials, region_texture(self.region))
                self.set_node.reparent_to(g.render)
            self.set_name = name
        self.offset = SET_ORIGIN if name else (0.0, 0.0, 0.0)
        if name and g.weather is not None:
            g.weather.root.hide()
        # Actors stand inside the set node, so the set's own lamps light them (positions are set-relative).
        parent = self.set_node if self.set_node is not None else g.render
        self._pending_cast = list(shot.get("cast", []))
        mgr = g.soldiers
        for a in shot.get("actors", []):
            for i in range(int(a.get("count", 1))):
                ox, oy = a.get("spread", [0, 0])
                x, y = a["pos"][0] + ox * i, a["pos"][1] + oy * i
                s = mgr.spawn(a.get("team", "friendly"), x, y, a.get("heading", 0.0),
                              profile=a.get("profile", "regular" if a.get("team") == "enemy" else "squad"),
                              name=a.get("name"), invulnerable=True)
                s.group = "_story"
                label = getattr(s.model, "label", None)
                if label is not None:                      # no "Ally" tags in a film
                    label.hide()
                if a.get("patrol"):
                    s.ai.patrol = [tuple(p) for p in a["patrol"]]
                    s.ai.set_state("PATROL")
                elif a.get("move_to"):
                    s.ai.command_hold(a["move_to"][0] + ox * i, a["move_to"][1] + oy * i, a.get("heading", 0.0))
                elif not a.get("fight", False):
                    s.ai.command_hold(x, y, a.get("heading", 0.0))
                if a.get("calm"):
                    s.ai.p = dict(s.ai.p, vision_range=0.5)
                self.actors.append(s)
        for v in shot.get("vehicles", []):
            params = {k: v[k] for k in ("pos", "heading", "path", "speed", "loop", "armed", "altitude",
                                         "orbit_radius") if k in v}
            if "path" in params:
                params["path"] = [tuple(p) for p in params["path"]]
            if "pos" in params:
                params["pos"] = tuple(params["pos"])
            veh = g.vehicles.spawn(v["kind"], f"_story_{len(self.vehicles)}", **params)
            if v.get("hover"):
                veh.mode = "hover"
                veh.hover_target = tuple(v["hover"])
            self.vehicles.append(veh)
        self.events = sorted(shot.get("events", []), key=lambda e: e.get("t", 0.0))
        for spec in self._pending_cast:
            ride = spec.get("ride")
            if ride is not None and ride < len(self.vehicles) and self.vehicles[ride].parts.get("root") is not None:
                self.puppets.append(Puppet(self.vehicles[ride].parts["root"], spec, (0.0, 0.0, 0.0)))
            else:
                self.puppets.append(Puppet(parent, spec, (0.0, 0.0, 0.0)))
        self._pending_cast = []

    def _update_scene(self, shot, k):
        g = self.game
        cam = g.camera
        o = self.offset
        pos = _lerp(shot["from"], shot.get("to", shot["from"]), k)
        cam.set_pos(Point3(pos[0] + o[0], pos[1] + o[1], pos[2] + o[2]))
        target = _lerp(shot["look_from"], shot.get("look_to", shot["look_from"]), k)
        target = [target[0] + o[0], target[1] + o[1], target[2] + o[2]]
        cam.look_at(Point3(*target))
        for p in self.puppets:
            p.update(self.t, self._dt)
        if shot.get("dof"):                                   # optional soft background (off by default)
            focus = (cam.get_pos(g.render) - Point3(*target)).length()
            g.postfx.set_dof(focus, max(4.0, focus * 0.8), 0.45)
        while self.events and self.t >= self.events[0].get("t", 0.0):
            e = self.events.pop(0)
            if "explosion" in e:
                p = tuple(e["explosion"])
                g.effects.explosion(p)
                g.audio.play_at("explosion", p, 1.0, min_distance=15.0)
                g.player.camera.add_trauma(e.get("shake", 0.3))
            if "fire" in e:
                f = e["fire"]
                g.add_fire(tuple(f[:3]), f[3] if len(f) > 3 else 1.0)
            if "smoke" in e:
                g.smoke_emitters.append([tuple(e["smoke"]), 60.0, 0.0])
            if "sound" in e:
                g.audio.play(e["sound"], e.get("volume", 0.8))
            if "flare" in e:
                g.fire_flare(tuple(e["flare"]), 20.0)
            if "clock" in e and self.set_node is not None:
                clock = self.set_node.find("**/clock")
                if not clock.is_empty():
                    clock.node().set_text(e["clock"])
                    g.audio.play("ui_click", 0.6)

    def _begin_dossier(self, shot):
        g = self.game
        if shot.get("backdrop", "black") == "black":
            self.black.show()
        else:
            self.black.show()
            self.black["frameColor"] = (0, 0, 0, 0.6)
        g.postfx.set_override(dict(FILM_GRADE, grain=0.06))
        card = self.ui.attach_new_node("dossier")
        DirectFrame(parent=card, frameColor=(0.83, 0.79, 0.68, 1), frameSize=(-0.75, 0.75, -0.48, 0.48))
        DirectFrame(parent=card, frameColor=(0.7, 0.66, 0.55, 1), frameSize=(-0.75, 0.75, 0.36, 0.48))
        OnscreenText(parent=card, text=shot.get("header", "REPUBLIC INTELLIGENCE  -  PERSONNEL FILE"), pos=(-0.7, 0.41),
                     scale=0.035, fg=(0.15, 0.13, 0.1, 1), align=TextNode.A_left)
        photo = DirectFrame(parent=card, frameColor=(0.2, 0.2, 0.2, 1), frameSize=(-0.68, -0.3, -0.3, 0.3))
        OnscreenText(parent=photo, text=shot.get("photo_text", "NO PHOTO\nON FILE"), pos=(-0.49, 0.02), scale=0.035,
                     fg=(0.6, 0.6, 0.6, 1))
        fields = [("NAME", shot.get("name", "")), ("RANK", shot.get("rank", "")), ("ROLE", shot.get("role", "")),
                  ("STATUS", shot.get("status", ""))]
        self.dossier_lines = []
        y = 0.25
        for label, value in fields:
            OnscreenText(parent=card, text=label, pos=(-0.22, y), scale=0.032, fg=(0.35, 0.3, 0.25, 1),
                         align=TextNode.A_left)
            t = OnscreenText(parent=card, text="", pos=(0.02, y), scale=0.036, fg=(0.1, 0.09, 0.08, 1),
                             align=TextNode.A_left, mayChange=True)
            self.dossier_lines.append((t, value))
            y -= 0.08
        notes = OnscreenText(parent=card, text="", pos=(-0.22, -0.1), scale=0.03, fg=(0.15, 0.13, 0.1, 1),
                             align=TextNode.A_left, wordwrap=22, mayChange=True)
        self.dossier_lines.append((notes, shot.get("notes", "")))
        stamp = OnscreenText(parent=card, text=shot.get("stamp", ""), pos=(0.38, -0.32), scale=0.1,
                             fg=(0.7, 0.08, 0.06, 0.85), mayChange=True)
        stamp.set_r(-12)
        stamp.hide()
        self.stamp = stamp
        self._stamped = False
        self.dossier = card

    def _update_dossier(self, shot, k):
        start = 0.4
        for t, value in self.dossier_lines:
            n = int(max(0.0, (self.t - start)) * 40)
            t.setText(value[:n])
            start += len(value) / 40.0 + 0.1
        if shot.get("stamp") and not self._stamped and self.t >= shot.get("stamp_t", start + 0.3):
            self._stamped = True
            self.stamp.show()
            self.game.audio.play("impact_hard", 0.8)
        self.dossier.set_scale(1.0 + 0.04 * k)

    # ------------------------------------------------------------------ cleanup per shot
    def _end_shot(self):
        g = self.game
        if self.region_map is not None:
            self.region_map.remove()
            self.region_map = None
        if self.sat_overlay is not None:
            self.sat_overlay.remove_node()
            self.sat_overlay = None
        for _, node in self.markers:
            node.remove_node()
        self.markers = []
        if self.arrows3d is not None:
            self.arrows3d.remove_node()
            self.arrows3d = None
        if self.dossier is not None:
            self.dossier.remove_node()
            self.dossier = None
        for n in self.title_nodes:
            n.destroy()
        self.title_nodes = []
        self.black.hide()
        self.black["frameColor"] = (0, 0, 0, 1)
        self._clear_actors()
        if getattr(self, "_rain_before", None) is not None and g.weather is not None:
            g.weather.set_intensity(self._rain_before)
            self._rain_before = None
        for p in self.puppets:
            p.remove()
        self.puppets = []
        g.postfx.set_dof(None)
        if self._fog is not None:
            g.render.set_fog(self._fog)
        g.camLens.set_far(self._far)
        if g.weather is not None and g.weather.intensity > 0:
            g.weather.root.show()

    def _clear_actors(self):
        g = self.game
        for s in self.actors:
            if s in g.soldiers.soldiers:
                g.soldiers.combat.unregister(s)
                if s.model:
                    s.model.remove()
                g.soldiers.soldiers.remove(s)
        self.actors = []
        for v in self.vehicles:
            g.vehicles.remove(v)
        self.vehicles = []

    # ------------------------------------------------------------------ per frame
    def update(self, dt):
        if self.done:
            return
        voice = getattr(self.game, "voice", None)
        speaking = voice is not None and voice.speaking()
        self.t += dt
        self._dt = dt
        shot = self.shots[self.index]
        # Narration: one line after another, never cut off.
        if self.line_i < len(self.lines):
            self.line_wait -= dt
            if self.line_wait <= 0.0 and not speaking:
                line = self.lines[self.line_i]
                speaker = line.get("speaker", "narrator")
                name = "" if speaker == "narrator" else self.game.campaign.speaker_name(speaker)
                self.subtitle.setText(f"{name}:  {line['text']}" if name else line["text"])
                length = voice.play(speaker, line["text"]) if voice is not None else 0.0
                self.line_wait = (length if length > 0 else self._line_seconds(line)) + 0.2
                self.line_i += 1
        elif self.line_wait > 0.0:
            self.line_wait -= dt
            if self.line_wait <= 0.0:
                self.subtitle.setText("")
        # Typed captions.
        c1, c2, _ = self._typed
        n = int(max(0.0, self.t - 0.3) * 30)
        self.caption.setText(c1[:n])
        self.caption2.setText(c2[:max(0, n - len(c1))])
        k = _smooth(min(1.0, self.t / max(0.1, self.duration)))
        getattr(self, f"_update_{shot['type']}")(shot, k)
        talking_done = self.line_i >= len(self.lines) and not speaking
        if self.t >= self.duration and talking_done:
            self.subtitle.setText("")
            self._next_shot()

    def skip(self):
        self.finish()

    def finish(self):
        if self.done:
            return
        self.done = True
        g = self.game
        self._end_shot()
        if self.set_node is not None:
            self.set_node.remove_node()
            self.set_node = None
        voice = getattr(g, "voice", None)
        if voice is not None:
            voice.stop()
        for n in (self.caption, self.caption2, self.subtitle, self.skip_hint):
            n.destroy()
        for b in self.bars:
            b.destroy()
        self.black.destroy()
        self.ui.remove_node()
        g.postfx.set_override(g.nvg_grading() if g.nvg_on else None)
        g.camLens.set_fov(g.player.camera.base_fov)
        g.soldiers.player_hidden = False
        g.effects.clear()
        while len(g.fires) > self.fires_before:
            f = g.fires.pop()
            f["glow"].remove_node()
        self.on_done()
