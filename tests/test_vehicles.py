"""Headless tests for vehicles, rides, the recon drone, stealth takedowns, intel and mission ranks."""
import math

import pytest

from core.drone import pick_target
from core.ride import seat_world
from core.stealth import IntelTracker, is_unaware, perform_takedown, takedown_target
from missions import ranking
from missions.objectives import make_objective
from systems.collision_system import BoxCollider, CollisionWorld
from systems.combat_system import CombatSystem
from vehicles.manager import VehicleManager
from vehicles.path import Path

from tests.test_ai import FakePlayer, run, setup

DT = 1 / 30


def vehicle_world(player_pos=(0, 0)):
    world = CollisionWorld()
    combat = CombatSystem(world)
    vm = VehicleManager(world, combat, game=None, seed=3)
    player = FakePlayer(world, *player_pos)
    combat.register(player)
    vm.player = player
    return world, combat, vm, player


def step(vm, seconds):
    for _ in range(int(seconds / DT)):
        vm.update(DT)


# ---------------------------------------------------------------- paths and movement
def test_path_length_and_points():
    p = Path([(0, 0, 0), (10, 0, 0), (20, 0, 0)])
    assert p.length == pytest.approx(20.0, rel=0.02)
    assert p.point_at(0)[0] == pytest.approx(0.0)
    assert p.point_at(10)[0] == pytest.approx(10.0, abs=0.3)
    assert p.point_at(999)[0] == pytest.approx(20.0)


def test_boat_follows_its_path_and_finishes():
    _, _, vm, _ = vehicle_world()
    vm.water_z = -1.3
    boat = vm.spawn("player_boat", "b", path=[(0, 0, -1.3), (30, 0, -1.3)], speed=10.0)
    assert boat.team == "friendly" and not boat.armed
    step(vm, 1.0)
    assert 8.0 < boat.pos[0] < 12.0 and boat.pos[2] == pytest.approx(-1.3)
    step(vm, 3.0)
    assert boat.finished and boat.pos[0] == pytest.approx(30.0, abs=0.3)


def test_tank_ignores_bullets_but_dies_to_explosions():
    _, combat, vm, _ = vehicle_world(player_pos=(0, -200))
    tank = vm.spawn("tank", "t", pos=(0, 0, 0))
    tank.take_damage(1000, None, "torso", (1, 0, 0))
    assert tank.health.current == pytest.approx(tank.health.maximum)
    for _ in range(5):
        tank.take_damage(300, None, "blast", (1, 0, 0))
    assert not tank.alive and vm.is_destroyed("t")


def test_tank_falls_when_the_bridge_goes():
    _, _, vm, _ = vehicle_world(player_pos=(0, -200))
    tank = vm.spawn("tank", "t", pos=(0, 0, 0.25))
    tank.fall()
    step(vm, 3.0)
    assert tank.pos[2] < -6.0 and not tank.alive and vm.is_destroyed("t")


def test_helicopter_flies_in_then_attacks_the_player():
    _, _, vm, player = vehicle_world()
    heli = vm.spawn("attack_helicopter", "h", path=[(200, 0, 40), (80, 0, 30)], speed=40.0, orbit_radius=40,
                    altitude=20)
    assert heli.mode == "path"
    step(vm, 4.0)
    assert heli.mode == "attack"
    step(vm, 15.0)
    d = math.hypot(heli.pos[0], heli.pos[1])
    assert 25 < d < 60 and heli.pos[2] > 10
    assert player.damage_taken > 0                       # it strafes the player


def test_rocket_direct_hit_brings_down_the_helicopter_in_two_shots():
    _, _, vm, player = vehicle_world()
    heli = vm.spawn("attack_helicopter", "h", pos=(0, 40, 10), armed=False)
    heli.mode = "hover"
    for _ in range(2):
        vm.launch_rocket(player, (0, 0, 1.6), heli.center(), damage=300.0)
        step(vm, 1.5)
    assert not heli.alive and vm.is_destroyed("h")


def test_player_rocket_proximity_fuse_on_drone_near_miss():
    _, _, vm, player = vehicle_world()
    drone = vm.spawn("kamikaze_drone", "d", pos=(2.6, 30, 2.0))
    drone.speed = 0.0
    vm.launch_rocket(player, (0, 0, 2.0), (0, 60, 2.0))      # passes 3 m to the side
    step(vm, 1.0)
    assert not drone.alive


def test_kamikaze_drone_hunts_and_hurts_the_player():
    _, _, vm, player = vehicle_world()
    vm.spawn("kamikaze_drone", "d", pos=(0, 40, 15))
    step(vm, 8.0)
    assert vm.is_destroyed("d") and player.damage_taken > 20


def test_vehicle_command_hover_and_new_path():
    _, _, vm, _ = vehicle_world(player_pos=(0, -300))
    heli = vm.spawn("transport_helicopter", "e", path=[(0, 100, 30), (0, 50, 5)], speed=30.0)
    step(vm, 4.0)
    assert heli.mode == "hover" and heli.finished
    assert vm.command("e", path=[(0, 50, 5), (0, 50, 40)], speed=10.0)
    step(vm, 6.0)
    assert heli.pos[2] > 30
    assert not vm.command("missing", mode="hover")


