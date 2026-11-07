"""Shared look for every menu: colours, font, buttons with hover effects, fade-in screens."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.gui.OnscreenText import OnscreenText
from direct.interval.IntervalGlobal import LerpColorScaleInterval
from panda3d.core import Filename, TextNode

from core.paths import ASSETS_DIR

log = logging.getLogger(__name__)

TEXT = (0.91, 0.89, 0.80, 1)
DIM = (0.62, 0.62, 0.55, 1)
ACCENT = (0.95, 0.76, 0.32, 1)
DANGER = (0.9, 0.3, 0.22, 1)
OK = (0.55, 0.85, 0.45, 1)
PANEL = (0.03, 0.04, 0.035, 0.86)
BUTTON = ((0.11, 0.13, 0.09, 0.92), (0.40, 0.42, 0.24, 1.0), (0.24, 0.27, 0.16, 0.98), (0.07, 0.07, 0.07, 0.55))

_font = None
_sounds = {}


def load_font(loader):
    """Use assets/fonts/ui.ttf if present, else Windows' Bahnschrift, else Panda3D's default font."""
    global _font
    candidates = [ASSETS_DIR / "fonts" / "ui.ttf", ASSETS_DIR / "fonts" / "ui.otf",
                  Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "bahnschrift.ttf"]
    for path in candidates:
        if path.is_file():
            try:
                # FontPool wants a plain string in Panda3D's path format ("/c/Windows/...").
                font = loader.load_font(Filename.from_os_specific(str(path)).get_fullpath())
                if font is not None and font.is_valid():
                    font.set_pixels_per_unit(64)
                    _font = font
                    DGG.setDefaultFont(font)
                    log.info("UI font: %s", path)
                    return font
            except Exception as exc:
                log.warning("Could not load font %s: %s", path, exc)
    return None


def set_ui_sounds(hover, click):
    _sounds["hover"], _sounds["click"] = hover, click


def text(parent, value, pos=(0, 0), scale=0.05, fg=TEXT, align=TextNode.A_left, wrap=None, may_change=True,
         shadow=(0, 0, 0, 0.8)):
    return OnscreenText(parent=parent, text=value, pos=pos, scale=scale, fg=fg, align=align, wordwrap=wrap,
                        mayChange=may_change, shadow=shadow)


def button(parent, label, pos, command, width=0.62, scale=0.055, enabled=True, extra_args=None, align="left"):
    """Military style button: dark plate, amber edge on hover, sound on hover/click."""
    half_h = 0.045
    if align == "left":
        frame = (-0.03, width, -half_h + 0.012, half_h + 0.012)
        text_pos, text_align = (0.0, 0.0), TextNode.A_left
    else:
        frame = (-width / 2, width / 2, -half_h + 0.012, half_h + 0.012)
        text_pos, text_align = (0.0, 0.0), TextNode.A_center
    b = DirectButton(
        parent=parent, text=label, command=command, extraArgs=extra_args or [], pos=(pos[0], 0, pos[1]),
        relief=DGG.FLAT, frameSize=frame, frameColor=BUTTON, text_scale=scale, text_align=text_align,
        text_pos=text_pos, text_fg=TEXT, text2_fg=ACCENT, text3_fg=(0.45, 0.45, 0.42, 1), pressEffect=1,
        rolloverSound=_sounds.get("hover"), clickSound=_sounds.get("click"),
        state=DGG.NORMAL if enabled else DGG.DISABLED,
    )
    edge = DirectFrame(parent=b, frameColor=ACCENT, frameSize=(frame[0], frame[0] + 0.008, frame[2], frame[3]))
    edge.hide()
    b.bind(DGG.ENTER, lambda _e: (edge.show(), b.set_x(pos[0] + 0.012)))
    b.bind(DGG.EXIT, lambda _e: (edge.hide(), b.set_x(pos[0])))
    return b


def panel(parent, frame, color=PANEL):
    return DirectFrame(parent=parent, frameColor=color, frameSize=frame)


class Screen:
    """A full-screen menu page that fades in and can be shown/hidden."""

    def __init__(self, game, dim=0.0):
        self.game = game
        self.root = DirectFrame(parent=game.aspect2d, frameColor=(0, 0, 0, dim), frameSize=(-4, 4, -2, 2),
                                state=DGG.NORMAL if dim > 0 else DGG.DISABLED)
        self.root.hide()
        self._fade = None
        self.anchored = []        # extra nodes pinned to screen edges (a2dLeftCenter, ...) shown with this screen

    def anchor(self, edge_node, name="anchored"):
        node = edge_node.attach_new_node(name)
        node.hide()
        self.anchored.append(node)
        return node

    def show(self):
        self.root.show()
        for node in self.anchored:
            node.show()
        if self._fade:
            self._fade.finish()
        for node in [self.root] + self.anchored:
            node.set_color_scale(1, 1, 1, 0)
        from direct.interval.IntervalGlobal import Parallel
        self._fade = Parallel(*[LerpColorScaleInterval(n, 0.25, (1, 1, 1, 1), (1, 1, 1, 0))
                                for n in [self.root] + self.anchored])
        self._fade.start()

    def hide(self):
        if self._fade:
            self._fade.finish()
            self._fade = None
        self.root.hide()
        for node in self.anchored:
            node.hide()

    @property
    def visible(self):
        return not self.root.is_hidden()

    def destroy(self):
        self.root.destroy()
