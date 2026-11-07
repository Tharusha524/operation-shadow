"""Generates data/missions/m06_the_broker.json (Mission 6: Crane meets Mira Sol at Lake Ostra).

Run:  .venv\\Scripts\\python.exe tools\\make_m06.py
"""
import json
import sys


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


ROAD = [[232, 124, 0], [214, 104, 0], [201, 92, 0], [200, 60, 0], [200, 0, 0], [199, -38, 0], [188, -49, 0],
        [120, -50, 0], [0, -50, 0], [-130, -50, 0], [-250, -50, 0], [-372, -50, 0]]

steps = [
    # 1 ------------------------------------------------------------------ arrive
    {"id": "arrive",
     "objective": {"type": "reach", "text": "Walk up to Mira Sol's villa", "pos": [200, 130, 0], "radius": 6},
     "on_start": [
         act("squad_hold", positions={"mira": [200, 134, 180]}),
         act("spawn_friendly", group="mira_guards", units=[
             {"pos": [194, 83], "heading": 180, "name": "Villa Guard"},
             {"pos": [206, 83], "heading": 180, "name": "Villa Guard"},
             {"pos": [190, 133], "heading": 180, "name": "Villa Guard"},
             {"pos": [210, 133], "heading": 180, "name": "Villa Guard"},
             {"pos": [216, 118], "heading": 150, "name": "Villa Guard"},
             {"pos": [184, 118], "heading": 210, "name": "Villa Guard"}]),
         radio("wren", "Mira Sol. She has sold rifles to both sides of every war in ten years.", 1.0),
         radio("crane", "And now she wants to talk about TEMPEST.", 6.0),
         radio("wren", "Those are her guards. Don't shoot anyone who isn't shooting you.", 9.5),
     ],
     "on_complete": []},
    # 2 ------------------------------------------------------------------ greet Mira
    {"id": "meet",
     "objective": {"type": "interact", "text": "Talk to Mira Sol", "pos": [200, 134, 1.5], "radius": 3.0, "hold": 0.8,
                   "prompt": "Hold E to talk to Mira"},
     "on_start": [],
     "on_complete": []},
    # 3 ------------------------------------------------------------------ the conversation
    {"id": "talk",
     "objective": {"type": "survive", "text": "Hear Mira out", "seconds": 38},
     "on_start": [
         radio("mira", "You came a long way to ask questions.", 0.5),
         radio("crane", "You came a long way to avoid answering them.", 3.5),
         radio("mira", "I sold equipment. I didn't build a war.", 7.0),
         radio("crane", "But you helped someone who did.", 10.0),
         radio("mira", "The final components went to a facility near Saint-Aurel.", 13.5),
         radio("crane", "What is Tempest?", 18.0),
         radio("mira", "A targeting network. Satellites, drones, missiles. One connected system.", 20.5),
         radio("crane", "Who controls it?", 26.5),
         radio("mira", "Harrow. The rest is in my safe.", 29.0),
     ],
     "on_complete": [
         act("kill_group", group="mira_guards", count=1, sound="shot_sniper"),
         act("explosion", pos=[200, 88, 0.5]),
         act("loop_start", sound="alarm_loop", volume=0.25),
         radio("mira", "You brought them here!", 0.3),
         radio("crane", "They were already watching you!", 2.6),
         act("checkpoint", delay=1.0, pos=[198, 132, 0.0], heading=180),
     ]},
    # 4 ------------------------------------------------------------------ armoury
    {"id": "armoury",
     "objective": {"type": "interact", "text": "Grab grenades from Mira's crates", "pos": [186, 136, 1.0],
                   "radius": 2.8, "hold": 0.8, "prompt": "Hold E to take the grenades"},
     "on_start": [
         act("squad_hold", positions={"mira": [201, 141, 0]}),
         act("spawn", delay=1.0, group="assault", units=[
             unit(196, 76, 0, alert=[198, 112]), unit(204, 76, 0, alert=[202, 112]),
             unit(200, 72, 0, alert=[200, 104], profile="gunner")]),
         radio("harrow", "Hello, Elias. You really should have stayed buried.", 2.5),
     ],
     "on_complete": [
         act("give_grenades", kind="smoke", count=2),
         act("give_grenades", kind="flash", count=3),
         act("give_grenades", kind="frag", count=2),
         radio("mira", "Smoke and flashbangs. T to switch, G to throw. I need one minute at the safe!", 0.5, 5.0),
     ]},
    # 5 ------------------------------------------------------------------ defend the villa
    {"id": "defend",
     "objective": {"type": "survive", "text": "Hold the terrace while Mira opens the safe", "seconds": 60},
     "on_start": [
         act("barrage", delay=6.0, area=[172, 100, 228, 132], count=9, seconds=46, radius=5.0, damage=55.0),
         act("spawn", delay=8.0, group="assault", units=[
             unit(158, 92, 60, alert=[186, 122]), unit(164, 96, 60, alert=[190, 124], profile="recruit"),
             unit(160, 104, 80, alert=[188, 128])]),
         act("spawn", delay=22.0, group="assault", units=[
             unit(242, 92, -60, alert=[214, 122]), unit(236, 96, -60, alert=[212, 124], profile="veteran"),
             unit(244, 106, -80, alert=[212, 130], profile="recruit")]),
         act("spawn", delay=40.0, group="assault", units=[
             unit(192, 78, 0, alert=[194, 124]), unit(200, 74, 0, alert=[200, 122], profile="veteran"),
             unit(208, 78, 0, alert=[206, 124]), unit(214, 82, 0, alert=[212, 126], profile="gunner")]),
         radio("mira", "Mortar! They've got a mortar somewhere up on the east slope!", 12.0),
         radio("harrow", "She'll sell you out too. She always does.", 30.0),
         radio("mira", "Don't listen to him. Twenty more seconds!", 42.0),
     ],
     "on_complete": [
         radio("mira", "Safe's open! But that mortar will flatten us before we reach the car.", 0.5),
         act("refill_ammo", delay=0.5),
         act("checkpoint", delay=1.0, pos=[205, 132, 0.0], heading=-60),
     ]},
    # 6 ------------------------------------------------------------------ the mortar
    {"id": "mortar",
     "objective": {"type": "eliminate", "group": "mortar", "text": "Silence the mortar on the east slope",
                   "pos": [320, 230, 1.5]},
     "on_start": [
         act("spawn", group="mortar", units=[
             unit(320, 228, 200, hold=[320, 228, 200]), unit(324, 233, 200, hold=[324, 233, 200], profile="recruit"),
             unit(310, 220, 230, hold=[310, 220, 230], profile="gunner"),
             unit(330, 220, 180, hold=[330, 220, 180]), unit(300, 208, 230, hold=[300, 208, 230], profile="veteran")]),
         act("barrage", delay=4.0, area=[172, 100, 245, 150], count=14, seconds=90, radius=5.0, damage=55.0),
         radio("mira", "Garden gate in the east wall. Go - I'll hold the house!", 1.0),
     ],
     "on_complete": [
         act("cancel_barrage"),
         radio("crane", "Mortar's down.", 0.5),
         radio("mira", "My jeep's by the garage. There's a ferry at the far end of the lake road.", 2.5),
         act("checkpoint", delay=1.0, pos=[318, 226, 0.0], heading=130),
     ]},
    # 7 ------------------------------------------------------------------ to the jeep
    {"id": "to_jeep",
     "objective": {"type": "reach", "text": "Get to Mira's jeep by the garage", "pos": [230, 128, 0], "radius": 3.5},
     "on_start": [
         act("spawn_vehicle", kind="player_jeep", id="getaway_parked", pos=[232, 128, 0.0], heading=180),
         act("squad_hold", positions={"mira": [235, 128, 180]}),
         act("spawn", delay=3.0, group="assault", units=[
             unit(246, 100, -60, alert=[232, 128]), unit(240, 96, -40, alert=[228, 126], profile="recruit"),
             unit(170, 150, 90, alert=[226, 130])]),
     ],
     "on_complete": [
         act("checkpoint", pos=[229, 128, 0.0], heading=180),
     ]},
    # 8 ------------------------------------------------------------------ the drive
    {"id": "drive",
     "objective": {"type": "reach", "text": "Drive to the ferry - smash through any roadblock", "pos": [-372, -54, 0],
                   "radius": 10},
     "on_start": [
         act("remove_vehicle", id="getaway_parked"),
         act("spawn_vehicle", kind="player_jeep", id="getaway", pos=[232, 128, 0.0], heading=180),
         act("start_ride", vehicle="getaway", drive=True, seat=[-0.42, -0.15, 0.05], squad={"mira": [0.42, -0.1, -0.2]},
             breakable=["roadblock_a", "roadblock_b", "roadblock_c"]),
         act("spawn_vehicle", delay=7.0, kind="enemy_jeep", id="ej1", path=ROAD, chase_offset=-22.0, health=260),
         act("spawn", delay=7.2, group="chasers", units=[
             unit(232, 124, 180, ride={"vehicle": "ej1", "seat": [0.0, -1.0, 0.55]}, profile="gunner")]),
         act("spawn_vehicle", delay=14.0, kind="enemy_jeep", id="ej2", path=ROAD, chase_offset=-34.0, health=260),
         act("spawn", delay=14.2, group="chasers", units=[
             unit(232, 124, 180, ride={"vehicle": "ej2", "seat": [0.0, -1.0, 0.55]})]),
         act("spawn", group="road", units=[
             unit(-60, -39, 180, hold=[-60, -39, 180]), unit(-56, -39, 180, hold=[-56, -39, 180], profile="recruit"),
             unit(-150, -39, 180, hold=[-150, -39, 180]), unit(-146, -39, 180, hold=[-146, -39, 180], profile="gunner"),
             unit(-266, -46, 90, hold=[-266, -46, 90]), unit(-266, -53, 90, hold=[-266, -53, 90], profile="gunner"),
             unit(-268, -49, 90, hold=[-268, -49, 90], profile="veteran")]),
         act("notice", delay=1.0, text="[W/S] DRIVE   [A/D] STEER   [SPACE] BRAKE"),
         radio("mira", "Drive! Out the gate and left at the lake - I'll shoot, you steer!", 1.0),
         radio("mira", "Jeep behind us!", 12.0),
         radio("crane", "You said you were finished with Harrow.", 18.0),
         radio("mira", "I was.", 21.0),
         radio("crane", "You worked with him before?", 23.0),
         radio("mira", "I moved equipment during Glass Harbour. I didn't know what he was planning.", 25.5),
         radio("wren", "Elias, there's a checkpoint on the lake road. Concrete barriers. Don't slow down.", 32.0, 4.5),
     ],
     "on_complete": [
         act("end_ride", pos=[-372, -56, 0.0], heading=170, squad={"mira": [-369, -56]}),
         act("squad_follow", member="mira"),
         act("checkpoint", pos=[-372, -56, 0.0], heading=170),
     ]},
    # 9 ------------------------------------------------------------------ ferry
    {"id": "ferry",
     "objective": {"type": "reach", "text": "Run down the pier to the ferry", "pos": [-380, -92, 0.25], "radius": 3.5},
     "on_start": [
         radio("mira", "That's the last boat tonight. Move!", 0.5),
     ],
     "on_complete": [
         act("complete_mission", delay=1.0),
     ]},
]

