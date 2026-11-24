"""Builds the rider in Blender: skinned body (riding jersey + baggy pants),
full-face helmet with goggles, flat-pedal shoes and gloves, plus a baked
standing-pedalling animation that keeps the feet locked to the pedals and the
hands on the grips. Exports rider.glb.

The animation "Pedal" is exactly one crank revolution (frames 0..48). The game
does not play it on a clock: it seeks it to the bike's real crank angle, so
the feet can never drift off the pedals.

Run with Blender's Python:  python build_rider.py
"""
import json
import math
import os
import sys


import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshkit as mk
from meshkit import Part

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "..", "game", "assets", "geometry.json")))

mk.clear_scene()
col = bpy.context.scene.collection

# ------------------------------------------------------------------ materials
JERSEY = mk.material("Jersey", (0.018, 0.018, 0.020), roughness=0.85)
JERSEY_ACC = mk.material("JerseyAccent", (0.07, 0.07, 0.075), roughness=0.8)
PANTS = mk.material("Pants", (0.115, 0.118, 0.125), roughness=0.95)        # charcoal, clearly not the black jersey
SHOE = mk.material("Shoe", (0.02, 0.02, 0.022), roughness=0.75)
SOLE = mk.material("Sole", (0.32, 0.20, 0.10), roughness=0.85)
GLOVE = mk.material("Glove", (0.03, 0.03, 0.032), roughness=0.8)
GLOVE_ACC = mk.material("GloveAccent", (0.85, 0.32, 0.05), roughness=0.75)
HELMET = mk.material("Helmet", (0.82, 0.82, 0.80), metallic=0.0, roughness=0.25)
HELMET_ACC = mk.material("HelmetAccent", (0.85, 0.30, 0.04), roughness=0.3)
HELMET_DK = mk.material("HelmetDark", (0.02, 0.02, 0.022), roughness=0.5)
LENS = mk.material("Lens", (0.85, 0.45, 0.08), metallic=0.9, roughness=0.08)
STRAP = mk.material("Strap", (0.9, 0.9, 0.9), roughness=0.7)
SKIN = mk.material("Skin", (0.62, 0.43, 0.33), roughness=0.6)

# ================================================================== skeleton (rest A-pose)
# x: rider's right (+), y: forward, z: up. Feet flat on the ground.
J = {
    "pelvis": (0, 0, 0.960), "spine0": (0, 0, 1.080), "chest0": (0, 0, 1.260),
    "neck0": (0, 0.0, 1.450), "head0": (0, 0.01, 1.560), "headT": (0, 0.01, 1.760),
}
for s, n in ((1, "R"), (-1, "L")):
    J["clav" + n] = (0.030 * s, 0.0, 1.420)
    J["shoulder" + n] = (0.180 * s, 0.0, 1.430)
    J["elbow" + n] = (0.397 * s, 0.0, 1.223)
    J["wrist" + n] = (0.585 * s, 0.0, 1.043)
    J["knuck" + n] = (0.657 * s, 0.0, 0.974)
    J["hip" + n] = (0.090 * s, 0.0, 0.930)
    J["knee" + n] = (0.100 * s, 0.0, 0.500)
    J["ankle" + n] = (0.100 * s, 0.0, 0.080)
    J["toe" + n] = (0.100 * s, 0.140, 0.020)

FWD, UP = Vector((0, 1, 0)), Vector((0, 0, 1))
BONES = [  # name, head, tail, parent, roll reference (rest)
    ("root", (0, 0, 0), (0, 0.15, 0), None, UP),
    ("hips", J["pelvis"], J["spine0"], "root", FWD),
    ("spine", J["spine0"], J["chest0"], "hips", FWD),
    ("chest", J["chest0"], J["neck0"], "spine", FWD),
    ("neck", J["neck0"], J["head0"], "chest", FWD),
    ("head", J["head0"], J["headT"], "neck", FWD),
]
for s, n in ((1, "R"), (-1, "L")):
    BONES += [
        ("shoulder." + n, J["clav" + n], J["shoulder" + n], "chest", FWD),
        ("upperarm." + n, J["shoulder" + n], J["elbow" + n], "shoulder." + n, -FWD),
        ("forearm." + n, J["elbow" + n], J["wrist" + n], "upperarm." + n, -FWD),
        ("hand." + n, J["wrist" + n], J["knuck" + n], "forearm." + n, Vector((s, 0, 0.6))),
        ("thigh." + n, J["hip" + n], J["knee" + n], "hips", FWD),
        ("shin." + n, J["knee" + n], J["ankle" + n], "thigh." + n, FWD),
        ("foot." + n, J["ankle" + n], J["toe" + n], "shin." + n, UP),
    ]

