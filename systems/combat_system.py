"""Hit detection and damage for every bullet in the game (player, enemies and squad).

A shot is a ray. It is tested against the level (CollisionWorld) and against the
hitboxes of every living character. The closest hit wins:
  * head   -> damage x weapon headshot multiplier
  * body   -> normal damage
  * legs   -> 0.8x damage
Damage falls off between falloff_start and falloff_end metres.

The system also broadcasts gunshot "noise" so enemies can hear shots.
"""
from __future__ import annotations

import math

from systems.collision_system import ray_sphere, ray_vertical_cylinder

ZONE_MULTIPLIER = {"head": None, "body": 1.0, "legs": 0.8}   # head uses the weapon value


class ShotResult:
    __slots__ = ("t", "point", "normal", "target", "zone", "damage", "killed", "surface")

    def __init__(self, t, point, normal, target=None, zone=None, surface="world"):
        self.t, self.point, self.normal = t, point, normal
        self.target, self.zone, self.surface = target, zone, surface
        self.damage = 0.0
        self.killed = False


def character_hitboxes(x, y, z, height):
    """Standard humanoid hitboxes for a character standing at (x, y, z) with the given height."""
    head_r = 0.14
    head_z = z + height - head_r - 0.02
    torso_top = head_z - head_r
    legs_top = z + height * 0.46
    return (
        ("head", "sphere", (x, y, head_z, head_r)),
        ("body", "cylinder", (x, y, legs_top, torso_top, 0.26)),
        ("legs", "cylinder", (x, y, z, legs_top, 0.2)),
    )


class CombatSystem:
    def __init__(self, collision_world):
        self.world = collision_world
        self.characters = []          # objects with .alive, .team, .hitboxes(), .take_damage(...)
        self.noise_listeners = []     # callables(position, radius, team, source)
        self.shot_listeners = []      # callables(shooter, result) - for effects/stats
        self.shots_fired = 0

    def register(self, character):
        if character not in self.characters:
            self.characters.append(character)

    def unregister(self, character):
        if character in self.characters:
            self.characters.remove(character)

    def clear(self):
        self.characters.clear()

    # ------------------------------------------------------------------ rays
    def raycast(self, origin, direction, max_dist, ignore=None):
        """Closest hit against the level and every character hitbox."""
        hit = self.world.raycast(origin, direction, max_dist)
        best = ShotResult(hit.t, hit.point, hit.normal) if hit else None
        limit = hit.t if hit else max_dist
        ox, oy, oz = origin
        dx, dy, dz = direction
        for ch in self.characters:
            if ch is ignore or not ch.alive:
                continue
            for zone, shape, p in ch.hitboxes():
                if shape == "sphere":
                    r = ray_sphere(ox, oy, oz, dx, dy, dz, limit, *p)
                else:
                    cx, cy, z0, z1, rad = p
                    r = ray_vertical_cylinder(ox, oy, oz, dx, dy, dz, limit, cx, cy, z0, z1, rad)
                if r is not None and r[0] < limit:
                    limit = r[0]
                    point = (ox + dx * r[0], oy + dy * r[0], oz + dz * r[0])
                    best = ShotResult(r[0], point, r[1], ch, zone, "flesh")
        return best

    def fire(self, shooter, origin, direction, weapon, noise_radius=None):
        """Fire one bullet/pellet. Applies damage and returns the ShotResult (or None for a miss)."""
        result = self.raycast(origin, direction, weapon.range, ignore=shooter)
        if result is not None and result.target is not None:
            target = result.target
            friendly = shooter is not None and getattr(shooter, "team", None) == target.team
            if not friendly:
                dmg = weapon.damage * self.falloff(weapon, result.t)
                mult = ZONE_MULTIPLIER[result.zone]
                dmg *= weapon.headshot_multiplier if mult is None else mult
                result.damage = dmg
                result.killed = target.take_damage(dmg, shooter, result.zone, direction)
        for listener in self.shot_listeners:
            listener(shooter, origin, direction, result)
        return result

    def emit_noise(self, position, radius, team, source=None):
        for listener in self.noise_listeners:
            listener(position, radius, team, source)

    @staticmethod
    def falloff(weapon, distance):
        start, end = weapon.falloff_start, weapon.falloff_end
        if distance <= start:
            return 1.0
        if distance >= end:
            return weapon.min_damage_multiplier
        t = (distance - start) / (end - start)
        return 1.0 + (weapon.min_damage_multiplier - 1.0) * t

    # ------------------------------------------------------------------ explosions
    def explode(self, position, radius, max_damage, source=None):
        """Radial damage with line-of-sight check. Returns list of (character, damage, killed)."""
        hits = []
        px, py, pz = position
        for ch in list(self.characters):
            if not ch.alive:
                continue
            cx, cy, cz = ch.center()
            d = math.sqrt((cx - px) ** 2 + (cy - py) ** 2 + (cz - pz) ** 2)
            if d > radius:
                continue
            if not self.world.line_of_sight((px, py, pz + 0.1), (cx, cy, cz)):
                continue
            dmg = max_damage * (1.0 - d / radius) ** 1.4
            direction = ((cx - px) / max(d, 1e-6), (cy - py) / max(d, 1e-6), (cz - pz) / max(d, 1e-6))
            killed = ch.take_damage(dmg, source, "blast", direction)
            hits.append((ch, dmg, killed))
        return hits