mission = {
    "id": "m06_the_broker",
    "map": "lake_ostra",
    "date": "Day 12 - 16:30",
    "briefing": [
        "The Port Calder manifests point to Lake Ostra, and to Mira Sol - an arms broker who has armed both sides "
        "of every war in ten years.",
        "Sol has offered to meet Crane at her villa above the lake. She says she sold something to the people "
        "behind TEMPEST, and that she wants out.",
        "Crane doesn't trust her. But he trusts Desmond Harrow's silence even less.",
    ],
    "story_objective": "Find out what Mira Sol knows about TEMPEST, and keep her alive.",
    "gameplay_objective": "Meet Mira, survive the ambush with smoke and flashbangs (T switches, G throws), take out "
                          "the mortar, then drive the jeep down the lake road and smash through the roadblock.",
    "par_time": 1020,
    "player": {"spawn": {"pos": [200, 70, 0.0], "heading": 0}, "loadout": ["kr7s", "p9s"], "grenades": 1},
    "squad": [{"id": "mira", "pos": [200, 134], "heading": 180}],
    "intel": [
        {"id": "m06_sales_ledger", "name": "Mira's sales ledger", "pos": [212, 134, 0.62]},
        {"id": "m06_harrow_orders", "name": "Harrow's written orders", "pos": [326, 232, 0.62]},
    ],
    "intro": {
        "shots": [
            {"from": [120, -160, 40], "to": [160, -90, 30], "look_from": [200, 150, 6], "look_to": [200, 150, 4],
             "duration": 7.0},
            {"from": [206, 58, 2.2], "to": [202, 68, 1.8], "look_from": [200, 150, 4], "look_to": [200, 150, 3],
             "duration": 6.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "narrator", "text": "Lake Ostra. Two weeks into the war, you could still buy "
                                                      "anything here.", "seconds": 3.6},
            {"t": 4.4, "speaker": "wren", "text": "She invited you. That's what worries me.", "seconds": 3.0},
            {"t": 8.0, "speaker": "crane", "text": "It should. Stay on the line.", "seconds": 2.6},
        ],
    },
    "outro": {
        "shots": [
            {"from": [-380, -130, 9], "to": [-330, -190, 14], "look_from": [-380, -60, 3], "look_to": [200, 150, 10],
             "duration": 12.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "mira", "text": "The parts went to a data centre outside Saint-Aurel.", "seconds": 3.4},
            {"t": 4.0, "speaker": "crane", "text": "A data centre. For a weapon.", "seconds": 2.6},
            {"t": 6.8, "speaker": "mira", "text": "TEMPEST doesn't blow anything up, Elias. It tells everything else "
                                                  "what to hit.", "seconds": 4.2},
        ],
    },
    "steps": steps,
}
with open(sys.argv[1] if len(sys.argv) > 1 else "data/missions/m06_the_broker.json", "w", encoding="utf-8") as f:
    json.dump(mission, f, indent=1)
print(len(steps), "steps")
