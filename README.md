# OPERATION SHADOW

An original single-player 3D first-person shooter campaign written in **Python 3 + Panda3D**.

> Current state: full FPS gameplay, AI soldiers, squad, campaign framework (16 missions planned).
> Playable: **Mission 1 "First Light"** (outpost defence), **Mission 2 "The Line Breaks"** (trench warfare),
> **Mission 3 "Ashfall"** (escort a wounded squad mate through a burning town) and
> **Mission 4 "No Way Back"** (night river raid: boat insertion, recon drone, stealth, C4, drones, gunship,
> tanks, bridge demolition and helicopter extraction - about 18-22 minutes) and
> **Mission 5 "Dead Drop"** (Elias Crane alone in a rainy harbour: suppressed weapons, security cameras,
> photographing targets, hacking a computer, hostage rescue, escort and a speedboat escape) and
> **Mission 6 "The Broker"** (a sunny lakeside villa: meet Mira Sol, survive an ambush with smoke and
> flashbangs, silence a mortar, then drive a jeep to the ferry with enemy jeeps behind you).
>
> Missions give a **Gold / Silver / Bronze rank** (time, retries, accuracy, stealth, intel) and some
> hide optional **intel documents**.

## 1. Install (one time)

Double-click **`setup.bat`**. It creates a private Python environment (`.venv`) inside this folder
and installs Panda3D, numpy and pytest. Nothing outside this folder is changed.

## 2. Play

Double-click **`run_game.bat`** - or, in a terminal opened in this folder:

```
.venv\Scripts\python.exe main.py
```

Main menu: **New Campaign** starts Mission 1 · **Continue** resumes your campaign ·
**Mission Selection** shows all 16 missions · **Settings** · **Controls** · **Credits** · **Exit Game**.

### Controls

| Key | Action |
|---|---|
| W A S D | move |
| Mouse | look |
| Shift (hold) | sprint |
| Space | jump / skip cutscene |
| Ctrl or C (hold) | crouch |
| Left mouse | fire |
| Right mouse | aim down sights |
| R | reload (fallen enemies drop ammo packs: walk over one to refill) |
| 1 2 3 4 / wheel / Q | switch weapon / last weapon |
| G / T | throw grenade / switch grenade type (frag, smoke, flashbang) |
| W S A D, Space | drive a jeep (go, reverse, steer, brake) |
| E (hold) | interact / pick up intel |
| V | silent takedown (from behind, while the enemy is unaware) |
| N | night-vision goggles (night missions) |
| Space / C | recon drone up / down (while flying the drone) |
| Esc | pause menu |
| F3 | debug info (FPS, position) |

## 3. The story (original)

The Varn Directorate invades the Kareth Republic without warning. **Pvt. Tomas Halden** fights to survive
the collapse of the frontier, while disgraced intelligence officer **Elias Crane** hunts the people behind
**Project TEMPEST**. The two stories meet in the final act. All names, places and events are fictional.

## 4. Run the tests

Double-click **`run_tests.bat`**, or:

```
.venv\Scripts\python.exe -m pytest              # 226 logic tests (no window)
.venv\Scripts\python.exe main.py --autotest     # plays the real game by itself: menus, movement,
                                                # weapons, AI combat and Missions 1 to 6
.venv\Scripts\python.exe main.py --autotest --only m04       # just the Mission 4 play-test
.venv\Scripts\python.exe main.py --autotest --views --maps tamsin_river   # screenshots of one map
```

The play-test uses its own save/settings files, ignores your keyboard and mouse, and never grabs your cursor.

## 5. Project layout

```
main.py                     start the game
config/                     constants (tuning, key bindings) and saved settings
core/game.py                window, game states, menus <-> missions, frame loop
core/mission_context.py     lets mission scripts control the game
core/autotest.py            automated in-game play-test
core/ride.py, core/drone.py riding boats/helicopters, flying the recon drone
core/stealth.py             silent takedowns, night vision, intel pick-ups
systems/security.py         security cameras (sweep, detect, can be shot out)
systems/weather.py          rain
tools/make_*.py             generators for the Mission 4/5 maps and mission scripts
player/                     movement physics, camera, health, player
weapons/                    weapon logic, 4 weapon types, grenades, first-person models, weapon manager
enemies/                    soldier model + animation, soldier, AI state machine, soldier manager
missions/                   mission runner, objectives, cinematics, campaign/mission data loading, ranks
vehicles/                   helicopters, tanks, boats, drones: paths, models, weapons, rockets
systems/                    collision, combat (hit detection), navigation (A*), effects, audio, sound synth, saves
environments/               procedural textures, 3D props, map loader, sky, lighting
ui/                         HUD, main menu, campaign/briefing/results screens, settings, pause menu
data/                       weapons.json, enemies.json, characters.json, campaign.json, maps/, missions/
assets/                     put real models / textures / sounds / fonts here (see assets/README.txt)
tests/                      automated tests
```

## 6. Save files

`data/settings.json` (options) and `data/progress.json` (campaign) are created automatically.
If either gets corrupted it is backed up (`.corrupt`) and replaced, so the game always starts.
Logs: `data/logs/game.log`.
