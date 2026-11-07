"""Download free CC0 textures and models from Poly Haven and prepare them for the game.

Run from the project folder:
    .venv\\Scripts\\python.exe tools\\fetch_assets.py            (textures + models)
    .venv\\Scripts\\python.exe tools\\fetch_assets.py textures   (textures only)

What it does
  * reads data/asset_sources.json
  * downloads 1K files from Poly Haven's official API into assets/downloads/ (raw files)
  * checks every download really is an image / glTF file of a sane size
  * textures -> assets/textures/<material>.png and <material>_normal.png (colour adjusted)
  * models   -> assets/models/<key>.bam (scaled to metres, base at the origin)
  * writes assets/LICENSES.txt listing every asset and its source (all CC0)
Nothing downloaded is ever executed - files are only read as image/model data.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = "https://api.polyhaven.com"
USER_AGENT = "OperationShadow-asset-tool/1.0 (offline game project)"
MAX_FILE = 60 * 1024 * 1024
DOWNLOADS = ROOT / "assets" / "downloads" / "polyhaven"
TEX_OUT = ROOT / "assets" / "textures"
MODEL_OUT = ROOT / "assets" / "models"
JPEG, PNG = b"\xff\xd8\xff", b"\x89PNG"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def download(url, dest: Path, expect=None):
    """Download url to dest (skips if already present). expect = allowed magic byte prefixes."""
    if not url.startswith("https://dl.polyhaven.org/"):
        raise ValueError(f"refusing to download from unexpected host: {url}")
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError(f"{url} is larger than {MAX_FILE // 1024 // 1024} MB")
    if expect and not any(data.startswith(m) for m in expect):
        raise ValueError(f"{url} is not the expected file type")
    dest.write_bytes(data)
    time.sleep(0.2)                      # be polite to the free service
    return dest


# ---------------------------------------------------------------------------- textures
def fetch_texture(material, spec, lic):
    from environments.materials import array_to_texture
    import numpy as np
    from panda3d.core import Filename, PNMImage, Texture

    asset = spec["polyhaven"]
    files = get_json(f"{API}/files/{asset}")
    folder = DOWNLOADS / asset
    diff = download(files["Diffuse"]["1k"]["jpg"]["url"], folder / f"{asset}_diff_1k.jpg", (JPEG,))
    nor = download(files["nor_gl"]["1k"]["jpg"]["url"], folder / f"{asset}_nor_gl_1k.jpg", (JPEG,))

    def load_rgb(path):
        img = PNMImage()
        if not img.read(Filename.from_os_specific(str(path))):
            raise ValueError(f"cannot read image {path}")
        tex = Texture()
        tex.load(img)
        data = np.frombuffer(bytes(tex.get_ram_image_as("RGB")), np.uint8)
        arr = data.reshape(tex.get_y_size(), tex.get_x_size(), 3)[::-1].astype(np.float32) / 255.0
        return arr

    rgb = load_rgb(diff)
    gray = rgb.mean(axis=-1, keepdims=True)
    rgb = rgb * (1.0 - spec.get("desaturate", 0.0)) + gray * spec.get("desaturate", 0.0)
    rgb *= spec.get("brightness", rgb.mean()) / max(1e-4, float(rgb.mean()))
    TEX_OUT.mkdir(parents=True, exist_ok=True)
    array_to_texture(material, rgb).write(Filename.from_os_specific(str(TEX_OUT / f"{material}.png")))
    array_to_texture(f"{material}_normal", load_rgb(nor)).write(
        Filename.from_os_specific(str(TEX_OUT / f"{material}_normal.png")))
    lic.append(f"texture  {material:12s} <- Poly Haven '{asset}' (CC0)  https://polyhaven.com/a/{asset}")
    print(f"  texture {material}: {asset}")


# ---------------------------------------------------------------------------- models
def simplify_materials(root):
    """Keep only each part's colour (base-colour) photo texture.

    glTF files also carry normal / metal-roughness layers and PBR materials that Panda3D's
    automatic shader cannot use without extra vertex data - they render black. The colour
    texture alone looks right with the game's lighting. sRGB textures are read as plain RGB
    because the whole game works in display colour space.
    """
    from panda3d.core import CullFaceAttrib, MaterialAttrib, Texture, TextureAttrib, TextureStage
    for gnp in root.find_all_matches("**/+GeomNode"):
        node = gnp.node()
        for i in range(node.get_num_geoms()):
            state = node.get_geom_state(i)
            base_tex = base_stage = None
            if state.has_attrib(TextureAttrib):
                attrib = state.get_attrib(TextureAttrib)
                for stage in attrib.get_on_stages():
                    if stage.get_mode() in (TextureStage.M_modulate, TextureStage.M_replace):
                        base_tex, base_stage = attrib.get_on_texture(stage), stage
                        break
            # Single-sided like the rest of the level (double-sided models get striped "shadow acne").
            state = state.remove_attrib(MaterialAttrib).remove_attrib(TextureAttrib).remove_attrib(CullFaceAttrib)
            if base_tex is not None:
                if base_tex.get_format() in (Texture.F_srgb, Texture.F_srgb_alpha):
                    base_tex.set_format(Texture.F_rgba8 if base_tex.get_format() == Texture.F_srgb_alpha
                                        else Texture.F_rgb8)
                # Keep the original stage: it knows which UV channel ("texcoord.0") the model uses.
                state = state.add_attrib(TextureAttrib.make().add_on_stage(base_stage, base_tex))
            node.set_geom_state(i, state)


def orient_weapon(root):
    """Turn a gun so its barrel points along +Y, the top of the gun is at z=0 and it is centred on x=0.

    The muzzle end is found automatically: near the muzzle the gun is thin (just the barrel),
    near the other end it is tall (grip / stock).
    """
    from panda3d.core import GeomVertexReader
    pts = []
    for gnp in root.find_all_matches("**/+GeomNode"):
        for geom in gnp.node().get_geoms():
            reader = GeomVertexReader(geom.get_vertex_data(), "vertex")
            while not reader.is_at_end():
                v = reader.get_data3()
                pts.append((v.x, v.y, v.z))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    long_axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    vals = xs if long_axis == 0 else ys
    lo, hi = min(vals), max(vals)
    span = hi - lo

    def height_near(end):
        zs = [p[2] for p in pts if abs(p[long_axis] - end) < span * 0.12]
        return (max(zs) - min(zs)) if zs else 0.0

    muzzle_at_max = height_near(hi) < height_near(lo)
    # Rotate so the muzzle direction becomes +Y.
    if long_axis == 0:
        root.set_h(90 if muzzle_at_max else -90)        # +X -> +Y  /  -X -> +Y
    else:
        root.set_h(0 if muzzle_at_max else 180)
    root.flatten_strong()
    lo3, hi3 = root.get_tight_bounds()
    root.set_pos(-(lo3.x + hi3.x) / 2, -(lo3.y + hi3.y) / 2, -hi3.z)
    root.flatten_strong()


def fetch_model(key, spec, lic, base):
    from panda3d.core import Filename, NodePath, Point3

    asset = spec["polyhaven"]
    files = get_json(f"{API}/files/{asset}")
    entry = files["gltf"]["1k"]["gltf"]
    folder = DOWNLOADS / asset
    main = download(entry["url"], folder / Path(entry["url"]).name)
    for rel, inc in entry.get("include", {}).items():
        if ".." in rel or rel.startswith(("/", "\\")):
            raise ValueError(f"unsafe path in {asset}: {rel}")
        download(inc["url"], folder / rel)
    model = base.loader.load_model(Filename.from_os_specific(str(main)), noCache=True)
    root = NodePath(key)
    model.reparent_to(root)
    lo, hi = model.get_tight_bounds()
    size = hi - lo
    if "height" in spec:
        scale = spec["height"] / max(1e-6, size.z)
    else:
        scale = spec["length"] / max(1e-6, max(size.x, size.y))
    model.set_scale(scale)
    model.set_pos(-(lo.x + hi.x) / 2 * scale, -(lo.y + hi.y) / 2 * scale, -lo.z * scale)
    root.flatten_strong()
    simplify_materials(root)
    if "length" in spec:
        orient_weapon(root)
    count = 0
    for gnode in root.find_all_matches("**/+GeomNode"):
        for geom in gnode.node().get_geoms():
            for prim in geom.get_primitives():
                count += prim.get_num_faces()
    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    out = MODEL_OUT / f"{key}.bam"
    root.write_bam_file(Filename.from_os_specific(str(out)))
    lo, hi = root.get_tight_bounds()
    lic.append(f"model    {key:14s} <- Poly Haven '{asset}' (CC0)  https://polyhaven.com/a/{asset}")
    print(f"  model {key}: {asset}  {count:,} triangles  size {hi - lo}")


def main():
    want = set(sys.argv[1:]) or {"textures", "models"}
    sources = json.loads((ROOT / "data" / "asset_sources.json").read_text(encoding="utf-8"))
    lic = ["Third-party assets used by OPERATION SHADOW", "All are CC0 (public domain) from Poly Haven.", ""]
    failed = []
    if "textures" in want:
        print("Textures:")
        for material, spec in sources["textures"].items():
            try:
                fetch_texture(material, spec, lic)
            except Exception as exc:
                failed.append(material)
                print(f"  FAILED {material}: {exc}")
    if "models" in want:
        from panda3d.core import loadPrcFileData
        # rawdata = store the textures INSIDE each .bam, so models don't depend on assets/downloads.
        loadPrcFileData("", "window-type none\naudio-library-name null\nbam-texture-mode rawdata")
        import gltf  # noqa: F401  - registers the glTF loader (pip package panda3d-gltf)
        from direct.showbase.ShowBase import ShowBase
        base = ShowBase()
        print("Models:")
        for key, spec in sources["models"].items():
            try:
                fetch_model(key, spec, lic, base)
            except Exception as exc:
                failed.append(key)
                print(f"  FAILED {key}: {exc}")
    old = ROOT / "assets" / "LICENSES.txt"
    keep = []
    if old.exists():
        keep = [l for l in old.read_text(encoding="utf-8").splitlines()
                if l.startswith(("texture", "model")) and l.split()[1] not in {x.split()[1] for x in lic[3:]}]
    (ROOT / "assets" / "LICENSES.txt").write_text("\n".join(lic + keep) + "\n", encoding="utf-8")
    print("Done." + (f"  Failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
