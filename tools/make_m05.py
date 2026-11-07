"""Generates data/missions/m05_dead_drop.json (Mission 5: Elias Crane at Port Calder harbour).

Run:  .venv\\Scripts\\python.exe tools\\make_m05.py
"""
import json
import sys

W = -1.3


def radio(speaker, text, delay=0.0, seconds=None):
    a = {"action": "radio", "speaker": speaker, "text": text}
    if delay:
        a["delay"] = delay
    a["seconds"] = seconds or max(2.5, min(6.0, len(text) / 17.0))
    return a


def act(name, delay=0.0, **kw):
    a = {"action": name, **kw}
    if delay:
        a["delay"] = delay
    return a


def unit(x, y, heading=180, **kw):
    return {"pos": [x, y], "heading": heading, **kw}


def camera(cid, x, y, z, heading, sweep=35, period=7.0, rng=22):
    return act("spawn_camera", id=cid, pos=[x, y, z], heading=heading, sweep=sweep, period=period, range=rng,
               pitch=-25)


ESCAPE_PATH = [[94.4, -68, W], [95, -90, W], [80, -130, W], [20, -170, W], [-80, -200, W], [-200, -230, W],
               [-320, -260, W], [-400, -280, W]]
ALARM_GROUPS = ["market", "quay", "officers", "office", "warehouse", "captors"]

