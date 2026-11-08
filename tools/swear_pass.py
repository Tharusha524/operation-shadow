"""Combat dialogue for Missions 1 and 2: soldiers under fire swear (mild and strong).

    .venv\\Scripts\\python.exe tools\\swear_pass.py

Replaces radio lines by their exact text in tools/make_m01.py (the M1 generator) and in the M2 mission
file. Calm lines (patrol, briefings, command radio) stay clean. Run make_m01.py afterwards.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LINES = {
    "INCOMING! Everybody get down!": "INCOMING! Get down! Get the fuck down!",
    "The north tower's gone! Pavel was up there!": "Shit, the north tower's gone! Pavel was up there!",
    "Where is it coming from?! I can't see anything!": "Where the hell is it coming from?! I can't see a damn thing!",
    "Missiles. They're hitting everything at once. Stay down!":
        "Missiles! They're hitting every fucking thing at once! Stay down!",
    "Bunker two is gone... they're all gone.": "Bunker two is gone... Jesus, they're all gone.",
    "Armour! Tanks on the north ridge!": "Oh shit. Armour! Tanks on the north ridge!",
    "Here they come. Everyone up! Get to the sandbags!": "Here they come! Everyone up! Move your asses, get to the sandbags!",
    "Sappers at the fence! They're setting charges!": "Sappers at the fence! Shit, they're setting charges!",
    "Shoot them! Don't let them blow the fence!": "Shoot them! Kill those bastards before they blow the fence!",
    "They're through! Every man on the line - FIRE!": "They're through! Fuck! Every man on the line - FIRE!",
    "There's too many of them!": "There's too many of them! There's too fucking many!",
    "Keep firing! Make every shot count!": "Keep firing, damn it! Make every shot count!",
    "Tank! Left side - it's aiming at the bunker!": "Tank! Left side! Shit, it's aiming at the bunker!",
    "Medic! Man down! MAN DOWN!": "Medic! MEDIC! Man down! Oh god, man down!",
    "Second group at the breach! Twenty, maybe more!": "Second group at the breach! Twenty, maybe more! Bloody hell!",
    "I'm almost out! Somebody throw me a magazine!": "I'm almost out! Somebody throw me a fucking magazine!",
    "Hold on! Just a little longer!": "Hold on! Hold on, damn you! Just a little longer!",
    "We can't hold here! Fall back to the hangar! GO!": "We can't hold here! Fuck it - fall back to the hangar! GO!",
    "Tomas! This way, behind the trucks!": "Tomas! This way, behind the trucks! Move it!",
    "Tanks at the breach! They're coming in!": "Tanks at the breach! Shit, shit, they're coming in!",
    "Get away from the walls! They'll bring the roof down!":
        "Get away from the walls! They'll bring the whole damn roof down!",
    "Doran's hit! Doran's hit!": "Doran's hit! Fuck! Doran's hit!",
    "Leave him! Keep shooting!": "Leave him! He's gone! Keep fucking shooting!",
    "They're flanking us on the left!": "They're flanking us on the left! Bastards!",
    "The hangar's lost! Halden - the cipher book in HQ! Move!":
        "The hangar's lost! Halden - the cipher book in HQ! Move your ass!",
    "They're in the motor pool! Hurry, Tomas!": "They're in the motor pool! Hurry the hell up, Tomas!",
    "Hold HQ until the truck is ready! Nobody runs before I say!":
        "Hold HQ until the truck is ready! Nobody runs until I fucking say so!",
    "Tank! It's coming through the motor pool!": "Tank! Shit! It's coming right through the motor pool!",
    "Not if you keep talking. SHOOT!": "Not if you keep talking! Shut up and SHOOT!",
    "That's it! Everyone to the south gate - the truck's waiting!":
        "That's it! Screw this - everyone to the south gate! The truck's waiting!",
    "Don't look back! Keep moving! Get to the truck!": "Don't look back! Keep moving! Get to the damn truck!",
    "Tomas, come on! Leave them, there's nothing left!": "Tomas, come on! Leave them! There's nothing fucking left!",
    # Mission 2
    "Here they come! Hold your fire until they reach the wire!":
        "Here they come! Hold your fire until they reach the wire! Steady, damn it!",
    "Keep firing! Don't let them reach the trench!": "Keep firing! Don't let those bastards reach the trench!",
    "Machine gun, centre-right, in the crater line! It's cutting us to pieces!":
        "Machine gun, centre-right, in the crater line! Shit, it's cutting us to pieces!",
    "They're shelling the forward trench! Everyone back to the second line - NOW!":
        "They're shelling the forward trench! Fuck! Everyone back to the second line - NOW!",
    "They're in the communication trenches! Watch the junctions!":
        "They're in the communication trenches! Shit! Watch the junctions!",
    "That's our signal. Go, Halden! We'll cover you!": "That's our signal! Go, Halden! Go, damn it! We'll cover you!",
}


def main():
    gen = ROOT / "tools" / "make_m01.py"
    s = gen.read_text(encoding="utf-8")
    n1 = 0
    for old, new in LINES.items():
        if f'"{old}"' in s:
            s = s.replace(f'"{old}"', f'"{new}"')
            n1 += 1
    gen.write_text(s, encoding="utf-8")
    path = ROOT / "data" / "missions" / "m02_line_breaks.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    n2 = 0
    for step in d["steps"]:
        for key in ("on_start", "on_complete"):
            for a in step.get(key, []):
                if a.get("action") == "radio" and a["text"] in LINES:
                    a["text"] = LINES[a["text"]]
                    a["seconds"] = round(1.0 + len(a["text"].split()) * 0.33, 1)
                    n2 += 1
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"M1 generator: {n1} lines, M2: {n2} lines")


if __name__ == "__main__":
    main()
