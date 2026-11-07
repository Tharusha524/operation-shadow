"""Vehicles: attack/transport helicopters, tanks, patrol boats and kamikaze drones.

Each vehicle takes part in combat like a soldier (it has hit boxes and health). Armour
decides how much damage bullets do; explosions ("blast" damage, e.g. rockets) always hurt.
"""
from __future__ import annotations

import math
import random

from player.health import Health
from systems.combat_system import character_hitboxes  # noqa: F401  (kept for symmetry)
from vehicles.path import Path


def _heading_to(dx, dy):
    return math.degrees(math.atan2(-dx, dy))


def _angle_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


class Vehicle:
    kind = "vehicle"
    bullet_factor = 1.0          # damage multiplier for bullets
    blast_factor = 1.0           # damage multiplier for explosions
    death_blast = (6.0, 60.0)    # radius, damage of the vehicle's own explosion

    def __init__(self, manager, vid, team="enemy", health=500.0, pos=(0, 0, 0), heading=0.0, path=None,
                 speed=8.0, loop=False):
        self.manager = manager
        self.id = vid
        self.team = team
        self.health = Health(health)
        self.pos = list(pos)
        self.heading = heading
        self.pitch = 0.0
        self.roll = 0.0
        self.path = Path(path, loop=loop) if path else None
        self.dist = 0.0
        self.speed = speed
        self.paused = False
        self.finished = False
        self.dead_time = 0.0
        self.parts = {}          # NodePaths created by the model builder (root, rotor, turret ...)
        self.loop_sound = None
        self.rng = manager.rng
        if self.path is not None:
            self.pos = list(self.path.point_at(0.0))
            self.heading = self.path.heading_at(0.0)

    # ------------------------------------------------------------------ combat interface
    @property
    def alive(self):
        return self.health.alive

    @property
    def position(self):
        return tuple(self.pos)

    def center(self):
        return self.pos[0], self.pos[1], self.pos[2] + 1.0

    def eye_position(self):
        return self.center()

    def hitboxes(self):
        x, y, z = self.center()
        return (("body", "sphere", (x, y, z, 1.5)),)

    def take_damage(self, amount, source, zone, direction):
        if not self.alive:
            return False
        factor = self.blast_factor if zone == "blast" else self.bullet_factor
        killed = self.health.take_damage(amount * factor)
        if amount * factor > 0:
            self.on_hit(source)
        if killed:
            self.on_destroyed(source)
        return killed

    def on_hit(self, source):
        pass

    def on_destroyed(self, source):
        g = self.manager.game
        if g is not None:
            g.explode(self.center(), self.death_blast[0], self.death_blast[1], None)
            g.add_fire(self.position, 1.4)
        self.manager.on_destroyed(self, source)

    # ------------------------------------------------------------------ movement
    def follow_path(self, dt):
        if self.path is None or self.paused or self.finished:
            return
        self.dist += self.speed * dt
        if not self.path.loop and self.dist >= self.path.length:
            self.dist = self.path.length
            self.finished = True
        self.pos = list(self.path.point_at(self.dist))
        self.heading = self.path.heading_at(self.dist)

    def update(self, dt):
        if self.alive:
            self.follow_path(dt)
        else:
            self.dead_time += dt
        self.sync()

    def sync(self):
        root = self.parts.get("root")
        if root is not None and not root.is_empty():
            root.set_pos(*self.pos)
            root.set_hpr(self.heading, self.pitch, self.roll)

    def player(self):
        return self.manager.player

    def can_see_player(self, origin):
        p = self.player()
        if p is None or not p.alive:
            return False
        return self.manager.world.line_of_sight(origin, p.eye_position())


