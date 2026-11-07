"""Campaign, character and mission definitions loaded from data/*.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.paths import DATA_DIR

MISSIONS_DIR = DATA_DIR / "missions"


class MissionDataError(Exception):
    pass


@dataclass
class Character:
    id: str
    name: str
    short: str
    faction: str
    role: str
    bio: str
    playable: bool = False


@dataclass
class MissionInfo:
    id: str
    number: int
    act: str
    title: str
    character: str
    location: str
    type: str
    summary: str
    file: str | None

    @property
    def playable(self):
        return bool(self.file) and (MISSIONS_DIR / self.file).is_file()


@dataclass
class Campaign:
    title: str
    subtitle: str
    premise: str
    acts: list
    missions: list
    characters: dict = field(default_factory=dict)

    @property
    def order(self):
        return [m.id for m in self.missions]

    def mission(self, mission_id):
        for m in self.missions:
            if m.id == mission_id:
                return m
        return None

    def act_title(self, act_id):
        for a in self.acts:
            if a["id"] == act_id:
                return a["title"]
        return act_id

    def speaker_name(self, speaker_id):
        c = self.characters.get(speaker_id)
        return c.name if c else speaker_id


def load_characters(path=DATA_DIR / "characters.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for cid, c in data["characters"].items():
        out[cid] = Character(cid, c["name"], c.get("short", c["name"]), c.get("faction", ""), c.get("role", ""),
                             c.get("bio", ""), bool(c.get("playable", False)))
    return out


def load_campaign(path=DATA_DIR / "campaign.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missions = [MissionInfo(**{k: m.get(k) for k in MissionInfo.__dataclass_fields__}) for m in data["missions"]]
    ids = [m.id for m in missions]
    if len(ids) != len(set(ids)):
        raise MissionDataError("duplicate mission ids in campaign.json")
    return Campaign(data["title"], data.get("subtitle", ""), data.get("premise", ""), data["acts"], missions,
                    load_characters())


def load_mission(info: MissionInfo) -> dict:
    """Read a playable mission definition (data/missions/<file>)."""
    if not info.playable:
        raise MissionDataError(f"Mission '{info.title}' is not playable yet")
    try:
        data = json.loads((MISSIONS_DIR / info.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MissionDataError(f"Could not read mission file {info.file}: {exc}") from None
    for key in ("map", "player", "steps"):
        if key not in data:
            raise MissionDataError(f"Mission file {info.file} is missing '{key}'")
    return data
