import pytest

from config import constants as C
from player.movement import MotorInput, PlayerMotor
from systems.collision_system import BoxCollider, CollisionWorld

DT = 1.0 / 60.0


def run(motor, seconds, **inp):
    steps = int(round(seconds / DT))
    for _ in range(steps):
        motor.update(DT, MotorInput(**inp))


def make(world=None, pos=(0, 0, 0)):
    world = world or CollisionWorld()
    motor = PlayerMotor(world, pos)
    run(motor, 0.1)  # settle onto the ground
    return motor


def test_falls_and_lands_on_floor():
    motor = PlayerMotor(CollisionWorld(), (0, 0, 3))
    run(motor, 1.5)
    assert motor.grounded
    assert motor.z == pytest.approx(0.0)
    assert "land" in motor.pop_events()


def test_walk_reaches_walk_speed_in_facing_direction():
    motor = make()
    run(motor, 1.0, forward=1.0, yaw=0.0)
    assert motor.horizontal_speed == pytest.approx(C.WALK_SPEED, rel=0.01)
    assert motor.y > 4.0 and abs(motor.x) < 1e-6


def test_yaw_rotates_movement():
    motor = make()
    run(motor, 1.0, forward=1.0, yaw=90.0)   # heading 90 = facing -X in Panda3D
    assert motor.x < -4.0 and abs(motor.y) < 1e-6


def test_strafe_right():
    motor = make()
    run(motor, 1.0, right=1.0, yaw=0.0)
    assert motor.x > 4.0


def test_sprint_is_faster_and_only_forward():
    motor = make()
    run(motor, 1.0, forward=1.0, sprint=True)
    assert motor.sprinting
    assert motor.horizontal_speed == pytest.approx(C.SPRINT_SPEED, rel=0.01)
    motor2 = make()
    run(motor2, 1.0, forward=-1.0, sprint=True)
    assert not motor2.sprinting
    assert motor2.horizontal_speed == pytest.approx(C.WALK_SPEED * C.BACKWARD_SPEED_FACTOR, rel=0.01)


def test_stops_when_input_released():
    motor = make()
    run(motor, 1.0, forward=1.0)
    run(motor, 0.5)
    assert motor.horizontal_speed == pytest.approx(0.0, abs=1e-6)


def test_jump_height_and_landing():
    motor = make()
    motor.update(DT, MotorInput(jump=True))
    assert "jump" in motor.pop_events()
    peak = 0.0
    for _ in range(120):
        motor.update(DT, MotorInput())
        peak = max(peak, motor.z)
    expected = C.JUMP_SPEED ** 2 / (2 * C.GRAVITY)
    assert peak == pytest.approx(expected, rel=0.05)
    assert motor.grounded and motor.z == pytest.approx(0.0)


def test_cannot_double_jump():
    motor = make()
    motor.update(DT, MotorInput(jump=True))
    run(motor, 0.3)
    vz_before = motor.vz
    motor.update(DT, MotorInput(jump=True))
    assert motor.vz < vz_before  # still falling/decelerating, no second boost


def test_coyote_time_allows_late_jump_after_ledge():
    world = CollisionWorld()
    world.add(BoxCollider(0, 0, 0, 2.0, hx=2, hy=2))
    motor = make(world, (0, 1.5, 2.0))
    assert motor.grounded and motor.z == pytest.approx(2.0)
    # Walk off the +Y edge.
    while motor.grounded:
        motor.update(DT, MotorInput(forward=1.0))
    motor.update(DT, MotorInput(forward=1.0, jump=True))
    assert motor.vz > 0.0


def test_wall_blocks_movement():
    world = CollisionWorld()
    world.add(BoxCollider(0, 5, 0, 3, hx=10, hy=0.2))
    motor = make(world)
    run(motor, 3.0, forward=1.0)
    assert motor.y <= 4.8 - C.PLAYER_RADIUS + 1e-6
    assert motor.y > 4.0


def test_slides_along_wall_when_moving_diagonally():
    world = CollisionWorld()
    world.add(BoxCollider(0, 2, 0, 3, hx=50, hy=0.2))
    motor = make(world)
    run(motor, 2.0, forward=1.0, right=1.0)
    assert motor.y <= 1.8 - C.PLAYER_RADIUS + 1e-6
    assert motor.x > 3.0


