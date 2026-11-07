"""Convert the Mixamo downloads into the game's soldier models.

Run:  .venv\\Scripts\\python.exe tools\\convert_soldiers.py
Needs portable Blender in D:\\tools\\blender and the downloads in D:\\op_shadow_assets\\mixamo.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"D:\tools\blender\blender.exe")
SOURCE = Path(r"D:\op_shadow_assets\mixamo")
# output model -> (Mixamo character, triangle budget)
CHARACTERS = {
    "soldier_enemy": ("Ch15_nonPBR.fbx", 12000),     # Varn Directorate soldiers
    "soldier_friend": ("Swat.fbx", 12000),           # the player's squad and allies
    "actor_officer": ("Ch33_nonPBR.fbx", 16000),     # suit: Director-General Drevan, officials
    "actor_man": ("Ch01_nonPBR.fbx", 16000),         # plain clothes: Elias Crane, civilians
    "actor_woman": ("Ch22_nonPBR.fbx", 16000),       # plain clothes: Isa Wren, civilians
}


def main():
    out_dir = ROOT / "assets" / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    for name, (fbx, triangles) in CHARACTERS.items():
        if only and name not in only:
            continue
        glb = out_dir / f"{name}.glb"
        print(f"== {fbx} -> {glb.name}", flush=True)
        subprocess.run([str(BLENDER), "-b", "--factory-startup", "-P", str(ROOT / "tools" / "convert_mixamo.py"),
                        "--", str(SOURCE / fbx), str(SOURCE), str(glb), str(triangles)], check=True)
        gltf2bam = Path(sys.executable).with_name("gltf2bam.exe")
        subprocess.run([str(gltf2bam), str(glb), str(out_dir / f"{name}.bam")], check=True)
        print(f"   wrote {name}.bam", flush=True)


if __name__ == "__main__":
    main()
