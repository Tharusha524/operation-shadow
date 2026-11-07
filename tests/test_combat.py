import math
import random

import pytest

from core.paths import DATA_DIR
from player.health import Health
from systems.collision_system import BoxCollider, CollisionWorld, CylinderCollider
from systems.combat_system import CombatSystem, character_hitboxes
from weapons.factory import create_weapon
from weapons.weapon_base import load_weapon_data

WEAPONS, GRENADE = load_weapon_data(DATA_DIR / "weapons.json")


# ---------------------------------------------------------------- ray casting
def test_raycast_hits_box_front_face_with_normal():
    w = CollisionWorld()
    w.add(BoxCollider(0, 10, 0, 3, hx=2, hy=0.5))
    hit = w.raycast((0, 0, 1), (0, 1, 0), 100)
    assert hit.t == pytest.approx(9.5)
    assert hit.normal == pytest.approx((0, -1, 0), abs=1e-9)


def test_raycast_rotated_box():
    w = CollisionWorld()
    w.add(BoxCollider(10, 0, 0, 3, hx=0.5, hy=3, yaw=45))
    hit = w.raycast((0, 0, 1), (1, 0, 0), 100)
    assert hit is not None and 8.5 < hit.t < 10
    assert hit.normal[0] < 0


def test_raycast_cylinder_and_floor():
    w = CollisionWorld()
    w.add(CylinderCollider(0, 20, 0, 5, radius=1))
    hit = w.raycast((0, 0, 1), (0, 1, 0), 100)
    assert hit.t == pytest.approx(19.0)
    down = w.raycast((5, 5, 2), (0, 0, -1), 100)
    assert down.t == pytest.approx(2.0) and down.normal == (0, 0, 1)


def test_raycast_long_distance_across_many_cells_and_miss():
    w = CollisionWorld(cell_size=4)
    w.add(BoxCollider(-150, 150, 0, 3, hx=1, hy=1))
    d = (-1 / math.sqrt(2), 1 / math.sqrt(2), 0)
    hit = w.raycast((0, 0, 1), d, 400)
    assert hit is not None and hit.t == pytest.approx(math.hypot(149, 149), rel=0.02)
    assert w.raycast((0, 0, 1), (1, 0, 0), 400) is None


def test_line_of_sight_and_remove_tag():
    w = CollisionWorld()
    w.add(BoxCollider(0, 5, 0, 3, hx=3, hy=0.2, tag="breach"))
    assert not w.line_of_sight((0, 0, 1), (0, 10, 1))
    assert w.line_of_sight((0, 0, 4), (0, 10, 4))      # over the wall
    assert w.remove_tag("breach") == 1
    assert w.line_of_sight((0, 0, 1), (0, 10, 1))


# ---------------------------------------------------------------- combat
class Dummy:
    def __init__(self, x, y, team="enemy", hp=100):
        self.x, self.y, self.z, self.height = x, y, 0.0, 1.8
        self.team = team
        self.health = Health(hp)
        self.last_zone = None

    @property
    def alive(self):
        return self.health.alive

    def hitboxes(self):
        return character_hitboxes(self.x, self.y, self.z, self.height)

    def center(self):
        return self.x, self.y, 1.0

    def take_damage(self, amount, source, zone, direction):
        self.last_zone = zone
        return self.health.take_damage(amount)


def make_combat():
    world = CollisionWorld()
    return world, CombatSystem(world)


def test_headshot_does_more_damage_than_body_and_legs():
    _, combat = make_combat()
    rifle = WEAPONS["kr7"]
    results = {}
    for zone, z in (("head", 1.65), ("body", 1.2), ("legs", 0.4)):
        d = Dummy(0, 10)
        combat.characters = [d]
        r = combat.fire(None, (0, 0, z), (0, 1, 0), rifle)
        assert r.zone == zone
        results[zone] = r.damage
    assert results["head"] == pytest.approx(rifle.damage * rifle.headshot_multiplier)
    assert results["body"] == pytest.approx(rifle.damage)
    assert results["legs"] == pytest.approx(rifle.damage * 0.8)


def test_wall_blocks_bullet():
    world, combat = make_combat()
    world.add(BoxCollider(0, 5, 0, 3, hx=3, hy=0.2))
    d = Dummy(0, 10)
    combat.characters = [d]
    r = combat.fire(None, (0, 0, 1.2), (0, 1, 0), WEAPONS["kr7"])
    assert r.target is None and d.health.current == 100


def test_no_friendly_fire():
    _, combat = make_combat()
    shooter = Dummy(0, 0, team="friendly")
    ally = Dummy(0, 10, team="friendly")
    combat.characters = [shooter, ally]
    r = combat.fire(shooter, (0, 0.5, 1.2), (0, 1, 0), WEAPONS["kr7"])
    assert r.target is ally and r.damage == 0 and ally.health.current == 100


