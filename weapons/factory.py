"""Create the right Weapon subclass for a WeaponStats entry."""
from weapons.assault_rifle import AssaultRifle
from weapons.pistol import Pistol
from weapons.shotgun import Shotgun
from weapons.sniper import SniperRifle
from weapons.weapon_base import Weapon

CLASSES = {
    "assault_rifle": AssaultRifle,
    "pistol": Pistol,
    "sniper": SniperRifle,
    "shotgun": Shotgun,
}


def create_weapon(stats, rng=None, infinite_reserve=False) -> Weapon:
    return CLASSES.get(stats.weapon_class, Weapon)(stats, rng, infinite_reserve)
