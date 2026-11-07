"""The player's weapons: firing, aiming, reloading, switching, recoil, grenades and their effects."""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, TransparencyAttrib, Vec3

from core.paths import DATA_DIR
from weapons.factory import create_weapon
from weapons.grenade import GrenadeProjectile
from weapons.viewmodel import ViewModel
from weapons.weapon_base import load_weapon_data

SLOT_ACTIONS = ("weapon_1", "weapon_2", "weapon_3", "weapon_4", "weapon_5")
LOWER_TIME = 0.18


class WeaponManager:
    def __init__(self, game, player, loadout=("kr7", "p12", "lr50", "sg8")):
        self.game = game
        self.player = player
        self.stats_db, self.grenade_stats = load_weapon_data(DATA_DIR / "weapons.json")
        self.weapons = [create_weapon(self.stats_db[w]) for w in loadout]
        self.index = 0
        self.last_index = 1 if len(self.weapons) > 1 else 0
        self.grenades = self.grenade_stats.start_count
        self.special = {"smoke": 0, "flash": 0}      # smoke grenades and flashbangs
        self.grenade_type = "frag"
        self.projectiles = []
        self.ads = 0.0
        self._switch_target = None
        self._lower = 1.0                 # 1 = fully lowered; raised when the game starts
        self._raising = True
        self._recoil_queue = [0.0, 0.0]
        self._recoil_debt = 0.0
        self._since_shot = 1.0
        self._flash_timer = 0.0
        self._cycle_timer = -1.0
        self._cycle_kind = None
        self._grenade_cooldown = 0.0
        self.shots_fired = 0
        self.shots_hit = 0
        self.headshots = 0
        self.kills = 0
        self.enabled = True
        self.hit_listeners = []           # callables(result) for HUD hit markers

        self.viewmodel = ViewModel(game, game.environment.materials)
        flash = game.effects._quad.make_copy()
        from panda3d.core import NodePath
        flash_np = NodePath(flash)
        flash_np.set_texture(game.effects.textures["flash"], 1)
        flash_np.set_transparency(TransparencyAttrib.M_alpha)
        flash_np.set_attrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                  ColorBlendAttrib.O_one))
        flash_np.set_light_off(1)
        flash_np.set_shader_off(1)
        flash_np.set_depth_write(False)
        flash_np.set_bin("fixed", 50)
        flash_np.set_two_sided(True)
        self.viewmodel.set_flash_node(flash_np)
        self.viewmodel.show_model(self.current.stats.model)

    # ------------------------------------------------------------------ properties
    @property
    def current(self):
        return self.weapons[self.index]

    @property
    def switching(self):
        return self._switch_target is not None or self._lower > 0.0

    @property
    def blocks_sprint(self):
        return self.ads > 0.15

    @property
    def scoped(self):
        return self.current.stats.weapon_class == "sniper" and self.ads > 0.9

    @property
    def fov_multiplier(self):
        return 1.0 + (self.current.stats.ads_fov_multiplier - 1.0) * self.ads

    @property
    def move_multiplier(self):
        s = self.current.stats
        return s.move_multiplier * (1.0 + (s.ads_move_multiplier - 1.0) * self.ads)

    @property
    def accuracy(self):
        return self.shots_hit / self.shots_fired if self.shots_fired else 0.0

    def reset_stats(self):
        self.shots_fired = self.shots_hit = self.headshots = self.kills = 0

    def refill_all(self):
        for w in self.weapons:
            w.refill()
        self.grenades = self.grenade_stats.start_count

    def needs_ammo(self):
        return any(w.stats.weapon_class != "launcher" and w.reserve < w.stats.max_reserve for w in self.weapons)

    def pickup_ammo(self, fraction):
        """An ammo pack: spare rounds for every gun you carry (rockets are not in it)."""
        added = 0
        for w in self.weapons:
            if w.stats.weapon_class != "launcher":
                added += w.add_ammo(max(2, int(w.stats.magazine * fraction)))
        return added

    def set_loadout(self, weapon_ids, grenades=None, smoke=0, flash=0):
        """Give the player a mission's weapons (fresh ammo)."""
        self.clear_projectiles()
        self.weapons = [create_weapon(self.stats_db[w]) for w in weapon_ids]
        self.index, self.last_index = 0, 1 if len(self.weapons) > 1 else 0
        self.grenades = self.grenade_stats.start_count if grenades is None else grenades
        self.special = {"smoke": int(smoke), "flash": int(flash)}
        self.grenade_type = "frag"
        self._switch_target, self._lower, self._raising = None, 1.0, True
        self.ads = 0.0
        self._recoil_queue = [0.0, 0.0]
        self._recoil_debt = 0.0
        self.viewmodel.show_model(self.current.stats.model)

    def snapshot(self):
        return {"ammo": [(w.mag, w.reserve) for w in self.weapons], "grenades": self.grenades, "index": self.index,
                "weapons": [w.stats.id for w in self.weapons], "special": dict(self.special)}

    def restore(self, snap):
        if "weapons" in snap and snap["weapons"] != [w.stats.id for w in self.weapons]:
            self.weapons = [create_weapon(self.stats_db[w]) for w in snap["weapons"]]   # e.g. a launcher picked up later
        self.special = dict(snap.get("special", self.special))
        for w, (mag, reserve) in zip(self.weapons, snap["ammo"]):
            w.cancel_reload()
            w.mag, w.reserve = mag, reserve
        self.grenades = snap["grenades"]
        self.index = min(snap["index"], len(self.weapons) - 1)
        self._switch_target, self._lower, self._raising = None, 1.0, True
        self.viewmodel.show_model(self.current.stats.model)
        self.clear_projectiles()

    # ------------------------------------------------------------------ switching
    def select(self, index):
        if index == self.index and self._switch_target is None:
            return
        if 0 <= index < len(self.weapons):
            self.current.cancel_reload()
            self._switch_target = index
            self._raising = False

    def _update_switch(self, dt):
        if self._switch_target is not None:
            self._lower = min(1.0, self._lower + dt / LOWER_TIME)
            if self._lower >= 1.0:
                self.last_index = self.index
                self.index = self._switch_target
                self._switch_target = None
                self._raising = True
                self.viewmodel.show_model(self.current.stats.model)
                self.game.audio.play("weapon_switch", 0.6)
        elif self._raising and self._lower > 0.0:
            self._lower = max(0.0, self._lower - dt / self.current.stats.equip_time)

    # ------------------------------------------------------------------ per frame
    def update(self, dt, inp, allow_input=True):
        w = self.current
        motor = self.player.motor
        self._since_shot += dt
        self._grenade_cooldown = max(0.0, self._grenade_cooldown - dt)

        if allow_input and self.enabled:
            for i, action in enumerate(SLOT_ACTIONS):
                if inp.was_pressed(action):
                    self.select(i)
            if inp.was_pressed("swap_weapon") or inp.was_pressed("next_weapon"):
                self.select(self.last_index if inp.was_pressed("swap_weapon") else (self.index + 1) % len(self.weapons))
            if inp.was_pressed("prev_weapon"):
                self.select((self.index - 1) % len(self.weapons))
            if inp.was_pressed("reload") and not self.switching:
                w.start_reload()
            if inp.was_pressed("grenade"):
                self.throw_grenade()
            if inp.was_pressed("grenade_type"):
                self.cycle_grenade_type()
        self._update_switch(dt)

        aiming = allow_input and self.enabled and inp.is_down("aim") and not self.switching and not motor.sprinting
        target = 1.0 if aiming else 0.0
        rate = dt / max(0.05, w.stats.ads_time)
        self.ads = min(target, self.ads + rate) if target > self.ads else max(target, self.ads - rate)

        trigger_held = allow_input and self.enabled and inp.is_down("fire")
        trigger_pressed = allow_input and self.enabled and inp.was_pressed("fire")
        if not self.switching and not motor.sprinting and w.wants_fire(trigger_pressed, trigger_held):
            if w.try_fire():
                self._shoot(w)
        w.update(dt)
        self._handle_events(w)
        self._apply_recoil(dt, w)
        self._update_grenades(dt)

        if self._cycle_timer >= 0.0:
            self._cycle_timer -= dt
            if self._cycle_timer < 0.0:
                self.viewmodel.cycle(self._cycle_kind)
                self.game.audio.play("pump" if self._cycle_kind == "pump" else "bolt", 0.7)

        self._flash_timer -= dt
        if self._flash_timer <= 0.0:
            self.viewmodel.flash.hide()

        cam = self.game.camera
        self.viewmodel.set_visible(not self.scoped and getattr(self.game, "drone", None) is None
                                   and not getattr(self.game, "driving", False))
        self.viewmodel.update(
            dt, ads=self.ads, bob_phase=motor.bob_phase,
            bob_weight=min(1.5, motor.horizontal_speed / motor.cfg.walk_speed) if motor.grounded else 0.0,
            mouse_dx=inp.mouse_dx, mouse_dy=inp.mouse_dy,
            sprint=1.0 if motor.sprinting and motor.horizontal_speed > motor.cfg.walk_speed else 0.0,
            reload_progress=w.reload_progress if w.reloading and w.stats.weapon_class != "shotgun" else
            (0.35 if w.reloading else 0.0),
            switch_lower=self._lower, sun_quat=self.game.environment.sun_np.get_quat(cam) if
            self.game.environment.sun_np else cam.get_quat(), aspect=self.game.getAspectRatio())

    # ------------------------------------------------------------------ shooting
    def _camera_frame(self):
        cam = self.game.camera
        q = cam.get_quat(self.game.render)
        return cam.get_pos(self.game.render), q.get_forward(), q.get_right(), q.get_up()

    def _shoot(self, w):
        game = self.game
        origin, fwd, right, up = self._camera_frame()
        if w.stats.weapon_class == "launcher":
            self._fire_rocket(w, origin, fwd, right, up)
            return
        motor = self.player.motor
        moving = min(1.0, motor.horizontal_speed / motor.cfg.walk_speed)
        spread = w.spread(self.ads, moving, not motor.grounded)
        muzzle = origin + fwd * 0.7 + right * (0.13 * (1 - self.ads)) - up * (0.1 * (1 - self.ads) + 0.03)
        any_hit = False
        killed_any = False
        head = False
        for yaw_off, pitch_off in w.pellet_offsets(spread):
            d = fwd + right * math.tan(math.radians(yaw_off)) + up * math.tan(math.radians(pitch_off))
            d.normalize()
            res = game.combat.fire(self.player, tuple(origin), tuple(d), w.stats)
            end = origin + d * w.stats.range
            if res is not None:
                end = Vec3(*res.point)
                if res.target is not None:
                    if res.damage > 0:
                        any_hit = True
                        head = head or res.zone == "head"
                        killed_any = killed_any or res.killed
                    game.effects.impact(res.point, res.normal, "flesh")
                else:
                    game.effects.impact(res.point, res.normal, "world")
                    if w.stats.pellets == 1:
                        game.audio.play_at("impact_hard", res.point, 0.5, min_distance=2.0)
            if w.stats.tracer_every and w.shots_fired % w.stats.tracer_every == 0:
                game.effects.tracer(muzzle + d * 1.5, end)
        self.shots_fired += 1
        if any_hit:
            self.shots_hit += 1
            if head:
                self.headshots += 1
            if killed_any:
                self.kills += 1
            for listener in self.hit_listeners:
                listener(killed_any, head)
            game.audio.play("killmarker" if killed_any else "hitmarker", 0.5)

        # Muzzle flash in the viewmodel + smoke in the world.
        flash = self.viewmodel.flash
        flash.set_pos(self.viewmodel.muzzle_local() + Vec3(0, 0.05, 0))
        flash.set_scale(0.09 if w.stats.weapon_class != "pistol" else 0.06)
        flash.set_r((w.shots_fired * 47) % 360)
        flash.show()
        self._flash_timer = 0.045
        game.effects.spawn("smoke", muzzle + fwd * 0.3, vel=fwd * 1.0 + Vec3(0, 0, 0.3), life=0.7,
                           size=(0.08, 0.45), alpha=0.18, color=(0.75, 0.75, 0.72), texture="smoke", drag=2.0)

        kick_p, kick_y = w.recoil_kick(self.ads)
        self._recoil_queue[0] += kick_p
        self._recoil_queue[1] += kick_y
        self._recoil_debt += kick_p * w.stats.recoil_recovery
        self._since_shot = 0.0
        self.viewmodel.kick(min(1.2, 0.35 + kick_p * 0.25))
        self.player.camera.add_trauma(min(0.35, 0.05 + kick_p * 0.04))
        noise = w.stats.noise or (120.0 if w.stats.weapon_class == "sniper" else 70.0)
        game.combat.emit_noise(tuple(origin), noise, "friendly", self.player)

    def _fire_rocket(self, w, origin, fwd, right, up):
        """Rocket launcher: a real projectile (flies, leaves smoke, explodes on impact)."""
        game = self.game
        muzzle = origin + fwd * 0.9 + right * (0.12 * (1 - self.ads)) - up * 0.05
        spread = math.radians(w.spread(self.ads, min(1.0, self.player.motor.horizontal_speed / 4.6),
                                       not self.player.motor.grounded))
        d = fwd + right * math.tan(spread * (game.vehicles.rng.random() - 0.5)) +             up * math.tan(spread * (game.vehicles.rng.random() - 0.5))
        d.normalize()
        target = origin + d * 300.0
        game.vehicles.launch_rocket(self.player, tuple(muzzle), tuple(target), speed=80.0, radius=5.5,
                                    damage=w.stats.damage)
        self.shots_fired += 1
        game.effects.spawn("smoke", origin - fwd * 1.2, vel=-fwd * 3.0, life=1.4, size=(0.6, 2.4), alpha=0.5,
                           color=(0.8, 0.8, 0.78), texture="smoke", drag=1.5)          # back-blast
        kick_p, kick_y = w.recoil_kick(self.ads)
        self._recoil_queue[0] += kick_p
        self._recoil_queue[1] += kick_y
        self._recoil_debt += kick_p * w.stats.recoil_recovery
        self._since_shot = 0.0
        self.viewmodel.kick(1.2)
        self.player.camera.add_trauma(0.35)
        game.combat.emit_noise(tuple(origin), 120.0, "friendly", self.player)

    def rocket_model(self):
        if getattr(self, "_rocket_np", None) is None:
            from environments.geometry import MeshBuilder
            from panda3d.core import NodePath
            mats = self.game.environment.materials
            mb = MeshBuilder(mats.uv_scales())
            mb.cylinder_between("metal", (0, -0.45, 0), (0, 0.35, 0), 0.045, (0.3, 0.33, 0.22), segments=8)
            mb.cylinder_between("metal", (0, 0.35, 0), (0, 0.5, 0), 0.045, (0.2, 0.2, 0.2), segments=8,
                                radius_end=0.0)
            mb.box("metal", 0, -0.4, -0.12, 0.008, 0.16, 0.24, (0.2, 0.2, 0.2))      # vertical tail fin
            mb.box("metal", 0, -0.4, -0.004, 0.24, 0.16, 0.008, (0.2, 0.2, 0.2))     # horizontal tail fin
            mb.box("emissive", 0, -0.48, -0.03, 0.06, 0.04, 0.06, (1.0, 0.7, 0.3))
            self._rocket_np = mb.build(NodePath("rocket_template"), mats, name="rocket")
        return self._rocket_np

    def give_weapon(self, weapon_id, ammo=None):
        """Add a weapon to the loadout (e.g. picking up a launcher). Returns its slot index."""
        for i, w in enumerate(self.weapons):
            if w.stats.id == weapon_id:
                if ammo is not None:
                    w.reserve = min(w.stats.max_reserve, w.reserve + ammo)
                return i
        w = create_weapon(self.stats_db[weapon_id])
        if ammo is not None:
            w.reserve = ammo
        self.weapons.append(w)
        return len(self.weapons) - 1

    def _handle_events(self, w):
        audio = self.game.audio
        for ev in w.pop_events():
            if ev == "fire":
                audio.play(w.stats.sound, 0.9, variation=0.04)
            elif ev == "dry":
                audio.play("dry_fire", 0.7)
            elif ev == "reload_start":
                audio.play("reload_out", 0.7)
            elif ev == "reload_end":
                audio.play("reload_in", 0.7)
            elif ev == "shell":
                audio.play("shell_in", 0.6, variation=0.05)
            elif ev == "cycle":
                self._cycle_kind = "pump" if w.stats.fire_mode == "pump" else "bolt"
                self._cycle_timer = 0.15

    def _apply_recoil(self, dt, w):
        look = self.player.camera.look
        # Apply queued kick quickly (over ~50 ms) so it feels punchy but smooth.
        k = min(1.0, dt * 20.0)
        dp, dy = self._recoil_queue[0] * k, self._recoil_queue[1] * k
        self._recoil_queue[0] -= dp
        self._recoil_queue[1] -= dy
        look.pitch = min(88.0, look.pitch + dp)
        look.yaw += dy
        # Pull part of it back down after the player stops shooting.
        if self._since_shot > 0.12 and self._recoil_debt > 0.0:
            back = min(self._recoil_debt, max(0.02, self._recoil_debt * dt * 6.0))
            self._recoil_debt -= back
            look.pitch = max(-88.0, look.pitch - back)

    # ------------------------------------------------------------------ grenades
    GRENADE_TYPES = ("frag", "smoke", "flash")
    FUSES = {"smoke": 1.4, "flash": 1.3}

    def grenade_count(self, kind=None):
        kind = kind or self.grenade_type
        return self.grenades if kind == "frag" else self.special.get(kind, 0)

    def cycle_grenade_type(self):
        """T: frag -> smoke -> flashbang (only types you have)."""
        i = self.GRENADE_TYPES.index(self.grenade_type)
        for k in range(1, len(self.GRENADE_TYPES) + 1):
            kind = self.GRENADE_TYPES[(i + k) % len(self.GRENADE_TYPES)]
            if kind == "frag" or self.special.get(kind, 0) > 0:
                if kind != self.grenade_type:
                    self.grenade_type = kind
                    self.game.audio.play("weapon_switch", 0.4)
                return kind
        return self.grenade_type

    def give_grenades(self, kind, count):
        if kind == "frag":
            self.grenades = min(self.grenade_stats.max_count + 2, self.grenades + count)
        else:
            self.special[kind] = self.special.get(kind, 0) + count

    def throw_grenade(self):
        kind = self.grenade_type
        if self.grenade_count(kind) <= 0:
            kind = self.grenade_type = "frag"
        if self.grenade_count(kind) <= 0 or self._grenade_cooldown > 0.0 or self.switching:
            return False
        origin, fwd, right, up = self._camera_frame()
        m = self.player.motor
        vel = fwd * self.grenade_stats.throw_speed + Vec3(0, 0, 3.0) + Vec3(m.vx, m.vy, 0) * 0.5
        start = origin + fwd * 0.5 - up * 0.1 + right * 0.15
        g = GrenadeProjectile(tuple(start), tuple(vel), self.FUSES.get(kind, self.grenade_stats.fuse),
                              owner=self.player, kind=kind)
        g.node = self._grenade_template().copy_to(self.game.render)
        if kind != "frag":
            g.node.set_color_scale((0.75, 0.75, 0.78, 1) if kind == "smoke" else (0.45, 0.5, 0.7, 1))
        g.node.set_pos(*start)
        self.projectiles.append(g)
        if kind == "frag":
            self.grenades -= 1
        else:
            self.special[kind] -= 1
            if self.special[kind] <= 0:
                self.grenade_type = "frag"
        self._grenade_cooldown = 0.8
        self.game.audio.play("grenade_pin", 0.7)
        self.viewmodel.kick(0.6)
        return True

    def _grenade_template(self):
        if getattr(self, "_grenade_np", None) is None:
            from environments.geometry import MeshBuilder
            from panda3d.core import NodePath
            mats = self.game.environment.materials
            mb = MeshBuilder(mats.uv_scales())
            mb.ellipsoid("metal", 0, 0, 0, 0.05, 0.05, 0.065, (0.28, 0.31, 0.2), rings=6, segments=10)
            mb.cylinder("metal", 0, 0, 0.055, 0.015, 0.03, (0.15, 0.15, 0.15), segments=6)
            mb.box("metal", 0.012, 0, 0.06, 0.012, 0.015, 0.06, (0.15, 0.15, 0.15))
            self._grenade_np = mb.build(NodePath("grenade_templates"), mats, name="grenade")
        return self._grenade_np

    def _update_grenades(self, dt):
        world = self.game.collision_world
        alive = []
        for g in self.projectiles:
            if g.update(dt, world):
                if g.kind == "smoke":
                    self.game.smoke_grenade(tuple(g.pos))
                elif g.kind == "flash":
                    self.game.flashbang(tuple(g.pos), g.owner)
                else:
                    self.game.explode(tuple(g.pos), self.grenade_stats.radius, self.grenade_stats.max_damage, g.owner)
                g.node.remove_node()
                continue
            g.node.set_pos(*g.pos)
            if g.bounced:
                self.game.audio.play_at("grenade_bounce", g.pos, 0.6)
            alive.append(g)
        self.projectiles = alive

    def clear_projectiles(self):
        for g in self.projectiles:
            g.node.remove_node()
        self.projectiles = []
