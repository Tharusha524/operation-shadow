"""A soldier controlled by AI - used for both enemies and squad mates."""
from __future__ import annotations

import math

from player.health import Health
from player.movement import MotorConfig, MotorInput, PlayerMotor
from systems.combat_system import character_hitboxes
from weapons.factory import create_weapon


def heading_to(dx, dy):
    """Panda3D heading (degrees) that faces along the vector (dx, dy)."""
    return math.degrees(math.atan2(-dx, dy))


def angle_diff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def cone_direction(d, spread_deg, rng):
    """Random unit vector inside a cone of half-angle spread_deg around unit vector d."""
    if spread_deg <= 0:
        return d
    # Two unit vectors perpendicular to d.
    helper = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    ux = d[1] * helper[2] - d[2] * helper[1]
    uy = d[2] * helper[0] - d[0] * helper[2]
    uz = d[0] * helper[1] - d[1] * helper[0]
    ul = math.sqrt(ux * ux + uy * uy + uz * uz)
    ux, uy, uz = ux / ul, uy / ul, uz / ul
    vx, vy, vz = d[1] * uz - d[2] * uy, d[2] * ux - d[0] * uz, d[0] * uy - d[1] * ux
    r = math.tan(math.radians(spread_deg)) * math.sqrt(rng.random())
    a = rng.uniform(0.0, 2.0 * math.pi)
    ca, sa = math.cos(a) * r, math.sin(a) * r
    x, y, z = d[0] + ux * ca + vx * sa, d[1] + uy * ca + vy * sa, d[2] + uz * ca + vz * sa
    n = math.sqrt(x * x + y * y + z * z)
    return x / n, y / n, z / n