class Helicopter(Vehicle):
    """Attack helicopter: flies in along a path, then circles the player and strafes."""
    kind = "helicopter"
    bullet_factor = 0.06
    blast_factor = 1.6
    death_blast = (7.0, 80.0)

    def __init__(self, manager, vid, armed=True, orbit_radius=55.0, altitude=24.0, **kw):
        kw.setdefault("health", 900.0)
        kw.setdefault("speed", 28.0)
        super().__init__(manager, vid, **kw)
        self.armed = armed
        self.orbit_radius = orbit_radius
        self.altitude = altitude
        self.mode = "path" if self.path else ("attack" if armed else "hover")
        self.orbit_angle = self.rng.uniform(0, 360)
        self.gun_timer = 3.0
        self.burst_left = 0
        self.shot_timer = 0.0
        self.rocket_timer = 9.0
        self.rotor_angle = 0.0
        self.crash_vz = 0.0
        self.hover_target = None
        self.vel = [0.0, 0.0, 0.0]

    def hitboxes(self):
        x, y, z = self.pos
        h = math.radians(self.heading)
        tx, ty = x + math.sin(h) * 5.0, y - math.cos(h) * 5.0
        return (("body", "sphere", (x, y, z + 1.2, 2.3)), ("body", "sphere", (tx, ty, z + 1.6, 1.1)))

    def on_hit(self, source):
        if self.mode == "path" and self.armed:
            self.mode = "attack"

    def on_destroyed(self, source):
        self.mode = "crash"
        self.crash_vz = 0.0
        g = self.manager.game
        if g is not None:
            g.effects.explosion(self.center())
            g.audio.play_at("explosion", self.center(), 1.0, min_distance=20.0)
            g.radio("", "Helicopter down!", seconds=2.0)
        self.manager.on_destroyed(self, source)

    def fly_to(self, target, dt, max_speed=30.0, accel=12.0):
        """Smooth flying towards a point (used by attack orbit and scripted hover)."""
        d = [target[i] - self.pos[i] for i in range(3)]
        dist = math.sqrt(sum(v * v for v in d)) or 1e-6
        want = [v / dist * min(max_speed, dist * 1.2) for v in d]
        for i in range(3):
            dv = want[i] - self.vel[i]
            step = max(-accel * dt, min(accel * dt, dv))
            self.vel[i] += step
            self.pos[i] += self.vel[i] * dt
        speed_h = math.hypot(self.vel[0], self.vel[1])
        self.pitch = -min(18.0, speed_h * 0.6)
        return dist

    def update(self, dt):
        self.rotor_angle = (self.rotor_angle + dt * 1400.0) % 360.0
        g = self.manager.game
        if self.mode == "crash":
            self.dead_time += dt
            self.crash_vz -= 9.0 * dt
            self.pos[2] += self.crash_vz * dt
            self.heading += 260.0 * dt
            self.roll = min(35.0, self.roll + 20 * dt)
            if g is not None and int(self.dead_time * 10) % 2 == 0:
                g.effects.spawn("smoke", self.center(), life=3.0, size=(1.0, 4.0), alpha=0.6, color=(0.1, 0.1, 0.1),
                                texture="smoke", drag=0.5)
            if self.pos[2] <= self.manager.ground_z(self.pos):
                self.pos[2] = self.manager.ground_z(self.pos)
                self.mode = "wreck"
                if g is not None:
                    g.explode(self.center(), 8.0, 120.0, None)
                    g.add_fire(self.position, 2.0)
            self.sync_with_rotor()
            return
        if self.mode == "wreck" or not self.alive:
            self.sync_with_rotor(spin=False)
            return
        if self.mode == "path":
            self.follow_path(dt)
            if self.finished:
                self.mode = "attack" if self.armed else "hover"
                self.vel = [0.0, 0.0, 0.0]
        elif self.mode == "hover":
            if self.hover_target is not None:
                self.fly_to(self.hover_target, dt, max_speed=14.0, accel=6.0)
            self.pitch *= 0.95
        elif self.mode == "attack":
            p = self.player()
            if p is not None:
                px, py, pz = p.position
                self.orbit_angle = (self.orbit_angle + dt * 8.0) % 360.0
                a = math.radians(self.orbit_angle)
                target = (px + math.cos(a) * self.orbit_radius, py + math.sin(a) * self.orbit_radius,
                          pz + self.altitude)
                self.fly_to(target, dt)
                want = _heading_to(px - self.pos[0], py - self.pos[1])
                self.heading += max(-90 * dt, min(90 * dt, _angle_diff(want, self.heading)))
                self._weapons(dt, p)
        self.sync_with_rotor()

    def _weapons(self, dt, p):
        g = self.manager.game
        nose = self.center()
        self.gun_timer -= dt
        self.rocket_timer -= dt
        if self.burst_left > 0:
            self.shot_timer -= dt
            if self.shot_timer <= 0:
                self.shot_timer = 0.07
                self.burst_left -= 1
                self.manager.fire_gun(self, nose, p.center(), spread=2.2, damage_scale=1.0)
        elif self.gun_timer <= 0 and self.can_see_player(nose):
            self.gun_timer = self.rng.uniform(2.5, 4.0)
            self.burst_left = self.rng.randint(8, 14)
            if g is not None:
                g.radio("", "Incoming fire from the helicopter!", seconds=1.6) if self.rng.random() < 0.15 else None
        if self.rocket_timer <= 0 and self.can_see_player(nose):
            self.rocket_timer = self.rng.uniform(8.0, 12.0)
            px, py, pz = p.position
            for i in range(2):
                err = (self.rng.uniform(-6, 6), self.rng.uniform(-6, 6))
                self.manager.launch_rocket(self, nose, (px + err[0], py + err[1], pz), speed=55.0)

    def sync_with_rotor(self, spin=True):
        self.sync()
        rotor = self.parts.get("rotor")
        if rotor is not None and spin:
            rotor.set_h(self.rotor_angle)
        tail = self.parts.get("tail_rotor")
        if tail is not None and spin:
            tail.set_p(self.rotor_angle * 1.7)