steps = [
    # 1 ------------------------------------------------------------------ to the overlook
    {"id": "overlook",
     "objective": {"type": "reach", "text": "Get to the harbour master's roof", "pos": [-70, -8, 3.67], "radius": 5},
     "on_start": [
         act("spawn", group="market", units=[
             unit(-108, 29, 90, patrol=[[-108, 29], [-66, 29]]), unit(-66, 40, 270, patrol=[[-66, 40], [-108, 40]]),
             unit(-60, 31, 90, profile="recruit"), unit(-113, 46, 0, profile="recruit")]),
         act("spawn", group="quay", units=[
             unit(-32, -14, 90), unit(-50, -21, 90, patrol=[[-50, -21], [8, -21]]), unit(0, -28, 180, profile="recruit")]),
         act("spawn", group="officers", units=[
             unit(-18, -27, 180, hold=[-18, -27, 180]), unit(-13, -30.5, 160, hold=[-13, -30.5, 160]),
             unit(-10, -27, 200, hold=[-10, -27, 200])]),
         act("spawn", group="office", units=[
             unit(4, 30, 90, patrol=[[4, 30], [26, 30], [26, 46], [4, 46]]), unit(10, 36.5, 90, profile="regular")]),
         act("spawn", group="warehouse", units=[
             unit(80, 6, 180, hold=[80, 6, 180]), unit(66, 0, 90, patrol=[[66, 0], [98, 0]], profile="recruit")]),
         camera("cam_office_w", 6.8, 32.9, 3.0, 160),
         camera("cam_office_e", 23.2, 32.9, 3.0, -160),
         camera("cam_office_in", 22.4, 42.0, 2.9, 130, sweep=30, period=6.0, rng=16),
         camera("cam_warehouse", 72.4, 7.7, 5.0, 180, sweep=40, period=9.0),
         act("alarm_arm"),
         radio("wren", "Brandt missed the meet, Elias. His phone last pinged here, on the docks.", 1.0),
         radio("crane", "Then the Directorate got here first. I'll find him.", 6.0),
         radio("wren", "The harbour master's roof overlooks the ship. Stairs on the east side.", 10.0),
         radio("wren", "Their people are everywhere. Stay quiet - your weapons are suppressed. [V] to take them down.",
               16.0, 5.0),
     ],
     "on_complete": [
         act("checkpoint", pos=[-70, -8, 3.67], heading=-110),
     ]},
    # 2 ------------------------------------------------------------------ photographs
    {"id": "photos",
     "objective": {"type": "photograph", "group": "officers", "count": 3, "range": 140, "angle": 3.0,
                   "text": "Photograph the officers by the ship (aim down sights and hold steady)"},
     "on_start": [
         radio("wren", "Three officers by the ship. I need their faces - use your scope.", 0.5),
     ],
     "on_complete": [
         radio("wren", "Running the faces... two Directorate security. The third...", 0.5),
         radio("wren", "Elias, the man in the grey coat. It's Desmond Harrow.", 5.0),
         radio("crane", "Harrow's dead. I carried his coffin.", 9.5),
         radio("wren", "Then somebody else was in it. Find Brandt - his dead drop is in the fish market lockers.", 13.0),
         act("checkpoint", delay=1.0, pos=[-70, -8, 3.67], heading=0),
     ]},
    # 3 ------------------------------------------------------------------ dead drop
    {"id": "dead_drop",
     "objective": {"type": "interact", "text": "Check Brandt's dead drop in the fish market", "pos": [-100, 46.2, 1.2],
                   "radius": 2.4, "hold": 1.5, "prompt": "Hold E to open the locker"},
     "on_start": [],
     "on_complete": [
         act("sound", sound="camera_shutter"),
         radio("crane", "A note. 'Copied the manifest to the harbour office computer. If I'm gone - warehouse four.'",
               0.5, 5.5),
         radio("wren", "Office first. They've got cameras on it - shoot them out or stay out of the red.", 6.5, 5.0),
         act("checkpoint", delay=1.0, pos=[-98, 42, 0], heading=-60),
     ]},
    # 4 ------------------------------------------------------------------ get inside the office
    {"id": "office",
     "objective": {"type": "reach", "text": "Get inside the harbour office", "pos": [15, 38.5, 0.25], "radius": 4.5},
     "on_start": [],
     "on_complete": []},
    # 5 ------------------------------------------------------------------ download
    {"id": "download",
     "objective": {"type": "download", "text": "Download the shipping data", "pos": [19, 41.5, 1.1], "seconds": 50,
                   "radius": 7.0, "prompt": "Hold E to start copying the files"},
     "on_start": [
         radio("wren", "That's the machine. Plug me in.", 0.5),
     ],
     "on_complete": [
         radio("wren", "Got it. All of it. Now get Brandt.", 0.5),
         act("refill_ammo", delay=1.0),
         act("checkpoint", delay=2.0, pos=[15, 30, 0.0], heading=-90),
     ]},
    # 6 ------------------------------------------------------------------ hostage rescue
    {"id": "rescue",
     "objective": {"type": "rescue", "group": "captors", "hostage": "brandt", "seconds": 6.0,
                   "text": "Rescue Brandt from warehouse four", "pos": [80, 20, 1.0],
                   "warning": "THEY'RE GOING TO EXECUTE BRANDT - TAKE THEM OUT!"},
     "on_start": [
         act("spawn_squad", id="brandt", pos=[80, 27], heading=180, profile="wounded", captive=True),
         act("spawn", group="captors", units=[
             unit(77, 25, -56, hold=[77, 25, -56]), unit(83, 25, 56, hold=[83, 25, 56], profile="veteran"),
             unit(80, 31, 180, hold=[80, 31, 180])]),
         radio("wren", "Warehouse four is the big one by the water. If they hear you coming, he's dead.", 1.0, 4.5),
     ],
     "on_complete": [
         act("set_captive", id="brandt", value=False),
         radio("brandt", "Crane? You came... I can't feel my leg.", 1.0),
         radio("crane", "Lean on the crates and walk. There's a boat at the east pier.", 4.5),
         act("checkpoint", delay=2.0, pos=[80, 20, 0.0], heading=0),
     ]},
    # 7 ------------------------------------------------------------------ escort to the pier
    {"id": "escort",
     "objective": {"type": "escort", "target": "brandt", "text": "Get Brandt to the east pier",
                   "route": [[80, 22], [83, 10], [86, -4], [89, -20], [90, -30], [90, -45], [90, -64]], "radius": 3.0},
     "on_start": [
         act("alarm_disarm"),
         act("loop_start", sound="alarm_loop", volume=0.3),
         radio("wren", "Every radio in the port just lit up. They're coming for you.", 2.0),
         act("spawn", delay=4.0, group="yard", units=[
             unit(52, -18, 90, alert=[86, -10]), unit(58, -2, 90, alert=[86, -6]),
             unit(66, -10, 90, alert=[88, -12], profile="gunner")]),
         act("spawn", delay=22.0, group="yard", units=[
             unit(108, 6, 200, alert=[89, -20]), unit(114, -4, 240, alert=[90, -28])]),
         act("spawn_vehicle", delay=30.0, kind="patrol_boat", id="pb0", health=220, speed=7.0, loop=True,
             path=[[120, -60, W], [100, -86, W], [70, -80, W], [60, -55, W], [90, -48, W]]),
         radio("brandt", "Boat! On the water!", 34.0),
         act("spawn", delay=40.0, group="yard", units=[
             unit(60, -28, 90, alert=[90, -36]), unit(70, -28, 90, alert=[90, -40], profile="veteran")]),
     ],
     "on_complete": [
         act("spawn_vehicle", kind="player_boat", id="escape", speed=8.5, paused=True, path=ESCAPE_PATH),
         radio("crane", "In the boat. Go!", 0.5),
     ]},
    # 8 ------------------------------------------------------------------ board
    {"id": "board",
     "objective": {"type": "reach", "text": "Get in the boat", "pos": [91.6, -68, 0.25], "radius": 2.6},
     "on_start": [],
     "on_complete": [
         act("checkpoint", pos=[91.6, -66, 0.25], heading=180),
     ]},
    # 9 ------------------------------------------------------------------ helicopter chase
    {"id": "chase",
     "objective": {"type": "destroy", "text": "Shoot down the pursuing helicopter", "targets": ["gunship"]},
     "on_start": [
         act("spawn_vehicle", kind="player_boat", id="escape", speed=8.5, paused=True, path=ESCAPE_PATH),
         act("start_ride", vehicle="escape", seat=[0.6, -0.6, -0.1], squad={"brandt": [-0.5, -2.0, -0.1]}),
         act("vehicle_command", delay=1.0, id="escape", paused=False),
         act("give_weapon", id="rl3", ammo=3),
         radio("wren", "There's a launcher in the boat locker. You'll want it.", 1.5),
         act("spawn_vehicle", delay=6.0, kind="attack_helicopter", id="gunship", speed=34.0, health=900,
             path=[[260, -10, 45], [170, -60, 30], [110, -110, 20]], orbit_radius=42, altitude=16),
         act("spawn_vehicle", delay=3.0, kind="patrol_boat", id="pb1", health=240, speed=8.0, loop=False,
             path=[[150, -80, W], [120, -130, W], [40, -175, W], [-70, -210, W], [-200, -240, W], [-330, -270, W]]),
         act("spawn_vehicle", delay=12.0, kind="patrol_boat", id="pb2", health=240, speed=9.0, loop=False,
             path=[[150, -60, W], [110, -110, W], [30, -160, W], [-90, -195, W], [-220, -228, W], [-340, -262, W]]),
         radio("wren", "Helicopter lifting off from the naval yard - it's coming for you!", 6.5),
         radio("brandt", "Two boats behind us!", 15.0),
     ],
     "on_complete": [
         radio("crane", "Helicopter's down.", 1.0),
     ]},
    # 10 ----------------------------------------------------------------- open sea
    {"id": "getaway",
     "objective": {"type": "ride", "text": "Get out to sea"},
     "on_start": [
         radio("wren", "Keep going. The rain will hide you once you're past the breakwater.", 1.0),
     ],
     "on_complete": [
         act("complete_mission", delay=2.0),
     ]},
]

