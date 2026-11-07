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
        if self.control_enabled and self.alive:
            self.camera.handle_mouse(inp.mouse_dx, inp.mouse_dy, scale=fov_mult ** 0.8)
            firing = inp.is_down("fire")
            motor_input = MotorInput(
                forward=inp.axis("move_forward", "move_backward"),
                right=inp.axis("move_right", "move_left"),
                yaw=self.camera.look.yaw,
                sprint=inp.is_down("sprint") and not firing and not (weapons and weapons.blocks_sprint),
                jump=inp.was_pressed("jump"),
                crouch=inp.is_down("crouch"),
                speed_scale=weapons.move_multiplier if weapons else 1.0,
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
