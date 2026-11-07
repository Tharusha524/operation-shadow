"""Silent takedowns (V), night-vision goggles (N) and collectible intel."""
from __future__ import annotations

import math

from enemies.soldier import angle_diff, heading_to

TAKEDOWN_RANGE = 1.9
TAKEDOWN_ANGLE = 55.0          # the enemy must be roughly in front of the player
NVG_GRADING = {"exposure": 5.0, "saturation": 0.0, "contrast": 1.12, "tint": [0.42, 1.25, 0.5], "grain": 0.1,
               "vignette": 1.1, "lift": 0.05, "bloom": 1.0, "bloom_threshold": 0.6, "shadow_tint": [1, 1, 1]}
INTEL_RADIUS = 1.8
INTEL_HOLD = 0.6


def takedown_target(player_pos, player_yaw, soldiers):
    """The enemy the player can take down right now (closest in front, within reach), or None."""
    px, py, pz = player_pos
    best, best_d = None, None
    for s in soldiers:
        if s.team != "enemy" or not s.alive:
            continue
        sx, sy, sz = s.position
        d = math.hypot(sx - px, sy - py)
        if d > TAKEDOWN_RANGE or abs(sz - pz) > 1.0:
            continue
        if abs(angle_diff(heading_to(sx - px, sy - py), player_yaw)) > TAKEDOWN_ANGLE:
            continue
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best


def is_unaware(soldier):
    """Takedowns are silent only on enemies who are not fighting."""
    from enemies.enemy_ai import COMBAT_STATES
    return soldier.ai.state not in COMBAT_STATES


def perform_takedown(player, soldier):
    """Kill the soldier instantly. Silent if they were unaware. Returns True if it was silent."""
    silent = is_unaware(soldier)
    soldier.silent_death = silent
    px, py, _ = player.position
    sx, sy, _ = soldier.position
    d = math.hypot(sx - px, sy - py) or 1.0
    soldier.take_damage(soldier.health.current + 1000.0, player, "body", ((sx - px) / d, (sy - py) / d, 0.0))
    return silent


class Intel:
    def __init__(self, iid, pos, name, node=None):
        self.id = iid
        self.pos = tuple(pos)
        self.name = name
        self.node = node
        self.collected = False
        self.held = 0.0


class IntelTracker:
    """Optional collectibles placed by the mission. Hold E next to one to pick it up."""

    def __init__(self):
        self.items = []

    def setup(self, specs, make_node=None):
        self.clear()
        for spec in specs:
            node = make_node(spec) if make_node else None
            self.items.append(Intel(spec["id"], spec["pos"], spec.get("name", "Intel"), node))

    def clear(self):
        for it in self.items:
            if it.node is not None:
                it.node.remove_node()
        self.items = []

    @property
    def total(self):
        return len(self.items)

    @property
    def found(self):
        return sum(1 for it in self.items if it.collected)

    def collected_ids(self):
        return [it.id for it in self.items if it.collected]

    def restore(self, ids):
        """Back to a checkpoint: only intel picked up before it stays collected."""
        for it in self.items:
            it.collected = it.id in ids
            it.held = 0.0
            if it.node is not None:
                it.node.show() if not it.collected else it.node.hide()

    def nearby(self, pos):
        for it in self.items:
            if not it.collected and math.dist(pos, it.pos) <= INTEL_RADIUS:
                return it
        return None

    def update(self, dt, eye_pos, holding):
        """Returns (item in reach or None, progress 0..1, item just collected or None)."""
        it = self.nearby(eye_pos)
        for other in self.items:
            if other is not it:
                other.held = 0.0
        if it is None:
            return None, 0.0, None
        it.held = it.held + dt if holding else 0.0
        if it.held >= INTEL_HOLD:
            it.collected = True
            if it.node is not None:
                it.node.hide()
            return None, 0.0, it
        return it, it.held / INTEL_HOLD, None