class Soldier:
    def __init__(self, manager, team, profile, x, y, heading=0.0, name=None, invulnerable=False,
                 group=None, patrol=None, profile_name="regular", post=None):
        from enemies.enemy_ai import SoldierAI       # local import avoids a cycle
        self.manager = manager
        self.team = team
        self.name = name or ("Hostile" if team == "enemy" else "Ally")
        self.profile = profile
        self.profile_name = profile_name
        self.group = group
        cfg = MotorConfig(walk_speed=profile["walk_speed"], sprint_speed=profile["run_speed"], crouch_speed=1.6,
                          radius=0.33, ground_accel=25.0, ground_decel=25.0)
        # Start standing on a low surface under the spawn point (e.g. a trench's firing step).
        z0 = manager.world.ground_height(x, y, 0.1, 0.5) if hasattr(manager.world, "ground_height") else 0.0
        self.motor = PlayerMotor(manager.world, (x, y, z0), cfg)
        self.health = Health(profile["health"], invulnerable=invulnerable,
                             regen_delay=5.0 if invulnerable else None, regen_rate=25.0)
        self.weapon = create_weapon(manager.weapon_stats[profile["weapon"]], manager.rng, infinite_reserve=True)
        self.facing = heading
        self.aim_pitch = 0.0
        self.move_input = MotorInput(yaw=heading)
        self.crouch = False
        self.aiming = False
        self.killer = None
        self.dead_time = 0.0
        self.fling = None                   # [vx, vy, vz] while thrown by an explosion
        self.fling_tilt = 0.0
        self._fling_back = True
        self.model = None
        self.mount = None                   # callable -> (x, y, z) while riding a vehicle
        self.captive = False                # a prisoner: nobody shoots at them on purpose
        self.silent_death = False           # killed by a silent takedown: nearby allies are not alerted
        if manager.render_root is not None:
            from enemies import soldier_model_mixamo
            from enemies.soldier_model import SoldierModel
            if manager.realistic_models and soldier_model_mixamo.available(team):
                SoldierModel = soldier_model_mixamo.MixamoSoldierModel          # noqa: N806 (realistic soldier)
            self.model = SoldierModel(manager.render_root, manager.materials, team, self.name,
                                      show_name=(team == "friendly" and (invulnerable or profile_name == "wounded")))
        self.ai = SoldierAI(self, profile, patrol=patrol, post=post or (x, y, heading))

    # ------------------------------------------------------------------ combat interface
    @property
    def alive(self):
        return self.health.alive

    @property
    def position(self):
        return self.motor.x, self.motor.y, self.motor.z

    def eye_position(self):
        m = self.motor
        return m.x, m.y, m.z + m.height - 0.15

    def center(self):
        m = self.motor
        return m.x, m.y, m.z + m.height * 0.55

    def hitboxes(self):
        m = self.motor
        return character_hitboxes(m.x, m.y, m.z, m.height)

    def take_damage(self, amount, source, zone, direction):
        if not self.alive:
            return False
        killed = self.health.take_damage(amount)
        if zone == "blast":
            self._blast(amount, direction, killed)
        if not self.silent_death:
            self.ai.on_damaged(source, amount)
        if killed:
            self.killer = source
            fwd = (-math.sin(math.radians(self.facing)), math.cos(math.radians(self.facing)))
            falls_forward = direction[0] * fwd[0] + direction[1] * fwd[1] > 0
            if self.model:
                self.model.start_death(forward=falls_forward)
            self.manager.on_death(self, source, zone)
        return killed

    def _blast(self, amount, direction, killed):
        """Shock wave: the dead are thrown through the air, survivors are knocked back and dazed."""
        dx, dy = direction[0], direction[1]
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        if killed:
            push = min(15.0, 4.0 + amount / 10.0)
            self.fling = [dx * push, dy * push, min(13.0, 4.0 + amount / 14.0)]
            self.fling_roll = self.manager.rng.uniform(-40.0, 40.0)
            self.fling_tilt = 0.0
            self._fling_back = (dx * -math.sin(math.radians(self.facing)) + dy * math.cos(math.radians(self.facing))) < 0
        else:
            push = min(7.0, amount / 8.0)
            self.motor.vx += dx * push
            self.motor.vy += dy * push
            if amount > 15:
                self.ai.stun(min(2.5, amount / 25.0))

    def _update_fling(self, dt):
        """Ballistic flight of a body thrown by an explosion; lands on the ground and stays."""
        vx, vy, vz = self.fling
        m = self.motor
        nx, ny = m.x + vx * dt, m.y + vy * dt
        world = self.manager.world
        if world.line_of_sight((m.x, m.y, m.z + 0.8), (nx, ny, m.z + 0.8)):
            m.x, m.y = nx, ny
        else:
            vx = vy = 0.0                                   # hit a wall: slide down it
        vz -= 18.0 * dt
        m.z += vz * dt
        ground = world.ground_height(m.x, m.y, 0.2, m.z + 0.4) if hasattr(world, "ground_height") else 0.0
        airborne = m.z > ground
        if not airborne:
            if vz < -4.0:                                   # thud: a puff of dust where he lands
                fx = getattr(getattr(self.manager, "game", None), "effects", None)
                if fx is not None:
                    for _ in range(6):
                        fx.spawn("dust", (m.x, m.y, ground + 0.2), vel=(self.manager.rng.uniform(-2, 2),
                                 self.manager.rng.uniform(-2, 2), self.manager.rng.uniform(0.5, 1.5)), life=1.5,
                                 size=(0.5, 1.8), alpha=0.45, color=(0.5, 0.44, 0.36), texture="smoke", drag=2.0)
            m.z = ground
            vx, vy, vz = vx * 0.3, vy * 0.3, 0.0
            if math.hypot(vx, vy) < 0.3:
                self.fling = None
        if self.fling is not None:
            self.fling = [vx, vy, vz]
        target = (80.0 if self._fling_back else -80.0) if airborne else 0.0
        self.fling_tilt += (target - self.fling_tilt) * min(1.0, dt * (5.0 if airborne else 9.0))

    def revive(self, x, y, z=0.0):
        """Bring a squad member back (used when retrying from a checkpoint)."""
        self.health.reset()
        self.killer = None
        self.dead_time = 0.0
        self.fling, self.fling_tilt = None, 0.0
        self.crouch = False
        self.motor.teleport(x, y, z)
        self.motor.height = self.motor.cfg.stand_height
        if self.model is not None:
            self.model.reset_pose()
        if self not in self.manager.combat.characters:
            self.manager.combat.register(self)
        self.ai.set_state("FOLLOW")

    # ------------------------------------------------------------------ actions used by the AI
    def muzzle_position(self):
        if self.model is not None:
            p = self.model.muzzle.get_pos(self.manager.render_root)
            return p.x, p.y, p.z
        ex, ey, ez = self.eye_position()
        h = math.radians(self.facing)
        return ex - math.sin(h) * 0.8, ey + math.cos(h) * 0.8, ez - 0.25

    def shoot_at(self, point, spread_deg):
        """Fire one round towards `point` with a random error cone. Returns True if a shot was fired."""
        if not self.weapon.try_fire():
            return False
        mgr = self.manager
        mx, my, mz = self.muzzle_position()
        dx, dy, dz = point[0] - mx, point[1] - my, point[2] - mz
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        d = (dx / dist, dy / dist, dz / dist)
        d = cone_direction(d, spread_deg, mgr.rng)
        mgr.fire_weapon(self, (mx, my, mz), d)
        return True

    # ------------------------------------------------------------------ update
    def update(self, dt):
        if not self.alive:
            self.dead_time += dt
            if self.fling is not None:
                self._update_fling(dt)
            if self.model:
                self.model.update(dt, x=self.motor.x, y=self.motor.y, z=self.motor.z, heading=self.facing,
                                  move_phase=0, move_speed=0, crouch=False, aim_pitch=0, aiming=False)
                if self.fling_tilt:
                    self.model.root.set_p(self.fling_tilt)
                    self.model.root.set_r(getattr(self, "fling_roll", 0.0) * abs(self.fling_tilt) / 80.0)
                    if self.fling is None and abs(self.fling_tilt) < 0.5:
                        self.fling_tilt = 0.0
                        self.model.root.set_p(0)
                        self.model.root.set_r(0)
            return
        self.health.update(dt)
        self.ai.update(dt)
        self.move_input.crouch = self.crouch
        if self.mount is not None:
            m = self.motor
            m.x, m.y, m.z = self.mount()
            m.vx = m.vy = m.vz = 0.0
            m.grounded = True
        else:
            self.motor.update(dt, self.move_input)
        self.motor.pop_events()
        self.weapon.update(dt)
        self.weapon.pop_events()
        if self.model:
            self.model.update(dt, x=self.motor.x, y=self.motor.y, z=self.motor.z, heading=self.facing,
                              move_phase=self.motor.bob_phase, move_speed=self.motor.horizontal_speed,
                              crouch=self.motor.crouching, aim_pitch=self.aim_pitch, aiming=self.aiming,
                              reloading=self.weapon.reloading, shots=self.weapon.shots_fired,
                              vel=(self.motor.vx, self.motor.vy))
