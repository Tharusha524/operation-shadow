"""Weapon logic: ammo, fire rate, reloading, spread and recoil numbers.

No graphics here - this is pure game logic, unit-tested in tests/test_weapons.py.
Visuals, sound and hit detection are handled by weapons/weapon_manager.py.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class WeaponStats:
    id: str
    name: str
    weapon_class: str
    slot: int
    fire_mode: str            # auto | semi | pump | bolt
    damage: float
    headshot_multiplier: float
    pellets: int
    rpm: float
    magazine: int
    start_reserve: int
    max_reserve: int
    reload_time: float
    reload_empty_time: float
    spread_hip: float
    spread_ads: float
    spread_move: float
    spread_air: float
    spread_per_shot: float
    spread_max_bloom: float
    spread_recovery: float
    recoil_pitch: float
    recoil_yaw: float
    recoil_ads_multiplier: float
    recoil_recovery: float
    range: float
    falloff_start: float
    falloff_end: float
    min_damage_multiplier: float
    ads_fov_multiplier: float
    ads_time: float
    move_multiplier: float
    ads_move_multiplier: float
    equip_time: float
    sound: str
    model: str
    tracer_every: int
    reload_start_delay: float = 0.0
    noise: float = 0.0            # how far enemies hear a shot (0 = default for the class); suppressors are quiet

    @property
    def fire_interval(self):
        return 60.0 / self.rpm


@dataclass
class GrenadeStats:
    name: str
    start_count: int
    max_count: int
    fuse: float
    throw_speed: float
    radius: float
    max_damage: float
    cook_allowed: bool = False


def load_weapon_data(path):
    """Read data/weapons.json -> ({id: WeaponStats}, GrenadeStats)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {f.name for f in fields(WeaponStats)}
    weapons = {}
    for wid, raw in data["weapons"].items():
        values = {k: v for k, v in raw.items() if k in names}
        values["weapon_class"] = raw["class"]
        weapons[wid] = WeaponStats(id=wid, **values)
    grenade = GrenadeStats(**{k: v for k, v in data["grenade"].items()
                              if k in {f.name for f in fields(GrenadeStats)}})
    return weapons, grenade


class Weapon:
    """Runtime state of one weapon in someone's hands."""

    def __init__(self, stats: WeaponStats, rng=None, infinite_reserve=False):
        self.stats = stats
        self.rng = rng or random.Random()
        self.mag = stats.magazine
        self.reserve = stats.start_reserve
        self.infinite_reserve = infinite_reserve
        self.cooldown = 0.0
        self.reload_timer = 0.0
        self.reloading = False
        self.bloom = 0.0
        self.shots_fired = 0
        self.events = []        # "fire", "dry", "reload_start", "reload_end", "shell", "cycle"

    # ------------------------------------------------------------------ state
    @property
    def total_ammo(self):
        return self.mag + self.reserve

    @property
    def empty(self):
        return self.mag == 0

    @property
    def needs_trigger_release(self):
        return self.stats.fire_mode != "auto"

    def pop_events(self):
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------ actions
    def wants_fire(self, trigger_pressed, trigger_held):
        return trigger_pressed if self.needs_trigger_release else trigger_held

    def try_fire(self):
        """Fire one round if possible. Returns True when a shot leaves the barrel."""
        if self.reloading:
            if self.mag > 0 and self.interruptible_reload:
                self.cancel_reload()
            else:
                return False
        if self.cooldown > 0.0:
            return False
        if self.mag <= 0:
            self.events.append("dry")
            self.cooldown = 0.25
            self.start_reload()
            return False
        self.mag -= 1
        self.shots_fired += 1
        self.cooldown = self.stats.fire_interval
        self.bloom = min(self.stats.spread_max_bloom, self.bloom + self.stats.spread_per_shot)
        self.events.append("fire")
        if self.stats.fire_mode in ("pump", "bolt") and self.mag > 0:
            self.events.append("cycle")
        return True

    def start_reload(self):
        if self.reloading or self.mag >= self.stats.magazine or self.reserve <= 0:
            return False
        self.reloading = True
        self.reload_timer = self._reload_duration()
        self.events.append("reload_start")
        return True

    def cancel_reload(self):
        self.reloading = False
        self.reload_timer = 0.0

    @property
    def interruptible_reload(self):
        return False

    def _reload_duration(self):
        return self.stats.reload_empty_time if self.mag == 0 else self.stats.reload_time

    @property
    def reload_progress(self):
        if not self.reloading:
            return 0.0
        total = self._reload_duration()
        return 1.0 - self.reload_timer / max(total, 1e-6)

    def _finish_reload(self):
        need = self.stats.magazine - self.mag
        take = min(need, self.reserve)
        self.mag += take
        if not self.infinite_reserve:
            self.reserve -= take
        self.reloading = False
        self.events.append("reload_end")

    def add_ammo(self, amount):
        before = self.reserve
        self.reserve = min(self.stats.max_reserve, self.reserve + amount)
        return self.reserve - before

    def refill(self):
        self.mag = self.stats.magazine
        self.reserve = self.stats.start_reserve
        self.cancel_reload()

    # ------------------------------------------------------------------ per frame
    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.bloom = max(0.0, self.bloom - self.stats.spread_recovery * dt)
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0.0:
                self._finish_reload()

    # ------------------------------------------------------------------ accuracy
    def spread(self, ads=0.0, moving=0.0, airborne=False):
        """Current cone half-angle in degrees."""
        s = self.stats
        base = s.spread_hip + (s.spread_ads - s.spread_hip) * ads
        base += s.spread_move * moving * (1.0 - 0.6 * ads)
        if airborne:
            base += s.spread_air
        return max(0.0, base + self.bloom * (1.0 - 0.5 * ads))

    def pellet_offsets(self, spread_deg):
        """Random (yaw, pitch) offsets in degrees for each pellet, uniform inside the cone."""
        out = []
        for _ in range(self.stats.pellets):
            r = spread_deg * math.sqrt(self.rng.random())
            a = self.rng.uniform(0.0, 2.0 * math.pi)
            out.append((r * math.cos(a), r * math.sin(a)))
        return out

    def recoil_kick(self, ads=0.0):
        """(pitch_up, yaw) recoil in degrees for one shot."""
        s = self.stats
        mult = 1.0 + (s.recoil_ads_multiplier - 1.0) * ads
        return s.recoil_pitch * mult * self.rng.uniform(0.85, 1.15), s.recoil_yaw * mult * self.rng.uniform(-1.0, 1.0)
