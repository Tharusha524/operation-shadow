"""Settings screen. Values apply immediately where possible and are saved when leaving the screen."""
from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectSlider
from panda3d.core import TextNode

from config.settings import (DIFFICULTY_LEVELS, GRAPHICS_QUALITY_LEVELS, SHADOW_QUALITY_LEVELS,
                             SUPPORTED_RESOLUTIONS)
from ui import style
from ui.style import Screen


class SettingsMenu(Screen):
    def __init__(self, game, on_back):
        super().__init__(game, dim=0.9)
        self.on_back = on_back
        s = game.settings
        style.text(self.root, "SETTINGS", (-1.2, 0.8), 0.09, may_change=False)
        self.note = style.text(self.root, "", (-1.2, -0.72), 0.034, style.DIM, wrap=70)
        self._labels = {}
        self._row = 0
        self._slider("Mouse sensitivity", "mouse_sensitivity", 0.1, 5.0, lambda v: f"{v:.2f}")
        self._slider("Field of view", "field_of_view", 60, 110, lambda v: f"{v:.0f} deg")
        self._slider("Master volume", "master_volume", 0, 1, lambda v: f"{v * 100:.0f}%")
        self._slider("Music volume", "music_volume", 0, 1, lambda v: f"{v * 100:.0f}%")
        self._slider("Effects volume", "sfx_volume", 0, 1, lambda v: f"{v * 100:.0f}%")
        self._cycle("Difficulty", "difficulty", DIFFICULTY_LEVELS)
        self._cycle("Graphics quality", "graphics_quality", GRAPHICS_QUALITY_LEVELS)
        self._cycle("Shadows", "shadow_quality", SHADOW_QUALITY_LEVELS)
        self._cycle("Resolution", "resolution", SUPPORTED_RESOLUTIONS, fmt=lambda r: f"{r[0]} x {r[1]}")
        self._cycle("Fullscreen", "fullscreen", (False, True), fmt=lambda b: "ON" if b else "OFF")
        self._cycle("V-Sync", "vsync", (True, False), fmt=lambda b: "ON" if b else "OFF")
        self._cycle("Show FPS", "show_fps", (False, True), fmt=lambda b: "ON" if b else "OFF")
        style.button(self.root, "BACK", (-1.2, -0.86), self._back, width=0.4)
        self.note.setText("Graphics quality and V-Sync apply after restarting the game. "
                          "Everything else applies immediately.")

    def _row_z(self):
        z = 0.62 - self._row * 0.105
        self._row += 1
        return z

    def _slider(self, label, key, lo, hi, fmt):
        z = self._row_z()
        style.text(self.root, label.upper(), (-1.2, z), 0.04, style.DIM, may_change=False)
        value = style.text(self.root, "", (0.95, z), 0.04, style.TEXT, TextNode.A_right)
        slider = DirectSlider(parent=self.root, range=(lo, hi), value=getattr(self.game.settings, key),
                              pos=(0.2, 0, z + 0.012), scale=0.5, pageSize=(hi - lo) / 20,
                              frameColor=(0.15, 0.17, 0.12, 0.9), thumb_frameColor=style.ACCENT,
                              thumb_relief=DGG.FLAT, thumb_frameSize=(-0.025, 0.025, -0.05, 0.05))

        def changed():
            v = float(slider["value"])
            setattr(self.game.settings, key, v)
            value.setText(fmt(v))
            self.game.apply_settings(key)

        slider["command"] = changed
        value.setText(fmt(getattr(self.game.settings, key)))
        self._labels[key] = (slider, value, fmt)

    def _cycle(self, label, key, options, fmt=lambda v: str(v).upper()):
        z = self._row_z()
        style.text(self.root, label.upper(), (-1.2, z), 0.04, style.DIM, may_change=False)
        value = style.text(self.root, "", (0.2, z), 0.04, style.TEXT, TextNode.A_center)
        options = list(options)

        def step(direction):
            current = getattr(self.game.settings, key)
            try:
                i = options.index(tuple(current) if isinstance(current, list) else current)
            except ValueError:
                i = 0
            new = options[(i + direction) % len(options)]
            setattr(self.game.settings, key, new)
            value.setText(fmt(new))
            self.game.apply_settings(key)

        style.button(self.root, "<", (-0.25, z), step, width=0.08, scale=0.045, extra_args=[-1], align="center")
        style.button(self.root, ">", (0.65, z), step, width=0.08, scale=0.045, extra_args=[1], align="center")
        value.setText(fmt(getattr(self.game.settings, key)))
        self._labels[key] = (None, value, fmt)

    def refresh(self):
        for key, (slider, value, fmt) in self._labels.items():
            v = getattr(self.game.settings, key)
            if slider is not None:
                slider["value"] = v
            value.setText(fmt(v))

    def _back(self):
        self.game.settings_store.save(self.game.settings)
        self.on_back()