def test_fast_movement_does_not_tunnel_through_thin_wall():
    world = CollisionWorld()
    world.add(BoxCollider(0, 3, 0, 3, hx=10, hy=0.05))
    motor = make(world)
    motor.vy = 200.0  # absurd speed for one frame
    motor.update(C.MAX_FRAME_DT, MotorInput(forward=1.0))
    assert motor.y < 3.0


def test_steps_up_low_obstacle_but_not_high_one():
    world = CollisionWorld()
    world.add(BoxCollider(0, 12, 0, 0.3, hx=1, hy=10))     # long kerb, can step onto it
    motor = make(world)
    run(motor, 1.5, forward=1.0)
    assert motor.z == pytest.approx(0.3)

    world2 = CollisionWorld()
    world2.add(BoxCollider(0, 3, 0, 0.7, hx=1, hy=1))      # crate, too high
    motor2 = make(world2)
    run(motor2, 1.5, forward=1.0)
    assert motor2.z == pytest.approx(0.0)
    assert motor2.y < 2.0


def test_can_jump_onto_crate():
    world = CollisionWorld()
    world.add(BoxCollider(0, 6, 0, 0.8, hx=1, hy=5))       # long crate row from y=1 to y=11
    motor = make(world)
    motor.update(DT, MotorInput(forward=1.0, jump=True))
    run(motor, 1.2, forward=1.0)
    assert motor.z == pytest.approx(0.8)


def test_climbs_stairs():
    world = CollisionWorld()
    rise, run_len = 0.25, 0.3
    for i in range(1, 17):
        y0 = 1.0 + (i - 1) * run_len
        world.add(BoxCollider(0, y0 + run_len / 2, 0, i * rise, hx=0.6, hy=run_len / 2))
    world.add(BoxCollider(0, 1.0 + 16 * run_len + 10, 0, 4.0, hx=1.5, hy=10))  # long landing
    motor = make(world)
    run(motor, 3.0, forward=1.0)
    assert motor.z == pytest.approx(4.0)


def test_walks_down_stairs_without_leaving_ground():
    world = CollisionWorld()
    for i in range(1, 9):
        world.add(BoxCollider(0, -(i * 0.3) + 0.15, 0, 2.0 - i * 0.25, hx=0.6, hy=0.15))
    world.add(BoxCollider(0, 1.0, 0, 2.0, hx=1, hy=1))
    motor = make(world, (0, 1.0, 2.0))
    airborne_frames = 0
    for _ in range(int(1.0 / DT)):
        motor.update(DT, MotorInput(forward=-1.0))
        if not motor.grounded:
            airborne_frames += 1
    assert motor.z < 0.5
    assert airborne_frames < 5


def test_ceiling_stops_jump():
    world = CollisionWorld()
    world.add(BoxCollider(0, 0, 2.2, 2.5, hx=2, hy=2))
    motor = make(world)
    motor.update(DT, MotorInput(jump=True))
    run(motor, 1.0)
    assert motor.z + C.PLAYER_STAND_HEIGHT <= 2.2 + 1e-6 or motor.grounded


def test_crouch_lowers_height_and_speed():
    motor = make()
    run(motor, 1.0, forward=1.0, crouch=True)
    assert motor.height == pytest.approx(C.PLAYER_CROUCH_HEIGHT)
    assert motor.horizontal_speed == pytest.approx(C.CROUCH_SPEED, rel=0.01)
    run(motor, 1.0)
    assert motor.height == pytest.approx(C.PLAYER_STAND_HEIGHT)


def test_cannot_stand_up_under_low_ceiling():
    world = CollisionWorld()
    world.add(BoxCollider(0, 3, 1.4, 2.0, hx=2, hy=1))   # low pipe/table
    motor = make(world)
    run(motor, 1.5, forward=1.0, crouch=True)
    assert 2.0 < motor.y < 4.0                        # crawled under it
    run(motor, 0.5, crouch=False)
    assert motor.height < 1.4                         # still crouched


def test_footstep_events_while_walking():
    motor = make()
    motor.pop_events()
    run(motor, 2.0, forward=1.0)
    steps = motor.pop_events().count("footstep")
    expected = (C.WALK_SPEED * 2.0) / C.WALK_STRIDE
    assert abs(steps - expected) <= 1.5
