"""Campaign progress saved as JSON (completed / unlocked missions, current mission, best stats).

A missing file means a new player. A corrupted file is backed up as progress.json.corrupt
and replaced with a fresh save, so the game always starts.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)
SAVE_VERSION = 1


@dataclass
class Progress:
    completed: list = field(default_factory=list)
    unlocked: list = field(default_factory=list)
    current_mission: str | None = None
    stats: dict = field(default_factory=dict)       # mission id -> {"best_time", "kills", "accuracy", ...}

    def to_dict(self):
        return {"version": SAVE_VERSION, "completed": self.completed, "unlocked": self.unlocked,
                "current_mission": self.current_mission, "stats": self.stats}

    @classmethod
    def from_dict(cls, data, valid_ids=None):
        p = cls()
        if not isinstance(data, dict):
            return p

        def ids(value):
            if not isinstance(value, list):
                return []
            out = [v for v in value if isinstance(v, str) and (valid_ids is None or v in valid_ids)]
            return list(dict.fromkeys(out))

        p.completed = ids(data.get("completed"))
        p.unlocked = ids(data.get("unlocked"))
        cur = data.get("current_mission")
        p.current_mission = cur if isinstance(cur, str) and (valid_ids is None or cur in valid_ids) else None
        stats = data.get("stats")
        if isinstance(stats, dict):
            p.stats = {k: v for k, v in stats.items() if isinstance(v, dict) and (valid_ids is None or k in valid_ids)}
        return p

    @property
    def has_progress(self):
        return bool(self.completed or self.current_mission)


class SaveManager:
    def __init__(self, path, mission_order, first_unlocked=None):
        self.path = Path(path)
        self.order = list(mission_order)
        self.first = first_unlocked or (self.order[0] if self.order else None)
        self.progress = self.load()

    def load(self):
        valid = set(self.order)
        if not self.path.exists():
            return self._fresh()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("save file is not a JSON object")
        except (OSError, ValueError) as exc:
            log.warning("Save file %s is unreadable (%s) - starting a new campaign save.", self.path, exc)
            try:
                os.replace(self.path, self.path.with_name(self.path.name + ".corrupt"))
            except OSError:
                pass
            p = self._fresh()
            self.progress = p
            self.save()
            return p
        p = Progress.from_dict(data, valid)
        if self.first and self.first not in p.unlocked:
            p.unlocked.insert(0, self.first)
        return p

    def _fresh(self):
        return Progress(unlocked=[self.first] if self.first else [])

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(self.progress.to_dict(), indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError as exc:
            log.error("Could not save progress: %s", exc)
            return False

    # ------------------------------------------------------------------ campaign events
    def is_unlocked(self, mission_id):
        return mission_id in self.progress.unlocked

    def start_mission(self, mission_id):
        self.progress.current_mission = mission_id
        self.save()

    def complete_mission(self, mission_id, stats=None):
        p = self.progress
        if mission_id not in p.completed:
            p.completed.append(mission_id)
        if stats:
            old = p.stats.get(mission_id, {})
            best = dict(stats)
            if "time" in old and "time" in stats:
                best["best_time"] = min(old.get("best_time", old["time"]), stats["time"])
            else:
                best["best_time"] = stats.get("time")
            if "rank" in stats or "best_rank" in old:
                from missions.ranking import better
                best["best_rank"] = better(old.get("best_rank"), stats.get("rank"))
            if "intel_ids" in stats or "intel_ids" in old:
                found = set(old.get("intel_ids", [])) | set(stats.get("intel_ids", []))
                best["intel_ids"] = sorted(found)
            p.stats[mission_id] = best
        nxt = self.next_mission(mission_id)
        if nxt and nxt not in p.unlocked:
            p.unlocked.append(nxt)
        p.current_mission = nxt
        self.save()
        return nxt

    def next_mission(self, mission_id):
        if mission_id not in self.order:
            return None
        i = self.order.index(mission_id)
        return self.order[i + 1] if i + 1 < len(self.order) else None

    def reset(self):
        self.progress = self._fresh()
        self.save()
