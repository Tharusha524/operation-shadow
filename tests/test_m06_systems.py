"""Headless tests for Mission 6 systems: driving, enemy jeeps, smoke and flashbangs."""
import math

import pytest

from enemies.enemy_manager import segment_hits_sphere
from systems.collision_system import BoxCollider
from tests.test_ai import run, setup
from tests.test_vehicles import DT, vehicle_world


def drive(jeep, seconds, throttle=1.0, steer=0.0, brake=False):
    for _ in range(int(seconds / DT)):
        jeep.drive(DT, throttle, steer, brake)


# ---------------------------------------------------------------- driving
def test_jeep_accelerates_to_top_speed_and_brakes():
    _, _, vm, _ = vehicle_world()
    jeep = vm.spawn("player_jeep", "j", pos=(0, 0, 0), heading=0)
    drive(jeep, 1.0)
    assert 7.0 < jeep.velocity < 9.0 and jeep.pos[1] > 2.0
    drive(jeep, 6.0)
    assert jeep.velocity == pytest.approx(jeep.MAX_SPEED)
    drive(jeep, 2.0, throttle=0.0, brake=True)
    assert jeep.velocity == pytest.approx(0.0)


def test_jeep_steers_left_and_right_only_when_moving():
    _, _, vm, _ = vehicle_world()
    jeep = vm.spawn("player_jeep", "j", pos=(0, 0, 0), heading=0)
    drive(jeep, 1.0, throttle=0.0, steer=1.0)
    assert jeep.heading == pytest.approx(0.0)                # parked: no turning on the spot
    drive(jeep, 1.5)
    drive(jeep, 0.5, steer=1.0)
    assert jeep.heading < -10.0                              # D turns right (clockwise)
    h = jeep.heading
    drive(jeep, 1.0, steer=-1.0)
    assert jeep.heading > h


def test_jeep_reverses_and_steering_flips():
    _, _, vm, _ = vehicle_world()
    jeep = vm.spawn("player_jeep", "j", pos=(0, 0, 0), heading=0)
    drive(jeep, 2.0, throttle=-1.0)
    assert jeep.velocity == pytest.approx(-jeep.REVERSE_SPEED) and jeep.pos[1] < -2.0
    drive(jeep, 0.5, throttle=-1.0, steer=1.0)
    assert jeep.heading > 5.0


def test_jeep_crashes_into_walls_and_stops():
    world, _, vm, _ = vehicle_world()
    world.add(BoxCollider(0, 30, 0, 3, 10, 1))
    jeep = vm.spawn("player_jeep", "j", pos=(0, 0, 0), heading=0)
    drive(jeep, 4.0)
    assert jeep.pos[1] < 29.0 and any(e[0] == "crash" for e in jeep.events)


def test_jeep_rams_breakable_barrier_at_speed_but_not_when_slow():
    world, _, vm, _ = vehicle_world()
    world.add(BoxCollider(0, 40, 0, 1.2, 4, 0.4, tag="barrier"))
    jeep = vm.spawn("player_jeep", "j", pos=(0, 0, 0), heading=0)
    jeep.breakables = {"barrier"}
    drive(jeep, 3.5)
    assert any(e[0] == "ram" and "barrier" in e[1] for e in jeep.events)
    jeep2 = vm.spawn("player_jeep", "k", pos=(0, 37.2, 0), heading=0)
    jeep2.breakables = {"barrier"}
    drive(jeep2, 0.6, throttle=0.3)
    assert not any(e[0] == "ram" for e in jeep2.events)


def test_enemy_jeep_keeps_up_with_the_player_along_the_road():
    _, _, vm, player = vehicle_world(player_pos=(0, 100))
    road = [(0, 0, 0), (0, 300, 0)]
    ej = vm.spawn("enemy_jeep", "e", path=road, chase_offset=-20.0)
    for _ in range(int(12 / DT)):
        vm.update(DT)
    assert ej.pos[1] == pytest.approx(80.0, abs=4.0)         # sits 20 m behind the player
    player.motor.teleport(0, 200, 0)
    for _ in range(int(8 / DT)):
        vm.update(DT)
    assert ej.pos[1] == pytest.approx(180.0, abs=6.0)


def test_enemy_jeep_takes_bullets_and_blows_up():
    _, _, vm, _ = vehicle_world(player_pos=(0, 300))
    ej = vm.spawn("enemy_jeep", "e", pos=(0, 0, 0), health=100)
    assert ej.team == "enemy"
    ej.take_damage(150, None, "torso", (0, 1, 0))
    assert ej.alive and ej.health.current == pytest.approx(25.0)
    ej.take_damage(100, None, "blast", (0, 1, 0))
    assert not ej.alive and vm.is_destroyed("e")


# ---------------------------------------------------------------- smoke and flashbangs
def test_smoke_cloud_blocks_sight_lines():
    assert segment_hits_sphere((0, 0, 1), (0, 20, 1), (0, 10, 1), 3)
    assert not segment_hits_sphere((0, 0, 1), (0, 20, 1), (8, 10, 1), 3)
    _, _, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 20, heading=180, profile="regular")
    mgr.smoke_clouds = [(0, 10, 1.3, 5.0)]
    run(mgr, 4.0)
    assert e.ai.awareness < 0.3 and e.ai.state not in ("ATTACK", "TAKE_COVER")
    mgr.smoke_clouds = []
    run(mgr, 4.0)
    assert e.ai.state in ("ATTACK", "TAKE_COVER", "CHASE")


def test_flashbang_stun_stops_an_enemy_from_shooting():
    _, _, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 12, heading=180, profile="regular")
    run(mgr, 3.0)
    assert e.ai.state in ("ATTACK", "TAKE_COVER")
    e.ai.stun(3.0)
    shots = e.weapon.shots_fired
    run(mgr, 2.5)
    assert e.weapon.shots_fired == shots and e.ai.stunned > 0.0
    run(mgr, 4.0)
    assert e.ai.stunned <= 0.0 and e.weapon.shots_fired > shots  # recovers and fights again


def test_stunned_soldier_cannot_see():
    _, _, mgr, _ = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 10, heading=180, profile="regular")
    e.ai.stun(2.0)
    run(mgr, 1.5)
    assert not e.ai.target_visible and math.isclose(e.ai.stunned, 0.5, abs_tol=0.1)
