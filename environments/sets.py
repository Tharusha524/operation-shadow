"""Indoor film sets for the story videos (built far below the map, lit by their own lamps).

  bunker   Varn command bunker in Vorsk: map table, wall screens, red banners, a desk for signing orders
  canteen  the mess hall at Outpost Ridgeback at dawn: tables, benches, coffee, windows
  office   Republic Intelligence office in Aldmere: desk, chairs, cabinets, window, flag

All coordinates in the story files are relative to the set's origin (SET_ORIGIN).
"""
from __future__ import annotations

from panda3d.core import AmbientLight, NodePath, PointLight, Spotlight, TextNode

from environments.geometry import MeshBuilder

SET_ORIGIN = (0.0, 0.0, -150.0)
CONCRETE = (0.42, 0.42, 0.41)
DARK = (0.12, 0.12, 0.13)
WOOD = (0.42, 0.3, 0.2)
STEEL = (0.45, 0.47, 0.5)
RED = (0.55, 0.06, 0.05)
BLUE = (0.12, 0.22, 0.45)


def _room(mb, w, d, h, wall=CONCRETE, floor=(0.3, 0.3, 0.3), ceiling=(0.25, 0.25, 0.25), windows=()):
    hw, hd = w / 2, d / 2
    mb.box("concrete", 0, 0, -0.2, w + 0.6, d + 0.6, 0.2, floor)
    mb.box("concrete", 0, 0, h, w + 0.6, d + 0.6, 0.2, ceiling, bottom=True)
    mb.box("block", 0, hd + 0.15, 0, w + 0.6, 0.3, h, wall)                       # back wall (+Y)
    mb.box("block", 0, -hd - 0.15, 0, w + 0.6, 0.3, h, wall)                      # front wall (camera side)
    for sx in (-1, 1):
        mb.box("block", sx * (hw + 0.15), 0, 0, 0.3, d, h, wall)
    for x, y, ww, hh, z in windows:                                               # bright window panes
        mb.box("emissive", x, y, z, ww, 0.05, hh, (1.0, 0.92, 0.75))


def _table(mb, x, y, w, d, h=0.78, top=WOOD):
    mb.box("wood", x, y, h - 0.05, w, d, 0.05, top)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box("metal", x + sx * (w / 2 - 0.06), y + sy * (d / 2 - 0.06), 0, 0.06, 0.06, h - 0.05, DARK)


def _chair(mb, x, y, h=0.45, yaw=0.0):
    with mb.place(x, y, 0, yaw):
        mb.box("wood", 0, 0, h - 0.04, 0.46, 0.46, 0.05, WOOD)
        mb.box("wood", 0, -0.21, h, 0.46, 0.04, 0.5, WOOD)                       # back rest behind (-Y)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box("metal", sx * 0.2, sy * 0.2, 0, 0.03, 0.03, h - 0.04, DARK)


def _lamp(parent, pos, color=(1.0, 0.85, 0.6), power=6.0, atten=0.18, name="lamp"):
    light = PointLight(name)
    light.set_color((color[0] * power, color[1] * power, color[2] * power, 1))
    light.set_attenuation((1.0, 0.0, atten))
    np_ = parent.attach_new_node(light)
    np_.set_pos(*pos)
    parent.set_light(np_)
    return np_


def _text(parent, text, pos, scale, color, hpr=(0, 0, 0)):
    tn = TextNode("sign")
    tn.set_text(text)
    tn.set_align(TextNode.A_center)
    tn.set_text_color(*color)
    np_ = parent.attach_new_node(tn)
    np_.set_pos(*pos)
    np_.set_hpr(*hpr)
    np_.set_scale(scale)
    np_.set_light_off(1)
    return np_