arm_data = bpy.data.armatures.new("RiderArmature")
arm_ob = bpy.data.objects.new("Rider", arm_data)
col.objects.link(arm_ob)
bpy.context.view_layer.objects.active = arm_ob
bpy.ops.object.mode_set(mode="EDIT")
for name, h, t, parent, ref in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = Vector(h), Vector(t)
    eb.align_roll(ref)
    if parent:
        eb.parent = arm_data.edit_bones[parent]
    eb.use_connect = False
    eb.use_deform = name != "root"
bpy.ops.object.mode_set(mode="OBJECT")
REST = {b.name: b.matrix_local.copy() for b in arm_data.bones}
PARENT = {name: parent for name, _, _, parent, _ in BONES}

# ================================================================== body (skin modifier)
NODES = [  # name, position, radius (lateral, depth)
    ("pelvis", J["pelvis"], (0.190, 0.150)),
    ("waist", (0, 0.0, 1.08), (0.175, 0.135)),
    ("belly", (0, 0.010, 1.20), (0.185, 0.145)),
    ("chest", (0, 0.005, 1.33), (0.200, 0.150)),
    ("uchest", (0, -0.005, 1.425), (0.185, 0.125)),
    ("neck", (0, 0.005, 1.50), (0.066, 0.066)),
    ("neckT", (0, 0.01, 1.60), (0.060, 0.060)),
]
for s, n in ((1, "R"), (-1, "L")):
    NODES += [
        ("hip" + n, (0.092 * s, 0, 0.900), (0.130, 0.128)),          # relaxed-fit riding pants
        ("thighM" + n, (0.098 * s, 0.0, 0.715), (0.122, 0.120)),
        ("knee" + n, J["knee" + n], (0.104, 0.106)),                 # room for a knee pad
        ("shinM" + n, (0.100 * s, 0.0, 0.300), (0.093, 0.093)),      # straight leg, not tapered
        ("ankle" + n, (0.100 * s, 0.0, 0.125), (0.086, 0.086)),
        ("shoulder" + n, (0.195 * s, 0.0, 1.415), (0.078, 0.078)),
        ("uarmM" + n, ((0.185 + 0.397) / 2 * s, 0, (1.415 + 1.223) / 2), (0.066, 0.066)),
        ("elbow" + n, J["elbow" + n], (0.056, 0.056)),
        ("farmM" + n, ((0.397 + 0.585) / 2 * s, 0, (1.223 + 1.043) / 2), (0.052, 0.052)),
        ("wrist" + n, (0.575 * s, 0, 1.052), (0.040, 0.040)),
    ]
EDGES = [("pelvis", "waist"), ("waist", "belly"), ("belly", "chest"), ("chest", "uchest"),
         ("uchest", "neck"), ("neck", "neckT")]
for n in ("R", "L"):
    EDGES += [("pelvis", "hip" + n), ("hip" + n, "thighM" + n), ("thighM" + n, "knee" + n),
              ("knee" + n, "shinM" + n), ("shinM" + n, "ankle" + n),
              ("uchest", "shoulder" + n), ("shoulder" + n, "uarmM" + n), ("uarmM" + n, "elbow" + n),
              ("elbow" + n, "farmM" + n), ("farmM" + n, "wrist" + n)]
EDGE_BONE = {("pelvis", "waist"): "hips", ("waist", "belly"): "spine", ("belly", "chest"): "spine",
             ("chest", "uchest"): "chest", ("uchest", "neck"): "neck", ("neck", "neckT"): "neck"}
for n in ("R", "L"):
    EDGE_BONE.update({
        ("pelvis", "hip" + n): "hips", ("hip" + n, "thighM" + n): "thigh." + n,
        ("thighM" + n, "knee" + n): "thigh." + n, ("knee" + n, "shinM" + n): "shin." + n,
        ("shinM" + n, "ankle" + n): "shin." + n, ("uchest", "shoulder" + n): "shoulder." + n,
        ("shoulder" + n, "uarmM" + n): "upperarm." + n, ("uarmM" + n, "elbow" + n): "upperarm." + n,
        ("elbow" + n, "farmM" + n): "forearm." + n, ("farmM" + n, "wrist" + n): "forearm." + n})

