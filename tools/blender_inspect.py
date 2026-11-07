"""Run inside Blender:  blender -b -P tools/blender_inspect.py -- <fbx> <preview.png>

Prints the meshes, triangle counts, textures and skeleton of a Mixamo character and renders a preview.
"""
import math
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
fbx, out_png = args[0], args[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)

tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        n = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        tris += n
        mats = [m.name for m in ob.data.materials if m]
        print(f"MESH {ob.name}: {n} triangles, materials {mats}")
    elif ob.type == "ARMATURE":
        bones = [b.name for b in ob.data.bones]
        print(f"ARMATURE {ob.name}: {len(bones)} bones, scale {tuple(round(v, 3) for v in ob.scale)}; "
              f"first: {bones[:4]}")
print(f"TOTAL TRIANGLES {tris}")
for img in bpy.data.images:
    print(f"IMAGE {img.name}: {img.size[0]}x{img.size[1]}")

# Height of the character (from the bounding boxes, in metres after import).
zs = []
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        for c in ob.bound_box:
            zs.append((ob.matrix_world @ __import__("mathutils").Vector(c)).z)
print(f"HEIGHT {max(zs) - min(zs):.2f} m")

# Preview render: front and side.
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x, scene.render.resolution_y = 640, 640
h = max(zs) - min(zs)
cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0.0, -3.6 * h / 1.8, h * 0.55)
cam.rotation_euler = (math.radians(90), 0, 0)
cam_data.lens = 40
scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print("PREVIEW", out_png)