def build_bunker(mb, banner=RED):
    _room(mb, 16, 12, 3.6, wall=(0.36, 0.36, 0.35), floor=(0.22, 0.22, 0.22))
    _table(mb, 0, 1.0, 6.0, 2.6, 0.92, top=(0.2, 0.2, 0.2))                   # the map table
    for i in range(3):                                                         # wall screens
        x = -4.5 + i * 4.5
        mb.box("paint", x, 5.82, 1.4, 3.4, 0.12, 1.9, DARK)
    for x in (-7.2, 7.2):                                                      # Directorate banners
        mb.box("fabric", x, 5.8, 0.6, 1.2, 0.05, 2.8, banner)
        mb.box("paint", x, 5.77, 2.2, 0.5, 0.02, 0.5, (0.05, 0.05, 0.05))
    _table(mb, -5.5, -2.5, 2.2, 1.1, 0.76)                                     # desk where the order is signed
    mb.box("paint", -5.4, -2.5, 0.765, 0.5, 0.35, 0.01, (0.92, 0.9, 0.84))     # the order
    _chair(mb, -5.5, -3.25, yaw=0)
    for i, x in enumerate((-2.2, 0.0, 2.2)):
        _chair(mb, x, -0.8, yaw=0)
    for sx in (-1, 1):                                                         # pipes, cables, radio racks
        mb.cylinder_between("metal", (sx * 7.7, -5.8, 3.3), (sx * 7.7, 5.8, 3.3), 0.08, STEEL, segments=6)
        mb.box("metal", sx * 7.3, -3.5, 0, 0.6, 1.2, 2.0, (0.2, 0.22, 0.2))
        for k in range(5):
            mb.box("emissive", sx * 7.0, -3.9 + k * 0.2, 1.3, 0.02, 0.06, 0.04, (0.3, 1.0, 0.4))
    mb.box("paint", 6.6, -5.6, 2.3, 0.6, 0.06, 0.6, (0.85, 0.85, 0.8))           # wall clock
    for x in (-3, 0, 3):
        mb.box("emissive", x, 1.0, 3.35, 0.6, 0.6, 0.05, (1.0, 0.85, 0.6))     # ceiling lights


def build_canteen(mb):
    _room(mb, 12, 8, 3.0, wall=(0.62, 0.6, 0.54), floor=(0.4, 0.37, 0.32), ceiling=(0.55, 0.53, 0.5),
          windows=[(-3, 4.0, 1.6, 1.0, 1.1), (1.5, 4.0, 1.6, 1.0, 1.1), (-6.0, 0, 0.05, 0, 0)])
    for y in (-1.4, 1.4):
        _table(mb, -1.0, y, 4.2, 0.9, 0.76)
        for sy in (-1, 1):
            mb.box("wood", -1.0, y + sy * 0.75, 0.42, 4.0, 0.32, 0.05, WOOD)    # benches
            for sx in (-1.8, 1.8):
                mb.box("metal", -1.0 + sx, y + sy * 0.75, 0, 0.05, 0.25, 0.42, DARK)
        for k in range(3):
            mb.cylinder("metal", -2.4 + k * 1.3, y + 0.15, 0.76, 0.045, 0.1, (0.85, 0.85, 0.82), segments=8)  # mugs
    mb.box("metal", 4.6, 3.3, 0, 2.2, 0.7, 0.92, STEEL)                          # counter
    mb.cylinder("metal", 4.2, 3.3, 0.92, 0.18, 0.5, (0.7, 0.7, 0.72), segments=10)  # coffee urn
    mb.box("paint", 5.8, -1.0, 1.0, 0.04, 1.6, 1.0, (0.2, 0.3, 0.2))             # notice board
    for k in range(4):
        mb.box("paint", 5.77, -1.6 + k * 0.4, 1.2 + (k % 2) * 0.3, 0.01, 0.25, 0.32, (0.9, 0.88, 0.8))


