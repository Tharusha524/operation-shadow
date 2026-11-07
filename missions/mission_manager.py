"""Runs a mission: steps, objectives, scripted actions, checkpoints, completion and failure.

The runner talks to the game only through a small "context" object (see GameMissionContext
in core/game.py), so the mission logic can be unit tested without a window.

Mission file format (data/missions/*.json), each step:
  {"id": "...", "objective": {...}, "on_start": [actions], "on_complete": [actions]}
Every action is a dict with an "action" name and an optional "delay" in seconds.
"""
from __future__ import annotations

import logging

from missions.objectives import EliminateGroup, make_objective

log = logging.getLogger(__name__)

RUNNING, COMPLETE, FAILED = "running", "complete", "failed"


class MissionRunner:
    def __init__(self, ctx, data, title=""):
        self.ctx = ctx
        self.data = data
        self.title = title
        self.steps = data["steps"]
        self.index = -1
        self.objective = None
        self.timers = []
        self.time = 0.0
        self.state = RUNNING
        self.checkpoint = None
        self.destroyed = []            # (prop id, step index)
        self.shown = []                # hidden props made visible: (prop id, step index)
        self.deaths = 0
        self.alarm = data.get("alarm")             # {"groups": [...], "actions": [...]} or None
        self.alarm_armed = False
        self.alarm_raised = False
        self.completed_objectives = []
        self._completing = False

    # ------------------------------------------------------------------ flow
    def start(self):
        self._enter_step(0)

    def _enter_step(self, i):
        self.index = i
        step = self.steps[i]
        self.objective = make_objective(step["objective"])
        for action in step.get("on_start", []):
            self._schedule(action)
        self.objective.start(self.ctx)
        self.ctx.on_new_objective(self.objective.text)
        self._refresh()

    def _complete_step(self):
        step = self.steps[self.index]
        self.objective.finish(self.ctx)
        self.completed_objectives.append(self.objective.text)
        self._completing = True
        for action in step.get("on_complete", []):
            self._schedule(action)
        self._completing = False
        if self.index + 1 < len(self.steps):
            self._enter_step(self.index + 1)
        else:
            self.objective = None
            if not any(a.get("action") == "complete_mission" for _, a in self.timers):
                self.finish()

    def finish(self):
        if self.state == RUNNING:
            self.state = COMPLETE
            self.ctx.set_marker(None)
            self.ctx.mission_complete()

    def fail(self, reason):
        if self.state == RUNNING:
            self.state = FAILED
            self.deaths += 1
            self.ctx.mission_failed(reason)

    def update(self, dt):
        if self.state != RUNNING:
            return
        self.time += dt
        due = []
        for timer in self.timers:
            timer[0] -= dt
            if timer[0] <= 0.0:
                due.append(timer)
        for timer in due:
            self.timers.remove(timer)
            self._run(timer[1])
        if self.state != RUNNING:
            return
        for p in self.data.get("protect", []):            # e.g. the wounded Kell must survive
            if not self.ctx.squad_alive(p["id"]):
                self.fail(p.get("message", "A squad member was killed."))
                return
        if self.alarm and self.alarm_armed and not self.alarm_raised and                 self.ctx.alarm_triggered(self.alarm.get("groups", [])):
            self.raise_alarm()
        if self.objective is not None and self.objective.update(self.ctx, dt):
            self._complete_step()
        self._refresh()

    def raise_alarm(self):
        """Stealth is broken: run the mission's alarm actions once (reinforcements, siren ...)."""
        if self.alarm_raised or not self.alarm:
            return
        self.alarm_raised = True
        self.ctx.notice("ALARM RAISED")
        for action in self.alarm.get("actions", []):
            self._schedule(action)

    @property
    def stealth(self):
        """None if the mission has no stealth section, else True while the alarm was never raised."""
        return None if not self.alarm else not self.alarm_raised

    def _refresh(self):
        if self.objective is None:
            self.ctx.set_objectives("", [])
            return
        if isinstance(self.objective, EliminateGroup):
            line = self.objective.status_with(self.ctx)
        else:
            line = self.objective.status()
        self.ctx.set_objectives("OBJECTIVE", [line])
        self.ctx.set_marker(self.objective.marker)

    # ------------------------------------------------------------------ actions
    def _schedule(self, action):
        delay = float(action.get("delay", 0.0))
        if delay <= 0.0:
            self._run(action)
        else:
            self.timers.append([delay, action])

    def _run(self, a):
        kind = a.get("action")
        ctx = self.ctx
        if kind == "radio":
            ctx.radio(a["speaker"], a["text"], a.get("seconds", 4.0))
        elif kind == "spawn":
            for unit in a["units"]:
                ctx.spawn_enemy(a["group"], unit)
        elif kind == "spawn_friendly":
            for unit in a["units"]:
                ctx.spawn_friendly(a["group"], unit)
        elif kind == "barrage":
            ctx.barrage(a["area"], int(a.get("count", 10)), float(a.get("seconds", 20.0)),
                        float(a.get("radius", 5.0)), float(a.get("damage", 70.0)))
        elif kind == "squad_hold":
            for member, pos in a["positions"].items():
                ctx.squad_hold(member, pos)
        elif kind == "squad_follow":
            ctx.squad_follow(a.get("member", "all"))
        elif kind == "squad_leader":
            ctx.squad_leader(a["member"], a.get("leader"))
        elif kind == "squad_invulnerable":
            ctx.squad_invulnerable(a["member"], bool(a.get("value", True)))
        elif kind == "destroy_prop":
            ctx.destroy_prop(a["id"], a.get("explode", False))
            self.destroyed.append((a["id"], self.index))
        elif kind == "explosion":
            ctx.explosion(a["pos"])
        elif kind == "loop_start":
            ctx.loop(a["sound"], True, a.get("volume", 0.5))
        elif kind == "loop_stop":
            ctx.loop(a["sound"], False)
        elif kind == "smoke":
            ctx.add_smoke(a["pos"], a.get("seconds", 120.0))
        elif kind == "checkpoint":
            self.save_checkpoint(a.get("pos"), a.get("heading", 0.0))
        elif kind == "notice":
            ctx.notice(a["text"])
        elif kind == "sound":
            ctx.play_sound(a["sound"])
        elif kind == "refill_ammo":
            ctx.refill_ammo()
        elif kind == "complete_mission":
            self.finish()
        elif kind == "spawn_vehicle":
            ctx.spawn_vehicle(a)
        elif kind == "remove_vehicle":
            ctx.remove_vehicle(a["id"])
        elif kind == "vehicle_command":
            ctx.vehicle_command(a["id"], a.get("mode"), a.get("target"), a.get("path"), a.get("speed"),
                                a.get("paused"))
        elif kind == "start_ride":
            ctx.start_ride(a["vehicle"], a.get("seat", [0.0, 1.6, -0.2]), a.get("squad", {}), a.get("drive", False),
                           a.get("breakable", []))
        elif kind == "end_ride":
            ctx.end_ride(a.get("pos"), a.get("heading"), a.get("squad", {}))
        elif kind == "drone_start":
            ctx.drone_start(a["pos"], a.get("heading", 0.0), a.get("max_range", 200.0))
        elif kind == "drone_end":
            ctx.drone_end()
        elif kind == "show_prop":
            ctx.show_prop(a["id"])
            self.shown.append((a["id"], self.index))
        elif kind == "hide_prop":
            ctx.destroy_prop(a["id"], False)
            self.destroyed.append((a["id"], self.index))
        elif kind == "collapse_bridge":
            for pid in a.get("spans", []):
                ctx.destroy_prop(pid, False)
                self.destroyed.append((pid, self.index))
            for pid in a.get("show", []):
                ctx.show_prop(pid)
                self.shown.append((pid, self.index))
            ctx.collapse_bridge(a.get("blasts", []), a.get("vehicles", []))
        elif kind == "flare":
            ctx.flare(a["pos"], a.get("seconds", 25.0))
        elif kind == "give_weapon":
            ctx.give_weapon(a["id"], a.get("ammo"))
        elif kind == "set_visibility":
            ctx.set_visibility(float(a["value"]), a.get("lit", []))
        elif kind == "nvg":
            ctx.enable_nvg(bool(a.get("available", True)), bool(a.get("on", False)))
        elif kind == "alarm_arm":
            self.alarm_armed = True
        elif kind == "alarm_disarm":
            self.alarm_armed = False
        elif kind == "raise_alarm":
            self.raise_alarm()
        elif kind == "spawn_camera":
            ctx.spawn_camera(a)
        elif kind == "spawn_squad":
            ctx.spawn_squad(a)
        elif kind == "set_captive":
            ctx.set_captive(a["id"], bool(a.get("value", False)))
        elif kind == "kill_group":
            ctx.kill_group(a["group"], int(a.get("count", 1)), a.get("sound"))
        elif kind == "cancel_barrage":
            ctx.cancel_barrage()
        elif kind == "give_grenades":
            ctx.give_grenades(a["kind"], int(a.get("count", 1)))
        elif kind == "fail_mission":
            self.fail(a.get("message", "Mission failed."))
        else:
            log.warning("Unknown mission action '%s'", kind)

    # ------------------------------------------------------------------ checkpoints
    def save_checkpoint(self, pos=None, heading=0.0):
        """Remember where to restart. The step after this checkpoint replays its on_start actions."""
        # Saved while finishing a step -> restart at the NEXT step.
        next_index = self.index + 1 if self._completing else self.index
        next_index = min(max(0, next_index), len(self.steps) - 1)
        self.checkpoint = {
            "step": next_index,
            "player": ctx_pos(self.ctx, pos, heading),
            "destroyed": list(self.destroyed),
            "shown": list(self.shown),
            "alarm": (self.alarm_armed, self.alarm_raised),
            "time": self.time,
        }
        self.ctx.notice("CHECKPOINT")
        self.ctx.on_checkpoint(self.checkpoint)

    def restart_from_checkpoint(self):
        cp = self.checkpoint
        if cp is None:
            return False
        ctx = self.ctx
        ctx.clear_enemies()
        # Undo destruction that happened after the checkpoint.
        keep = {pid for pid, _ in cp["destroyed"]}
        for pid, _ in list(self.destroyed):
            if pid not in keep:
                ctx.restore_prop(pid)
        self.destroyed = list(cp["destroyed"])
        keep = {pid for pid, _ in cp.get("shown", [])}
        for pid, _ in list(self.shown):
            if pid not in keep:
                ctx.destroy_prop(pid, False)
        self.shown = list(cp.get("shown", []))
        self.alarm_armed, self.alarm_raised = cp.get("alarm", (False, False))
        self.timers = []
        self.state = RUNNING
        ctx.restore_player(cp["player"])
        # Bring back the enemies and cameras that were alive at the checkpoint, except what the step
        # we restart at creates itself (otherwise they would appear twice).
        start = self.steps[cp["step"]].get("on_start", [])
        ctx.restore_world({a["group"] for a in start if a.get("action") == "spawn"},
                          {a["id"] for a in start if a.get("action") == "spawn_camera"})
        self._enter_step(cp["step"])
        return True


def ctx_pos(ctx, pos, heading):
    if pos is not None:
        return {"pos": list(pos), "heading": heading}
    x, y, z = ctx.player_position()
    return {"pos": [x, y, z], "heading": ctx.player_heading()}
