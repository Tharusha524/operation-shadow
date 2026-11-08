"""Flying debris: chunks of concrete, metal, wood or earth thrown by explosions.

Each chunk is a small solid piece that flies, tumbles, bounces once and then lies on the ground
for a while before sinking away. Cheap: a few shared meshes instanced with a colour per chunk.
"""
from __future__ import annotations

import math
import random

from panda3d.core import NodePath

from environments.geometry import MeshBuilder

MAX_CHUNKS = 180
LIFE = 28.0
GRAVITY = 16.0

COLORS = {
    "concrete": (0.55, 0.53, 0.5), "brick": (0.5, 0.33, 0.25), "metal": (0.3, 0.32, 0.27),
    "olive": (0.3, 0.33, 0.2), "wood": (0.42, 0.3, 0.18), "earth": (0.32, 0.26, 0.19), "charred": (0.12, 0.11, 0.1),
}


class _Chunk:
    __slots__ = ("np", "vel", "spin", "age", "resting", "bounced")


class Debris:
    def __init__(self, game):
        self.game = game
        self.root = game.render.attach_new_node("debris")
        self.chunks = []
        self._shapes = None
        self.rng = random.Random(7)

    def _templates(self):
        if self._shapes is None:
            mats = self.game.environment.materials
            self._shapes = []
            for sx, sy, sz in ((1.0, 1.0, 1.0), (1.6, 0.9, 0.35), (2.2, 0.4, 0.4), (1.2, 1.2, 0.6)):
                mb = MeshBuilder(mats.uv_scales())
                mb.box("paint", 0, 0, -sz / 2, sx, sy, sz, (1, 1, 1), bottom=True)
                self._shapes.append(mb.build(NodePath("chunk"), mats, name="chunk"))
        return self._shapes

    def burst(self, pos, count=12, kind="concrete", size=0.35, speed=9.0, up=7.0):
        """Throw `count` chunks outwards and upwards from pos."""
        shapes = self._templates()
        base = COLORS.get(kind, COLORS["concrete"])
        u = self.rng.uniform
        for _ in range(count):
            if len(self.chunks) >= MAX_CHUNKS:
                old = self.chunks.pop(0)
                old.np.remove_node()
            c = _Chunk()
            c.np = shapes[self.rng.randrange(len(shapes))].copy_to(self.root)
            s = size * u(0.5, 1.4)
            c.np.set_scale(s)
            k = u(0.75, 1.15)
            c.np.set_color_scale(base[0] * k, base[1] * k, base[2] * k, 1)
            c.np.set_pos(pos[0] + u(-0.6, 0.6), pos[1] + u(-0.6, 0.6), pos[2] + u(0.2, 1.0))
            c.np.set_hpr(u(0, 360), u(0, 360), u(0, 360))
            a = u(0, math.tau)
            v = u(0.4, 1.0) * speed
            c.vel = [math.cos(a) * v, math.sin(a) * v, u(0.5, 1.0) * up + 2.0]
            c.spin = (u(-400, 400), u(-400, 400), u(-400, 400))
            c.age = 0.0
            c.resting = False
            c.bounced = False
            self.chunks.append(c)

    def update(self, dt):
        world = self.game.collision_world
        keep = []
        for c in self.chunks:
            c.age += dt
            if c.age > LIFE:
                c.np.remove_node()
                continue
            if c.resting:
                if c.age > LIFE - 3.0:                            # sink into the ground before vanishing
                    c.np.set_z(c.np.get_z() - 0.15 * dt)
                keep.append(c)
                continue
            p = c.np.get_pos()
            c.vel[2] -= GRAVITY * dt
            nx, ny, nz = p.x + c.vel[0] * dt, p.y + c.vel[1] * dt, p.z + c.vel[2] * dt
            ground = world.ground_height(nx, ny, 0.05, max(p.z, nz) + 0.2)
            if nz <= ground:
                nz = ground + 0.05
                if not c.bounced and c.vel[2] < -4.0:
                    c.bounced = True
                    c.vel = [c.vel[0] * 0.4, c.vel[1] * 0.4, -c.vel[2] * 0.3]
                else:
                    c.resting = True
            c.np.set_pos(nx, ny, nz)
            if not c.resting:
                h, pp, r = c.np.get_hpr()
                c.np.set_hpr(h + c.spin[0] * dt, pp + c.spin[1] * dt, r + c.spin[2] * dt)
            keep.append(c)
        self.chunks = keep

    def clear(self):
        for c in self.chunks:
            c.np.remove_node()
        self.chunks = []
