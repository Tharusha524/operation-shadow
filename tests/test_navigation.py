import math

from systems.collision_system import BoxCollider, CollisionWorld
from systems.navigation import NavGrid


def make_world():
    world = CollisionWorld()
    # A wall from x=-5..5 at y=0 with no gap: paths must go around it.
    world.add(BoxCollider(0, 0, 0, 3, hx=5, hy=0.3))
    # A low sandbag wall (cover) at y=8.
    world.add(BoxCollider(0, 8, 0, 1.1, hx=2, hy=0.3))
    return world


def test_walkable_cells():
    nav = NavGrid(make_world(), (-15, -15, 15, 15))
    assert not nav.is_walkable(0, 0)
    assert nav.is_walkable(0, -5)
    assert nav.is_walkable(10, 0)


def test_path_goes_around_wall():
    nav = NavGrid(make_world(), (-15, -15, 15, 15))
    path = nav.find_path((0, -5), (0, 5))
    assert path is not None and len(path) >= 2
    assert math.dist(path[-1], (0.5, 5.5)) < 1.5
    pts = [(0, -5)] + path
    for a, b in zip(pts, pts[1:]):
        assert nav.line_walkable(a[0], a[1], b[0], b[1])
    assert any(abs(p[0]) > 5 for p in path)          # had to walk round the end of the wall


def test_unreachable_goal_returns_none():
    world = CollisionWorld()
    for x0, y0, x1, y1 in ((-4, -4, 4, -3), (-4, 3, 4, 4), (-4, -4, -3, 4), (3, -4, 4, 4)):
        world.add(BoxCollider((x0 + x1) / 2, (y0 + y1) / 2, 0, 3, (x1 - x0) / 2, (y1 - y0) / 2))
    nav = NavGrid(world, (-10, -10, 10, 10))
    assert nav.find_path((-8, -8), (0, 0)) is None


def test_cover_points_and_find_cover():
    nav = NavGrid(make_world(), (-15, -15, 15, 15))
    assert nav.cover_points
    # Threat north of the sandbags: good cover is on the south side of them.
    cover = nav.find_cover(0, 3, threat=(0, 14, 1.6))
    assert cover is not None
    assert cover[1] < 8 and abs(cover[0]) <= 2.5


def test_rebuild_after_wall_removed():
    world = make_world()
    world.add(BoxCollider(0, -10, 0, 3, hx=1, hy=1, tag="gate"))
    nav = NavGrid(world, (-15, -15, 15, 15))
    assert not nav.is_walkable(0, -10)
    world.remove_tag("gate")
    nav.rebuild((-2, -12, 2, -8))
    assert nav.is_walkable(0, -10)
