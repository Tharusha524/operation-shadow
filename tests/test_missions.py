import math

import pytest

from missions.mission_data import load_campaign, load_mission
from missions.mission_manager import COMPLETE, FAILED, MissionRunner

KNOWN_ACTIONS = {"radio", "spawn", "squad_hold", "squad_follow", "destroy_prop", "explosion", "loop_start",
                 "loop_stop", "smoke", "checkpoint", "notice", "sound", "refill_ammo", "complete_mission",
                 "spawn_friendly", "barrage", "squad_leader", "squad_invulnerable", "spawn_vehicle", "remove_vehicle",
                 "vehicle_command", "start_ride", "end_ride", "drone_start", "drone_end", "show_prop", "hide_prop",
                 "collapse_bridge", "flare", "give_weapon", "set_visibility", "nvg", "alarm_arm", "alarm_disarm",
                 "raise_alarm", "fail_mission", "spawn_camera", "spawn_squad", "set_captive",
                 "give_grenades", "kill_group", "cancel_barrage"}
OBJECTIVE_TYPES = ("reach", "interact", "eliminate", "survive", "escort", "ride", "tag", "destroy", "vehicles_arrive",
                   "interact_multi", "photograph", "download", "rescue")


class FakeCtx:
    def __init__(self):
        self.pos = [0.0, 0.0, 0.0]
        self.heading = 0.0
        self.looking = True
        self.interact = False
        self.groups = {}           # group -> [alive flags]
        self.log = []
        self.objectives = None
        self.marker = None
        self.prompt = None
        self.completed = False
        self.failed = None
        self.destroyed = set()
        self.dead = set()
        self.squad_pos = {}
        self.shown = set()
        self.vehicles = {}         # id -> destroyed?
        self.ride_done = False
        self.tags = 0
        self.alarm = False
        self.points = []
        self.cameras = []
        self.photo = None
        self.executed = []
        self.alerted = set()

    # queries
    def player_position(self): return tuple(self.pos)
    def player_eye_position(self): return (self.pos[0], self.pos[1], self.pos[2] + 1.68)
    def player_heading(self): return self.heading
    def player_looking_at(self, pos, deg): return self.looking
    def interact_held(self): return self.interact
    def group_total(self, g): return len(self.groups.get(g, []))
    def group_alive(self, g): return sum(self.groups.get(g, []))

    # outputs
    def set_objectives(self, title, lines): self.objectives = (title, lines)
    def set_marker(self, m): self.marker = m
    def set_prompt(self, text, progress=None): self.prompt = text
    def on_new_objective(self, text): self.log.append(("objective", text))
    def on_checkpoint(self, cp): self.log.append(("checkpoint", cp["step"]))
    def radio(self, speaker, text, seconds): self.log.append(("radio", speaker))
    def spawn_enemy(self, group, unit): self.groups.setdefault(group, []).append(True)
    def spawn_friendly(self, group, unit): self.log.append(("friendly", group))
    def barrage(self, area, count, seconds, radius, damage): self.log.append(("barrage", count))
    def squad_leader(self, member, leader): self.log.append(("leader", member, leader))
    def squad_invulnerable(self, member, value): self.log.append(("invuln", member, value))
    def escort_start(self, target, route): self.log.append(("escort", target))
    def squad_alive(self, member): return member not in self.dead
    def squad_position(self, member): return self.squad_pos.get(member)
    def squad_hold(self, member, pos): self.log.append(("hold", member))
    def squad_follow(self, member): self.log.append(("follow", member))
    def destroy_prop(self, pid, explode): self.destroyed.add(pid)
    def restore_prop(self, pid): self.destroyed.discard(pid)
    def explosion(self, pos): self.log.append(("boom",))
    def loop(self, name, on, volume=0.5): self.log.append(("loop", name, on))
    def add_smoke(self, pos, seconds): pass
    def notice(self, text): self.log.append(("notice", text))
    def play_sound(self, name): pass
    def refill_ammo(self): self.log.append(("ammo",))
    def clear_enemies(self): self.groups = {}
    def restore_world(self, groups, cameras): self.log.append(("restore", tuple(sorted(groups)), tuple(sorted(cameras))))
    def restore_player(self, placement): self.pos = list(placement["pos"])
    def mission_complete(self): self.completed = True
    def mission_failed(self, reason): self.failed = reason

    # vehicles, rides, drone, stealth
    def spawn_vehicle(self, a): self.vehicles[a["id"]] = False
    def remove_vehicle(self, vid): self.vehicles.pop(vid, None)
    def vehicle_command(self, *args): self.log.append(("vcmd", args[0]))
    def vehicle_destroyed(self, vid): return self.vehicles.get(vid, False)
    def vehicle_position(self, vid): return (0.0, 0.0, 0.0) if vid in self.vehicles else None
    def vehicle_arrived(self, vid): return vid in self.vehicles and self.ride_done
    def start_ride(self, vid, seat, squad, drive=False, breakable=()): self.log.append(("ride", vid))
    def end_ride(self, pos=None, heading=None, squad=None): self.log.append(("end_ride",))
    def ride_finished(self): return self.ride_done
    def drone_start(self, pos, heading, max_range): self.log.append(("drone",))
    def drone_end(self): self.log.append(("drone_end",))
    def tagged_count(self): return self.tags
    def alarm_triggered(self, groups): return self.alarm
    def point_done(self, spec, pos): self.points.append(tuple(pos))
    def show_prop(self, pid): self.shown.add(pid); self.destroyed.discard(pid)
    def collapse_bridge(self, blasts, vehicles): self.log.append(("collapse", tuple(vehicles)))
    def flare(self, pos, seconds): self.log.append(("flare",))
    def give_weapon(self, wid, ammo=None): self.log.append(("give", wid))
    def set_visibility(self, value, lit): self.log.append(("vis", value))
    def enable_nvg(self, available, on): self.log.append(("nvg", available))
    # cameras, photos, hostages
    def spawn_camera(self, a): self.cameras.append(a["id"])
    def give_grenades(self, kind, count): self.log.append(("grenades", kind, count))
    def kill_group(self, group, count, sound=None): self.log.append(("killgroup", group, count))
    def cancel_barrage(self): self.log.append(("cancel",))
    def spawn_squad(self, a): self.squad_pos[a["id"]] = tuple(a["pos"]) + (0.0,)
    def set_captive(self, member, value): self.log.append(("captive", member, value))
    def photo_target(self, group, angle, rng): return self.photo
    def photo_taken(self, n, total): self.log.append(("photo", n))
    def group_members(self, g): return [(i, (0.0, 0.0, 0.0), a) for i, a in enumerate(self.groups.get(g, []))]
    def group_alerted(self, g): return g in self.alerted
    def execute_hostage(self, hostage, group): self.executed.append(hostage); self.dead.add(hostage)
    def download_started(self, spec): self.log.append(("download",))


