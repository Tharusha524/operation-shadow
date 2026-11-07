"""Creates, updates and coordinates all AI soldiers (enemies and squad mates).

Also provides the shared services the AI needs: path-finding budget, cover reservations,
hearing, ally alerts, enemy grenades, call-outs, kill tracking and soldier separation.
"""
from __future__ import annotations

import dataclasses
import json
import math
import random
import time

from core.paths import DATA_DIR
from enemies.soldier import Soldier, angle_diff, heading_to
from weapons.grenade import GrenadeProjectile
from weapons.weapon_base import load_weapon_data

ENEMY_WEAPONS = ("vk74", "mg_npc")      # these get the difficulty damage multiplier
PATHS_PER_FRAME = 3
PATH_MS_PER_FRAME = 6.0
CALLOUTS = {
    "contact": ["Contact! Enemy spotted!", "Hostiles, ahead!", "Eyes on enemy!"],
    "reload": ["Reloading!", "Changing mags!"],
    "kill": ["Target down.", "Got him.", "Enemy down."],
    "clear": ["Area clear.", "All clear here."],
    "grenade": ["Grenade! Move!"],
    "wait": ["Halden! Don't leave us behind!", "Wait for us - I can't go any faster!"],
    "pinned": ["Contact! Get down, get down!", "They're right on top of us!"],
}


def segment_hits_sphere(a, b, center, radius):
    d = [b[i] - a[i] for i in range(3)]
    seg2 = sum(v * v for v in d) or 1e-9
    t = max(0.0, min(1.0, sum((center[i] - a[i]) * d[i] for i in range(3)) / seg2))
    closest = [a[i] + d[i] * t for i in range(3)]
    return sum((closest[i] - center[i]) ** 2 for i in range(3)) < radius * radius