def build_office(mb):
    _room(mb, 8, 6, 3.0, wall=(0.6, 0.62, 0.64), floor=(0.33, 0.25, 0.18), ceiling=(0.7, 0.7, 0.7),
          windows=[(1.5, 3.0, 2.4, 1.4, 0.9)])
    _table(mb, 0, 1.0, 2.0, 1.0, 0.76)
    mb.box("paint", 0.3, 1.0, 0.765, 0.4, 0.3, 0.02, (0.85, 0.82, 0.7))           # case file
    mb.box("metal", -0.6, 1.2, 0.765, 0.12, 0.12, 0.45, (0.15, 0.15, 0.15))       # desk lamp
    _chair(mb, 0, 1.75, yaw=180)
    _chair(mb, 0.8, -0.6, yaw=0)
    for k in range(3):
        mb.box("metal", -3.6, -1.6 + k * 0.6, 0, 0.6, 0.55, 1.3, (0.4, 0.42, 0.4))   # filing cabinets
    mb.cylinder("metal", 3.4, 2.4, 0, 0.03, 2.3, (0.7, 0.6, 0.3), segments=6)     # flag pole + flag
    mb.box("fabric", 3.4, 2.15, 1.5, 0.04, 0.55, 0.8, BLUE)
    mb.box("paint", -1.5, 2.86, 1.4, 1.2, 0.02, 0.8, (0.85, 0.85, 0.8))           # framed map
    mb.box("paint", -1.5, 2.85, 1.45, 1.0, 0.02, 0.6, (0.3, 0.38, 0.25))


def build_apartment(mb):
    """Crane's flat at night: desk with photographs, sofa, city lights through the window."""
    _room(mb, 7, 5, 2.7, wall=(0.48, 0.44, 0.4), floor=(0.3, 0.22, 0.16), ceiling=(0.5, 0.48, 0.45))
    mb.box("emissive", 1.2, 2.5, 0.9, 2.6, 0.04, 1.3, (0.12, 0.16, 0.3))           # night window
    for k in range(9):
        mb.box("emissive", 0.0 + k * 0.3, 2.47, 1.0 + (k * 37 % 9) * 0.1, 0.05, 0.01, 0.07, (1.0, 0.8, 0.45))
    _table(mb, -1.4, 1.6, 1.6, 0.8, 0.76)
    for k in range(5):                                                             # photographs and files
        mb.box("paint", -2.0 + k * 0.3, 1.5 + (k % 2) * 0.15, 0.765, 0.2, 0.15, 0.005, (0.85, 0.83, 0.78))
    mb.box("metal", -0.8, 1.85, 0.765, 0.1, 0.1, 0.4, DARK)                          # desk lamp
    _chair(mb, -1.4, 0.95, yaw=0)
    mb.box("fabric", 2.0, -1.4, 0, 2.2, 0.9, 0.45, (0.25, 0.27, 0.3))                # sofa
    mb.box("fabric", 2.0, -1.8, 0.45, 2.2, 0.2, 0.45, (0.25, 0.27, 0.3))
    mb.box("wood", -3.2, -1.2, 0, 0.4, 1.6, 1.9, WOOD)                               # bookshelf


def build_villa(mb):
    """Mira Sol's living room: big window over the lake at sunset, sofa, a table covered in documents."""
    _room(mb, 12, 9, 3.4, wall=(0.82, 0.78, 0.7), floor=(0.55, 0.42, 0.3), ceiling=(0.85, 0.82, 0.78))
    mb.box("emissive", 0, 4.5, 0.4, 8.0, 0.05, 2.6, (1.0, 0.72, 0.45))               # sunset over the lake
    mb.box("emissive", 0, 4.47, 0.4, 8.0, 0.01, 0.9, (0.35, 0.5, 0.65))              # the water
    for x in (-4, 0, 4):
        mb.box("metal", x, 4.45, 0.4, 0.12, 0.08, 2.6, (0.2, 0.2, 0.2))              # window frames
    mb.box("fabric", -3.0, 0.5, 0, 2.6, 1.0, 0.45, (0.75, 0.72, 0.65))               # sofa
    mb.box("fabric", -3.0, 0.05, 0.45, 2.6, 0.2, 0.5, (0.75, 0.72, 0.65))
    _table(mb, 1.8, 0.6, 2.2, 1.2, 0.76, top=(0.25, 0.2, 0.16))
    for k in range(6):
        mb.box("paint", 1.0 + k * 0.3, 0.5 + (k % 3) * 0.2, 0.765, 0.22, 0.3, 0.005, (0.92, 0.9, 0.84))
    mb.box("paint", 4.5, -4.35, 1.2, 2.0, 0.03, 1.2, (0.3, 0.38, 0.25))              # map on the wall
    mb.box("wood", -5.6, -2.0, 0, 0.5, 2.4, 1.0, (0.35, 0.25, 0.18))                 # sideboard
    mb.cylinder("metal", -5.6, -1.4, 1.0, 0.06, 0.3, (0.6, 0.55, 0.3), segments=8)   # lamp