class Tank(Vehicle):
    """Main battle tank: drives a path, turns its turret to the player and fires its cannon."""
    kind = "tank"
    bullet_factor = 0.0
    blast_factor = 1.0
    death_blast = (8.0, 90.0)

    def __init__(self, manager, vid, **kw):
        kw.setdefault("health", 1200.0)
        kw.setdefault("speed", 5.0)
        super().__init__(manager, vid, **kw)
        self.turret_heading = 0.0       # relative to the hull
        self.fire_timer = self.rng.uniform(5.0, 8.0)
        self.falling = False
        self.fall_t = 0.0

    def hitboxes(self):
        x, y, z = self.pos
        return (("body", "sphere", (x, y, z + 1.3, 2.6)),)

    def center(self):
        return self.pos[0], self.pos[1], self.pos[2] + 1.4

    def fall(self):
        """Used when the bridge under the tank is destroyed."""
        self.falling = True
        self.paused = True

    def update(self, dt):
        g = self.manager.game
        if self.falling:
            self.fall_t += dt
            self.pos[2] = max(-9.0, self.pos[2] - (2.0 + self.fall_t * 9.0) * dt)    # rests on the river bed
            self.pitch = min(40.0, self.pitch + 30 * dt)
            if self.pos[2] < -6.0 and self.alive:
                self.health.take_damage(1e9)
                if g is not None:
                    g.effects.explosion(self.center())
                    g.audio.play_at("explosion", self.center(), 1.0, min_distance=15.0)
                self.manager.on_destroyed(self, None)
            self.sync()
            return
        if not self.alive:
            self.dead_time += dt
            self.sync()
            return
        self.follow_path(dt)
        p = self.player()
        if p is not None and p.alive:
            px, py, _ = p.position
            want = _angle_diff(_heading_to(px - self.pos[0], py - self.pos[1]), self.heading)
            self.turret_heading += max(-25 * dt, min(25 * dt, _angle_diff(want, self.turret_heading)))
            self.fire_timer -= dt
            muzzle = (self.pos[0], self.pos[1], self.pos[2] + 2.3)
            aligned = abs(_angle_diff(want, self.turret_heading)) < 4.0
            if self.fire_timer <= 0 and aligned and self.can_see_player(muzzle):
                self.fire_timer = self.rng.uniform(6.0, 9.0)
                err = (self.rng.uniform(-5, 5), self.rng.uniform(-5, 5))
                self.manager.tank_shell(self, muzzle, (px + err[0], py + err[1], p.position[2]))
        self.sync()
        turret = self.parts.get("turret")
        if turret is not None:
            turret.set_h(self.turret_heading)