idx = {n: i for i, (n, _, _) in enumerate(NODES)}
me = bpy.data.meshes.new("BodySkel")
me.from_pydata([p for _, p, _ in NODES], [(idx[a], idx[b]) for a, b in EDGES], [])
body_src = bpy.data.objects.new("BodySrc", me)
col.objects.link(body_src)
sk = body_src.modifiers.new("Skin", "SKIN")
sk.use_smooth_shade = True
sk.branch_smoothing = 0.6
for i, (_, _, r) in enumerate(NODES):
    me.skin_vertices[0].data[i].radius = r
me.skin_vertices[0].data[idx["pelvis"]].use_root = True
sub = body_src.modifiers.new("Sub", "SUBSURF")
sub.levels = 2
dg = bpy.context.evaluated_depsgraph_get()
body_me = bpy.data.meshes.new_from_object(body_src.evaluated_get(dg))
bpy.data.objects.remove(body_src, do_unlink=True)
body_me.name = "Body"
body = bpy.data.objects.new("Body", body_me)
col.objects.link(body)


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length, t


# materials by region + skin weights from the nearest skeleton edge
for m in (JERSEY, PANTS, JERSEY_ACC, SKIN):
    body_me.materials.append(m)
pos = {n: Vector(p) for n, p, _ in NODES}
rad = {n: Vector(r) for n, _, r in NODES}
vgroups = {b[0]: body.vertex_groups.new(name=b[0]) for b in BONES if b[0] != "root"}
LEG_BONES = {"hips", "thigh.R", "thigh.L", "shin.R", "shin.L"}
vert_bone = []
for v in body_me.vertices:
    p = v.co
    scores = []
    for (a, b) in EDGES:
        d, t = seg_dist(p, pos[a], pos[b])
        r = rad[a][0] * (1 - t) + rad[b][0] * t
        scores.append((d - r, EDGE_BONE[(a, b)]))
    best = min(s for s, _ in scores)
    w = {}
    for s, bone in scores:
        k = math.exp(-(s - best) / 0.012)
        if k > 0.02:
            w[bone] = w.get(bone, 0.0) + k
    tot = sum(w.values())
    for bone, k in w.items():
        vgroups[bone].add([v.index], k / tot, "REPLACE")
    vert_bone.append(max(w, key=w.get))
for poly in body_me.polygons:
    bones = [vert_bone[i] for i in poly.vertices]
    leg = sum(b in LEG_BONES for b in bones) > len(bones) / 2
    z = sum(body_me.vertices[i].co.z for i in poly.vertices) / len(bones)
    x = abs(sum(body_me.vertices[i].co.x for i in poly.vertices) / len(bones))
    WAIST_Z = 1.005                    # clean, level waistline (rest pose)
    poly.material_index = 1 if z < WAIST_Z else 0
    if not leg and (1.30 < z < 1.37 and x < 0.2):
        poly.material_index = 2         # chest stripe
    if not leg and x > 0.53:
        poly.material_index = 2         # cuffs
    if not leg and z > 1.50 and x < 0.08:
        poly.material_index = 3         # neck
    poly.use_smooth = True


def rigid_part(part, bone, local_builder):
    """Build a part whose geometry is authored in `bone`'s rest frame, weighted 100% to it."""
    Mr = REST[bone]
    local_builder(part, Mr)
    ob = part.build()
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


