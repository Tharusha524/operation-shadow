"""Fleeing civilians: animated townspeople who run along a route (e.g. to the evacuation trucks).

They have no AI and nobody aims at them, but explosions kill them: they are thrown like soldiers and
stay on the ground. Reaching the end of the route they either board (vanish into a truck) or cower.
"""
from __future__ import annotations

import math
import random

from environments.sets import Puppet

GRAVITY = 18.0


class Civilian:
    def __init__(self, game, group, spec):
        self.game = game
        self.group = group
        model = spec.get("model", "man")
        path = [list(p) for p in spec["path"]]
        self.puppet = Puppet(game.render, {"model": model, "pos": path[0][:2], "path": path,
                                           "speed": spec.get("speed", 4.2), "move": spec.get("move", "run"),
                                           "anim": "terrified", "start": spec.get("start", 0.0),
                                           "then": {"anim": spec.get("then", "terrified")}})
        self.board = bool(spec.get("board", False))
        self.t = 0.0
        self.alive = True
        self.gone = False
        self.fling = None
        self.tilt = 0.0
        self.back = True

    @property
    def position(self):
        p = self.puppet.root.get_pos()
        return p.x, p.y, p.z

    def blast(self, origin, radius):
        x, y, z = self.position
        d = math.dist((x, y, z + 1.0), origin)
        if d > radius or not self.alive:
            return False
        self.alive = False
        a = self.puppet.actor
        a.stop()
        a.play("death")
        dx, dy = x - origin[0], y - origin[1]
        n = math.hypot(dx, dy) or 1.0
        push = 6.0 + 7.0 * (1.0 - d / radius)
        self.fling = [dx / n * push, dy / n * push, 5.0 + 6.0 * (1.0 - d / radius)]
        h = math.radians(self.puppet.root.get_h())
        self.back = (dx * -math.sin(h) + dy * math.cos(h)) < 0
        return True

    def shot(self):
        """Hit by gunfire: falls where he stands."""
        if not self.alive:
            return
        self.alive = False
        self.puppet.walking = False
        self.puppet.actor.stop()
        self.puppet.actor.play("death")

    def update(self, dt):
        if self.gone:
            return
        root = self.puppet.root
        if self.alive:
            self.t += dt
            self.puppet.update(self.t, dt)
            ground = self.game.collision_world.ground_height(root.get_x(), root.get_y(), 0.1, root.get_z() + 0.5)
            root.set_z(ground)
            if self.board and not self.puppet.walking and self.t > self.puppet.start + 0.5:
                self.gone = True                       # climbed into the truck
                root.hide()
            return
        if self.fling is not None:
            vx, vy, vz = self.fling
            vz -= GRAVITY * dt
            x, y, z = root.get_x() + vx * dt, root.get_y() + vy * dt, root.get_z() + vz * dt
            ground = self.game.collision_world.ground_height(x, y, 0.1, z + 0.4)
            airborne = z > ground
            if not airborne:
                z = ground
                vx, vy, vz = vx * 0.3, vy * 0.3, 0.0
                if math.hypot(vx, vy) < 0.3:
                    self.fling = None
            root.set_pos(x, y, z)
            if self.fling is not None:
                self.fling = [vx, vy, vz]
            target = (80.0 if self.back else -80.0) if airborne else 0.0
            self.tilt += (target - self.tilt) * min(1.0, dt * (5.0 if airborne else 9.0))
            root.set_p(self.tilt)
        elif abs(self.tilt) > 0.5:
            self.tilt *= max(0.0, 1.0 - dt * 9.0)
            root.set_p(self.tilt)

    def remove(self):
        self.puppet.remove()


class Civilians:
    def __init__(self, game):
        self.game = game
        self.people = []
        self.rng = random.Random(11)
        self.pending = []                              # [seconds, group, spec]

    def spawn(self, group, specs):
        for spec in specs:
            delay = float(spec.get("delay", 0.0))
            if delay > 0.0:
                self.pending.append([delay, group, spec])
            else:
                self.people.append(Civilian(self.game, group, spec))

    def alive(self, group=None):
        return [c for c in self.people if c.alive and not c.gone and (group is None or c.group == group)]

    def dead_count(self):
        return sum(1 for c in self.people if not c.alive)

    def blast(self, origin, radius):
        for c in self.people:
            if not c.gone:
                c.blast(origin, radius)

    def update(self, dt):
        keep = []
        for p in self.pending:
            p[0] -= dt
            if p[0] <= 0.0:
                self.people.append(Civilian(self.game, p[1], p[2]))
            else:
                keep.append(p)
        self.pending = keep
        for c in self.people:
            c.update(dt)

    def clear(self):
        for c in self.people:
            c.remove()
        self.people = []
        self.pending = []
