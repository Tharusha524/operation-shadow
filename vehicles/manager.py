"""Spawns and updates vehicles, and handles their weapons (guns, tank shells, rockets).

Rockets are shared with the player's rocket launcher.
"""
from __future__ import annotations

import math
import random

from vehicles.entities import Helicopter, Jeep, KamikazeDrone, PatrolBoat, Tank, Vehicle

KINDS = {"attack_helicopter": Helicopter, "transport_helicopter": Helicopter, "tank": Tank,
         "patrol_boat": PatrolBoat, "player_boat": PatrolBoat, "kamikaze_drone": KamikazeDrone,
         "player_jeep": Jeep, "enemy_jeep": Jeep}
SOUNDS = {"attack_helicopter": "rotor_loop", "transport_helicopter": "rotor_loop", "tank": "tank_loop",
          "patrol_boat": "boat_loop", "player_boat": "boat_loop", "kamikaze_drone": "drone_loop",
          "player_jeep": "jeep_loop", "enemy_jeep": "jeep_loop"}


class Rocket:
    def __init__(self, owner, pos, vel, radius, damage, life=6.0):
        self.owner = owner
        self.pos = list(pos)
        self.vel = list(vel)
        self.radius = radius
        self.damage = damage
        self.life = life
        self.node = None
        self.trail_timer = 0.0


class GunStats:
    """Minimal weapon description for vehicle machine guns (used by CombatSystem.fire)."""

    def __init__(self, damage):
        self.damage = damage
        self.headshot_multiplier = 1.5
        self.range = 250.0
        self.falloff_start = 60.0
        self.falloff_end = 200.0
        self.min_damage_multiplier = 0.6


