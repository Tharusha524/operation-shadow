"""Plays sound effects (2D and 3D-positioned), loops and music with volume settings."""
from __future__ import annotations

import logging
import random

from direct.showbase.Audio3DManager import Audio3DManager
from panda3d.core import Filename

from core.paths import ASSETS_DIR, user_data_dir
from systems.sound_synth import ensure_sounds

log = logging.getLogger(__name__)

def _pf(path):
    """Panda3D wants its own path format (forward slashes), not Windows paths."""
    return Filename.from_os_specific(str(path))


AUDIO_EXTENSIONS = (".ogg", ".wav", ".mp3", ".flac")
POOL_SIZE = 4


class AudioManager:
    def __init__(self, base, settings):
        self.base = base
        self.settings = settings
        self._paths = ensure_sounds(user_data_dir() / "cache" / "sfx")
        self._sfx = base.sfxManagerList[0] if base.sfxManagerList else None
        self._music_mgr = base.musicManager
        self.enabled = self._sfx is not None and self._sfx.is_valid()
        if not self.enabled:
            log.warning("No audio device available - the game runs silently.")
        self._a3d = Audio3DManager(self._sfx, base.camera) if self.enabled else None
        self._pools = {}
        self._pool_index = {}
        self._pos_nodes = [base.render.attach_new_node(f"sound_emitter_{i}") for i in range(24)]
        self._pos_index = 0
        self._loops = {}
        self._moving_loops = []
        self.music = None
        self.music_name = None
        self._duck = 1.0
        self._unducked = {}
        self.apply_volumes()

    # ------------------------------------------------------------------ files
    def _file_for(self, name):
        folder = ASSETS_DIR / ("music" if name.startswith("music_") else "sounds")
        for ext in AUDIO_EXTENSIONS:
            path = folder / f"{name}{ext}"
            if path.is_file():
                return path
        return self._paths.get(name)

    def _get(self, name, positional=False):
        key = (name, positional)
        pool = self._pools.get(key)
        if pool is None:
            path = self._file_for(name)
            if path is None:
                log.warning("Unknown sound '%s'", name)
                pool = []
            elif positional:
                pool = [self._a3d.load_sfx(_pf(path)) for _ in range(POOL_SIZE)]
            else:
                pool = [self.base.loader.load_sfx(_pf(path)) for _ in range(POOL_SIZE)]
            self._pools[key] = pool
            self._pool_index[key] = 0
        if not pool:
            return None
        i = self._pool_index[key]
        self._pool_index[key] = (i + 1) % len(pool)
        return pool[i]

    def preload(self, positional_names=("shot_enemy", "explosion", "impact_hard", "grenade_bounce",
                                        "enemy_shout_0", "enemy_shout_1", "enemy_shout_2")):
        """Load every sound now, so nothing stutters the first time it plays."""
        if not self.enabled:
            return
        for name in self._paths:
            if not name.startswith("music_") and not name.endswith("_loop"):
                self._get(name)
        for name in positional_names:
            self._get(name, positional=True)

    # ------------------------------------------------------------------ playback
    def play(self, name, volume=1.0, rate=1.0, variation=0.0):
        """Non-positional sound (the player's own weapon, UI)."""
        if not self.enabled:
            return
        snd = self._get(name)
        if snd is None:
            return
        snd.stop()
        snd.set_volume(volume)
        snd.set_play_rate(rate * (1.0 + random.uniform(-variation, variation)))
        snd.play()

    def play_at(self, name, position, volume=1.0, rate=1.0, variation=0.05, min_distance=4.0):
        """3D sound that comes from a point in the world (enemy gunfire, explosions)."""
        if not self.enabled:
            return
        snd = self._get(name, positional=True)
        if snd is None:
            return
        node = self._pos_nodes[self._pos_index]
        self._pos_index = (self._pos_index + 1) % len(self._pos_nodes)
        node.set_pos(*position)
        snd.stop()
        self._a3d.attach_sound_to_object(snd, node)
        self._a3d.set_sound_min_distance(snd, min_distance)
        snd.set_volume(volume)
        snd.set_play_rate(rate * (1.0 + random.uniform(-variation, variation)))
        snd.play()

    def loop_at(self, name, node, volume=0.8, min_distance=12.0):
        """Looping 3D sound that follows a moving node (engines, rotors). Returns a handle."""
        if not self.enabled:
            return None
        path = self._file_for(name)
        if path is None:
            return None
        snd = self._a3d.load_sfx(_pf(path))
        self._a3d.attach_sound_to_object(snd, node)
        self._a3d.set_sound_min_distance(snd, min_distance)
        snd.set_loop(True)
        snd.set_volume(volume)
        snd.play()
        self._moving_loops.append(snd)
        return snd

    def stop_loop_sound(self, snd):
        if snd is None:
            return
        snd.stop()
        if self._a3d is not None:
            self._a3d.detach_sound(snd)
        if snd in self._moving_loops:
            self._moving_loops.remove(snd)

    def play_footstep(self, volume=0.35):
        self.play(f"footstep_{random.randrange(4)}", volume=volume, variation=0.08)

    def start_loop(self, name, volume=0.5):
        if not self.enabled or name in self._loops:
            return
        path = self._file_for(name)
        if path is None:
            return
        snd = self.base.loader.load_sfx(_pf(path))
        snd.set_loop(True)
        snd.set_volume(volume)
        snd.play()
        self._loops[name] = snd

    def stop_loop(self, name):
        snd = self._loops.pop(name, None)
        if snd is not None:
            snd.stop()

    def stop_all_loops(self):
        for name in list(self._loops):
            self.stop_loop(name)
        for snd in list(self._moving_loops):
            self.stop_loop_sound(snd)

    def play_music(self, name, volume=1.0):
        if self.music_name == name or not self._music_mgr or not self._music_mgr.is_valid():
            return
        self.stop_music()
        path = self._file_for(name)
        if path is None:
            return
        self.music = self.base.loader.load_music(_pf(path))
        self.music.set_loop(True)
        self.music.set_volume(volume)
        self.music.play()
        self.music_name = name

    def stop_music(self):
        if self.music is not None:
            self.music.stop()
        self.music = None
        self.music_name = None

    def set_music_duck(self, factor, dt):
        """Lower the music while someone is speaking (factor 1 = normal)."""
        cur = getattr(self, "_duck", 1.0)
        cur += (factor - cur) * min(1.0, dt * 4.0)
        self._duck = cur
        if self._music_mgr and self._music_mgr.is_valid():
            s = self.settings
            self._music_mgr.set_volume(s.master_volume * s.music_volume * cur)

    def set_duck(self, factor):
        """Muffle every sound effect (shell shock). 1 = normal."""
        self._duck = max(0.0, min(1.0, factor))
        self.apply_volumes()

    def play_unducked(self, name, volume=1.0):
        """A sound that is NOT muffled by set_duck (the ringing in your ears)."""
        if not self.enabled or self._music_mgr is None:
            return
        path = self._file_for(name)
        if path is None:
            return
        snd = self._unducked.get(name)
        if snd is None:
            snd = self._unducked[name] = self.base.loader.load_music(_pf(path))
        snd.stop()
        s = self.settings
        snd.set_volume(volume * s.master_volume * s.sfx_volume / max(0.05, s.master_volume * s.music_volume))
        snd.play()

    def apply_volumes(self):
        s = self.settings
        if self._sfx is not None:
            self._sfx.set_volume(s.master_volume * s.sfx_volume * getattr(self, "_duck", 1.0))
        if self._music_mgr is not None:
            self._music_mgr.set_volume(s.master_volume * s.music_volume)
