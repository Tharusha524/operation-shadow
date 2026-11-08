"""Bridge between the mission script (MissionRunner) and the running game."""
from __future__ import annotations

import logging
import math

from environments.map_loader import Placement

log = logging.getLogger(__name__)


class MissionContext:
    def __init__(self, game):
        self.game = game

    # ------------------------------------------------------------------ queries
    def player_position(self):
        return self.game.player.position

    def player_eye_position(self):
        return self.game.player.eye_position()

    def player_heading(self):
        return self.game.player.camera.look.yaw

    def player_looking_at(self, pos, max_angle):
        g = self.game
        cam = g.camera
        origin = cam.get_pos(g.render)
        fwd = cam.get_quat(g.render).get_forward()
        d = [pos[i] - origin[i] for i in range(3)]
        dist = math.sqrt(sum(v * v for v in d)) or 1.0
        cosang = (d[0] * fwd[0] + d[1] * fwd[1] + d[2] * fwd[2]) / dist
        return cosang >= math.cos(math.radians(max_angle))

    def interact_held(self):
        return self.game.input.is_down("interact")

    def group_total(self, group):
        return self.game.soldiers.group_count(group)

    def group_alive(self, group):
        return len(self.game.soldiers.group_alive(group))

    # ------------------------------------------------------------------ HUD
    def set_objectives(self, title, lines):
        self.game.hud.set_objectives(title, lines)

    def set_marker(self, marker):
        self.game.hud.set_marker(marker)

    def set_prompt(self, text, progress=None):
        self.game.hud.set_prompt(text, progress)

    def on_new_objective(self, text):
        self.game.audio.play("objective", 0.5)
        self.game.hud.show_notice(f"NEW OBJECTIVE: {text.upper()}", 3.5)

    def notice(self, text):
        self.game.hud.show_notice(text, 3.0)

    def radio(self, speaker, text, seconds=4.0):
        g = self.game
        name = g.campaign.speaker_name(speaker)
        g.radio(name, text, beep=speaker == "bastion", seconds=seconds, voice=speaker)

    # ------------------------------------------------------------------ world
    def spawn_enemy(self, group, unit):
        g = self.game
        x, y = unit["pos"][0], unit["pos"][1]
        heading = unit.get("heading", 180.0)
        s = g.soldiers.spawn("enemy", x, y, heading, profile=unit.get("profile", "regular"), group=group,
                             patrol=unit.get("patrol"))
        if "ride" in unit:                                   # gunner in the back of an enemy jeep
            from core.ride import seat_world
            v = g.vehicles.find(unit["ride"]["vehicle"])
            if v is not None:
                seat = tuple(unit["ride"].get("seat", [0.0, -1.0, 0.6]))
                s.mount = (lambda v=v, seat=seat: seat_world(v, seat))
        if "hold" in unit:
            h = unit["hold"]
            s.ai.command_hold(h[0], h[1], h[2] if len(h) > 2 else heading)
        elif "alert" in unit:
            ax, ay = unit["alert"]
            s.ai.alert(g.player, (ax, ay, 0.0))
        return s

    def spawn_friendly(self, group, unit):
        """Allied soldiers (not the player's squad): they hold a position and can be killed."""
        g = self.game
        x, y = unit["pos"][0], unit["pos"][1]
        heading = unit.get("heading", 0.0)
        s = g.soldiers.spawn("friendly", x, y, heading, profile=unit.get("profile", "rifleman"), group=group,
                             name=unit.get("name", "Rifleman"))
        h = unit.get("hold", [x, y, heading])
        s.ai.command_hold(h[0], h[1], h[2] if len(h) > 2 else heading)
        return s

    def barrage(self, area, count, seconds, radius, damage, scale=2.5, source="north", target_group=None,
                aimed=0.5):
        """Artillery: `count` shells land inside area=[x0, y0, x1, y1] over `seconds`.

        Shells fall visibly from the `source` side ("north"/"south") with a smoke trail. With target_group,
        a share (`aimed`) of them come down right on top of soldiers of that group."""
        g = self.game
        rng = g.soldiers.rng
        direction = {"north": (0.15, 1.0), "south": (-0.1, -1.0), "east": (1.0, 0.1), "west": (-1.0, 0.1)}.get(
            source, (0.15, 1.0))
        for _ in range(count):
            when = rng.uniform(0.0, seconds)
            pos = (rng.uniform(area[0], area[2]), rng.uniform(area[1], area[3]), 0.2)
            victim = target_group if target_group and rng.random() < aimed else None
            g.shells.append([when, pos, False, radius, damage, scale, direction, victim, 0.0])

    def squad_hold(self, member, pos):
        for sid, s in self._squad(member):
            s.ai.command_hold(pos[0], pos[1], pos[2] if len(pos) > 2 else None)

    def squad_follow(self, member="all"):
        for sid, s in self._squad(member):
            s.ai.command_follow()

    def squad_leader(self, member, leader_id):
        """Make a squad member follow another squad member (None = follow the player again)."""
        leader = self.game.squad.get(leader_id) if leader_id else None
        for sid, s in self._squad(member):
            s.ai.leader = leader
            s.ai.command_follow()

    def squad_invulnerable(self, member, value):
        for sid, s in self._squad(member):
            s.health.invulnerable = value

    def escort_start(self, target, route):
        s = self.game.squad.get(target)
        if s is not None:
            s.ai.command_escort(route)

    def squad_alive(self, member):
        s = self.game.squad.get(member)
        return s is None or s.alive

    def squad_position(self, member):
        s = self.game.squad.get(member)
        return s.position if s is not None else None

    def _squad(self, member):
        squad = self.game.squad
        if member == "all":
            return list(squad.items())
        return [(member, squad[member])] if member in squad else []

    def destroy_prop(self, prop_id, explode=False):
        g = self.game
        entry = g.environment.dynamic.get(prop_id)
        bounds = g.environment.destroy_prop(prop_id)
        if bounds:
            g.nav.rebuild(bounds)
        if explode and entry:
            x, y, z = entry["pos"]
            g.clear_charges(near=[(x, y, z)], radius=8.0)
            g.explode((x, y, z + 0.5), 6.0, 60.0)

    def restore_prop(self, prop_id):
        g = self.game
        bounds = g.environment.restore_prop(prop_id)
        if bounds:
            g.nav.rebuild(bounds)

    def missile(self, target, radius, damage, scale=4.0, origin=None):
        """A missile streaking down from the sky onto `target` [x, y]."""
        g = self.game
        tx, ty = target[0], target[1]
        tz = target[2] if len(target) > 2 else 0.0
        if origin is None:
            origin = (tx - 90.0, ty + 330.0, 130.0)           # in low from the north, over the hills
        g.vehicles.launch_rocket(None, tuple(origin), (tx, ty, tz), speed=150.0, radius=radius, damage=damage,
                                 scale=scale)

    def blast_group(self, group, interval=0.35, debris="earth"):
        """Every soldier of the group is caught by an explosion, one after another (the line is blown)."""
        g = self.game
        for i, s in enumerate(g.soldiers.group_alive(group)):
            def boom(s=s):
                if not s.alive:
                    return
                x, y, z = s.position
                g.explode((x + g.soldiers.rng.uniform(-0.6, 0.6), y + 0.4, z + 0.6), 4.5, 500.0, None, 4.5)
                g.debris.burst((x, y + 1.2, z + 0.8), 12, debris, 0.4, 9.0, 8.0)
            g.timed.append([i * interval + 0.01, boom])

    def _shooter(self, spec, near):
        g = self.game
        if spec.startswith("team:"):
            pool = [s for s in g.soldiers.soldiers if s.team == spec[5:] and s.alive]
        else:
            pool = g.soldiers.group_alive(spec)
        if not pool:
            return None
        pool.sort(key=lambda s: math.hypot(s.motor.x - near[0], s.motor.y - near[1]))
        return g.soldiers.rng.choice(pool[:3])

    def _shoot_fx(self, shooter, point):
        g = self.game
        mx, my, mz = shooter.muzzle_position()
        shooter.facing = math.degrees(math.atan2(-(point[0] - mx), point[1] - my))
        g.effects.tracer((mx, my, mz), point)
        g.effects.muzzle_flash((mx, my, mz), (0, 0, 1), 0.8)
        g.audio.play_at("shot_enemy", (mx, my, mz), 0.8, min_distance=8.0)

    def civ_shot(self, group, shooter="team:enemy", count=1, interval=1.0):
        """Enemy soldiers gun down fleeing civilians, one by one."""
        g = self.game
        rng = g.soldiers.rng

        def shoot():
            people = g.civilians.alive(group)
            if not people:
                return
            c = rng.choice(people)
            x, y, z = c.position
            s = self._shooter(shooter, (x, y))
            if s is None:
                return
            for _ in range(3):
                self._shoot_fx(s, (x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), z + rng.uniform(0.8, 1.5)))
            c.shot()

        for i in range(count):
            g.timed.append([interval * i + 0.01, shoot])

    def gunfire(self, shooter, target, seconds=6.0, rate=8.0):
        """Sustained enemy fire at a vehicle (the burning truck): tracers and sparks on it."""
        g = self.game
        rng = g.soldiers.rng

        def burst():
            v = g.vehicles.find(target)
            if v is None:
                return
            x, y, z = v.center()
            s = self._shooter(shooter, (x, y))
            if s is None:
                return
            p = (x + rng.uniform(-1.8, 1.8), y + rng.uniform(-1.8, 1.8), z + rng.uniform(-0.6, 0.8))
            self._shoot_fx(s, p)
            g.effects.impact(p, (0, 0, 1), "metal")

        for i in range(int(seconds * rate)):
            g.timed.append([i / rate + rng.uniform(0, 0.08), burst])

    def destroy_vehicle(self, vid):
        v = self.game.vehicles.find(vid)
        if v is not None and v.alive:
            v.take_damage(1e9, None, "blast", (0.0, 0.0, 1.0))

    def player_weapons(self, enabled):
        g = self.game
        g.weapons.enabled = enabled
        g.weapons.viewmodel.set_visible(enabled)

    def player_invulnerable(self, value):
        self.game.player.invulnerable = value

    def spawn_civilians(self, group, units):
        self.game.civilians.spawn(group, units)

    def rpg(self, shooter, target, count=1, interval=4.0, damage=220.0, radius=5.0):
        """Rocket-propelled grenades: soldiers of `shooter` (group or "team:x") fire at `target`
        (a vehicle id, a soldier group, "team:x" or "player"), `count` times, `interval` s apart."""
        g = self.game
        rng = g.soldiers.rng

        def pick(spec):
            if spec.startswith("team:"):
                return [s for s in g.soldiers.soldiers if s.team == spec[5:] and s.alive]
            return g.soldiers.group_alive(spec)

        def fire():
            shooters = pick(shooter)
            if not shooters:
                return
            v = g.vehicles.find(target)
            if v is not None:
                if not v.alive:
                    return
                aim = v.center()
            elif target == "player":
                aim = g.player.eye_position()
            else:
                victims = pick(target)
                if not victims:
                    return
                aim = rng.choice(victims).center()
            shooters.sort(key=lambda s: math.hypot(s.motor.x - aim[0], s.motor.y - aim[1]))
            s = rng.choice(shooters[:3])
            ex, ey, ez = s.eye_position()
            dist = math.hypot(aim[0] - ex, aim[1] - ey)
            if dist > 160.0:
                return
            s.facing = math.degrees(math.atan2(-(aim[0] - ex), aim[1] - ey))
            err = dist * 0.04
            point = (aim[0] + rng.uniform(-err, err), aim[1] + rng.uniform(-err, err), aim[2] + rng.uniform(-0.5, 0.5))
            g.vehicles.launch_rocket(s, (ex, ey, ez - 0.1), point, speed=60.0, radius=radius, damage=damage,
                                     scale=2.6)
            g.effects.spawn("smoke", (ex, ey, ez), life=2.0, size=(0.6, 2.5), alpha=0.5, color=(0.7, 0.68, 0.64),
                            texture="smoke", drag=1.5)

        for i in range(count):
            if i == 0:
                fire()
            else:
                g.timed.append([interval * i + rng.uniform(-0.5, 0.5), fire])

    def near_miss(self, distance=4.0, damage=25.0):
        """A shell lands a few metres from the player (in front, slightly to the side): the big scare moment."""
        g = self.game
        p = g.player
        yaw = math.radians(p.camera.look.yaw + g.soldiers.rng.uniform(-50, 50))
        x = p.motor.x - math.sin(yaw) * distance
        y = p.motor.y + math.cos(yaw) * distance
        g.shells.append([1.6, (x, y, p.motor.z + 0.2), False, 6.0, damage, 3.4, (0.15, 1.0), None, 0.0])

    def debris(self, pos, count=14, kind="concrete", size=0.4, speed=9.0):
        p = (pos[0], pos[1], pos[2] if len(pos) > 2 else 0.5)
        self.game.debris.burst(p, count, kind, size, speed, speed * 0.8)

    def tank_fire(self, vid, target):
        """A tank fires its cannon at a scripted point (a building, a bunker...)."""
        g = self.game
        v = g.vehicles.find(vid)
        if v is None or not v.alive:
            return
        t = (target[0], target[1], target[2] if len(target) > 2 else 1.0)
        muzzle = (v.pos[0], v.pos[1], v.pos[2] + 2.3)
        g.vehicles.tank_shell(v, muzzle, t)

    def fire(self, pos, size=1.5):
        self.game.add_fire(tuple(pos), size)

    def group_move(self, group, pos, spread=(2.0, 0.0), heading=180.0):
        """Order a group (e.g. retreating riflemen) to run to a new position, spaced out."""
        for i, s in enumerate(self.game.soldiers.group_alive(group)):
            s.ai.command_hold(pos[0] + spread[0] * i, pos[1] + spread[1] * i, heading)

    def explosion(self, pos, radius=6.0, damage=80.0, scale=None):
        self.game.explode(tuple(pos), radius, damage, None, scale)

    def loop(self, name, on, volume=0.5):
        if on:
            self.game.audio.start_loop(name, volume)
        else:
            self.game.audio.stop_loop(name)

    def add_smoke(self, pos, seconds):
        self.game.smoke_emitters.append([tuple(pos), float(seconds), 0.0])

    def play_sound(self, name):
        self.game.audio.play(name, 0.6)

    def refill_ammo(self):
        self.game.weapons.refill_all()

    # ------------------------------------------------------------------ vehicles, rides, drone
    VEHICLE_PARAMS = ("pos", "heading", "path", "speed", "loop", "team", "health", "altitude", "orbit_radius",
                      "armed")

    def spawn_vehicle(self, a):
        if a.get("if_missing") and self.game.vehicles.find(a["id"]) is not None:
            return None                                  # already there (only re-created after a retry)
        params = {k: a[k] for k in self.VEHICLE_PARAMS if k in a}
        if "path" in params:
            params["path"] = [tuple(p) for p in params["path"]]
        if "pos" in params:
            params["pos"] = tuple(params["pos"])
        v = self.game.vehicles.spawn(a["kind"], a["id"], **params)
        if a.get("mode"):
            self.game.vehicles.command(a["id"], mode=a["mode"], target=a.get("target"))
        if a.get("paused"):
            v.paused = True                              # e.g. a boat waiting at the pier
        return v

    def remove_vehicle(self, vid):
        v = self.game.vehicles.find(vid)
        if v is not None:
            self.game.vehicles.remove(v)

    def vehicle_command(self, vid, mode=None, target=None, path=None, speed=None, paused=None):
        self.game.vehicles.command(vid, mode, target, path, speed, paused)

    def vehicle_destroyed(self, vid):
        v = self.game.vehicles.find(vid)
        return self.game.vehicles.is_destroyed(vid) or (v is not None and not v.alive)

    def vehicle_position(self, vid):
        v = self.game.vehicles.find(vid)
        return v.position if v is not None else None

    def vehicle_arrived(self, vid):
        v = self.game.vehicles.find(vid)
        return v is None or v.finished or not v.alive

    def start_ride(self, vid, seat, squad, drive=False, breakable=()):
        self.game.start_ride(vid, seat, squad, drive)
        v = self.game.vehicles.find(vid)
        if v is not None and hasattr(v, "breakables"):
            v.breakables = set(breakable)

    def look(self, yaw, pitch=0.0):
        cam = self.game.player.camera
        cam.look.yaw, cam.look.pitch = yaw, pitch

    def end_ride(self, pos=None, heading=None, squad=None):
        self.game.end_ride(pos, heading, squad)

    def ride_finished(self):
        r = self.game.ride
        return r is None or r.finished

    def drone_start(self, pos, heading, max_range):
        self.game.start_drone(pos, heading, max_range)

    def drone_end(self):
        self.game.end_drone()

    def tagged_count(self):
        return len(self.game.tagged)

    def alarm_triggered(self, groups):
        from enemies.enemy_ai import COMBAT_STATES
        if self.game.security.spotted:
            log.info("Alarm raised by a security camera")
            return True
        for group in groups:
            for s in self.game.soldiers.group_alive(group):
                if s.ai.state in COMBAT_STATES:
                    t = s.ai.target
                    log.info("Alarm raised by %s soldier at (%.0f, %.0f): %s, target %s at %s", group, s.motor.x,
                             s.motor.y, s.ai.state, getattr(t, "name", None),
                             tuple(round(v) for v in t.position) if t is not None else None)
                    return True
        return False

    def point_done(self, spec, pos):
        g = self.game
        if spec.get("charge"):
            g.place_charge(pos)
        g.audio.play(spec.get("sound", "c4_plant"), 0.6)

    def show_prop(self, prop_id):
        self.restore_prop(prop_id)

    def collapse_bridge(self, blasts, vehicles):
        self.game.collapse_bridge(blasts, vehicles)

    def flare(self, pos, seconds):
        self.game.fire_flare(tuple(pos), seconds)

    def give_weapon(self, weapon_id, ammo=None):
        g = self.game
        slot = g.weapons.give_weapon(weapon_id, ammo)
        g.hud.show_notice(f"PICKED UP {g.weapons.weapons[slot].stats.name.upper()}  [{slot + 1}]", 3.5)

    def give_grenades(self, kind, count):
        g = self.game
        g.weapons.give_grenades(kind, count)
        names = {"frag": "FRAG GRENADES", "smoke": "SMOKE GRENADES", "flash": "FLASHBANGS"}
        g.hud.show_notice(f"PICKED UP {count} {names.get(kind, kind.upper())}  [T] switch, [G] throw", 3.5)

    def set_visibility(self, value, lit):
        g = self.game
        g.soldiers.visibility = value
        g.base_lit_zones = [tuple(z) for z in lit]

    def enable_nvg(self, available, on):
        self.game.set_nvg(on and available, available)

    # ------------------------------------------------------------------ intel work, cameras, hostages
    def photo_target(self, group, max_angle, max_range):
        """The group member under the crosshair while aiming down sights (clear view), or None."""
        g = self.game
        if g.weapons.ads < 0.85:
            return None
        cam = g.camera
        origin = cam.get_pos(g.render)
        fwd = cam.get_quat(g.render).get_forward()
        hits = []
        for s in g.soldiers.group_alive(group):
            c = s.center()
            d = [c[i] - origin[i] for i in range(3)]
            dist = math.sqrt(sum(v * v for v in d)) or 1.0
            if dist > max_range:
                continue
            ang = math.degrees(math.acos(max(-1.0, min(1.0, sum(d[i] * fwd[i] for i in range(3)) / dist))))
            if ang <= max_angle and g.collision_world.line_of_sight((origin.x, origin.y, origin.z), c):
                hits.append((ang, dist, s))
        if not hits:
            return None
        # Two people in line: the nearer one is the one in the picture.
        best_ang = min(h[0] for h in hits)
        near = min((h for h in hits if h[0] <= best_ang + 1.0), key=lambda h: h[1])
        return id(near[2])

    def photo_taken(self, n, total):
        g = self.game
        g.audio.play("camera_shutter", 0.8)
        g.hud.show_notice(f"PHOTO TAKEN  {n}/{total}", 1.5)

    def group_members(self, group):
        return [(id(s), s.position, s.alive) for s in self.game.soldiers.soldiers if s.group == group]

    def group_alerted(self, group):
        from enemies.enemy_ai import COMBAT_STATES
        return any(s.ai.state in COMBAT_STATES for s in self.game.soldiers.group_alive(group))

    def execute_hostage(self, hostage_id, group):
        g = self.game
        s = g.squad.get(hostage_id)
        captors = g.soldiers.group_alive(group)
        if s is None or not s.alive:
            return
        shooter = captors[0] if captors else None
        if shooter is not None:
            g.audio.play_at(shooter.weapon.stats.sound, shooter.eye_position(), 1.0)
        s.health.invulnerable = False
        s.take_damage(9999.0, shooter, "head", (0.0, 1.0, 0.0))

    def download_started(self, spec):
        self.game.audio.play("tag_beep", 0.6)
        self.game.hud.show_notice("DOWNLOAD STARTED - DEFEND THE TERMINAL", 2.5)

    def spawn_camera(self, a):
        params = {k: a[k] for k in ("heading", "sweep", "period", "pitch", "fov") if k in a}
        if "range" in a:
            params["view_range"] = a["range"]
        return self.game.security.spawn(a["id"], tuple(a["pos"]), **params)

    def kill_group(self, group, count, sound=None):
        """Scripted deaths (e.g. a sniper drops a guard to start an ambush)."""
        g = self.game
        for s in g.soldiers.group_alive(group)[:count]:
            s.take_damage(99999.0, None, "head", (0.0, 1.0, 0.0))
        if sound:
            g.audio.play(sound, 0.9)

    def cancel_barrage(self):
        self.game.shells = []

    def spawn_squad(self, a):
        """Add a friendly character to the player's group mid-mission (e.g. a rescued prisoner)."""
        g = self.game
        old = g.squad.pop(a["id"], None)                     # retrying from a checkpoint: replace the old one
        if old is not None:
            g.soldiers.combat.unregister(old)
            if old.model:
                old.model.remove()
            if old in g.soldiers.soldiers:
                g.soldiers.soldiers.remove(old)
        char = g.campaign.characters.get(a["id"])
        pos = a["pos"]
        s = g.soldiers.spawn("friendly", pos[0], pos[1], a.get("heading", 0.0), profile=a.get("profile", "squad"),
                             name=char.name if char else a["id"], invulnerable=bool(a.get("invulnerable", False)))
        s.captive = bool(a.get("captive", False))
        if s.captive or "hold" in a:
            h = a.get("hold", [pos[0], pos[1], a.get("heading", 0.0)])
            s.ai.command_hold(h[0], h[1], h[2] if len(h) > 2 else None)
        g.squad[a["id"]] = s
        return s

    def set_captive(self, member, value):
        s = self.game.squad.get(member)
        if s is not None:
            s.captive = value
            if not value:
                s.ai.command_follow()

    # ------------------------------------------------------------------ restart
    def clear_enemies(self):
        g = self.game
        g.soldiers.remove_team("enemy")
        g.shells = []
        g.end_drone()
        g.end_ride()
        g.vehicles.remove_all()
        g.civilians.clear()                                  # re-created by the steps that spawn them
        g.tagged = []
        g.clear_charges()
        g.security.remove_all()
        g.pickups.clear()
        g.smoke_clouds = []
        # Allied riflemen are re-created by the steps that spawn them.
        squad = set(map(id, g.squad.values()))
        for s in [s for s in g.soldiers.soldiers
                  if s.team == "friendly" and not s.health.invulnerable and id(s) not in squad]:
            g.soldiers.combat.unregister(s)
            if s.model:
                s.model.remove()
            g.soldiers.soldiers.remove(s)

    def snapshot_world(self):
        """Remember the living enemies and security cameras, for 'retry from checkpoint'."""
        g = self.game
        soldiers = [{"group": s.group, "profile": s.profile_name, "pos": s.position[:2], "heading": s.facing,
                     "patrol": list(s.ai.patrol), "anchor": s.ai.anchor}
                    for s in g.soldiers.soldiers if s.team == "enemy" and s.alive and s.mount is None]
        cameras = [{"id": c.id, "pos": c.pos, "heading": c.base_heading, "sweep": c.sweep, "period": c.period,
                    "view_range": c.range, "fov": c.fov, "pitch": c.pitch} for c in g.security.cameras if c.alive]
        return {"soldiers": soldiers, "cameras": cameras}

    def restore_world(self, skip_groups, skip_cameras):
        g = self.game
        snap = g.checkpoint_world or {}
        for u in snap.get("soldiers", []):
            if u["group"] in skip_groups:
                continue
            s = g.soldiers.spawn("enemy", u["pos"][0], u["pos"][1], u["heading"], profile=u["profile"],
                                 group=u["group"], patrol=u["patrol"] or None)
            if u["anchor"] is not None:
                s.ai.command_hold(*u["anchor"])
        for c in snap.get("cameras", []):
            if c["id"] not in skip_cameras:
                params = {k: v for k, v in c.items() if k not in ("id", "pos")}
                g.security.spawn(c["id"], c["pos"], **params)

    def on_checkpoint(self, checkpoint):
        self.game.checkpoint_world = self.snapshot_world()
        self.game.checkpoint_weapons = self.game.weapons.snapshot()
        self.game.checkpoint_intel = self.game.intel.collected_ids()

    def restore_player(self, placement):
        g = self.game
        pos = placement["pos"]
        p = Placement(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0, placement.get("heading", 0.0))
        g.player.respawn(p)
        if g.checkpoint_weapons:
            g.weapons.restore(g.checkpoint_weapons)
        else:
            g.weapons.refill_all()
        g.intel.restore(g.checkpoint_intel or [])
        # Bring the squad back next to the player.
        for i, s in enumerate(g.squad.values()):
            ang = math.radians(p.heading + 150 + i * 30)
            s.revive(p.x - math.sin(ang) * 2.5, p.y + math.cos(ang) * 2.5, p.z)
            s.ai.leader = None
            s.ai.escort = None
            s.ai.command_follow()

    def mission_complete(self):
        self.game.on_mission_complete()

    def mission_failed(self, reason):
        self.game.on_mission_failed(reason)
