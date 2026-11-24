"""Orthographic front / side / rear (+ 3/4) renders of the helmet on an upright
head:  python render_helmet.py rider.blend out_prefix"""
import math
import sys

import bpy
from mathutils import Vector

blend, prefix = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
arm = bpy.data.objects["Rider"]
arm.data.pose_position = "REST"                 # upright, facing +Y
for coll in bpy.data.collections:
    if coll.name == "BikeReference":
        coll.hide_render = True
sc.render.engine = "CYCLES"
sc.cycles.samples = 32
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = 640
sc.world = sc.world or bpy.data.worlds.new("W")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.80, 0.80, 0.80, 1)
bg.inputs[1].default_value = 0.8
for name, rot, energy in (("key", (50, 0, 35), 3.2), ("rim", (60, 0, 200), 2.0)):
    l = bpy.data.lights.new(name, "SUN")
    l.energy = energy
    o = bpy.data.objects.new(name, l)
    o.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(o)
cam = bpy.data.cameras.new("cam")
co = bpy.data.objects.new("cam", cam)
sc.collection.objects.link(co)
sc.camera = co
cam.type = "ORTHO"
cam.ortho_scale = 0.46
c = Vector((0, 0.03, 1.66))
for name, off in (("front", (0, 1, 0)), ("side", (1, 0, 0)), ("rear", (0, -1, 0)), ("threeq", (0.8, 0.8, 0.35))):
    co.location = c + Vector(off).normalized() * 2.0
    co.rotation_euler = (c - co.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