class VehicleManager:
    def __init__(self, world, combat, game=None, seed=99):
        self.world = world
        self.combat = combat
        self.game = game
        self.rng = random.Random(seed)
        self.vehicles = []
        self.rockets = []
        self.shells = []                 # (time left, target point, owner)
        self.player = None
        self.destroyed_ids = set()
        self.destroy_listeners = []
        self.gun = GunStats(9.0)
        self.water_z = None

    # ------------------------------------------------------------------ spawning
    def spawn(self, kind, vid, **params):
        cls = KINDS[kind]
        if kind == "transport_helicopter":
            params.setdefault("armed", False)
            params.setdefault("health", 5000.0)
            params.setdefault("team", "friendly")
        if kind == "player_boat":
            params.setdefault("armed", False)
            params.setdefault("team", "friendly")
            params.setdefault("loop", False)
            params.setdefault("speed", 6.0)
        if kind == "player_jeep":
            params.setdefault("team", "friendly")
            params.setdefault("driven", True)
            params.setdefault("health", 5000.0)
        if kind == "enemy_jeep":
            params.setdefault("chase_offset", -18.0)
        if vid is not None and self.find(vid) is not None:
            self.remove(self.find(vid))
        v = cls(self, vid, **params)
        v.spawn_kind = kind
        if self.game is not None:
            self._attach_model(v, kind)
        self.vehicles.append(v)
        if v.team != "friendly":
            self.combat.register(v)
        if self.game is not None:
            sound = SOUNDS.get(kind)
            root = v.parts.get("root")
            if sound and root is not None:
                v.loop_sound = self.game.audio.loop_at(sound, root, 0.9 if "helicopter" in kind else 0.6)
        return v

    def _attach_model(self, v, kind):
        from vehicles import models
        mats = self.game.environment.materials
        if kind == "attack_helicopter":
            parts = models.build_helicopter(mats, attack=True)
        elif kind == "transport_helicopter":
            parts = models.build_helicopter(mats, attack=False)
        elif kind == "tank":
            parts = models.build_tank(mats)
        elif kind == "patrol_boat":
            parts = models.build_boat(mats, patrol=True)
        elif kind == "player_boat":
            parts = models.build_boat(mats, patrol=False)
        elif kind in ("player_jeep", "enemy_jeep"):
            parts = models.build_jeep(mats, enemy=kind == "enemy_jeep")
        else:
            parts = models.build_drone(mats, kamikaze=True)
        parts["root"].reparent_to(self.game.render)
        v.parts = parts
        v.sync()

    def find(self, vid):
        for v in self.vehicles:
            if v.id == vid:
                return v
        return None

    def is_destroyed(self, vid):
        return vid in self.destroyed_ids

    def on_destroyed(self, v, source):
        self.destroyed_ids.add(v.id)
        self.combat.unregister(v)
        if v.loop_sound is not None and self.game is not None:
            self.game.audio.stop_loop_sound(v.loop_sound)
            v.loop_sound = None
        for listener in self.destroy_listeners:
            listener(v, source)

    def remove(self, v):
        if v in self.vehicles:
            self.vehicles.remove(v)
        self.combat.unregister(v)
        if v.loop_sound is not None and self.game is not None:
            self.game.audio.stop_loop_sound(v.loop_sound)
        for np_ in v.parts.values():
            if not np_.is_empty():
                np_.remove_node()

    def remove_all(self):
        for v in list(self.vehicles):
            self.remove(v)
        for r in self.rockets:
            if r.node is not None:
                r.node.remove_node()
        self.rockets = []
        self.shells = []
        self.destroyed_ids.clear()

    def command(self, vid, mode=None, target=None, path=None, speed=None, paused=None):
        """Scripted orders from the mission: change mode, hover point, new path, speed or pause."""
        v = self.find(vid)
        if v is None or not v.alive:
            return False
        if path is not None:
            from vehicles.path import Path
            v.path = Path([tuple(p) for p in path], loop=False)
            v.dist = 0.0
            v.finished = False
            if isinstance(v, Helicopter):
                v.mode = "path"
        if speed is not None:
            v.speed = float(speed)
        if paused is not None:
            v.paused = bool(paused)
        if isinstance(v, Helicopter):
            if target is not None:
                v.hover_target = tuple(target)
            if mode is not None:
                v.mode = mode
                v.vel = [0.0, 0.0, 0.0] if mode == "hover" and path is None else v.vel
        return True

    def alive_count(self, kind_prefix):
        return sum(1 for v in self.vehicles if v.alive and v.kind.startswith(kind_prefix))

    def ground_z(self, pos):
        z = self.world.ground_height(pos[0], pos[1], 0.5, pos[2] + 0.5)
        if self.water_z is not None and self.game is not None and self.game.in_water(pos[0], pos[1]):
            z = self.water_z
        return z

    # ------------------------------------------------------------------ weapons
    def blast(self, pos, radius, damage, source=None):
        """Explosion with effects when running in the game, plain radial damage in headless tests."""
        if self.game is not None:
            return self.game.explode(tuple(pos), radius, damage, source)
        return self.combat.explode(tuple(pos), radius, damage, source)

    def fire_gun(self, owner, origin, target, spread=2.0, damage_scale=1.0):
        from enemies.soldier import cone_direction
        d = [target[i] - origin[i] for i in range(3)]
        dist = math.sqrt(sum(v * v for v in d)) or 1.0
        direction = cone_direction(tuple(v / dist for v in d), spread, self.rng)
        self.gun.damage = 9.0 * damage_scale
        res = self.combat.fire(owner, origin, direction, self.gun)
        if self.game is not None:
            end = res.point if res is not None else tuple(origin[i] + direction[i] * 200 for i in range(3))
            if res is not None:
                self.game.effects.impact(res.point, res.normal, res.surface if res.target else "world")
            if self.rng.random() < 0.5:
                self.game.effects.tracer(origin, end, speed=420.0)
            self.game.effects.spawn("flash", origin, life=0.05, size=(0.6, 0.7), texture="flash", blend="add",
                                    color=(1.0, 0.8, 0.5))
            self.game.audio.play_at("shot_enemy", origin, 0.8, min_distance=10.0)
        return res

    def tank_shell(self, owner, muzzle, target):
        if self.game is not None:
            self.game.effects.spawn("flash", muzzle, life=0.12, size=(2.0, 3.0), texture="flash", blend="add",
                                    color=(1.0, 0.7, 0.4))
            self.game.audio.play_at("tank_cannon", muzzle, 1.0, min_distance=25.0)
        d = [target[i] - muzzle[i] for i in range(3)]
        dist = math.sqrt(sum(v * v for v in d)) or 1.0
        hit = self.world.raycast(muzzle, tuple(v / dist for v in d), dist)
        point = hit.point if hit is not None else target
        self.shells.append([dist / 260.0, tuple(point), owner])

    def launch_rocket(self, owner, origin, target, speed=70.0, radius=5.0, damage=300.0):
        d = [target[i] - origin[i] for i in range(3)]
        dist = math.sqrt(sum(v * v for v in d)) or 1.0
        vel = [v / dist * speed for v in d]
        r = Rocket(owner, origin, vel, radius, damage)
        if self.game is not None:
            r.node = self.game.weapons.rocket_model().copy_to(self.game.render)
            r.node.set_pos(*origin)
            r.node.look_at(*target)
            self.game.audio.play_at("rocket_launch", origin, 0.9, min_distance=8.0)
        self.rockets.append(r)
        return r

    # ------------------------------------------------------------------ update
    def update(self, dt):
        for v in list(self.vehicles):
            v.update(dt)
        self._update_rockets(dt)
        keep = []
        for shell in self.shells:
            shell[0] -= dt
            if shell[0] <= 0:
                if self.game is not None:
                    self.game.explode(shell[1], 5.0, 70.0, shell[2])
                else:
                    self.combat.explode(shell[1], 5.0, 70.0, shell[2])
            else:
                keep.append(shell)
        self.shells = keep

    PROXIMITY_FUSE = 3.2

    def _proximity_target(self, start, step):
        """An enemy aircraft that passes within the fuse distance of this frame's flight segment."""
        seg2 = sum(v * v for v in step) or 1e-9
        for v in self.vehicles:
            if not (v.alive and v.team == "enemy" and v.kind in ("helicopter", "drone")):
                continue
            c = v.center()
            t = max(0.0, min(1.0, sum((c[i] - start[i]) * step[i] for i in range(3)) / seg2))
            closest = [start[i] + step[i] * t for i in range(3)]
            if math.dist(c, closest) <= self.PROXIMITY_FUSE + (1.0 if v.kind == "helicopter" else 0.0):
                return v
        return None

    def _update_rockets(self, dt):
        keep = []
        for r in self.rockets:
            r.life -= dt
            step = [v * dt for v in r.vel]
            dist = math.sqrt(sum(s * s for s in step)) or 1e-6
            direction = tuple(s / dist for s in step)
            hit = self.combat.raycast(tuple(r.pos), direction, dist, ignore=r.owner)
            direct = hit.target if hit is not None and isinstance(hit.target, Vehicle) else None
            if direct is None and r.owner is not None and r.owner is self.player:
                direct = self._proximity_target(r.pos, step)    # near-miss on a helicopter or drone still counts
            if hit is not None or direct is not None or r.life <= 0:
                point = hit.point if hit is not None else tuple(r.pos)
                if direct is not None and direct.alive:
                    direct.take_damage(r.damage, r.owner, "blast", direction)   # direct hit: full warhead damage
                if self.game is not None:
                    self.game.explode(point, r.radius, r.damage, r.owner)
                else:
                    self.combat.explode(point, r.radius, r.damage, r.owner)
                if r.node is not None:
                    r.node.remove_node()
                continue
            r.pos = [r.pos[i] + step[i] for i in range(3)]
            r.vel[2] -= 0.8 * dt
            if r.node is not None:
                r.node.set_pos(*r.pos)
            if self.game is not None:
                r.trail_timer -= dt
                if r.trail_timer <= 0:
                    r.trail_timer = 0.025
                    self.game.effects.spawn("smoke", tuple(r.pos), life=1.6, size=(0.25, 1.4), alpha=0.5,
                                            color=(0.75, 0.74, 0.7), texture="smoke", drag=1.5)
                    self.game.effects.spawn("fire", tuple(r.pos), life=0.08, size=(0.35, 0.2), texture="soft",
                                            blend="add", color=(1.0, 0.7, 0.3))
            keep.append(r)
        self.rockets = keep