# ---------------------------------------------------------------- rides
def test_seat_world_rotates_with_vehicle_heading():
    class V:
        pos = [10.0, 0.0, -1.0]
        heading = 0.0
    v = V()
    assert seat_world(v, (0, 2, 0.5)) == pytest.approx((10.0, 2.0, -0.5))
    v.heading = 90.0                                     # facing -X
    x, y, z = seat_world(v, (0, 2, 0))
    assert x == pytest.approx(8.0) and y == pytest.approx(0.0, abs=1e-9)


def test_mounted_soldier_rides_and_still_shoots():
    _, _, mgr, player = setup(player_pos=(0, 20))
    s = mgr.spawn("friendly", 0, 0, profile="squad", invulnerable=True)
    enemy = mgr.spawn("enemy", 6, 15, heading=180, profile="recruit")
    seat = [0.0, 0.0, 0.0]
    s.mount = lambda: tuple(seat)
    shots0 = s.weapon.shots_fired
    for i in range(int(6 / DT)):
        seat[0] = i * DT * 2.0                           # the vehicle moves along X
        mgr.update(DT)
    assert s.motor.x == pytest.approx(seat[0]) and s.motor.y == pytest.approx(0.0)
    assert s.weapon.shots_fired > shots0 or not enemy.alive


# ---------------------------------------------------------------- drone tagging
class Target:
    def __init__(self, pos, alive=True):
        self.pos = pos
        self.alive = alive

    def center(self):
        return self.pos


def test_drone_tags_the_target_under_the_reticle():
    world = CollisionWorld()
    a, b = Target((0, 50, 1)), Target((10, 50, 1))
    fwd = (0.0, 50 / math.hypot(50, 24), -24 / math.hypot(50, 24))
    assert pick_target((0, 0, 25), fwd, [a, b], world.line_of_sight) is a
    assert pick_target((0, 0, 25), fwd, [b], world.line_of_sight) is None
    assert pick_target((0, 0, 25), fwd, [Target((0, 50, 1), alive=False)], world.line_of_sight) is None


def test_drone_cannot_tag_through_a_roof():
    world = CollisionWorld()
    world.add(BoxCollider(0, 50, 2.5, 3.0, 5, 5))
    fwd = (0.0, 50 / math.hypot(50, 24), -24 / math.hypot(50, 24))
    assert pick_target((0, 0, 25), fwd, [Target((0, 50, 1))], world.line_of_sight) is None


# ---------------------------------------------------------------- takedowns and night vision range
def test_silent_takedown_does_not_alert_a_guard_looking_away():
    _, _, mgr, player = setup(player_pos=(0, 0))
    victim = mgr.spawn("enemy", 0, 1.2, heading=0, profile="regular")        # back to the player
    other = mgr.spawn("enemy", 6, 1.2, heading=-90, profile="regular")       # looking away (east)
    assert takedown_target(player.position, 0.0, mgr.soldiers) is victim
    assert takedown_target(player.position, 180.0, mgr.soldiers) is None     # player facing the other way
    assert is_unaware(victim)
    assert perform_takedown(player, victim) is True
    assert not victim.alive and other.ai.state not in ("ATTACK", "CHASE", "TAKE_COVER")


def test_loud_kill_alerts_nearby_guards():
    _, combat, mgr, player = setup(player_pos=(0, 0))
    victim = mgr.spawn("enemy", 0, 1.2, heading=0, profile="regular")
    other = mgr.spawn("enemy", 6, 1.2, heading=-90, profile="regular")
    victim.take_damage(500, player, "torso", (0, 1, 0))
    assert other.ai.awareness > 0.5


def test_night_shortens_enemy_vision_except_in_light():
    _, _, mgr, player = setup(player_pos=(0, -30))
    e = mgr.spawn("enemy", 0, 0, heading=180, profile="regular")
    rng_day = e.ai.p["vision_range"] * mgr.vision_scale(e, player)
    mgr.visibility = 0.4
    assert mgr.vision_scale(e, player) == pytest.approx(0.4)
    mgr.lit_zones = [(0, -30, 5)]
    assert mgr.vision_scale(e, player) == 1.0
    assert rng_day == e.ai.p["vision_range"]


def test_enemy_does_not_spot_player_in_the_dark_at_range():
    _, _, mgr, player = setup(player_pos=(0, -28))
    e = mgr.spawn("enemy", 0, 0, heading=180, profile="regular")
    mgr.visibility = 0.3
    run(mgr, 3.0)
    assert e.ai.awareness < 0.3
    mgr.visibility = 1.0
    run(mgr, 4.0)
    assert e.ai.awareness > 0.3