def tick(runner, seconds, dt=0.1):
    for _ in range(int(seconds / dt)):
        runner.update(dt)


def kill_group(ctx, g):
    ctx.groups[g] = [False] * len(ctx.groups.get(g, []))


SIMPLE = {
    "map": "x", "player": {},
    "steps": [
        {"objective": {"type": "reach", "pos": [10, 0, 0], "radius": 2, "text": "Go"},
         "on_start": [{"action": "radio", "speaker": "marek", "text": "go", "delay": 1.0}],
         "on_complete": [{"action": "checkpoint", "pos": [10, 0, 0]}]},
        {"objective": {"type": "eliminate", "group": "w1", "text": "Kill"},
         "on_start": [{"action": "spawn", "group": "w1", "units": [{"pos": [0, 9]}, {"pos": [1, 9]}]},
                      {"action": "destroy_prop", "id": "fence"}]},
        {"objective": {"type": "interact", "pos": [0, 0, 1.68], "radius": 2, "hold": 1.0, "text": "Use"}},
    ],
}


def test_runner_flow_reach_eliminate_interact_complete():
    ctx = FakeCtx()
    r = MissionRunner(ctx, SIMPLE)
    r.start()
    assert ctx.objectives == ("OBJECTIVE", ["Go"]) and ctx.marker == (10, 0, 0)
    tick(r, 1.2)
    assert ("radio", "marek") in ctx.log                  # delayed action ran
    ctx.pos = [10, 0, 0]
    tick(r, 0.2)
    assert r.index == 1 and ("checkpoint", 1) in ctx.log
    assert ctx.objectives[1] == ["Kill (0/2)"]
    ctx.groups["w1"][0] = False
    tick(r, 0.2)
    assert ctx.objectives[1] == ["Kill (1/2)"]
    kill_group(ctx, "w1")
    tick(r, 0.2)
    assert r.index == 2
    ctx.pos = [0, 0, 0]
    tick(r, 0.5)
    assert ctx.prompt is not None and not ctx.completed     # in range but E not held
    ctx.interact = True
    tick(r, 1.3)
    assert ctx.completed and r.state == COMPLETE


