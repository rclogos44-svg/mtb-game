"""Render the helmet alone (transparent background) from a direction given in
head space:  python overlay_render.py rider.blend out.png ox oy oz [ortho]"""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
blend, outdir = args[0], args[1]
views = [tuple(float(x) for x in v.split(",")) for v in args[2:]]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
bpy.data.objects["Rider"].data.pose_position = "REST"
for ob in sc.objects:
    if ob.type == "MESH" and ob.name != "Helmet":
        ob.hide_render = True
sc.render.engine = "CYCLES"
sc.cycles.samples = int(__import__("os").environ.get("SAMPLES", "24"))
sc.cycles.use_denoising = False
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = int(__import__("os").environ.get("RES", "800"))
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.9, 0.9, 0.9, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
l = bpy.data.lights.new("key", "SUN"); l.energy = 3.0
lo = bpy.data.objects.new("key", l); lo.rotation_euler = (math.radians(40), 0, math.radians(-30)); sc.collection.objects.link(lo)
cam = bpy.data.cameras.new("cam"); cam.type = "PERSP"; cam.lens = 85
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co
c = Vector((0, 0.04, 1.67))
for k, v in enumerate(views):
    off = Vector(v[:3])
    co.location = c + off.normalized() * 1.6
    co.rotation_euler = (c - co.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{outdir}/view_{k}.png"
    bpy.ops.render.render(write_still=True)