# ================================================================== shoes (authored in world rest pose)
def shoe(n, s):
    p = Part("Shoe." + n)
    x0 = 0.100 * s
    def pt(x, y, z):
        return Vector((x0 + x * s, y, z))
    sole = [pt(x, y, z) for z in (0.0, 0.022) for (x, y) in
            ((-0.040, -0.075), (0.040, -0.075), (-0.050, 0.0), (0.050, 0.0), (-0.050, 0.12), (0.052, 0.12),
             (-0.035, 0.19), (0.040, 0.19), (0.0, 0.205))]
    p.hull(sole, SOLE)
    upper = [pt(x, y, z) for (x, y, z) in
             ((-0.040, -0.070, 0.022), (0.040, -0.070, 0.022), (-0.047, 0.12, 0.022), (0.049, 0.12, 0.022),
              (-0.03, 0.188, 0.022), (0.035, 0.188, 0.022), (0.0, 0.200, 0.025),
              (-0.038, -0.065, 0.12), (0.038, -0.065, 0.12), (-0.045, 0.0, 0.135), (0.045, 0.0, 0.135),
              (-0.040, 0.05, 0.10), (0.040, 0.05, 0.10), (-0.035, 0.13, 0.068), (0.040, 0.13, 0.068),
              (-0.02, 0.18, 0.05), (0.025, 0.18, 0.05))]
    p.hull(upper, SHOE)
    # tongue / collar padding
    p.tube(pt(-0.045, -0.01, 0.13), pt(0.045, -0.01, 0.13), 0.014, mat=SHOE, seg=10)
    p.hull([pt(x, y, z) for x in (-0.028, 0.028) for (y, z) in ((0.03, 0.115), (0.10, 0.085), (0.035, 0.14))], SOLE)
    ob = p.build()
    vg = ob.vertex_groups.new(name="foot." + n)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


# ================================================================== gloves (authored in hand-bone frame)
def glove(n, s):
    p = Part("Glove." + n)
    Mr = REST["hand." + n]
    def L(x, y, z):  # bone local: Y along hand, Z back of hand, X across the knuckles
        return Mr @ Vector((x, y, z))
    # palm / back of hand
    p.hull([L(x, y, z) for x in (-0.042, 0.042) for y in (-0.02, 0.075) for z in (-0.012, 0.022)] +
           [L(x, -0.035, z) for x in (-0.030, 0.030) for z in (-0.01, 0.02)], GLOVE)
    # cuff
    p.hull([L(math.cos(a) * 0.040, -0.06 + d, math.sin(a) * 0.032 + 0.005) for a in [k * math.pi / 6 for k in range(12)] for d in (0.0, 0.03)], GLOVE_ACC)
    # four fingers curled round the grip (grip axis is local X at y=0.08, z=-0.03)
    for i, fx in enumerate((-0.03, -0.01, 0.01, 0.03)):
        pts = []
        for k in range(7):
            a = math.radians(90 - k * 38)
            c = Vector((fx * s, 0.082, -0.030))
            pts.append(L(c.x, c.y + math.cos(a) * 0.033, c.z + math.sin(a) * 0.033 + 0.008))
        for a, b in zip(pts, pts[1:]):
            p.tube(a, b, 0.0095, mat=GLOVE, seg=8)
        for q in pts:
            p.sphere(q, 0.0096, GLOVE, seg=8, rings=6)
    # thumb wraps under the grip from the inside
    th0 = L(-0.035 * s, 0.03, -0.01)
    th1 = L(-0.03 * s, 0.07, -0.055)
    th2 = L(-0.015 * s, 0.10, -0.06)
    p.polytube([th0, th1, th2], 0.0105, GLOVE, seg=8)
    ob = p.build()
    vg = ob.vertex_groups.new(name="hand." + n)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


# ================================================================== helmet (authored in head-bone frame)
from helmet import build_helmet

HELMET_STAGE = os.environ.get("HELMET_STAGE", "final")     # "blockout" or "final"


def helmet():
    """Full-face MTB helmet (see art/helmet.py), plus a plain face inside."""
    p = Part("Helmet")
    build_helmet(p, REST["head"], HELMET_STAGE, SKIN, graphics=os.environ.get("HELMET_GRAPHICS", "1") == "1")
    ob = p.build(sharp_angle=math.radians(28))
    vg = ob.vertex_groups.new(name="head")
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


def jersey_hem():
    """The jersey's hem: a slightly proud band round the waist that the shirt
    ends in, so it reads as sitting over the pants."""
    p = Part("JerseyHem")
    secs = []
    for k in range(49):
        a = 2 * math.pi * k / 48
        sec = []
        for (dz, grow_) in ((0.016, 0.000), (0.016, 0.007), (-0.010, 0.009), (-0.012, 0.002)):
            rx, ry = 0.150 + grow_, 0.121 + grow_
            sec.append(Vector((rx * math.cos(a), 0.008 + ry * math.sin(a), 1.008 + dz)))
        secs.append(sec)
    p.loft(secs, JERSEY, cap=False)
    ob = p.build()
    vg = ob.vertex_groups.new(name="hips")
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


