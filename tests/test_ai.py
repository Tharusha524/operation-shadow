"""Headless tests for the soldier AI (no window, no graphics)."""
import math

import pytest

from enemies.enemy_manager import SoldierManager
from player.health import Health
from player.movement import PlayerMotor
from systems.collision_system import BoxCollider, CollisionWorld
from systems.combat_system import CombatSystem, character_hitboxes
from systems.navigation import NavGrid

DT = 1 / 30


class FakeCamera:
    class look:
        yaw = 0.0
        pitch = 0.0


class FakePlayer:
    team = "friendly"
    name = "Player"

    def __init__(self, world, x, y):
        self.motor = PlayerMotor(world, (x, y, 0))
        self.health = Health(100000)
        self.camera = FakeCamera()
        self.damage_taken = 0.0

    alive = property(lambda s: s.health.alive)
    position = property(lambda s: (s.motor.x, s.motor.y, s.motor.z))

    def eye_position(self):
        return self.motor.x, self.motor.y, 1.68

    def center(self):
        return self.motor.x, self.motor.y, 1.0

    def hitboxes(self):
        return character_hitboxes(self.motor.x, self.motor.y, 0.0, 1.8)

    def take_damage(self, amount, source, zone, direction):
        self.damage_taken += amount
        return self.health.take_damage(amount)


def setup(extra=(), player_pos=(0, 0)):
    world = CollisionWorld()
    for c in extra:
        world.add(c)
    combat = CombatSystem(world)
    nav = NavGrid(world, (-40, -40, 40, 40))
    mgr = SoldierManager(world, combat, nav, seed=7)
    player = FakePlayer(world, *player_pos)
    mgr.player = player
    combat.register(player)
    return world, combat, mgr, player


def run(mgr, seconds, until=None):
    for _ in range(int(seconds / DT)):
        mgr.update(DT)
        if until and until():
            return True
    return False


def test_patrol_walks_between_waypoints():
    _, _, mgr, player = setup(player_pos=(0, -35))
    player.motor.teleport(0, -39, 0)
    e = mgr.spawn("enemy", 10, 10, heading=0, patrol=[(10, 18), (18, 18)])
    e.ai.p = dict(e.ai.p, vision_range=5)          # don't notice the player for this test
    reached = run(mgr, 25, until=lambda: math.dist((e.motor.x, e.motor.y), (18, 18)) < 1.5)
    assert reached and e.ai.state == "PATROL"


def test_enemy_spots_and_shoots_player_in_view():
    _, _, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 25, heading=180)      # facing the player
    run(mgr, 8)
    assert e.ai.state in ("ATTACK", "TAKE_COVER")
    assert player.damage_taken > 0


def test_enemy_cannot_see_through_walls():
    wall = BoxCollider(0, 12, 0, 4, hx=8, hy=0.3)
    _, _, mgr, player = setup([wall], player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 25, heading=180)
    run(mgr, 5)
    assert e.ai.state == "IDLE" and player.damage_taken == 0


def test_enemy_behind_player_does_not_notice_at_distance():
    _, _, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 25, heading=0)        # looking away
    run(mgr, 4)
    assert e.ai.state == "IDLE"


def test_hearing_a_gunshot_makes_enemy_investigate():
    wall = BoxCollider(0, 12, 0, 4, hx=8, hy=0.3)
    _, combat, mgr, player = setup([wall], player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 25, heading=0)
    start = (e.motor.x, e.motor.y)
    combat.emit_noise((0, 0, 1.5), 70, "friendly", player)
    run(mgr, 0.5)
    assert e.ai.state == "INVESTIGATE"
    run(mgr, 4)
    assert math.dist(start, (e.motor.x, e.motor.y)) > 2.0


def test_damaged_enemy_takes_cover_when_available():
    cover_wall = BoxCollider(6, 18, 0, 1.1, hx=1.5, hy=0.3)
    _, _, mgr, player = setup([cover_wall], player_pos=(0, 0))
    e = mgr.spawn("enemy", 4, 22, heading=180, profile="recruit")
    e.ai.p = dict(e.ai.p, aggression=0.0)
    e.take_damage(10, player, "body", (0, 1, 0))
    seen_cover = run(mgr, 6, until=lambda: e.ai.state == "TAKE_COVER" and e.ai.cover_phase == "hiding")
    assert seen_cover
    assert e.motor.y > 18.0                          # on the far side of the wall from the player


def test_enemy_chases_last_known_position():
    wall = BoxCollider(5, 10, 0, 4, hx=3, hy=0.3)
    _, _, mgr, player = setup([wall], player_pos=(0, 5))
    e = mgr.spawn("enemy", 0, 30, heading=180)
    run(mgr, 3)
    assert e.ai.state in ("ATTACK", "TAKE_COVER")
    player.motor.teleport(5, 2, 0)                   # hide behind the wall
    e.ai.p = dict(e.ai.p, aggression=1.0)
    moved = run(mgr, 12, until=lambda: e.ai.state in ("CHASE", "INVESTIGATE"))
    assert moved


def test_enemy_reloads_after_emptying_magazine():
    _, _, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 15, heading=180, profile="veteran")
    e.ai.p = dict(e.ai.p, aggression=1.0, burst=[30, 30], burst_pause=[0.1, 0.1])
    reloaded = run(mgr, 20, until=lambda: e.weapon.reloading)
    assert reloaded
    run(mgr, 3)
    assert e.weapon.mag > 0


