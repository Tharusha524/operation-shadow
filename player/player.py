"""The player: connects keyboard/mouse input, movement physics, camera, health and weapons."""
from __future__ import annotations

import math

from config import constants as C
from player.camera import FirstPersonCamera
from player.health import Health
from player.movement import MotorInput, PlayerMotor
from systems.combat_system import character_hitboxes


class Player:
    team = "friendly"
    name = "You"

    def __init__(self, base, collision_world, settings, spawn):
        self.base = base
        self.root = base.render.attach_new_node("player")
        self.motor = PlayerMotor(collision_world, (spawn.x, spawn.y, spawn.z))
        self.camera = FirstPersonCamera(base, self.root, settings)
        self.health = Health(C.PLAYER_MAX_HEALTH, regen_delay=C.PLAYER_REGEN_DELAY, regen_rate=C.PLAYER_REGEN_RATE)
        self.invulnerable = False
        self.hits_taken = 0
        self.spawn = spawn
        self.weapons = None                 # WeaponManager, attached by the game
        self.last_input = MotorInput()
        self.control_enabled = True
        self.mount = None                   # callable -> (x, y, z) while riding a vehicle
        self.teleport(spawn.x, spawn.y, spawn.z, spawn.heading, getattr(spawn, "pitch", 0.0))

    # ------------------------------------------------------------------ combat interface
    @property
    def alive(self):
        return self.health.alive

    @property
    def position(self):
        return self.motor.x, self.motor.y, self.motor.z

    def eye_position(self):
        m = self.motor
        return m.x, m.y, m.z + m.eye_height

    def center(self):
        m = self.motor
        return m.x, m.y, m.z + m.height * 0.55

    def hitboxes(self):
        m = self.motor
        return character_hitboxes(m.x, m.y, m.z, m.height)

    def take_damage(self, amount, source, zone, direction):
        self.hits_taken += 1
        if self.invulnerable or not self.alive:
            return False
        killed = self.health.take_damage(amount)
        src = getattr(source, "position", None)
        if src is not None:
            yaw = math.degrees(math.atan2(-(src[0] - self.motor.x), src[1] - self.motor.y))
        else:
            yaw = math.degrees(math.atan2(direction[0], -direction[1]))
        self.base.messenger.send("player-damaged", [amount, yaw, killed])
        self.camera.add_trauma(min(0.4, amount / 60.0))
        return killed

    # ------------------------------------------------------------------ movement
    def teleport(self, x, y, z, heading=0.0, pitch=0.0):
        self.motor.teleport(x, y, z)
        self.camera.look.yaw = heading
        self.camera.look.pitch = pitch
        self.camera.snap()
        self._sync()

    def respawn(self, placement=None):
        s = placement or self.spawn
        self.health.reset()
        self.teleport(s.x, s.y, s.z, s.heading, 0.0)

    shock = 0.0                   # 0..1 shell shock (set by the game): slows you down
    knock_t = -1.0                # >= 0 while knocked down by a blast
    KNOCK_TIME = 3.2

    def knockdown(self, direction):
        """A shell lands right next to you: thrown off your feet, on the ground, then back up."""
        if self.knock_t >= 0.0 or not self.alive:
            return
        self.knock_t = 0.0
        self._knock_side = 1.0 if direction[0] >= 0 else -1.0
        m = self.motor
        m.vx += direction[0] * 6.5
        m.vy += direction[1] * 6.5
        m.vz = 4.0
        m.grounded = False

    def _update_knock(self, dt):
        t = self.knock_t = self.knock_t + dt
        side = self._knock_side
        if t < 0.45:                                   # thrown: tumble sideways, see the sky
            k = t / 0.45
            knock = (75.0 * side * k, -1.3 * k, 30.0 * k)
        elif t < 2.1:                                  # lying on the ground, dazed
            w = math.sin(t * 2.3) * 3.0
            knock = (80.0 * side + w, -1.35, 18.0 + w)
        elif t < self.KNOCK_TIME:                      # getting back up
            k = 1.0 - (t - 2.1) / (self.KNOCK_TIME - 2.1)
            k = k * k * (3 - 2 * k)
            knock = (80.0 * side * k, -1.35 * k, 18.0 * k)
        else:
            knock = (0.0, 0.0, 0.0)
            self.knock_t = -1.0
        self.camera.knock = knock


    def update(self, dt, inp):
        weapons = self.weapons
        ads = weapons.ads if weapons else 0.0
        fov_mult = weapons.fov_multiplier if weapons else 1.0
        if self.mount is not None:
            # Riding a vehicle: free look and shooting, but the vehicle moves the body.
            if self.control_enabled and self.alive:
                self.camera.handle_mouse(inp.mouse_dx, inp.mouse_dy, scale=fov_mult ** 0.8)
            m = self.motor
            m.x, m.y, m.z = self.mount()
            m.vx = m.vy = m.vz = 0.0
            m.grounded = True
            m.sprinting = False
            m.events.clear()
            motor_input = MotorInput(yaw=self.camera.look.yaw, crouch=False)
            self.last_input = motor_input
            self.health.update(dt)
            self._sync()
            self.camera.update(dt, m, 0.0, fov_multiplier=fov_mult)
            return
        knocked = self.knock_t >= 0.0
        if knocked:
            self._update_knock(dt)
        if self.control_enabled and self.alive and not knocked:
            self.camera.handle_mouse(inp.mouse_dx, inp.mouse_dy, scale=fov_mult ** 0.8)
            firing = inp.is_down("fire")
            motor_input = MotorInput(
                forward=inp.axis("move_forward", "move_backward"),
                right=inp.axis("move_right", "move_left"),
                yaw=self.camera.look.yaw,
                sprint=inp.is_down("sprint") and not firing and not (weapons and weapons.blocks_sprint),
                jump=inp.was_pressed("jump"),
                crouch=inp.is_down("crouch"),
                speed_scale=(weapons.move_multiplier if weapons else 1.0) * (1.0 - 0.6 * self.shock),
            )
        else:
            motor_input = MotorInput(yaw=self.camera.look.yaw, crouch=not self.alive)
        self.last_input = motor_input
        self.motor.update(dt, motor_input)
        self.health.update(dt)
        self._sync()
        self.camera.update(dt, self.motor, motor_input.right, fov_multiplier=fov_mult)
        if ads > 0.5:
            self.camera.offset.set_pos(0, 0, 0)       # no head-bob while aiming
        for event in self.motor.pop_events():
            self.base.messenger.send(f"player-{event}", [self])

    def _sync(self):
        m = self.motor
        self.root.set_pos(m.x, m.y, m.z)
        self.root.set_h(self.camera.look.yaw)
