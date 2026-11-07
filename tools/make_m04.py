"""Generates data/missions/m04_no_way_back.json."""
import json
import sys

W = -1.3          # water level on the Tamsin River map


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


BOAT_PATH = [[-380, -4, W], [-330, 3, W], [-270, -5, W], [-210, 6, W], [-150, -4, W], [-90, 5, W], [-30, -5, W],
             [30, 4, W], [80, 9, W], [100, 12, W], [108, 13, W]]
SQUAD_SEATS = {"marek": [-0.55, -0.7, -0.1], "voss": [0.0, 1.8, -0.1], "doran": [0.0, -2.5, -0.1]}

compound = [
    unit(150, 60, 0, patrol=[[150, 60], [150, 90], [175, 95], [175, 62]]),
    unit(210, 58, 90, patrol=[[210, 58], [240, 50], [252, 82], [215, 86]]),
    unit(228, 104, 180, profile="regular"),
    unit(234, 90, 270, profile="recruit"),
    unit(160, 100, 270, patrol=[[160, 100], [200, 106], [232, 118]]),
    unit(178, 63, 270, profile="recruit"),
    unit(244, 73, 270, profile="regular"),
]
bridge_guard = [
    unit(191, 40, 180, profile="regular"),
    unit(209, 40, 180, profile="regular"),
    unit(200, 28, 180, patrol=[[200, 28], [200, -26]], profile="recruit"),
]
TANKS = [("tank1", -300, 14), ("tank2", -316, 0), ("tank3", -332, -14)]

