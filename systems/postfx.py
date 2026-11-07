"""Cinematic post-processing: HDR, bloom, filmic tone mapping, colour grading, vignette and grain.

How it works
  1. The 3D scene (and the first-person weapon) is rendered into a floating-point (HDR) texture,
     so very bright things - sun, fire, muzzle flashes - keep values above 1.0.
  2. Bright parts are extracted at 1/4 resolution and blurred -> bloom (soft glow).
  3. A final pass adds the bloom, applies exposure + a filmic (ACES) curve, colour grading
     (contrast, saturation, tint, shadow/highlight balance), a vignette and light film grain.

Each map can tune its look with a "grading" block in its atmosphere (see data/maps/*.json).
Graphics quality "low" disables the whole pipeline for weak PCs.
"""
from __future__ import annotations

import logging

from direct.filter.FilterManager import FilterManager
from panda3d.core import FrameBufferProperties, SamplerState, Shader, Texture

log = logging.getLogger(__name__)

VERT = """
#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_Vertex.xz * 0.5 + 0.5;
}
"""

BRIGHT = """
#version 130
uniform sampler2D src;
uniform float threshold;
in vec2 uv;
out vec4 o;
void main() {
    // 4 taps = cheap downsample + bright pass
    vec2 t = 1.0 / vec2(textureSize(src, 0));
    vec3 c = (texture(src, uv + t * vec2(-1, -1)).rgb + texture(src, uv + t * vec2(1, -1)).rgb +
              texture(src, uv + t * vec2(-1, 1)).rgb + texture(src, uv + t * vec2(1, 1)).rgb) * 0.25;
    if (any(isnan(c)) || any(isinf(c))) c = vec3(0.0);          // never let a bad pixel spread
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float k = max(l - threshold, 0.0) / max(l, 1e-4);
    o = vec4(c * k, 1.0);
}
"""

BLUR = """
#version 130
uniform sampler2D src;
uniform vec2 direction;
in vec2 uv;
out vec4 o;
void main() {
    vec2 t = direction / vec2(textureSize(src, 0));
    vec3 c = texture(src, uv).rgb * 0.2270;
    c += (texture(src, uv + t * 1.3846).rgb + texture(src, uv - t * 1.3846).rgb) * 0.3162;
    c += (texture(src, uv + t * 3.2308).rgb + texture(src, uv - t * 3.2308).rgb) * 0.0703;
    o = vec4(c, 1.0);
}
"""