def test_damage_falloff():
    rifle = WEAPONS["kr7"]
    assert CombatSystem.falloff(rifle, 10) == 1.0
    assert CombatSystem.falloff(rifle, 500) == rifle.min_damage_multiplier
    mid = CombatSystem.falloff(rifle, (rifle.falloff_start + rifle.falloff_end) / 2)
    assert rifle.min_damage_multiplier < mid < 1.0


def test_explosion_damages_by_distance_and_respects_walls():
    world, combat = make_combat()
    near, far, hidden = Dummy(1, 0), Dummy(5, 0), Dummy(0, -4)
    world.add(BoxCollider(0, -2, 0, 3, hx=2, hy=0.2))
    combat.characters = [near, far, hidden]
    combat.explode((0, 0, 0.2), 7.0, 180)
    assert near.health.current < far.health.current < 100
    assert hidden.health.current == 100


# ---------------------------------------------------------------- health
def test_health_regen_and_death():
    h = Health(100, regen_delay=4.0, regen_rate=25)
    h.take_damage(60)
    h.update(3.0)
    assert h.current == 40
    h.update(1.0)
    h.update(1.0)
    assert h.current == pytest.approx(65)
    assert h.take_damage(500) is True and not h.alive
    h.update(10)
    assert h.current == 0


def test_invulnerable_never_dies():
    h = Health(100, invulnerable=True)
    assert h.take_damage(1000) is False and h.alive


# ---------------------------------------------------------------- weapons
def test_weapon_data_has_four_player_weapons_with_different_stats():
    player = [WEAPONS[k] for k in ("kr7", "p12", "lr50", "sg8")]
    for attr in ("damage", "rpm", "magazine", "reload_time", "recoil_pitch", "spread_hip", "sound", "model"):
        assert len({getattr(w, attr) for w in player}) == 4, attr


def fire_n(weapon, n):
    fired = 0
    for _ in range(n):
        weapon.cooldown = 0
        fired += weapon.try_fire()
    return fired


def test_magazine_and_reload_ammo_math():
    w = create_weapon(WEAPONS["kr7"])
    assert (w.mag, w.reserve) == (30, 120)
    assert fire_n(w, 10) == 10 and w.mag == 20
    assert w.start_reload()
    for _ in range(300):
        w.update(0.01)
    assert (w.mag, w.reserve) == (30, 110)


def test_cannot_fire_when_empty_and_auto_reloads():
    w = create_weapon(WEAPONS["p12"])
    fire_n(w, 12)
    assert w.mag == 0
    w.cooldown = 0
    assert w.try_fire() is False
    assert "dry" in w.pop_events() and w.reloading
    for _ in range(300):
        w.update(0.01)
    assert w.mag == 12 and w.reserve == 36


def test_reload_with_little_reserve_and_none():
    w = create_weapon(WEAPONS["kr7"])
    w.mag, w.reserve = 0, 7
    w.start_reload()
    for _ in range(400):
        w.update(0.01)
    assert (w.mag, w.reserve) == (7, 0)
    w.mag = 3
    assert w.start_reload() is False          # nothing left to load


def test_full_magazine_does_not_reload():
    assert create_weapon(WEAPONS["kr7"]).start_reload() is False


def test_fire_rate_limits_shots():
    w = create_weapon(WEAPONS["kr7"])
    shots = 0
    for _ in range(100):                       # one second at 100 fps
        shots += w.try_fire()
        w.update(0.01)
    assert abs(shots - 12) <= 1                # 720 rpm = 12 per second


def test_semi_auto_needs_trigger_release():
    w = create_weapon(WEAPONS["p12"])
    assert w.wants_fire(trigger_pressed=False, trigger_held=True) is False
    auto = create_weapon(WEAPONS["kr7"])
    assert auto.wants_fire(trigger_pressed=False, trigger_held=True) is True


def test_shotgun_loads_shells_one_by_one_and_can_interrupt():
    w = create_weapon(WEAPONS["sg8"])
    fire_n(w, 4)
    assert w.mag == 2
    w.start_reload()
    while w.mag < 4:
        w.update(0.01)
    assert w.reloading
    w.cooldown = 0
    assert w.try_fire() is True and not w.reloading and w.mag == 3
    assert len(w.pellet_offsets(5.0)) == 8


def test_pellets_stay_inside_spread_cone():
    w = create_weapon(WEAPONS["sg8"], rng=random.Random(3))
    for yaw, pitch in w.pellet_offsets(5.0):
        assert math.hypot(yaw, pitch) <= 5.0 + 1e-9


def test_spread_is_smaller_when_aiming_and_larger_when_moving():
    w = create_weapon(WEAPONS["kr7"])
    assert w.spread(ads=1.0) < w.spread(ads=0.0) < w.spread(ads=0.0, moving=1.0) < w.spread(moving=1.0, airborne=True)


def test_grenade_data():
    assert GRENADE.start_count == 2 and GRENADE.radius > 0
