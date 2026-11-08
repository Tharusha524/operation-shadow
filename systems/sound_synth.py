"""Procedural sound effects and music, generated with numpy and saved as WAV files.

These are placeholders so the game has real audio without any downloaded assets.
To replace one, put a file with the same name in assets/sounds/ (or assets/music/
for music): e.g. assets/sounds/shot_rifle.wav or .ogg - it is used automatically.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 22050
SYNTH_VERSION = 9


def _t(n):
    return np.arange(n, dtype=np.float32) / SR


def _env(n, attack, decay):
    t = _t(n)
    return (1.0 - np.exp(-t / max(attack, 1e-5))) * np.exp(-t / max(decay, 1e-5))


def _filter(sig, low=None, high=None, order=2):
    spec = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1.0 / SR)
    gain = np.ones_like(f)
    if low is not None:
        gain *= 1.0 / (1.0 + (f / low) ** (2 * order))
    if high is not None:
        gain *= 1.0 / (1.0 + (high / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(spec * gain, len(sig)).astype(np.float32)


def _norm(sig, peak=0.9):
    m = float(np.max(np.abs(sig))) or 1.0
    return (sig / m * peak).astype(np.float32)


def _soft_clip(sig, drive=1.5):
    return np.tanh(sig * drive) / np.tanh(drive)


def gunshot(rng, body_freq, crack, decay, tail, length, brightness=2500):
    n = int(length * SR)
    t = _t(n)
    noise = rng.standard_normal(n).astype(np.float32)
    crack_part = _filter(noise, high=brightness) * _env(n, 0.0003, crack) * 1.4
    body = _filter(noise, low=1100) * _env(n, 0.0008, decay) * 2.2
    freq = body_freq * (1.0 + 1.5 * np.exp(-t / 0.02))
    thump = np.sin(2 * math.pi * np.cumsum(freq) / SR) * _env(n, 0.001, decay * 1.6) * 1.6
    room = _filter(rng.standard_normal(n).astype(np.float32), low=600) * _env(n, 0.015, tail) * 0.55
    return _norm(_soft_clip(crack_part + body + thump + room, 2.0))


def click(rng, freq=3200, length=0.05, decay=0.006, ring=0.02, level=1.0):
    n = int(length * SR)
    t = _t(n)
    noise = _filter(rng.standard_normal(n).astype(np.float32), high=1500) * _env(n, 0.0002, decay)
    ping = np.sin(2 * math.pi * freq * t) * _env(n, 0.0005, ring) * 0.5
    return _norm(noise + ping, 0.8 * level)


def sequence(parts, gaps, total):
    out = np.zeros(int(total * SR), np.float32)
    pos = 0.0
    for part, gap in zip(parts, gaps):
        pos += gap
        i = int(pos * SR)
        out[i:i + len(part)] += part[: max(0, len(out) - i)]
    return _norm(out, 0.85)


def footstep(rng):
    n = int(0.16 * SR)
    noise = rng.standard_normal(n).astype(np.float32)
    thud = _filter(noise, low=300) * _env(n, 0.004, 0.03) * 1.5
    grit = np.zeros(n, np.float32)
    for _ in range(rng.integers(4, 8)):
        i = int(rng.uniform(0.0, 0.07) * SR)
        m = int(0.012 * SR)
        grit[i:i + m] += _filter(rng.standard_normal(m).astype(np.float32), high=2000) * _env(m, 0.0002, 0.003) * rng.uniform(0.2, 0.6)
    return _norm(thud + grit, 0.7)


def impact(rng, hard=True):
    n = int(0.35 * SR)
    noise = rng.standard_normal(n).astype(np.float32)
    if hard:
        sig = _filter(noise, high=1200) * _env(n, 0.0002, 0.012) * 1.2 + _filter(noise, low=700) * _env(n, 0.001, 0.05)
        debris = np.zeros(n, np.float32)
        for _ in range(6):
            i = int(rng.uniform(0.02, 0.2) * SR)
            m = int(0.01 * SR)
            debris[i:i + m] += _filter(rng.standard_normal(m).astype(np.float32), high=2500) * _env(m, 0.0002, 0.002) * 0.25
        return _norm(sig + debris, 0.8)
    return _norm(_filter(noise, low=450) * _env(n, 0.002, 0.04) * 2.0, 0.8)


def explosion(rng, length=2.8):
    n = int(length * SR)
    t = _t(n)
    noise = rng.standard_normal(n).astype(np.float32)
    crack = _filter(noise, high=800) * _env(n, 0.0005, 0.03) * 1.5
    boom = _filter(noise, low=180, order=3) * _env(n, 0.005, 0.6) * 4.0
    sub = np.sin(2 * math.pi * (45 + 60 * np.exp(-t / 0.08)) * t) * _env(n, 0.003, 0.35) * 2.0
    rumble = _filter(rng.standard_normal(n).astype(np.float32), low=120) * _env(n, 0.05, 1.2) * 1.5
    return _norm(_soft_clip(crack + boom + sub + rumble, 2.5))


def loop_noise(rng, length, low, high=None, mod_rate=0.15, mod_depth=0.5):
    n = int(length * SR)
    t = _t(n)
    sig = _filter(rng.standard_normal(n).astype(np.float32), low=low, high=high)
    mod = 1.0 - mod_depth * 0.5 * (1 + np.sin(2 * math.pi * mod_rate * t + rng.uniform(0, 6)))
    sig *= mod
    fade = int(0.5 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    sig[:fade] = sig[:fade] * ramp + sig[-fade:] * (1 - ramp)      # seamless loop
    return _norm(sig[: n - fade], 0.6)


def siren(length=3.0):
    n = int(length * SR)
    t = _t(n)
    freq = 620 + 260 * (0.5 - 0.5 * np.cos(2 * math.pi * t / length))
    phase = 2 * math.pi * np.cumsum(freq) / SR
    sig = np.sign(np.sin(phase)) * 0.25 + np.sin(phase) * 0.5
    return _norm(_filter(sig.astype(np.float32), low=2500), 0.55)


def tones(freqs, durations, level=0.5):
    parts = []
    for f, d in zip(freqs, durations):
        n = int(d * SR)
        t = _t(n)
        env = np.minimum(1.0, np.minimum(t / 0.005, (d - t) / 0.01))
        parts.append(np.sin(2 * math.pi * f * t) * env if f else np.zeros(n))
    return _norm(np.concatenate(parts).astype(np.float32), level)


def chord_pad(rng, freqs, length, level=0.5, attack=1.5, release=2.0, detune=0.004):
    n = int(length * SR)
    t = _t(n)
    sig = np.zeros(n, np.float32)
    for f in freqs:
        for d in (-detune, 0.0, detune):
            ph = rng.uniform(0, 2 * math.pi)
            sig += np.sin(2 * math.pi * f * (1 + d) * t + ph) + 0.3 * np.sin(4 * math.pi * f * (1 + d) * t + ph)
    env = np.minimum(1.0, t / attack) * np.minimum(1.0, (length - t) / release)
    sig = _filter(sig * env, low=1800)
    return _norm(sig, level)


def menu_music(rng, length=32.0):
    """Dark, slow military drone: low pads + distant timpani-like pulses."""
    n = int(length * SR)
    t = _t(n)
    out = np.zeros(n, np.float32)
    chords = [(55.0, 82.4, 110.0, 130.8), (49.0, 73.4, 98.0, 116.5), (43.7, 65.4, 87.3, 103.8), (49.0, 73.4, 98.0, 123.5)]
    seg = length / len(chords)
    for i, ch in enumerate(chords):
        pad = chord_pad(rng, ch, seg + 2.0, level=1.0, attack=2.0, release=2.0)
        start = int(i * seg * SR)
        end = min(n, start + len(pad))
        out[start:end] += pad[: end - start]
        tail = len(pad) - (end - start)
        if tail > 0:
            out[:tail] += pad[end - start:]
    beat = 60.0 / 70.0
    k = 0
    while k * beat < length - 0.5:
        i = int(k * beat * SR)
        m = int(0.9 * SR)
        hit_t = _t(m)
        drum = np.sin(2 * math.pi * (55 + 40 * np.exp(-hit_t / 0.05)) * hit_t) * _env(m, 0.002, 0.25)
        level = 0.55 if k % 4 == 0 else 0.25
        end = min(n, i + m)
        out[i:end] += drum[: end - i] * level
        k += 1
    return _norm(out, 0.6)


def stinger(rng, freqs, length=4.0):
    return chord_pad(rng, freqs, length, level=0.7, attack=0.05, release=2.5)


def _recipes():
    r = lambda seed: np.random.default_rng(seed)  # noqa: E731
    out = {
        "shot_rifle": lambda: gunshot(r(1), 115, 0.012, 0.06, 0.35, 0.7),
        "shot_pistol": lambda: gunshot(r(2), 160, 0.008, 0.035, 0.22, 0.45, 3200),
        "shot_sniper": lambda: gunshot(r(3), 70, 0.02, 0.12, 0.9, 1.5, 1800),
        "shot_shotgun": lambda: gunshot(r(4), 85, 0.016, 0.11, 0.5, 0.9, 1500),
        "shot_enemy": lambda: gunshot(r(5), 135, 0.01, 0.05, 0.3, 0.6, 2800),
        "dry_fire": lambda: click(r(6), 4200, 0.06, 0.004, 0.01),
        "reload_out": lambda: sequence([click(r(7), 1800, 0.08, 0.01, 0.03), click(r(8), 900, 0.1, 0.02, 0.04)], [0.0, 0.12], 0.4),
        "reload_in": lambda: sequence([click(r(9), 2400, 0.06, 0.006, 0.02), click(r(10), 3000, 0.08, 0.005, 0.03)], [0.0, 0.18], 0.4),
        "bolt": lambda: sequence([click(r(11), 2000, 0.07, 0.008, 0.02), click(r(12), 2600, 0.07, 0.008, 0.02),
                                  click(r(13), 1700, 0.07, 0.008, 0.02)], [0.0, 0.15, 0.2], 0.6),
        "pump": lambda: sequence([click(r(14), 900, 0.1, 0.03, 0.03), click(r(15), 1300, 0.1, 0.02, 0.03)], [0.0, 0.2], 0.45),
        "shell_in": lambda: click(r(16), 2200, 0.08, 0.01, 0.03),
        "weapon_switch": lambda: sequence([click(r(17), 1500, 0.06, 0.01, 0.02, 0.6), click(r(18), 2100, 0.06, 0.01, 0.02, 0.6)], [0.0, 0.1], 0.3),
        "impact_hard": lambda: impact(r(19), True),
        "impact_flesh": lambda: impact(r(20), False),
        "hitmarker": lambda: tones([1900], [0.035], 0.35),
        "killmarker": lambda: tones([1500, 2100], [0.04, 0.06], 0.4),
        "explosion": lambda: explosion(r(21)),
        "grenade_bounce": lambda: click(r(22), 2800, 0.15, 0.004, 0.05, 0.7),
        "grenade_pin": lambda: sequence([click(r(23), 3500, 0.05, 0.003, 0.02), click(r(24), 2000, 0.08, 0.01, 0.03)], [0.0, 0.1], 0.3),
        "wind_loop": lambda: loop_noise(r(25), 10.0, 420, 60, 0.12, 0.6),
        "alarm_loop": lambda: siren(3.0),
        "radio_beep": lambda: tones([1200, 0, 1600], [0.06, 0.04, 0.08], 0.35),
        "radio_static": lambda: _norm(_filter(r(26).standard_normal(int(0.35 * SR)).astype(np.float32), 3500, 800)
                                      * _env(int(0.35 * SR), 0.01, 0.12), 0.35),
        "ui_hover": lambda: tones([900], [0.03], 0.18),
        "ui_click": lambda: click(r(27), 1600, 0.08, 0.006, 0.03, 0.6),
        "player_hurt": lambda: _norm(_filter(r(28).standard_normal(int(0.25 * SR)).astype(np.float32), 500)
                                     * _env(int(0.25 * SR), 0.005, 0.06), 0.6),
        "mission_complete": lambda: stinger(r(29), (130.8, 164.8, 196.0, 261.6, 329.6)),
        "mission_failed": lambda: stinger(r(30), (65.4, 69.3, 98.0, 103.8)),
        "objective": lambda: tones([660, 0, 880], [0.12, 0.05, 0.25], 0.4),
    }
    for i in range(4):
        out[f"footstep_{i}"] = (lambda i=i: footstep(r(40 + i)))
    for i in range(3):
        out[f"enemy_shout_{i}"] = (lambda i=i: _shout(r(50 + i), 180 + 30 * i))
    out["music_menu"] = lambda: menu_music(r(60))
    out["shell_whistle"] = lambda: whistle(r(61))
    out["rotor_loop"] = lambda: rotor_loop(r(62))
    out["tank_loop"] = lambda: engine_loop(r(63), base=38.0, low=160, rattle=True)
    out["boat_loop"] = lambda: engine_loop(r(64), base=55.0, low=420, rattle=False, splash=True)
    out["drone_loop"] = lambda: drone_loop(r(65))
    out["tank_cannon"] = lambda: gunshot(r(66), 42, 0.03, 0.25, 1.6, 2.6, 900)
    out["rocket_launch"] = lambda: rocket_whoosh(r(67))
    out["flare_pop"] = lambda: sequence([click(r(68), 900, 0.12, 0.02, 0.05)], [0.0], 0.3)
    out["takedown"] = lambda: sequence([impact(r(69), False), click(r(70), 500, 0.15, 0.04, 0.05, 0.8)], [0.0, 0.05], 0.45)
    out["c4_plant"] = lambda: tones([2200, 0, 2200, 0, 2800], [0.05, 0.08, 0.05, 0.08, 0.12], 0.35)
    out["tag_beep"] = lambda: tones([1800, 2600], [0.05, 0.08], 0.35)
    out["shot_suppressed"] = lambda: _norm(gunshot(r(71), 240, 0.004, 0.025, 0.07, 0.3, 1100), 0.5)
    out["shot_suppressed_pistol"] = lambda: _norm(gunshot(r(72), 280, 0.003, 0.02, 0.05, 0.25, 1300), 0.45)
    out["camera_shutter"] = lambda: sequence([click(r(73), 4200, 0.04, 0.003, 0.01), click(r(74), 2600, 0.06, 0.005, 0.02)],
                                             [0.0, 0.07], 0.2)
    out["rain_loop"] = lambda: loop_noise(r(75), 8.0, 7000, 900, 0.3, 0.25)
    out["camera_alert"] = lambda: tones([1500, 0, 1500, 0, 1500], [0.08, 0.06, 0.08, 0.06, 0.08], 0.3)
    out["flashbang"] = lambda: sequence([gunshot(r(76), 90, 0.02, 0.08, 0.4, 0.8, 4000), tones([3800], [1.6], 0.12)],
                                        [0.0, 0.1], 1.8)
    out["tinnitus"] = lambda: _tinnitus(r(90))
    out["smoke_pop"] = lambda: sequence([click(r(77), 700, 0.1, 0.02, 0.05),
                                        _norm(_filter(r(78).standard_normal(int(1.5 * SR)).astype(np.float32), 6000, 1500)
                                              * _env(int(1.5 * SR), 0.05, 0.8), 0.4)], [0.0, 0.08], 1.7)
    out["jeep_loop"] = lambda: engine_loop(r(79), base=48.0, low=320, rattle=True)
    out["crash"] = lambda: sequence([impact(r(80), True), click(r(81), 600, 0.3, 0.05, 0.1)], [0.0, 0.05], 0.6)
    out["nvg_on"] = lambda: tones([3000, 3600, 4200], [0.05, 0.05, 0.12], 0.18)
    return out


def _seamless(sig, fade_s=0.3):
    fade = int(fade_s * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    sig[:fade] = sig[:fade] * ramp + sig[-fade:] * (1 - ramp)
    return sig[: len(sig) - fade]


def rotor_loop(rng, length=4.3, blade_hz=5.8):
    n = int(length * SR)
    t = _t(n)
    out = np.zeros(n, np.float32)
    m = int(0.09 * SR)
    for k in range(int(length * blade_hz)):
        i = int(k / blade_hz * SR)
        burst = _filter(rng.standard_normal(m).astype(np.float32), low=220) * _env(m, 0.004, 0.035)
        end = min(n, i + m)
        out[i:end] += burst[: end - i] * 2.5
    whine = np.sin(2 * math.pi * 1650 * t) * 0.04 + _filter(rng.standard_normal(n).astype(np.float32), 5000, 2000) * 0.05
    return _norm(_seamless(out + whine), 0.7)


def engine_loop(rng, base=40.0, low=200, rattle=False, splash=False, length=4.0):
    n = int(length * SR)
    t = _t(n)
    noise = _filter(rng.standard_normal(n).astype(np.float32), low=low)
    am = 0.6 + 0.4 * np.sin(2 * math.pi * base * t)
    sig = noise * am + np.sin(2 * math.pi * base * 0.5 * t) * 0.3
    if rattle:
        for _ in range(int(length * 9)):
            i = int(rng.uniform(0, length - 0.05) * SR)
            m = int(0.02 * SR)
            sig[i:i + m] += _filter(rng.standard_normal(m).astype(np.float32), high=900) * _env(m, 0.001, 0.006) * 0.4
    if splash:
        sig += _filter(rng.standard_normal(n).astype(np.float32), 2500, 600) * (0.25 + 0.15 * np.sin(2 * math.pi * 0.7 * t))
    return _norm(_seamless(sig), 0.6)


def drone_loop(rng, length=3.0):
    n = int(length * SR)
    t = _t(n)
    f = 185 * (1 + 0.01 * np.sin(2 * math.pi * 3 * t))
    phase = 2 * math.pi * np.cumsum(f) / SR
    saw = sum(np.sin(phase * k) / k for k in range(1, 12))
    return _norm(_seamless(_filter(saw.astype(np.float32), low=4000)), 0.45)


def rocket_whoosh(rng, length=1.4):
    n = int(length * SR)
    t = _t(n)
    noise = rng.standard_normal(n).astype(np.float32)
    whoosh = _filter(noise, low=2500, high=300) * _env(n, 0.02, 0.6) * 1.5
    thump = np.sin(2 * math.pi * (60 + 80 * np.exp(-t / 0.05)) * t) * _env(n, 0.002, 0.1)
    return _norm(_soft_clip(whoosh + thump, 1.5), 0.85)


def _tinnitus(rng, length=4.5):
    """Shell shock: a high ringing in the ears with a muffled rumble under it, fading out."""
    n = int(length * SR)
    t = _t(n)
    env = np.minimum(1.0, t / 0.05) * np.exp(-t / 1.8)
    ring = np.sin(2 * math.pi * 3900 * t) * 0.6 + np.sin(2 * math.pi * 4170 * t) * 0.25
    rumble = _filter(rng.standard_normal(n).astype(np.float32), 180, 40) * np.exp(-t / 1.0) * 2.5
    return _norm((ring * env + rumble).astype(np.float32), 0.55)


def whistle(rng, length=1.3):
    """Incoming artillery shell: a falling whistle that warns the player before the blast."""
    n = int(length * SR)
    t = _t(n)
    freq = 1500 - 900 * (t / length) ** 1.5
    phase = 2 * math.pi * np.cumsum(freq) / SR
    env = np.minimum(1.0, t / 0.4) * np.minimum(1.0, (length - t) / 0.05)
    sig = np.sin(phase) * env + _filter(rng.standard_normal(n).astype(np.float32), 3000, 1000) * env * 0.15
    return _norm(sig.astype(np.float32), 0.45)


def _shout(rng, base):
    """Abstract, wordless radio-filtered shout (enemy voice placeholder)."""
    n = int(0.55 * SR)
    t = _t(n)
    f = base * (1 + 0.25 * np.sin(2 * math.pi * 3.5 * t) * np.exp(-t / 0.3))
    phase = 2 * math.pi * np.cumsum(f) / SR
    voiced = sum(np.sin(phase * k) / k for k in range(1, 8))
    env = _env(n, 0.03, 0.25) * (0.6 + 0.4 * np.sin(2 * math.pi * 6 * t) ** 2)
    sig = _filter(voiced * env + rng.standard_normal(n) * 0.05 * env, 3000, 300)
    return _norm(_soft_clip(sig, 2.0), 0.6)


SOUND_NAMES = tuple(_recipes().keys())


def write_wav(path, samples):
    data = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data.tobytes())


def ensure_sounds(cache_dir) -> dict:
    """Generate any missing WAV files. Returns {name: path}."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = cache_dir / f"version_{SYNTH_VERSION}.txt"
    regenerate = not stamp.exists()
    paths = {}
    for name, recipe in _recipes().items():
        path = cache_dir / f"{name}.wav"
        if regenerate or not path.exists():
            write_wav(path, recipe())
        paths[name] = path
    if regenerate:
        for old in cache_dir.glob("version_*.txt"):
            old.unlink()
        stamp.write_text("generated sound cache", encoding="utf-8")
    return paths