# ---------------------------------------------------------------- intel
def test_intel_pickup_needs_holding_e_and_restores_from_checkpoint():
    t = IntelTracker()
    t.setup([{"id": "a", "pos": (0, 0, 1), "name": "Map"}, {"id": "b", "pos": (20, 0, 1)}])
    assert t.total == 2 and t.found == 0
    item, progress, got = t.update(0.1, (0, 0.5, 1.6), False)
    assert item is not None and got is None and progress == 0
    for _ in range(10):
        item, progress, got = t.update(0.1, (0, 0.5, 1.6), True)
        if got:
            break
    assert got is not None and got.id == "a" and t.found == 1
    t.restore([])
    assert t.found == 0
    t.restore(["a"])
    assert t.collected_ids() == ["a"]


# ---------------------------------------------------------------- ranking
def test_mission_rank():
    gold = {"time": 900, "deaths": 0, "accuracy": 0.4, "stealth": True, "intel": 3, "intel_total": 3}
    assert ranking.rank(gold, 1200) == "GOLD"
    assert ranking.rank(dict(gold, accuracy=0.1), 1200) == "GOLD"          # one point may be missed
    assert ranking.rank(dict(gold, accuracy=0.1, stealth=False), 1200) == "SILVER"
    assert ranking.rank({"time": 5000, "deaths": 3, "accuracy": 0.1, "stealth": False, "intel": 0,
                         "intel_total": 3}, 1200) == "BRONZE"
    assert ranking.rank({"time": 100, "deaths": 0, "accuracy": 0.5}) == "GOLD"   # no stealth / intel section
    assert ranking.better("SILVER", "GOLD") == "GOLD" and ranking.better(None, "BRONZE") == "BRONZE"


# ---------------------------------------------------------------- objectives
class Ctx:
    def __init__(self):
        self.eye = (0, 0, 1.68)
        self.held = True
        self.done = []
        self.prompt = None

    def player_eye_position(self): return self.eye
    def player_looking_at(self, pos, deg): return True
    def interact_held(self): return self.held
    def set_prompt(self, text, progress=None): self.prompt = text
    def point_done(self, spec, pos): self.done.append(pos)


def test_interact_multi_marks_the_nearest_point_and_counts():
    o = make_objective({"type": "interact_multi", "text": "Plant", "points": [[0, 0, 1], [30, 0, 1]], "hold": 1.0})
    ctx = Ctx()
    for _ in range(12):
        o.update(ctx, 0.1)
    assert ctx.done == [(0, 0, 1)] and o.status() == "Plant (1/2)" and o.marker == (30, 0, 1)
    ctx.eye = (30, 0, 1.68)
    finished = any(o.update(ctx, 0.1) for _ in range(12))
    assert finished and len(ctx.done) == 2


# ---------------------------------------------------------------- security cameras and captives
def test_security_camera_sweeps_spots_and_can_be_shot_out():
    from systems.security import SecurityManager
    world = CollisionWorld()
    combat = CombatSystem(world)
    sec = SecurityManager(world, combat)
    cam = sec.spawn("c", (0, 0, 3.0), heading=0, sweep=0, view_range=20, pitch=-20)
    _, _, _, player = vehicle_world(player_pos=(0, 10))
    for _ in range(int(0.5 / DT)):
        sec.update(DT, player)
    assert 0 < cam.suspicion < 1 and not sec.spotted
    for _ in range(int(1.0 / DT)):
        sec.update(DT, player)
    assert sec.spotted
    cam2 = sec.spawn("c2", (40, 0, 3.0), heading=0, sweep=0)
    hit = combat.fire(player, (40, -5, 3.0), (0, 1, 0), type("G", (), {"damage": 30, "headshot_multiplier": 1,
                      "range": 50, "falloff_start": 50, "falloff_end": 60, "min_damage_multiplier": 1})())
    assert hit is not None and not cam2.alive


def test_camera_does_not_see_behind_or_through_walls():
    from systems.security import SecurityCamera
    world = CollisionWorld()
    cam = SecurityCamera("c", (0, 0, 3.0), heading=0, view_range=20, pitch=-20)
    assert cam.sees((0, 10, 1.0), world.line_of_sight)
    assert not cam.sees((0, -10, 1.0), world.line_of_sight)        # behind
    world.add(BoxCollider(0, 5, 0, 4, 3, 0.2))
    assert not cam.sees((0, 10, 1.0), world.line_of_sight)         # wall in between


def test_captive_is_not_targeted_by_enemies():
    _, _, mgr, player = setup(player_pos=(0, 38))          # far behind the guard
    hostage = mgr.spawn("friendly", 0, 0, profile="wounded")
    hostage.captive = True
    guard = mgr.spawn("enemy", 0, 3, heading=180, profile="regular")
    assert hostage not in mgr.hostiles("enemy")
    run(mgr, 3.0)
    assert hostage.alive and guard.ai.state not in ("ATTACK", "TAKE_COVER")
    hostage.captive = False
    assert hostage in mgr.hostiles("enemy")
