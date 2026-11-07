"""Spoken dialogue with the free, offline Windows voices (Microsoft David / Zira).

Every line (narrator, cutscene dialogue, radio calls, squad call-outs) is turned into a WAV file once and
cached in data/voice_cache. Each character gets its own pitch and speed, so the two Windows voices can
play a whole cast; people talking over the radio also get a band-pass "radio" sound with hiss and squelch.

The generation runs PowerShell (tools/tts_batch.ps1) in a background thread, so the game never waits for
it: a line whose file is not ready yet is simply shown as a subtitle without sound.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
import wave
from pathlib import Path

import numpy as np

from core.paths import DATA_DIR, user_data_dir

log = logging.getLogger(__name__)

VOICE_VERSION = 4
SR = 22050
DAVID, ZIRA = "Microsoft David Desktop", "Microsoft Zira Desktop"
# speaker id -> (windows voice, pitch factor, extra speed steps, radio)
VOICES = {
    "narrator": (DAVID, 0.86, 0, False),
    "halden": (DAVID, 1.10, 0, False),
    "marek": (DAVID, 0.91, 0, False),
    "kell": (DAVID, 1.16, 1, False),
    "doran": (DAVID, 1.05, 2, False),
    "crane": (DAVID, 0.96, -1, False),
    "harrow": (DAVID, 0.80, -1, True),
    "brandt": (DAVID, 1.12, 1, False),
    "bastion": (DAVID, 1.0, 1, True),
    "hammer": (DAVID, 0.95, 1, True),
    "convoy": (DAVID, 1.04, 1, True),
    "rifleman": (DAVID, 1.02, 1, False),
    "civilian": (DAVID, 1.07, 1, False),
    "drevan": (DAVID, 0.83, -1, False),
    "kade": (DAVID, 0.98, 0, False),
    "ostrova": (DAVID, 0.88, -1, False),
    "stranger": (DAVID, 0.79, -1, False),
    "venn": (ZIRA, 0.97, -1, False),
    "voss": (ZIRA, 0.93, 0, False),
    "wren": (ZIRA, 1.04, 1, True),
    "mira": (ZIRA, 0.88, -1, False),
    "rusk": (ZIRA, 0.98, 0, False),
    "lind": (ZIRA, 0.92, -1, False),
}
FEMALE_DEFAULT, MALE_DEFAULT = "voss", "rifleman"


def cache_dir():
    d = user_data_dir() / "voice_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def line_key(speaker, text):
    return hashlib.sha1(f"{VOICE_VERSION}|{speaker}|{text}".encode("utf-8")).hexdigest()[:16]


def line_path(speaker, text):
    return cache_dir() / f"{line_key(speaker, text)}.wav"


def spoken_text(text):
    """What the voice actually says: no stage directions like [static], no stray symbols."""
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = text.replace("--", ",").replace("...", ", ").replace("(", "").replace(")", "")
    text = re.sub(r"(\s*,\s*)+", ", ", text)
    return re.sub(r"\s+", " ", text).strip(" ,")


def profile(speaker):
    return VOICES.get(speaker, VOICES[MALE_DEFAULT])


# ---------------------------------------------------------------------------------------------- sound
def _read_wav(path):
    with wave.open(str(path)) as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    return data, rate


def _write_wav(path, samples, rate=SR):
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _band(sig, low, high):
    spec = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1.0 / SR)
    gain = 1.0 / (1.0 + (f / high) ** 4) / (1.0 + (low / np.maximum(f, 1.0)) ** 4)
    return np.fft.irfft(spec * gain, len(sig)).astype(np.float32)


def shape(raw, rate, speaker):
    """Pitch-shift the raw Windows voice for this character and add the radio sound if needed."""
    _, factor, _, radio = profile(speaker)
    if rate != SR:
        raw = np.interp(np.arange(0, len(raw), rate / SR), np.arange(len(raw)), raw).astype(np.float32)
    # Playing the samples faster/slower moves the pitch; the speech rate was compensated when generating.
    n = int(len(raw) / factor)
    out = np.interp(np.arange(n) * factor, np.arange(len(raw)), raw).astype(np.float32)
    nz = np.nonzero(np.abs(out) > 0.01)[0]                     # trim silence at both ends
    if len(nz):
        out = out[max(0, nz[0] - int(0.05 * SR)): nz[-1] + int(0.15 * SR)]
    if radio:
        rng = np.random.default_rng(len(out))
        out = _band(out, 350.0, 3000.0) * 1.8
        out = np.tanh(out * 2.2) / np.tanh(2.2)
        out += rng.normal(0, 0.012, len(out)).astype(np.float32)
        click = (rng.normal(0, 0.25, int(0.04 * SR)) * np.linspace(1, 0, int(0.04 * SR))).astype(np.float32)
        hiss = rng.normal(0, 0.03, int(0.12 * SR)).astype(np.float32)
        out = np.concatenate([click, hiss * np.linspace(0, 1, len(hiss)), out, hiss[::-1] * 0.6, click * 0.7])
    peak = float(np.max(np.abs(out))) or 1.0
    return out * (0.85 / peak)


def speech_rate(speaker):
    """Windows speech-rate steps so the final line (after the pitch change) speaks at a natural speed."""
    _, factor, extra, _ = profile(speaker)
    return max(-10, min(10, round(math.log(1.0 / factor) / math.log(1.1)) + extra))


# ---------------------------------------------------------------------------------------------- generation
def generate(lines, script=None):
    """Make WAVs for (speaker, text) pairs that are not cached yet. Returns how many were made."""
    todo = [(s, t) for s, t in dict.fromkeys(lines) if t and not line_path(s, t).is_file()]
    if not todo or sys.platform != "win32":
        return 0
    script = script or (Path(__file__).resolve().parents[1] / "tools" / "tts_batch.ps1")
    tmp = cache_dir() / "_tmp"
    tmp.mkdir(exist_ok=True)
    jobs = []
    for i, (speaker, text) in enumerate(todo):
        voice = profile(speaker)[0]
        jobs.append({"out": str((tmp / f"{i}.wav").resolve()), "voice": voice, "rate": speech_rate(speaker),
                     "pitch": "+0%", "text": spoken_text(text)})
    job_file = tmp / "jobs.json"
    job_file.write_text(json.dumps(jobs), encoding="utf-8")
    flags = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW: no console pops up
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                        str(job_file)], check=True, capture_output=True, timeout=600, creationflags=flags)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Voice generation failed: %s", exc)
        return 0
    made = 0
    for i, (speaker, text) in enumerate(todo):
        raw_path = tmp / f"{i}.wav"
        if not raw_path.is_file():
            continue
        raw, rate = _read_wav(raw_path)
        _write_wav(line_path(speaker, text), shape(raw, rate, speaker))
        raw_path.unlink(missing_ok=True)
        made += 1
    return made


def collect_lines(campaign=None):
    """Every spoken line in the game: missions (cutscenes, radio, alarms), story videos and call-outs."""
    from enemies.enemy_manager import CALLOUTS
    from missions.mission_data import MISSIONS_DIR
    lines = []

    def add_actions(actions):
        for a in actions:
            if a.get("action") == "radio":
                lines.append((a["speaker"], a["text"]))

    for path in sorted(MISSIONS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("intro", "outro"):
            for line in (data.get(key) or {}).get("lines", []):
                lines.append((line["speaker"], line["text"]))
        for step in data.get("steps", []):
            add_actions(step.get("on_start", []))
            add_actions(step.get("on_complete", []))
        add_actions((data.get("alarm") or {}).get("actions", []))
    story_dir = DATA_DIR / "story"
    for path in sorted(story_dir.glob("*.json")) if story_dir.is_dir() else []:
        data = json.loads(path.read_text(encoding="utf-8"))
        for line in data.get("lines", []):
            lines.append((line.get("speaker", "narrator"), line["text"]))
    for speaker in ("marek", "voss", "kell", "doran", "mira", "brandt", "rifleman"):
        for options in CALLOUTS.values():
            for text in options:
                lines.append((speaker, text))
    return list(dict.fromkeys(lines))


# ---------------------------------------------------------------------------------------------- playback
class VoicePlayer:
    """Plays one line at a time (a new line cuts the previous one, like a real radio)."""

    def __init__(self, game, characters=None):
        self.game = game
        self.characters = characters or {}
        self._by_name = {c.name: cid for cid, c in self.characters.items()}
        self.current = None
        self.duck = 0.0
        self.ready = threading.Event()
        self._thread = None

    def speaker_for_name(self, name):
        return self._by_name.get(name, MALE_DEFAULT)

    def prepare_all(self):
        """Generate missing voice files in the background (first start takes a minute, later starts nothing)."""
        if self._thread is not None:
            return
        lines = collect_lines()

        def work():
            try:
                made = generate(lines)
                if made:
                    log.info("Generated %d voice lines", made)
            finally:
                self.ready.set()

        self._thread = threading.Thread(target=work, name="voice-gen", daemon=True)
        self._thread.start()

    def duration(self, speaker, text):
        path = line_path(speaker, text)
        if not path.is_file():
            return 0.0
        try:
            with wave.open(str(path)) as w:
                return w.getnframes() / float(w.getframerate())
        except (OSError, wave.Error):
            return 0.0

    def play(self, speaker, text, volume=1.0):
        """Speak a line. Returns its length in seconds (0 if no voice file exists yet)."""
        path = line_path(speaker, text)
        audio = getattr(self.game, "audio", None)
        if audio is None or not getattr(audio, "enabled", False) or not path.is_file():
            return 0.0
        self.stop()
        from panda3d.core import Filename
        snd = self.game.loader.load_sfx(Filename.from_os_specific(str(path)))
        if snd is None:
            return 0.0
        s = self.game.settings
        snd.set_volume(min(1.0, volume * s.master_volume * max(0.35, s.sfx_volume) * 1.1))
        snd.play()
        self.current = snd
        length = snd.length() or self.duration(speaker, text)
        self.duck = length
        return length

    def speaking(self):
        from panda3d.core import AudioSound
        return self.current is not None and self.current.status() == AudioSound.PLAYING

    def stop(self):
        if self.current is not None:
            self.current.stop()
            self.current = None