def pant_cuffs():
    """Loose cuffs that sit on the shoes, with the fabric stacking into a couple
    of soft folds just above, as relaxed riding pants do."""
    obs = []
    for s, n in ((1, "R"), (-1, "L")):
        p = Part("PantCuff." + n)
        cx = 0.100 * s
        for (z0, z1, r_in, r_out) in ((0.118, 0.146, 0.072, 0.080),     # cuff
                                      (0.168, 0.184, 0.074, 0.079),     # folds
                                      (0.214, 0.228, 0.075, 0.0795)):
            secs = []
            for k in range(41):
                a = 2 * math.pi * k / 40
                wob = 1.0 + 0.04 * math.sin(3 * a + z0 * 40)              # fabric isn't a perfect ring
                sec = []
                for (z, r) in ((z1, r_in), ((z0 + z1) / 2, r_out), (z0, r_in)):
                    sec.append(Vector((cx + r * wob * math.cos(a), 0.004 + r * wob * math.sin(a) * 1.05, z)))
                secs.append(sec)
            p.loft(secs, PANTS, cap=False)
        ob = p.build()
        vg = ob.vertex_groups.new(name="shin." + n)
        vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
        obs.append(ob)
    return obs


parts = [body, shoe("R", 1), shoe("L", -1), glove("R", 1), glove("L", -1), helmet(), jersey_hem()] + pant_cuffs()
for ob in parts:
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_ob
    mk.parent_keep(ob, arm_ob)

# ================================================================== pose solver
def bone_matrix(head, y_dir, z_ref):
    y = Vector(y_dir).normalized()
    z = Vector(z_ref)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(head)
    return M


def child_head(parent_pose, parent, child):
    """Where `child`'s head goes when `parent` has pose matrix `parent_pose`."""
    return parent_pose @ (REST[parent].inverted() @ REST[child].translation)


def two_bone_ik(a, target, l1, l2, pole):
    d = target - a
    dist = min(d.length, l1 + l2 - 1e-4)
    dirn = d.normalized()
    cos_a = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
    cos_a = max(-1.0, min(1.0, cos_a))
    pole_perp = (pole - dirn * pole.dot(dirn)).normalized()
    mid = a + dirn * (l1 * cos_a) + pole_perp * (l1 * math.sqrt(max(0.0, 1 - cos_a * cos_a)))
    end = a + dirn * dist
    return mid, end


def blen(name):
    return (arm_data.bones[name].tail_local - arm_data.bones[name].head_local).length


BB = Vector((0, G["bb"][0], G["bb"][1]))
CL = G["crank_len"]
GRIP = G["grip"]
FOOT_X = 0.143
BALL_FWD, ANKLE_UP = 0.120, 0.080         # rest: ankle is 12 cm behind and 8 cm above the ball
PEDAL_TOP = 0.0135


