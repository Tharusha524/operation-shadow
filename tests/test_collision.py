import math

import pytest

from systems.collision_system import BoxCollider, CollisionWorld, CylinderCollider


def test_box_pushes_circle_out_sideways():
    box = BoxCollider(0, 0, 0, 3, hx=1, hy=1)
    push = box.circle_push(1.2, 0, 0.35)
    assert push is not None
    px, py = push
    assert px == pytest.approx(0.15)
    assert py == pytest.approx(0.0)


def test_box_no_push_when_apart():
    box = BoxCollider(0, 0, 0, 3, hx=1, hy=1)
    assert box.circle_push(2.0, 0, 0.35) is None


def test_box_push_when_centre_inside_uses_shallowest_side():
    box = BoxCollider(0, 0, 0, 3, hx=2, hy=1)
    px, py = box.circle_push(0.5, 0.8, 0.35)
    assert px == pytest.approx(0.0)
    assert py == pytest.approx(0.2 + 0.35)


def test_rotated_box_pushes_along_rotated_normal():
    # A long thin wall rotated 45 degrees.
    box = BoxCollider(0, 0, 0, 3, hx=5, hy=0.1, yaw=45)
    # Point slightly off the wall along its local +Y normal.
    n = (-math.sin(math.radians(45)), math.cos(math.radians(45)))
    x, y = n[0] * 0.3, n[1] * 0.3
    px, py = box.circle_push(x, y, 0.35)
    length = math.hypot(px, py)
    assert length == pytest.approx(0.15, abs=1e-6)
    assert px / length == pytest.approx(n[0], abs=1e-6)
    assert py / length == pytest.approx(n[1], abs=1e-6)


def test_rotated_box_bounds_cover_corners():
    box = BoxCollider(10, 5, 0, 1, hx=2, hy=1, yaw=30)
    x0, y0, x1, y1 = box.bounds
    for sx in (-1, 1):
        for sy in (-1, 1):
            lx, ly = sx * 2, sy * 1
            c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
            wx, wy = 10 + lx * c - ly * s, 5 + lx * s + ly * c
            assert x0 - 1e-9 <= wx <= x1 + 1e-9
            assert y0 - 1e-9 <= wy <= y1 + 1e-9


def test_cylinder_push():
    cyl = CylinderCollider(0, 0, 0, 2, radius=0.5)
    px, py = cyl.circle_push(0.6, 0, 0.35)
    assert px == pytest.approx(0.25)
    assert py == pytest.approx(0.0)


def test_world_query_finds_collider_spanning_many_cells():
    world = CollisionWorld(cell_size=4)
    wall = BoxCollider(0, 0, 0, 3, hx=50, hy=0.2)
    world.add(wall)
    assert world.query_circle(-45, 0, 0.5) == [wall]
    assert world.query_circle(45, 0, 0.5) == [wall]
    assert world.query_circle(0, 30, 0.5) == []


def test_resolve_horizontal_ignores_low_steps_and_blocks_walls():
    world = CollisionWorld()
    world.add(BoxCollider(0, 1, 0, 0.3, hx=1, hy=1))      # low step
    world.add(BoxCollider(5, 1, 0, 3.0, hx=1, hy=1))      # wall
    x, y, normals = world.resolve_horizontal(0, 0.2, 0.35, 0.0, 1.8, 0.45)
    assert (x, y) == (0, 0.2) and normals == []
    x, y, normals = world.resolve_horizontal(5, -0.2, 0.35, 0.0, 1.8, 0.45)
    assert y == pytest.approx(-0.35)
    assert normals


def test_overhead_collider_does_not_block_horizontally():
    world = CollisionWorld()
    world.add(BoxCollider(0, 0, 2.5, 3.0, hx=2, hy=2))    # beam above head
    x, y, normals = world.resolve_horizontal(0, 0, 0.35, 0.0, 1.8, 0.45)
    assert normals == []


def test_ground_and_ceiling_heights():
    world = CollisionWorld(floor_z=0.0)
    world.add(BoxCollider(0, 0, 0, 0.4, hx=1, hy=1))
    world.add(BoxCollider(0, 0, 3.0, 3.2, hx=1, hy=1))
    assert world.ground_height(0, 0, 0.3, max_z=0.45) == pytest.approx(0.4)
    assert world.ground_height(0, 0, 0.3, max_z=0.2) == pytest.approx(0.0)
    assert world.ceiling_height(0, 0, 0.3, min_z=2.0) == pytest.approx(3.0)
    assert world.ceiling_height(5, 5, 0.3, min_z=2.0) == math.inf


def test_is_free():
    world = CollisionWorld()
    world.add(BoxCollider(0, 0, 1.5, 2.0, hx=1, hy=1))
    assert not world.is_free(0, 0, 0.3, 0.0, 1.8)
    assert world.is_free(0, 0, 0.3, 0.0, 1.4)
    assert world.is_free(3, 0, 0.3, 0.0, 1.8)
