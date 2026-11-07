"""Cut single gunshots out of "The Free Firearm Sound Library" (CC0, opengameart.org) for the game.

    .venv\\Scripts\\python.exe tools\\import_gun_sounds.py "D:\\op_shadow_assets\\sounds\\lib\\Prepared SFX Library"

Each recording holds several shots with silence between them. For every game sound we pick the
cleanest, loudest shot, cut it with its natural echo tail, convert to mono 16-bit 44.1 kHz and write
assets/sounds/<name>.wav (the game uses such files instead of its generated placeholder sounds).
"""
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sounds"
SR = 44100

# game sound -> (library folder, length of the cut in seconds, gain)
SOUNDS = {
    "shot_rifle": ("AR-15", 0.75, 1.0),          # player's assault rifle (automatic: short tail)
    "shot_enemy": ("AK-47", 0.85, 0.9),          # enemy rifles
    "shot_pistol": ("1911", 0.6, 0.9),
    "shot_sniper": ("Savage 10 .300 Blackout", 1.6, 1.0),
    "shot_shotgun": ("Mossberg", 1.1, 1.0),
}


def read(path):
    with wave.open(str(path)) as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        x = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        x = np.where(x >= 1 << 23, x - (1 << 24), x).astype(np.float32) / (1 << 23)
    elif width == 2:
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    else:
        raise ValueError(f"{path}: {width * 8}-bit audio not supported")
    x = x.reshape(-1, ch).mean(axis=1)
    if rate != SR:
        x = np.interp(np.arange(0, len(x), rate / SR), np.arange(len(x)), x).astype(np.float32)
    return x


def onsets(x, gap=0.35):
    """Sample indices where a shot starts (sharp rise above a third of the loudest peak)."""
    env = np.abs(x)
    thr = env.max() * 0.33
    hits, last = [], -10 ** 9
    for i in np.flatnonzero(env > thr):
        if i - last > gap * SR:
            hits.append(i)
        last = i
    return hits


def best_shot(files, length):
    """The cleanest shot: loud, and quiet just before it (no overlap with the previous shot)."""
    best, best_score = None, -1.0
    n = int(length * SR)
    for f in files:
        x = read(f)
        for i in onsets(x):
            a = max(0, i - int(0.004 * SR))
            cut = x[a:a + n]
            if len(cut) < n * 0.8:
                continue
            pre = x[max(0, a - int(0.25 * SR)):a]
            noise = float(np.sqrt(np.mean(pre ** 2))) if len(pre) else 0.0
            peak = float(np.abs(cut).max())
            score = peak / (noise + 1e-3)
            if score > best_score:
                best, best_score = cut, score
    return best


def finish(cut, length, gain):
    n = int(length * SR)
    cut = np.pad(cut, (0, max(0, n - len(cut))))[:n]
    cut = cut - np.mean(cut[: int(0.004 * SR)])                   # no click from a DC offset
    fade = int(0.25 * n)
    cut[-fade:] *= np.linspace(1, 0, fade) ** 2
    cut[: 32] *= np.linspace(0, 1, 32)
    cut *= gain * 0.95 / (np.abs(cut).max() or 1.0)
    return (np.clip(cut, -1, 1) * 32767).astype(np.int16)


def main(lib):
    lib = Path(lib)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (folder, length, gain) in SOUNDS.items():
        files = sorted((lib / folder).glob("*.wav"))
        if not files:
            print(f"skip {name}: no files in {folder}")
            continue
        cut = best_shot(files, length)
        if cut is None:
            print(f"skip {name}: no clean shot found")
            continue
        with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(finish(cut, length, gain).tobytes())
        print(f"{name}.wav  <- {folder}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"D:\op_shadow_assets\sounds\lib\Prepared SFX Library")