class SoldierManager:
    def __init__(self, world, combat, nav, *, render_root=None, materials=None, game=None, difficulty="normal",
                 seed=1234):
        self.world = world
        self.combat = combat
        self.nav = nav
        self.render_root = render_root
        self.materials = materials
        self.game = game
        self.rng = random.Random(seed)
        data = json.loads((DATA_DIR / "enemies.json").read_text(encoding="utf-8"))
        self.profiles = data["profiles"]
        self.difficulty = data["difficulty"].get(difficulty, data["difficulty"]["normal"])
        stats, self.grenade_stats = load_weapon_data(DATA_DIR / "weapons.json")
        # Enemy weapons get the difficulty damage multiplier.
        self.weapon_stats = dict(stats)
        for wid, st in stats.items():
            if wid in ENEMY_WEAPONS:
                self.weapon_stats[wid] = dataclasses.replace(st, damage=st.damage * self.difficulty["enemy_damage"])
        self.soldiers = []
        self.player = None
        self.grenades = []
        self._covers = {}
        self._paths_this_frame = 0
        self._path_ms = 0.0
        self._callout_timer = 0.0
        self.kill_listeners = []         # callables(soldier, killer, zone)
        self.player_hidden = False       # story videos: actors ignore the (invisible) player
        self.realistic_models = False    # True: rigged Mixamo soldiers (set by the game from the settings)
        self.visibility = 1.0            # < 1 at night: enemies see the player from shorter range
        self.lit_zones = []              # (x, y, radius) - searchlights etc. where night does not hide you
        self.smoke_clouds = []           # (x, y, z, radius) - smoke grenades block sight
        combat.noise_listeners.append(self.on_noise)

    # ------------------------------------------------------------------ spawning
    def spawn(self, team, x, y, heading=0.0, profile="regular", name=None, group=None, patrol=None,
              invulnerable=False):
        p = self.profiles[profile]
        s = Soldier(self, team, p, x, y, heading, name=name, invulnerable=invulnerable, group=group,
                    patrol=patrol, profile_name=profile)
        if team == "friendly":
            s.ai.formation_index = sum(1 for o in self.soldiers if o.team == "friendly"
                                       and (o.health.invulnerable or o.profile_name == "wounded"))
        self.soldiers.append(s)
        self.combat.register(s)
        return s

    def remove_all(self):
        for s in self.soldiers:
            self.combat.unregister(s)
            if s.model:
                s.model.remove()
        self.soldiers = []
        for g in self.grenades:
            if g.node is not None:
                g.node.remove_node()
        self.grenades = []
        self._covers.clear()

    def remove_team(self, team):
        keep = []
        for s in self.soldiers:
            if s.team == team:
                self.combat.unregister(s)
                self.release_cover(s)
                if s.model:
                    s.model.remove()
            else:
                keep.append(s)
        self.soldiers = keep
        for g in list(self.grenades):
            if getattr(g.owner, "team", None) == team:
                if g.node is not None:
                    g.node.remove_node()
                self.grenades.remove(g)

    def cull_corpses(self, keep=20):
        dead = sorted((s for s in self.soldiers if not s.alive), key=lambda s: -s.dead_time)
        for s in dead[:-keep] if len(dead) > keep else []:
            self.combat.unregister(s)
            if s.model:
                s.model.remove()
            self.soldiers.remove(s)

    def set_difficulty(self, name):
        data = json.loads((DATA_DIR / "enemies.json").read_text(encoding="utf-8"))["difficulty"]
        self.difficulty = data.get(name, data["normal"])
        base, _ = load_weapon_data(DATA_DIR / "weapons.json")
        for wid in ENEMY_WEAPONS:
            self.weapon_stats[wid] = dataclasses.replace(base[wid], damage=base[wid].damage * self.difficulty["enemy_damage"])

    # ------------------------------------------------------------------ sight lines
    def clear_view(self, a, b):
        """Line of sight that also stops at smoke clouds."""
        if not self.world.line_of_sight(a, b):
            return False
        return not any(segment_hits_sphere(a, b, c[:3], c[3]) for c in self.smoke_clouds)

    # ------------------------------------------------------------------ night vision range
    def vision_scale(self, viewer, target):
        """How far `viewer` can see `target`: shorter at night, unless the target stands in light."""
        if viewer.team != "enemy" or self.visibility >= 1.0:
            return 1.0
        tx, ty = target.position[0], target.position[1]
        for x, y, r in self.lit_zones:
            if (tx - x) ** 2 + (ty - y) ** 2 <= r * r:
                return 1.0
        return self.visibility

    # ------------------------------------------------------------------ queries
    def hostiles(self, team):
        out = [s for s in self.soldiers if s.team != team and s.alive and not s.captive]
        if self.player is not None and team != self.player.team and self.player.alive and not self.player_hidden:
            out.append(self.player)
        return out

    def allies(self, team):
        return [s for s in self.soldiers if s.team == team and s.alive]

    def group_alive(self, group):
        return [s for s in self.soldiers if s.group == group and s.alive]

    def group_count(self, group):
        return sum(1 for s in self.soldiers if s.group == group)

    def accuracy_scale(self, soldier):
        return self.difficulty["enemy_accuracy"] if soldier.team == "enemy" else 1.0

    # ------------------------------------------------------------------ services for the AI
    def request_path(self, soldier, start, goal):
        """Path list, None (no path) or False (budget used up this frame - ask again next frame).

        Path-finding is limited to a few searches and ~6 ms per frame so big battles never stutter.
        """
        if self._paths_this_frame >= PATHS_PER_FRAME or self._path_ms > PATH_MS_PER_FRAME:
            return False
        self._paths_this_frame += 1
        t0 = time.perf_counter()
        path = self.nav.find_path(start, goal)
        self._path_ms += (time.perf_counter() - t0) * 1000.0
        return path

    def find_cover(self, soldier, threat):
        occupied = [pos for owner, pos in self._covers.items() if owner is not soldier]
        return self.nav.find_cover(soldier.motor.x, soldier.motor.y, threat, occupied=occupied)

    def claim_cover(self, soldier, pos):
        self._covers[soldier] = pos

    def release_cover(self, soldier):
        self._covers.pop(soldier, None)

    def alert_allies(self, soldier, target, position, radius=30.0):
        for other in self.allies(soldier.team):
            if other is soldier:
                continue
            if math.hypot(other.motor.x - soldier.motor.x, other.motor.y - soldier.motor.y) <= radius:
                other.ai.alert(target, position)

    def on_noise(self, position, radius, team, source):
        for s in self.soldiers:
            if not s.alive or s.team == team:
                continue
            if math.hypot(s.motor.x - position[0], s.motor.y - position[1]) <= radius:
                s.ai.hear(position, source)

    def callout(self, soldier, kind):
        if self.game is None:
            return
        if soldier.team == "enemy":
            if kind in ("contact", "grenade") and self.rng.random() < 0.6:
                self.game.audio.play_at(f"enemy_shout_{self.rng.randrange(3)}", soldier.eye_position(), 0.8)
            return
        if self._callout_timer > 0.0:
            return
        self._callout_timer = 6.0
        lines = CALLOUTS.get(kind)
        if lines:
            self.game.radio(soldier.name, self.rng.choice(lines), beep=False, seconds=2.5)

    def fire_weapon(self, soldier, origin, direction):
        game = self.game
        result = self.combat.fire(soldier, origin, direction, soldier.weapon.stats)
        self.combat.emit_noise(origin, 60.0, soldier.team, soldier)
        if game is None:
            return result
        end = [origin[i] + direction[i] * soldier.weapon.stats.range for i in range(3)]
        if result is not None:
            end = result.point
            game.effects.impact(result.point, result.normal, result.surface if result.target else "world")
        if soldier.weapon.shots_fired % max(1, soldier.weapon.stats.tracer_every) == 0:
            game.effects.tracer(origin, end)
        game.effects.spawn("flash", origin, life=0.05, size=(0.4, 0.5), texture="flash", blend="add",
                           color=(1.0, 0.8, 0.5))
        game.audio.play_at(soldier.weapon.stats.sound, origin, 0.7 if soldier.team == "enemy" else 0.55,
                           min_distance=6.0)
        return result

    def throw_grenade(self, soldier, target_pos):
        sx, sy, sz = soldier.eye_position()
        tx, ty = target_pos[0], target_pos[1]
        d = math.hypot(tx - sx, ty - sy)
        t = max(0.8, d / 14.0)                     # flight time
        g = 18.0
        vx, vy = (tx - sx) / t, (ty - sy) / t
        vz = (0.2 - sz + 0.5 * g * t * t) / t
        gren = GrenadeProjectile((sx, sy, sz), (vx, vy, vz), self.grenade_stats.fuse, owner=soldier)
        if self.game is not None:
            gren.node = self.game.weapons._grenade_template().copy_to(self.game.render)
            gren.node.set_pos(sx, sy, sz)
        self.grenades.append(gren)
        self.callout(soldier, "grenade")

    def on_death(self, soldier, killer, zone):
        self.release_cover(soldier)
        soldier.ai.set_state("DEAD")
        for listener in self.kill_listeners:
            listener(soldier, killer, zone)
        # Allies who saw it become alert. A silent takedown is only noticed by someone close who can see it.
        if killer is not None:
            for other in self.allies(soldier.team):
                d = math.hypot(other.motor.x - soldier.motor.x, other.motor.y - soldier.motor.y)
                if soldier.silent_death:
                    if d > 9.0 or not self.world.line_of_sight(other.eye_position(), soldier.center()):
                        continue
                    if abs(angle_diff(heading_to(soldier.motor.x - other.motor.x, soldier.motor.y - other.motor.y),
                                      other.facing)) > other.profile["fov"] / 2:
                        continue
                if d < 25:
                    other.ai.alert(killer, killer.position)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        self._paths_this_frame = 0
        self._path_ms = 0.0
        self._callout_timer = max(0.0, self._callout_timer - dt)
        order = list(self.soldiers)
        self.rng.shuffle(order)            # fair path-finding budget
        for s in order:
            s.update(dt)
        self._separate()
        self._update_grenades(dt)

    def _separate(self):
        bodies = [s for s in self.soldiers if s.alive]
        min_d = 0.7
        for i, a in enumerate(bodies):
            for b in bodies[i + 1:]:
                dx, dy = b.motor.x - a.motor.x, b.motor.y - a.motor.y
                d = math.hypot(dx, dy)
                if 1e-6 < d < min_d:
                    push = (min_d - d) / 2.0
                    nx, ny = dx / d, dy / d
                    self._nudge(a, -nx * push, -ny * push)
                    self._nudge(b, nx * push, ny * push)
            if self.player is not None and self.player.alive:
                pm = self.player.motor
                dx, dy = a.motor.x - pm.x, a.motor.y - pm.y
                d = math.hypot(dx, dy)
                if 1e-6 < d < min_d:
                    push = min_d - d
                    self._nudge(a, dx / d * push * 0.8, dy / d * push * 0.8)
                    self._nudge_player(-dx / d * push * 0.2, -dy / d * push * 0.2)

    def _nudge(self, s, dx, dy):
        m = s.motor
        x, y, _ = self.world.resolve_horizontal(m.x + dx, m.y + dy, m.cfg.radius, m.z, m.z + m.height, m.cfg.step_height)
        m.x, m.y = x, y

    def _nudge_player(self, dx, dy):
        m = self.player.motor
        x, y, _ = self.world.resolve_horizontal(m.x + dx, m.y + dy, m.cfg.radius, m.z, m.z + m.height, m.cfg.step_height)
        m.x, m.y = x, y

    def _update_grenades(self, dt):
        alive = []
        for g in self.grenades:
            if g.update(dt, self.world):
                if self.game is not None:
                    self.game.explode(tuple(g.pos), self.grenade_stats.radius, self.grenade_stats.max_damage, g.owner)
                    g.node.remove_node()
                else:
                    self.combat.explode(tuple(g.pos), self.grenade_stats.radius, self.grenade_stats.max_damage, g.owner)
                continue
            if g.node is not None:
                g.node.set_pos(*g.pos)
            if g.bounced and self.game is not None:
                self.game.audio.play_at("grenade_bounce", g.pos, 0.6)
            alive.append(g)
        self.grenades = alive

    def live_grenades_near(self, pos, radius):
        return [g for g in self.grenades if math.dist(g.pos, pos) < radius]
