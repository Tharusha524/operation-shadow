"""Player movement physics (walk, sprint, crouch, jump, gravity, collisions).

This module has no Panda3D dependency: it only needs a CollisionWorld. That keeps
the movement rules unit-testable (see tests/test_movement.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from config import constants as C


@dataclass
class MotorConfig:
    radius: float = C.PLAYER_RADIUS
    stand_height: float = C.PLAYER_STAND_HEIGHT
    crouch_height: float = C.PLAYER_CROUCH_HEIGHT
    eye_offset: float = C.PLAYER_EYE_OFFSET
    step_height: float = C.STEP_HEIGHT
    air_step_height: float = C.AIR_STEP_HEIGHT
    ground_snap: float = C.GROUND_SNAP_DISTANCE
    support_factor: float = C.GROUND_SUPPORT_FACTOR
    walk_speed: float = C.WALK_SPEED
    sprint_speed: float = C.SPRINT_SPEED
    crouch_speed: float = C.CROUCH_SPEED
    backward_factor: float = C.BACKWARD_SPEED_FACTOR
    ground_accel: float = C.GROUND_ACCELERATION
    ground_decel: float = C.GROUND_DECELERATION
    air_accel: float = C.AIR_ACCELERATION
    jump_speed: float = C.JUMP_SPEED
    gravity: float = C.GRAVITY
    max_fall_speed: float = C.MAX_FALL_SPEED
    coyote_time: float = C.COYOTE_TIME
    jump_buffer_time: float = C.JUMP_BUFFER_TIME
    crouch_rate: float = C.CROUCH_TRANSITION_SPEED
    sprint_min_forward: float = C.SPRINT_MIN_FORWARD
    walk_stride: float = C.WALK_STRIDE
    sprint_stride: float = C.SPRINT_STRIDE
    crouch_stride: float = C.CROUCH_STRIDE


@dataclass
class MotorInput:
    forward: float = 0.0        # -1 (back) .. 1 (forward)
    right: float = 0.0          # -1 (left) .. 1 (right)
    yaw: float = 0.0            # facing direction in degrees (Panda3D heading)
    sprint: bool = False
    jump: bool = False          # True only on the frame the jump key went down
    crouch: bool = False
    speed_scale: float = 1.0    # e.g. slower while aiming down sights


class PlayerMotor:
    """Moves an upright cylinder through a CollisionWorld."""

    MAX_SUBSTEP_DISTANCE = 0.15

    def __init__(self, world, position=(0.0, 0.0, 0.0), config: MotorConfig | None = None):
        self.cfg = config or MotorConfig()
        self.world = world
        self.x, self.y, self.z = (float(v) for v in position)
        self.vx = self.vy = self.vz = 0.0
        self.height = self.cfg.stand_height
        self.grounded = False
        self.crouching = False
        self.sprinting = False
        self.bob_phase = 0.0            # advances by pi every footstep (used for head bob)
        self.last_landing_speed = 0.0
        self.events = []                # "jump", "land", "footstep" - read with pop_events()
        self._coyote = 0.0
        self._jump_buffer = 0.0

    # ------------------------------------------------------------------ properties
    @property
    def position(self):
        return self.x, self.y, self.z

    @property
    def eye_height(self):
        return self.height - self.cfg.eye_offset

    @property
    def horizontal_speed(self):
        return math.hypot(self.vx, self.vy)

    def teleport(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vx = self.vy = self.vz = 0.0
        self.grounded = False
        self._coyote = self._jump_buffer = 0.0
        self.events.clear()

    def pop_events(self):
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------ update
    def update(self, dt, inp: MotorInput):
        if dt <= 0.0:
            return
        cfg = self.cfg
        self._update_crouch(dt, inp.crouch)

        # Desired horizontal direction in world space.
        f = max(-1.0, min(1.0, inp.forward))
        r = max(-1.0, min(1.0, inp.right))
        mag = math.hypot(f, r)
        if mag > 1.0:
            f, r = f / mag, r / mag
        h = math.radians(inp.yaw)
        sin_h, cos_h = math.sin(h), math.cos(h)
        wish_x = -sin_h * f + cos_h * r
        wish_y = cos_h * f + sin_h * r

        # Sprint is decided on the ground and kept through a jump.
        wants_sprint = inp.sprint and f > cfg.sprint_min_forward and not self.crouching
        if self.grounded or not wants_sprint:
            self.sprinting = wants_sprint

        if self.crouching:
            speed = cfg.crouch_speed
        elif self.sprinting:
            speed = cfg.sprint_speed
        else:
            speed = cfg.walk_speed
        if f < 0.0:
            speed *= cfg.backward_factor
        speed *= inp.speed_scale

        target_x, target_y = wish_x * speed, wish_y * speed
        has_input = (wish_x * wish_x + wish_y * wish_y) > 1e-6
        if self.grounded:
            accel = cfg.ground_accel if has_input else cfg.ground_decel
        else:
            accel = cfg.air_accel
        self.vx, self.vy = _approach_2d(self.vx, self.vy, target_x, target_y, accel * dt)

        # Jumping (with coyote time and input buffering so it feels responsive).
        if inp.jump:
            self._jump_buffer = cfg.jump_buffer_time
        if self.grounded:
            self._coyote = cfg.coyote_time
        if self._jump_buffer > 0.0 and self._coyote > 0.0 and not self.crouching:
            self.vz = cfg.jump_speed
            self.grounded = False
            self._coyote = 0.0
            self._jump_buffer = 0.0
            self.events.append("jump")

        # Integrate in small sub-steps so fast movement never skips through geometry.
        travel = max(math.hypot(self.vx, self.vy), abs(self.vz)) * dt
        steps = max(1, math.ceil(travel / self.MAX_SUBSTEP_DISTANCE))
        sub_dt = dt / steps
        for _ in range(steps):
            self._substep(sub_dt)

        if not self.grounded:
            self._coyote = max(0.0, self._coyote - dt)
        self._jump_buffer = max(0.0, self._jump_buffer - dt)

        self._update_footsteps(dt)

    def _substep(self, h):
        cfg = self.cfg
        world = self.world
        old_feet = self.z
        step = cfg.step_height if self.grounded else cfg.air_step_height

        # Horizontal move + slide along walls.
        x = self.x + self.vx * h
        y = self.y + self.vy * h
        x, y, normals = world.resolve_horizontal(x, y, cfg.radius, old_feet, old_feet + self.height, step)
        for nx, ny in normals:
            dot = self.vx * nx + self.vy * ny
            if dot < 0.0:
                self.vx -= dot * nx
                self.vy -= dot * ny
        self.x, self.y = x, y

        # Vertical move: gravity, landing, stepping up, snapping down stairs, ceilings.
        old_vz = self.vz
        self.vz = max(self.vz - cfg.gravity * h, -cfg.max_fall_speed)
        new_z = self.z + 0.5 * (old_vz + self.vz) * h   # exact for constant gravity
        ground = world.ground_height(x, y, cfg.radius * cfg.support_factor, old_feet + step)

        if new_z <= ground:
            self.z = ground
            if self.vz <= 0.0:
                if not self.grounded:
                    self.last_landing_speed = -self.vz
                    self.events.append("land")
                self.vz = 0.0
                self.grounded = True
        elif self.grounded and self.vz <= 0.0 and new_z - ground <= cfg.ground_snap:
            self.z = ground
            self.vz = 0.0
        else:
            self.z = new_z
            self.grounded = False
            if self.vz > 0.0:
                ceiling = world.ceiling_height(x, y, cfg.radius, old_feet + self.height - 0.01)
                if self.z + self.height > ceiling:
                    self.z = ceiling - self.height
                    self.vz = 0.0

    def _update_crouch(self, dt, wants_crouch):
        cfg = self.cfg
        target = cfg.crouch_height if wants_crouch else cfg.stand_height
        if target > self.height:
            # Only stand up if there is room above the head.
            if not self.world.is_free(self.x, self.y, cfg.radius * 0.95,
                                      self.z + self.height, self.z + cfg.stand_height):
                target = self.height
        delta = target - self.height
        max_change = cfg.crouch_rate * dt
        if abs(delta) <= max_change:
            self.height = target
        else:
            self.height += math.copysign(max_change, delta)
        self.crouching = wants_crouch or self.height < cfg.stand_height - 0.05

    def _update_footsteps(self, dt):
        if not self.grounded:
            return
        speed = self.horizontal_speed
        if speed < 0.3:
            return
        cfg = self.cfg
        if self.crouching:
            stride = cfg.crouch_stride
        elif self.sprinting:
            stride = cfg.sprint_stride
        else:
            stride = cfg.walk_stride
        before = int(self.bob_phase // math.pi)
        self.bob_phase += math.pi * speed * dt / stride
        if int(self.bob_phase // math.pi) != before:
            self.events.append("footstep")


def _approach_2d(x, y, tx, ty, max_delta):
    dx, dy = tx - x, ty - y
    dist = math.hypot(dx, dy)
    if dist <= max_delta or dist < 1e-9:
        return tx, ty
    k = max_delta / dist
    return x + dx * k, y + dy * k
