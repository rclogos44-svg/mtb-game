"""Render quick previews of a .blend:  python preview.py file.blend out_prefix [frame]"""
import math
import sys

import bpy
from mathutils import Vector

blend, prefix = sys.argv[-2], sys.argv[-1]
frame = None
if sys.argv[-3].endswith(".blend") is False and sys.argv[-3].isdigit():
    frame = int(sys.argv[-3])
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
for ob in sc.objects:
    if ob.name.startswith("Chain") and ob.type == "MESH" and ob.name != "Chainstay":
        ob.hide_render = True
if frame is not None:
    sc.frame_set(frame)
sc.render.engine = "CYCLES"
sc.cycles.samples = 24
sc.cycles.use_denoising = False
sc.render.resolution_x, sc.render.resolution_y = 1100, 820
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.92, 0.92, 0.92, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.9

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 3.0
so = bpy.data.objects.new("sun", sun)
so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
sc.collection.objects.link(so)

cam = bpy.data.cameras.new("cam")
co = bpy.data.objects.new("cam", cam)
sc.collection.objects.link(co)
sc.camera = co


def shoot(loc, target, lens, name, ortho=None):
    co.location = loc
    d = Vector(target) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    else:
        cam.type = "PERSP"
        cam.lens = lens
    sc.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)


shoot((4.0, 0.15, 0.55), (0, 0.15, 0.55), 50, "side", ortho=1.55)
shoot((2.4, -1.8, 1.4), (0, 0.1, 0.6), 50, "threequarter")
shoot((-1.3, 0.25, 0.65), (0, 0.0, 0.55), 50, "detail", ortho=0.75)
shoot((4.0, 0.1, 0.95), (0, 0.1, 0.95), 50, "full", ortho=2.1)
shoot((-2.6, 2.6, 1.6), (0, 0.1, 0.85), 50, "front")

import mathutils
arm = bpy.data.objects.get("Rider")
if arm is not None:
    hb = arm.pose.bones["head"]
    hc = arm.matrix_world @ (hb.matrix @ mathutils.Vector((0, 0.09, 0)))
    shoot(hc + mathutils.Vector((0.45, 0.55, 0.12)), hc, 50, "helmet", ortho=0.42)
    shoot(hc + mathutils.Vector((0.7, 0.0, 0.05)), hc, 50, "helmetside", ortho=0.42)