steps = [
    # 1 ------------------------------------------------------------------ boat insertion
    {"id": "insertion",
     "objective": {"type": "ride", "text": "Ride the river to the drop point - shoot from the boat"},
     "on_start": [
         act("spawn_vehicle", kind="player_boat", id="insertion", path=BOAT_PATH, speed=6.0),
         act("start_ride", vehicle="insertion", seat=[0.6, -0.6, -0.1], squad=SQUAD_SEATS),
         act("spawn_vehicle", kind="patrol_boat", id="pb1", health=260, speed=7.0, loop=True,
             path=[[-170, -12, W], [-210, -14, W], [-250, -8, W], [-250, 8, W], [-210, 12, W], [-170, 8, W]]),
         act("spawn_vehicle", kind="patrol_boat", id="pb2", health=260, speed=7.0, loop=True,
             path=[[30, -10, W], [-10, -13, W], [-50, -8, W], [-50, 8, W], [-10, 12, W], [30, 8, W]]),
         act("spawn", group="bank", units=[
             unit(-222, 31, 180, hold=[-222, 31, 180]), unit(-217, 31, 180, hold=[-217, 31, 180], profile="gunner"),
             unit(-112, -30, 0, hold=[-112, -30, 0]), unit(-106, -31, 0, hold=[-106, -31, 0], profile="recruit"),
             unit(-27, 31, 180, hold=[-27, 31, 180]), unit(-22, 32, 180, hold=[-22, 32, 180], profile="recruit")]),
         act("loop_start", sound="wind_loop", volume=0.25),
         radio("marek", "Engines low. Nobody fires unless they find us first.", 1.0),
         radio("doran", "Bridge is eight hundred metres up-river. I've got enough charge to drop it three times over.", 6.0),
         act("notice", delay=10.0, text="PRESS [N] FOR NIGHT VISION"),
         radio("voss", "Patrol boat, dead ahead. They've seen us - light it up!", 22.0),
         radio("marek", "MG on the north bank! Keep your heads down!", 30.0),
         radio("voss", "Searchlight on the south side. Stay out of the beam.", 50.0),
         radio("doran", "Second boat by the old quay - hit the gunner!", 64.0),
     ],
     "on_complete": [
         act("end_ride", pos=[110, 29, 0.0], heading=-80,
             squad={"marek": [107, 30], "voss": [113, 31], "doran": [110, 33]}),
         act("squad_hold", positions={"marek": [108, 34, -90], "voss": [113, 36, -80], "doran": [104, 31, -90]}),
         act("checkpoint", pos=[110, 29, 0.0], heading=-80),
         radio("marek", "Everybody out. Quiet now.", 0.5),
     ]},
    # 2 ------------------------------------------------------------------ prepare the drone
    {"id": "launch_drone",
     "objective": {"type": "interact", "text": "Launch the recon drone", "pos": [116, 36, 0.9], "radius": 2.6,
                   "hold": 1.0, "prompt": "Hold E to launch the drone"},
     "on_start": [
         radio("doran", "Drone case is on the crates. Put it up and mark every guard you can see.", 1.0),
     ],
     "on_complete": []},
    # 3 ------------------------------------------------------------------ drone recon
    {"id": "recon",
     "objective": {"type": "tag", "count": 5, "text": "Tag enemies with the drone"},
     "on_start": [
         act("spawn", group="compound", units=compound),
         act("spawn", group="bridge_guard", units=bridge_guard),
         act("drone_start", pos=[116, 36, 26], heading=-70, max_range=170),
         radio("doran", "Drone's up. Thermal camera on. Fly it over the compound east of here.", 0.5),
         radio("marek", "Guards on the bridge, more around the barracks. Tag them all.", 9.0),
     ],
     "on_complete": [
         act("drone_end", delay=1.0),
         radio("doran", "Good tags. They're on your display now.", 1.2),
         act("checkpoint", delay=1.5, pos=[116, 33, 0.0], heading=-80),
     ]},
    # 4 ------------------------------------------------------------------ stealth: AA gun
    {"id": "aa_gun",
     "objective": {"type": "interact", "text": "Sneak in and plant a charge on the AA gun", "pos": [228, 96, 1.6],
                   "radius": 4.2, "hold": 2.5, "prompt": "Hold E to plant the charge", "charge": True},
     "on_start": [
         act("alarm_arm"),
         radio("marek", "That AA gun keeps our ride away. Halden - go in alone, quietly. Use your knife. [V]", 1.0, 5.0),
         radio("voss", "I'll watch you from the trees. Stay in the dark and stay crouched.", 7.0),
     ],
     "on_complete": [
         act("sound", sound="c4_plant"),
         radio("doran", "Charge on the AA gun. I'll blow it when the helicopter comes in.", 0.5),
     ]},
    # 5 ------------------------------------------------------------------ stealth: bridge charges
    {"id": "bridge_charges",
     "objective": {"type": "interact_multi", "text": "Plant charges on the bridge",
                   "points": [[197.5, 16, 0.75], [202.5, 0, 0.75], [197.5, -16, 0.75]], "radius": 2.6, "hold": 2.5,
                   "prompt": "Hold E to plant the charge", "charge": True},
     "on_start": [
         radio("doran", "Three charges, one on each span. North, middle, south.", 1.0),
         radio("voss", "Searchlights sweep the north end. Move between the beams.", 6.0),
     ],
     "on_complete": [
         act("alarm_disarm"),
         radio("doran", "All three set. Wire's running back to the detonator by the bunker.", 0.5),
         act("checkpoint", delay=1.0, pos=[186, 47, 0.0], heading=180),
     ]},
    # 6 ------------------------------------------------------------------ kamikaze drones
    {"id": "drones",
     "objective": {"type": "destroy", "text": "Shoot down the attack drones",
                   "targets": ["kd1", "kd2", "kd3", "kd4", "kd5"], "marker": False},
     "on_start": [
         radio("voss", "Drones! Coming in from the east - shoot them before they reach you!", 0.5),
         act("loop_start", sound="alarm_loop", volume=0.3),
         act("squad_hold", positions={"marek": [189, 49, 180], "voss": [178, 50, 160], "doran": [184, 47, 180]}),
         act("spawn_vehicle", delay=2.0, kind="kamikaze_drone", id="kd1", pos=[300, 60, 22]),
         act("spawn_vehicle", delay=4.0, kind="kamikaze_drone", id="kd2", pos=[300, 90, 26]),
         act("spawn_vehicle", delay=7.0, kind="kamikaze_drone", id="kd3", pos=[290, 30, 20]),
         act("spawn_vehicle", delay=10.0, kind="kamikaze_drone", id="kd4", pos=[300, 120, 28]),
         act("spawn_vehicle", delay=12.0, kind="kamikaze_drone", id="kd5", pos=[280, 140, 24]),
     ],
     "on_complete": [
         radio("marek", "Drones down. That won't be all they've got.", 0.5),
     ]},
    # 7 ------------------------------------------------------------------ launcher
    {"id": "launcher",
     "objective": {"type": "interact", "text": "Grab the RL-3 launcher from the weapons crate", "pos": [196, 52, 1.0],
                   "radius": 2.6, "hold": 1.0, "prompt": "Hold E to take the launcher"},
     "on_start": [
         radio("doran", "Gunship inbound! There's a launcher in the Varn weapons crate by the road.", 1.0),
     ],
     "on_complete": [
         act("give_weapon", id="rl3", ammo=4),
         radio("marek", "Switch to the launcher. Lead the target - and let it come to you.", 0.5),
         act("checkpoint", delay=1.0, pos=[194, 54, 0.0], heading=90),
     ]},
    # 8 ------------------------------------------------------------------ attack helicopter
    {"id": "gunship",
     "objective": {"type": "destroy", "text": "Shoot down the attack helicopter", "targets": ["gunship"]},
     "on_start": [
         act("spawn_vehicle", kind="attack_helicopter", id="gunship", speed=30.0, health=900,
             path=[[480, 220, 45], [340, 130, 32], [250, 80, 24]], orbit_radius=48, altitude=20),
         act("refill_ammo"),
         radio("voss", "Gunship, east! Get under cover!", 2.0),
         act("flare", delay=4.0, pos=[205, 70, 45], seconds=30.0),
         act("spawn", delay=6.0, group="alarm_wave", units=[
             unit(200, 150, 180, alert=[200, 60]), unit(206, 155, 180, alert=[200, 60], profile="recruit"),
             unit(194, 158, 180, alert=[196, 56])]),
     ],
     "on_complete": [
         radio("marek", "Splash one! Nice shot, Halden!", 1.5),
         act("checkpoint", delay=2.5, pos=[186, 47, 0.0], heading=180),
     ]},
    # 9 ------------------------------------------------------------------ hold until the tanks are on the bridge
    {"id": "hold",
     "objective": {"type": "vehicles_arrive", "text": "Hold the north bank - let the tanks onto the bridge",
                   "targets": [t[0] for t in TANKS]},
     "on_start": [
         *[act("spawn_vehicle", kind="tank", id=tid, speed=5.0,
               path=[[200, y0, 0], [200, -40, 0], [200, -30, 0.25], [200, end, 0.25]]) for tid, y0, end in TANKS],
         radio("marek", "Armour on the south road! Wait until they're all on the bridge!", 1.0),
         radio("doran", "If we blow it early they just go round. Hold!", 6.0),
         act("spawn", delay=8.0, group="crossing", units=[
             unit(195, -60, 0, alert=[196, 44]), unit(205, -62, 0, alert=[204, 44]),
             unit(200, -66, 0, alert=[200, 46], profile="recruit")]),
         act("spawn", delay=28.0, group="crossing", units=[
             unit(196, -60, 0, alert=[190, 44]), unit(204, -60, 0, alert=[208, 46], profile="gunner"),
             unit(200, -64, 0, alert=[200, 46])]),
         act("spawn", delay=46.0, group="crossing", units=[
             unit(197, -60, 0, alert=[186, 46], profile="veteran"), unit(203, -62, 0, alert=[212, 46])]),
         act("flare", delay=20.0, pos=[200, -10, 45], seconds=30.0),
         radio("voss", "Infantry on the bridge!", 10.0),
         radio("marek", "Lead tank is almost across - keep them busy!", 50.0),
     ],
     "on_complete": [
         radio("doran", "They're all on it! Halden - the detonator! NOW!", 0.3),
     ]},
    # 10 ----------------------------------------------------------------- blow the bridge
    {"id": "detonate",
     "objective": {"type": "interact", "text": "Blow the bridge", "pos": [182.5, 45.5, 0.75], "radius": 2.8,
                   "hold": 0.8, "prompt": "Hold E to detonate"},
     "on_start": [],
     "on_complete": [
         act("collapse_bridge", spans=["span_n", "span_m", "span_s"],
             show=["ruin_n", "ruin_m", "ruin_s", "bridge_end_wall"],
             blasts=[[197.5, 16, 0.5], [202.5, 0, 0.5], [197.5, -16, 0.5], [200, 20, -1.0], [200, 0, -1.0],
                     [200, -20, -1.0]],
             vehicles=[t[0] for t in TANKS]),
         radio("marek", "Bridge is down! The column's in the river!", 2.5),
         radio("doran", "Hah! Three tanks, one button.", 5.5),
         act("checkpoint", delay=7.0, pos=[186, 50, 0.0], heading=0),
     ]},
    # 11 ----------------------------------------------------------------- escape to the LZ
    {"id": "escape",
     "objective": {"type": "reach", "text": "Fight your way to the landing zone", "pos": [214, 190, 0], "radius": 8},
     "on_start": [
         act("squad_follow", member="all"),
         radio("marek", "Bastion, this is Marek. Bridge is gone. Request pick-up at the north LZ.", 2.0),
         radio("bastion", "Copy, Marek. Bird is two minutes out. Keep the LZ clear.", 7.5),
         act("spawn", delay=3.0, group="pursuit", units=[
             unit(280, 150, 270, alert=[214, 170]), unit(284, 160, 270, alert=[214, 175], profile="gunner"),
             unit(276, 175, 270, alert=[214, 180]), unit(140, 170, 90, alert=[200, 170]),
             unit(136, 180, 90, alert=[205, 185], profile="veteran")]),
         act("spawn", delay=25.0, group="pursuit", units=[
             unit(214, 214, 180, alert=[214, 190]), unit(222, 212, 180, alert=[214, 190], profile="recruit"),
             unit(206, 212, 180, alert=[214, 190])]),
         act("smoke", delay=10.0, pos=[214, 196, 0.2], seconds=120.0),
     ],
     "on_complete": [
         radio("marek", "LZ's ours. Hold here!", 0.5),
     ]},
    # 12 ----------------------------------------------------------------- extraction
    {"id": "extraction",
     "objective": {"type": "vehicles_arrive", "targets": ["evac"], "text": "Hold the LZ until the helicopter lands"},
     "on_start": [
         act("spawn_vehicle", kind="transport_helicopter", id="evac", speed=26.0,
             path=[[-60, 420, 60], [100, 290, 38], [190, 220, 16], [214, 197, 0.4]]),
         act("destroy_prop", delay=4.0, id="aa_gun", explode=True),
         radio("doran", "Blowing the AA gun - the sky is clear!", 3.0),
         act("spawn", delay=2.0, group="lz_attack", units=[
             unit(250, 220, 220, alert=[214, 192]), unit(255, 205, 250, alert=[214, 192]),
             unit(178, 222, 140, alert=[214, 192], profile="gunner"), unit(170, 205, 110, alert=[214, 192])]),
         radio("bastion", "Marek, I see your smoke. Coming in hot.", 14.0),
     ],
     "on_complete": [
         radio("marek", "Clear! Get on the bird!", 0.5),
     ]},
    # 13 ----------------------------------------------------------------- board
    {"id": "board",
     "objective": {"type": "reach", "text": "Board the helicopter", "pos": [215.5, 197, 0], "radius": 3.0},
     "on_start": [],
     "on_complete": [
         act("start_ride", vehicle="evac", seat=[1.0, 0.4, 0.45],
             squad={"marek": [-0.7, 0.6, 0.45], "voss": [-0.7, -0.6, 0.45], "doran": [0.6, -0.8, 0.45]}),
         act("vehicle_command", delay=1.5, id="evac", path=[[214, 197, 0.4], [214, 205, 12], [150, 300, 40],
                                                            [0, 420, 70]], speed=18.0),
         radio("bastion", "Everybody aboard. Lifting off.", 1.0),
         act("complete_mission", delay=9.0),
     ]},
]