mission = {
    "id": "m05_dead_drop",
    "map": "port_calder",
    "date": "Day 9 - 19:10",
    "briefing": [
        "Lio Brandt, a shipping clerk in Port Calder, copied a cargo manifest marked TEMPEST and called the one "
        "number he was given for emergencies: Isa Wren's.",
        "He never made the meeting. Directorate security has locked down the harbour, and Brandt's last signal "
        "came from the docks.",
        "Elias Crane goes in alone, at dusk, in the rain: find out who is running the operation, recover the "
        "data and get Brandt out alive.",
    ],
    "story_objective": "Recover Brandt's TEMPEST data and get him out of Port Calder.",
    "gameplay_objective": "Stealth (suppressed weapons, V takedowns, security cameras), photograph targets "
                          "through the scope, download files while defending the terminal, rescue a hostage, "
                          "escort him to a boat and escape a helicopter. Optional: 3 intel, stay undetected.",
    "par_time": 1140,
    "night": {"visibility": 0.7, "lit": []},
    "player": {"spawn": {"pos": [-118, 100, 0.0], "heading": -150}, "loadout": ["kr7s", "p9s", "lr50"],
               "grenades": 2, "nvg": False},
    "squad": [],
    "protect": [{"id": "brandt", "message": "Lio Brandt is dead - and the TEMPEST data died with him."}],
    "intel": [
        {"id": "m05_patrol_rota", "name": "Harbour patrol rota", "pos": [-80, 40, 0.62]},
        {"id": "m05_officer_id", "name": "Directorate officer's ID card", "pos": [-25, -19.5, 0.62]},
        {"id": "m05_manifest_page", "name": "Torn manifest page", "pos": [86, 28, 0.62]},
    ],
    "alarm": {
        "groups": ALARM_GROUPS,
        "actions": [
            act("loop_start", sound="alarm_loop", volume=0.3),
            radio("wren", "They know you're there, Elias. Move!", 0.5),
            act("spawn", delay=8.0, group="response", units=[
                unit(0, 70, 180, alert=[-40, 10]), unit(10, 72, 180, alert=[0, 20]),
                unit(-10, 74, 180, alert=[-60, 20], profile="veteran")]),
        ],
    },
    "intro": {
        "shots": [
            {"from": [-180, 140, 30], "to": [-140, 110, 22], "look_from": [-10, -40, 0], "look_to": [-10, -45, 5],
             "duration": 7.0},
            {"from": [-121, 104, 1.8], "to": [-119, 101, 1.7], "look_from": [-60, 20, 2], "look_to": [-70, -8, 4],
             "duration": 6.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "narrator", "text": "Port Calder. The ninth day of the war.", "seconds": 3.0},
            {"t": 3.6, "speaker": "wren", "text": "Brandt's message came in an hour ago. Then nothing.",
             "seconds": 3.2},
            {"t": 7.2, "speaker": "crane", "text": "What did he find?", "seconds": 2.0},
            {"t": 9.4, "speaker": "wren", "text": "One word on a shipping manifest. TEMPEST.", "seconds": 3.2},
        ],
    },
    "outro": {
        "shots": [
            {"from": [-380, -300, 12], "to": [-420, -330, 22], "look_from": [-10, -40, 4], "look_to": [-10, -40, 8],
             "duration": 12.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "wren", "text": "The manifests list one shipment: TEMPEST, routed through Lake Ostra.",
             "seconds": 3.6},
            {"t": 4.2, "speaker": "crane", "text": "Then that's where I'm going.", "seconds": 2.4},
            {"t": 7.0, "speaker": "wren", "text": "Elias... if Harrow's alive, who did we bury?", "seconds": 3.4},
        ],
    },
    "steps": steps,
}
with open(sys.argv[1] if len(sys.argv) > 1 else "data/missions/m05_dead_drop.json", "w", encoding="utf-8") as f:
    json.dump(mission, f, indent=1)
print(len(steps), "steps")
