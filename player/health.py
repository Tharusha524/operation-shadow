"""Health with optional regeneration after a short delay without damage."""
from __future__ import annotations


class Health:
    def __init__(self, maximum=100.0, regen_delay=None, regen_rate=0.0, invulnerable=False):
        self.maximum = float(maximum)
        self.current = float(maximum)
        self.regen_delay = regen_delay        # seconds without damage before regen starts (None = never)
        self.regen_rate = float(regen_rate)   # hp per second
        self.invulnerable = invulnerable      # takes "damage" for feedback but never dies (squad mates)
        self._since_damage = 0.0

    @property
    def alive(self):
        return self.current > 0.0

    @property
    def fraction(self):
        return self.current / self.maximum

    def take_damage(self, amount):
        """Apply damage. Returns True if this hit killed."""
        if not self.alive or amount <= 0:
            return False
        self._since_damage = 0.0
        floor = 1.0 if self.invulnerable else 0.0
        self.current = max(floor, self.current - amount)
        return not self.alive

    def heal(self, amount):
        if self.alive:
            self.current = min(self.maximum, self.current + amount)

    def reset(self):
        self.current = self.maximum
        self._since_damage = 0.0

    def update(self, dt):
        self._since_damage += dt
        if self.alive and self.regen_delay is not None:
            regen_time = min(dt, self._since_damage - self.regen_delay)   # only the part after the delay
            if regen_time > 0:
                self.heal(self.regen_rate * regen_time)

    @property
    def time_since_damage(self):
        return self._since_damage
