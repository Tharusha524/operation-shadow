"""Run inside Blender (see tools/convert_soldiers.bat):

    blender -b --factory-startup -P tools/convert_mixamo.py -- <character.fbx> <animations folder> <out.glb> <triangles>

Builds one game-ready soldier: the Mixamo character with fewer triangles and smaller textures, plus all
the animations the game uses (idle, walk, run, fire, reload, crouch, death ...) as named clips.
Horizontal root motion is removed so the game moves the soldiers itself.
"""
import os
import re
import sys

import bpy

PREFIX = re.compile(r"mixamorig\d*:")


def standard(name):
    """Mixamo numbers its skeletons per download (mixamorig7:Hips ...). Use one name for all."""
    return PREFIX.sub("mixamorig:", name)

ANIMATIONS = {                      # clip name -> file (first one found is used)
    "idle": ["Rifle Idle.fbx", "pack/rifle aiming idle.fbx"],
    "aim": ["pack/rifle aiming idle.fbx", "Idle Crouching Aiming.fbx"],
    "walk": ["Rifle Walk (1).fbx", "Rifle Walk.fbx", "pack/walking.fbx"],
    "run": ["Rifle Run.fbx", "pack/rifle run.fbx"],
    "fire": ["Firing Rifle.fbx", "pack/firing rifle.fbx"],
    "reload": ["Reloading.fbx", "pack/reloading.fbx"],
    "crouch_idle": ["Idle Crouching Aiming.fbx"],
    "crouch_walk": ["Rifle Crouch Walk (1).fbx", "Rifle Crouch Walk.fbx"],
    "death": ["Death.fbx"],
    "hit": ["pack/hit reaction.fbx"],
    "walk_back": ["pack/walking backwards.fbx"],
    "strafe_left": ["pack/strafe left.fbx"],
    "strafe_right": ["pack/strafe right.fbx"],
    "throw": ["pack/toss grenade.fbx"],
    # Acting (story videos): talking, deciding, working, fear, wounds.
    "stand": ["Standing Idle.fbx"],
    "argue": ["Standing Arguing.fbx"],
    "point": ["Pointing.fbx"],
    "salute": ["Salute.fbx"],
    "sit": ["Sitting Idle.fbx"],
    "sit_talk": ["Sitting Talking.fbx", "Sitting Talking (1).fbx"],
    "type": ["Typing.fbx"],
    "write": ["Writing.fbx"],
    "phone": ["Talking On Phone.fbx"],
    "scared": ["Scared.fbx"],
    "terrified": ["Terrified.fbx"],
    "kneel": ["Kneeling Down.fbx"],
    "kneel_inspect": ["Kneeling Inspecting.fbx"],
    "injured_walk": ["Injured Walk.fbx", "Injured Walking.fbx"],
}
TEXTURE_SIZE = 1024

args = sys.argv[sys.argv.index("--") + 1:]
char_fbx, anim_dir, out_glb, target_tris = args[0], args[1], args[2], int(args[3])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=char_fbx)
armature = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for bone in armature.data.bones:                       # renaming a bone also renames the mesh weights
    bone.name = standard(bone.name)
for m in meshes:
    for vg in m.vertex_groups:
        vg.name = standard(vg.name)

# --- fewer triangles ---------------------------------------------------------------------------
total = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
ratio = min(1.0, target_tris / max(1, total))
for m in meshes:
    if ratio < 0.98:
        mod = m.modifiers.new("decimate", "DECIMATE")
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.modifier_apply(modifier=mod.name)
after = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
print(f"TRIANGLES {total} -> {after}")

# --- smaller textures ------------------------------------------------------------------------------
for img in bpy.data.images:
    w, h = img.size
    if w > TEXTURE_SIZE or h > TEXTURE_SIZE:
        img.scale(min(w, TEXTURE_SIZE), min(h, TEXTURE_SIZE))
        img.pack()
        print(f"TEXTURE {img.name}: {w}x{h} -> {img.size[0]}x{img.size[1]}")

# --- simple, non-metal materials ----------------------------------------------------------------------
# Mixamo materials come out half "metallic", which the game's renderer draws almost black. Soldiers are
# cloth and matte armour: keep the colour (and normal) textures, drop metal / roughness / specular maps.
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type != "BSDF_PRINCIPLED":
            continue
        for name, value in (("Metallic", 0.0), ("Roughness", 0.8), ("Specular IOR Level", 0.25)):
            sock = node.inputs.get(name)
            if sock is None:
                continue
            for link in list(sock.links):
                mat.node_tree.links.remove(link)
            sock.default_value = value
    # Keep only what the game uses (colour, normal map, alpha); drop the other texture nodes.
    keep = {"Base Color", "Normal", "Alpha"}
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            for sock in node.inputs:
                if sock.name not in keep:
                    for link in list(sock.links):
                        mat.node_tree.links.remove(link)
    changed = True
    while changed:
        changed = False
        for node in list(mat.node_tree.nodes):
            if node.type in ("TEX_IMAGE", "SEPRGB", "SEPARATE_COLOR", "MATH", "INVERT", "MIX_RGB", "MIX",
                             "VALTORGB", "BUMP") and not any(o.links for o in node.outputs):
                mat.node_tree.nodes.remove(node)
                changed = True
    print(f"MATERIAL {mat.name}: matte")

# --- animations ----------------------------------------------------------------------------------------
def strip_root_motion(action):
    """Keep the hips' height (crouching, falling) but drop the walk-forward movement."""
    for fc in action.fcurves:
        if fc.data_path == 'pose.bones["mixamorig:Hips"].location' and fc.array_index in (0, 2):
            first = fc.keyframe_points[0].co[1] if fc.keyframe_points else 0.0
            for kp in fc.keyframe_points:
                kp.co[1] = first
                kp.handle_left[1] = first
                kp.handle_right[1] = first


armature.animation_data_create()
for clip, candidates in ANIMATIONS.items():
    path = next((os.path.join(anim_dir, c) for c in candidates if os.path.isfile(os.path.join(anim_dir, c))), None)
    if path is None:
        print(f"MISSING {clip}")
        continue
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    src = next((o for o in new if o.type == "ARMATURE" and o.animation_data and o.animation_data.action), None)
    if src is None:
        print(f"NO ACTION IN {path}")
    else:
        action = src.animation_data.action
        action.name = clip
        for fc in action.fcurves:
            fc.data_path = standard(fc.data_path)
        for grp in action.groups:
            grp.name = standard(grp.name)
        action.use_fake_user = True
        strip_root_motion(action)
        print(f"CLIP {clip}: {int(action.frame_range[1] - action.frame_range[0])} frames from {os.path.basename(path)}")
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)

# Push every clip onto its own NLA track so the glTF exporter writes them all as separate animations.
for action in [a for a in bpy.data.actions if a.name in ANIMATIONS]:
    track = armature.animation_data.nla_tracks.new()
    track.name = action.name
    track.strips.new(action.name, int(action.frame_range[0]), action)
armature.animation_data.action = None

bpy.ops.export_scene.gltf(
    filepath=out_glb, export_format="GLB", export_animation_mode="NLA_TRACKS", export_image_format="JPEG",
    export_jpeg_quality=85, export_skins=True, export_yup=True, export_apply=False,
    export_force_sampling=True, export_frame_step=1)
print("WROTE", out_glb, os.path.getsize(out_glb))
