"""Player-adjustable settings and their JSON storage.

Settings are saved to a JSON file so they survive restarting the game.
A missing file is created with defaults. A corrupted file is backed up
(settings.json.corrupt) and replaced with defaults - the game never crashes
because of a bad settings file.
"""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

GRAPHICS_QUALITY_LEVELS = ("low", "medium", "high")
SHADOW_QUALITY_LEVELS = ("off", "low", "medium", "high")
DIFFICULTY_LEVELS = ("easy", "normal", "hard")

# Shadow map resolution (pixels) and the size of the area around the player that gets shadows (metres).
SHADOW_MAP_SIZES = {"off": 0, "low": 1024, "medium": 2048, "high": 4096}
SHADOW_FILM_SIZES = {"off": 0.0, "low": 60.0, "medium": 80.0, "high": 100.0}

GRAPHICS_PRESETS = {
    "low": {"view_distance": 220.0, "msaa": 0, "anisotropy": 1},
    "medium": {"view_distance": 350.0, "msaa": 2, "anisotropy": 4},
    "high": {"view_distance": 480.0, "msaa": 4, "anisotropy": 8},
}

SUPPORTED_RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]


@dataclass
class Settings:
    mouse_sensitivity: float = 1.0
    invert_mouse_y: bool = False
    field_of_view: float = 90.0
    master_volume: float = 0.8
    music_volume: float = 0.6
    sfx_volume: float = 0.9
    graphics_quality: str = "medium"
    shadow_quality: str = "medium"
    resolution: tuple = (1280, 720)
    fullscreen: bool = False
    vsync: bool = True
    show_fps: bool = False
    difficulty: str = "normal"

    @property
    def preset(self) -> dict:
        return GRAPHICS_PRESETS[self.graphics_quality]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["resolution"] = list(self.resolution)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        """Build settings from untrusted JSON data. Bad or missing values fall back to defaults."""
        d = cls()
        if not isinstance(data, dict):
            return d
        return cls(
            mouse_sensitivity=_float(data.get("mouse_sensitivity"), d.mouse_sensitivity, 0.1, 5.0),
            invert_mouse_y=_bool(data.get("invert_mouse_y"), d.invert_mouse_y),
            field_of_view=_float(data.get("field_of_view"), d.field_of_view, 60.0, 110.0),
            master_volume=_float(data.get("master_volume"), d.master_volume, 0.0, 1.0),
            music_volume=_float(data.get("music_volume"), d.music_volume, 0.0, 1.0),
            sfx_volume=_float(data.get("sfx_volume"), d.sfx_volume, 0.0, 1.0),
            graphics_quality=_choice(data.get("graphics_quality"), GRAPHICS_QUALITY_LEVELS, d.graphics_quality),
            shadow_quality=_choice(data.get("shadow_quality"), SHADOW_QUALITY_LEVELS, d.shadow_quality),
            resolution=_resolution(data.get("resolution"), d.resolution),
            fullscreen=_bool(data.get("fullscreen"), d.fullscreen),
            vsync=_bool(data.get("vsync"), d.vsync),
            show_fps=_bool(data.get("show_fps"), d.show_fps),
            difficulty=_choice(data.get("difficulty"), DIFFICULTY_LEVELS, d.difficulty),
        )


def _float(value, default, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = float(value)
    if math.isnan(value) or math.isinf(value):
        return default
    return min(hi, max(lo, value))


def _bool(value, default):
    return value if isinstance(value, bool) else default


def _choice(value, options, default):
    return value if value in options else default


def _resolution(value, default):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return default
    w, h = value
    if isinstance(w, bool) or isinstance(h, bool) or not isinstance(w, int) or not isinstance(h, int):
        return default
    if not (640 <= w <= 7680 and 480 <= h <= 4320):
        return default
    return (w, h)


class SettingsStore:
    """Loads and saves Settings to a JSON file."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> Settings:
        if not self.path.exists():
            settings = Settings()
            self.save(settings)
            return settings
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("settings file does not contain a JSON object")
        except (OSError, ValueError) as exc:
            log.warning("Settings file %s is unreadable (%s). Using defaults.", self.path, exc)
            self._backup_corrupt_file()
            settings = Settings()
            self.save(settings)
            return settings
        return Settings.from_dict(data)

    def save(self, settings: Settings) -> bool:
        """Write settings atomically (temp file + rename) so a crash never leaves a half-written file."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.error("Could not save settings to %s: %s", self.path, exc)
            return False

    def _backup_corrupt_file(self):
        try:
            os.replace(self.path, self.path.with_name(self.path.name + ".corrupt"))
        except OSError as exc:
            log.warning("Could not back up corrupt settings file: %s", exc)
