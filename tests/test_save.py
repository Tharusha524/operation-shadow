import json

from systems.save_manager import SaveManager

ORDER = ["m01", "m02", "m03"]


def test_new_save_unlocks_first_mission(tmp_path):
    sm = SaveManager(tmp_path / "progress.json", ORDER)
    assert sm.progress.unlocked == ["m01"]
    assert not sm.progress.has_progress


def test_complete_mission_unlocks_next_and_persists(tmp_path):
    path = tmp_path / "progress.json"
    sm = SaveManager(path, ORDER)
    nxt = sm.complete_mission("m01", {"time": 300.0, "kills": 14})
    assert nxt == "m02"
    again = SaveManager(path, ORDER)
    assert again.progress.completed == ["m01"]
    assert again.is_unlocked("m02") and not again.is_unlocked("m03")
    assert again.progress.current_mission == "m02"
    assert again.progress.stats["m01"]["best_time"] == 300.0


def test_best_time_is_kept(tmp_path):
    sm = SaveManager(tmp_path / "progress.json", ORDER)
    sm.complete_mission("m01", {"time": 300.0})
    sm.complete_mission("m01", {"time": 400.0})
    assert sm.progress.stats["m01"]["best_time"] == 300.0
    sm.complete_mission("m01", {"time": 250.0})
    assert sm.progress.stats["m01"]["best_time"] == 250.0


def test_corrupted_save_is_backed_up_and_replaced(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text("{{{ broken", encoding="utf-8")
    sm = SaveManager(path, ORDER)
    assert sm.progress.unlocked == ["m01"]
    assert (tmp_path / "progress.json.corrupt").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["unlocked"] == ["m01"]


def test_unknown_or_bad_entries_are_dropped(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text(json.dumps({"completed": ["m01", "hack", 5], "unlocked": "nope",
                                "current_mission": "zzz", "stats": {"m01": {"kills": 3}, "x": 1}}), encoding="utf-8")
    sm = SaveManager(path, ORDER)
    assert sm.progress.completed == ["m01"]
    assert sm.progress.unlocked == ["m01"]
    assert sm.progress.current_mission is None
    assert sm.progress.stats == {"m01": {"kills": 3}}


def test_reset(tmp_path):
    sm = SaveManager(tmp_path / "progress.json", ORDER)
    sm.complete_mission("m01")
    sm.reset()
    assert sm.progress.completed == [] and sm.progress.unlocked == ["m01"]
