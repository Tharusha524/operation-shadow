"""The game application: window, menus, missions and the frame loop.

Game states
  menu       main menu and its sub-screens (3D outpost orbiting in the background)
  briefing   mission briefing screen
  loading    loading screen while the mission is built
  cinematic  intro / outro cutscene
  playing    in mission (self.paused toggles the pause menu)
  dead       short death camera before the "mission failed" screen
  failed     mission failed screen
  complete   mission complete results screen
  sandbox    free movement on the map without a mission (used by the automated tests)
"""
from __future__ import annotations

import logging
import math
import random

from direct.showbase.ShowBase import ShowBase
from panda3d.core import AntialiasAttrib, BitMask32, ClockObject, WindowProperties, loadPrcFileData

from config import constants as C
from core import stealth
from core.drone import DroneController
from core.input_manager import InputManager
from core.mission_context import MissionContext
from core.pickups import AMMO_FRACTION, Pickups
from core.ride import Ride
from core.paths import MAPS_DIR, user_data_dir
from enemies.enemy_manager import SoldierManager
from environments.environment_manager import EnvironmentManager
from environments.map_loader import Placement, load_map
from missions.cinematics import CinematicPlayer
from missions.story_video import StoryVideo, load_story
from missions.mission_data import MissionDataError, load_campaign, load_mission
from missions import ranking
from missions.mission_manager import MissionRunner
from player.player import Player
from systems.audio_manager import AudioManager
from systems.collision_system import CollisionWorld
from systems.combat_system import CombatSystem
from systems.effects import Effects
from systems.navigation import NavGrid
from systems.postfx import PostFX
from systems.save_manager import SaveManager
from systems.security import SecurityManager
from systems.voice import VoicePlayer
from systems.weather import Rain
from ui import style
from ui.game_hud import GameHUD
from ui.main_menu import ControlsScreen, CreditsScreen, MainMenu
from ui.mission_screen import (BriefingScreen, CampaignScreen, LoadingScreen, MissionEndScreen,
                               MissionFailedScreen)
from ui.pause_menu import PauseMenu
from ui.settings_menu import SettingsMenu
from vehicles.manager import VehicleManager
from weapons.weapon_manager import WeaponManager

log = logging.getLogger(__name__)

MENU_MAP = "border_outpost"
NAV_MARGIN = 28.0


def configure_engine(settings, *, uncapped=False):
    """Panda3D options that must be set BEFORE the window opens."""
    w, h = settings.resolution
    msaa = settings.preset["msaa"]
    lines = [
        f"window-title {C.GAME_TITLE}",
        f"win-size {w} {h}",
        f"fullscreen {'#t' if settings.fullscreen else '#f'}",
        f"sync-video {'#t' if settings.vsync and not uncapped else '#f'}",
        f"framebuffer-multisample {'#t' if msaa else '#f'}",
        f"multisamples {msaa}",
        "textures-power-2 none",
        "show-frame-rate-meter #f",
        "audio-library-name p3openal_audio",
        "want-pstats #f",
        "hardware-animated-vertices #t",        # skin the soldiers on the graphics card
        f"model-cache-dir {(user_data_dir() / 'cache').as_posix()}",   # keep Panda's cache next to the game (D:)
    ]
    loadPrcFileData("operation-shadow", "\n".join(lines))