def build_storage(mb):
    """Warehouse corner where Brandt is held: crates, a chair, one bare bulb."""
    _room(mb, 12, 10, 5.0, wall=(0.4, 0.4, 0.38), floor=(0.28, 0.28, 0.27), ceiling=(0.2, 0.2, 0.2))
    for x, y in ((-4, 3), (-4.6, 1.6), (-3.2, 3.2), (4, 3.5), (4.5, 2.0), (3.0, 3.6), (-4.5, -2.5)):
        mb.box("wood", x, y, 0, 1.2, 1.2, 1.2, (0.45, 0.36, 0.24))
    mb.box("wood", -4.0, 3.0, 1.2, 1.2, 1.2, 1.2, (0.42, 0.33, 0.22))
    _chair(mb, 0, 0.4, yaw=180)
    mb.cylinder("metal", 0, 0.4, 3.0, 0.01, 2.0, DARK, segments=4)                   # bulb cable
    mb.box("emissive", 0, 0.4, 2.9, 0.12, 0.12, 0.15, (1.0, 0.85, 0.6))


def build_terminal_room(mb):
    """Harbour office at night: a computer desk, filing cabinets, rain on the window."""
    _room(mb, 8, 6, 2.9, wall=(0.55, 0.57, 0.6), floor=(0.3, 0.3, 0.32), ceiling=(0.6, 0.6, 0.6))
    mb.box("emissive", -1.5, 3.0, 0.9, 2.4, 0.04, 1.3, (0.16, 0.2, 0.26))           # rainy night window
    _table(mb, 1.0, 1.6, 1.8, 0.8, 0.76)
    mb.box("metal", 1.0, 1.8, 0.77, 0.6, 0.05, 0.42, DARK)                           # monitor
    mb.box("emissive", 1.0, 1.77, 0.8, 0.55, 0.01, 0.36, (0.3, 0.6, 0.95))
    mb.box("metal", 1.0, 1.45, 0.765, 0.45, 0.15, 0.025, (0.15, 0.15, 0.15))         # keyboard
    _chair(mb, 1.0, 0.95, yaw=0)
    for k in range(4):
        mb.box("metal", -3.6, -2.0 + k * 0.6, 0, 0.6, 0.55, 1.3, (0.4, 0.42, 0.4))


SETS = {"bunker": build_bunker, "canteen": build_canteen, "office": build_office, "apartment": build_apartment,
        "villa": build_villa, "storage": build_storage, "terminal": build_terminal_room,
        "bunker_kareth": lambda mb: build_bunker(mb, banner=BLUE)}