def test_checkpoint_restart_respawns_enemies_and_restores_props():
    ctx = FakeCtx()
    r = MissionRunner(ctx, SIMPLE)
    r.start()
    ctx.pos = [10, 0, 0]
    tick(r, 0.2)
    assert "fence" in ctx.destroyed and ctx.group_total("w1") == 2
    ctx.groups["w1"][0] = False
    r.fail("killed")
    assert r.state == FAILED and ctx.failed == "killed"
    ctx.pos = [50, 50, 0]
    assert r.restart_from_checkpoint()
    assert r.state == "running" and r.index == 1
    assert ctx.pos == [10, 0, 0]
    assert ctx.group_total("w1") == 2 and ctx.group_alive("w1") == 2      # fresh wave
    assert "fence" in ctx.destroyed                                       # destroyed again by step on_start


def test_campaign_has_16_missions_and_first_is_playable():
    c = load_campaign()
    assert len(c.missions) == 16
    assert c.missions[0].playable
    assert [m.number for m in c.missions] == list(range(1, 17))
    assert {m.character for m in c.missions} <= set(c.characters)
    assert sum(1 for m in c.missions if m.playable) >= 1


PLAYABLE = [m for m in load_campaign().missions if m.playable]


@pytest.mark.parametrize("info", PLAYABLE, ids=lambda m: m.id)
def test_mission_file_is_valid(info):
    c = load_campaign()
    data = load_mission(info)
    groups_spawned, groups_needed = set(), set()
    for step in data["steps"]:
        assert step["objective"]["type"] in OBJECTIVE_TYPES
        if step["objective"]["type"] == "eliminate":
            groups_needed.add(step["objective"]["group"])
        for a in step.get("on_start", []) + step.get("on_complete", []):
            assert a["action"] in KNOWN_ACTIONS, a
            if a["action"] == "spawn":
                groups_spawned.add(a["group"])
            if a["action"] == "radio":
                assert a["speaker"] in c.characters
    assert groups_needed <= groups_spawned
    for s in data["squad"]:
        assert s["id"] in c.characters


@pytest.mark.parametrize("info", PLAYABLE, ids=lambda m: m.id)
def test_mission_runs_to_completion_with_fake_game(info):
    data = load_mission(info)
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    ctx.interact = True
    for _ in range(len(data["steps"]) * 2 + 2):
        if r.state != "running":
            break
        obj = r.objective.spec
        if obj["type"] in ("reach", "interact"):
            ctx.pos = list(obj["pos"][:2]) + [obj["pos"][2] - 1.68 if obj["type"] == "interact" else 0.0]
            if obj["type"] == "reach":
                ctx.pos[2] = obj["pos"][2] if len(obj["pos"]) > 2 else 0.0       # e.g. a rooftop
        if obj["type"] == "escort":
            end = obj["route"][-1]
            ctx.squad_pos[obj["target"]] = (end[0], end[1], 0.0)
        if obj["type"] in ("ride", "vehicles_arrive"):
            ctx.ride_done = True
        if obj["type"] == "tag":
            ctx.tags = obj["count"]
        if obj["type"] == "destroy":
            tick(r, 15.0)                                   # let delayed spawns happen first
            for t in obj["targets"]:
                ctx.vehicles[t] = True
        if obj["type"] == "photograph":
            for i in range(obj["count"]):
                ctx.photo = i
                tick(r, obj.get("hold", 0.8) + 0.3)
            ctx.photo = None
        if obj["type"] == "download":
            ctx.pos = [obj["pos"][0], obj["pos"][1], obj["pos"][2] - 1.68]
            tick(r, 2.0)
            tick(r, obj["seconds"] + 1)
        if obj["type"] == "rescue":
            tick(r, 1.0)
            kill_group(ctx, obj["group"])
        if obj["type"] == "interact_multi":
            for p in obj["points"]:
                ctx.pos = [p[0], p[1], p[2] - 1.68]
                tick(r, obj.get("hold", 2.0) + 0.5)
        tick(r, 12.0 if obj["type"] != "survive" else obj["seconds"] + 1)
        if obj["type"] == "eliminate":
            kill_group(ctx, obj["group"])
            tick(r, 0.5)
    assert ctx.completed
    if info.id == "m01_first_light":
        assert {"north_breach", "main_gate"} <= ctx.destroyed


def test_mission_two_is_playable_and_has_checkpoint_safe_spawns():
    """Every eliminate step must (re)spawn its own group, so 'retry from checkpoint' works."""
    for info in PLAYABLE:
        data = load_mission(info)
        for step in data["steps"]:
            if step["objective"]["type"] == "eliminate":
                spawned_here = {a["group"] for a in step.get("on_start", []) if a["action"] == "spawn"}
                previous = data["steps"][data["steps"].index(step) - 1]
                checkpoint_before = any(a["action"] == "checkpoint" for a in previous.get("on_complete", []))
                if checkpoint_before:
                    assert step["objective"]["group"] in spawned_here, (info.id, step["id"])