mission = {
    "id": "m04_no_way_back",
    "map": "tamsin_river",
    "date": "Day 5 - 02:10",
    "briefing": [
        "Kareth forces are falling back across the Tamsin River. One road bridge is still standing - and a Varn "
        "armoured column will reach it before dawn.",
        "Sgt. Marek's squad and the combat engineer Pvt. Rafe Doran will go up-river by boat under cover of "
        "darkness, slip into the guard post at the north end and wire the bridge to blow.",
        "Wait for the tanks to roll onto the bridge, drop it into the river, then fight your way to the "
        "landing zone for extraction.",
    ],
    "story_objective": "Destroy the Tamsin bridge with the Varn armour on it.",
    "gameplay_objective": "Boat insertion, drone recon, stealth (V = silent takedown, N = night vision), plant "
                          "charges, shoot down drones and a gunship, hold for the tanks, detonate, extract. "
                          "Optional: find 3 intel documents and stay undetected.",
    "par_time": 1260,
    "night": {"visibility": 0.5, "lit": [[195, 11, 8], [217, 11, 8], [-120, 1, 9], [-11, 2, 9]]},
    "player": {"spawn": {"pos": [110, 29, 0.0], "heading": -80}, "loadout": ["kr7", "p12"], "grenades": 3,
               "nvg": True},
    "squad": [
        {"id": "marek", "pos": [-380, 40], "heading": 90},
        {"id": "voss", "pos": [-378, 42], "heading": 90},
        {"id": "doran", "pos": [-376, 40], "heading": 90},
    ],
    "intel": [
        {"id": "m04_patrol_schedule", "name": "Varn patrol schedule", "pos": [104, 34, 0.62]},
        {"id": "m04_bridge_survey", "name": "Bridge demolition survey", "pos": [226, 52.5, 0.62]},
        {"id": "m04_flight_log", "name": "Gunship flight log", "pos": [236, 99, 0.62]},
    ],
    "alarm": {
        "groups": ["compound", "bridge_guard"],
        "actions": [
            act("loop_start", sound="alarm_loop", volume=0.35),
            radio("marek", "They've spotted you! So much for quiet - fight!", 0.5),
            act("flare", delay=2.0, pos=[205, 70, 45], seconds=30.0),
            act("spawn", delay=8.0, group="alarm_wave", units=[
                unit(200, 150, 180, alert=[200, 70]), unit(206, 152, 180, alert=[210, 70]),
                unit(194, 156, 180, alert=[190, 70], profile="recruit")]),
            act("squad_hold", positions={"marek": [150, 46, -90], "voss": [140, 44, -80], "doran": [146, 40, -90]}),
        ],
    },
    "intro": {
        "shots": [
            {"from": [-300, -60, 26], "to": [-200, -40, 18], "look_from": [-150, 0, 0], "look_to": [-60, 0, 0],
             "duration": 7.0},
            {"from": [150, -60, 14], "to": [160, -40, 10], "look_from": [200, 0, 0], "look_to": [200, 10, 0],
             "duration": 7.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "narrator", "text": "Day Five. The Tamsin River.", "seconds": 2.6},
            {"t": 3.2, "speaker": "narrator", "text": "Everything we had left was falling back across it.",
             "seconds": 3.4},
            {"t": 7.2, "speaker": "marek", "text": "One bridge still standing. By sunrise there'll be Varn tanks on it.",
             "seconds": 3.6},
            {"t": 11.0, "speaker": "doran", "text": "Not if I get there first.", "seconds": 2.4},
        ],
    },
    "outro": {
        "shots": [
            {"from": [230, 150, 40], "to": [200, 120, 60], "look_from": [200, 0, -2], "look_to": [200, 0, -2],
             "duration": 12.0},
        ],
        "lines": [
            {"t": 0.4, "speaker": "narrator", "text": "We dropped the Tamsin bridge with three tanks on it.",
             "seconds": 3.4},
            {"t": 4.0, "speaker": "narrator", "text": "It bought the army a week.", "seconds": 2.4},
            {"t": 6.6, "speaker": "marek", "text": "Good work, all of you. Get some sleep.", "seconds": 2.8},
            {"t": 9.6, "speaker": "narrator", "text": "None of us did.", "seconds": 2.2},
        ],
    },
    "steps": steps,
}
with open(sys.argv[1] if len(sys.argv) > 1 else "data/missions/m04_no_way_back.json", "w", encoding="utf-8") as f:
    json.dump(mission, f, indent=1)
print(len(steps), "steps")
