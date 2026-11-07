"""Pump shotgun: fires several pellets, reloads one shell at a time and can interrupt the reload to fire."""
from weapons.weapon_base import Weapon


class Shotgun(Weapon):
    @property
    def interruptible_reload(self):
        return True

    def start_reload(self):
        if self.reloading or self.mag >= self.stats.magazine or self.reserve <= 0:
            return False
        self.reloading = True
        self.reload_timer = self.stats.reload_start_delay + self.stats.reload_time
        self.events.append("reload_start")
        return True

    @property
    def reload_progress(self):
        return self.mag / self.stats.magazine if self.reloading else 0.0

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.bloom = max(0.0, self.bloom - self.stats.spread_recovery * dt)
        if not self.reloading:
            return
        self.reload_timer -= dt
        while self.reloading and self.reload_timer <= 0.0:
            self.mag += 1
            if not self.infinite_reserve:
                self.reserve -= 1
            self.events.append("shell")
            if self.mag >= self.stats.magazine or self.reserve <= 0:
                self.reloading = False
                self.events.append("reload_end")
            else:
                self.reload_timer += self.stats.reload_time
