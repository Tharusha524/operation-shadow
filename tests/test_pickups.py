"""Ammo packs dropped by fallen enemies."""
import random

import pytest

from core.pickups import DROP_CHANCE, LIFETIME, MAX_ACTIVE, Pickups
from weapons.weapon_base import Weapon, load_weapon_data
from core.paths import DATA_DIR


def always():
    rng = random.Random(1)
    rng.random = lambda: 0.0
    return rng


def test_drop_chance_is_roughly_right():
    p = Pickups(random.Random(3))
    drops = sum(1 for _ in range(1000) if (p.drop((0, 0, 0)) is not None))
    assert drops == pytest.approx(1000 * DROP_CHANCE, abs=60)


def test_walking_over_a_pack_takes_it():
    p = Pickups(always())
    p.drop((5, 0, 0))
    assert p.update(0.1, (0, 0, 0), True) is None and len(p.packs) == 1
    assert p.update(0.1, (5.5, 0, 0), True) is not None and not p.packs


def test_pack_stays_if_you_are_full_of_ammo():
    p = Pickups(always())
    p.drop((0, 0, 0))
    assert p.update(0.1, (0, 0, 0), False) is None and len(p.packs) == 1


def test_pack_on_another_floor_is_not_taken():
    p = Pickups(always())
    p.drop((0, 0, 0))
    assert p.update(0.1, (0, 0, 4.0), True) is None and len(p.packs) == 1


def test_packs_disappear_after_a_while_and_are_limited():
    p = Pickups(always())
    p.drop((0, 0, 0))
    p.update(LIFETIME + 1, None, True)
    assert not p.packs
    for i in range(MAX_ACTIVE + 5):
        p.drop((i, 0, 0))
    assert len(p.packs) == MAX_ACTIVE


def test_weapon_reserve_never_goes_over_the_maximum():
    stats, _ = load_weapon_data(DATA_DIR / "weapons.json")
    w = Weapon(stats["kr7"])
    w.reserve = w.stats.max_reserve - 5
    assert w.add_ammo(30) == 5 and w.reserve == w.stats.max_reserve
