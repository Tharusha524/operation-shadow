"""Ammo packs dropped by fallen enemies. Walk over one to take it."""
from __future__ import annotations

import math

DROP_CHANCE = 0.7
PICKUP_RADIUS = 1.5
LIFETIME = 90.0
MAX_ACTIVE = 14
AMMO_FRACTION = 0.7            # one pack adds this share of a magazine to every weapon you carry


class AmmoPack:
    def __init__(self, pos, node=None):
        self.pos = tuple(pos)
        self.node = node
        self.age = 0.0


class Pickups:
    def __init__(self, rng, make_node=None):
        self.rng = rng
        self.make_node = make_node
        self.packs = []

    def drop(self, pos):
        """Maybe leave a pack where an enemy fell. Returns the pack or None."""
        if self.rng.random() > DROP_CHANCE:
            return None
        while len(self.packs) >= MAX_ACTIVE:
            self._remove(self.packs[0])
        pack = AmmoPack(pos, self.make_node(pos) if self.make_node else None)
        self.packs.append(pack)
        return pack

    def _remove(self, pack):
        if pack.node is not None:
            pack.node.remove_node()
        self.packs.remove(pack)

    def clear(self):
        for pack in list(self.packs):
            self._remove(pack)

    def update(self, dt, player_pos, needs_ammo):
        """Age the packs. Returns the pack taken this frame, or None."""
        taken = None
        for pack in list(self.packs):
            pack.age += dt
            if pack.age >= LIFETIME:
                self._remove(pack)
            elif taken is None and needs_ammo and player_pos is not None and \
                    math.hypot(pack.pos[0] - player_pos[0], pack.pos[1] - player_pos[1]) <= PICKUP_RADIUS and \
                    abs(pack.pos[2] - player_pos[2]) < 2.0:
                taken = pack
                self._remove(pack)
        return taken
