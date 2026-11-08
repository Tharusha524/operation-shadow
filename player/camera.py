"""First-person camera: mouse look, head bob, landing dip, sprint FOV and smoothing on stairs."""
from __future__ import annotations

import math

from config import constants as C


class LookAngles:
    """Yaw/pitch from mouse movement. Pure maths - unit tested."""

    def __init__(self, yaw=0.0, pitch=0.0):
        self.yaw = yaw
        self.pitch = pitch

    def apply_mouse(self, dx, dy, sensitivity=1.0, invert_y=False):
        k = C.MOUSE_DEGREES_PER_PIXEL * sensitivity
        self.yaw = (self.yaw - dx * k + 180.0) % 360.0 - 180.0
        dp = dy * k
        self.pitch += dp if invert_y else -dp
        self.pitch = max(-C.PITCH_LIMIT, min(C.PITCH_LIMIT, self.pitch))


class FirstPersonCamera:
    def __init__(self, base, player_root, settings):
        self.base = base
        self.settings = settings
        self.look = LookAngles()
        self.eye = player_root.attach_new_node("eye")             # pitch lives here
        self.offset = self.eye.attach_new_node("camera_offset")   # bob / roll / dip live here
        base.camera.reparent_to(self.offset)
        base.camera.set_pos_hpr(0, 0, 0, 0, 0, 0)
        self.base_fov = settings.field_of_view
        self._fov = self.base_fov
        base.camLens.set_fov(self._fov)
        base.camLens.set_near_far(C.NEAR_CLIP, settings.preset["view_distance"])
        self._eye_z = None
        self._bob_weight = 0.0
        self._dip = 0.0
        self._dip_vel = 0.0
        self._roll = 0.0
        self._trauma = 0.0
        self._time = 0.0
        self.knock = (0.0, 0.0, 0.0)          # (roll, height drop, pitch) while knocked down by a blast

    def detach_for_cinematic(self, fov=55.0):
        """Free the camera from the player's head so a cutscene can move it."""
        self.base.camera.wrt_reparent_to(self.base.render)
        self.base.camera.set_r(0)
        self.base.camLens.set_fov(fov)

    def reattach(self):
        self.base.camera.reparent_to(self.offset)
        self.base.camera.set_pos_hpr(0, 0, 0, 0, 0, 0)
        self.base.camLens.set_fov(self._fov)
        self.snap()

    def add_trauma(self, amount):
        """Camera shake: 0 = none, 1 = huge (explosion next to you)."""
        self._trauma = min(1.0, self._trauma + amount)

    def snap(self):
        """Forget smoothing state (after a teleport/respawn)."""
        self._eye_z = None
        self._dip = self._dip_vel = 0.0

    def handle_mouse(self, dx, dy, scale=1.0):
        self.look.apply_mouse(dx, dy, self.settings.mouse_sensitivity * scale, self.settings.invert_mouse_y)

    def update(self, dt, motor, move_right, fov_multiplier=1.0):
        self._time += dt
        cfg = motor.cfg
        # Eye height: follows the body exactly in the air, smoothly on stairs.
        target = motor.z + motor.eye_height
        if self._eye_z is None or not motor.grounded or abs(target - self._eye_z) > 1.0:
            self._eye_z = target
        else:
            self._eye_z += (target - self._eye_z) * min(1.0, dt * C.EYE_SMOOTHING_RATE)

        # Landing dip: a damped spring kicked by the landing speed.
        for event in motor.events:
            if event == "land" and motor.last_landing_speed > 2.5:
                self._dip_vel -= min(motor.last_landing_speed * 0.3, 2.5)
        k = C.LANDING_DIP_STIFFNESS
        c = 2.0 * math.sqrt(k)
        self._dip_vel += (-k * self._dip - c * self._dip_vel) * dt
        self._dip += self._dip_vel * dt

        # Head bob scaled by speed (only on the ground).
        speed_ratio = motor.horizontal_speed / cfg.walk_speed if motor.grounded else 0.0
        self._bob_weight += (min(speed_ratio, 1.6) - self._bob_weight) * min(1.0, dt * 10.0)
        phase = motor.bob_phase
        bob_z = (abs(math.sin(phase)) - 1.0) * C.HEAD_BOB_VERTICAL * self._bob_weight
        bob_x = math.sin(phase) * C.HEAD_BOB_HORIZONTAL * self._bob_weight

        target_roll = -move_right * C.STRAFE_ROLL_DEGREES if motor.grounded else 0.0
        self._roll += (target_roll - self._roll) * min(1.0, dt * 6.0)

        sprint_fov = motor.sprinting and motor.horizontal_speed > cfg.walk_speed * 1.05
        target_fov = (self.base_fov + (C.SPRINT_FOV_BONUS if sprint_fov else 0.0)) * fov_multiplier
        rate = 30.0 if fov_multiplier < 0.999 else C.FOV_LERP_RATE
        self._fov += (target_fov - self._fov) * min(1.0, dt * rate)
        self.base.camLens.set_fov(self._fov)

        self._trauma = max(0.0, self._trauma - dt * 1.4)
        shake = self._trauma * self._trauma
        t = self._time
        sh = shake * 4.0 * math.sin(t * 37.0) * math.cos(t * 11.0)
        sp = shake * 4.0 * math.sin(t * 29.0 + 1.3)
        sr = shake * 3.0 * math.sin(t * 23.0 + 2.1)

        self.eye.set_z(self._eye_z - motor.z)
        kr, kz, kp = self.knock
        self.eye.set_p(self.look.pitch + kp)
        self.offset.set_pos(bob_x, 0.0, bob_z + self._dip + kz)
        self.offset.set_r(self._roll + kr)
        self.base.camera.set_hpr(sh, sp, sr)

    @property
    def fov(self):
        return self._fov
