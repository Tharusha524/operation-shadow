"""In-engine cutscenes: smooth camera moves with letterbox bars and subtitles. Space/Enter/Esc skips."""
from __future__ import annotations

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Point3, TextNode


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp(a, b, t):
    return Point3(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


class CinematicPlayer:
    BAR = 0.16

    def __init__(self, game, spec, on_done, speaker_name):
        self.game = game
        self.shots = spec.get("shots", [])
        self.lines = sorted(spec.get("lines", []), key=lambda l: l["t"])
        self.duration = sum(s["duration"] for s in self.shots) or 0.1
        self.on_done = on_done
        self.speaker_name = speaker_name
        self.t = 0.0
        self.done = False
        self._line_index = 0
        self._line_timer = 0.0
        self._hold = 0.0                  # extra time added because a voice line ran long
        self.root = game.render2d.attach_new_node("cinematic")
        DirectFrame(parent=self.root, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, 1 - self.BAR * 2, 1))
        DirectFrame(parent=self.root, frameColor=(0, 0, 0, 1), frameSize=(-1, 1, -1, -1 + self.BAR * 2))
        self.subtitle = OnscreenText(parent=game.aspect2d, text="", pos=(0, -0.88), scale=0.045,
                                     fg=(0.95, 0.93, 0.86, 1), shadow=(0, 0, 0, 1), mayChange=True, wordwrap=36)
        self.skip_hint = OnscreenText(parent=game.a2dTopRight, text="[SPACE] skip", pos=(-0.08, -0.12), scale=0.032,
                                      fg=(0.7, 0.7, 0.65, 0.8), align=TextNode.A_right, mayChange=False)
        game.player.camera.detach_for_cinematic()
        self.update(0.0)

    def skip(self):
        self.finish()

    def update(self, dt):
        if self.done:
            return
        voice = getattr(self.game, "voice", None)
        pending = self._line_index < len(self.lines)
        speaking = voice is not None and voice.speaking()
        if speaking and pending and self.t >= self.lines[self._line_index]["t"] + self._hold:
            self._hold += dt                                  # wait for the current speaker to finish
        elif speaking and not pending and self.t >= self.duration + self._hold - 0.3:
            self._hold += dt
        else:
            self.t += dt
        if self.t >= self.duration + self._hold and not speaking:
            self.finish()
            return
        # Camera.
        acc = 0.0
        view_t = min(self.t, self.duration - 1e-3)
        for shot in self.shots:
            if view_t <= acc + shot["duration"]:
                k = _smooth((view_t - acc) / shot["duration"])
                cam = self.game.camera
                cam.set_pos(_lerp(shot["from"], shot["to"], k))
                cam.look_at(_lerp(shot["look_from"], shot["look_to"], k))
                break
            acc += shot["duration"]
        # Subtitles.
        while self._line_index < len(self.lines) and self.t >= self.lines[self._line_index]["t"] + self._hold \
                and not (voice is not None and voice.speaking()):
            line = self.lines[self._line_index]
            name = self.speaker_name(line["speaker"])
            self.subtitle.setText(f"{name}:  {line['text']}" if name else line["text"])
            length = voice.play(line["speaker"], line["text"]) if voice is not None else 0.0
            self._line_timer = max(line.get("seconds", 4.0), length + 0.3)
            self._line_index += 1
        if self._line_timer > 0:
            self._line_timer -= dt
            if self._line_timer <= 0:
                self.subtitle.setText("")

    def finish(self):
        if self.done:
            return
        self.done = True
        voice = getattr(self.game, "voice", None)
        if voice is not None:
            voice.stop()
        self.root.remove_node()
        self.subtitle.destroy()
        self.skip_hint.destroy()
        self.game.player.camera.reattach()
        self.on_done()