class Game(ShowBase):
    def __init__(self, settings_store, settings, autotest=None):
        ShowBase.__init__(self)
        self.settings_store = settings_store
        self.settings = settings
        self.clock = ClockObject.get_global_clock()
        self.autotest_mode = autotest is not None
        self.state = "menu"
        self.paused = False
        self.sim_time = 0.0

        self.disable_mouse()
        self.cam.node().set_camera_mask(BitMask32.bit(C.MAIN_CAMERA_MASK_BIT))
        self.render.set_shader_auto()
        if settings.preset["msaa"]:
            self.render.set_antialias(AntialiasAttrib.M_multisample)
        style.load_font(self.loader)
        self.postfx = PostFX(self, enabled=settings.graphics_quality != "low",
                             multisamples=settings.preset["msaa"])

        self.input = InputManager(self, C.DEFAULT_KEY_BINDINGS, C.EVENT_BINDINGS)
        self.audio = AudioManager(self, settings)
        self.audio.preload()
        style.set_ui_sounds(self.audio._get("ui_hover"), self.audio._get("ui_click"))
        self.campaign = load_campaign()
        self.voice = VoicePlayer(self, self.campaign.characters)
        self.voice.prepare_all()                 # makes any missing voice files in the background
        # The automated test uses its own save file so it never touches the player's real progress.
        save_name = "autotest_progress.json" if self.autotest_mode else "progress.json"
        if self.autotest_mode:
            (user_data_dir() / save_name).unlink(missing_ok=True)
        self.save = SaveManager(user_data_dir() / save_name, self.campaign.order)

        self.collision_world = CollisionWorld()
        self.combat = CombatSystem(self.collision_world)
        self.effects = Effects(self)
        from systems.debris import Debris
        self.debris = Debris(self)
        from systems.civilians import Civilians
        self.civilians = Civilians(self)
        self.environment = EnvironmentManager(self, self.collision_world, settings)
        self.fires = []
        self.map_name = None
        self.map_data = None
        self.nav = None
        self.water_rect = None
        self.water_z = None
        self._load_map(MENU_MAP)

        self.player = Player(self, self.collision_world, settings, self.map_data.player_spawn)
        self.combat.register(self.player)
        self.weapons = WeaponManager(self, self.player)
        self.player.weapons = self.weapons
        self.soldiers = SoldierManager(self.collision_world, self.combat, self.nav, render_root=self.render,
                                       materials=self.environment.materials, game=self,
                                       difficulty=settings.difficulty)
        self.soldiers.player = self.player
        self.soldiers.realistic_models = settings.graphics_quality != "low"
        self.soldiers.kill_listeners.append(self._on_soldier_killed)
        self.hud = GameHUD(self, settings)
        self.weapons.hit_listeners.append(self.hud.hit_marker)
        self.vehicles = VehicleManager(self.collision_world, self.combat, game=self)
        self.vehicles.player = self.player
        self.vehicles.water_z = self.water_z
        self.security = SecurityManager(self.collision_world, self.combat, game=self)
        self.pickups = Pickups(random.Random(11), self._make_ammo_node)
        self.weather = Rain(self)
        self.weather.set_intensity(self.environment.atmosphere.get("rain", 0.0))
        self.ride = None
        self.drone = None
        self.tagged = []                 # enemies tagged by the recon drone
        self.nvg_available = False
        self.nvg_on = False
        self.flares = []
        self.base_lit_zones = []
        self.charges = []
        self.intel = stealth.IntelTracker()
        self.checkpoint_intel = None
        self.checkpoint_world = None
        self.takedowns = 0
        self._takedown_cooldown = 0.0
        self.timed = []                  # [seconds left, callable]
        self.smoke_clouds = []           # smoke grenades: {"pos", "t", "life", "timer"}

        self.ctx = MissionContext(self)
        self.mission = None
        self.mission_info = None
        self.mission_data = None
        self.squad = {}
        self.cinematic = None
        self.story = None                 # story video being shown (prologue / mission briefing video)
        self.story_enabled = True
        self.kills = 0
        self.smoke_emitters = []
        self._knocked_down = False       # the once-per-mission "thrown by a shell" moment has happened
        self.shock = 0.0                 # shell shock seconds left (blur, muffled sound, slow)
        self.shells = []                 # incoming artillery: [seconds until impact, pos, whistled, radius, damage]
        self.checkpoint_weapons = None
        self._death_timer = 0.0
        self._screen_stack = []

        self.main_menu = MainMenu(self, self.new_campaign, self.continue_campaign,
                                  lambda: self.open_screen(self.campaign_screen), lambda: self.open_settings(),
                                  lambda: self.open_screen(self.controls_screen),
                                  lambda: self.open_screen(self.credits_screen), self.exit_game)
        self.campaign_screen = CampaignScreen(self, self.open_briefing, self.back)
        self.briefing = BriefingScreen(self, self.begin_mission, self.back)
        self.loading = LoadingScreen(self)
        self.mission_end = MissionEndScreen(self, self._after_mission_end, self.show_main_menu)
        self.failed_screen = MissionFailedScreen(self, self.retry_checkpoint, self.restart_mission, self.show_main_menu)
        self.settings_menu = SettingsMenu(self, self.back)
        self.controls_screen = ControlsScreen(self, self.back)
        self.credits_screen = CreditsScreen(self, self.back)
        self.pause_menu = PauseMenu(self, self.resume, self.restart_mission, self.open_settings,
                                    self.show_main_menu, self.exit_game)

        self.accept("player-footstep", self._on_footstep)
        self.accept("player-land", lambda p: self.audio.play_footstep(0.5))
        self.accept("player-damaged", self._on_player_damaged)

        self.taskMgr.add(self._update, "game-update", sort=10)
        self.show_main_menu()
        if autotest is not None:
            from core.autotest import AutoTest
            self.autotest = AutoTest(self, **autotest)

    # ================================================================== maps
    def _load_map(self, name, atmosphere=None):
        if self.map_name == name and self.environment.map is not None:
            for bounds in self.environment.reset_props():
                self.nav.rebuild(bounds)
            self.environment.set_atmosphere(atmosphere)
            self.postfx.set_grading(self.environment.atmosphere.get("grading"))
            if getattr(self, "weather", None) is not None:
                self.weather.set_intensity(self.environment.atmosphere.get("rain", 0.0))
            return
        self.map_data = load_map(MAPS_DIR / f"{name}.json")
        self.environment.load(self.map_data, atmosphere)
        if hasattr(self, "fires"):
            self.clear_fires()
            for x, y, z, size in self.map_data.fires:
                self.add_fire((x, y, z), size)
        bounds = self.map_data.terrain.get("nav_bounds")
        if not bounds:
            half = float(self.map_data.terrain.get("play_area", 72.0)) + NAV_MARGIN
            bounds = (-half, -half, half, half)
        self.nav = NavGrid(self.collision_world, tuple(bounds))
        self.postfx.set_grading(self.environment.atmosphere.get("grading"))
        if getattr(self, "soldiers", None) is not None:
            self.soldiers.nav = self.nav
        self.map_name = name
        self._setup_water()
        if getattr(self, "weather", None) is not None:
            self.weather.set_intensity(self.environment.atmosphere.get("rain", 0.0))

    def _setup_water(self):
        water = self.map_data.terrain.get("water")
        self.water_rect = tuple(water["rect"]) if water else None
        self.water_z = float(water.get("z", -1.5)) if water else None
        if getattr(self, "vehicles", None) is not None:
            self.vehicles.water_z = self.water_z
        self.security = SecurityManager(self.collision_world, self.combat, game=self)
        self.weather = Rain(self)
        self.weather.set_intensity(self.environment.atmosphere.get("rain", 0.0))

    def in_water(self, x, y):
        r = self.water_rect
        return r is not None and r[0] <= x <= r[2] and r[1] <= y <= r[3]

    # ================================================================== screens
    def _hide_screens(self):
        for screen in (self.main_menu, self.campaign_screen, self.briefing, self.loading, self.mission_end,
                       self.failed_screen, self.settings_menu, self.controls_screen, self.credits_screen,
                       self.pause_menu):
            screen.hide()

    def open_screen(self, screen):
        if self._screen_stack:
            self._screen_stack[-1].hide()
        if screen is self.campaign_screen:
            screen.refresh()
        self._screen_stack.append(screen)
        screen.show()

    def back(self):
        if self._screen_stack:
            self._screen_stack.pop().hide()
        if self._screen_stack:
            top = self._screen_stack[-1]
            if top is self.main_menu:
                self.main_menu.refresh(self._continue_label())
            top.show()

    def open_settings(self):
        self.settings_menu.refresh()
        self.open_screen(self.settings_menu)

    def _set_gameplay_view(self, playing):
        self.hud.set_visible(playing)
        self.weapons.viewmodel.set_visible(playing)
        self.input.capture_mouse(playing)

    def show_main_menu(self):
        self._end_mission_world()
        self.state = "menu"
        self.paused = False
        self._hide_screens()
        self._screen_stack = []
        self._load_map(MENU_MAP)
        self._set_gameplay_view(False)
        self.player.camera.detach_for_cinematic(fov=60.0)
        self.main_menu.refresh(self._continue_label())
        self.open_screen(self.main_menu)
        self.audio.stop_all_loops()
        self.audio.start_loop("wind_loop", 0.25)
        self.audio.play_music("music_menu", 0.8)

    def _continue_label(self):
        mid = self.save.progress.current_mission
        info = self.campaign.mission(mid) if mid else None
        if info and info.playable:
            return f"{info.number:02d} {info.title}"
        return None

    # ================================================================== campaign flow
    def new_campaign(self):
        first = self.campaign.order[0]
        if not (self.story_enabled and load_story("prologue")):
            self.open_briefing(first)
            return

        def after():                                   # the prologue flows straight into Mission 1
            info = self.campaign.mission(first)
            try:
                data = load_mission(info)
            except MissionDataError as exc:
                log.error("%s", exc)
                self.show_main_menu()
                return
            self.mission_info, self.mission_data = info, data
            self.begin_mission()

        self.play_story("prologue", after)

    def play_story(self, name, on_done):
        """Show a voiced story video (data/story/<name>.json), then call on_done."""
        spec = load_story(name) if self.story_enabled else None
        if spec is None:
            on_done()
            return
        self._hide_screens()
        self._screen_stack = []
        self.state = "story"
        self.paused = False
        self._set_gameplay_view(False)
        self.audio.stop_music()

        def done():
            self.story = None
            on_done()

        self.story = StoryVideo(self, spec, done)

    def continue_campaign(self):
        mid = self.save.progress.current_mission
        if mid and self.campaign.mission(mid) and self.campaign.mission(mid).playable:
            self.open_briefing(mid)

    def open_briefing(self, mission_id):
        info = self.campaign.mission(mission_id)
        try:
            data = load_mission(info)
        except MissionDataError as exc:
            log.error("%s", exc)
            return
        self.mission_info, self.mission_data = info, data
        self.briefing.set_mission(info, data, self.campaign.characters.get(info.character))
        self.open_screen(self.briefing)

    def begin_mission(self):
        self._hide_screens()
        self._screen_stack = []
        self.state = "loading"
        self.loading.set_text(self.mission_info.title)
        self.loading.show()
        self.audio.stop_music()
        # Wait two frames so the loading screen is actually drawn before the heavy work.
        self.taskMgr.do_method_later(0.05, lambda task: self._load_mission() or task.done, "load-mission")

    def restart_mission(self):
        self.paused = False
        self.mission_end.hide()
        self.failed_screen.hide()
        self.pause_menu.hide()
        self.begin_mission()

    def _end_mission_world(self):
        self.end_drone()
        self.end_ride()
        self.vehicles.remove_all()
        self.tagged = []
        self.set_nvg(False, False)
        self._clear_flares()
        self.base_lit_zones = []
        self.soldiers.visibility = 1.0
        self.soldiers.lit_zones = []
        self.intel.clear()
        self.clear_charges()
        self.security.remove_all()
        self.pickups.clear()
        self.smoke_clouds = []
        self.soldiers.smoke_clouds = []
        self.timed = []
        self.hud.set_action_hint(None)
        self.soldiers.remove_all()
        self.weapons.clear_projectiles()
        self.effects.clear()
        self.debris.clear()
        self.civilians.clear()
        self.smoke_emitters = []
        self.shells = []
        self._knocked_down = False
        self.player.knock_t = -1.0
        self.player.camera.knock = (0.0, 0.0, 0.0)
        if self.shock > 0.0:
            self.shock = 0.0
            self.player.shock = 0.0
            self.audio.set_duck(1.0)
            self.postfx.set_dof(None)
        self.squad = {}
        self.mission = None
        self.cinematic = None
        self.hud.set_prompt(None)
        self.hud.set_marker(None)
        self.hud.set_objectives("", [])

    def _load_mission(self):
        data, info = self.mission_data, self.mission_info
        self._end_mission_world()
        self._load_map(data["map"], data.get("atmosphere"))
        self.soldiers.set_difficulty(self.settings.difficulty)
        p = data["player"]
        sp = p["spawn"]
        spawn = Placement(sp["pos"][0], sp["pos"][1], sp["pos"][2] if len(sp["pos"]) > 2 else 0.0, sp.get("heading", 0))
        self.player.spawn = spawn
        self.player.respawn(spawn)
        self.player.camera.base_fov = self.settings.field_of_view
        self.weapons.set_loadout(p.get("loadout", ["kr7", "p12"]), p.get("grenades"), p.get("smoke", 0),
                                 p.get("flash", 0))
        self.weapons.reset_stats()
        self.checkpoint_weapons = None
        for member in data.get("squad", []):
            char = self.campaign.characters.get(member["id"])
            s = self.soldiers.spawn("friendly", member["pos"][0], member["pos"][1], member.get("heading", 0),
                                    profile=member.get("profile", "squad"), name=char.name if char else member["id"],
                                    invulnerable=member.get("invulnerable", True))
            self.squad[member["id"]] = s
        night = data.get("night") or {}
        self.soldiers.visibility = float(night.get("visibility", 1.0))
        self.base_lit_zones = [tuple(z) for z in night.get("lit", [])]
        self.soldiers.lit_zones = list(self.base_lit_zones)
        self.set_nvg(False, bool(p.get("nvg", False)))
        self.intel.setup(data.get("intel", []), self._make_intel_node)
        self.checkpoint_intel = None
        self.checkpoint_world = None
        self.takedowns = 0
        self.kills = 0
        self.mission = MissionRunner(self.ctx, data, info.title)
        self.save.start_mission(info.id)
        self.loading.hide()
        self.audio.stop_all_loops()
        # A mission story video (data/story/<id>.json) replaces the short intro cutscene.
        has_story = self.story_enabled and load_story(info.id) is not None
        self.play_story(info.id, self._begin_play if has_story else self._start_intro)

    def _start_intro(self):
        data = self.mission_data
        if data.get("intro"):
            self.state = "cinematic"
            self._set_gameplay_view(False)
            self.cinematic = CinematicPlayer(self, data["intro"], self._begin_play, self.campaign.speaker_name)
        else:
            self._begin_play()

    def _begin_play(self):
        self.cinematic = None
        self.state = "playing"
        self.paused = False
        self._set_gameplay_view(True)
        self.player.camera.reattach()
        if self.mission is not None and self.mission.index < 0:
            self.mission.start()

    def start_sandbox(self, map_name=MENU_MAP, atmosphere=None):
        """Free roam on a map without a mission (used by the automated play-test)."""
        self._hide_screens()
        self._screen_stack = []
        self._end_mission_world()
        self._load_map(map_name, atmosphere)
        self.player.spawn = self.map_data.player_spawn
        self.player.respawn()
        self.weapons.set_loadout(["kr7", "p12", "lr50", "sg8"])
        self.audio.stop_music()
        self.state = "sandbox"
        self.paused = False
        self._set_gameplay_view(True)
        self.player.camera.reattach()

    # ================================================================== mission events
    def on_mission_complete(self):
        info = self.mission_info
        stats = self.mission_stats()
        self.save.complete_mission(info.id, stats)
        self.audio.stop_all_loops()
        self.audio.play("mission_complete", 0.8)
        self._set_gameplay_view(False)
        if self.story_enabled and load_story(f"{info.id}_end") is not None:
            self.play_story(f"{info.id}_end", self._show_mission_end)      # the mission's ending video
            return
        outro = self.mission_data.get("outro")
        if outro:
            self.state = "cinematic"
            self.cinematic = CinematicPlayer(self, outro, self._show_mission_end, self.campaign.speaker_name)
        else:
            self._show_mission_end()

    def mission_stats(self):
        m = self.mission
        stats = {"time": round(m.time, 1) if m else 0.0, "kills": self.kills, "headshots": self.weapons.headshots,
                 "accuracy": round(self.weapons.accuracy, 3), "deaths": m.deaths if m else 0,
                 "takedowns": self.takedowns, "stealth": m.stealth if m else None,
                 "intel": self.intel.found, "intel_total": self.intel.total, "intel_ids": self.intel.collected_ids()}
        stats["rank"] = ranking.rank(stats, (self.mission_data or {}).get("par_time"))
        return stats

    def _show_mission_end(self):
        self.cinematic = None
        self.state = "complete"
        self._set_gameplay_view(False)
        self.player.camera.detach_for_cinematic()
        nxt = self.campaign.mission(self.save.progress.current_mission) if self.save.progress.current_mission else None
        if nxt is None:
            text = "Campaign complete."
        elif nxt.playable:
            text = f"Next mission unlocked: {nxt.number:02d} {nxt.title}"
        else:
            text = f"Next: {nxt.number:02d} {nxt.title} - {nxt.location}.  This mission is still in development."
        self.mission_end.set_results(self.mission_info.title, self.mission_stats(), text)
        self.mission_end.show()
        self.audio.play_music("music_menu", 0.6)

    def _after_mission_end(self):
        self.show_main_menu()
        self.open_screen(self.campaign_screen)

    def on_mission_failed(self, reason):
        self.state = "failed"
        self._set_gameplay_view(False)
        self.audio.stop_loop("alarm_loop")
        self.audio.play("mission_failed", 0.7)
        self.failed_screen.set_reason(reason, self.mission is not None and self.mission.checkpoint is not None)
        self.failed_screen.show()

    def retry_checkpoint(self):
        if self.mission is None or not self.mission.restart_from_checkpoint():
            self.restart_mission()
            return
        self.failed_screen.hide()
        self.effects.clear()
        self.state = "playing"
        self._set_gameplay_view(True)
        self.player.camera.reattach()

    # ================================================================== pause / exit / settings
    def pause(self):
        if self.state not in ("playing", "sandbox") or self.paused:
            return
        self.paused = True
        self._set_gameplay_view(False)
        obj = self.mission.objective.text if self.mission and self.mission.objective else ""
        self.pause_menu.set_info(self.mission_info.title if self.mission_info and self.mission else "Free roam", obj)
        self._screen_stack = [self.pause_menu]
        self.pause_menu.show()

    def resume(self):
        if not self.paused:
            return
        self.paused = False
        self._hide_screens()
        self._screen_stack = []
        self._set_gameplay_view(True)
        if self.drone is not None:
            self.weapons.viewmodel.set_visible(False)

    def exit_game(self):
        self.settings_store.save(self.settings)
        self.userExit()

    def apply_settings(self, key):
        s = self.settings
        if key == "field_of_view":
            self.player.camera.base_fov = s.field_of_view
        elif key in ("master_volume", "music_volume", "sfx_volume"):
            self.audio.apply_volumes()
        elif key == "shadow_quality":
            self.environment.refresh_lighting()
        elif key in ("resolution", "fullscreen"):
            props = WindowProperties()
            props.set_size(*s.resolution)
            props.set_fullscreen(s.fullscreen)
            self.win.request_properties(props)
        elif key == "show_fps":
            if self.hud.debug_visible != s.show_fps:
                self.hud.toggle_debug()

    def windowEvent(self, win):
        ShowBase.windowEvent(self, win)          # keep Panda3D's default handling (close button etc.)
        if win is not self.win or win is None or not hasattr(self, "hud"):
            return
        props = win.get_properties()
        if props.has_size():
            self.hud.on_window_resized(props.get_y_size())
        if props.has_foreground() and not props.get_foreground() and not self.autotest_mode:
            self.pause()                          # alt-tab: pause and release the mouse

    # ================================================================== game events
    def radio(self, speaker, text, beep=False, seconds=4.0, voice=None):
        """Subtitle plus spoken voice. `voice` is the speaker id (found from the name if not given)."""
        sid = voice or self.voice.speaker_for_name(speaker)
        length = self.voice.play(sid, text)
        seconds = max(seconds, length + 0.4)
        self.hud.show_subtitle(speaker, text, seconds)
        if beep:
            self.audio.play("radio_beep", 0.4)

    def _on_footstep(self, player):
        m = player.motor
        self.audio.play_footstep(0.15 if m.crouching else (0.45 if m.sprinting else 0.3))

    def _on_player_damaged(self, amount, yaw, killed):
        self.hud.damage_from(yaw)
        self.audio.play("player_hurt", min(1.0, 0.3 + amount / 50.0), variation=0.1)

    def _on_soldier_killed(self, soldier, killer, zone):
        if killer is self.player and soldier.team == "enemy":
            self.kills += 1
        if soldier.team == "enemy" and soldier.mount is None:
            self.pickups.drop(soldier.position)            # a fallen enemy may leave an ammo pack

    def explode(self, position, radius, max_damage, source=None, scale=None):
        """Grenades, explosive props, shells and missiles all go through here.

        scale sets the size of the effect (1 = grenade, 2-3 = shell, 4+ = missile); by default it
        follows the blast radius."""
        if scale is None:
            scale = max(1.0, min(5.0, radius / 5.0))
        hits = self.combat.explode(position, radius, max_damage, source)
        if max_damage > 0:
            self.civilians.blast(position, radius * 0.9)
        self.effects.explosion(position, scale)
        if scale >= 2.0:                                     # clods of earth and stones
            self.debris.burst(position, int(3 + 2 * scale), "earth", 0.22 + 0.04 * scale, 6.0 + scale, 6.0 + scale)
        self.audio.play_at("explosion", position, min(1.0, 0.7 + 0.15 * scale), min_distance=10.0 * scale ** 0.7)
        self.combat.emit_noise(position, 150.0 * scale ** 0.5, getattr(source, "team", None), source)
        d = math.dist(self.player.eye_position(), position)
        reach = 30.0 * scale ** 0.7
        self.player.camera.add_trauma(max(0.0, 1.0 - d / reach) * min(1.4, 0.8 + 0.2 * scale))
        if self.player.alive and scale >= 1.8 and d < max(14.0, radius * 2.2):
            self.shell_shock(1.0 - d / max(14.0, radius * 2.2))
            if (d < radius * 1.3 and scale >= 2.5 and not self._knocked_down and self.state == "playing"
                    and self.mission is not None and self.mission.data.get("knockdown")):
                self._knocked_down = True                # thrown off your feet once per mission
                m = self.player.motor
                dx, dy = m.x - position[0], m.y - position[1]
                n = math.hypot(dx, dy) or 1.0
                self.player.knockdown((dx / n, dy / n))
                self.weapons.viewmodel.set_visible(False)
                self.timed.append([self.player.KNOCK_TIME, lambda: self.weapons.viewmodel.set_visible(True)])
        if self.player.alive and d < radius * 1.6 and scale >= 1.8:
            m = self.player.motor                    # the shock wave shoves you
            dx, dy = m.x - position[0], m.y - position[1]
            n = math.hypot(dx, dy) or 1.0
            push = 7.0 * (1.0 - d / (radius * 1.6))
            m.vx += dx / n * push
            m.vy += dy / n * push
        if source is self.player and any(k for ch, _, k in hits if ch is not self.player):
            self.hud.hit_marker(killed=True)
        return hits

    # ================================================================== frame loop
    def _update(self, task):
        dt = min(self.clock.get_dt(), C.MAX_FRAME_DT)
        self.sim_time += dt
        self.postfx.update(dt)
        self.input.update()
        state = self.state

        if self.input.was_pressed("pause"):
            if state in ("playing", "sandbox"):
                if self.paused:
                    if self._screen_stack and self._screen_stack[-1] is not self.pause_menu:
                        self.back()
                    else:
                        self.resume()
                else:
                    self.pause()
            elif state == "cinematic" and self.cinematic:
                self.cinematic.skip()
            elif state == "menu" and len(self._screen_stack) > 1:
                self.back()
        if state == "cinematic" and self.cinematic and self.input.was_pressed("skip"):
            self.cinematic.skip()
        if state == "story" and self.story and (self.input.was_pressed("skip") or self.input.was_pressed("pause")):
            self.story.skip()
        if self.input.was_pressed("toggle_debug"):
            self.hud.toggle_debug()

        if state == "menu":
            self.main_menu.update(dt)
        elif state == "story" and self.story:
            self.soldiers.update(dt)
            self.vehicles.update(dt)
            self.effects.update(dt)
            self._update_smoke(dt)
            self._update_fires(dt)
            self._update_flares(dt)
            self.story.update(dt)
        elif state == "cinematic" and self.cinematic:
            self.soldiers.update(dt)
            self.vehicles.update(dt)
            self.effects.update(dt)
            self.debris.update(dt)
            self.civilians.update(dt)
            self._update_smoke(dt)
            self._update_fires(dt)
            self.cinematic.update(dt)
        elif state in ("playing", "sandbox", "dead") and not self.paused:
            self._update_play(dt)
        self.environment.update(self.camera.get_pos(self.render), dt)
        self.environment.update_water(dt)
        self.audio.set_music_duck(0.35 if self.voice.speaking() else 1.0, dt)
        cam = self.camera.get_pos(self.render)
        self.weather.update(dt, (cam.x, cam.y, cam.z),
                            active=state in ("playing", "sandbox", "cinematic", "dead") and not self.paused)
        return task.cont

    def _update_play(self, dt):
        if self.driving and self.player.alive and self.state == "playing":
            self._update_driving(dt)
        self.player.update(dt, self.input)
        if self.drone is not None:
            self.drone.update(dt, self.input)     # after the player: the drone owns the camera
        if self.state != "dead":
            self.weapons.update(dt, self.input, allow_input=self.player.alive and self.player.knock_t < 0.0
                                and self.drone is None
                                and not self.driving)
        self.soldiers.update(dt)
        self.soldiers.cull_corpses()
        self.vehicles.update(dt)
        self.security.update(dt, self.player if self.state == "playing" and self.drone is None else None)
        self._update_timed(dt)
        self._update_flares(dt)
        self._update_smoke_clouds(dt)
        self._update_field_actions(dt)
        self.effects.update(dt)
        self.debris.update(dt)
        self.civilians.update(dt)
        self._update_smoke(dt)
        self._update_fires(dt)
        self._update_shells(dt)
        self._update_shock(dt)
        if self.mission is not None and self.state == "playing":
            self.mission.update(dt)
        if self.player.motor.z < C.KILL_Z:
            self.player.respawn()
        if self.soldiers.live_grenades_near(self.player.position, 7.0):
            self.hud.show_notice("GRENADE!", 0.3)
        if not self.player.alive and self.state in ("playing", "sandbox"):
            self.state = "dead"
            self._death_timer = 0.0
            self.weapons.viewmodel.set_visible(False)
        if self.state == "dead":
            self._death_timer += dt
            self.player.camera.offset.set_r(min(70.0, self._death_timer * 60.0))
            if self._death_timer > 2.5:
                if self.mission is not None:
                    self.mission.fail("You were killed in action.")
                else:
                    self.player.respawn()
                    self.state = "sandbox"
                    self.weapons.viewmodel.set_visible(True)
        self.hud.update(dt, self.player, self.weapons, self.kills,
                        (f"tris {self.environment.stats.get('triangles', 0):,}  soldiers {len(self.soldiers.soldiers)}"
                         f"  vehicles {len(self.vehicles.vehicles)}",))
        self.hud.update_tags(self.tagged)
        cam = self.camera.get_pos(self.render)
        for s in self.squad.values():                 # name tags only at a distance (not in your face)
            label = s.model.label if s.model is not None else None
            if label is not None:
                hide = not s.alive or (s.motor.x - cam.x) ** 2 + (s.motor.y - cam.y) ** 2 < 16.0
                if hide != label.is_hidden():
                    label.hide() if hide else label.show()

    # ------------------------------------------------------------------ fires
    def add_fire(self, pos, size=1.0):
        glow = self.effects.make_glow(pos, size)
        self.fires.append({"pos": tuple(pos), "size": size, "timer": 0.0, "glow": glow})

    def clear_fires(self):
        for f in self.fires:
            f["glow"].remove_node()
        self.fires = []

    def _update_fires(self, dt):
        cam = self.camera.get_pos(self.render)
        px, py, pz = self.player.position
        for f in self.fires:
            x, y, z = f["pos"]
            if (x - cam.x) ** 2 + (y - cam.y) ** 2 > 140.0 ** 2:
                continue                          # too far to see - save particles
            f["timer"] -= dt
            while f["timer"] <= 0.0:
                f["timer"] += 0.09 / max(0.5, f["size"])
                self.effects.fire(f["pos"], f["size"])
            if self.state == "playing" and math.hypot(px - x, py - y) < 0.9 * f["size"] and abs(pz - z) < 1.5:
                self.player.take_damage(25.0 * dt, None, "legs", (0.0, 0.0, 1.0))

    def shell_shock(self, amount):
        """A blast close to you: white flash, blurred sight, muffled hearing with ringing, staggering."""
        if amount <= 0.05 or self.state not in ("playing", "sandbox"):
            return
        seconds = 1.2 + 3.0 * amount
        if seconds > self.shock + 0.5:
            self.audio.play_unducked("tinnitus", min(1.0, 0.4 + amount))
        self.shock = max(self.shock, seconds)
        self.hud.flash_white(0.5 + 1.2 * amount)
        self.player.camera.add_trauma(0.4 + 0.6 * amount)

    def _update_shock(self, dt):
        if self.shock <= 0.0:
            return
        self.shock = max(0.0, self.shock - dt)
        k = min(1.0, self.shock / 2.5)
        self.player.shock = k
        self.audio.set_duck(1.0 - 0.8 * k)
        if self.shock > 0.0:
            self.postfx.set_dof(0.4, 0.3, 0.95 * k)
        else:
            self.postfx.set_dof(None)
            self.player.shock = 0.0

    SHELL_FALL = 2.4                     # seconds a shell is visible in the sky before impact

    def _update_shells(self, dt):
        """Artillery shells: fall from the sky along a smoking trail, then explode."""
        pending = []
        for shell in self.shells:
            if len(shell) < 9:                               # old-style entry: [t, pos, whistled, r, dmg, (scale)]
                shell += [2.5, (0.15, 1.0), None, 0.0][len(shell) - 5:]
            was = shell[0]
            shell[0] -= dt
            if was > self.SHELL_FALL >= shell[0] and shell[7]:
                # Aimed shell: pick a soldier of the target group and come down right on him.
                group = shell[7]
                if group.startswith("civ"):
                    spots = [c.position for c in self.civilians.alive()]
                elif group.startswith("team:"):
                    spots = [s.position for s in self.soldiers.soldiers if s.team == group[5:] and s.alive]
                else:
                    spots = [s.position for s in self.soldiers.group_alive(group)]
                px, py = shell[1][0], shell[1][1]
                spots = [p for p in spots if math.hypot(p[0] - px, p[1] - py) < 35.0]      # stay in the area
                if spots:
                    r = self.soldiers.rng
                    x, y, z = r.choice(spots)
                    shell[1] = (x + r.uniform(-1.5, 1.5), y + r.uniform(-1.5, 1.5), z + 0.2)
            if not shell[2] and shell[0] <= 1.2:
                shell[2] = True
                self.audio.play_at("shell_whistle", shell[1], 0.7, min_distance=12.0)
            if shell[0] <= 0.0:
                self.explode(shell[1], shell[3], shell[4], None, shell[5])
                continue
            if shell[0] <= self.SHELL_FALL:
                self._shell_trail(shell, dt)
            pending.append(shell)
        self.shells = pending

    def _shell_trail(self, shell, dt):
        t = 1.0 - shell[0] / self.SHELL_FALL                # 0 = high in the sky, 1 = impact
        dx, dy = shell[6]
        n = math.hypot(dx, dy) or 1.0
        px, py, pz = shell[1]
        dist = 170.0 * (1.0 - t)                          # comes in low over the horizon (~30 degrees)
        pos = (px + dx / n * dist * 0.85, py + dy / n * dist * 0.85, pz + dist * 0.5)
        # One puff every ~1.2 m along the path since the last frame: a solid smoke line.
        prev = shell[8] if isinstance(shell[8], tuple) else pos
        seg = math.dist(prev, pos)
        n = min(10, max(1, int(seg / 1.2)))
        for i in range(n):
            q = tuple(prev[j] + (pos[j] - prev[j]) * (i + 1) / n for j in range(3))
            self.effects.spawn("smoke", q, life=6.0, size=(1.3, 5.0), alpha=0.75, color=(0.4, 0.39, 0.37),
                               texture="smoke", drag=0.4)
        shell[8] = pos
        if True:
            self.effects.spawn("fire", pos, life=0.07, size=(1.6, 0.9), texture="soft", blend="add",
                               color=(1.0, 0.7, 0.35))

    def _update_smoke(self, dt):
        alive = []
        for emitter in self.smoke_emitters:
            emitter[1] -= dt
            emitter[2] -= dt
            if emitter[2] <= 0.0:
                emitter[2] = 0.45
                self.effects.smoke_plume(emitter[0])
            if emitter[1] > 0.0:
                alive.append(emitter)
        self.smoke_emitters = alive

    # ================================================================== rides, drone, stealth, intel
    def start_ride(self, vehicle_id, seat, squad_seats, drive=False):
        self.end_ride()
        v = self.vehicles.find(vehicle_id)
        if v is not None:
            self.ride = Ride(self, v, seat, squad_seats, drive=drive)

    @property
    def driving(self):
        return self.ride is not None and self.ride.drive

    def end_ride(self, pos=None, heading=None, squad_positions=None):
        if self.ride is not None:
            self.ride.end(pos, heading, squad_positions)
            self.ride = None
        self.player.mount = None

    def start_drone(self, pos, heading=0.0, max_range=200.0):
        self.end_drone()
        self.drone = DroneController(self, pos, heading, max_range)

    def end_drone(self):
        if self.drone is not None:
            drone, self.drone = self.drone, None
            drone.end()

    def nvg_grading(self):
        return stealth.NVG_GRADING

    def set_nvg(self, on, available=None):
        if available is not None:
            self.nvg_available = available
        on = bool(on and self.nvg_available)
        self.nvg_on = on
        if self.drone is None:
            if self.postfx.enabled:
                self.postfx.set_override(stealth.NVG_GRADING if on else None)
            elif on:
                self.render.set_color_scale(0.7, 2.2, 0.8, 1.0)     # simple fallback without post-processing
            else:
                self.render.clear_color_scale()
        self.hud.set_nvg(on, self.nvg_available)

    def after(self, seconds, fn):
        """Run fn after a delay in game time (paused while the game is paused)."""
        self.timed.append([float(seconds), fn])

    def _update_timed(self, dt):
        due = []
        for t in self.timed:
            t[0] -= dt
            if t[0] <= 0.0:
                due.append(t)
        for t in due:
            self.timed.remove(t)
            t[1]()

    # ------------------------------------------------------------------ flares
    def fire_flare(self, pos, seconds=25.0):
        from panda3d.core import PointLight
        light = PointLight("flare")
        light.set_color((2.4, 1.2, 0.9, 1.0))
        light.set_attenuation((1.0, 0.0, 0.0008))
        np_ = self.render.attach_new_node(light)
        np_.set_pos(*pos)
        self.render.set_light(np_)
        self.flares.append({"pos": list(pos), "time": float(seconds), "light": np_, "timer": 0.0})
        self.audio.play_at("flare_pop", pos, 0.8, min_distance=20.0)

    def _update_flares(self, dt):
        keep = []
        for f in self.flares:
            f["time"] -= dt
            f["pos"][2] = max(4.0, f["pos"][2] - 0.7 * dt)
            f["light"].set_pos(*f["pos"])
            f["timer"] -= dt
            if f["timer"] <= 0.0:
                f["timer"] = 0.05
                self.effects.spawn("fire", tuple(f["pos"]), life=0.15, size=(1.2, 0.6), texture="soft", blend="add",
                                   color=(1.0, 0.45, 0.35))
                self.effects.spawn("smoke", tuple(f["pos"]), life=2.5, size=(0.3, 1.6), alpha=0.25,
                                   color=(0.9, 0.6, 0.55), texture="smoke", drag=1.0)
            if f["time"] > 0.0:
                keep.append(f)
            else:
                self.render.clear_light(f["light"])
                f["light"].remove_node()
        self.flares = keep
        self.soldiers.lit_zones = self.base_lit_zones + [(f["pos"][0], f["pos"][1], 55.0) for f in self.flares]

    def _clear_flares(self):
        for f in self.flares:
            self.render.clear_light(f["light"])
            f["light"].remove_node()
        self.flares = []

    # ------------------------------------------------------------------ demolition
    def _small_model(self, name, build):
        from panda3d.core import NodePath
        from environments.geometry import MeshBuilder
        mats = self.environment.materials
        mb = MeshBuilder(mats.uv_scales())
        build(mb)
        return mb.build(NodePath(name), mats, name=name)

    def place_charge(self, pos):
        def build(mb):
            mb.box("paint", 0, 0, 0, 0.3, 0.12, 0.2, (0.42, 0.42, 0.3))
            mb.box("metal", 0, -0.065, 0.08, 0.12, 0.02, 0.07, (0.1, 0.1, 0.1))
            mb.box("emissive", 0.09, -0.07, 0.15, 0.03, 0.02, 0.03, (1.0, 0.1, 0.05))
        node = self._small_model("c4", build)
        node.reparent_to(self.render)
        node.set_pos(pos[0], pos[1], pos[2] - 0.4)
        self.charges.append(node)

    def clear_charges(self, near=None, radius=30.0):
        """Remove placed charges (all, or only those within radius of any point in `near`)."""
        keep = []
        for n in self.charges:
            p = n.get_pos()
            if near is None or any(math.dist((p.x, p.y, p.z), b) < radius for b in near):
                n.remove_node()
            else:
                keep.append(n)
        self.charges = keep

    def collapse_bridge(self, blasts, vehicle_ids):
        """Scripted demolition: charges go off one after another, tanks on the span fall into the river."""
        self.clear_charges(near=[tuple(b) for b in blasts])
        for i, b in enumerate(blasts):
            self.after(i * 0.3, lambda b=tuple(b): self.explode(b, 9.0, 160.0))
        self.player.camera.add_trauma(0.8)
        for vid in vehicle_ids:
            v = self.vehicles.find(vid)
            if v is not None and hasattr(v, "fall"):
                self.after(0.4, v.fall)
        self.smoke_emitters.extend([[tuple(b), 40.0, 0.0] for b in blasts])

    # ------------------------------------------------------------------ intel
    def _make_intel_node(self, spec):
        def build(mb):
            mb.box("paint", 0, 0, 0, 0.34, 0.26, 0.03, (0.62, 0.52, 0.34))              # folder
            mb.box("paint", 0.02, 0.01, 0.03, 0.28, 0.2, 0.01, (0.9, 0.88, 0.8))        # papers
            mb.box("emissive", -0.12, 0.09, 0.04, 0.05, 0.03, 0.005, (0.3, 0.7, 1.0))   # glowing tab
        node = self._small_model("intel", build)
        node.reparent_to(self.render)
        x, y, z = spec["pos"]
        node.set_pos(x, y, z)
        node.set_h(spec.get("heading", 20.0))
        glow = self.effects.make_glow((x, y, z - 0.02), 0.12, (0.35, 0.75, 1.0))
        glow.wrt_reparent_to(node)
        return node

    # ------------------------------------------------------------------ per-frame field actions
    def _make_ammo_node(self, pos):
        def build(mb):
            mb.box("paint", 0, 0, 0, 0.34, 0.22, 0.18, (0.3, 0.34, 0.2))              # ammo pouch
            mb.box("metal", 0, -0.115, 0.05, 0.1, 0.02, 0.07, (0.15, 0.15, 0.14))     # buckle
            mb.box("emissive", 0, 0, 0.18, 0.2, 0.08, 0.012, (1.0, 0.8, 0.3))         # bright strip: easy to spot
        node = self._small_model("ammo_pack", build)
        node.reparent_to(self.render)
        x, y, z = pos
        node.set_pos(x, y, z + 0.02)
        glow = self.effects.make_glow((x, y, z + 0.02), 0.14, (1.0, 0.75, 0.3))
        glow.wrt_reparent_to(node)
        return node

    def _update_field_actions(self, dt):
        inp = self.input
        walking = self.player.alive and self.player.mount is None and self.drone is None
        taken = self.pickups.update(dt, self.player.position if walking else None, self.weapons.needs_ammo())
        if taken is not None:
            self.weapons.pickup_ammo(AMMO_FRACTION)
            self.audio.play("reload_in", 0.8)
            self.hud.show_notice("AMMO PICKED UP", 1.2)
        if self.state not in ("playing", "sandbox") or not self.player.alive:
            self.hud.set_action_hint(None)
            return
        if inp.was_pressed("nvg") and self.nvg_available and self.drone is None:
            self.set_nvg(not self.nvg_on)
            self.audio.play("nvg_on", 0.5)
        hint = None
        self._takedown_cooldown = max(0.0, self._takedown_cooldown - dt)
        if self.drone is None and self.player.mount is None:
            target = stealth.takedown_target(self.player.position, self.player.camera.look.yaw,
                                             self.soldiers.soldiers)
            if target is not None:
                hint = "[V] SILENT TAKEDOWN" if stealth.is_unaware(target) else "[V] MELEE"
                if inp.was_pressed("takedown") and self._takedown_cooldown <= 0.0:
                    self._takedown_cooldown = 0.8
                    silent = stealth.perform_takedown(self.player, target)
                    self.takedowns += 1
                    self.audio.play("takedown", 0.8)
                    self.player.camera.add_trauma(0.15)
                    self.hud.hit_marker(killed=True)
                    self.hud.show_notice("SILENT TAKEDOWN" if silent else "TAKEDOWN", 1.5)
                    if not silent:
                        self.combat.emit_noise(self.player.position, 20.0, "friendly", self.player)
                    hint = None
            item, progress, got = self.intel.update(dt, self.player.eye_position(), inp.is_down("interact"))
            if got is not None:
                self.audio.play("objective", 0.5)
                self.hud.show_notice(f"INTEL FOUND: {got.name.upper()}  ({self.intel.found}/{self.intel.total})", 3.0)
            elif item is not None:
                hint = f"Hold [E] to collect intel: {item.name}" + (f"  {int(progress * 100)}%" if progress else "")
        if not self.driving:                          # the speed read-out uses the same line
            self.hud.set_action_hint(hint)
        # Falling into the river is fatal (the banks are walled off; this is a safety net).
        if self.water_rect is not None and self.player.mount is None and self.state == "playing":
            px, py, pz = self.player.position
            if self.in_water(px, py) and pz < self.water_z - 0.5:
                self.player.take_damage(1000.0, None, "body", (0.0, 0.0, 1.0))

    # ------------------------------------------------------------------ smoke grenades and flashbangs
    SMOKE_RADIUS = 5.5

    def smoke_grenade(self, pos):
        self.smoke_clouds.append({"pos": tuple(pos), "t": 0.0, "life": 24.0, "timer": 0.0})
        self.audio.play_at("smoke_pop", pos, 0.9, min_distance=6.0)

    def smoke_radius(self, cloud):
        grow = min(1.0, cloud["t"] / 2.5)
        fade = min(1.0, max(0.0, (cloud["life"] - cloud["t"]) / 4.0))
        return self.SMOKE_RADIUS * grow * fade

    def _update_smoke_clouds(self, dt):
        keep = []
        rng = self.vehicles.rng
        for c in self.smoke_clouds:
            c["t"] += dt
            if c["t"] >= c["life"]:
                continue
            keep.append(c)
            c["timer"] -= dt
            if c["timer"] <= 0.0 and c["t"] < c["life"] - 3.0:
                c["timer"] = 0.11
                r = self.smoke_radius(c)
                x, y, z = c["pos"]
                for _ in range(2):
                    a, d = rng.uniform(0, 6.283), rng.uniform(0, max(0.5, r * 0.8))
                    self.effects.spawn("smoke", (x + d * math.cos(a), y + d * math.sin(a), z + rng.uniform(0.3, 2.5)),
                                       vel=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0.15), life=6.0,
                                       size=(1.8, 4.5), alpha=0.75, color=(0.78, 0.78, 0.76), texture="smoke",
                                       drag=0.8)
        self.smoke_clouds = keep
        self.soldiers.smoke_clouds = [(c["pos"][0], c["pos"][1], c["pos"][2] + 1.3, self.smoke_radius(c))
                                      for c in keep if self.smoke_radius(c) > 0.5]

    def flashbang(self, pos, owner=None):
        """Blinds every enemy who can see the blast for a few seconds (and you, if you look at it)."""
        self.audio.play_at("flashbang", pos, 1.0, min_distance=12.0)
        self.effects.spawn("flash", pos, life=0.25, size=(4.0, 8.0), texture="flash", blend="add",
                           color=(1.0, 1.0, 1.0))
        self.combat.emit_noise(pos, 40.0, getattr(owner, "team", None), owner)
        for s in self.soldiers.soldiers:
            if s.team != "enemy" or not s.alive:
                continue
            d = math.dist(s.eye_position(), pos)
            if d > 14.0 or not self.collision_world.line_of_sight(s.eye_position(), (pos[0], pos[1], pos[2] + 0.2)):
                continue
            facing = abs(((math.degrees(math.atan2(-(pos[0] - s.motor.x), pos[1] - s.motor.y)) - s.facing)
                          + 180) % 360 - 180) < 100
            s.ai.stun((5.0 if facing else 2.5) * (1.0 - d / 18.0) + 1.0)
        eye = self.player.eye_position()
        d = math.dist(eye, pos)
        if d < 16.0 and self.collision_world.line_of_sight(eye, (pos[0], pos[1], pos[2] + 0.2)):
            fwd = self.camera.get_quat(self.render).get_forward()
            v = [(pos[i] - eye[i]) / max(d, 0.1) for i in range(3)]
            looking = sum(v[i] * fwd[i] for i in range(3)) > 0.3
            self.hud.flash_white((3.0 if looking else 1.0) * (1.0 - d / 16.0))
            self.player.camera.add_trauma(0.3)

    # ------------------------------------------------------------------ driving
    def _update_driving(self, dt):
        jeep = self.ride.vehicle
        inp = self.input
        old_heading = jeep.heading
        jeep.drive(dt, inp.axis("move_forward", "move_backward"), inp.axis("move_right", "move_left"),
                   inp.is_down("jump"))
        self.player.camera.look.yaw += jeep.heading - old_heading        # the view turns with the car
        for kind, data in jeep.events:
            if kind == "ram":
                for pid in data:
                    entry = self.environment.dynamic.get(pid)
                    self.ctx.destroy_prop(pid, False)
                    if self.mission is not None:
                        self.mission.destroyed.append((pid, self.mission.index))
                    if entry:
                        x, y, z = entry["pos"]
                        for _ in range(8):
                            self.effects.spawn("smoke", (x, y, z + 0.6), vel=(0, 0, 1.5), life=1.2, size=(0.4, 1.4),
                                               alpha=0.5, color=(0.6, 0.6, 0.58), texture="smoke", drag=2.0)
                self.audio.play("crash", 1.0)
                self.player.camera.add_trauma(0.5)
                self.hud.show_notice("SMASHED THROUGH!", 1.2)
            elif kind == "crash":
                self.audio.play("crash", min(1.0, data / 15.0))
                self.player.camera.add_trauma(min(0.8, data / 20.0))
                if data > 12.0:
                    self.player.take_damage((data - 12.0) * 3.0, None, "torso", (0.0, 1.0, 0.0))
        jeep.events.clear()
        # Running enemies over.
        if abs(jeep.velocity) > 5.0:
            fx, fy = jeep.forward()
            front = (jeep.pos[0] + fx * 1.8 * (1 if jeep.velocity > 0 else -1),
                     jeep.pos[1] + fy * 1.8 * (1 if jeep.velocity > 0 else -1))
            for s in self.soldiers.soldiers:
                if s.team == "enemy" and s.alive and s.mount is None and \
                        math.hypot(s.motor.x - front[0], s.motor.y - front[1]) < 1.8:
                    s.take_damage(500.0, self.player, "torso", (fx, fy, 0.3))
                    self.audio.play("impact_flesh", 0.8)
        self.hud.set_action_hint(f"{abs(jeep.velocity) * 3.6:3.0f} km/h    [W/S] drive   [A/D] steer   [Space] brake")