def test_enemy_dies():
    _, combat, mgr, player = setup(player_pos=(0, 0))
    e = mgr.spawn("enemy", 0, 15, heading=0)
    deaths = []
    mgr.kill_listeners.append(lambda s, k, z: deaths.append((s, k, z)))
    assert e.take_damage(1000, player, "head", (0, 1, 0)) is True
    assert not e.alive and e.ai.state == "DEAD" and deaths[0][1] is player
    r = combat.raycast((0, 0, 1.2), (0, 1, 0), 50, ignore=player)
    assert r is None or r.target is None


def test_squad_member_follows_player():
    _, _, mgr, player = setup(player_pos=(0, 0))
    ally = mgr.spawn("friendly", -20, -20, name="Sgt. Marek", invulnerable=True, profile="squad")
    run(mgr, 12)
    assert ally.ai.state == "FOLLOW"
    assert math.dist((ally.motor.x, ally.motor.y), (0, 0)) < 6.0


def test_squad_member_fights_enemies_and_cannot_die():
    _, _, mgr, player = setup(player_pos=(0, -6))       # squad mates stay within ~14 m of the player
    ally = mgr.spawn("friendly", 0, 0, heading=0, name="Cpl. Voss", invulnerable=True, profile="squad")
    enemy = mgr.spawn("enemy", 0, 25, heading=180, profile="recruit")
    run(mgr, 12)
    assert enemy.health.current < enemy.health.maximum
    assert ally.alive


def test_squad_fighting_retreat_keeps_shooting_while_returning_to_player():
    _, _, mgr, player = setup(player_pos=(0, -30))
    ally = mgr.spawn("friendly", 0, 0, heading=0, invulnerable=True, profile="squad")
    mgr.spawn("enemy", 0, 25, heading=180, profile="recruit")
    run(mgr, 10)
    assert ally.weapon.shots_fired > 0
    assert math.dist((ally.motor.x, ally.motor.y), (0, -30)) < 25.0      # moved back towards the player


def test_hold_command_keeps_squad_in_place():
    _, _, mgr, player = setup(player_pos=(0, 0))
    ally = mgr.spawn("friendly", 2, 2, invulnerable=True, profile="squad")
    ally.ai.command_hold(10, 10, 0)
    run(mgr, 8)
    assert math.dist((ally.motor.x, ally.motor.y), (10, 10)) < 1.2
    player.motor.teleport(-30, -30, 0)
    run(mgr, 4)
    assert math.dist((ally.motor.x, ally.motor.y), (10, 10)) < 1.2


def test_enemy_holding_a_position_never_leaves_it():
    cover_wall = BoxCollider(5, 18, 0, 1.1, hx=2, hy=0.3)
    _, combat, mgr, player = setup([cover_wall], player_pos=(0, -10))
    gunner = mgr.spawn("enemy", 0, 25, heading=180, profile="gunner")
    gunner.ai.command_hold(0, 25, 180)
    combat.emit_noise((10, 5, 1.5), 80, "friendly", player)            # gunfire nearby
    gunner.ai.alert(player, (0, -10, 0))                               # ally shouts
    gunner.take_damage(40, player, "body", (0, 1, 0))                  # gets shot
    run(mgr, 10)
    assert math.dist((gunner.motor.x, gunner.motor.y), (0, 25)) < 1.2
    assert gunner.weapon.shots_fired > 0                               # but fights back from the post


def test_soldiers_do_not_overlap():
    _, _, mgr, player = setup(player_pos=(0, -30))
    a = mgr.spawn("enemy", 0, 0)
    b = mgr.spawn("enemy", 0.1, 0.05)
    run(mgr, 1)
    assert math.dist((a.motor.x, a.motor.y), (b.motor.x, b.motor.y)) > 0.6


# ---------------------------------------------------------------- escort (wounded soldier)
ROUTE = [(0, 0), (0, 15), (15, 15)]


def test_wounded_soldier_walks_route_while_player_is_near():
    _, _, mgr, player = setup(player_pos=(0, -3))
    kell = mgr.spawn("friendly", 0, 0, profile="wounded", name="Kell")
    kell.ai.command_escort(ROUTE)
    for _ in range(int(25 / DT)):
        player.motor.teleport(kell.motor.x, kell.motor.y - 3, 0)      # the player stays close
        mgr.update(DT)
    assert math.dist((kell.motor.x, kell.motor.y), (15, 15)) < 2.0
    assert kell.weapon.shots_fired == 0


def test_wounded_soldier_waits_for_player():
    _, _, mgr, player = setup(player_pos=(0, -30))
    kell = mgr.spawn("friendly", 0, 0, profile="wounded")
    kell.ai.command_escort(ROUTE)
    run(mgr, 6)
    assert math.dist((kell.motor.x, kell.motor.y), (0, 0)) < 1.0         # player too far: he waits


def test_wounded_soldier_gets_down_when_enemy_close_and_never_shoots():
    _, _, mgr, player = setup(player_pos=(0, -2))
    kell = mgr.spawn("friendly", 0, 0, heading=0, profile="wounded")
    kell.ai.command_escort(ROUTE)
    mgr.spawn("enemy", 0, 14, heading=180, profile="recruit")
    run(mgr, 3)
    assert kell.crouch and kell.weapon.shots_fired == 0
    assert kell.motor.y < 3.0


def test_marek_follows_the_wounded_instead_of_the_player():
    _, _, mgr, player = setup(player_pos=(-30, -30))
    kell = mgr.spawn("friendly", 10, 10, profile="wounded")
    kell.ai.command_hold(10, 10, 0)                    # resting at a spot (as in the mission)
    marek = mgr.spawn("friendly", 0, 0, invulnerable=True, profile="squad")
    marek.ai.leader = kell
    run(mgr, 8)
    assert math.dist((marek.motor.x, marek.motor.y), (10, 10)) < 6.0
