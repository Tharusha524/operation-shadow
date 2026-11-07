"""Bolt-action sniper rifle: huge damage, needs a bolt cycle between shots, very inaccurate from the hip."""
from weapons.weapon_base import Weapon


class SniperRifle(Weapon):
    @property
    def has_scope(self):
        return True
