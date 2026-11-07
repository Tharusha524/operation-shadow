import json

from config.settings import Settings, SettingsStore
from player.camera import LookAngles
from config import constants as C


def test_missing_file_creates_defaults(tmp_path):
    path = tmp_path / "settings.json"
    s = SettingsStore(path).load()
    assert s == Settings()
    assert path.exists()


def test_save_and_load_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    s = Settings(mouse_sensitivity=2.5, graphics_quality="high", resolution=(1920, 1080), fullscreen=True)
    assert store.save(s)
    loaded = store.load()
    assert loaded == s


def test_corrupted_file_is_backed_up_and_defaults_used(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")
    s = SettingsStore(path).load()
    assert s == Settings()
    assert (tmp_path / "settings.json.corrupt").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["graphics_quality"] == "medium"


def test_bad_values_are_clamped_or_replaced(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "mouse_sensitivity": 99, "master_volume": -3, "graphics_quality": "ultra",
        "resolution": [10, 10], "fullscreen": "yes", "field_of_view": "wide", "show_fps": True,
    }), encoding="utf-8")
    s = SettingsStore(path).load()
    assert s.mouse_sensitivity == 5.0
    assert s.master_volume == 0.0
    assert s.graphics_quality == "medium"
    assert s.resolution == (1280, 720)
    assert s.fullscreen is False
    assert s.field_of_view == 90.0
    assert s.show_fps is True


def test_mouse_look_maths():
    look = LookAngles()
    look.apply_mouse(100, 0)
    assert abs(look.yaw - (-100 * C.MOUSE_DEGREES_PER_PIXEL)) < 1e-9     # mouse right = turn right
    look.apply_mouse(0, -100)
    assert look.pitch > 0                                               # mouse up = look up
    look.apply_mouse(0, -1e6)
    assert look.pitch == C.PITCH_LIMIT
    inv = LookAngles()
    inv.apply_mouse(0, -100, invert_y=True)
    assert inv.pitch < 0
    wrap = LookAngles(yaw=179.0)
    wrap.apply_mouse(-100, 0)
    assert -180.0 <= wrap.yaw < 180.0
