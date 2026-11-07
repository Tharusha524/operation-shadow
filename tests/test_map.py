import random

import pytest

from config import constants as C
from core.paths import MAPS_DIR
from environments.geometry import MeshBuilder
from environments.map_loader import MapLoadError, expand_scatter, load_map, parse_map
from environments.materials import MaterialLibrary
from environments.props import PROP_BUILDERS
from systems.collision_system import CollisionWorld

MAP_FILE = MAPS_DIR / "border_outpost.json"


@pytest.fixture(scope="module")
def outpost():
    return load_map(MAP_FILE)


@pytest.fixture(scope="module")
def outpost_world(outpost):
    mb = MeshBuilder(MaterialLibrary.uv_scales())
    for i, prop in enumerate(outpost.props):
        rng = random.Random(outpost.seed * 1000003 + i)
        with mb.place(prop.x, prop.y, prop.z, prop.heading):
            PROP_BUILDERS[prop.type](mb, rng, **prop.params)
    world = CollisionWorld()
    world.add_many(mb.colliders)
    return world, mb


@pytest.mark.parametrize("name", sorted(PROP_BUILDERS))
def test_every_prop_builds_with_defaults(name):
    mb = MeshBuilder(MaterialLibrary.uv_scales())
    with mb.place(5, 5, 0, 30):
        PROP_BUILDERS[name](mb, random.Random(1))
    assert mb.vertex_count > 0 or (name == "invisible_wall" and mb.colliders)


def test_map_loads_and_uses_known_props(outpost):
    unknown = {p.type for p in outpost.props} - set(PROP_BUILDERS)
    assert not unknown
    assert len(outpost.props) > 300


def test_whole_map_builds(outpost_world):
    world, mb = outpost_world
    assert len(world) > 500
    assert mb.triangle_count > 50_000


def _standing_free(world, p):
    return world.is_free(p.x, p.y, C.PLAYER_RADIUS, p.z + C.STEP_HEIGHT, p.z + C.PLAYER_STAND_HEIGHT)


def test_spawn_and_test_points_are_not_inside_walls(outpost, outpost_world):
    world, _ = outpost_world
    assert _standing_free(world, outpost.player_spawn)
    for name, point in outpost.points.items():
        assert _standing_free(world, point), name


def test_perimeter_is_closed(outpost_world):
    """Walking outward in every direction from the centre must hit a wall before leaving the base."""
    world, _ = outpost_world
    import math
    for deg in range(0, 360, 5):
        dx, dy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        blocked = False
        for step in range(0, 400):
            d = step * 0.25
            x, y = dx * d, dy * d
            if not world.is_free(x, y, 0.1, 0.5, 1.7):
                blocked = True
                break
            if abs(x) > 72 or abs(y) > 72:
                break
        assert blocked, f"escape route at {deg} degrees"


def test_scatter_is_deterministic_and_respects_exclusion():
    rule = {"type": "rock", "count": 40, "area": [-50, -50, 50, 50], "exclude": [[-20, -20, 20, 20]],
            "min_spacing": 3, "params": {"size": [1, 2]}}
    a = expand_scatter(rule, random.Random(5))
    b = expand_scatter(rule, random.Random(5))
    assert [(p.x, p.y) for p in a] == [(p.x, p.y) for p in b]
    assert len(a) == 40
    for p in a:
        assert not (-20 <= p.x <= 20 and -20 <= p.y <= 20)
        assert 1 <= p.params["size"] <= 2


def test_invalid_maps_raise_readable_errors(tmp_path):
    with pytest.raises(MapLoadError):
        parse_map({"props": []})                       # no player_spawn
    with pytest.raises(MapLoadError):
        parse_map({"player_spawn": {"pos": ["x", 0]}})
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(MapLoadError):
        load_map(bad)
    with pytest.raises(MapLoadError):
        load_map(tmp_path / "missing.json")


# ---------------------------------------------------------------- every map
ALL_MAPS = sorted(p.stem for p in MAPS_DIR.glob("*.json"))


def _build(map_data):
    mb = MeshBuilder(MaterialLibrary.uv_scales())
    for i, prop in enumerate(map_data.props):
        with mb.place(prop.x, prop.y, prop.z, prop.heading):
            PROP_BUILDERS[prop.type](mb, random.Random(map_data.seed * 1000003 + i), **prop.params)
    world = CollisionWorld()
    world.add_many(mb.colliders)
    return world


@pytest.mark.parametrize("name", ALL_MAPS)
def test_every_map_builds_with_free_spawn_points(name):
    data = load_map(MAPS_DIR / f"{name}.json")
    assert not ({p.type for p in data.props} - set(PROP_BUILDERS))
    world = _build(data)
    assert _standing_free(world, data.player_spawn)
    for pname, point in data.points.items():
        assert _standing_free(world, point), pname


def test_kesh_ridge_routes_are_walkable():
    from systems.navigation import NavGrid
    data = load_map(MAPS_DIR / "kesh_ridge.json")
    world = _build(data)
    nav = NavGrid(world, tuple(data.terrain["nav_bounds"]))
    routes = [((-30, -31), (0, 0.4)), ((0, 116), (0, 0.4)), ((0, 0.4), (18, 58)),
              ((0, 0.4), (-12, -41)), ((-12, -41), (24, -76)), ((-40, 114), (-30, -41))]
    for a, b in routes:
        assert nav.find_path(a, b) is not None, (a, b)
