"""Mission 1 "First Light": calm patrol -> missile strike -> armoured assault -> the outpost falls.

    .venv\\Scripts\\python.exe tools\\make_m01.py

Rewrites data/missions/m01_first_light.json (keeping the patrol, relay and codebook objectives)
and adds destroyable props (ids + hidden burnt wrecks and craters) to data/maps/border_outpost.json.
Safe to run again: everything it adds is replaced, not duplicated.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "data" / "missions" / "m01_first_light.json"
MAP = ROOT / "data" / "maps" / "border_outpost.json"
ARRIVE = 2.5              # seconds a missile needs from launch to impact (see MissionContext.missile)

# ------------------------------------------------------------------------------------------- map
INTACT = {                # id -> (type, pos) of existing props that the strike destroys
    "tower_ne": ("watchtower", [62, 60]),
    "jeep_a": ("jeep", [13, 16]),
    "jeep_b": ("jeep", [18, 16]),
    "truck_a": ("truck", [27, 16]),
    "truck_b": ("truck", [2.2, 40]),
}
WRECKS = [                # hidden until the strike
    {"type": "jeep", "pos": [13.4, 16.6], "heading": 24, "params": {"burnt": True}, "id": "jeep_a_wreck"},
    {"type": "jeep", "pos": [18.8, 15.2], "heading": -31, "params": {"burnt": True}, "id": "jeep_b_wreck"},
    {"type": "truck", "pos": [27, 16], "heading": 12, "params": {"burnt": True, "cargo": False}, "id": "truck_a_wreck"},
    {"type": "truck", "pos": [2.6, 40.5], "heading": 20, "params": {"burnt": True, "covered": False},
     "id": "truck_b_wreck"},
]
CRATERS = {"crater_ne": [60, 58], "crater_bunker": [12, -1], "crater_ruins": [-17, 49], "crater_bunker2": [-13, 10],
           "crater_west": [-31, 2], "crater_north": [20, 50], "crater_breach": [-2, 66],
           "crater_barracks": [-24, -8], "crater_hq": [33, -22]}


def build_map():
    data = json.loads(MAP.read_text(encoding="utf-8"))
    props = []
    for p in data["props"]:
        if str(p.get("id", "")).endswith("_wreck") or str(p.get("id", "")).startswith("crater_"):
            continue                                            # re-added below
        for pid, (ptype, pos) in INTACT.items():
            if p["type"] == ptype and p["pos"][:2] == pos:
                p["id"] = pid
        props.append(p)
    for w in WRECKS:
        props.append(dict(w, hidden=True))
    for pid, pos in CRATERS.items():
        props.append({"type": "crater", "pos": pos, "params": {"radius": 3.2}, "id": pid, "hidden": True})
    data["props"] = props
    missing = set(INTACT) - {p.get("id") for p in props}
    if missing:
        raise SystemExit(f"props not found in the map: {missing}")
    MAP.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------- helpers
def radio(speaker, text, delay, seconds=None):
    a = {"action": "radio", "speaker": speaker, "text": text, "delay": delay}
    a["seconds"] = seconds or round(1.0 + len(text.split()) * 0.33, 1)
    return a


def strike(launch, target, radius=12.0, damage=400.0, scale=6.0, fire=1.8, crater=None, hide=(), show=()):
    """Missile launched at `launch` s; the wreckage, crater and fire appear when it lands."""
    t = launch + ARRIVE
    out = [{"action": "missile", "target": target, "radius": radius, "damage": damage, "scale": scale,
            "delay": launch}]
    for pid in hide:
        out.append({"action": "destroy_prop", "id": pid, "explode": False, "delay": t})
    for pid in show + ((crater,) if crater else ()):
        out.append({"action": "show_prop", "id": pid, "delay": t})
    if fire:
        out.append({"action": "fire", "pos": [target[0], target[1], 0.0], "size": fire, "delay": t + 0.1})
    return out


def unit(pos, profile="regular", alert=None, hold=None, heading=180):
    u = {"pos": pos, "profile": profile, "heading": heading}
    if alert:
        u["alert"] = alert
    if hold:
        u["hold"] = hold
    return u


GARRISON = [  # Kareth riflemen around the outpost; many of them die in the strike
    ([8, -2], 20), ([12, -6], -10), ([-10, 17], 0), ([-13, 12], 30), ([-20, 50], 0), ([-15, 53], -20),
    ([21, 53], 10), ([30, 40], 0), ([-28, 8], 20), ([38, 19], -30), ([-40, -18], 0), ([4, 44], 0),
    ([16, 4], 0), ([22, 8], 10), ([4, 10], -10), ([-4, 24], 0), ([10, 30], 20), ([26, 26], 0),
]


# ------------------------------------------------------------------------------------------- steps
def bombardment_step():
    s = [{"action": "loop_start", "sound": "alarm_loop", "volume": 0.45, "delay": 0.4},
         radio("bastion", "Ridgeback, Bastion! Missiles inbound on your position - take cover, take cover!", 0.2),
         {"action": "notice", "text": "MISSILE STRIKE", "delay": 2.0},
         radio("marek", "INCOMING! Get down! Get the fuck down!", 3.0),
         radio("voss", "Shit, the north tower's gone! Pavel was up there!", 6.5),
         radio("kell", "Where the hell is it coming from?! I can't see a damn thing!", 10.5),
         radio("marek", "Missiles! They're hitting every fucking thing at once! Stay down!", 14.5),
         radio("voss", "Bunker two is gone... Jesus, they're all gone.", 19.0),
         {"action": "barrage", "area": [-60, -8, 60, 68], "count": 34, "seconds": 26, "radius": 7,
          "damage": 160, "scale": 3.2, "target_group": "garrison", "aimed": 0.45, "delay": 4.0}]
    s += strike(1.0, [62, 60, 4], radius=12, crater="crater_ne", hide=("tower_ne",), fire=2.6)
    s += strike(2.2, [10, -3], crater="crater_bunker")
    s += strike(3.4, [15.5, 16], hide=("jeep_a", "jeep_b"), show=("jeep_a_wreck", "jeep_b_wreck"), fire=2.2)
    s += strike(4.6, [-17, 51], crater="crater_ruins")
    s += strike(5.8, [27, 17], hide=("truck_a",), show=("truck_a_wreck",), fire=2.6)
    s += strike(7.0, [-12, 13], crater="crater_bunker2")
    s += strike(8.4, [3, 41], hide=("truck_b",), show=("truck_b_wreck",), fire=2.0)
    s += strike(9.8, [34, 30], fire=3.0)
    s += strike(11.2, [-30, 4], crater="crater_west")
    s += strike(12.6, [20, 51], crater="crater_north")
    s += strike(15.0, [-40, -17], radius=9, fire=1.5)
    return {"id": "bombardment",
            "objective": {"type": "survive", "seconds": 26, "text": "Survive the missile strike"},
            "on_start": s,
            "on_complete": [radio("voss", "Oh shit. Armour! Tanks on the north ridge!", 0.2),
                            radio("marek", "Here they come! Everyone up! Move your asses, get to the sandbags!", 2.4),
                            {"action": "checkpoint", "pos": [24, -40, 0], "heading": 0, "delay": 1.0}]}


TANKS = [
    {"action": "spawn_vehicle", "kind": "tank", "id": "tank1", "path": [[-30, 260, 0], [-24, 108, 0]],
     "speed": 6.0, "loop": False, "health": 3000},
    {"action": "spawn_vehicle", "kind": "tank", "id": "tank2", "path": [[30, 270, 0], [24, 112, 0]],
     "speed": 6.0, "loop": False, "health": 3000, "delay": 4.0},
    {"action": "spawn_vehicle", "kind": "tank", "id": "tank3", "path": [[2, 320, 0], [6, 128, 0]],
     "speed": 6.0, "loop": False, "health": 3000, "delay": 12.0},
]

def tanks_at(*spots):
    """Re-create the tanks at their current stage positions after a retry from a checkpoint."""
    return [{"action": "spawn_vehicle", "kind": "tank", "id": f"tank{i + 1}", "pos": [x, y, 0], "heading": 180,
             "health": 3000, "if_missing": True} for i, (x, y) in enumerate(spots)]


def wave(group, delay, units):
    return {"action": "spawn", "group": group, "delay": delay, "units": units}


def squad_hold(delay, **pos):
    return {"action": "squad_hold", "delay": delay, "positions": pos}


def tank_fire(tid, delay, target, debris="concrete"):
    """Scripted tank shot at a building / bunker, with chunks blasted off it."""
    return [{"action": "tank_fire", "id": tid, "target": target, "delay": delay},
            {"action": "debris", "pos": target, "count": 16, "kind": debris, "size": 0.45, "delay": delay + 0.5}]


def line_wave(y, xs, alert_y, profile="regular"):
    return [unit([x, y + (i % 2) * 4], "veteran" if (i % 4 == 3) else profile, [x * 0.6, alert_y])
            for i, x in enumerate(xs)]


# Stage 1: sappers blow the fence; hold the north sandbags while waves pour through and tanks shell.
def breach_step():
    s = TANKS + [
        radio("voss", "Sappers at the fence! Shit, they're setting charges!", 7.0),
        radio("marek", "Shoot them! Kill those bastards before they blow the fence!", 9.0),
        wave("sappers", 5.0, [unit([-4, 92], "recruit", hold=[-3, 72.5]), unit([3, 94], "recruit", hold=[2, 72.5]),
                               unit([9, 96], "regular", hold=[6, 73.5])]),
        {"action": "spawn_friendly", "group": "garrison", "delay": 2.0, "units": [
            {"pos": [-24, -10], "heading": 0, "profile": "rifleman", "name": "Rifleman", "hold": hold}
            for hold in ([-12, 15.5, 0], [-7, 16, 0], [6, 15, 0], [12, -1, 0], [16, 3, 0], [-2, 22, 0])]},
        squad_hold(1.0, marek=[-10, 15.5, 0], voss=[10.0, -3.5, 20], kell=[-6.5, 15.8, 0]),
        # The charges go off whether the sappers live or not.
        {"action": "explosion", "pos": [-1, 71, 0.3], "radius": 10, "damage": 250, "scale": 6.0, "delay": 17.0},
        {"action": "destroy_prop", "id": "north_breach", "explode": False, "delay": 17.0},
        {"action": "debris", "pos": [-1, 71, 1.0], "count": 22, "kind": "metal", "size": 0.35, "delay": 17.1},
        {"action": "show_prop", "id": "crater_breach", "delay": 17.1},
        {"action": "fire", "pos": [-6, 68, 0], "size": 1.6, "delay": 17.2},
        {"action": "smoke", "pos": [0, 70, 0.5], "seconds": 400, "delay": 17.2},
        {"action": "notice", "text": "THE FENCE IS BREACHED", "delay": 17.5},
        radio("marek", "They're through! Fuck! Every man on the line - FIRE!", 18.0),
    ]
    return {"id": "breach", "objective": {"type": "reach", "pos": [-8, 14, 0], "radius": 7,
                                          "text": "Get to the north sandbags"},
            "on_start": s, "on_complete": [{"action": "checkpoint", "pos": [-8, 12, 0], "heading": 0}]}


def hold_north_step():
    s = tanks_at((-24, 108), (24, 112), (6, 128)) + [wave("n1", 3.0, line_wave(84, (-12, -6, 0, 6, 12, 18), 40)),
         wave("n2", 30.0, line_wave(90, (-20, -10, -2, 8, 16, 24), 30)),
         wave("n3", 62.0, line_wave(88, (-16, -8, 0, 8, 16), 25, "veteran")),
         wave("n4", 95.0, line_wave(92, (-22, -12, -4, 4, 12, 22), 20)),
         wave("n5", 125.0, line_wave(86, (-10, -2, 6, 14), 15, "veteran")),
         {"action": "barrage", "area": [-35, 5, 35, 60], "count": 22, "seconds": 150, "radius": 6, "damage": 130,
          "scale": 3.0, "target_group": "garrison", "aimed": 0.5, "delay": 10.0},
         radio("kell", "There's too many of them! There's too fucking many!", 24.0),
         radio("marek", "Keep firing, damn it! Make every shot count!", 27.0),
         radio("voss", "Tank! Left side! Shit, it's aiming at the bunker!", 44.0),
         radio("marek", "Medic! MEDIC! Man down! Oh god, man down!", 70.0),
         radio("voss", "Second group at the breach! Twenty, maybe more! Bloody hell!", 92.0),
         radio("kell", "I'm almost out! Somebody throw me a fucking magazine!", 112.0),
         radio("marek", "Hold on! Hold on, damn you! Just a little longer!", 132.0),
         {"action": "refill_ammo", "delay": 75.0}]
    s += tank_fire("tank1", 46.0, [-10, 14, 1.0], "earth") + tank_fire("tank2", 58.0, [10, -3, 1.0], "earth")
    s += tank_fire("tank3", 80.0, [-20, 56, 3.0]) + tank_fire("tank1", 104.0, [30, 40, 2.0])
    s += tank_fire("tank2", 120.0, [-2, 22, 1.0], "earth") + tank_fire("tank3", 140.0, [16, 3, 1.0], "earth")
    s += strike(100.0, [-14, 52], radius=10, fire=2.0) + strike(118.0, [18, 48], radius=10, fire=2.0)
    return {"id": "hold_north", "objective": {"type": "survive", "seconds": 150, "text": "Hold the north sandbags"},
            "on_start": s,
            "on_complete": [radio("marek", "We can't hold here! Fuck it - fall back to the hangar! GO!", 0.2),
                            {"action": "refill_ammo"},
                            {"action": "checkpoint", "pos": [-6, 8, 0], "heading": 120, "delay": 1.0}]}


# Stage 2: the hangar. The tanks drive up to the breach and shell everything.
def fall_hangar_step():
    s = [{"action": "group_move", "group": "garrison", "pos": [22, 20], "spread": [2.5, 0.8], "heading": -20},
         squad_hold(0.5, marek=[26, 21, -10], voss=[31, 20, 0], kell=[22, 22, -20]),
         {"action": "vehicle_command", "id": "tank1", "path": [[-24, 108, 0], [-8, 80, 0]], "speed": 3.0},
         {"action": "vehicle_command", "id": "tank2", "path": [[24, 112, 0], [8, 82, 0]], "speed": 3.0, "delay": 2.0},
         {"action": "barrage", "area": [-30, 0, 30, 30], "count": 10, "seconds": 25, "radius": 6, "damage": 110,
          "scale": 3.0, "target_group": "garrison", "aimed": 0.4, "delay": 2.0},
         radio("kell", "Tomas! This way, behind the trucks! Move it!", 4.0),
         {"action": "near_miss", "distance": 4.0, "delay": 6.5}]
    s += strike(3.0, [-10, 16], fire=2.2) + strike(6.0, [8, -2], fire=1.8)
    return {"id": "fall_hangar", "objective": {"type": "reach", "pos": [27, 22, 0], "radius": 6,
                                               "text": "Fall back to the hangar"},
            "on_start": s, "on_complete": [{"action": "checkpoint", "pos": [27, 20, 0], "heading": -10}]}


def hold_hangar_step():
    s = tanks_at((-8, 80), (8, 82), (6, 128)) + [wave("h1", 2.0, line_wave(70, (-14, -6, 2, 10, 18), 20)),
         wave("h2", 32.0, line_wave(74, (-18, -8, 0, 8, 16, 24), 18)),
         wave("h3", 64.0, line_wave(72, (-12, -2, 6, 14), 15, "veteran")),
         wave("h4", 92.0, line_wave(76, (-20, -10, 0, 10, 20), 12)),
         {"action": "barrage", "area": [5, 5, 45, 40], "count": 14, "seconds": 120, "radius": 6, "damage": 120,
          "scale": 3.0, "target_group": "garrison", "aimed": 0.55, "delay": 8.0},
         radio("voss", "Tanks at the breach! Shit, shit, they're coming in!", 10.0),
         radio("marek", "Get away from the walls! They'll bring the whole damn roof down!", 36.0),
         radio("kell", "Doran's hit! Fuck! Doran's hit!", 58.0),
         radio("marek", "Leave him! He's gone! Keep fucking shooting!", 61.0),
         radio("voss", "They're flanking us on the left! Bastards!", 84.0),
         {"action": "refill_ammo", "delay": 60.0}]
    targets = [[30, 30, 3.0], [38, 26, 2.0], [26, 18, 1.0], [36, 16, 1.5]]
    for i, t in enumerate((14, 26, 40, 52, 70, 88, 104)):
        s += tank_fire(("tank1", "tank2")[i % 2], float(t), targets[i % 4], "metal" if i % 3 == 2 else "concrete")
    return {"id": "hold_hangar", "objective": {"type": "survive", "seconds": 120, "text": "Hold the hangar"},
            "on_start": s,
            "on_complete": [radio("marek", "The hangar's lost! Halden - the cipher book in HQ! Move your ass!", 0.2),
                            {"action": "refill_ammo"},
                            {"action": "checkpoint", "pos": [26, 14, 0], "heading": 180, "delay": 1.0}]}


# Stage 3: the last stand at HQ, then the run to the truck.
def hold_hq_step():
    s = tanks_at((-8, 80), (8, 82), (6, 128)) + [{"action": "group_move", "group": "garrison", "pos": [18, -26], "spread": [2.0, -1.2], "heading": 0},
         squad_hold(0.5, marek=[22, -22, 0], voss=[34, -22, 10], kell=[18, -24, -10]),
         {"action": "vehicle_command", "id": "tank1", "path": [[-8, 80, 0], [-4, 60, 0], [-2, 36, 0]], "speed": 3.0},
         {"action": "vehicle_command", "id": "tank2", "path": [[8, 82, 0], [6, 58, 0], [14, 40, 0]], "speed": 3.0},
         wave("q1", 4.0, line_wave(60, (-10, 0, 10, 20, 30), 0)),
         wave("q2", 34.0, line_wave(64, (-16, -6, 4, 14, 24, 34), -5)),
         wave("q3", 66.0, line_wave(62, (-8, 2, 12, 22, 32), -10, "veteran")),
         {"action": "barrage", "area": [0, -40, 45, 0], "count": 12, "seconds": 100, "radius": 6, "damage": 110,
          "scale": 3.0, "target_group": "garrison", "aimed": 0.5, "delay": 6.0},
         radio("bastion", "All Northern Sector units, Line Kesh is your rally point. Trucks are at the south gates.",
               8.0),
         radio("marek", "Hold HQ until the truck is ready! Nobody runs until I fucking say so!", 13.0),
         radio("voss", "Tank! Shit! It's coming right through the motor pool!", 40.0),
         radio("kell", "We're not getting out of here, are we?", 76.0),
         radio("marek", "Not if you keep talking! Shut up and SHOOT!", 79.0),
         {"action": "refill_ammo", "delay": 50.0}]
    targets = [[22, -22, 3.0], [34, -24, 2.5], [-24, -14, 2.0], [28, -34, 3.5]]
    for i, t in enumerate((20, 34, 48, 62, 78, 92)):
        s += tank_fire(("tank1", "tank2")[i % 2], float(t), targets[i % 4])
    s += strike(30.0, [-24, -10], crater="crater_barracks", fire=2.4) + strike(56.0, [-44, -24], fire=2.2)
    done = [{"action": "sound", "sound": "radio_beep"},
            radio("bastion", "All Northern Sector units: fall back to Line Kesh. I repeat, fall back.", 0.2),
            radio("marek", "That's it! Screw this - everyone to the south gate! The truck's waiting!", 4.6),
            {"action": "destroy_prop", "id": "main_gate", "explode": False},
            {"action": "group_move", "group": "garrison", "pos": [-9, -60], "spread": [3, 0], "heading": 0,
             "delay": 2.0},
            {"action": "refill_ammo"},
            {"action": "checkpoint"}]
    done += strike(9.0, [34, -22], radius=9, damage=160, crater="crater_hq", fire=2.6)
    return {"id": "hold_hq", "objective": {"type": "survive", "seconds": 100, "text": "Hold HQ until the truck is ready"},
            "on_start": s, "on_complete": done}


WAVE3 = [unit([x, y], "veteran" if x % 8 == 0 else "regular", [x * 0.3, -20]) for x, y in
         ((-8, 40), (0, 44), (8, 40), (-14, 48), (14, 48), (-4, 54), (4, 56), (-20, 56), (20, 56), (0, 62))]


def rebuild_mission():
    d = json.loads(MISSION.read_text(encoding="utf-8"))
    steps = {s["id"]: s for s in d["steps"]}
    patrol, relay, codebook, fall_back = (steps[k] for k in ("patrol", "relay", "codebook", "fall_back"))

    # Calm morning: the garrison stands at its posts.
    patrol["on_start"] = [a for a in patrol["on_start"] if not (a["action"] == "spawn_friendly"
                                                                and a.get("group") == "garrison")]
    patrol["on_start"].insert(0, {"action": "spawn_friendly", "group": "garrison", "units": [
        {"pos": pos, "heading": h, "profile": "rifleman", "name": "Rifleman"} for pos, h in GARRISON]})
    relay["on_complete"] = [radio("bastion", "...Ridgeback, this is Bastion, do you read--", 0.2)]

    # Cipher book: HQ is about to be overrun.
    codebook["on_start"] = [radio("voss", "They're in the motor pool! Hurry the hell up, Tomas!", 4.0),
                            wave("cb", 6.0, line_wave(40, (0, 10, 20, 30), -20))]
    codebook["on_complete"] = [{"action": "notice", "text": "CIPHER BOOK RECOVERED"},
                               radio("marek", "Got it? Good. Now get on the line - we hold HQ!", 0.6),
                               {"action": "checkpoint", "pos": [26, -26, 0], "heading": 0, "delay": 0.5}]

    fall_back["on_start"] = [
        wave("wave3", 3.0, WAVE3),
        {"action": "barrage", "area": [-55, -40, 55, 45], "count": 32, "seconds": 45, "radius": 7, "damage": 100,
         "scale": 3.2, "target_group": "garrison", "aimed": 0.35, "delay": 3.0},
        {"action": "vehicle_command", "id": "tank1", "path": [[-2, 36, 0], [-4, 0, 0]], "speed": 3.5, "delay": 4.0},
        radio("marek", "Don't look back! Keep moving! Get to the damn truck!", 6.0),
        radio("kell", "Tomas, come on! Leave them! There's nothing fucking left!", 16.0),
    ]
    fall_back["objective"]["text"] = "Fall back to the south gate"

    d["knockdown"] = True                      # one shell throws the player off his feet
    d["steps"] = [patrol, relay, bombardment_step(), breach_step(), hold_north_step(), fall_hangar_step(),
                  hold_hangar_step(), codebook, hold_hq_step(), fall_back]
    d["outro"]["lines"] = [
        {"t": 0.3, "speaker": "marek", "text": "Into the truck! Go, go, go!", "seconds": 2.6},
        {"t": 3.0, "speaker": "narrator", "text": "At 06:14 the Directorate crossed the frontier along two hundred "
                                                   "kilometres.", "seconds": 4.0},
        {"t": 7.2, "speaker": "narrator", "text": "Outpost Ridgeback held for thirty-one minutes. Twenty-two men were "
                                                   "stationed there.", "seconds": 4.5},
        {"t": 11.8, "speaker": "narrator", "text": "Nine of us made it to the truck.", "seconds": 2.6},
    ]
    d["outro"]["shots"][0]["duration"] = 15.0
    MISSION.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"m01: {len(d['steps'])} steps")


if __name__ == "__main__":
    build_map()
    rebuild_mission()
