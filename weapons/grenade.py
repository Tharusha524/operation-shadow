"""Thrown grenade (frag, smoke or flashbang): bounces off the level, goes off after its fuse."""
from __future__ import annotations

import math


class GrenadeProjectile:
    RESTITUTION = 0.42
    FRICTION = 0.7
    GRAVITY = 18.0
    RADIUS = 0.06

    def __init__(self, position, velocity, fuse, owner=None, kind="frag"):
        self.kind = kind              # frag | smoke | flash
        self.pos = list(position)
        self.vel = list(velocity)
        self.fuse = fuse
        self.owner = owner
        self.resting = False
        self.bounced = False          # True on frames where it hit something (for sound)
        self.node = None

    def update(self, dt, world):
        """Advance the grenade. Returns True when the fuse runs out."""
        self.fuse -= dt
        self.bounced = False
        if not self.resting:
            self.vel[2] -= self.GRAVITY * dt
            step = [v * dt for v in self.vel]
            dist = math.sqrt(sum(s * s for s in step))
            if dist > 1e-6:
                direction = [s / dist for s in step]
                hit = world.raycast(self.pos, direction, dist + self.RADIUS)
                if hit is not None:
                    n = hit.normal
                    self.pos = [hit.point[i] + n[i] * self.RADIUS for i in range(3)]
                    vn = sum(self.vel[i] * n[i] for i in range(3))
                    if vn < 0:
                        normal_part = [n[i] * vn for i in range(3)]
                        tangent = [self.vel[i] - normal_part[i] for i in range(3)]
                        self.vel = [tangent[i] * self.FRICTION - normal_part[i] * self.RESTITUTION for i in range(3)]
                        self.bounced = abs(vn) > 1.5
                    speed = math.sqrt(sum(v * v for v in self.vel))
                    if speed < 1.0 and n[2] > 0.6:
                        self.resting = True
                        self.vel = [0.0, 0.0, 0.0]
                else:
                    self.pos = [self.pos[i] + step[i] for i in range(3)]
        return self.fuse <= 0.0