def pose_for(alpha):
    """Pose matrices (armature space) for right-crank angle alpha."""
    P = {}
    P["root"] = REST["root"].copy()
    bob = -0.010 * math.cos(2 * alpha)
    pelvis = Vector((0.0, -0.135, 1.060 + bob))
    lean = math.radians(28)
    P["hips"] = bone_matrix(pelvis, (0, math.sin(lean), math.cos(lean)), FWD)
    sp_l = math.radians(40)
    P["spine"] = bone_matrix(child_head(P["hips"], "hips", "spine"), (0, math.sin(sp_l), math.cos(sp_l)), FWD)
    ch_l = math.radians(50)
    P["chest"] = bone_matrix(child_head(P["spine"], "spine", "chest"), (0, math.sin(ch_l), math.cos(ch_l)), FWD)
    nk = math.radians(22)
    P["neck"] = bone_matrix(child_head(P["chest"], "chest", "neck"), (0, math.sin(nk), math.cos(nk)), FWD)
    hd = math.radians(-12)
    P["head"] = bone_matrix(child_head(P["neck"], "neck", "head"), (0, math.sin(hd), math.cos(hd)), FWD)

    for s, n, phase in ((1, "R", 0.0), (-1, "L", math.pi)):
        # ---- legs: ball of the foot on the pedal, ankling through the stroke
        a = alpha + phase
        pedal = BB + Vector((0, CL * math.cos(a), -CL * math.sin(a)))
        ball = pedal + Vector((s * (FOOT_X - 0.0), 0, PEDAL_TOP))
        ball.x = s * FOOT_X
        psi = math.radians(6 + 11 * math.sin(a))          # heel drops on the downstroke
        def r2(du, dv):
            return Vector((0, du * math.cos(psi) - dv * math.sin(psi), du * math.sin(psi) + dv * math.cos(psi)))
        ankle = ball + r2(-BALL_FWD, ANKLE_UP)
        toe = ball + r2(0.140 - BALL_FWD, 0.020)
        hip = child_head(P["hips"], "hips", "thigh." + n)
        pole = Vector((s * 0.12, 1.0, 0.15))
        knee, ankle_reached = two_bone_ik(hip, ankle, blen("thigh." + n), blen("shin." + n), pole)
        P["thigh." + n] = bone_matrix(hip, knee - hip, pole)
        P["shin." + n] = bone_matrix(knee, ankle_reached - knee, pole)
        P["foot." + n] = bone_matrix(ankle_reached, toe - ankle, r2(0, 1))

        # ---- arms: hands wrapped on the grips
        sh = child_head(P["chest"], "chest", "shoulder." + n)
        grip_c = Vector((s * 0.322, GRIP[0], GRIP[1]))
        P["shoulder." + n] = bone_matrix(sh, Vector((s * 1.0, 0.30, -0.05)), FWD)
        shoulder = child_head(P["shoulder." + n], "shoulder." + n, "upperarm." + n)
        hand_y = Vector((s * 0.10, 1.0, -0.15)).normalized()           # wrist -> knuckles
        hand_z = Vector((s * 0.25, 0.20, 1.0))                            # back of the hand
        Mh = bone_matrix(Vector((0, 0, 0)), hand_y, hand_z)
        # grip sits at local (0, 0.082, -0.030) in the hand frame
        wrist = grip_c - (Mh.to_3x3() @ Vector((0, 0.082, -0.030)))
        epole = Vector((s * 0.8, -0.35, 0.35))
        elbow, wrist_r = two_bone_ik(shoulder, wrist, blen("upperarm." + n), blen("forearm." + n), epole)
        P["upperarm." + n] = bone_matrix(shoulder, elbow - shoulder, epole)
        P["forearm." + n] = bone_matrix(elbow, wrist_r - elbow, epole)
        P["hand." + n] = bone_matrix(wrist_r, hand_y, hand_z)
    return P


def set_pose(P):
    for name, *_ in BONES:
        pb = arm_ob.pose.bones[name]
        parent = PARENT[name]
        if parent is None:
            base = REST[name]
        else:
            base = P[parent] @ REST[parent].inverted() @ REST[name]
        basis = base.inverted() @ P[name]
        pb.rotation_mode = "QUATERNION"
        loc, rot, _ = basis.decompose()
        pb.location = loc
        pb.rotation_quaternion = rot
        pb.scale = (1, 1, 1)


# sanity check: how far can the hands/feet reach?
P0 = pose_for(0.0)
for n in ("R", "L"):
    sh = child_head(P0["shoulder." + n], "shoulder." + n, "upperarm." + n)
    print("arm reach", n, round((P0["hand." + n].translation - sh).length, 3), "of",
          round(blen("upperarm." + n) + blen("forearm." + n), 3))

FRAMES = 48
act = bpy.data.actions.new("Pedal")
arm_ob.animation_data_create()
arm_ob.animation_data.action = act
for f in range(FRAMES + 1):
    alpha = 2 * math.pi * f / FRAMES
    set_pose(pose_for(alpha))
    for pb in arm_ob.pose.bones:
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
for fc in act.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 0, FRAMES
sc.render.fps = 24
sc.frame_set(0)

# also drop the bike into the .blend for reference (not exported)
bike_blend = os.path.join(HERE, "bike.blend")
if os.path.exists(bike_blend):
    with bpy.data.libraries.load(bike_blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    ref = bpy.data.collections.new("BikeReference")
    sc.collection.children.link(ref)
    for ob in dst.objects:
        if ob is not None:
            ref.objects.link(ob)

# export only the rider
for ob in bpy.data.objects:
    ob.select_set(False)
arm_ob.select_set(True)
for ob in parts:
    ob.select_set(True)
out_glb = os.path.join(HERE, "..", "game", "assets", "rider.glb")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True, export_apply=False,
                          export_yup=True, export_animations=True, export_animation_mode="ACTIONS",
                          export_force_sampling=True, export_frame_range=False, export_skins=True,
                          export_def_bones=False, export_optimize_animation_size=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "rider.blend"))
print("exported", os.path.normpath(out_glb))