class PatrolBoat(Vehicle):
    kind = "boat"
    bullet_factor = 0.45
    blast_factor = 1.4
    death_blast = (5.0, 50.0)

    def __init__(self, manager, vid, armed=True, **kw):
        kw.setdefault("health", 450.0)
        kw.setdefault("speed", 9.0)
        kw.setdefault("loop", True)
        super().__init__(manager, vid, **kw)
        self.armed = armed
        self.gun_timer = 2.0
        self.burst_left = 0
        self.shot_timer = 0.0
        self.t = 0.0

    def hitboxes(self):
        x, y, z = self.pos
        return (("body", "sphere", (x, y, z + 0.8, 2.2)),)

    def update(self, dt):
        self.t += dt
        if not self.alive:
            self.dead_time += dt
            self.pos[2] -= 0.6 * dt                      # sinks
            self.roll = min(25.0, self.roll + 8 * dt)
            self.sync()
            return
        self.follow_path(dt)
        if self.manager.water_z is not None:
            self.pos[2] = self.manager.water_z
        self.roll = math.sin(self.t * 1.7) * 3.0
        self.pitch = math.sin(self.t * 1.3) * 2.0
        g = self.manager.game
        if g is not None and not self.paused and not self.finished and int(self.t * 20) % 2 == 0:
            h = math.radians(self.heading)
            g.effects.spawn("smoke", (self.pos[0] + math.sin(h) * 3.2, self.pos[1] - math.cos(h) * 3.2, self.pos[2] + 0.2),
                            life=1.2, size=(0.6, 2.2), alpha=0.35, color=(0.75, 0.8, 0.82), texture="smoke", drag=2.0)
        p = self.player()
        gun = (self.pos[0], self.pos[1], self.pos[2] + 1.6)
        if self.armed and self.team == "enemy" and p is not None and p.alive and math.dist(gun, p.position) < 90:
            self.gun_timer -= dt
            if self.burst_left > 0:
                self.shot_timer -= dt
                if self.shot_timer <= 0:
                    self.shot_timer = 0.09
                    self.burst_left -= 1
                    self.manager.fire_gun(self, gun, p.center(), spread=3.5, damage_scale=0.7)
            elif self.gun_timer <= 0 and self.can_see_player(gun):
                self.gun_timer = self.rng.uniform(1.8, 3.2)
                self.burst_left = self.rng.randint(5, 9)
        self.sync()


class KamikazeDrone(Vehicle):
    kind = "drone"
    bullet_factor = 1.0
    blast_factor = 1.0
    death_blast = (2.5, 25.0)

    def __init__(self, manager, vid, **kw):
        kw.setdefault("health", 25.0)
        kw.setdefault("speed", 13.0)
        super().__init__(manager, vid, **kw)
        self.vel = [0.0, 0.0, 0.0]
        self.t = 0.0
        self.falling = False

    def hitboxes(self):
        x, y, z = self.pos
        return (("body", "sphere", (x, y, z, 0.45)),)

    def center(self):
        return tuple(self.pos)

    def on_destroyed(self, source):
        self.falling = True
        self.manager.on_destroyed(self, source)

    def update(self, dt):
        self.t += dt
        g = self.manager.game
        if self.falling:
            self.vel[2] -= 12.0 * dt
            for i in range(3):
                self.pos[i] += self.vel[i] * dt
            ground = self.manager.ground_z(self.pos)
            if self.pos[2] <= ground + 0.2:
                self.falling = False
                self.manager.blast(tuple(self.pos), 2.5, 20.0, None)
                self.manager.remove(self)
                return
            self.sync()
            return
        p = self.player()
        if p is None or not p.alive:
            self.sync()
            return
        tx, ty, tz = p.center()
        d = [tx - self.pos[0], ty - self.pos[1], tz + 1.5 - self.pos[2]]
        dist = math.sqrt(sum(v * v for v in d)) or 1e-6
        if dist < 6:
            d[2] -= 1.5          # dive at the end
        want = [v / dist * self.speed for v in d]
        for i in range(3):
            self.vel[i] += (want[i] - self.vel[i]) * min(1.0, dt * 2.5)
            self.pos[i] += self.vel[i] * dt
        self.pos[0] += math.sin(self.t * 6.0) * 0.6 * dt          # a little wobble
        self.heading = _heading_to(self.vel[0], self.vel[1])
        if dist < 2.4:
            self.health.take_damage(1e9)
            self.manager.blast(tuple(self.pos), 6.0, 90.0, self)
            self.manager.on_destroyed(self, None)
            self.manager.remove(self)
            return
        self.sync()
        for name in ("rotor1", "rotor2", "rotor3", "rotor4"):
            r = self.parts.get(name)
            if r is not None:
                r.set_h(self.t * 2000.0)


