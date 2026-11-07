"""Campaign / mission selection, briefing, loading, mission complete and mission failed screens."""
from __future__ import annotations

from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode

from ui import style
from ui.style import Screen


def _fmt_time(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class CampaignScreen(Screen):
    """All 16 missions grouped by act, with their status. Click a playable one to open its briefing."""

    def __init__(self, game, on_pick, on_back):
        super().__init__(game, dim=0.9)
        self.on_pick = on_pick
        self.title = style.text(self.root, "CAMPAIGN", (-1.55, 0.83), 0.08)
        self.progress = style.text(self.root, "", (1.55, 0.84), 0.04, style.DIM, TextNode.A_right)
        self.info = style.text(self.root, "", (-1.55, -0.72), 0.036, style.DIM, wrap=60)
        self.items = []
        style.button(self.root, "BACK", (-1.55, -0.86), on_back, width=0.4)

    def refresh(self):
        for node in self.items:
            node.destroy()
        self.items = []
        game = self.game
        campaign = game.campaign
        save = game.save.progress
        done = len(save.completed)
        self.progress.setText(f"CAMPAIGN PROGRESS  {done} / {len(campaign.missions)}")
        columns = {"act1": (-1.55, 0), "act2": (-1.55, 1), "act3": (0.12, 0), "act4": (0.12, 1)}
        for act in campaign.acts:
            x, block = columns.get(act["id"], (-1.55, 0))
            z0 = 0.66 - block * 0.66
            hdr = style.text(self.root, act["title"], (x, z0), 0.038, style.ACCENT)
            self.items.append(hdr)
            missions = [m for m in campaign.missions if m.act == act["id"]]
            for i, m in enumerate(missions):
                z = z0 - 0.1 - i * 0.11
                unlocked = game.save.is_unlocked(m.id)
                if m.id in save.completed:
                    tag, color = "COMPLETED", style.OK
                elif not m.playable:
                    tag, color = "IN DEVELOPMENT", style.DIM
                elif unlocked:
                    tag, color = "AVAILABLE", style.ACCENT
                else:
                    tag, color = "LOCKED", style.DIM
                enabled = m.playable and unlocked
                b = style.button(self.root, f"{m.number:02d}  {m.title.upper()}", (x, z), self._clicked,
                                 width=0.95, scale=0.042, enabled=True, extra_args=[m, enabled, tag])
                if not enabled:
                    b["text_fg"] = (0.5, 0.5, 0.47, 1)
                t = style.text(self.root, tag, (x + 0.92, z + 0.003), 0.03, color, TextNode.A_right)
                self.items += [b, t]
        self.info.setText("Select a mission. Missions marked IN DEVELOPMENT are planned for later phases "
                          "and cannot be played yet.")

    def _clicked(self, mission, enabled, tag):
        char = self.game.campaign.characters.get(mission.character)
        who = char.name if char else mission.character
        if enabled:
            self.on_pick(mission.id)
        elif tag == "IN DEVELOPMENT":
            self.info.setText(f"{mission.number:02d} {mission.title} - {mission.location} ({who}). "
                              f"{mission.summary}  This mission is not built yet.")
        else:
            self.info.setText(f"{mission.title} is locked. Complete the previous mission first.")


class BriefingScreen(Screen):
    def __init__(self, game, on_begin, on_back):
        super().__init__(game, dim=0.92)
        r = self.root
        self.act = style.text(r, "", (-1.4, 0.8), 0.038, style.ACCENT)
        self.title = style.text(r, "", (-1.4, 0.66), 0.1)
        self.meta = style.text(r, "", (-1.4, 0.55), 0.036, style.DIM)
        self.body = style.text(r, "", (-1.4, 0.4), 0.04, style.TEXT, wrap=42)
        self.objectives = style.text(r, "", (0.35, 0.4), 0.038, style.TEXT, wrap=30)
        self.begin = style.button(r, "BEGIN MISSION", (-1.4, -0.8), on_begin, width=0.6)
        style.button(r, "BACK", (-0.7, -0.8), on_back, width=0.4)

    def set_mission(self, info, data, character):
        self.act.setText(self.game.campaign.act_title(info.act))
        self.title.setText(f"{info.number:02d}  {info.title.upper()}")
        self.meta.setText(f"{info.location}   |   {data.get('date', '')}   |   {character.name if character else ''}")
        self.body.setText("\n\n".join(data.get("briefing", [])))
        self.objectives.setText(
            "STORY OBJECTIVE\n" + data.get("story_objective", "") + "\n\n"
            "MISSION\n" + data.get("gameplay_objective", "") + "\n\n"
            "OPERATOR\n" + (f"{character.name} - {character.role}" if character else ""))


class LoadingScreen(Screen):
    TIPS = [
        "Aim down sights (right mouse button) for much better accuracy.",
        "Health recovers if you avoid damage for a few seconds.",
        "Enemies hear gunfire. A sniper shot carries further than a pistol.",
        "Crouch behind sandbags and vehicles - enemies do the same.",
        "Red arcs around the crosshair show where damage is coming from.",
    ]

    def __init__(self, game):
        super().__init__(game, dim=1.0)
        self.title = style.text(self.root, "", (0, 0.1), 0.08, style.TEXT, TextNode.A_center)
        self.sub = style.text(self.root, "LOADING", (0, -0.02), 0.04, style.ACCENT, TextNode.A_center)
        self.tip = style.text(self.root, "", (0, -0.7), 0.035, style.DIM, TextNode.A_center, wrap=50)
        self._i = 0

    def set_text(self, title):
        self.title.setText(title.upper())
        self.tip.setText("TIP: " + self.TIPS[self._i % len(self.TIPS)])
        self._i += 1

    def show(self):
        self.root.show()                    # no fade: it must be visible on the very next frame
        self.root.set_color_scale(1, 1, 1, 1)


class MissionEndScreen(Screen):
    RANK_COLORS = {"GOLD": (1.0, 0.82, 0.3, 1), "SILVER": (0.82, 0.85, 0.9, 1), "BRONZE": (0.85, 0.55, 0.32, 1)}

    def __init__(self, game, on_continue, on_menu):
        super().__init__(game, dim=0.85)
        r = self.root
        self.head = style.text(r, "MISSION COMPLETE", (0, 0.62), 0.11, style.ACCENT, TextNode.A_center)
        self.title = style.text(r, "", (0, 0.48), 0.05, style.TEXT, TextNode.A_center)
        self.stats = style.text(r, "", (-0.45, 0.28), 0.045, style.TEXT)
        self.values = style.text(r, "", (0.45, 0.28), 0.045, style.ACCENT, TextNode.A_right)
        self.rank = style.text(r, "", (0, 0.36), 0.06, style.ACCENT, TextNode.A_center)
        self.next = style.text(r, "", (0, -0.48), 0.038, style.DIM, TextNode.A_center, wrap=50)
        style.button(r, "CONTINUE", (-0.32, -0.66), on_continue, width=0.5, align="center")
        style.button(r, "MAIN MENU", (0.32, -0.66), on_menu, width=0.5, align="center")

    def set_results(self, title, stats, next_text):
        self.title.setText(title.upper())
        names = ["TIME", "KILLS", "HEADSHOTS", "ACCURACY", "RETRIES"]
        values = [_fmt_time(stats["time"]), str(stats["kills"]), str(stats["headshots"]),
                  f"{stats['accuracy'] * 100:.0f}%", str(stats["deaths"])]
        if stats.get("takedowns"):
            names.append("TAKEDOWNS")
            values.append(str(stats["takedowns"]))
        if stats.get("stealth") is not None:
            names.append("STEALTH")
            values.append("UNDETECTED" if stats["stealth"] else "ALARM RAISED")
        if stats.get("intel_total"):
            names.append("INTEL")
            values.append(f"{stats['intel']} / {stats['intel_total']}")
        self.stats.setText("\n".join(names))
        self.values.setText("\n".join(values))
        rank = stats.get("rank")
        self.rank.setText(f"RANK:  {rank}" if rank else "")
        self.rank["fg"] = self.RANK_COLORS.get(rank, style.ACCENT)
        self.next.setText(next_text)


class MissionFailedScreen(Screen):
    def __init__(self, game, on_checkpoint, on_restart, on_menu):
        super().__init__(game, dim=0.82)
        r = self.root
        style.text(r, "MISSION FAILED", (0, 0.4), 0.11, style.DANGER, TextNode.A_center)
        self.reason = style.text(r, "", (0, 0.26), 0.045, style.TEXT, TextNode.A_center)
        style.text(r, "Tip: take cover and let your health recover before pushing forward.", (0, 0.17), 0.034,
                   style.DIM, TextNode.A_center, may_change=False)
        self.checkpoint = style.button(r, "RETRY FROM CHECKPOINT", (0, -0.05), on_checkpoint, width=0.8, align="center")
        style.button(r, "RESTART MISSION", (0, -0.17), on_restart, width=0.8, align="center")
        style.button(r, "MAIN MENU", (0, -0.29), on_menu, width=0.8, align="center")

    def set_reason(self, reason, has_checkpoint):
        self.reason.setText(reason)
        self.checkpoint["state"] = DGG.NORMAL if has_checkpoint else DGG.DISABLED
