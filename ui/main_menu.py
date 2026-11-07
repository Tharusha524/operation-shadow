"""Main menu over a slowly orbiting 3D view of the outpost."""
from __future__ import annotations

import math

import numpy as np
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import TextNode, TransparencyAttrib

from config import constants as C
from environments.materials import array_to_texture
from ui import style
from ui.style import Screen


def _gradient_texture(size=256):
    """Dark vignette + left-side darkening so the menu text stays readable over the 3D scene."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / (size - 1)
    vign = np.clip(np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2) * 1.6, 0, 1) ** 1.8
    left = np.clip(1.0 - x * 1.6, 0, 1) ** 1.2
    a = np.clip(0.25 + vign * 0.55 + left * 0.55, 0, 0.92)
    rgb = np.zeros((size, size, 3), np.float32) + np.array([0.02, 0.03, 0.02], np.float32)
    return array_to_texture("menu_gradient", np.concatenate([rgb, a[..., None]], -1))


class MainMenu(Screen):
    def __init__(self, game, on_new, on_continue, on_select, on_settings, on_controls, on_credits, on_exit):
        super().__init__(game)
        overlay = OnscreenImage(image=_gradient_texture(), parent=self.root, scale=(2.2, 1, 1.05))
        overlay.set_transparency(TransparencyAttrib.M_alpha)
        overlay.set_bin("background", 10)          # draw behind the menu text
        self.scan = DirectFrame(parent=self.root, frameColor=(0.95, 0.8, 0.4, 0.05), frameSize=(-3, 3, -0.004, 0.004))
        self.scan.set_bin("background", 11)
        self.left = self.anchor(game.a2dLeftCenter, "menu_left")
        self.left.set_x(0.18)
        corner = self.anchor(game.a2dBottomRight, "menu_corner")
        style.text(self.left, "OPERATION", (0, 0.66), 0.075, style.DIM)
        style.text(self.left, "SHADOW", (0, 0.5), 0.17, style.TEXT)
        style.text(self.left, "AN ORIGINAL CAMPAIGN", (0.005, 0.42), 0.035, style.ACCENT)
        names = [("NEW CAMPAIGN", on_new), ("CONTINUE", on_continue), ("MISSION SELECTION", on_select),
                 ("SETTINGS", on_settings), ("CONTROLS", on_controls), ("CREDITS", on_credits), ("EXIT GAME", on_exit)]
        self.buttons = {}
        for i, (label, cmd) in enumerate(names):
            self.buttons[label] = style.button(self.left, label, (0.0, 0.2 - i * 0.115), cmd)
        self.continue_info = style.text(self.left, "", (0.0, -0.66), 0.032, style.DIM)
        self.premise = style.text(corner, "", (-0.08, 0.5), 0.03, style.DIM, TextNode.A_right, wrap=30)
        style.text(corner, f"v{C.GAME_VERSION}", (-0.08, 0.05), 0.028, style.DIM, TextNode.A_right, may_change=False)
        self._t = 0.0

    def refresh(self, continue_label):
        """continue_label: text describing the mission Continue will start, or None to disable it."""
        from direct.gui import DirectGuiGlobals as DGG
        b = self.buttons["CONTINUE"]
        b["state"] = DGG.NORMAL if continue_label else DGG.DISABLED
        self.continue_info.setText(f"Continue: {continue_label}" if continue_label else "No campaign in progress")
        self.premise.setText(self.game.campaign.premise)

    def update(self, dt):
        self._t += dt
        self.scan.set_z(1.0 - (self._t * 0.18) % 2.0)
        # Slow orbit around the outpost.
        cam = self.game.camera
        a = self._t * 0.035 + 2.2
        cam.set_pos(math.sin(a) * 95, -math.cos(a) * 95, 28 + 6 * math.sin(self._t * 0.05))
        cam.look_at(0, 0, 3)


class ControlsScreen(Screen):
    ROWS = [
        ("Move", "W A S D"), ("Look", "Mouse"), ("Sprint", "Left Shift (hold)"), ("Jump", "Space"),
        ("Crouch", "Ctrl or C (hold)"), ("Fire", "Left mouse button"), ("Aim down sights", "Right mouse button"),
        ("Reload", "R"), ("Weapons", "1 2 3 4 / mouse wheel / Q (last weapon)"), ("Grenade: throw / switch type", "G / T"),
        ("Interact / pick up intel", "E (hold)"), ("Silent takedown", "V (behind an unaware enemy)"),
        ("Night vision", "N (night missions)"), ("Drone up / down", "Space / C (while flying the drone)"),
        ("Drive a jeep", "W S (go, reverse)  A D (steer)  Space (brake)"),
        ("Skip cutscene", "Space"), ("Pause", "Esc"), ("Debug info", "F3"),
    ]

    def __init__(self, game, on_back):
        super().__init__(game, dim=0.88)
        style.text(self.root, "CONTROLS", (-0.9, 0.72), 0.09, style.TEXT)
        for i, (action, keys) in enumerate(self.ROWS):
            z = 0.56 - i * 0.072
            style.text(self.root, action.upper(), (-0.9, z), 0.042, style.DIM, may_change=False)
            style.text(self.root, keys, (-0.2, z), 0.042, style.TEXT, may_change=False)
        style.button(self.root, "BACK", (-0.9, -0.8), on_back, width=0.4)


class CreditsScreen(Screen):
    LINES = [
        ("OPERATION SHADOW", style.TEXT, 0.08),
        ("An original single-player campaign", style.ACCENT, 0.04),
        ("", None, 0.025),
        ("Developer & script writer", style.DIM, 0.035),
        ("Tharusha Nanayakara", style.ACCENT, 0.05),
        ("", None, 0.025),
        ("Programming", style.DIM, 0.033),
        ("Python 3 and the Panda3D engine - panda3d.org (Modified BSD licence)", style.TEXT, 0.036),
        ("", None, 0.025),
        ("Art & audio", style.DIM, 0.033),
        ("Textures and props: Poly Haven - polyhaven.com (CC0)", style.TEXT, 0.036),
        ("Characters and animations: Mixamo - mixamo.com", style.TEXT, 0.036),
        ("Voices: Microsoft Windows speech (David, Zira)", style.TEXT, 0.036),
        ("Other models, sounds and music are generated by the game's own code", style.TEXT, 0.036),
        ("", None, 0.025),
        ("Story & characters", style.DIM, 0.033),
        ("Original. Any resemblance to real people or events is coincidental.", style.TEXT, 0.036),
    ]

    def __init__(self, game, on_back):
        super().__init__(game, dim=0.9)
        z = 0.7
        for line, color, scale in self.LINES:
            if line:
                style.text(self.root, line, (0, z), scale, color, TextNode.A_center, may_change=False)
            z -= scale * 1.6
        style.button(self.root, "BACK", (0, -0.82), on_back, width=0.4, align="center")