class Jeep(Vehicle):
    """Light 4x4. The player's one is driven with W/S/A/D; enemy jeeps chase along a road path."""
    kind = "jeep"
    bullet_factor = 0.5
    blast_factor = 1.2
    death_blast = (6.0, 70.0)
    MAX_SPEED = 24.0
    REVERSE_SPEED = 7.0
    ACCEL = 8.0
    BRAKE = 18.0
    ROLL = 3.0
    STEER_RATE = 65.0              # degrees per second at full lock and speed
    HALF_LENGTH = 1.3
    RADIUS = 1.0

    def __init__(self, manager, vid, driven=False, chase_offset=None, **kw):
        kw.setdefault("health", 300.0)
        kw.setdefault("speed", 14.0)
        super().__init__(manager, vid, **kw)
        self.driven = driven
        self.velocity = 0.0
        self.chase_offset = chase_offset       # enemy jeeps: stay this far ahead (+) / behind (-) of the player
        self.breakables = set()                # prop ids this jeep can smash through
        self.events = []                       # ("ram", [ids]) or ("crash", speed)
        self._player_along = None
        self._player_rate = 0.0

    def hitboxes(self):
        x, y, z = self.pos
        return (("body", "sphere", (x, y, z + 1.0, 1.7)),)

    def center(self):
        return self.pos[0], self.pos[1], self.pos[2] + 1.0

    def forward(self, heading=None):
        h = math.radians(self.heading if heading is None else heading)
        return -math.sin(h), math.cos(h)

    def blocking(self, x, y, heading):
        """Colliders the jeep body would overlap at (x, y, heading): (blocked, set of tags)."""
        world = self.manager.world
        z = self.pos[2]
        fx, fy = self.forward(heading)
        tags, blocked = set(), False
        for off in (self.HALF_LENGTH, -self.HALF_LENGTH):
            cx, cy = x + fx * off, y + fy * off
            for col in world.query_circle(cx, cy, self.RADIUS):
                if col.z_max > z + 0.45 and col.z_min < z + 1.7 and col.overlaps_circle(cx, cy, self.RADIUS):
                    blocked = True
                    tags.add(col.tag)
            g = self.manager.game
            if g is not None and g.in_water(cx, cy):
                blocked = True
                tags.add("water")
        return blocked, tags

    def drive(self, dt, throttle, steer, brake):
        """Arcade driving: throttle/steer in -1..1, brake = handbrake."""
        v = self.velocity
        if brake:
            v -= math.copysign(min(abs(v), self.BRAKE * dt), v)
        elif throttle > 0:
            v += (self.ACCEL * throttle if v >= 0 else self.BRAKE) * dt
        elif throttle < 0:
            v -= (self.BRAKE if v > 0 else self.ACCEL * 0.7 * -throttle) * dt
        else:
            v -= math.copysign(min(abs(v), self.ROLL * dt), v)
        v = max(-self.REVERSE_SPEED, min(self.MAX_SPEED, v))
        turn = steer * self.STEER_RATE * min(1.0, abs(v) / 6.0) * (1.0 if v >= 0 else -1.0)
        heading = self.heading - turn * dt
        fx, fy = self.forward(heading)
        nx, ny = self.pos[0] + fx * v * dt, self.pos[1] + fy * v * dt
        blocked, tags = self.blocking(nx, ny, heading)
        if blocked:
            rams = sorted(t for t in tags if t in self.breakables)
            if rams and abs(v) > 7.0 and tags <= set(rams):
                self.events.append(("ram", rams))
                v *= 0.7
                self.pos[0], self.pos[1], self.heading = nx, ny, heading
            else:
                if abs(v) > 2.0:
                    self.events.append(("crash", abs(v)))
                v = -v * 0.2
        else:
            self.pos[0], self.pos[1], self.heading = nx, ny, heading
        self.velocity = v
        self.pos[2] = self.manager.world.ground_height(self.pos[0], self.pos[1], 0.6, self.pos[2] + 0.5)

    def update(self, dt):
        if not self.alive:
            self.dead_time += dt
            self.sync()
            return
        if self.driven:
            self.sync()
            return
        p = self.player()
        if self.chase_offset is not None and self.path is not None and p is not None:
            along = self.path.closest_distance(p.position)
            if self._player_along is not None and dt > 0.0:
                raw = (along - self._player_along) / dt
                self._player_rate += (raw - self._player_rate) * min(1.0, dt * 2.0)   # smoothed player speed
            self._player_along = along
            gap = along + self.chase_offset - self.dist
            self.speed = max(0.0, min(27.0, self._player_rate + gap * 1.2))
        self.follow_path(dt)
        self.velocity = self.speed if not self.finished else 0.0
        self.sync()
