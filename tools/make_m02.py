"""Mission 2 "The Line Breaks": a heavy assault on Kesh Ridge that Kareth cannot stop.

    .venv\\Scripts\\python.exe tools\\make_m02.py

Stages: report -> man the trench -> hold the line (waves, enemy RPGs and mortars, our MGs and mortars)
-> tanks (the player gets a launcher) -> machine-gun nest -> sappers blow the line -> fall back
-> second line while civilians flee to the trucks -> the last truck.
Keeps the existing report / trench / MG-nest / fall-back / truck objectives and rewrites the rest.
Also gives the forward wire ids and adds hidden craters to data/maps/kesh_ridge.json. Safe to re-run.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "data" / "missions" / "m02_line_breaks.json"
MAP = ROOT / "data" / "maps" / "kesh_ridge.json"

WIRES = {"wire_a": [-40, 10], "wire_b": [-4, 9.5], "wire_c": [28, 10], "wire_d": [52, 10]}
TRENCH_CRATERS = {"tcrater_1": [-44, 4.0], "tcrater_2": [-20, 3.0], "tcrater_3": [3, 4.2], "tcrater_4": [22, 3.2],
                  "tcrater_5": [46, 4.0]}


TRUCK_PROPS = {"ptruck_a": [-30, -80], "ptruck_b": [-12, -80], "ptruck_c": [6, -80], "ptruck_d": [24, -80]}
# The convoy: lead truck first. The player rides truck 4; truck 5 (the last) is 12 m behind him.
CONVOY = [("truck1", 24), ("truck2", 6), ("truck3", -12), ("truck4", -30), ("truck5", -42)]
ROAD_Y = -80.0


def build_map():
    data = json.loads(MAP.read_text(encoding="utf-8"))
    props = [p for p in data["props"] if not str(p.get("id", "")).startswith("tcrater_")]
    for p in props:
        for wid, pos in WIRES.items():
            if p["type"] == "wire_line" and p["pos"][:2] == pos:
                p["id"] = wid
        for tid, pos in TRUCK_PROPS.items():
            if p["type"] == "truck" and p["pos"][:2] == pos:
                p["id"] = tid
    for cid, pos in TRENCH_CRATERS.items():
        props.append({"type": "crater", "pos": pos, "params": {"radius": 3.4}, "id": cid, "hidden": True})
    data["props"] = props
    MAP.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------- helpers
def radio(speaker, text, delay):
    return {"action": "radio", "speaker": speaker, "text": text, "delay": delay,
            "seconds": round(1.0 + len(text.split()) * 0.33, 1)}


def unit(pos, profile="regular", alert=None, hold=None, heading=180):
    u = {"pos": pos, "profile": profile, "heading": heading}
    if alert:
        u["alert"] = alert
    if hold:
        u["hold"] = hold
    return u


def wave(group, delay, y, xs, alert_y=6, vet_every=4):
    units = [unit([x, y + (i % 3) * 3], "veteran" if i % vet_every == vet_every - 1 else "regular",
                  [x * 0.8, alert_y]) for i, x in enumerate(xs)]
    return {"action": "spawn", "group": group, "delay": delay, "units": units}


def boom(t, pos, radius=9.0, damage=320.0, scale=5.5, debris="earth"):
    return [{"action": "explosion", "pos": [pos[0], pos[1], 0.3], "radius": radius, "damage": damage, "scale": scale,
             "delay": t},
            {"action": "debris", "pos": [pos[0], pos[1], 0.8], "count": 18, "kind": debris, "size": 0.4,
             "delay": t + 0.05}]


def tank(tid, path, delay=0.0, speed=4.0):
    return {"action": "spawn_vehicle", "kind": "tank", "id": tid, "path": path, "speed": speed, "loop": False,
            "health": 900, "delay": delay}


# ------------------------------------------------------------------------------------------- stages
def hold_line_step(old):
    line = next(a for a in old["on_start"] if a["action"] == "spawn_friendly" and a["group"] == "line")
    s = [line,
         {"action": "spawn_friendly", "group": "mg_team", "units": [
             {"pos": [-30, 0.0], "heading": 0, "profile": "gunner", "name": "Machine gunner"},
             {"pos": [30, 0.0], "heading": 0, "profile": "gunner", "name": "Machine gunner"}]},
         radio("rusk", "Here they come! Hold your fire until they reach the wire! Steady, damn it!", 1.0),
         wave("assault", 2.0, 114, (-40, -24, -8, 8, 24, 40)),
         wave("assault", 24.0, 116, (-46, -30, -14, 2, 18, 34, 48)),
         wave("assault", 48.0, 115, (-36, -18, 0, 18, 36), vet_every=3),
         wave("assault", 72.0, 117, (-44, -26, -8, 10, 28, 46)),
         wave("assault", 96.0, 114, (-34, -16, 2, 20, 38), vet_every=2),
         {"action": "spawn", "group": "rpg_team", "delay": 20.0, "units": [
             unit([-20, 112], "veteran", hold=[-18, 40, 180]), unit([6, 113], "veteran", hold=[6, 26, 180]),
             unit([30, 112], "veteran", hold=[28, 33, 180])]},
         {"action": "rpg", "shooter": "rpg_team", "target": "team:friendly", "count": 16, "interval": 6.0,
          "delay": 34.0},
         # Enemy mortars on our trench, ours on their infantry.
         {"action": "barrage", "delay": 22.0, "area": [-55, -6, 55, 6], "count": 16, "seconds": 100, "radius": 6,
          "damage": 150, "scale": 3.2, "from": "north", "target_group": "line", "aimed": 0.7},
         {"action": "barrage", "delay": 40.0, "area": [-55, 30, 55, 100], "count": 26, "seconds": 70, "radius": 6,
          "damage": 220, "scale": 3.2, "from": "south", "target_group": "team:enemy", "aimed": 0.75},
         radio("hammer", "Hammer, fire mission. Rounds on the way - heads down!", 39.0),
         radio("marek", "Keep firing! Don't let those bastards reach the trench!", 14.0),
         radio("voss", "RPG! Crater line, left! Shit, get down!", 36.0),
         radio("kell", "They just keep coming! How many of these fuckers are there?!", 62.0),
         radio("rusk", "Machine guns, sweep the wire! Cut them down!", 66.0),
         radio("marek", "Medic! Rifleman down on the right! Damn it!", 88.0),
         radio("voss", "Another wave! Behind the smoke! Fuck, it's a whole battalion!", 102.0),
         {"action": "refill_ammo", "delay": 70.0}]
    return {"id": "hold_line", "objective": {"type": "survive", "seconds": 120, "text": "Hold the line"},
            "on_start": s,
            "on_complete": [radio("bastion", "Kesh Ridge, Bastion: enemy armour moving on your sector. Hold them.", 0.2),
                            {"action": "refill_ammo", "delay": 1.0},
                            {"action": "checkpoint", "pos": [12, -0.2, 0], "heading": 10, "delay": 1.0}]}


def tanks_step():
    s = [tank("tank1", [[-34, 240, 0], [-28, 120, 0], [-24, 58, 0]], 0.0),
         tank("tank2", [[30, 250, 0], [24, 124, 0], [18, 62, 0]], 3.0),
         radio("voss", "TANKS! Two of them, coming straight down the middle!", 3.0),
         radio("rusk", "Halden! Grab the launcher - kill those fucking tanks!", 6.0),
         {"action": "give_weapon", "id": "rl3", "ammo": 8, "delay": 7.0},
         radio("marek", "Switch to the launcher, Tomas - press three! Aim for the hull!", 9.0),
         # Our rocket teams and the enemy's.
         {"action": "rpg", "shooter": "line", "target": "tank1", "count": 4, "interval": 9.0, "delay": 14.0},
         {"action": "rpg", "shooter": "line", "target": "tank2", "count": 4, "interval": 10.0, "delay": 19.0},
         {"action": "rpg", "shooter": "rpg_team", "target": "team:friendly", "count": 10, "interval": 6.0,
          "delay": 4.0},
         wave("armour_inf", 6.0, 118, (-40, -28, -16, 16, 28, 40)),
         wave("armour_inf", 40.0, 116, (-36, -20, -4, 12, 28, 44), vet_every=2),
         {"action": "barrage", "delay": 8.0, "area": [-55, -6, 55, 6], "count": 10, "seconds": 70, "radius": 6,
          "damage": 150, "scale": 3.2, "from": "north", "target_group": "line", "aimed": 0.6},
         radio("kell", "That tank's turning towards us! Oh fuck, oh fuck!", 30.0),
         radio("voss", "Rocket team's down! It's on you, Halden!", 52.0),
         {"action": "refill_ammo", "delay": 45.0}]
    return {"id": "tanks", "objective": {"type": "destroy", "targets": ["tank1", "tank2"],
                                         "text": "Destroy the tanks"},
            "on_start": s,
            "on_complete": [radio("marek", "Hell yes! Both tanks are burning!", 0.3),
                            radio("rusk", "Machine gun, centre-right, in the crater line! Shit, it's cutting us to "
                                          "pieces!", 3.5),
                            {"action": "refill_ammo"},
                            {"action": "checkpoint", "pos": [12, -0.2, 0], "heading": 10, "delay": 1.0}]}


def breach_line_step():
    s = [radio("voss", "Sappers! They're running for the wire with charges!", 0.5),
         radio("rusk", "Shoot the sappers! Shoot them NOW!", 2.5),
         {"action": "spawn", "group": "sappers", "delay": 0.5, "units": [
             unit([x, 60 + (i % 2) * 6], "recruit" if i % 2 else "regular", hold=[x, 11.5, 180])
             for i, x in enumerate((-42, -30, -18, -4, 8, 22, 34, 48))]},
         wave("assault", 3.0, 112, (-40, -24, -8, 8, 24, 40)),
         {"action": "smoke", "pos": [-20, 30, 0.5], "seconds": 60, "delay": 1.0},
         {"action": "smoke", "pos": [20, 32, 0.5], "seconds": 60, "delay": 1.5},
         radio("kell", "There's too many! I can't stop them all!", 10.0)]
    # The charges go off along the whole forward line - wire, sandbags and the men behind them.
    for i, (wid, pos) in enumerate(WIRES.items()):
        t = 16.0 + i * 0.7
        s += boom(t, [pos[0], pos[1] - 2.0], debris="wood")
        s.append({"action": "destroy_prop", "id": wid, "explode": False, "delay": t})
    for i, (cid, pos) in enumerate(TRENCH_CRATERS.items()):
        t = 16.3 + i * 0.6
        s += boom(t, pos, radius=8.0, damage=300.0, scale=5.0)
        s.append({"action": "show_prop", "id": cid, "delay": t + 0.05})
    # Nobody on the forward line survives the charges.
    s.append({"action": "blast_group", "group": "line", "interval": 0.3, "debris": "wood", "delay": 16.4})
    s.append({"action": "blast_group", "group": "mg_team", "interval": 0.5, "debris": "earth", "delay": 17.0})
    s.append({"action": "notice", "text": "THE LINE IS BROKEN", "delay": 19.5})
    return {"id": "breach_line", "objective": {"type": "survive", "seconds": 22, "text": "Stop the sappers!"},
            "on_start": s,
            "on_complete": [radio("rusk", "The line's gone! Everyone back to the second line - NOW! MOVE!", 0.2)]}


def civilians():
    """Families from Kesh running to the trucks; staggered so the crowd keeps coming."""
    starts = [(-40, -93), (-24, -94), (-8, -93), (8, -94), (24, -93), (40, -94), (-52, -86), (55, -86)]
    trucks = [-30, -12, 6, 24]
    people = []
    for i in range(18):
        sx, sy = starts[i % len(starts)]
        tx = trucks[i % 4]
        people.append({"model": "woman" if i % 3 == 1 else "man", "delay": 2.0 + i * 4.5,
                       "path": [[sx + (i % 3) - 1, sy], [sx * 0.6 + tx * 0.4, -88], [tx + 4.0, -82.5]],
                       "speed": 3.6 + (i % 4) * 0.4, "board": True})
    # A few run along the road behind the line, terrified, and stay there.
    for i, (x0, x1) in enumerate(((-60, -20), (60, 22), (-55, -40))):
        people.append({"model": "man" if i else "woman", "delay": 6.0 + i * 12, "path": [[x0, -72], [x1, -70]],
                       "speed": 4.2, "then": "terrified"})
    return people


def convoy_trucks(if_missing=False):
    """The parked trucks become real vehicles (waiting, engines running) so they can drive away."""
    out = []
    if not if_missing:
        out += [{"action": "destroy_prop", "id": tid, "explode": False} for tid in TRUCK_PROPS]
    for tid, x in CONVOY:
        a = {"action": "spawn_vehicle", "kind": "truck", "id": tid, "path": [[x, ROAD_Y, 0], [x + 260, ROAD_Y, 0]],
             "speed": 0.8, "loop": False, "paused": True, "health": 300}
        if if_missing:
            a["if_missing"] = True
        out.append(a)
    return out


def to_truck_step(old):
    old["objective"].update({"pos": [-34.5, ROAD_Y + 1.2, 0], "radius": 3.5, "text": "Get to the last truck"})
    old["on_start"] = convoy_trucks(if_missing=True) + [
        radio("marek", "Truck four! Get in, get in!", 1.0)]
    old["on_complete"] = []
    return old


def convoy_step():
    """Driving away: an RPG hits the last truck. The enemy keeps shooting it, and the people who
    climb out are gunned down. You can only watch."""
    s = [{"action": "player_weapons", "enabled": False},
         {"action": "player_invulnerable", "value": True},
         {"action": "start_ride", "vehicle": "truck4", "seat": [0.0, -3.0, 1.15], "yaw": 90,
          "squad": {"marek": [0.7, -1.6, 1.15], "voss": [-0.7, -1.8, 1.15], "kell": [0.6, -2.6, 1.15]}}]
    s += [{"action": "vehicle_command", "id": tid, "paused": False, "speed": 0.8} for tid, _ in CONVOY]
    s += [
        # Enemy soldiers come over the ridge behind the convoy.
        {"action": "spawn", "group": "pursuers", "delay": 0.5, "units": [
            unit([x, y], "veteran" if i % 2 else "regular", hold=[x, y, 90])
            for i, (x, y) in enumerate(((-62, -66), (-58, -62), (-66, -72), (-55, -70), (-60, -58), (-50, -64)))]},
        radio("kell", "We made it... we actually made it.", 2.0),
        radio("voss", "RPG! Behind us! Truck five!", 5.4),
        {"action": "rpg", "shooter": "pursuers", "target": "truck5", "count": 3, "interval": 0.8, "damage": 500,
         "delay": 6.0},
        {"action": "destroy_vehicle", "id": "truck5", "delay": 6.5},      # the rocket always finds it
        {"action": "gunfire", "shooter": "pursuers", "target": "truck5", "seconds": 14.0, "rate": 7.0, "delay": 7.5},
        radio("kell", "No! NO! There are people in there!", 8.0),
        {"action": "spawn_civilians", "group": "truck5", "delay": 9.5, "units": [
            {"model": "woman" if i % 2 else "man", "delay": i * 0.6,
             "path": [[-42 + dx, ROAD_Y - 1.5], [-42 + dx * 3, ROAD_Y + dy]], "speed": 3.2 + i * 0.2,
             "then": "terrified"}
            for i, (dx, dy) in enumerate(((-1.5, 14), (1.0, 12), (0.5, -13), (-0.8, -15), (1.8, 16), (0.0, -11)))]},
        radio("marek", "Keep driving! Don't stop the truck!", 10.5),
        {"action": "civ_shot", "group": "truck5", "shooter": "pursuers", "count": 6, "interval": 1.4, "delay": 11.5},
        radio("kell", "They're shooting them! They're shooting them in the back!", 13.0),
        radio("marek", "Don't look, Tomas. Don't look.", 19.0),
        {"action": "vehicle_command", "id": "truck1", "speed": 6.0, "delay": 20.0},
        {"action": "vehicle_command", "id": "truck2", "speed": 6.0, "delay": 20.0},
        {"action": "vehicle_command", "id": "truck3", "speed": 6.0, "delay": 20.0},
        {"action": "vehicle_command", "id": "truck4", "speed": 6.0, "delay": 20.0},
        radio("kell", "We left them... we just left them there.", 23.0),
    ]
    return {"id": "convoy", "objective": {"type": "survive", "seconds": 28, "text": "Get out of Kesh"},
            "on_start": s,
            "on_complete": [{"action": "player_weapons", "enabled": True},
                            {"action": "player_invulnerable", "value": False},
                            {"action": "complete_mission"}]}


def hold_second_step(old):
    rear = next(a for a in old["on_start"] if a["action"] == "spawn_friendly" and a["group"] == "rear")
    s = [rear] + convoy_trucks() + [
         {"action": "spawn_civilians", "group": "kesh", "units": civilians()},
         tank("tank3", [[0, 230, 0], [2, 110, 0], [4, 30, 0]], 6.0, speed=3.5),
         wave("push", 8.0, 70, (-40, -24, -8, 8, 24, 40), alert_y=-35),
         wave("push", 34.0, 50, (-44, -28, -12, 4, 20, 36, 50), alert_y=-38, vet_every=3),
         wave("push", 62.0, 30, (-36, -16, 4, 24, 44), alert_y=-40, vet_every=2),
         {"action": "spawn", "group": "rpg_team2", "delay": 20.0, "units": [
             unit([-24, 60], "veteran", hold=[-22, 4, 180]), unit([20, 62], "veteran", hold=[20, 4, 180])]},
         {"action": "rpg", "shooter": "rpg_team2", "target": "team:friendly", "count": 10, "interval": 7.0,
          "delay": 30.0},
         {"action": "barrage", "delay": 12.0, "area": [-50, -48, 50, -34], "count": 12, "seconds": 80, "radius": 6,
          "damage": 150, "scale": 3.2, "from": "north", "target_group": "rear", "aimed": 0.6},
         {"action": "barrage", "delay": 26.0, "area": [-50, -96, 50, -66], "count": 9, "seconds": 70, "radius": 6,
          "damage": 200, "scale": 3.2, "from": "north", "target_group": "civ", "aimed": 0.6},
         radio("convoy", "Convoy Two-Six to Kesh Ridge: loading the last families now. Give us a few more minutes.",
               3.0),
         radio("kell", "Shells are falling on the trucks! There are kids down there!", 30.0),
         radio("marek", "Eyes front, Kell! If we break, they all die!", 33.0),
         radio("rusk", "They're in the communication trenches! Shit! Watch the junctions!", 48.0),
         radio("voss", "Third tank! It's on the old line, shelling us!", 58.0),
         radio("kell", "Oh god... they hit the crowd. They hit the fucking crowd!", 72.0),
         {"action": "refill_ammo", "delay": 50.0}]
    return {"id": "hold_second", "objective": {"type": "survive", "seconds": 100,
                                               "text": "Hold the second line until the convoy is ready"},
            "on_start": s,
            "on_complete": [radio("convoy", "Convoy Two-Six: we're full. Last truck is waiting for you - move!", 0.2),
                            radio("rusk", "That's our signal! Go, Halden! Go, damn it! We'll cover you!", 4.0),
                            {"action": "squad_follow"},
                            {"action": "checkpoint", "pos": [-10, -43, 0], "heading": 180, "delay": 1.0}]}


def rebuild_mission():
    d = json.loads(MISSION.read_text(encoding="utf-8"))
    steps = {s["id"]: s for s in d["steps"]}
    report, man_trench, mg_nest, fall_back, to_truck = (steps[k] for k in
                                                        ("report", "man_trench", "mg_nest", "fall_back", "to_truck"))
    for key in ("on_start", "on_complete"):
        mg_nest[key] = [a for a in mg_nest.get(key, []) if a["action"] != "radio" or a["speaker"] != "rusk"]
    mg_nest["on_complete"] = [a for a in mg_nest.get("on_complete", []) if a["action"] not in ("checkpoint",)] + [
        {"action": "refill_ammo"}, {"action": "checkpoint", "pos": [12, -0.2, 0], "heading": 10, "delay": 1.0}]
    # Fall back under fire: tanks' successors and the enemy pour over the broken line.
    fall_back["on_start"] = [a for a in fall_back["on_start"] if a["action"] not in ("radio", "sound")] + [
        {"action": "group_move", "group": "line", "pos": [-40, -40.2], "spread": [8, 0], "heading": 0, "delay": 1.0},
        {"action": "group_move", "group": "mg_team", "pos": [-28, -40.2], "spread": [30, 0], "heading": 0},
        radio("marek", "Go, go! Don't stop for anything!", 2.0),
        radio("kell", "They're right behind us! Fuck, run!", 9.0)]
    old_line = steps.get("hold_line")
    old_second = steps.get("hold_second")
    d["steps"] = [report, man_trench, hold_line_step(old_line), tanks_step(), mg_nest, breach_line_step(),
                  fall_back, hold_second_step(old_second), to_truck_step(to_truck), convoy_step()]
    d["knockdown"] = True
    MISSION.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"m02: {len(d['steps'])} steps")


if __name__ == "__main__":
    build_map()
    rebuild_mission()
    # Riflemen spawned inside a trench stand on its firing step.
    subprocess.run([sys.executable, str(ROOT / "tools" / "snap_to_firing_step.py"), str(MISSION)], check=True)
