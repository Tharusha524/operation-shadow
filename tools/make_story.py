"""Writes the story videos: data/story/prologue.json, <mission>.json (before) and <mission>_end.json (after).

Story and dialogue from the campaign script (OPERATION SHADOW - complete story script). Scenes that would
give away a mission's outcome are played after the mission as its ending video.
Run:  .venv\\Scripts\\python.exe tools\\make_story.py
Shot types and fields are documented in missions/story_video.py; sets in environments/sets.py.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "story"
W = -1.3                     # water level on the river / harbour / lake maps


def line(speaker, text):
    return {"speaker": speaker, "text": text}


def narr(*texts):
    return [line("narrator", t) for t in texts]


def title(text, sub="", duration=4.5):
    return {"type": "title", "title": text, "subtitle": sub, "duration": duration, "lines": []}


def cast(model, pos, heading, anim="stand", **kw):
    return {"model": model, "pos": pos, "heading": heading, "anim": anim, **kw}


def shot(frm, to, look_from, look_to, lines, duration=5.0, caption=None, **kw):
    s = {"type": "scene", "from": frm, "to": to, "look_from": look_from, "look_to": look_to, "lines": lines,
         "duration": duration, **kw}
    if caption:
        s["caption"] = caption
    return s


def unit(pos, t, color="red"):
    return {"pos": pos, "t": t, "color": color}


def explosion(t, pos, shake=0.3, fire=None):
    e = {"t": t, "explosion": pos, "shake": shake}
    if fire:
        e["fire"] = fire
    return e


STORIES = {}

# =========================================================================================== PROLOGUE
# "The Last Morning of Peace" - 16 scenes. The man in the grey coat (Harrow) is never seen clearly.
FLASHBACK = {"saturation": 0.12, "tint": [1.12, 1.0, 0.82], "grain": 0.14, "contrast": 1.22, "vignette": 1.1}
NIGHT = {"exposure": 0.45, "saturation": 0.6, "tint": [0.75, 0.85, 1.15], "lift": 0.0}
SUNRISE = {"exposure": 1.0, "tint": [1.08, 0.98, 0.88], "saturation": 0.9}
GREY_COAT = "man"
TOWER = (62, 60.2, 4.0)                # north-east watchtower platform at Outpost Ridgeback


def bunker(*people):
    return list(people)


DREVAN_TABLE = cast("officer", [0.9, -1.4], 0)
KADE_TABLE = cast("enemy", [-1.6, -0.9], 0, "point", gun=False)
OSTROVA_SIDE = cast("enemy", [2.4, -1.3], -20, "stand", gun=False)
GUARD_L, GUARD_R = cast("enemy", [-7.2, 5.0], 180, "idle"), cast("enemy", [7.2, -5.0], 0, "idle")
SCREENS = [cast("officer", [0.5, 4.2], 0), cast("enemy", [-1.8, 4.4], 30, "point", gun=False),
           cast(GREY_COAT, [4.5, 4.8], 120, dark=True)]
ARGUE = [cast("officer", [0.0, -0.85], 0, "sit"), cast("enemy", [-1.6, -0.9], 0, "point", gun=False),
         cast("enemy", [2.2, 2.9], 180, "argue", gun=False), GUARD_L]
ORDER = [cast("officer", [0.9, -1.4], 0, "point"), cast("enemy", [-1.6, -0.9], 60, "salute", gun=False),
         cast("enemy", [2.2, 2.9], 180, "stand", gun=False), cast(GREY_COAT, [3.8, 5.0], 160, dark=True), GUARD_L]
FINAL = [cast("officer", [0.0, -0.85], 0, "sit"), cast("enemy", [-1.6, 4.2], 0, "point", gun=False),
         cast("enemy", [2.4, -1.3], -20, "stand", gun=False), cast(GREY_COAT, [-5.5, -3.2], 0, "type", dark=True)]
OUTPOST = [cast("friendly", [56, 67], 0, gun=False),
           cast("friendly", [48, 60], 30, path=[[48, 60], [54.6, 66.2]], speed=1.3,
                then={"anim": "argue", "heading": 40}, gun=False),
           cast("friendly", [60, 58], -30, gun=False),
           cast("friendly", [TOWER[0], TOWER[1]], 0, "aim", z=TOWER[2])]
OUTPOST_TALK = [cast("friendly", [56, 67], 0, gun=False), cast("friendly", [54.6, 66.2], 40, "argue", gun=False),
                cast("friendly", [60, 58], -30, gun=False), cast("friendly", [TOWER[0], TOWER[1]], 0, "aim", z=TOWER[2])]
MAREK_WALKS = [cast("friendly", [56, 67], 0, gun=False), cast("friendly", [54.6, 66.2], 40, "argue", gun=False),
               cast("friendly", [60, 58], -30, path=[[60, 58], [57.6, 64.4]], speed=1.2,
                    then={"anim": "point", "heading": 100}, gun=False),
               cast("friendly", [TOWER[0], TOWER[1]], 0, "aim", z=TOWER[2])]
ATTACK_ACTORS = [{"team": "enemy", "pos": [30, 130], "heading": 180, "count": 6, "spread": [6, 3], "move_to": [36, 92]},
                 {"team": "friendly", "pos": [44, 66], "heading": 0, "count": 3, "spread": [5, 0]}]
ATTACK_VEHICLES = [{"kind": "tank", "path": [[52, 280, 0], [50, 150, 0]], "speed": 7.0},
                   {"kind": "tank", "path": [[20, 300, 0], [22, 160, 0]], "speed": 7.0},
                   {"kind": "attack_helicopter", "path": [[-120, 240, 45], [60, 90, 32], [220, -120, 36]],
                    "speed": 36.0, "armed": False}]

STORIES["prologue"] = {"map": "border_outpost", "shots": [
    title("OPERATION SHADOW", "The Last Morning of Peace", 4.0),
    # 01 - Thirty-two years of silence (old war, black-and-white)
    shot([-40, 72, 8], [-22, 76, 6], [0, 112, 1], [6, 116, 1], narr(
        "Thirty-two years ago, the northern border was a battlefield. The Kareth Republic and the Varn "
        "Directorate fought a war that neither side could afford to win."), duration=9, grade=FLASHBACK,
        actors=[{"team": "friendly", "pos": [-16, 96], "heading": 0, "count": 5, "spread": [8, 1]},
                {"team": "enemy", "pos": [-18, 132], "heading": 180, "count": 5, "spread": [9, 2]}],
        events=[explosion(1.0, [-6, 110, 0.5], 0.2), explosion(3.5, [10, 118, 0.5], 0.2),
                explosion(6.0, [-14, 104, 0.5], 0.2)],
        caption=["THE NORTHERN BORDER", "THIRTY-TWO YEARS AGO"]),
    shot([0, 58, 3.2], [0, 63, 2.6], [0, 72, 1.6], [0, 74, 1.4], narr(
        "Eventually, both governments signed a ceasefire treaty. The guns fell silent. The borders remained "
        "unchanged. And for thirty-two years, there was peace.",
        "But a ceasefire does not always mean an end to war. Sometimes, it only means one side is waiting."),
        duration=10, grade=dict(FLASHBACK, saturation=0.5)),
    # 02 - Two countries
    {"type": "region", "view_from": [0.5, 0.45, 1.15], "view_to": [0.55, 0.72, 2.2], "duration": 10,
     "lines": narr("To the south lies the Kareth Republic. A small democracy, with its capital at Aldmere. Its army "
                   "is small, poorly tested, and has never fought a war.",
                   "To the north stands the Varn Directorate. A powerful military state, with its capital at Vorsk. "
                   "For eleven years it has been ruled by its security services, under one man: Director-General "
                   "Kasimir Drevan.",
                   "Varn wants control of the northern region. Kareth stands directly in its way."),
     "units": [unit([0.3, 0.8], 9.0), unit([0.42, 0.83], 9.5), unit([0.52, 0.81], 10.0), unit([0.6, 0.85], 10.5),
               unit([0.7, 0.8], 11.0), unit([0.8, 0.79], 11.5)],
     "caption": ["KARETH  AND  VARN", "PRESENT DAY"]},
    # 03 - The man who never hurries
    shot([0.9, 2.4, 2.2], [0.9, 0.9, 1.75], [0.9, -1.4, 1.3], [0.9, -1.4, 1.62], [
        line("drevan", "Thirty-two years. We have waited long enough."),
        line("kade", "Our forces are positioned. The northern formations are ready. Give me the order, and Kareth "
                     "will fall.")], set="bunker", cast=[DREVAN_TABLE, KADE_TABLE, OSTROVA_SIDE, GUARD_L, GUARD_R],
        duration=8, caption=["VORSK COMMAND BUNKER", "22:40, THE NIGHT BEFORE THE INVASION"]),
    shot([4.6, 1.8, 2.0], [4.3, 1.5, 1.95], [1.2, -1.0, 1.3], [1.4, -1.1, 1.35], [
        line("ostrova", "Kareth has never attacked us. There is no justification for an invasion."),
        line("drevan", "Generals, history does not reward the patient. It rewards those who understand when "
                       "patience must end.")], set="bunker",
        cast=[DREVAN_TABLE, KADE_TABLE, dict(OSTROVA_SIDE, anim="argue"), GUARD_L, GUARD_R], duration=8),
    # 04 - The exercises (night, staging area north of the border)
    shot([-26, 102, 13], [-20, 110, 12], [0, 130, 0.5], [3, 138, 2], narr(
        "For weeks, Varn had been moving troops, tanks, artillery and aircraft towards the northern border.",
        "Officially, they were military exercises. A routine show of strength.") +
        [line("kade", "I want every formation ready before sunrise. No delays. No mistakes.")] +
        narr("Kareth's leaders saw the movements. They believed it was another political threat. They did not "
             "believe an attack was coming."), duration=14, grade=NIGHT,
        vehicles=[{"kind": "tank", "pos": [-12, 130, 0], "heading": 180}, {"kind": "tank", "pos": [2, 128, 0], "heading": 180},
                  {"kind": "tank", "pos": [14, 132, 0], "heading": 180}, {"kind": "tank", "pos": [-2, 146, 0], "heading": 180},
                  {"kind": "attack_helicopter", "pos": [10, 150, 18], "armed": False, "hover": [10, 150, 18]}],
        cast=[cast("enemy", [-6, 116], 0, path=[[-6, 116], [-6, 142]], speed=1.6),
              cast("enemy", [-3, 124], 90, "salute", gun=False), cast("enemy", [7, 122], -90, "idle"),
              cast("enemy", [8, 136], 180, "kneel_inspect"), cast("enemy", [-14, 140], 90, "idle")],
        events=[{"t": 0.0, "flare": [0, 132, 26]}],
        caption=["NORTHERN VARN STAGING AREA", "23:05"]),
    # 05 - Project TEMPEST
    shot([0.4, 3.4, 2.1], [0.2, 4.4, 2.3], [0, 5.8, 2.2], [0, 5.8, 2.35], [
        line("kade", "Project Tempest is operational. Satellites identify targets. Drones confirm their positions. "
                     "Missiles receive their coordinates.")], set="bunker", cast=SCREENS, duration=7,
        caption=["CLASSIFIED TECHNOLOGY ROOM", "23:18"]),
    shot([0.5, 5.3, 1.7], [0.5, 5.2, 1.7], [0.5, 4.2, 1.62], [0.5, 4.2, 1.62], [
        line("drevan", "Explain it simply.")], set="bunker", cast=SCREENS, duration=3),
    shot([-3.4, 3.0, 2.0], [-3.0, 3.2, 1.95], [-1.8, 4.4, 1.5], [-1.6, 4.5, 1.5], [
        line("kade", "Every weapon knows exactly where to strike. Every target is connected to the same network.")],
        set="bunker", cast=SCREENS, duration=5),
    shot([1.5, 2.0, 1.8], [2.6, 2.7, 1.75], [3.5, 4.2, 1.6], [4.5, 4.8, 1.5], [
        line("stranger", "Radar stations, air defences, command centres, communication towers. Once the network is "
                         "active, they will have nowhere to hide.")], set="bunker", cast=SCREENS, duration=7,
        grade={"exposure": 0.9}),
    shot([-5.0, -3.6, 2.6], [-3.5, -2.0, 2.2], [0.5, 4.5, 1.6], [0.5, 4.8, 2.0], narr(
        "Tempest was not simply another weapon. It was a system designed to make every weapon work together.",
        "In a matter of hours, Kareth's entire defence could be destroyed."), set="bunker", cast=SCREENS, duration=8),
    # 06 - A general's warning
    shot([4.6, -3.4, 2.2], [4.2, -3.0, 2.1], [0.5, 1.0, 1.3], [0.6, 1.2, 1.35], [
        line("ostrova", "You are talking about destroying an entire country's military in hours. What happens "
                        "after that?"),
        line("kade", "We secure the region. We control the border. The operation ends before Kareth understands "
                     "what happened."),
        line("ostrova", "And if another country intervenes? If Tempest fails?")], set="bunker", cast=ARGUE,
        duration=12, caption=["VORSK COMMAND BUNKER", "23:27"]),
    shot([0.2, 1.0, 1.32], [0.2, 0.9, 1.3], [0.0, -0.85, 1.15], [0.0, -0.85, 1.15], [
        line("drevan", "Then we adapt.")], set="bunker", cast=ARGUE, duration=3),
    shot([2.1, 1.3, 1.72], [2.15, 1.45, 1.72], [2.2, 2.9, 1.6], [2.2, 2.9, 1.6], [
        line("ostrova", "You cannot control a war once you start it.")], set="bunker", cast=ARGUE, duration=3.5),
    shot([0.2, 1.0, 1.32], [0.2, 0.85, 1.3], [0.0, -0.85, 1.15], [0.0, -0.85, 1.15], [
        line("drevan", "I am not asking you to control it, General. I am asking you to obey.")], set="bunker",
        cast=ARGUE, duration=4.5),
    # 07 - The man who was supposed to be dead
    shot([-1.4, 1.75, 2.3], [-1.45, 1.7, 2.2], [-1.5, 1.6, 0.77], [-1.5, 1.6, 0.77], [
        line("crane", "I found another connection. The satellite movements match the old intelligence reports."),
        line("wren", "Elias, you have been following this for two years. The investigation was closed.")],
        set="apartment", cast=[cast("man", [-1.4, 0.95], 0, "write")], duration=8,
        caption=["ELIAS CRANE'S APARTMENT, ALDMERE", "23:46"]),
    shot([-1.1, 2.2, 1.3], [-1.15, 2.1, 1.3], [-1.4, 0.95, 1.15], [-1.4, 0.95, 1.15], [
        line("crane", "Because someone wanted it closed."),
        line("wren", "Glass Harbour was a disaster. Harrow was reported killed. You were blamed. Venn dismissed you.")],
        set="apartment", cast=[cast("man", [-1.4, 0.95], 0, "sit_talk")], duration=7),
    shot([2.6, -1.8, 1.9], [2.2, -1.4, 1.8], [-1.4, 1.3, 0.9], [-1.4, 1.2, 1.0], [
        line("crane", "We lost the operation before it even began. Someone knew our movements."),
        line("wren", "You think there was a leak?"),
        line("crane", "I don't think, Isa. I know we were betrayed.")], set="apartment",
        cast=[cast("man", [-1.4, 0.95], 0, "sit_talk")], duration=9),
    # 08 - Operation Glass Harbour (flashback, rainy night)
    shot([-44, -4, 2.0], [-38, 12, 2.0], [-34, 4, 1.5], [-30, 22, 1.5], narr(
        "Two years earlier, Crane had led an intelligence operation inside Varn. Its mission was to uncover a "
        "secret military programme.",
        "It was called Operation Glass Harbour.",
        "The operation failed. Intelligence officer Colonel Desmond Harrow was reported killed. Crane was accused "
        "of compromising the mission, and dismissed by Deputy Director Alda Venn.") +
        [line("crane", "We were betrayed from inside.")], duration=16, rain=0.9,
        grade=dict(FLASHBACK, exposure=0.55, saturation=0.15),
        actors=[{"team": "friendly", "pos": [-42, 0], "heading": 0, "count": 3, "spread": [3, 1]},
                {"team": "enemy", "pos": [-34, 30], "heading": 180, "count": 4, "spread": [4, 1]}],
        cast=[cast("man", [-40, -2], 0, path=[[-40, -2], [-36, 14]], speed=1.4),
              cast(GREY_COAT, [-30, 16], 30, path=[[-30, 16], [-24, 26]], speed=1.1, dark=True)],
        events=[explosion(2.0, [-30, 24, 0.5], 0.15), {"t": 2.2, "smoke": [-30, 22, 0.5]},
                explosion(7.0, [-40, 26, 0.5], 0.2)],
        caption=["OPERATION GLASS HARBOUR", "TWO YEARS EARLIER"]),
    # 09 - Nobody is listening
    shot([-3.3, -2.6, 1.9], [-2.6, -2.2, 1.8], [0.2, 0.8, 1.4], [0.3, 1.0, 1.5], [
        line("crane", "Varn is preparing something. Their movements are not exercises. They are preparing to invade."),
        line("venn", "You are no longer part of this service, Major.")], set="office",
        cast=[cast("man", [0.3, -0.9], 0, "point"), cast("woman", [0.5, 2.2], 180, "argue"),
              cast("woman", [0.8, -0.6], 0, "sit")], duration=9,
        caption=["REPUBLIC INTELLIGENCE, ALDMERE", "00:12"]),
    shot([0.6, 0.9, 1.65], [0.6, 0.8, 1.65], [0.3, -0.9, 1.6], [0.3, -0.9, 1.6], [
        line("crane", "Tempest is real. I have evidence connecting the military movements to a targeting network.")],
        set="office", cast=[cast("man", [0.3, -0.9], 0, "argue"), cast("woman", [0.5, 2.2], 180, "stand")], duration=6),
    shot([0.2, 0.6, 1.65], [0.25, 0.7, 1.65], [0.5, 2.2, 1.6], [0.5, 2.2, 1.6], [
        line("venn", "You have theories. Not evidence that can justify an international crisis.")], set="office",
        cast=[cast("man", [0.3, -0.9], 0, "stand"), cast("woman", [0.5, 2.2], 180, "argue",
                                                           actions=[{"t": 3.5, "heading": 0}])], duration=5),
    shot([-3.0, -2.4, 1.8], [-2.4, -2.0, 1.75], [0.3, -0.9, 1.4], [0.4, 0.4, 1.4], [
        line("crane", "When the missiles start falling, it will be too late.")] +
        narr("Crane was getting closer to the truth. But nobody in power was willing to listen."), set="office",
        cast=[cast("man", [0.3, -0.9], 0, "argue"), cast("woman", [0.5, 2.2], 0, "stand"),
              cast("woman", [0.8, -0.6], 0, "sit")], duration=9),
    # 10 - The invasion order
    shot([1.7, 1.0, 1.6], [1.55, 0.75, 1.58], [0.9, -1.4, 1.3], [0.9, -1.4, 1.32], [
        line("drevan", "The ceasefire protected us for thirty-two years. Tonight, it becomes irrelevant.")],
        set="bunker", cast=ORDER, duration=6, caption=["VORSK COMMAND BUNKER", "01:35"]),
    shot([4.6, -3.4, 2.2], [4.2, -3.0, 2.1], [0.5, 0.6, 1.3], [0.6, 0.8, 1.35], [
        line("kade", "First strike will target Kareth's radar and communication systems. Ground forces will advance "
                     "immediately afterwards."),
        line("ostrova", "You are making a decision that cannot be reversed.")], set="bunker",
        cast=[dict(ORDER[0], anim="stand"), dict(ORDER[1], anim="point")] + ORDER[2:], duration=9),
    shot([0.9, 1.1, 1.72], [0.9, 0.8, 1.7], [0.9, -1.4, 1.62], [0.9, -1.4, 1.62], [
        line("drevan", "The decision has already been made."),
        line("drevan", "General Kade. Begin the operation at 06:14.")], set="bunker",
        cast=[dict(ORDER[0], anim="stand")] + ORDER[1:], duration=7),
    shot([-3.4, 2.0, 2.2], [-3.1, 1.8, 2.1], [-1.0, -0.8, 1.3], [-0.8, -0.9, 1.35], [
        line("kade", "Understood, Director-General.")], set="bunker",
        cast=[dict(ORDER[0], anim="stand")] + ORDER[1:], duration=3),
    shot([0, 1.5, 2.0], [0, 4.4, 2.3], [0, 5.8, 2.0], [0, 5.8, 2.35], narr(
        "The invasion had a time. A plan. And a name. Operation Shadow."), set="bunker", cast=ORDER, duration=6),
    # 11 - The boy in uniform
    shot([30, 40, 10], [46, 56, 3.5], [60, 64, 2], [56, 67, 1.6], narr(
        "Forty kilometres from Varn's northern command line, a small Kareth outpost prepared for another ordinary "
        "morning.",
        "Private Tomas Halden was nineteen. He had never seen combat. Neither had most of the soldiers stationed "
        "there."), duration=11, grade=SUNRISE, cast=OUTPOST, caption=["OUTPOST RIDGEBACK, KARETH NORTHERN BORDER", "04:52"]),
    shot([55.2, 68.3, 1.72], [55.3, 68.2, 1.72], [56, 67, 1.6], [55.4, 66.8, 1.6], [
        line("kell", "Still thinking about home, Halden?"),
        line("halden", "Just wondering when they will let us go back."),
        line("kell", "Hopefully before the food gets worse.")], duration=7, grade=SUNRISE, cast=OUTPOST_TALK),
    # 12 - The last quiet minutes
    shot([50.5, 59.0, 1.75], [51.5, 60.0, 1.75], [59, 60, 1.5], [57.2, 64.0, 1.5], [
        line("marek", "Halden. Kell. Check your equipment. Stay alert."),
        line("kell", "Sergeant, nothing has happened here in thirty-two years."),
        line("marek", "And I intend to keep it that way. Do your job.")], duration=10, grade=SUNRISE, cast=MAREK_WALKS,
        caption=["OUTPOST RIDGEBACK", "05:31"]),
    shot([56.6, 65.6, 1.72], [56.5, 65.5, 1.72], [56, 67, 1.6], [57.6, 64.4, 1.6], [
        line("halden", "Sergeant, do you think they will actually attack?"),
        line("marek", "I think you should stop worrying about things you cannot control.")], duration=6,
        grade=SUNRISE, cast=[OUTPOST_TALK[0], OUTPOST_TALK[1], cast("friendly", [57.6, 64.4], 100, "stand", gun=False),
                            OUTPOST_TALK[3]]),
    shot([62.75, 58.85, 5.85], [62.7, 59.0, 5.85], [61.7, 62.6, 5.35], [61.7, 62.8, 5.35], [
        line("voss", "Movement on the northern ridge.")], duration=3.5, grade=SUNRISE, cast=OUTPOST_TALK),
    # 13 - Something is wrong (long lens on the hills)
    shot([62.5, 63.0, 18.0], [62.5, 63.0, 18.0], [50, 232, 2], [49, 224, 2], [
        line("voss", "I have movement. Multiple vehicles. Can't identify the formation."),
        line("marek", "Are they inside the border?"),
        line("voss", "Not yet. But they're getting closer.")], duration=10, fov=14, grade=SUNRISE,
        vehicles=[{"kind": "tank", "path": [[40, 320, 0], [44, 230, 0]], "speed": 6.0},
                  {"kind": "tank", "path": [[60, 340, 0], [58, 240, 0]], "speed": 6.0},
                  {"kind": "tank", "path": [[24, 330, 0], [28, 236, 0]], "speed": 6.0}],
        caption=["OUTPOST RIDGEBACK", "05:58"]),
    shot([53.5, 64.5, 1.8], [53.8, 64.2, 1.8], [56, 66.6, 1.55], [56.4, 66.4, 1.55], [
        line("kell", "Probably another exercise."),
        line("voss", "Exercises don't move like that."),
        line("halden", "Sergeant?"),
        line("marek", "All stations, maintain alert. Nobody leaves their position.")], duration=9, grade=SUNRISE,
        cast=[OUTPOST_TALK[0], dict(OUTPOST_TALK[1], anim="stand"), cast("friendly", [58.6, 62.4], 60, "point", gun=False),
              OUTPOST_TALK[3]]),
    # 14 - The final warning (the clock)
    shot([4.6, -3.4, 2.2], [4.3, -3.1, 2.1], [0.0, 1.5, 1.3], [0.2, 1.6, 1.35], [
        line("kade", "All formations are in position. Tempest is connected."),
        line("ostrova", "Last chance to stop this.")], set="bunker", cast=FINAL, duration=7,
        caption=["VORSK COMMAND BUNKER", "06:12"], events=[{"t": 0.0, "clock": "06:12"}]),
    shot([0.2, 1.0, 1.32], [0.2, 0.9, 1.3], [0.0, -0.85, 1.15], [0.0, -0.85, 1.15], [
        line("drevan", "There will be no second chance.")], set="bunker", cast=FINAL, duration=3.5),
    shot([-4.2, -1.8, 1.55], [-4.5, -2.0, 1.5], [-5.5, -2.9, 1.1], [-5.5, -2.9, 1.1], [
        line("stranger", "Targeting network confirmed. All systems are ready.")], set="bunker", cast=FINAL,
        duration=4.5, grade={"exposure": 0.85}),
    shot([0.2, 1.0, 1.32], [0.2, 0.8, 1.3], [0.0, -0.85, 1.15], [0.0, -0.85, 1.15], [
        line("drevan", "Proceed.")], set="bunker", cast=FINAL, duration=2.5),
    shot([6.6, -4.3, 2.5], [6.6, -4.6, 2.5], [6.6, -5.55, 2.5], [6.6, -5.55, 2.5],
         narr("At 06:14, thirty-two years of peace came to an end."), set="bunker", cast=FINAL, duration=5, fov=30,
         events=[{"t": 0.0, "clock": "06:13"}, {"t": 2.0, "clock": "06:14"}]),
    # 15 - 06:14
    shot([40, 42, 8], [41, 43, 8], [60, 64, 2], [60, 64, 2], narr(
        "The first missiles struck before the warning sirens could finish their first cycle."), duration=4.5,
        grade=SUNRISE, cast=OUTPOST_TALK,
        events=[{"t": 0.2, "sound": "alarm_loop", "volume": 0.6}, explosion(1.2, [66, 68, 1.0], 0.6, [66, 68, 0.3, 1.6]),
                explosion(2.4, [48, 74, 0.5], 0.4)], caption=["OUTPOST RIDGEBACK", "06:14"]),
    shot([62.75, 58.85, 5.85], [62.8, 58.95, 5.9], [61.7, 62.6, 5.35], [61.7, 62.8, 5.35], [
        line("voss", "Incoming! Take cover!")], duration=2.5, grade=SUNRISE,
        cast=[cast("friendly", [TOWER[0], TOWER[1]], 0, "fire", z=TOWER[2])],
        events=[explosion(0.6, [58, 78, 0.5], 0.5)]),
    shot([52, 54, 1.7], [50, 52, 1.7], [57, 61, 1.5], [52, 57, 1.5], [
        line("marek", "Contact front! Enemy armour! Everyone into cover!")], duration=4, grade=SUNRISE,
        cast=[cast("friendly", [58, 62], -140, "point", path=[[58, 62], [53, 57]], speed=3.0, move="run",
                   then={"anim": "point", "heading": 20})],
        events=[explosion(1.0, [62, 70, 0.5], 0.5)]),
    shot([53, 63, 1.6], [53.2, 63.4, 1.6], [56, 66.5, 1.5], [55.5, 66, 1.5], [
        line("kell", "Tomas! Move!"),
        line("halden", "What is happening?")], duration=4.5, grade=SUNRISE,
        cast=[cast("friendly", [56, 67], 0, "scared", gun=False),
              cast("friendly", [54.6, 66.2], 220, path=[[54.6, 66.2], [52, 62]], speed=3.2, move="run")],
        events=[explosion(0.5, [54, 74, 0.5], 0.6)]),
    shot([20, 50, 12], [24, 56, 14], [40, 110, 3], [44, 100, 3], narr(
        "Tempest had found its targets. Radar stations, communication centres and military positions across "
        "northern Kareth were being destroyed."), duration=9, grade=SUNRISE,
        actors=ATTACK_ACTORS, vehicles=ATTACK_VEHICLES,
        events=[explosion(0.8, [40, 80, 0.5], 0.3), explosion(2.5, [20, 72, 0.5], 0.3, [20, 72, 0.3, 1.4]),
                explosion(4.5, [55, 90, 0.5], 0.3), explosion(6.5, [30, 66, 0.5], 0.4)]),
    # 16 - Operation Shadow
    shot([55.5, 60.6, 1.25], [55.4, 60.8, 1.2], [57, 62.6, 1.0], [56.6, 63.2, 1.0], [
        line("kell", "Tomas! Get up! We have to move!"),
        line("marek", "Hold this position! Do not let them through!")], duration=6, grade=SUNRISE,
        cast=[cast("friendly", [57, 62.2], 20, "kneel", gun=False), cast("friendly", [58.2, 62.8], -40, "kneel"),
              cast("friendly", [54.5, 63.5], 0, "fire")],
        events=[explosion(1.0, [60, 76, 0.5], 0.5), explosion(3.5, [50, 80, 0.5], 0.4)],
        caption=["OUTPOST RIDGEBACK", "06:16"]),
    shot([62.75, 58.85, 5.85], [62.8, 58.95, 5.9], [61.7, 62.6, 5.35], [61.7, 62.8, 5.35], [
        line("voss", "More armour coming! We can't hold them!")], duration=3.5, grade=SUNRISE,
        cast=[cast("friendly", [TOWER[0], TOWER[1]], 0, "fire", z=TOWER[2])],
        events=[explosion(0.8, [64, 82, 0.5], 0.5)]),
    shot([54.9, 65.3, 1.45], [55.0, 65.1, 1.4], [57, 62.2, 0.8], [57, 62.2, 0.8], [
        line("halden", "Sergeant! What do we do?")], duration=3, grade=SUNRISE,
        cast=[cast("friendly", [57, 62.2], 20, "kneel", gun=False)]),
    shot([52.8, 62.4, 1.7], [52.7, 62.3, 1.7], [54.5, 63.5, 1.55], [54.5, 63.5, 1.55], [
        line("marek", "We fight! That's what we do!")], duration=3, grade=SUNRISE,
        cast=[cast("friendly", [54.5, 63.5], 160, "fire")], events=[explosion(1.5, [48, 76, 0.5], 0.5)]),
    shot([50, 52, 6], [44, 46, 10], [56, 80, 2], [56, 100, 2], narr(
        "Kareth had spent thirty-two years believing the war was over. Its soldiers had never fought a battle. Its "
        "defences were falling. And the enemy was already at the gates.",
        "For Private Tomas Halden, this was supposed to be another morning on border duty.",
        "It became the first day of a war that would change everything."), duration=16, grade=SUNRISE,
        actors=ATTACK_ACTORS, vehicles=ATTACK_VEHICLES,
        events=[explosion(1.0, [52, 76, 0.5], 0.4), {"t": 1.2, "smoke": [54, 70, 0.5]},
                explosion(5.0, [40, 84, 0.5], 0.3), explosion(9.0, [62, 88, 0.5], 0.3),
                explosion(12.0, [46, 72, 0.5], 0.4)]),
    title("OPERATION SHADOW", "DAY ONE  -  OUTPOST RIDGEBACK", 4.0),
]}

# =========================================================================================== MISSION 1
STORIES["m01_first_light"] = {"shots": [
    title("MISSION 1:  FIRST LIGHT", "06:00  -  FOURTEEN MINUTES EARLIER", 4.0),
    shot([-15, -31, 1.8], [-15.6, -31.6, 1.75], [-17, -33.5, 1.55], [-17, -33.5, 1.55], [
        line("marek", "Voss saw movement on the northern ridge. Halden, you're with me. We walk the north fence and "
                      "we report what we see.")], duration=6,
        cast=[cast("friendly", [-17, -33.5], 50, "point", gun=False), cast("friendly", [-19, -34.5], -60, "stand", gun=False)],
        caption=["OUTPOST RIDGEBACK", "DAY 1 - 06:00"]),
]}

STORIES["m01_first_light_end"] = {"shots": [
    shot([-2.4, 46.8, 1.3], [-2.6, 46.5, 1.25], [-4, 45.2, 1.0], [-4, 45.2, 0.9], [
        line("halden", "He's not moving."),
        line("marek", "Halden, look at me. We have to move."),
        line("halden", "We can't leave him."),
        line("marek", "We cannot save everyone. Get up.")], duration=9,
        cast=[cast("friendly", [-4, 44], 90, "death", frame=-1), cast("friendly", [-4, 45.2], 180, "kneel_inspect"),
              cast("friendly", [-1, 46], 0, "aim"), cast("friendly", [-6.5, 46.5], -120, "argue"),
              cast("friendly", [-8, 48], 20, "aim")],
        events=[{"t": 0.2, "smoke": [-6, 42, 0.5]}, explosion(3.0, [6, 60, 0.5], 0.25, [6, 60, 0.3, 1.2])],
        caption=["OUTPOST RIDGEBACK", "06:25"]),
    shot([0, -44, 2.2], [0, -82, 2.2], [0, -60, 1.4], [0, -100, 1.4], [
        line("marek", "Fall back to Kesh Ridge!"),
        line("kell", "First day, and they already destroyed our post."),
        line("halden", "Where are we going?"),
        line("marek", "Somewhere we can still fight.")] + narr("The invasion had only just begun."), duration=12,
        cast=[cast("friendly", [0, -50], 180, path=[[0, -50], [0, -110]], speed=1.1, move="injured_walk"),
              cast("friendly", [1.4, -48], 180, path=[[1.4, -48], [1.4, -112]], speed=1.6),
              cast("friendly", [-1.4, -47], 180, path=[[-1.4, -47], [-1.4, -108]], speed=1.0, move="injured_walk"),
              cast("friendly", [2.5, -46], 0, "aim", path=[[2.5, -46], [2.5, -60]], speed=0.9,
                   then={"anim": "aim", "heading": 0})],
        events=[explosion(2.0, [8, -20, 0.5], 0.2), explosion(6.0, [-10, -10, 0.5], 0.2)],
        caption=["SOUTH GATE", "06:40"]),
]}

# =========================================================================================== MISSION 2
TRENCH = [cast("friendly", [-6, 0.2], 0, "point"), cast("friendly", [-4, -0.3], 20, "kneel"),
          cast("friendly", [-2.8, 0.1], -60, "argue"), cast("friendly", [0, 0.5], 0, "aim"),
          cast("friendly", [-8, -0.2], 40, "kneel_inspect")]
STORIES["m02_line_breaks"] = {"shots": [
    title("MISSION 2:  THE LINE BREAKS", "Pvt. Tomas Halden  -  Kesh Ridge", 4.0),
    shot([-14, -6, 3.0], [-10, -5, 2.6], [-4, 2, 1.0], [-3, 6, 1.4], [
        line("marek", "This road is the only safe evacuation route."),
        line("halden", "How many civilians?"),
        line("marek", "Thousands."),
        line("kell", "Then I suppose we're staying.")], duration=9, cast=TRENCH,
        caption=["KESH RIDGE", "DAY 2 - 09:20"]),
    shot([-30, -27.2, 1.65], [-30.2, -27.4, 1.65], [-30, -29, 1.6], [-30, -29, 1.6], [
        line("bastion", "Hold Kesh Ridge until the evacuation is complete."),
        line("marek", "Understood."),
        line("voss", "They are already moving through the valley."),
        line("marek", "Then we make sure they don't reach the road.")], duration=8,
        cast=[cast("friendly", [-30, -29], 0, "phone"), cast("friendly", [-28.6, -28.5], -60),
              cast("friendly", [-31.6, -27.8], 120)], caption=["COMMAND TRENCH", "09:35"]),
]}
STORIES["m02_line_breaks_end"] = {"shots": [
    shot([12, -64, 2.0], [-6, -66, 2.0], [2, -70, 1.2], [0, -74, 1.2], [
        line("civilian", "Please! My daughter is still inside!"),
        line("halden", "Keep moving! The road is clear!"),
        line("kell", "Come on, sir. Don't stop here.")] + narr("For the soldiers at Kesh Ridge, every minute mattered."),
        duration=10, cast=[cast("man", [-10, -60], 150, path=[[-10, -60], [6, -78]], speed=2.6, move="run"),
                           cast("woman", [-12, -58], 150, path=[[-12, -58], [4, -79]], speed=2.4, move="run"),
                           cast("man", [2, -69], 90, "death", frame=-1), cast("friendly", [2, -67.6], 180, "kneel_inspect"),
                           cast("friendly", [4, -66], -150, "point")],
        caption=["EVACUATION ROAD", "11:00"]),
    shot([-10, -4, 2.2], [-6, -6, 2.0], [-4, 1, 1.4], [-2, 3, 1.4], [
        line("voss", "They're through the eastern trench!"),
        line("marek", "The evacuation is complete. Fall back!"),
        line("halden", "We're abandoning the ridge?"),
        line("marek", "We're saving the people we came here to protect.")], duration=9,
        cast=[cast("friendly", [-6, 0], 180, "point"), cast("friendly", [-4, 0.4], 0, "aim"),
              cast("friendly", [-3, 0], 180, path=[[-3, 0], [-3, -20]], speed=1.0, move="injured_walk"),
              cast("friendly", [0, 0.5], 0, "aim")],
        events=[explosion(1.0, [6, 20, 0.5], 0.3), explosion(4.0, [-12, 16, 0.5], 0.3)],
        caption=["KESH RIDGE", "12:15"]),
]}

# =========================================================================================== MISSION 3
STORIES["m03_ashfall"] = {"shots": [
    title("MISSION 3:  ASHFALL", "Pvt. Tomas Halden  -  Veyra", 4.0),
    shot([-33, -34, 2.0], [-33, -24, 2.0], [-29.5, -18, 1.5], [-29.5, -8, 1.5], [
        line("kell", "Remember when you said you wanted to see the country?"),
        line("halden", "Not like this."),
        line("marek", "Stay focused. We're not clear yet.")], duration=8,
        cast=[cast("friendly", [-30, -30], 0, path=[[-30, -30], [-30, -16]], speed=1.3),
              cast("friendly", [-28.8, -31], 0, path=[[-28.8, -31], [-28.8, -17]], speed=1.3),
              cast("friendly", [-29.5, -25], 0, path=[[-29.5, -25], [-29.5, -11]], speed=1.3),
              cast("friendly", [-27, -12], 0, "aim")],
        events=[{"t": 0.1, "fire": [-26, -16, 0.3, 1.2]}, {"t": 0.1, "smoke": [-34, -10, 0.5]}],
        caption=["VEYRA", "DAY 3 - 15:10"]),
    shot([-28.2, -12.6, 1.0], [-28.3, -12.8, 0.95], [-29.6, -13.8, 0.6], [-29.6, -13.8, 0.5], [
        line("halden", "Jonah! Jonah, look at me!"),
        line("kell", "That wasn't part of the plan."),
        line("marek", "Get him behind cover!"),
        line("halden", "He's bleeding badly!"),
        line("marek", "Then move faster!")], duration=9,
        cast=[cast("friendly", [-30, -14], 0, "death", frame=-1), cast("friendly", [-29.2, -13.5], 100, "kneel"),
              cast("friendly", [-31.5, -12], -30, "point"), cast("enemy", [-20, -2], 140, "aim")],
        events=[{"t": 0.3, "sound": "shot_enemy"}, {"t": 0.6, "sound": "shot_enemy"}],
        caption=["RESIDENTIAL STREET", "15:25"]),
    shot([-32.6, -20.9, 1.1], [-32.6, -21.1, 1.05], [-32.6, -22, 0.8], [-32.6, -22, 0.8], [
        line("halden", "I'm not leaving you."),
        line("kell", "Good. I was getting tired of walking."),
        line("marek", "The field hospital is two streets away. Get him there.")], duration=7,
        cast=[cast("friendly", [-32, -22], 90, "kneel"), cast("friendly", [-33.2, -22], -90, "kneel"),
              cast("friendly", [-31, -20.5], 150, "argue"), cast("friendly", [-30, -24], 180, "aim")],
        caption=["ALLEYWAY", "15:35"]),
]}
STORIES["m03_ashfall_end"] = {"shots": [
    shot([42, 48.5, 1.7], [43, 50, 1.65], [44, 52, 1.55], [44, 52, 1.55], [
        line("halden", "Will he survive?"),
        line("marek", "The doctors are doing everything they can."),
        line("halden", "I should have protected him."),
        line("marek", "You brought him here. Don't forget that.")] +
        narr("That evening, Halden learned that surviving a battle was not the same as winning."), duration=12,
        cast=[cast("friendly", [44, 52], 20), cast("friendly", [45.5, 52.5], -30),
              cast("friendly", [44, 54], 0, path=[[44, 54], [44, 61]], speed=0.8, move="injured_walk")],
        caption=["VEYRA FIELD HOSPITAL", "16:30"]),
]}

# =========================================================================================== MISSION 4
STORIES["m04_no_way_back"] = {"shots": [
    title("MISSION 4:  NO WAY BACK", "Pvt. Tomas Halden  -  Tamsin River", 4.0),
    shot([0, 4.2, 2.6], [0.6, 0.0, 2.2], [0, 1, 0.9], [0.9, -1.4, 1.5], [
        line("bastion", "Varn armour is moving towards Tamsin."),
        line("marek", "If they cross, they reach the interior."),
        line("doran", "Then we make sure they don't cross.")], set="bunker_kareth", duration=8,
        cast=[cast("friendly", [0.9, -1.4], 0), cast("friendly", [5.5, -4.5], 120), cast("friendly", [-1.6, -0.9], 0, "point"),
              cast("friendly", [2.6, 0.3], -90)],
        caption=["KARETH FIELD HEADQUARTERS", "DAY 5 - 21:00"]),
    shot([-206, -8, 0.6], [-162, -8, 0.6], [-200, 0, -0.6], [-156, 0, -0.6], [
        line("halden", "How many soldiers are on that bridge?"),
        line("voss", "Enough."),
        line("marek", "Stay quiet. We're close.")], duration=9, grade={"exposure": 3.6, "lift": 0.06},
        vehicles=[{"kind": "player_boat", "path": [[-205, 0, W], [-150, 0, W]], "speed": 5.0}],
        cast=[cast("friendly", [0.6, -0.6], 180, "sit", ride=0, z=-0.45), cast("friendly", [-0.55, -0.7], 180, "sit", ride=0, z=-0.45),
              cast("friendly", [0, 1.8], 0, "aim", ride=0, z=-0.1), cast("friendly", [0, -2.4], 0, "kneel_inspect", ride=0, z=-0.1)],
        caption=["TAMSIN RIVER", "23:10"]),
]}
STORIES["m04_no_way_back_end"] = {"shots": [
    shot([160, -40, 22], [150, -10, 30], [200, 0, -1], [200, 0, -2], [
        line("marek", "Bastion, this is Marek. The Tamsin bridge is down."),
        line("doran", "Goodbye, Tamsin.")] + narr("The road was closed. But the war was far from over."), duration=10,
        grade={"exposure": 3.4, "lift": 0.05},
        vehicles=[{"kind": "transport_helicopter", "path": [[214, 197, 12], [180, 80, 30], [120, -80, 45]], "speed": 16.0}],
        caption=["TAMSIN RIVER", "00:02"]),
]}

# =========================================================================================== MISSION 5
STORIES["m05_dead_drop"] = {"shots": [
    title("MISSION 5:  DEAD DROP", "Elias Crane  -  Port Calder", 4.0),
    shot([2.6, -1.8, 1.9], [2.3, -1.5, 1.8], [-1.4, 1.3, 0.9], [-1.4, 1.2, 1.0], [
        line("wren", "You shouldn't go to Port Calder."),
        line("crane", "Someone wants me to see something.")], set="apartment",
        cast=[cast("man", [-1.4, 0.95], 0, "sit")], duration=6, caption=["ALDMERE", "DAY 9 - 20:40"]),
    shot([-1.1, 2.2, 1.3], [-1.15, 2.1, 1.3], [-1.4, 0.95, 1.15], [-1.4, 0.95, 1.15], [
        line("wren", "Someone wanted you dead two years ago."),
        line("crane", "Then perhaps I should find out who.")], set="apartment",
        cast=[cast("man", [-1.4, 0.95], 0, "sit")], duration=6),
    shot([-60, 30, 12], [-40, 18, 9], [-10, -40, 4], [-10, -46, 6], [], duration=5,
        caption=["PORT CALDER HARBOUR", "23:15"]),
]}
STORIES["m05_dead_drop_end"] = {"shots": [
    shot([60, -170, 3], [10, -190, 4], [20, -170, -1], [-40, -198, -1], [
        line("brandt", "They'll come after us."),
        line("crane", "They already have."),
        line("wren", "Elias, you need to hear this. The shipments were sent inland."),
        line("crane", "Where?"),
        line("wren", "Saint-Aurel. And the broker who moved them lives at Lake Ostra. Mira Sol.")], duration=13,
        vehicles=[{"kind": "player_boat", "path": [[40, -165, W], [-80, -200, W]], "speed": 9.0}],
        cast=[cast("man", [0.6, -0.6], 180, "sit", ride=0, z=-0.45), cast("man", [-0.5, -2.0], 180, "scared", ride=0, z=-0.1)],
        caption=["PORT CALDER", "00:25"]),
]}

# =========================================================================================== MISSION 6
STORIES["m06_the_broker"] = {"shots": [
    title("MISSION 6:  THE BROKER", "Elias Crane  -  Lake Ostra", 4.0),
    shot([120, -150, 40], [160, -90, 30], [200, 150, 6], [200, 150, 4], [
        line("wren", "Elias, Mira's records match the Port Calder shipments."),
        line("crane", "Then she knows where they went."),
        line("wren", "She also knows who you are. Be careful.")], duration=9,
        caption=["LAKE OSTRA", "DAY 12 - 19:10"]),
    shot([204, 62, 1.8], [203, 70, 1.8], [200, 90, 1.5], [200, 110, 2], [], duration=5,
        cast=[cast("man", [200, 66], 0, path=[[200, 66], [200, 82]], speed=1.3)]),
]}
STORIES["m06_the_broker_end"] = {"shots": [
    shot([-372, -84, 1.8], [-374, -88, 1.8], [-380, -92, 1.5], [-382, -96, 1.5], [
        line("mira", "Saint-Aurel is where everything comes together."),
        line("crane", "Then that's where I'm going."),
        line("mira", "You won't find Harrow there."),
        line("crane", "I don't need to find him yet. I need to find Tempest.")], duration=11,
        cast=[cast("man", [-379, -92], 200, "stand"), cast("woman", [-381, -92.5], 160, "argue")],
        caption=["LAKE OSTRA FERRY", "20:40"]),
]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("m0*.json"):
        old.unlink()
    for name, story in STORIES.items():
        story = dict(story)
        story["lines"] = [l for s in story["shots"] for l in s.get("lines", [])]     # for the voice generator
        (OUT / f"{name}.json").write_text(json.dumps(story, indent=1), encoding="utf-8")
        print(f"{name}: {len(story['shots'])} shots, {len(story['lines'])} lines")


if __name__ == "__main__":
    main()