def test_protected_squad_member_death_fails_mission():
    data = {"map": "x", "player": {}, "protect": [{"id": "kell", "message": "Kell died"}],
            "steps": [{"objective": {"type": "escort", "target": "kell", "route": [[0, 0], [10, 0]], "text": "Go"}}]}
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    ctx.squad_pos["kell"] = (5.0, 0.0, 0.0)
    tick(r, 0.5)
    assert r.state == "running" and ctx.marker[:2] == (5.0, 0.0)          # marker follows the escorted soldier
    ctx.dead.add("kell")
    tick(r, 0.2)
    assert r.state == FAILED and ctx.failed == "Kell died"


def test_rescue_executes_hostage_if_captors_are_alerted_too_long():
    data = {"map": "x", "player": {}, "protect": [{"id": "brandt", "message": "dead"}], "steps": [
        {"objective": {"type": "rescue", "group": "captors", "hostage": "brandt", "seconds": 3, "text": "Save him"},
         "on_start": [{"action": "spawn", "group": "captors", "units": [{"pos": [0, 0]}, {"pos": [1, 0]}]}]}]}
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    tick(r, 5.0)
    assert r.state == "running" and not ctx.executed            # calm captors never execute
    ctx.alerted.add("captors")
    tick(r, 1.0)
    assert "s!)" in ctx.objectives[1][0]                        # countdown shown
    tick(r, 3.0)
    assert ctx.executed == ["brandt"] and r.state == FAILED and ctx.failed == "dead"


def test_rescue_succeeds_when_captors_die_in_time():
    data = {"map": "x", "player": {}, "steps": [
        {"objective": {"type": "rescue", "group": "captors", "hostage": "brandt", "seconds": 3, "text": "Save him"},
         "on_start": [{"action": "spawn", "group": "captors", "units": [{"pos": [0, 0]}]}]}]}
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    ctx.alerted.add("captors")
    tick(r, 1.0)
    kill_group(ctx, "captors")
    tick(r, 0.2)
    assert r.state == COMPLETE and not ctx.executed


def test_download_pauses_when_the_player_walks_away():
    data = {"map": "x", "player": {}, "steps": [
        {"objective": {"type": "download", "pos": [0, 0, 1.0], "seconds": 10, "radius": 5, "text": "Copy"}}]}
    ctx = FakeCtx()
    ctx.interact = True
    r = MissionRunner(ctx, data)
    r.start()
    tick(r, 1.5)
    assert ("download",) in ctx.log
    tick(r, 5.0)
    assert "%" in ctx.objectives[1][0]
    ctx.pos = [30, 0, 0]
    tick(r, 20.0)
    assert r.state == "running"                                # paused far away
    ctx.pos = [1, 0, 0]
    tick(r, 6.0)
    assert r.state == COMPLETE


def test_photograph_counts_each_officer_once():
    data = {"map": "x", "player": {}, "steps": [
        {"objective": {"type": "photograph", "group": "o", "count": 2, "text": "Photo"},
         "on_start": [{"action": "spawn", "group": "o", "units": [{"pos": [0, 0]}, {"pos": [1, 0]}]}]}]}
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    ctx.photo = 0
    tick(r, 2.0)
    assert ctx.log.count(("photo", 1)) == 1 and r.state == "running"
    ctx.photo = None
    tick(r, 0.2)
    ctx.photo = 1
    tick(r, 1.0)
    assert r.state == COMPLETE


def test_checkpoint_restores_world_but_not_what_the_step_spawns_itself():
    data = {"map": "x", "player": {}, "steps": [
        {"objective": {"type": "reach", "pos": [0, 0, 0], "text": "a"},
         "on_start": [{"action": "spawn", "group": "old", "units": [{"pos": [1, 1]}]}],
         "on_complete": [{"action": "checkpoint", "pos": [0, 0, 0]}]},
        {"objective": {"type": "reach", "pos": [50, 0, 0], "text": "b"},
         "on_start": [{"action": "spawn", "group": "new", "units": [{"pos": [2, 2]}]},
                      {"action": "spawn_camera", "id": "cam1", "pos": [0, 0, 3]}]},
    ]}
    ctx = FakeCtx()
    r = MissionRunner(ctx, data)
    r.start()
    tick(r, 0.2)
    assert r.index == 1
    assert r.restart_from_checkpoint()
    assert ("restore", ("new",), ("cam1",)) in ctx.log
    assert len(ctx.groups["new"]) == 1
