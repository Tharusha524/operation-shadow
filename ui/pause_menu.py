"""Pause menu: Resume, Restart Mission, Settings, Main Menu, Exit Game."""
from __future__ import annotations

from panda3d.core import TextNode

from ui import style
from ui.style import Screen


class PauseMenu(Screen):
    def __init__(self, game, on_resume, on_restart, on_settings, on_menu, on_exit):
        super().__init__(game, dim=0.7)
        style.text(self.root, "PAUSED", (0, 0.42), 0.12, style.TEXT, TextNode.A_center, may_change=False)
        self.subtitle = style.text(self.root, "", (0, 0.31), 0.04, style.DIM, TextNode.A_center)
        self.objective = style.text(self.root, "", (0, 0.24), 0.036, style.ACCENT, TextNode.A_center, wrap=40)
        rows = [("RESUME", on_resume), ("RESTART MISSION", on_restart), ("SETTINGS", on_settings),
                ("MAIN MENU", on_menu), ("EXIT GAME", on_exit)]
        self.buttons = {}
        for i, (label, cmd) in enumerate(rows):
            self.buttons[label] = style.button(self.root, label, (0, 0.06 - i * 0.12), cmd, width=0.7, align="center")
        self.resume_button = self.buttons["RESUME"]

    def set_info(self, mission_title, objective):
        self.subtitle.setText(mission_title.upper())
        self.objective.setText(objective or "")