def build_set(name, materials, region_texture=None):
    """Return a NodePath with the set geometry and its lights, placed at SET_ORIGIN."""
    root = NodePath(f"set_{name}")
    mb = MeshBuilder(materials.uv_scales())
    SETS[name](mb)
    mb.build(root, materials, name=f"set_{name}_geo")
    root.set_pos(*SET_ORIGIN)
    amb = AmbientLight("set_ambient")
    if name in ("bunker", "bunker_kareth"):
        amb.set_color((0.16, 0.15, 0.16, 1))
        for x in (-3, 0, 3):
            _lamp(root, (x, 1.0, 3.0), (1.0, 0.82, 0.55), 4.5, 0.12)
        _lamp(root, (0, 5.0, 1.8), (0.4, 0.55, 1.0), 2.0, 0.25, "screens")
        if region_texture is not None:                                      # the war map on the table & screens
            from panda3d.core import CardMaker
            cm = CardMaker("map")
            cm.set_frame(-2.9, 2.9, -1.2, 1.2)
            table = root.attach_new_node(cm.generate())
            table.set_p(-90)
            table.set_pos(0, 1.0, 0.93)
            table.set_texture(region_texture)
            for i in range(3):
                cm.set_frame(-1.6, 1.6, -0.85, 0.85)
                screen = root.attach_new_node(cm.generate())
                screen.set_pos(-4.5 + i * 4.5, 5.75, 2.35)          # a card faces -Y: into the room
                screen.set_texture(region_texture)
                screen.set_light_off(1)
                screen.set_color_scale(0.6, 0.75, 1.0, 1)
        _text(root, "23:58", (6.6, -5.55, 2.55), 0.18, (0.1, 0.1, 0.1, 1), hpr=(180, 0, 0)).set_name("clock")
    elif name == "apartment":
        amb.set_color((0.1, 0.11, 0.15, 1))
        _lamp(root, (-0.8, 1.85, 1.3), (1.0, 0.8, 0.55), 3.0, 0.3, "desk_lamp")
        _lamp(root, (1.2, 2.2, 1.6), (0.4, 0.5, 0.9), 1.5, 0.2, "window")
    elif name == "villa":
        amb.set_color((0.3, 0.27, 0.24, 1))
        _lamp(root, (0, 3.6, 1.8), (1.0, 0.7, 0.45), 5.0, 0.05, "sunset")
        _lamp(root, (-5.6, -1.4, 1.5), (1.0, 0.85, 0.6), 2.0, 0.2, "lamp")
    elif name == "storage":
        amb.set_color((0.05, 0.05, 0.06, 1))
        _lamp(root, (0, 0.4, 2.7), (1.0, 0.82, 0.55), 5.0, 0.12, "bulb")
    elif name == "terminal":
        amb.set_color((0.12, 0.13, 0.16, 1))
        _lamp(root, (1.0, 1.6, 1.0), (0.4, 0.65, 1.0), 2.5, 0.4, "screen")
        _lamp(root, (0, 0, 2.7), (0.9, 0.9, 0.85), 1.5, 0.15, "ceiling")
    elif name == "canteen":
        amb.set_color((0.28, 0.27, 0.25, 1))
        _lamp(root, (-1, 0, 2.8), (1.0, 0.9, 0.72), 3.0, 0.1)
        _lamp(root, (-1, 3.6, 1.6), (1.0, 0.8, 0.6), 3.5, 0.08, "dawn")       # sunrise through the windows
    else:
        amb.set_color((0.3, 0.3, 0.32, 1))
        _lamp(root, (0, 0.5, 2.8), (1.0, 0.95, 0.85), 3.0, 0.1)
        _lamp(root, (1.5, 2.6, 1.6), (0.9, 0.95, 1.0), 3.0, 0.1, "window")
    amb_np = root.attach_new_node(amb)
    root.set_light(amb_np)
    return root


class _MaterialsProxy:
    """The material library is needed to build the NPC rifle; the game sets it once."""
    materials = None

    @classmethod
    def get(cls):
        return cls.materials