COMPOSITE = """
#version 130
uniform sampler2D scene;
uniform sampler2D bloom;
uniform sampler2D soft;    // blurred copy of the scene (depth of field)
uniform sampler2D depth;
uniform vec4 dof;          // focus distance, sharp range, strength, far clip
uniform float near_clip;
uniform vec4 grade;       // exposure, contrast, saturation, bloom strength
uniform vec4 tint;        // rgb tint, vignette strength
uniform vec4 balance;     // shadow tint rgb, grain strength
uniform float lift;       // raises the darkest tones so shadows keep detail
uniform float time;
in vec2 uv;
out vec4 o;

vec3 aces(vec3 x) {       // Narkowicz 2015 ACES fit
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
    // Scene colours are authored in display (gamma) space: go to linear light, tone-map, come back.
    vec3 s = texture(scene, uv).rgb;
    if (any(isnan(s)) || any(isinf(s))) s = vec3(0.0);
    if (dof.z > 0.0) {                                               // cinematic focus: blur what's far from focus
        float zn = texture(depth, uv).r * 2.0 - 1.0;
        float dist = 2.0 * near_clip * dof.w / (dof.w + near_clip - zn * (dof.w - near_clip));
        float coc = smoothstep(0.0, dof.y, abs(dist - dof.x) - dof.y * 0.25) * dof.z;
        vec3 soft_c = texture(soft, uv).rgb;
        if (!(any(isnan(soft_c)) || any(isinf(soft_c)))) s = mix(s, soft_c, clamp(coc, 0.0, 1.0));
    }
    vec3 b = texture(bloom, uv).rgb;
    if (any(isnan(b)) || any(isinf(b))) b = vec3(0.0);
    vec3 c = s + b * grade.w;
    c = pow(max(c, vec3(0.0)), vec3(2.2)) * grade.x;
    c = pow(aces(c), vec3(1.0 / 2.2));
    c = c + lift * (1.0 - c);
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = mix(vec3(l), c, grade.z);                                   // saturation
    c = (c - 0.5) * grade.y + 0.5;                                  // contrast
    c *= tint.rgb;                                                  // overall tint
    c = mix(c * balance.rgb, c, smoothstep(0.0, 0.6, l));           // cool/warm shadows
    vec2 d = uv - 0.5;
    c *= 1.0 - tint.w * smoothstep(0.15, 0.75, dot(d, d) * 2.2);    // vignette
    c += (hash(uv * 1000.0 + time) - 0.5) * balance.w;              // film grain
    o = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""

DEFAULT_GRADING = {
    "exposure": 1.15, "contrast": 1.06, "saturation": 1.12, "bloom": 0.45, "bloom_threshold": 0.9,
    "tint": [1.0, 1.0, 1.0], "shadow_tint": [0.90, 0.95, 1.08], "vignette": 0.4, "grain": 0.02, "lift": 0.015,
}


class PostFX:
    def __init__(self, base, enabled=True, multisamples=0):
        self.base = base
        self.multisamples = multisamples
        self.enabled = False
        self.scene_buffer = None
        self._time = 0.0
        self.final = None
        if not enabled:
            return
        try:
            self._build()
            self.enabled = True
        except Exception as exc:                     # never let post-processing stop the game
            log.error("Post-processing disabled: %s", exc)
            self.enabled = False

    def _hdr_props(self, msaa=0):
        fb = FrameBufferProperties()
        fb.set_float_color(True)
        fb.set_rgba_bits(16, 16, 16, 0)
        if msaa:
            fb.set_multisamples(msaa)
        return fb

    def _build(self):
        base = self.base
        self.manager = FilterManager(base.win, base.cam)
        self.scene_tex = Texture("scene_hdr")
        self.depth_tex = Texture("scene_depth")
        self.final = self.manager.renderSceneInto(colortex=self.scene_tex, depthtex=self.depth_tex,
                                                  fbprops=self._hdr_props(self.multisamples))
        if self.final is None and self.multisamples:
            log.warning("Anti-aliased HDR buffer not supported - using one without anti-aliasing")
            self.final = self.manager.renderSceneInto(colortex=self.scene_tex, depthtex=self.depth_tex,
                                                      fbprops=self._hdr_props())
        if self.final is None:
            raise RuntimeError("could not create the HDR scene buffer")
        self.scene_buffer = self.manager.buffers[-1]
        bright_tex, blur1_tex, blur2_tex = Texture("bloom_bright"), Texture("bloom_h"), Texture("bloom_v")
        bright = self.manager.renderQuadInto(colortex=bright_tex, div=4, fbprops=self._hdr_props())
        blur_h = self.manager.renderQuadInto(colortex=blur1_tex, div=4, fbprops=self._hdr_props())
        blur_v = self.manager.renderQuadInto(colortex=blur2_tex, div=4, fbprops=self._hdr_props())
        for tex in (self.scene_tex, bright_tex, blur1_tex, blur2_tex):
            tex.set_wrap_u(SamplerState.WM_clamp)
            tex.set_wrap_v(SamplerState.WM_clamp)
            tex.set_minfilter(SamplerState.FT_linear)
            tex.set_magfilter(SamplerState.FT_linear)
        bright.set_shader(Shader.make(Shader.SL_GLSL, VERT, BRIGHT))
        bright.set_shader_input("src", self.scene_tex)
        bright.set_shader_input("threshold", 0.85)
        blur_h.set_shader(Shader.make(Shader.SL_GLSL, VERT, BLUR))
        blur_h.set_shader_input("src", bright_tex)
        blur_h.set_shader_input("direction", (1.6, 0.0))
        blur_v.set_shader(Shader.make(Shader.SL_GLSL, VERT, BLUR))
        blur_v.set_shader_input("src", blur1_tex)
        blur_v.set_shader_input("direction", (0.0, 1.6))
        self.bright = bright
        # Depth of field (only switched on during story videos): a blurred quarter-size copy of the scene.
        soft_a, soft_b, soft_c = Texture("dof_down"), Texture("dof_h"), Texture("dof_v")
        down = self.manager.renderQuadInto(colortex=soft_a, div=4, fbprops=self._hdr_props())
        self._dof_buffers = [self.manager.buffers[-1]]
        dof_h = self.manager.renderQuadInto(colortex=soft_b, div=4, fbprops=self._hdr_props())
        self._dof_buffers.append(self.manager.buffers[-1])
        dof_v = self.manager.renderQuadInto(colortex=soft_c, div=4, fbprops=self._hdr_props())
        self._dof_buffers.append(self.manager.buffers[-1])
        for tex in (soft_a, soft_b, soft_c):
            tex.set_wrap_u(SamplerState.WM_clamp)
            tex.set_wrap_v(SamplerState.WM_clamp)
            tex.set_minfilter(SamplerState.FT_linear)
            tex.set_magfilter(SamplerState.FT_linear)
        down.set_shader(Shader.make(Shader.SL_GLSL, VERT, BRIGHT))
        down.set_shader_input("src", self.scene_tex)
        down.set_shader_input("threshold", 0.0)                      # keep everything (plain downsample)
        dof_h.set_shader(Shader.make(Shader.SL_GLSL, VERT, BLUR))
        dof_h.set_shader_input("src", soft_a)
        dof_h.set_shader_input("direction", (2.2, 0.0))
        dof_v.set_shader(Shader.make(Shader.SL_GLSL, VERT, BLUR))
        dof_v.set_shader_input("src", soft_b)
        dof_v.set_shader_input("direction", (0.0, 2.2))
        self._soft_tex = soft_c
        self.final.set_shader(Shader.make(Shader.SL_GLSL, VERT, COMPOSITE))
        self.final.set_shader_input("scene", self.scene_tex)
        self.final.set_shader_input("bloom", blur2_tex)
        self.final.set_shader_input("time", 0.0)
        self.final.set_shader_input("soft", self._soft_tex)
        self.final.set_shader_input("depth", self.depth_tex)
        self.final.set_shader_input("near_clip", float(base.camLens.get_near()))
        self.set_dof(None)
        self.set_grading({})

    def set_dof(self, focus=None, sharp_range=6.0, strength=0.85):
        """Blur everything far from `focus` metres (story videos). None switches it off (no cost)."""
        if self.final is None:
            return
        on = focus is not None
        for buf in getattr(self, "_dof_buffers", []):
            buf.set_active(on)
        far = float(self.base.camLens.get_far())
        self.final.set_shader_input("dof", (float(focus or 0.0), float(sharp_range), strength if on else 0.0, far))

    def set_grading(self, grading):
        """Colour grading of the current map. An active override (night vision, drone camera) wins."""
        self._grading = dict(grading or {})
        self._apply(self._override if getattr(self, "_override", None) is not None else self._grading)

    def set_override(self, grading):
        """Temporary full-screen look (e.g. night vision). None goes back to the map grading."""
        self._override = dict(grading) if grading is not None else None
        self._apply(self._override if self._override is not None else getattr(self, "_grading", {}))

    def _apply(self, grading):
        if not self.enabled and self.final is None:
            return
        if self.final is None:
            return
        g = dict(DEFAULT_GRADING)
        g.update(grading or {})
        self.final.set_shader_input("grade", (g["exposure"], g["contrast"], g["saturation"], g["bloom"]))
        self.final.set_shader_input("tint", (*g["tint"], g["vignette"]))
        self.final.set_shader_input("balance", (*g["shadow_tint"], g["grain"]))
        self.final.set_shader_input("lift", g["lift"])
        self.bright.set_shader_input("threshold", g["bloom_threshold"])

    def update(self, dt):
        if self.enabled:
            self._time = (self._time + dt) % 100.0
            self.final.set_shader_input("time", self._time)
