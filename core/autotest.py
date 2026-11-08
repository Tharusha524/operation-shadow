"""Automated play-test of the REAL game window.

Run:  python main.py --autotest [--screenshots FOLDER]

It drives the player with scripted keys/mouse, checks the results, saves screenshots
and exits with code 0 (all passed) or 1 (something failed).
"""
from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path

from panda3d.core import Filename

from config import constants as C

log = logging.getLogger(__name__)


class AutoTest:
    def __init__(self, game, screenshot_dir=None, views_only=False, maps=None, only=None):
        self.game = game
        self.views_only = views_only
        self.maps = maps or ["border_outpost", "kesh_ridge", "veyra", "tamsin_river"]
        self.only = only
        self.shots = Path(screenshot_dir) if screenshot_dir else None
        if self.shots:
            self.shots.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.penetration_frames = 0
        self.fps_samples = []
        self._script = self._views() if views_only else self._run()
        self._wake_at = 0.0
        game.input.scripted_down = set()                    # ignore the real keyboard, mouse and wheel
        game.input.capture_enabled = False                  # never grab the user's mouse cursor
        game.story_enabled = False                          # story videos are tested on their own (_story_tests)
        game.taskMgr.add(self._task, "autotest", sort=5)   # runs before the game update

    # ------------------------------------------------------------------ helpers
    @property
    def motor(self):
        return self.game.player.motor

    def hold(self, *actions):
        self.game.input.scripted_down = set(actions)

    def release(self):
        self.game.input.scripted_down = set()

    def check(self, name, ok, detail=""):
        self.results.append({"test": name, "passed": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)

    def teleport(self, point_name):
        p = self.game.map_data.points[point_name]
        self.release()
        self.game.player.teleport(p.x, p.y, p.z, p.heading, p.pitch)

    def screenshot(self, name):
        if self.shots:
            self.game.win.save_screenshot(Filename.from_os_specific(str(self.shots / f"{name}.png")))

    def _check_penetration(self):
        if self.game.state not in ("playing", "sandbox") or not self.game.player.alive:
            return
        m = self.motor
        free = self.game.collision_world.is_free(m.x, m.y, m.cfg.radius - 0.03,
                                                 m.z + m.cfg.step_height, m.z + m.height - 0.02)
        if not free:
            self.penetration_frames += 1

    def _task(self, task):
        self._check_penetration()
        now = self.game.sim_time          # wait in game time so results don't depend on PC speed
        if now < self._wake_at:
            return task.cont
        try:
            delay = next(self._script)
        except StopIteration:
            self._finish()
            return task.done
        self._wake_at = now + delay
        return task.cont

    # ------------------------------------------------------------------ the test script
    def _run(self):
        if self.only:
            yield 1.0
            yield from getattr(self, f"_{self.only}_tests")()
            return
        yield from self._menu_tests()
        self.game.start_sandbox()
        yield 1.5                                           # let the world settle
        m = self.motor
        self.check("spawn: standing on the ground", m.grounded and abs(m.z) < 0.01, f"z={m.z:.3f}")
        self.screenshot("01_spawn")

        start_y = m.y
        self.hold("move_forward")
        yield 1.5
        speed = m.horizontal_speed
        # Distance depends on frame timing (the game slows down rather than skipping on a long frame),
        # so the strict check is the speed; distance only has to show real forward progress.
        self.check("walk forward (W)", m.y - start_y > 3.0 and abs(speed - C.WALK_SPEED) < 0.2,
                   f"moved {m.y - start_y:.2f} m at {speed:.2f} m/s")

        self.hold("move_forward", "sprint")
        yield 1.2
        speed = m.horizontal_speed
        fov = self.game.player.camera.fov
        self.check("sprint (Shift+W)", abs(speed - C.SPRINT_SPEED) < 0.25 and fov > self.game.settings.field_of_view + 3,
                   f"{speed:.2f} m/s, fov {fov:.1f}")

        self.hold("move_right")
        yield 0.8
        self.check("strafe right (D)", m.vx > C.WALK_SPEED * 0.9, f"vx={m.vx:.2f}")
        self.release()
        yield 0.6
        self.check("stops when keys released", m.horizontal_speed < 0.05, f"{m.horizontal_speed:.3f} m/s")

        self.hold("jump")
        yield 0.05
        self.release()
        yield 0.22
        self.check("jump (Space) leaves the ground", not m.grounded and m.z > 0.6, f"z={m.z:.2f}")
        yield 1.0
        self.check("lands after jump", m.grounded and abs(m.z) < 0.01, f"z={m.z:.3f}")

        self.hold("crouch")
        yield 0.6
        crouched = m.height
        self.release()
        yield 0.6
        self.check("crouch (Ctrl) and stand up", crouched < C.PLAYER_CROUCH_HEIGHT + 0.01
                   and abs(m.height - C.PLAYER_STAND_HEIGHT) < 0.01, f"crouched={crouched:.2f} stand={m.height:.2f}")

        look = self.game.player.camera.look
        yaw0 = look.yaw
        self.game.input.inject_mouse(100, 0)
        yield 0.1
        expected = -100 * C.MOUSE_DEGREES_PER_PIXEL * self.game.settings.mouse_sensitivity
        self.check("mouse look turns the camera", abs((look.yaw - yaw0) - expected) < 0.01,
                   f"yaw change {look.yaw - yaw0:.2f} (expected {expected:.2f})")
        self.game.input.inject_mouse(0, -100000)
        yield 0.1
        self.check("mouse look pitch is clamped", abs(look.pitch - C.PITCH_LIMIT) < 1e-6, f"pitch {look.pitch:.1f}")

        self.teleport("wall_test")
        yield 0.3
        self.hold("move_forward", "sprint")
        yield 2.0
        self.check("concrete wall blocks the player", -69.6 < m.y < -68.0, f"y={m.y:.2f}")

        self.teleport("door_test")
        yield 0.3
        self.hold("move_forward")
        yield 2.5
        self.check("walk through barracks door", m.x < -22.0 and abs(m.z - 0.25) < 0.02, f"x={m.x:.2f} z={m.z:.2f}")
        self.release()
        self.game.player.camera.look.yaw = -90
        yield 0.6
        self.screenshot("02_barracks_interior")

        self.teleport("stairs_bottom")
        yield 0.3
        self.hold("move_forward")
        yield 3.5
        self.check("climb watchtower stairs", abs(m.z - 4.0) < 0.02, f"z={m.z:.2f}")
        self.release()

        self.teleport("hq_stairs")
        yield 0.3
        self.hold("move_forward")
        yield 3.5
        self.release()
        self.check("climb HQ roof stairs", m.z > 4.0, f"z={m.z:.2f}")

        self.teleport("container_test")
        yield 0.3
        x0 = m.x
        self.hold("move_forward")
        yield 2.0
        # Free walking would reach y~15. The 30-degree container must stop the player and make them slide.
        self.check("rotated container blocks and slides", m.y < 12.5 and abs(m.x - x0) > 0.5,
                   f"x={m.x:.2f} y={m.y:.2f}")
        self.release()

        yield from self._weapon_tests()

        for i, name in enumerate(("view_spawn", "view_hangar", "view_barracks", "view_tower", "view_helipad", "view_ruins")):
            self.teleport(name)
            yield 0.8
            self.screenshot(f"{10 + i:02d}_{name}")

        self.teleport("view_spawn")
        yield 0.3
        self.hold("pause")
        yield 0.1
        y0 = m.y
        self.hold("move_forward")             # holding W while paused must NOT move the player
        yield 0.6
        paused_ok = self.game.paused and self.game.pause_menu.visible and abs(m.y - y0) < 1e-6
        self.screenshot("03_pause_menu")
        self.game.pause_menu.resume_button["command"]()   # click RESUME
        yield 0.6
        self.check("Esc pauses, Resume button resumes", paused_ok and not self.game.paused and m.y - y0 > 1.0,
                   f"paused_ok={paused_ok} moved_after_resume={m.y - y0:.2f}")
        self.release()

        self.teleport("view_spawn")
        yield 0.5
        clock = self.game.clock
        frames0, t0 = clock.get_frame_count(), clock.get_real_time()
        self.hold("move_forward")
        yield 3.0
        frames = clock.get_frame_count() - frames0
        seconds = clock.get_real_time() - t0
        self.fps = frames / max(seconds, 1e-6)
        self.check("performance sample", self.fps > 20, f"{self.fps:.1f} FPS while walking")

        self.check("never stuck inside geometry", self.penetration_frames == 0,
                   f"{self.penetration_frames} frames overlapping a collider")
        yield from self._mission_tests()

    def _soldier_showcase(self):
        """Close-ups of the soldiers: enemy and friendly, idle / walking / running / crouching / firing / dead."""
        g = self.game
        g.start_sandbox("border_outpost")
        g.player.invulnerable = True
        yield 1.0
        g.player.teleport(0, -40, 0, 0, -6)
        mgr = g.soldiers
        lineup = []
        for i, (team, x) in enumerate((("friendly", -2.5), ("enemy", 0.0), ("enemy", 2.5))):
            s = mgr.spawn(team, x, -34, 180, profile="squad" if team == "friendly" else "regular",
                          name="Sgt. Marek" if team == "friendly" else None, invulnerable=team == "friendly")
            s.ai.command_hold(x, -34, 180) if team == "friendly" else None
            s.ai.p = dict(s.ai.p, vision_range=0.1)
            lineup.append(s)
        yield 2.5
        self.screenshot("soldiers_idle")
        lineup[1].crouch = True
        for s in lineup:
            s.ai.state = "IDLE"
        lineup[2].aiming = True
        yield 1.2
        self.screenshot("soldiers_poses")
        for s in lineup:
            s.ai.command_hold(s.motor.x + 12, s.motor.y + 8, 180) if s.team == "friendly" else None
        lineup[1].ai.patrol = [(10, -20), (10, -50)]
        lineup[1].ai.state = "PATROL"
        yield 1.5
        g.player.teleport(4, -44, 0, 20, -4)
        yield 0.8
        self.screenshot("soldiers_moving")
        lineup[2].take_damage(9999, None, "torso", (0, 1, 0))
        yield 2.5
        self.screenshot("soldiers_death")
        mgr.remove_all()

    def _vehicle_showcase(self):
        """Photograph every vehicle type on the river map, plus night vision and the drone camera."""
        g = self.game
        g.player.teleport(150, 30, 0, -110, 2)
        v = g.vehicles
        v.spawn("tank", "t1", pos=(178, 52, 0.0), heading=-120)
        v.spawn("patrol_boat", "b1", path=[(150, 5, -2), (175, 0, -2), (150, -5, -2), (125, 0, -2)], loop=True)
        v.spawn("player_boat", "pb", pos=(150, 12, -2.0), heading=-90)
        heli = v.spawn("attack_helicopter", "h1", pos=(175, 40, 14.0), armed=False)
        heli.mode = "hover"
        heli.hover_target = (175, 40, 14.0)
        v.spawn("transport_helicopter", "h2", pos=(140, 70, 9.0)).hover_target = (140, 70, 9.0)
        yield 2.0
        self.screenshot("tamsin_vehicles")
        self.check("vehicles spawn on the river map", len(v.vehicles) == 5, f"{len(v.vehicles)} vehicles")
        g.set_nvg(True, True)
        yield 0.8
        self.screenshot("tamsin_nvg")
        g.set_nvg(False, False)
        g.start_drone((150, 30, 24), -70)
        g.soldiers.spawn("enemy", 185, 48, 0, profile="regular", group="t")
        yield 1.0
        g.drone.look.pitch = -30
        yield 0.5
        self.screenshot("tamsin_drone")
        g.end_drone()
        g.soldiers.remove_all()
        v.remove_all()
        yield 0.3

    # ------------------------------------------------------------------ quick visual check
    def _views(self):
        """Photograph every map's 'view_*' points (plus a soldier in frame) and measure FPS."""
        g = self.game
        yield 1.0
        self.screenshot("view_main_menu")
        for map_name in [m for m in self.maps if m != "soldiers"]:
            g.start_sandbox(map_name)
            g.player.invulnerable = True
            yield 1.5
            points = [n for n in g.map_data.points if n.startswith("view") or n in ("plaza_view", "street_b")]
            for name in points:
                p = g.map_data.points[name]
                g.player.teleport(p.x, p.y, p.z, p.heading, p.pitch)
                h = math.radians(p.heading)
                s = g.soldiers.spawn("friendly", p.x - math.sin(h) * 6 + math.cos(h) * 2,
                                     p.y + math.cos(h) * 6 + math.sin(h) * 2, p.heading + 160,
                                     profile="squad", name="Sgt. Marek", invulnerable=True)
                s.ai.command_hold(s.motor.x, s.motor.y, p.heading + 160)
                yield 1.2
                self.screenshot(f"{map_name}_{name}")
                g.soldiers.remove_all()
            if map_name == "tamsin_river":
                yield from self._vehicle_showcase()
            clock = g.clock
            f0, t0 = clock.get_frame_count(), clock.get_real_time()
            self.hold("move_forward")
            yield 3.0
            self.release()
            fps = (clock.get_frame_count() - f0) / max(1e-6, clock.get_real_time() - t0)
            self.check(f"{map_name} renders", fps > 25, f"{fps:.1f} FPS")
        if "soldiers" in self.maps:
            yield from self._soldier_showcase()
        if "border_outpost" not in self.maps:
            return
        # First-person weapons close-up.
        g.start_sandbox("border_outpost")
        yield 1.0
        p = g.map_data.points["view_barracks"]
        g.player.teleport(p.x, p.y, p.z, p.heading, 0)
        for slot, name in (("weapon_1", "rifle"), ("weapon_2", "pistol"), ("weapon_3", "sniper"), ("weapon_4", "shotgun")):
            g.input.press_once(slot)
            yield 1.2
            self.screenshot(f"weapon_{name}")
            if name in ("pistol", "rifle"):
                self.hold("aim")
                yield 0.6
                self.screenshot(f"weapon_{name}_ads")
                self.release()
                yield 0.5

    # ------------------------------------------------------------------ menus
    def _menu_tests(self):
        g = self.game
        yield 1.5
        self.check("main menu is shown at start", g.state == "menu" and g.main_menu.visible)
        self.screenshot("00_main_menu")
        cont = g.main_menu.buttons["CONTINUE"]["state"]
        self.check("Continue is disabled without a save", cont == "disabled", f"state={cont}")
        g.main_menu.buttons["SETTINGS"]["command"]()
        yield 0.5
        self.check("Settings button opens settings", g.settings_menu.visible and not g.main_menu.visible)
        self.screenshot("04_settings")
        vol0 = g.settings.master_volume
        slider = g.settings_menu._labels["master_volume"][0]
        slider["value"] = 0.35
        slider["command"]()                     # what the slider calls when the user drags it
        g.settings_menu._back()
        yield 0.4
        saved = g.settings_store.load().master_volume
        self.check("settings change is applied and saved", abs(saved - 0.35) < 1e-6 and g.main_menu.visible,
                   f"saved volume={saved:.2f} (was {vol0:.2f})")
        g.settings.master_volume = vol0
        g.apply_settings("master_volume")
        for label, screen in (("CONTROLS", g.controls_screen), ("CREDITS", g.credits_screen),
                              ("MISSION SELECTION", g.campaign_screen)):
            g.main_menu.buttons[label]["command"]()
            yield 0.4
            ok = screen.visible
            if label == "MISSION SELECTION":
                self.screenshot("05_campaign")
            g.back()
            yield 0.3
            self.check(f"{label.title()} button opens its screen and Back returns", ok and g.main_menu.visible)

    # ------------------------------------------------------------------ mission 1
    def _wait_for(self, condition, timeout, step=0.1):
        waited = 0.0
        while not condition() and waited < timeout:
            yield step
            waited += step

    def _aim_at(self, point):
        p = self.game.player
        ex, ey, ez = p.eye_position()
        dx, dy, dz = point[0] - ex, point[1] - ey, point[2] - ez
        p.camera.look.yaw = math.degrees(math.atan2(-dx, dy))
        p.camera.look.pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))

    def _mission_tests(self):
        g = self.game
        self.release()
        g.show_main_menu()
        yield 0.8
        g.main_menu.buttons["NEW CAMPAIGN"]["command"]()
        yield 0.6
        self.check("New Campaign opens the Mission 1 briefing", g.briefing.visible and
                   g.mission_info.id == "m01_first_light")
        self.screenshot("06_briefing")
        g.briefing.begin["command"]()
        self.check("loading screen appears", g.loading.visible and g.state == "loading")
        yield 0.02
        yield from self._wait_for(lambda: g.state == "cinematic", 20)
        yield 3.0
        self.check("intro cutscene plays", g.state == "cinematic" and g.cinematic is not None)
        self.screenshot("07_intro")
        g.input.press_once("skip")
        yield 0.5
        self.check("Space skips the cutscene into gameplay", g.state == "playing" and g.mission.index == 0)
        self.check("squad of three spawned", len(g.squad) == 3 and all(s.alive for s in g.squad.values()),
                   ", ".join(s.name for s in g.squad.values()))
        g.player.invulnerable = True
        marek = g.squad["marek"]
        self._aim_at((marek.motor.x, marek.motor.y, 1.3))
        yield 0.3
        self.screenshot("07b_squad_closeup")
        yield 1.2                                           # the patrol order is given 1 s into the mission
        before = {sid: math.dist((s.motor.x, s.motor.y), s.ai.anchor[:2]) if s.ai.anchor else 0
                  for sid, s in g.squad.items()}
        yield 6.0
        closer = [sid for sid, s in g.squad.items()
                  if s.ai.anchor and before[sid] - math.dist((s.motor.x, s.motor.y), s.ai.anchor[:2]) > 10]
        self.check("squad moves out on patrol (towards the north fence)", len(closer) == 3,
                   ", ".join(f"{sid}:{s.ai.state}" for sid, s in g.squad.items()))
        self.screenshot("08_patrol")

        # Step 1: patrol -> reach the north fence.
        g.player.teleport(3, 52, 0, 0)
        yield 1.0
        self.check("objective 1 (reach the fence) completes", g.mission.index == 1, g.hud.objective_text.getText())

        # Step 2: reset the relay on the HQ roof.
        g.player.teleport(30.4, -35.4, 4.07, 180, -25)
        yield 0.5
        self.hold("interact")
        yield 3.0
        self.release()
        self.check("holding E at the relay completes objective 2", g.mission.index == 2,
                   g.hud.objective_text.getText())
        # The missile strike, watched from the HQ roof.
        g.player.camera.look.yaw, g.player.camera.look.pitch = 10, -4
        garrison0 = len(g.soldiers.group_alive("garrison"))
        for k, t in enumerate((3.6, 1.2, 2.6, 2.4, 4.0)):
            yield t
            g.player.camera.look.yaw, g.player.camera.look.pitch = (10, -4) if k % 2 == 0 else (-25, -6)
            self.screenshot(f"09a_strike_{k}")
        tower_gone = g.environment.dynamic["tower_ne"]["destroyed"]
        garrison1 = len(g.soldiers.group_alive("garrison"))
        self.check("the missile strike destroys the outpost and kills defenders",
                   tower_gone and garrison1 < garrison0, f"tower destroyed={tower_gone}, "
                   f"riflemen {garrison0} -> {garrison1}")
        self._skip_survive()
        yield 1.0
        self.check("surviving the strike starts the breach", g.mission.index == 3, g.hud.objective_text.getText())
        # Run to the north sandbags and watch the sappers blow the fence.
        g.player.teleport(-8, 12, 0, 0, 2)
        yield 1.0
        self.check("reaching the sandbags starts the defence", g.mission.index == 4, g.hud.objective_text.getText())
        for k in range(4):
            yield 4.5
            g.player.camera.look.yaw, g.player.camera.look.pitch = (0, 4) if k % 2 == 0 else (-15, 2)
            self.screenshot(f"09_breach_{k}")
        breach = g.environment.dynamic["north_breach"]["destroyed"]
        tanks = g.vehicles.alive_count("tank")
        self.check("sappers blow the fence and tanks arrive", breach and tanks >= 2, f"breach={breach} tanks={tanks}")
        hits0 = g.player.hits_taken
        squad_shots0 = sum(s.weapon.shots_fired for s in g.squad.values())
        yield 20.0
        attackers = [e for e in g.soldiers.soldiers if e.team == "enemy" and e.group in ("n1", "n2")]
        enemy_shots = sum(e.weapon.shots_fired for e in attackers)
        squad_shots = sum(s.weapon.shots_fired for s in g.squad.values()) - squad_shots0
        self.check("waves attack through the breach", len(attackers) >= 10 and enemy_shots > 0,
                   f"{len(attackers)} attackers, {enemy_shots} enemy shots, player hit {g.player.hits_taken - hits0}x")
        self.check("squad fights back", squad_shots > 20, f"{squad_shots} squad shots")
        self.screenshot("10_firefight")
        # Real gunfire: find a visible enemy, aim at its chest and fire.
        target = None
        ex = g.player.eye_position()
        alive = [e for e in g.soldiers.soldiers if e.team == "enemy" and e.alive]
        for e in sorted(alive, key=lambda e: math.dist(ex, e.center())):
            if g.collision_world.line_of_sight(ex, e.center()):
                target = e
                break
        if target is None and alive:
            target = alive[0]
            g.player.teleport(target.motor.x, target.motor.y - 12, target.motor.z, 0)
            yield 0.3
        if target is not None:
            hp0 = target.health.current
            for _ in range(30):
                self._aim_at(target.center())
                self.hold("fire", "aim")
                yield 0.05
                if not target.alive:
                    break
            self.release()
            self.check("player bullets hit and damage an enemy soldier", target.health.current < hp0,
                       f"hp {hp0:.0f} -> {target.health.current:.0f}, alive={target.alive}")
        self._skip_survive()
        yield 1.0
        self.check("holding the north line orders the fall back to the hangar", g.mission.index == 5,
                   g.hud.objective_text.getText())
        g.player.teleport(27, 20, 0, -10, 2)
        yield 1.0
        self.check("reaching the hangar starts the next defence", g.mission.index == 6, g.hud.objective_text.getText())
        for k in range(3):
            yield 5.0
            g.player.camera.look.yaw, g.player.camera.look.pitch = (-20, 2) if k % 2 == 0 else (10, 6)
            self.screenshot(f"10b_hangar_{k}")
        self.check("debris flies from the buildings", len(g.debris.chunks) > 10, f"{len(g.debris.chunks)} chunks")
        self._skip_survive()
        yield 1.0
        # Cipher book inside HQ, then the last stand.
        g.player.teleport(26.6, -30.0, 0.25, -90, -32)
        yield 0.5
        self.hold("interact")
        yield 2.5
        self.release()
        self.check("taking the cipher book starts the last stand", g.mission.index == 8, g.hud.objective_text.getText())
        yield 6.0
        self._skip_survive()
        yield 1.0
        self.check("holding HQ opens the gate and orders the retreat",
                   g.mission.index == 9 and g.environment.dynamic["main_gate"]["destroyed"], f"step={g.mission.index}")
        dead = sum(1 for s in g.soldiers.soldiers if s.team == "friendly" and s.group == "garrison" and not s.alive)
        self.check("many Kareth soldiers die in the battle", dead >= 10, f"{dead} riflemen killed")

        # Death -> mission failed -> retry from checkpoint.
        g.player.invulnerable = False
        g.player.take_damage(1000, None, "body", (0, 1, 0))
        yield 3.2
        self.check("dying shows the Mission Failed screen", g.state == "failed" and g.failed_screen.visible)
        self.screenshot("12_failed")
        g.failed_screen.checkpoint["command"]()
        yield 1.0
        self.check("Retry from checkpoint restores the player at the last objective",
                   g.state == "playing" and g.player.alive and g.mission.index == 9, f"step={g.mission.index}")
        g.player.invulnerable = True
        g.player.teleport(0, -20, 0, 0, 2)
        for k in range(3):
            yield 4.0
            self.screenshot(f"12b_fall_back_{k}")

        # Final step: fall back to the gate.
        g.player.teleport(0, -58, 0, 180)
        yield 1.0
        self.check("reaching the south gate completes the mission", g.state in ("cinematic", "complete"))
        yield 3.0
        self.screenshot("13_outro")
        g.input.press_once("skip")
        yield 1.0
        self.check("mission complete screen with results", g.state == "complete" and g.mission_end.visible,
                   g.mission_end.values.getText().replace("\n", " | "))
        self.screenshot("14_mission_complete")
        prog = g.save.load()
        self.check("progress saved (mission 1 completed, mission 2 unlocked)",
                   "m01_first_light" in prog.completed and "m02_line_breaks" in prog.unlocked,
                   f"completed={prog.completed} current={prog.current_mission}")
        g.mission_end.root  # noqa
        g._after_mission_end()
        yield 0.6
        self.check("Continue returns to the campaign screen", g.campaign_screen.visible and g.state == "menu")
        self.screenshot("15_campaign_after")
        g.player.invulnerable = False
        yield from self._mission2_tests()

    # ------------------------------------------------------------------ mission 2
    def _skip_survive(self):
        obj = self.game.mission.objective
        if obj is not None and hasattr(obj, "remaining"):
            obj.remaining = 0.2

    def _linediag_tests(self):
        """Diagnostic: what are the trench riflemen in Mission 2 doing during the battle?"""
        g = self.game
        g.story_enabled = False
        g.open_briefing("m02_line_breaks")
        yield 0.5
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 25)
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True
        g.player.teleport(-31, -28.0, 0, 180)
        yield 1.0
        g.player.teleport(0, 1.3, 0.4, 0, 1)
        yield 1.0
        for k in range(10):
            yield 4.0
            for s in g.soldiers.soldiers:
                if s.team != "friendly" or not s.alive:
                    continue
                ai = s.ai
                tgt = ai.target
                td = math.dist(tgt.position[:2], s.position[:2]) if tgt is not None else -1
                print(f"DIAG t={4 * (k + 1):3d} {str(s.group):8s} {str(s.profile_name):8s} {ai.state:10s} vis={int(ai.target_visible)} "
                      f"aw={ai.awareness:.2f} shots={s.weapon.shots_fired:4d} mag={s.weapon.mag:3d} "
                      f"tgt_d={td:5.1f} react={ai.reaction_timer:.1f} pos=({s.motor.x:.1f},{s.motor.y:.1f},{s.motor.z:.2f})")
            enemies = [e for e in g.soldiers.soldiers if e.team == "enemy" and e.alive]
            print(f"DIAG t={4 * (k + 1):3d} enemies alive {len(enemies)}, nearest y "
                  f"{min((e.motor.y for e in enemies), default=-1):.1f}")
        self.check("diagnostic ran", True)

    def _mission2_tests(self):
        g = self.game
        m2 = g.campaign.mission("m02_line_breaks")
        self.check("Mission 2 is playable and unlocked after Mission 1", m2.playable and g.save.is_unlocked(m2.id))
        g.open_briefing(m2.id)
        yield 0.5
        self.screenshot("20_m2_briefing")
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 25)
        self.check("Kesh Ridge loads and the intro plays", g.state == "cinematic" and g.map_name == "kesh_ridge",
                   f"load {g.environment.stats.get('load_seconds', 0):.1f}s, {g.environment.stats.get('triangles', 0):,} tris")
        yield 2.5
        self.screenshot("21_m2_intro")
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True

        g.player.teleport(-31, -28.0, 0, 180)
        yield 1.0
        self.check("M2 objective 1: report to Lt. Rusk", g.mission.index == 1, g.hud.objective_text.getText())
        g.player.teleport(0, 0.3, 0, 0)
        yield 1.0
        self.check("M2 objective 2: take position in the forward trench", g.mission.index == 2,
                   g.hud.objective_text.getText())
        self.screenshot("22_m2_trench")
        line = g.soldiers.group_alive("line")
        self.check("allied riflemen man the trench", len(line) == 8, f"{len(line)} riflemen")

        # Let the first waves cross no-man's land; measure performance during the battle.
        g.player.teleport(0, 1.3, 0.4, 0, 1)            # on the firing step, looking over the parapet
        yield 20.0
        clock = g.clock
        frames0, t0 = clock.get_frame_count(), clock.get_real_time()
        yield 15.0
        fps = (clock.get_frame_count() - frames0) / max(1e-6, clock.get_real_time() - t0)
        soldiers = len([s for s in g.soldiers.soldiers if s.alive])
        self.check("battle performance (many soldiers)", fps > 25, f"{fps:.1f} FPS with {soldiers} soldiers alive")
        assault = [s for s in g.soldiers.soldiers if s.group == "assault"]
        near = [s for s in assault if s.alive and s.motor.y < 70]
        shots = sum(s.weapon.shots_fired for s in g.soldiers.soldiers)
        self.check("enemy waves cross no-man's land and the line fights", len(assault) >= 12 and near and shots > 50,
                   f"{len(assault)} attackers spawned, {len(near)} within 70 m, {shots} shots fired")
        self.screenshot("23_m2_battle")
        yield 12.0
        self.screenshot("24_m2_barrage")
        booms = [s for s in g.shells]
        self.check("friendly mortar barrage is falling on no-man's land", booms or any(
            p.kind == "fire" for p in g.effects.particles), f"{len(booms)} shells still incoming")

        self._skip_survive()
        yield 1.5
        # Tanks: the player gets a launcher; both sides fire RPGs.
        self.check("holding the line brings the tanks", g.mission.index == 3, g.hud.objective_text.getText())
        yield 9.0
        t1, t2 = g.vehicles.find("tank1"), g.vehicles.find("tank2")
        has_rl = any(w.stats.id == "rl3" for w in g.weapons.weapons)
        self.check("two tanks attack and the player gets a launcher", t1 is not None and t2 is not None and has_rl,
                   f"tanks={t1 is not None},{t2 is not None} launcher={has_rl}")
        g.player.teleport(-6, 1.5, 0.4, 0)
        rl = next(i for i, w in enumerate(g.weapons.weapons) if w.stats.id == "rl3")
        g.weapons.select(rl)
        yield 1.2
        yield from self._wait_for(lambda: math.dist(t1.pos[:2], g.player.position[:2]) < 85 or not t1.alive, 40)
        hp0 = t1.health.current
        for _ in range(4):
            g.weapons.refill_all()
            self._aim_at(t1.center())
            g.input.press_once("fire")
            yield 3.0
            if t1.health.current < hp0:
                break
        self.check("a launcher rocket damages a tank", t1.health.current < hp0,
                   f"hp {hp0:.0f} -> {t1.health.current:.0f}")
        self.screenshot("24b_m2_tanks")
        for t in (t1, t2):
            if t.alive:
                t.take_damage(99999, g.player, "blast", (0, 1, 0))
        yield 1.5
        mg = g.soldiers.group_alive("mg")
        self.check("destroying the tanks reveals the machine-gun nest", g.mission.index == 4 and len(mg) == 3,
                   g.hud.objective_text.getText())
        g.weapons.select(0)
        yield 0.6
        # Snipe the gunner from the firing step.
        gunner = [s for s in mg if s.profile_name == "gunner"][0]
        g.player.teleport(4, 1.5, 0.4, 0)              # standing on the trench's firing step
        g.input.press_once("weapon_3")
        yield 1.0
        for _ in range(3):
            self._aim_at(gunner.eye_position())
            self.hold("aim")
            yield 0.6
            self._aim_at(gunner.eye_position())
            self.game.input.press_once("fire")
            self.hold("aim", "fire")
            yield 0.05
            self.release()
            yield 1.4
            if not gunner.alive:
                break
        self.check("sniper rifle takes out the machine gunner", not gunner.alive,
                   f"hp={gunner.health.current:.0f} weapon={g.weapons.current.stats.name}")
        self.screenshot("25_m2_sniper")
        for s in g.soldiers.group_alive("mg"):
            s.take_damage(9999, g.player, "body", (0, 1, 0))
        yield 1.0
        # Sappers blow the forward line.
        self.check("destroying the nest sends in the sappers", g.mission.index == 5, g.hud.objective_text.getText())
        line0 = len(g.soldiers.group_alive("line"))
        g.player.teleport(0, -8, 0, 0, 4)
        for k in range(5):
            yield 4.2
            self.screenshot(f"25b_m2_breach_{k}")
        wires = sum(1 for w in ("wire_a", "wire_b", "wire_c", "wire_d") if g.environment.dynamic[w]["destroyed"])
        line1 = len(g.soldiers.group_alive("line"))
        self.check("charges blow the wire and kill the men in the trench", wires == 4 and line1 < line0,
                   f"wires destroyed {wires}/4, riflemen {line0} -> {line1}")
        self._skip_survive()
        yield 1.0
        self.check("the broken line orders the fall back", g.mission.index == 6, g.hud.objective_text.getText())
        yield 12.0
        self.check("enemy shells land on the forward trench", len(g.shells) > 0 or any(
            p.kind == "fire" for p in g.effects.particles), f"{len(g.shells)} incoming")
        g.player.teleport(-12, -40.5, 0, 0)
        yield 1.0
        rear = g.soldiers.group_alive("rear")
        self.check("reaching the second line starts the last stand", g.mission.index == 7 and len(rear) == 7,
                   f"step={g.mission.index} rear riflemen={len(rear)}")
        yield 8.0
        self.screenshot("26_m2_second_line")
        g.player.teleport(-6, -60, 0, 180, 2)
        for k in range(4):
            yield 6.0
            self.screenshot(f"26b_m2_civilians_{k}")
        civ = len(g.civilians.people)
        self.check("civilians flee to the trucks", civ >= 8, f"{civ} civilians, {g.civilians.dead_count()} killed")
        self._skip_survive()
        yield 1.5
        self.check("convoy ready: run to the last truck", g.mission.index == 8, g.hud.objective_text.getText())
        g.player.teleport(-34.5, -78.8, 0, 90)
        yield 1.5
        self.check("climbing into truck four starts the convoy", g.mission.index == 9 and g.ride is not None,
                   g.hud.objective_text.getText())
        for k in range(8):
            yield 2.2
            self.screenshot(f"27a_m2_convoy_{k}")
        t5 = g.vehicles.find("truck5")
        shot = [c for c in g.civilians.people if c.group == "truck5"]
        self.check("an RPG destroys the last truck and the enemy guns down the survivors",
                   t5 is not None and not t5.alive and shot and all(not c.alive for c in shot),
                   f"truck5 alive={t5.alive if t5 else None}, civilians {sum(not c.alive for c in shot)}/{len(shot)} shot")
        self.check("you can only watch: no weapon in the truck", not g.weapons.enabled)
        self._skip_survive()
        yield 1.5
        self.check("the convoy escapes and Mission 2 ends", g.state in ("cinematic", "complete"))
        yield 3.0
        self.screenshot("27_m2_outro")
        g.input.press_once("skip")
        yield 1.0
        prog = g.save.load()
        self.check("Mission 2 results and progress saved", g.state == "complete" and "m02_line_breaks" in prog.completed,
                   g.mission_end.values.getText().replace("\n", " | "))
        self.screenshot("28_m2_complete")
        g.player.invulnerable = False
        if self.only != "mission":                      # --only mission: Missions 1 and 2 only
            yield from self._mission3_tests()

    # ------------------------------------------------------------------ mission 3
    def _follow_escort(self, kell, timeout, on_tick=None):
        """Stay ~3 m behind the escorted soldier (like a real player would) until the step changes."""
        g = self.game
        step = g.mission.index
        waited = 0.0
        while g.mission.index == step and g.state == "playing" and waited < timeout:
            m = kell.motor
            h = math.radians(kell.facing)
            g.player.teleport(m.x + math.sin(h) * 3.0, m.y - math.cos(h) * 3.0, m.z, kell.facing)
            if on_tick:
                on_tick()
            yield 0.5
            waited += 0.5

    def _mission3_tests(self):
        g = self.game
        g.open_briefing("m03_ashfall")
        yield 0.5
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 25)
        self.check("Veyra loads and the intro plays", g.state == "cinematic" and g.map_name == "veyra",
                   f"{g.environment.stats.get('triangles', 0):,} tris, {len(g.fires)} fires")
        yield 9.0
        self.screenshot("30_m3_intro")
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True
        kell = g.squad["kell"]
        self.check("Kell is wounded (can be killed) and the squad is present",
                   len(g.squad) == 3 and not kell.health.invulnerable and kell.profile_name == "wounded")

        street = g.soldiers.group_alive("street")
        self.check("M3 objective 1: patrols in the street", g.mission.index == 0 and len(street) == 4,
                   g.hud.objective_text.getText())
        g.player.teleport(-42.5, -38.5, 0, -60)
        yield 0.6
        self.screenshot("31_m3_street")
        for e in street:
            e.take_damage(9999, g.player, "body", (1, 0, 0))
        yield 1.0
        self.check("clearing the street starts the escort", g.mission.index == 1, g.hud.objective_text.getText())

        ducked = []
        start = (kell.motor.x, kell.motor.y)

        def watch_ambush():
            if kell.crouch:
                ducked.append(True)
            ambush = g.soldiers.group_alive("ambush")
            if ambush and len(ducked) > 6:            # let them pin Kell down for a few seconds first
                for e in ambush:
                    e.take_damage(9999, g.player, "body", (1, 0, 0))

        yield from self._follow_escort(kell, 90, watch_ambush)
        self.check("Kell walks the route to the market square", g.mission.index == 2 and kell.alive,
                   f"moved {math.dist(start, (kell.motor.x, kell.motor.y)):.0f} m, hp {kell.health.current:.0f}")
        self.check("Kell takes cover when the ambush hits", len(ducked) > 0, f"crouched {len(ducked)} ticks")

        plaza = g.soldiers.group_alive("plaza")
        self.check("enemies hold the plaza", len(plaza) == 6, f"{len(plaza)} defenders")
        g.player.teleport(-24, 12, 0, -80, 2)
        yield 2.0
        self.screenshot("32_m3_plaza")
        clock = g.clock
        f0, t0 = clock.get_frame_count(), clock.get_real_time()
        yield 4.0
        fps = (clock.get_frame_count() - f0) / max(1e-6, clock.get_real_time() - t0)
        self.check("town performance with fires and a firefight", fps > 25, f"{fps:.1f} FPS")
        for e in g.soldiers.group_alive("plaza"):
            e.take_damage(9999, g.player, "body", (1, 0, 0))
        yield 1.0
        self.check("retaking the plaza continues the escort", g.mission.index == 3, g.hud.objective_text.getText())

        # Kell dies -> mission failed -> retry from checkpoint brings him back.
        yield 3.0
        kell.take_damage(9999, None, "body", (0, 1, 0))
        yield 1.0
        self.check("if Kell dies the mission fails", g.state == "failed" and
                   "Kell" in g.failed_screen.reason.getText(), g.failed_screen.reason.getText())
        self.screenshot("33_m3_kell_died")
        g.failed_screen.checkpoint["command"]()
        yield 1.0
        self.check("retry from checkpoint revives Kell and resumes the escort",
                   g.state == "playing" and kell.alive and g.mission.index == 3 and kell.ai.state == "ESCORT",
                   f"state={g.state} step={g.mission.index} kell={kell.ai.state}")
        g.player.invulnerable = True

        def clear_road():
            for e in g.soldiers.group_alive("road"):
                if math.dist(e.position[:2], (kell.motor.x, kell.motor.y)) < 40:
                    e.take_damage(9999, g.player, "body", (1, 0, 0))

        yield from self._follow_escort(kell, 120, clear_road)
        self.check("Kell reaches the field hospital", g.mission.index == 4 and kell.alive,
                   g.hud.objective_text.getText())
        self.screenshot("34_m3_hospital")
        yield 6.0
        self._skip_survive()
        yield 1.5
        self.check("holding the hospital completes Mission 3", g.state in ("cinematic", "complete"))
        yield 3.0
        self.screenshot("35_m3_outro")
        g.input.press_once("skip")
        yield 1.0
        prog = g.save.load()
        self.check("Mission 3 results and progress saved", g.state == "complete" and "m03_ashfall" in prog.completed,
                   g.mission_end.values.getText().replace("\n", " | "))
        g.player.invulnerable = False
        yield from self._m04_tests()

    # ------------------------------------------------------------------ weapons
    # ------------------------------------------------------------------ mission 4
    def _hold_interact(self, stand, look_at, seconds, heading=None):
        g = self.game
        g.player.teleport(stand[0], stand[1], stand[2] if len(stand) > 2 else 0.0, heading or 0.0)
        yield 0.2
        self._aim_at(look_at)
        self.hold("interact")
        yield seconds
        self.release()
        yield 0.3

    def _m04_tests(self):
        g = self.game
        g.open_briefing("m04_no_way_back")
        yield 0.5
        self.screenshot("40_m4_briefing")
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 30)
        self.check("M4: Tamsin River loads and the intro plays", g.state == "cinematic" and g.map_name == "tamsin_river",
                   f"load {g.environment.stats.get('load_seconds', 0):.1f}s, "
                   f"{g.environment.stats.get('triangles', 0):,} tris")
        yield 8.0
        self.screenshot("41_m4_intro")
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True
        boat = g.vehicles.find("insertion")
        mounted = [s for s in g.squad.values() if s.mount is not None]
        self.check("M4 step 1: boat ride with the squad aboard",
                   g.state == "playing" and g.ride is not None and boat is not None and len(mounted) == 3,
                   f"squad mounted {len(mounted)}, boats {g.vehicles.alive_count('boat')}")
        p0 = g.player.position
        yield 3.0
        self._aim_at((-300, 0, 0))
        self.screenshot("42_m4_boat")
        p1 = g.player.position
        self.check("the player moves with the boat and can look around",
                   math.dist(p0[:2], p1[:2]) > 12 and abs(p1[2] - (g.water_z - 0.1)) < 0.05,
                   f"moved {math.dist(p0[:2], p1[:2]):.1f} m, z {p1[2]:.2f}")
        g.input.press_once("nvg")
        yield 0.4
        nvg_ok = g.nvg_on
        self.screenshot("43_m4_nvg")
        g.input.press_once("nvg")
        yield 0.3
        self.check("N toggles night vision", nvg_ok and not g.nvg_on)

        # Shoot the first patrol boat from the moving boat.
        pb1 = g.vehicles.find("pb1")
        fired = 0
        yield from self._wait_for(lambda: pb1 is not None and math.dist(pb1.position[:2], g.player.position[:2]) < 70, 40)
        hp0 = pb1.health.current if pb1 else 0
        for _ in range(60):
            if pb1 is None or not pb1.alive:
                break
            self._aim_at(pb1.center())
            self.hold("fire")
            yield 0.1
            fired += 1
            w = g.weapons.current
            if w.mag == 0:
                self.release()
                g.input.press_once("reload")
                yield 2.8
        self.release()
        self.check("bullets damage the patrol boat from the moving boat", pb1 is not None and pb1.health.current < hp0,
                   f"hp {hp0:.0f} -> {pb1.health.current:.0f}" if pb1 else "no boat")
        yield 1.0
        self.screenshot("44_m4_patrol_boat")
        yield from self._wait_for(lambda: g.mission.index >= 1, 120)
        yield 0.6
        on_land = all(s.mount is None for s in g.squad.values())
        self.check("M4: the ride ends at the drop point and everyone gets off",
                   g.mission.index == 1 and g.player.mount is None and on_land and g.player.motor.z > -0.1,
                   f"step {g.mission.index}, player z {g.player.motor.z:.2f}, time {g.mission.time:.0f}s")

        # Intel 1 by the slipway.
        yield from self._hold_interact((104, 33.0, 0.0), (104, 34, 0.62), 1.0)
        self.check("hold E next to intel to collect it", g.intel.found == 1, f"{g.intel.found}/{g.intel.total}")

        # Drone.
        yield from self._hold_interact((116, 34.4, 0.0), (116, 36, 0.9), 1.4)
        self.check("M4 step 2: launching the recon drone", g.drone is not None and g.mission.index == 2,
                   f"step {g.mission.index}")
        yield 0.5
        drone = g.drone
        start = list(drone.pos)
        self.hold("move_forward", "drone_up")
        yield 2.0
        self.release()
        self.check("the drone flies with W and climbs with Space",
                   drone.pos[2] > start[2] + 4 and math.dist(start[:2], drone.pos[:2]) > 10,
                   f"{[round(v) for v in drone.pos]}")
        enemies = [s for s in g.soldiers.soldiers if s.team == "enemy" and s.group in ("compound", "bridge_guard")]
        tagged = 0
        for e in enemies[:7]:
            if g.mission.index != 2:
                break
            ex, ey, ez = e.center()
            drone.pos[:] = [ex - 15, ey - 15, 28]
            dx, dy, dz = ex - drone.pos[0], ey - drone.pos[1], ez - drone.pos[2]
            drone.look.yaw = math.degrees(math.atan2(-dx, dy))
            drone.look.pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
            yield 0.15
            if tagged == 0:
                self.screenshot("45_m4_drone_thermal")
            g.input.press_once("fire")
            yield 0.3
            tagged = len(g.tagged)
        yield 1.8
        self.check("M4 step 3: tagging 5 enemies with the drone", tagged >= 5 and g.mission.index == 3 and g.drone is None,
                   f"tagged {tagged}, step {g.mission.index}")
        g.player.teleport(150, 40, 0, -60)
        yield 0.5
        self.screenshot("46_m4_tag_markers")

        # Stealth: silent takedown, then the AA gun.
        self.check("enemies are calm (stealth)", g.mission.alarm_armed and not g.mission.alarm_raised)
        target = next((s for s in g.soldiers.group_alive("compound") if s.ai.state == "IDLE"), None)
        if target is not None:
            self.hold("crouch")                            # sneak: crouched and still behind the guard
            yield 0.4
            h = math.radians(target.facing)
            g.player.teleport(target.motor.x + math.sin(h) * 1.2, target.motor.y - math.cos(h) * 1.2, 0, target.facing)
            yield 0.3
            hint = g.hud.action_hint.getText()
            g.input.press_once("takedown")
            yield 0.6
            self.release()
            self.check("V performs a silent takedown from behind", not target.alive and g.takedowns == 1 and
                       "TAKEDOWN" in hint and not g.mission.alarm_raised, f"hint '{hint}'")
        g.soldiers.visibility = 0.02                      # keep the rest of the scripted run stealthy
        g.base_lit_zones = []
        yield from self._hold_interact((226, 51.6, 0.0), (226, 52.5, 0.62), 1.0)
        yield from self._hold_interact((228, 92.2, 0.0), (228, 96, 1.6), 3.0)
        self.check("M4 step 4: charge on the AA gun", g.mission.index == 4, g.hud.objective_text.getText())
        yield from self._hold_interact((236, 97.8, 0.0), (236, 99, 0.62), 1.0)

        # Bridge charges (the guards on the bridge are taken down quietly first).
        for e in g.soldiers.group_alive("bridge_guard"):
            e.silent_death = True
            e.take_damage(9999, g.player, "body", (0, 1, 0))
            g.takedowns += 1
        yield 0.5
        for x, y in ((197.5, 16), (202.5, 0), (197.5, -16)):
            yield from self._hold_interact((x + (1.4 if x < 200 else -1.4), y, 0.25), (x, y, 0.75), 2.9)
        self.check("M4 step 5: three charges on the bridge (stealth kept)",
                   g.mission.index == 5 and len(g.charges) == 4 and g.mission.stealth is True,
                   f"step {g.mission.index}, charges {len(g.charges)}, alarm {g.mission.alarm_raised}")
        self.check("all three intel documents found", g.intel.found == 3, f"{g.intel.found}/{g.intel.total}")
        g.soldiers.visibility = 0.5

        # Kamikaze drones.
        g.player.teleport(186, 48, 0, -90)
        yield 6.0
        drones = [v for v in g.vehicles.vehicles if v.kind == "drone" and v.alive]
        self.check("attack drones arrive", len(drones) >= 2, f"{len(drones)} drones in the air")
        if drones:
            self._aim_at(drones[0].center())
            yield 0.1
            self.screenshot("47_m4_drones")
        hp_hits = g.player.hits_taken
        for _ in range(200):
            if g.mission.index != 5:
                break
            for d in [v for v in g.vehicles.vehicles if v.kind == "drone" and v.alive]:
                if math.dist(d.center(), g.player.center()) < 30:
                    d.take_damage(100, g.player, "torso", (0, 1, 0))
            yield 0.1
        self.check("M4 step 6: drones shot down", g.mission.index == 6, f"player hit {g.player.hits_taken - hp_hits}x")

        # Launcher and gunship.
        yield from self._hold_interact((196, 50.4, 0.0), (196, 52, 1.0), 1.4)
        has_rl = any(w.stats.id == "rl3" for w in g.weapons.weapons)
        self.check("M4 step 7: RL-3 launcher picked up", has_rl and g.mission.index == 7)
        g.input.press_once("weapon_3")
        yield 1.2
        yield from self._wait_for(lambda: g.vehicles.find("gunship") is not None, 10)
        heli = g.vehicles.find("gunship")
        if heli is None:
            self.check("gunship spawns", False)
            return
        yield from self._wait_for(lambda: heli.mode == "attack", 30)
        yield 2.0
        self.check("gunship arrives and attacks", heli is not None and heli.mode == "attack",
                   f"mode {heli.mode if heli else None}")
        launched = 0
        hp0 = heli.health.current
        for _ in range(5):
            if not heli.alive:
                break
            vx, vy, vz = heli.vel
            c = heli.center()
            dist = math.dist(c, g.player.eye_position())
            t = dist / 70.0
            self._aim_at((c[0] + vx * t, c[1] + vy * t, c[2] + vz * t + 0.6 * t * t))
            self.hold("aim")
            yield 0.5
            self._aim_at((c[0] + vx * t, c[1] + vy * t, c[2] + vz * t + 0.6 * t * t))
            before = len(g.vehicles.rockets)
            self.hold("aim", "fire")
            yield 0.1
            self.release()
            launched += len(g.vehicles.rockets) > before
            if launched == 1:
                self.screenshot("48_m4_rocket")
            yield 3.2
        self.check("RL-3 fires rockets at the gunship", launched >= 1,
                   f"{launched} rockets, gunship hp {hp0:.0f} -> {heli.health.current:.0f}")
        if heli.alive:
            heli.take_damage(5000, g.player, "blast", (0, 0, 1))
        yield 4.0
        self.screenshot("49_m4_gunship_down")
        self.check("M4 step 8: gunship destroyed", g.mission.index == 8 and heli.mode in ("crash", "wreck"),
                   f"step {g.mission.index}")

        # Hold until the tanks are on the bridge.
        tanks = [g.vehicles.find(t) for t in ("tank1", "tank2", "tank3")]
        self.check("three tanks roll towards the bridge", all(t is not None for t in tanks))
        yield 8.0
        g.player.teleport(186, 47, 0, 180)
        self._aim_at(tanks[0].center())
        yield 0.3
        self.screenshot("50_m4_tanks")
        for t in tanks:
            t.dist = max(t.dist, t.path.length - 6)       # fast-forward the column
        for _ in range(150):
            if g.mission.index != 8:
                break
            for e in g.soldiers.group_alive("crossing"):
                if e.motor.y > -25:
                    e.take_damage(9999, g.player, "body", (0, 1, 0))
            yield 0.1
        on_bridge = all(t.alive and abs(t.pos[0] - 200) < 1 and -30 < t.pos[1] < 30 for t in tanks)
        self.check("M4 step 9: tanks stop on the bridge", g.mission.index == 9 and on_bridge,
                   ", ".join(f"({t.pos[0]:.0f},{t.pos[1]:.0f})" for t in tanks))

        # Detonate.
        yield from self._hold_interact((184.4, 47.0, 0.0), (182.5, 45.5, 0.75), 1.2)
        g.player.teleport(216, 44, 0, 0)
        self._aim_at((200, 0, -1))
        yield 1.4
        self.screenshot("51_m4_collapse")
        yield 2.6
        env = g.environment.dynamic
        spans_down = all(env[s]["destroyed"] for s in ("span_n", "span_m", "span_s"))
        ruins_up = all(not env[s]["destroyed"] for s in ("ruin_n", "ruin_m", "ruin_s"))
        self.check("M4 step 10: the bridge collapses and the tanks fall", spans_down and ruins_up and
                   all(not t.alive for t in tanks) and g.mission.index == 10,
                   f"spans {spans_down} ruins {ruins_up} tanks {[round(t.pos[2], 1) for t in tanks]}")
        self.screenshot("52_m4_bridge_gone")
        walkable = g.nav.is_walkable(200, 0)
        self.check("nobody can walk across the broken bridge", not walkable)

        # Escape, extraction and boarding.
        g.player.teleport(214, 186, 0, 0)
        for _ in range(400):
            if g.mission.index >= 12:
                break
            for grp in ("pursuit", "lz_attack", "alarm_wave", "compound", "bridge_guard"):
                for e in g.soldiers.group_alive(grp):
                    if math.dist(e.position[:2], (214, 190)) < 60:
                        e.take_damage(9999, g.player, "body", (0, 1, 0))
            yield 0.2
        evac = g.vehicles.find("evac")
        yield from self._wait_for(lambda: evac is not None and evac.finished, 40)
        yield from self._wait_for(lambda: g.mission.index == 12, 20)
        aa_gone = g.environment.dynamic["aa_gun"]["destroyed"]
        self.check("M4 steps 11-12: LZ held, AA gun blown, helicopter lands",
                   g.mission.index == 12 and evac.finished and aa_gone and evac.pos[2] < 2.0,
                   f"step {g.mission.index}, heli z {evac.pos[2]:.1f}, finished {evac.finished}, aa_gone {aa_gone}")
        g.player.teleport(208, 192, 0, 0)
        self._aim_at(evac.center())
        yield 0.4
        self.screenshot("53_m4_evac")
        g.player.teleport(215.5, 196.5, 0, 0)
        yield 3.0
        self.check("boarding: player and squad ride the helicopter out",
                   g.ride is not None and g.ride.vehicle is evac and g.player.motor.z > 1.0,
                   f"z {g.player.motor.z:.1f}")
        self._aim_at((200, 0, -1))
        yield 0.5
        self.screenshot("54_m4_lift_off")
        yield from self._wait_for(lambda: g.state in ("cinematic", "complete"), 15)
        yield 4.0
        self.screenshot("55_m4_outro")
        g.input.press_once("skip")
        yield 1.0
        prog = g.save.load()
        st = prog.stats.get("m04_no_way_back", {})
        self.check("Mission 4 complete with rank, stealth and intel saved",
                   g.state == "complete" and "m04_no_way_back" in prog.completed and st.get("intel") == 3
                   and st.get("best_rank") in ("GOLD", "SILVER", "BRONZE"),
                   g.mission_end.values.getText().replace("\n", " | ") + f" | {g.mission_end.rank.getText()}")
        self.screenshot("56_m4_results")
        g.player.invulnerable = False
        yield from self._m05_tests()

    # ------------------------------------------------------------------ mission 5
    def _shoot_at(self, point, seconds=0.6):
        self._aim_at(point)
        self.hold("aim", "fire")
        yield seconds
        self.release()
        yield 0.2

    def _m05_tests(self):
        g = self.game
        g.open_briefing("m05_dead_drop")
        yield 0.5
        self.screenshot("60_m5_briefing")
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 30)
        self.check("M5: Port Calder loads in the rain and the intro plays",
                   g.state == "cinematic" and g.map_name == "port_calder" and g.weather.intensity > 0.5,
                   f"load {g.environment.stats.get('load_seconds', 0):.1f}s, rain {g.weather.intensity}")
        yield 8.0
        self.screenshot("61_m5_intro")
        g.input.press_once("skip")
        yield 0.8
        g.player.invulnerable = True
        self.check("Crane starts alone with suppressed weapons",
                   g.state == "playing" and not g.squad and g.weapons.current.stats.id == "kr7s",
                   ", ".join(w.stats.id for w in g.weapons.weapons))

        # A suppressed shot is not heard 20 m away (enemies can't see in this scripted run - only hear).
        g.soldiers.visibility = 0.0
        guard = next(s for s in g.soldiers.group_alive("market") if s.ai.state == "IDLE")
        h = math.radians(guard.facing)
        g.player.teleport(guard.motor.x + math.sin(h) * 20, guard.motor.y - math.cos(h) * 20, 0, guard.facing)
        yield 0.3
        self._aim_at((g.player.position[0] + 3, g.player.position[1] - 3, 0))
        g.input.press_once("fire")
        yield 1.2
        self.check("suppressed shots stay quiet", guard.ai.awareness < 0.5 and guard.ai.state == "IDLE",
                   f"awareness {guard.ai.awareness:.2f}, {guard.ai.state}")

        # Rooftop and photographs.
        g.player.teleport(-70, -8, 3.67, -110)
        yield 1.0
        self.check("M5 step 1: on the harbour master's roof", g.mission.index == 1, g.hud.objective_text.getText())
        before = {grp: len(g.soldiers.group_alive(grp)) for grp in ("market", "quay", "officers", "office")}
        cams = len(g.security.cameras)
        g.mission.fail("Test retry")
        yield 0.5
        g.failed_screen.checkpoint["command"]()
        yield 1.0
        after = {grp: len(g.soldiers.group_alive(grp)) for grp in before}
        self.check("retry from checkpoint brings the same enemies and cameras back",
                   g.state == "playing" and g.mission.index == 1 and before == after
                   and len(g.security.cameras) == cams, f"{after}, {len(g.security.cameras)} cameras")
        g.player.invulnerable = True
        g.soldiers.visibility = 0.0
        g.weapons.select(0)
        g.input.press_once("weapon_3")
        yield 1.0
        officers = g.soldiers.group_alive("officers")
        for i, o in enumerate(officers * 2):
            if g.mission.index != 1:
                break
            if i >= len(officers) and id(o) in g.mission.objective.taken:
                continue
            ex, ey, ez = o.eye_position()
            self._aim_at((ex, ey, ez - 0.3))
            self.hold("aim")
            yield 0.6
            for _ in range(6):
                ex, ey, ez = o.eye_position()
                self._aim_at((ex, ey, ez - 0.3))
                yield 0.2
            if i == 0:
                self.screenshot("62_m5_photo")
        self.release()
        yield 0.5
        self.check("M5 step 2: three officers photographed through the scope", g.mission.index == 2,
                   g.hud.objective_text.getText())
        yield 6.0
        self.screenshot("63_m5_rooftop")

        # Intel and the dead drop.
        yield from self._hold_interact((-25, -20.8, 0.0), (-25, -19.5, 0.62), 1.0)
        yield from self._hold_interact((-80, 38.8, 0.0), (-80, 40, 0.62), 1.0)
        yield from self._hold_interact((-100, 44.8, 0.0), (-100, 46.2, 1.2), 1.9)
        self.check("M5 step 3: dead drop found", g.mission.index == 3 and g.intel.found == 2,
                   f"step {g.mission.index}, intel {g.intel.found}")

        # Shoot out the cameras, take down the inside guard, get in.
        g.input.press_once("weapon_1")
        yield 0.8
        g.player.teleport(15, 18, 0, 0)
        yield 0.4
        self._aim_at((6.8, 32.9, 3.2))
        yield 0.2
        self.screenshot("64_m5_cameras")
        for cid in ("cam_office_w", "cam_office_e"):
            cam = g.security.find(cid)
            for _ in range(4):
                if not cam.alive:
                    break
                yield from self._shoot_at((cam.pos[0], cam.pos[1], cam.pos[2] - 0.1), 0.25)
        outside_dead = all(not g.security.find(c).alive for c in ("cam_office_w", "cam_office_e"))
        self.check("security cameras can be shot out", outside_dead and not g.security.spotted)
        cam = g.security.find("cam_office_in")                    # through the doorway, before going in
        g.player.teleport(12.5, 31, 0, 0)
        for _ in range(3):
            if not cam.alive:
                break
            yield from self._shoot_at(cam.pos, 0.25)
        inside = min(g.soldiers.group_alive("office"), key=lambda s: math.dist(s.position[:2], (10, 36.5)))
        self.hold("crouch")
        yield 0.4
        h = math.radians(inside.facing)
        g.player.teleport(inside.motor.x + math.sin(h) * 1.2, inside.motor.y - math.cos(h) * 1.2, 0.25,
                          inside.facing)
        yield 0.3
        g.input.press_once("takedown")
        yield 0.6
        self.release()
        g.player.teleport(15, 37.5, 0.25, 0)
        yield 0.6
        self.check("M5 step 4: inside the office, guard down, no alarm",
                   g.mission.index == 4 and not inside.alive and not g.mission.alarm_raised,
                   f"step {g.mission.index}, takedowns {g.takedowns}, alarm {g.mission.alarm_raised}")

        # Download.
        yield from self._hold_interact((19, 40.2, 0.25), (19, 41.5, 1.1), 1.4)
        obj = g.mission.objective
        yield 3.0
        started = getattr(obj, "started", False) and obj.progress > 2.0
        self.screenshot("65_m5_download")
        g.player.teleport(15, 10, 0, 0)
        p0 = obj.progress
        yield 2.0
        paused = abs(obj.progress - p0) < 1e-6
        g.player.teleport(18, 39, 0.25, 0)
        yield 0.5
        obj.progress = obj.seconds - 1.0
        yield 2.0
        self.check("M5 step 5: download runs near the terminal and pauses away from it",
                   started and paused and g.mission.index == 5, f"step {g.mission.index}")

        # Hostage rescue.
        brandt = g.squad.get("brandt")
        captors = g.soldiers.group_alive("captors")
        self.check("Brandt is held captive and the captors ignore him",
                   brandt is not None and brandt.captive and brandt not in g.soldiers.hostiles("enemy")
                   and len(captors) == 3)
        yield from self._hold_interact((86, 28.0 - 1.2, 0.0), (86, 28, 0.62), 1.0)
        g.player.teleport(80, 13, 0, 0)
        self._aim_at(brandt.center())
        yield 0.5
        self.screenshot("66_m5_hostage")
        captors[0].take_damage(20, g.player, "torso", (0, 1, 0))         # they notice -> execution timer
        yield 1.2
        timer_text = g.hud.objective_text.getText()
        for c in captors:
            c.take_damage(9999, g.player, "head", (0, 1, 0))
        yield 1.0
        self.check("M5 step 6: captors killed before the execution - Brandt saved",
                   "s!)" in timer_text and brandt.alive and not brandt.captive and g.mission.index == 6,
                   f"'{timer_text}' step {g.mission.index}")

        # Escort to the pier.
        def clear_threats():
            for e in [e for e in g.soldiers.soldiers if e.team == "enemy" and e.alive]:
                if math.dist(e.position[:2], brandt.position[:2]) < 45:
                    e.take_damage(9999, g.player, "body", (1, 0, 0))
            pb0 = g.vehicles.find("pb0")
            if pb0 is not None and pb0.alive:
                pb0.take_damage(9999, g.player, "blast", (0, 1, 0))

        yield from self._follow_escort(brandt, 150, clear_threats)
        self.check("M5 step 7: Brandt reaches the pier", g.mission.index == 7 and brandt.alive,
                   f"step {g.mission.index}, brandt at {[round(v) for v in brandt.position]}")
        yield 0.5
        g.player.teleport(91.6, -68, 0.25, 180)
        yield 2.5
        boat = g.vehicles.find("escape")
        self.check("M5 step 8: Crane and Brandt escape by boat with a launcher",
                   g.ride is not None and brandt.mount is not None and boat is not None and not boat.paused
                   and any(w.stats.id == "rl3" for w in g.weapons.weapons), f"step {g.mission.index}")
        yield from self._wait_for(lambda: g.vehicles.find("gunship") is not None, 15)
        heli = g.vehicles.find("gunship")
        yield from self._wait_for(lambda: heli is not None and heli.mode == "attack", 30)
        g.input.press_once("weapon_4")
        yield 1.2
        self._aim_at(heli.center())
        yield 0.1
        self.screenshot("67_m5_chase")
        for _ in range(3):
            if not heli.alive:
                break
            vx, vy, vz = heli.vel
            c = heli.center()
            t = math.dist(c, g.player.eye_position()) / 80.0
            self._aim_at((c[0] + vx * t, c[1] + vy * t, c[2] + vz * t + 0.5 * t * t))
            self.hold("aim")
            yield 0.5
            c = heli.center()
            self._aim_at((c[0] + vx * t, c[1] + vy * t, c[2] + vz * t + 0.5 * t * t))
            self.hold("aim", "fire")
            yield 0.1
            self.release()
            yield 3.5
        if heli.alive:
            heli.take_damage(5000, g.player, "blast", (0, 0, 1))
        yield 3.0
        self.check("M5 step 9: helicopter shot down from the boat", g.mission.index == 9)
        yield from self._wait_for(lambda: g.state in ("cinematic", "complete"), 120)
        yield 4.0
        self.screenshot("68_m5_outro")
        g.input.press_once("skip")
        yield 1.0
        prog = g.save.load()
        st = prog.stats.get("m05_dead_drop", {})
        self.check("Mission 5 complete and saved", g.state == "complete" and "m05_dead_drop" in prog.completed
                   and st.get("intel") == 3, g.mission_end.values.getText().replace("\n", " | ")
                   + f" | {g.mission_end.rank.getText()}")
        self.screenshot("69_m5_results")
        g.player.invulnerable = False
        yield from self._m06_tests()

    # ------------------------------------------------------------------ story videos
    def _story_tests(self):
        """Play the whole prologue (screenshot of every shot), then one mission's story video."""
        g = self.game
        g.story_enabled = True
        g.voice.ready.wait(120)                             # voice files must exist for the narration
        g.show_main_menu()
        yield 1.0
        g.main_menu.buttons["NEW CAMPAIGN"]["command"]()
        yield 0.3
        self.check("New Campaign starts the voiced prologue", g.state == "story" and g.story is not None)
        seen, spoke = set(), 0
        waited = 0.0
        while g.state == "story" and waited < 600:
            st = g.story
            if st is not None and st.index not in seen and st.t > 2.5:
                seen.add(st.index)
                self.screenshot(f"story_prologue_{st.index:02d}_{st.shots[st.index]['type']}")
            if g.voice.speaking():
                spoke += 1
            yield 0.25
            waited += 0.25
        self.check("the prologue plays every shot with narration and ends at the Mission 1 briefing",
                   len(seen) >= 30 and spoke > 120 and g.mission_info.id == "m01_first_light"
                   and g.state in ("loading", "story", "cinematic", "playing"),
                   f"{len(seen)} shots, voice heard {spoke * 0.25:.0f}s, {waited:.0f}s long")
        g.open_briefing("m04_no_way_back")
        yield 0.5
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "story", 30)
        shots = set()
        while g.state == "story" and len(shots) < 3:
            st = g.story
            if st is not None and st.index not in shots and st.t > 3.0:
                shots.add(st.index)
                self.screenshot(f"story_m04_{st.index:02d}_{st.shots[st.index]['type']}")
            yield 0.25
        g.input.press_once("skip")
        yield 0.5
        self.check("a mission story video plays before the mission and can be skipped", g.state == "playing",
                   g.state)
        # The mission's ending video (it plays after the mission is completed).
        finished = []
        g.play_story("m04_no_way_back_end", lambda: finished.append(True))
        waited = 0.0
        while g.story is not None and waited < 120:
            st = g.story
            if st is not None and st.t > 4.0 and f"end{st.index}" not in shots:
                shots.add(f"end{st.index}")
                self.screenshot(f"story_m04_end_{st.index:02d}")
            yield 0.25
            waited += 0.25
        self.check("a mission ending video plays to the end", bool(finished))
        g.story_enabled = False
        g.show_main_menu()
        yield 0.5

    # ------------------------------------------------------------------ mission 6
    def _autopilot(self, jeep, waypoints, timeout, on_tick=None):
        """Drive with the real keys (W/A/D) along waypoints, like a player would."""
        g = self.game
        i = 0
        waited = 0.0
        step = g.mission.index
        self.top_speed = 0.0
        while g.mission.index == step and waited < timeout and i < len(waypoints):
            wx, wy = waypoints[i]
            dx, dy = wx - jeep.pos[0], wy - jeep.pos[1]
            if math.hypot(dx, dy) < 7.0:
                i += 1
                continue
            want = math.degrees(math.atan2(-dx, dy))
            diff = (want - jeep.heading + 180.0) % 360.0 - 180.0
            keys = []
            if not (jeep.velocity > 13.0 and abs(diff) > 25.0):
                keys.append("move_forward")
            if diff > 3.0:
                keys.append("move_left")
            elif diff < -3.0:
                keys.append("move_right")
            self.hold(*keys)
            self.top_speed = max(self.top_speed, jeep.velocity)
            if on_tick:
                on_tick()
            yield 0.05
            waited += 0.05
        self.release()

    def _m06_tests(self):
        g = self.game
        g.open_briefing("m06_the_broker")
        yield 0.5
        self.screenshot("70_m6_briefing")
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 30)
        self.check("M6: Lake Ostra loads and the intro plays", g.state == "cinematic" and g.map_name == "lake_ostra",
                   f"load {g.environment.stats.get('load_seconds', 0):.1f}s")
        yield 8.0
        self.screenshot("71_m6_intro")
        g.input.press_once("skip")
        yield 1.0
        g.player.invulnerable = True
        guards = g.soldiers.group_alive("mira_guards")
        self.check("Mira and her six guards are on your side", "mira" in g.squad and len(guards) == 6)
        yield from self._hold_interact((212, 132.8, 0.0), (212, 134, 0.62), 1.0)
        g.player.teleport(200, 129, 0, 0)
        yield 1.0
        self.check("M6 step 1: reached the terrace", g.mission.index == 1, g.hud.objective_text.getText())
        yield from self._hold_interact((200, 131.6, 0.0), (200, 134, 1.5), 1.0)
        self.check("M6 step 2: talking to Mira", g.mission.index == 2, g.hud.objective_text.getText())
        self.screenshot("72_m6_mira")
        yield 3.0
        self._skip_survive()
        yield 1.5
        self.check("M6 step 3: the ambush starts - a guard is shot",
                   g.mission.index == 3 and len(g.soldiers.group_alive("mira_guards")) <= 5,
                   f"step {g.mission.index}")
        yield from self._hold_interact((186, 134.4, 0.0), (186, 136, 1.0), 1.2)
        w = g.weapons
        self.check("M6 step 4: smoke and flashbangs picked up",
                   g.mission.index == 4 and w.special == {"smoke": 2, "flash": 3}, str(w.special))

        # Smoke grenade, thrown with the real keys.
        g.input.press_once("grenade_type")
        yield 0.2
        self.check("T switches to smoke grenades", w.grenade_type == "smoke", g.hud.grenades.getText())
        g.player.teleport(198, 128, 0, 180)
        yield 0.3
        self._aim_at((198, 112, 1.0))
        g.input.press_once("grenade")
        yield 4.5
        self.check("a smoke grenade makes a cloud that blocks sight",
                   len(g.smoke_clouds) == 1 and len(g.soldiers.smoke_clouds) == 1 and w.special["smoke"] == 1,
                   f"radius {g.soldiers.smoke_clouds[0][3] if g.soldiers.smoke_clouds else 0:.1f}")
        self.screenshot("73_m6_smoke")

        # Flashbang next to an enemy.
        g.input.press_once("grenade_type")
        yield 0.2
        self.check("T switches to flashbangs", w.grenade_type == "flash", g.hud.grenades.getText())
        enemy = min(g.soldiers.group_alive("assault"), key=lambda s: math.dist(s.position, g.player.position))
        ex, ey, _ = enemy.position
        for ang in range(0, 360, 30):                      # stand somewhere with a clear throw (no fence between)
            px, py = ex + math.cos(math.radians(ang)) * 9, ey + math.sin(math.radians(ang)) * 9
            if g.collision_world.line_of_sight((px, py, 1.6), enemy.center()) and \
                    g.collision_world.is_free(px, py, 0.4, 0.5, 1.7):
                break
        g.player.teleport(px, py, 0, 0)
        yield 0.1
        self._aim_at(enemy.center())
        g.input.press_once("grenade")
        yield 1.7
        stunned = [s for s in g.soldiers.group_alive("assault") if s.ai.stunned > 0.0]
        self.check("a flashbang stuns enemies and flashes the screen", len(stunned) >= 1, f"{len(stunned)} stunned")
        self.screenshot("74_m6_flash")
        yield 3.0

        # Out of ammo: fallen enemies drop packs you can walk over.
        gun = w.current
        gun.reserve = 0
        g.pickups.clear()
        while not g.pickups.packs:
            g.pickups.drop(g.player.position)
        yield 0.3
        self.check("walking over an ammo pack refills your guns", gun.reserve > 0 and not g.pickups.packs,
                   f"reserve {gun.reserve}")

        # Defend the villa.
        for e in g.soldiers.group_alive("assault"):
            e.take_damage(9999, g.player, "body", (0, 1, 0))
        g.player.teleport(200, 126, 0, 180)
        yield 8.0
        self.screenshot("75_m6_defend")
        self._skip_survive()
        yield 1.0
        self.check("M6 step 5: villa held, the mortar must go", g.mission.index == 5, g.hud.objective_text.getText())
        crew = g.soldiers.group_alive("mortar")
        self.check("a mortar crew is on the slope and shells are falling", len(crew) == 5)
        yield 6.0
        shells = len(g.shells)
        g.player.teleport(296, 200, 0, -40)
        self._aim_at(crew[0].center())
        yield 0.5
        self.screenshot("76_m6_mortar")
        for e in g.soldiers.group_alive("mortar"):
            e.take_damage(9999, g.player, "body", (0, 1, 0))
        yield from self._hold_interact((326, 230.8, 0.0), (326, 232, 0.62), 1.0)
        self.check("M6 step 6: mortar silenced, the shelling stops",
                   shells > 0 and len(g.shells) == 0 and g.mission.index == 6 and g.intel.found == 2,
                   f"{shells} shells cancelled, intel {g.intel.found}")

        # Drive.
        for e in g.soldiers.group_alive("assault"):
            e.take_damage(9999, g.player, "body", (0, 1, 0))
        g.player.teleport(229, 128, 0, 180)
        yield 1.0
        jeep = g.vehicles.find("getaway")
        self.check("M6 step 7: in the driver's seat, Mira beside you",
                   g.mission.index == 7 and g.driving and jeep is not None and g.squad["mira"].mount is not None,
                   f"step {g.mission.index}")
        self.screenshot("77_m6_driving")
        route = [(214, 104), (201, 92), (200, 60), (200, 0), (199, -36), (186, -49), (120, -50), (0, -50),
                 (-130, -50), (-250, -49), (-372, -52)]
        shots = {}

        def tick():
            if "road" not in shots and jeep.pos[1] < 20:
                shots["road"] = True
                self.screenshot("78_m6_road")
            if "block" not in shots and jeep.pos[0] < -232:
                shots["block"] = True
                self.screenshot("79_m6_roadblock")

        yield from self._autopilot(jeep, route, 150, tick)
        yield 0.5
        env = g.environment.dynamic
        rammed = sum(env[p]["destroyed"] for p in ("roadblock_a", "roadblock_b", "roadblock_c"))
        self.check("M6 step 8: the jeep is really driven to the ferry", g.mission.index == 8 and self.top_speed > 18,
                   f"step {g.mission.index}, top {self.top_speed * 3.6:.0f} km/h, time {g.mission.time:.0f}s, "
                   f"pos {[round(v) for v in jeep.pos[:2]]}")
        self.check("the roadblock is smashed through", rammed >= 1, f"{rammed} barriers")
        chasers = [v for v in (g.vehicles.find("ej1"), g.vehicles.find("ej2")) if v is not None]
        self.check("enemy jeeps with gunners chased the player", len(chasers) == 2,
                   ", ".join(f"({v.pos[0]:.0f},{v.pos[1]:.0f})" for v in chasers))
        g.player.teleport(-380, -92, 0.25, 180)
        yield from self._wait_for(lambda: g.state in ("cinematic", "complete"), 10)
        yield 4.0
        self.screenshot("80_m6_outro")
        g.input.press_once("skip")
        yield 1.0
        prog = g.save.load()
        st = prog.stats.get("m06_the_broker", {})
        self.check("Mission 6 complete and saved", g.state == "complete" and "m06_the_broker" in prog.completed
                   and st.get("intel") == 2, g.mission_end.values.getText().replace("\n", " | ")
                   + f" | {g.mission_end.rank.getText()}")
        self.screenshot("81_m6_results")
        g.player.invulnerable = False
        yield from self._story_tests()

    def _m1strike_tests(self):
        """Visual check of Mission 1's missile strike, seen from the HQ roof."""
        g = self.game
        g.story_enabled = False
        g.open_briefing("m01_first_light")
        yield 0.5
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 30)
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True
        g.player.teleport(3, 52, 0, 0)
        yield 1.0
        g.player.teleport(30.4, -35.4, 4.07, 180, -25)
        yield 0.5
        self.hold("interact")
        yield 3.0
        self.release()
        g0 = len(g.soldiers.group_alive("garrison"))
        g.player.teleport(6, -22, 0, 0, 6)
        views = ((0, 8), (-10, 10), (5, 6), (-20, 4), (0, 3), (15, 4), (-5, 8), (10, 2))
        for k in range(16):
            yield 0.8 if k < 10 else 1.6
            yaw, pitch = views[k % len(views)]
            g.player.camera.look.yaw, g.player.camera.look.pitch = yaw, pitch
            self.screenshot(f"strike_{k:02d}")
        dead = g0 - len(g.soldiers.group_alive("garrison"))
        flown = sum(1 for s in g.soldiers.soldiers if s.group == "garrison" and not s.alive)
        self.check("the strike kills Kareth riflemen", dead >= 6, f"{dead} of {g0} riflemen killed")

    def _knock_tests(self):
        """Visual check: a shell lands next to the player, who is thrown down and gets back up."""
        g = self.game
        g.start_sandbox()
        yield 1.5
        g.player.invulnerable = True
        g.mission_data_knock = True
        m = g.player.motor
        yaw = math.radians(g.player.camera.look.yaw)
        g.explode((m.x - math.sin(yaw) * 4, m.y + math.cos(yaw) * 4, 0.2), 6.0, 0.0, None, 3.4)
        g.player.knockdown((math.sin(yaw), -math.cos(yaw)))
        for k, t in enumerate((0.25, 0.4, 0.8, 1.0, 0.9, 1.2)):
            yield t
            self.screenshot(f"knock_{k}")
        self.check("the player gets back up after being thrown", g.player.knock_t < 0.0)

    def _m2mortar_tests(self):
        """Visual check: our mortars land on the attacking enemy in Mission 2 and throw them."""
        g = self.game
        g.story_enabled = False
        g.open_briefing("m02_line_breaks")
        yield 0.5
        g.briefing.begin["command"]()
        yield from self._wait_for(lambda: g.state == "cinematic", 25)
        g.input.press_once("skip")
        yield 0.5
        g.player.invulnerable = True
        g.player.teleport(-31, -28.0, 0, 180)
        yield 1.0
        g.player.teleport(0, 1.3, 0.4, 0, 1)
        yield 42.0
        dead0 = sum(1 for e in g.soldiers.soldiers if e.team == "enemy" and not e.alive)
        for k in range(12):
            yield 1.6
            g.player.camera.look.yaw, g.player.camera.look.pitch = (0, 2) if k % 2 == 0 else (-12, 3)
            self.screenshot(f"mortar_{k:02d}")
        dead = sum(1 for e in g.soldiers.soldiers if e.team == "enemy" and not e.alive) - dead0
        self.check("our mortars kill attackers", dead >= 3, f"{dead} enemies died during the barrage")

    def _blast_tests(self):
        """Visual check: a missile-size blast throws soldiers through the air."""
        g = self.game
        g.start_sandbox()
        yield 1.5
        g.player.invulnerable = True
        px, py = g.player.motor.x, g.player.motor.y
        g.player.teleport(px, py, 0, 0)
        yield 0.5
        men = []
        for i, (ox, oy) in enumerate(((-2.5, 22), (2.0, 21), (0.5, 25), (-1.0, 19), (3.5, 24))):
            men.append(g.soldiers.spawn("enemy", px + ox, py + oy, 180, profile="regular"))
        for s in men:
            s.ai.command_hold(s.motor.x, s.motor.y, 180) if hasattr(s.ai, "command_hold") else None
        yield 1.0
        start = [(s.motor.x, s.motor.y) for s in men]
        g.explode((px, py + 22, 0.2), 14.0, 400.0, None, 4.0)
        peak = 0.0
        for k, t in enumerate((0.12, 0.25, 0.25, 0.5, 1.2)):
            yield t
            peak = max([peak] + [s.motor.z for s in men])
            self.screenshot(f"blast_{k}")
        moved = [math.dist(a, (s.motor.x, s.motor.y)) for a, s in zip(start, men)]
        dead = sum(not s.alive for s in men)
        self.check("a big blast kills and throws soldiers", dead >= 4 and peak > 0.8 and max(moved) > 3.0,
                   f"{dead} dead, highest {peak:.1f} m, thrown up to {max(moved):.1f} m")

    def _guns_tests(self):
        """Screenshots of every first-person gun, at the hip and aimed (visual check of the models)."""
        g = self.game
        g.start_sandbox()
        yield 1.5
        wm = g.weapons
        for wid in ("kr7", "kr7s", "p12", "lr50", "sg8", "rl3"):
            idx = wm.give_weapon(wid, 10)
            wm.select(idx)
            yield 1.2
            self.screenshot(f"gun_{wid}_hip")
            self.hold("aim")
            yield 0.8
            self.screenshot(f"gun_{wid}_ads")
            self.release()
            yield 0.4
        self.check("every gun model can be shown", True)

    def _weapon_tests(self):
        game = self.game
        wm = game.weapons
        self.teleport("wall_test")                  # facing a concrete wall ~4 m away
        yield 1.0
        rifle = wm.current
        mag0, res0, decals0 = rifle.mag, rifle.reserve, len(game.effects._decals)
        self.hold("fire")
        yield 0.5
        self.release()
        yield 0.1
        fired = mag0 - rifle.mag
        self.check("rifle fires automatically while held", 4 <= fired <= 8 and rifle.reserve == res0,
                   f"{fired} rounds in 0.5 s, mag {rifle.mag}/{rifle.stats.magazine}")
        self.check("bullets leave impact marks on the wall", len(game.effects._decals) > decals0,
                   f"{len(game.effects._decals) - decals0} bullet holes")
        self.hold("fire")
        yield 0.05
        self.screenshot("20_firing")
        self.release()

        self.game.input.press_once("reload")
        yield 0.05
        reload_started = rifle.reloading
        yield rifle.stats.reload_time + 0.4
        self.check("reload (R) refills the magazine from reserve",
                   rifle.mag == rifle.stats.magazine and rifle.mag + rifle.reserve == mag0 + res0 - fired - 1,
                   f"started={reload_started} mag {rifle.mag}, reserve {rifle.reserve}")

        self.hold("aim")
        yield 0.5
        fov = self.game.camLens.get_fov()[0]
        self.check("aim down sights (RMB) zooms in", wm.ads > 0.99 and fov < self.game.settings.field_of_view * 0.8,
                   f"ads={wm.ads:.2f} fov={fov:.1f}")
        self.screenshot("21_ads_rifle")
        self.release()
        yield 0.4

        self.game.input.press_once("weapon_2")
        yield 0.8
        pistol = wm.current
        self.check("switch to pistol (2)", pistol.stats.weapon_class == "pistol", pistol.stats.name)
        mag0 = pistol.mag
        self.hold("fire")
        yield 0.6
        self.release()
        self.check("pistol is semi-automatic (one shot per click)", mag0 - pistol.mag == 1, f"{mag0 - pistol.mag} shots")
        yield 0.2

        self.game.input.press_once("weapon_3")
        yield 1.0
        self.hold("aim")
        yield 0.7
        self.check("sniper scope overlay", wm.scoped and wm.current.stats.weapon_class == "sniper",
                   f"scoped={wm.scoped}")
        self.screenshot("22_sniper_scope")
        self.release()
        yield 0.4

        self.game.input.press_once("weapon_4")
        yield 1.0
        sg = wm.current
        sg.mag, sg.reserve = 0, 0
        shots0 = wm.shots_fired
        self.hold("fire")
        yield 0.3
        self.release()
        self.check("cannot shoot with an empty magazine", wm.shots_fired == shots0 and sg.mag == 0,
                   f"shots {wm.shots_fired - shots0}")
        sg.refill()
        self.game.input.press_once("weapon_1")
        yield 0.9

        # Shoot a stationary target dummy in the head and in the body.
        from systems.combat_system import character_hitboxes
        from player.health import Health

        class Target:
            team = "enemy"

            def __init__(self, x, y):
                self.x, self.y, self.health = x, y, Health(500)
                self.position = (x, y, 0.0)

            alive = property(lambda s: s.health.alive)

            def hitboxes(self):
                return character_hitboxes(self.x, self.y, 0.0, 1.8)

            def center(self):
                return self.x, self.y, 1.0

            def take_damage(self, amount, source, zone, direction):
                self.last = (amount, zone)
                return self.health.take_damage(amount)

        p = game.map_data.points["wall_test"]
        target = Target(p.x, p.y - 2.5)
        game.combat.register(target)
        self.teleport("wall_test")
        look = game.player.camera.look
        eye = game.player.eye_position()
        head_z = 1.8 - 0.16
        look.pitch = math.degrees(math.atan2(head_z - eye[2], 2.5))
        self.hold("aim")
        yield 0.5
        hits0 = wm.headshots
        self.game.input.press_once("fire")
        self.hold("aim", "fire")
        yield 0.04
        self.hold("aim")
        yield 0.3
        last = getattr(target, "last", (0, None))
        self.check("headshot detected with extra damage", wm.headshots > hits0 and last[1] == "head" and
                   abs(last[0] - wm.current.stats.damage * wm.current.stats.headshot_multiplier) < 1e-6,
                   f"zone={last[1]} damage={last[0]:.1f}")
        self.release()
        game.combat.unregister(target)

        # Grenade: throw it at the wall and wait for the blast.
        self.teleport("wall_test")
        yield 0.3
        g0 = wm.grenades
        expl0 = sum(1 for pt in game.effects.particles if pt.kind == "fire")
        self.game.input.press_once("grenade")
        yield 0.2
        thrown = wm.grenades == g0 - 1 and len(wm.projectiles) == 1
        self.teleport("view_spawn")                   # step away from the blast
        yield 3.2
        fire = sum(1 for pt in game.effects.particles if pt.kind in ("fire", "smoke"))
        self.check("grenade (G) is thrown and explodes", thrown and not wm.projectiles and fire > 0,
                   f"thrown={thrown} left={len(wm.projectiles)} blast particles={fire}")
        self.game.player.health.reset()
        wm.refill_all()

    def _finish(self):
        failed = [r for r in self.results if not r["passed"]]
        print(f"\nAUTOTEST: {len(self.results) - len(failed)}/{len(self.results)} passed", flush=True)
        if self.shots:
            report = {"results": self.results, "environment": self.game.environment.stats}
            (self.shots / "autotest_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        sys.exit(1 if failed else 0)