class Puppet:
    """An animated character for story scenes (no AI): plays one action, can walk along a path."""

    MODELS = {"officer": "actor_officer", "man": "actor_man", "woman": "actor_woman",
              "friendly": "soldier_friend", "enemy": "soldier_enemy"}

    def __init__(self, parent, spec, offset=(0.0, 0.0, 0.0)):
        from direct.actor.Actor import Actor
        from panda3d.core import Filename
        from core.paths import ASSETS_DIR
        model = self.MODELS.get(spec.get("model", "man"), "actor_man")
        self.root = parent.attach_new_node("puppet")
        self.actor = Actor(Filename.from_os_specific(str(ASSETS_DIR / "models" / f"{model}.bam")))
        self.actor.reparent_to(self.root)
        self.actor.set_h(180)
        self.offset = offset
        self.path = [tuple(p) for p in spec.get("path", [])]
        self.speed = float(spec.get("speed", 1.3))
        self.start = float(spec.get("start", 0.0))
        self.after = spec.get("then")                      # action after the walk ends
        self.move = spec.get("move", "walk")               # walk / run / injured_walk along the path
        self.anim = spec.get("anim", "stand")
        self.dist = 0.0
        x, y = spec.get("pos", self.path[0][:2] if self.path else (0, 0))
        z = spec.get("z", 0.0)
        self.root.set_pos(x + offset[0], y + offset[1], z + offset[2])
        self.root.set_h(spec.get("heading", 0.0))
        if spec.get("dark"):
            self.actor.set_color_scale(0.25, 0.25, 0.27, 1)      # a figure in the shadows
        else:
            boost = 1.3 if model in ("soldier_enemy", "soldier_friend") else 1.1
            self.actor.set_color_scale(boost, boost, boost, 1)
        self.actor.setPlayRate(float(spec.get("rate", 1.0)), self.anim)
        self.actions = sorted(spec.get("actions", []), key=lambda a: a["t"])   # change action over time
        self.gun = None
        if model in ("soldier_friend", "soldier_enemy") and spec.get("gun", True):
            from enemies.soldier_model_mixamo import _rifle
            self.right_hand = self.actor.exposeJoint(None, "modelRoot", "mixamorig:RightHand")
            self.left_hand = self.actor.exposeJoint(None, "modelRoot", "mixamorig:LeftHand")
            self.gun = self.root.attach_new_node("gun")
            _rifle(_MaterialsProxy.get()).instance_to(self.gun)
            self._gun_rel = None
        self.walking = bool(self.path)
        self.actor.loop(self.move if self.walking and self.start <= 0 else self.anim)
        if spec.get("frame") is not None:
            frame = int(spec["frame"])
            if frame < 0:
                frame = self.actor.getNumFrames(self.anim) + frame
            self.actor.pose(self.anim, frame)

    def _place_gun(self):
        from panda3d.core import LVector3
        r = self.right_hand.get_pos(self.root)
        lh = self.left_hand.get_pos(self.root)
        if 0.15 < (lh - r).length() < 0.75:
            self.gun.set_pos(r)
            self.gun.look_at(lh, LVector3(0, 0, 1))
            self._gun_rel = self.gun.get_transform(self.right_hand)
        elif self._gun_rel is not None:
            self.gun.set_transform(self.right_hand, self._gun_rel)
        else:
            self.gun.set_pos(r)

    def update(self, t, dt):
        if self.gun is not None:
            self._place_gun()
        while self.actions and t >= self.actions[0]["t"]:
            act = self.actions.pop(0)
            if "heading" in act:
                self.root.set_h(act["heading"])
            if "anim" in act:
                self.anim = act["anim"]
                self.walking = False
                self.actor.loop(act["anim"])
        if not self.walking or t < self.start:
            return
        if self.actor.getCurrentAnim() != self.move:
            self.actor.loop(self.move)
        self.dist += self.speed * dt
        acc = 0.0
        for a, b in zip(self.path, self.path[1:]):
            seg = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            if self.dist <= acc + seg:
                f = (self.dist - acc) / max(seg, 1e-6)
                x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                import math
                self.root.set_pos(x + self.offset[0], y + self.offset[1], self.root.get_z())
                self.root.set_h(math.degrees(math.atan2(-(b[0] - a[0]), b[1] - a[1])))
                return
            acc += seg
        self.walking = False
        if self.after:
            self.root.set_h(self.after.get("heading", self.root.get_h()))
            self.actor.loop(self.after.get("anim", "stand"))

    def remove(self):
        self.actor.cleanup()
        self.root.remove_node()
