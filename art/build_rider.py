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
PANTS = mk.material("Pants", (0.045, 0.047, 0.05), roughness=0.9)
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
        ("hip" + n, (0.090 * s, 0, 0.900), (0.110, 0.110)),
        ("thighM" + n, (0.096 * s, 0.0, 0.715), (0.098, 0.098)),
        ("knee" + n, J["knee" + n], (0.078, 0.078)),
        ("shinM" + n, (0.100 * s, 0.0, 0.300), (0.072, 0.072)),
        ("ankle" + n, (0.100 * s, 0.0, 0.110), (0.060, 0.060)),
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
    poly.material_index = 1 if (leg and z < 1.02) else 0
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
HELM_BLACK = mk.material("HelmetBlack", (0.012, 0.012, 0.014), roughness=0.22)
HELM_MATTE = mk.material("HelmetMatte", (0.016, 0.016, 0.018), roughness=0.6)
HELM_GREY = mk.material("HelmetGrey", (0.30, 0.31, 0.33), metallic=0.3, roughness=0.35)
HELM_VENT = mk.material("HelmetVent", (0.003, 0.003, 0.004), roughness=0.95)
HELM_PAD = mk.material("HelmetPadding", (0.22, 0.22, 0.24), roughness=0.95)
GOG_FRAME = mk.material("GoggleFrame", (0.03, 0.03, 0.035), roughness=0.5)
GOG_LENS = mk.material("GoggleLens", (0.95, 0.38, 0.04), metallic=0.85, roughness=0.06)
GOG_STRAP = mk.material("GoggleStrap", (0.06, 0.06, 0.065), roughness=0.8)


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def helmet():
    """Downhill full-face (moto style), all black: one closed shell with an eye
    port, a chin bar that juts forward and down, vents, padded interior, a
    large vented peak screwed on at the temples, and goggles in the port."""
    p = Part("Helmet")
    Mr = REST["head"]
    CY, CZ = 0.100, -0.012
    RX, RY, RZ = 0.132, 0.160, 0.162
    C = Vector((0, CY, CZ))
    D = math.radians

    def shape(phi, th):
        """Outer shell in head-local coords (X lateral, Y up, Z forward).
        phi: 0 = front; th: 0 = crown."""
        x = RX * math.sin(th) * math.sin(phi)
        y = CY + RY * math.cos(th)
        z = CZ + RZ * math.sin(th) * math.cos(phi)
        front = max(0.0, math.cos(phi))
        w = front ** 2 * _smooth(D(100), D(142), th)      # chin bar region
        z += 0.058 * w + 0.016 * w * front ** 12
        y -= 0.022 * w
        x *= 1.0 - 0.20 * w
        return Vector((x, y, z))

    def grow(v, g):
        d = v - C
        return C + d * (1.0 + g / d.length)

    def th_max(phi):
        return D(118 + 34 * ((1 + math.cos(phi)) / 2) ** 1.6)

    def in_port(phi, th):
        return (abs(phi) / D(57)) ** 4 + (abs(th - D(88)) / D(17)) ** 4 < 1.0

    # ---- shell surface -> solidify (padding inside, matte rim) -> subdivide
    NP, NT = 128, 64
    bm = bmesh.new()
    pole = bm.verts.new(shape(0.0, 0.0))
    grid = []
    for i in range(NT):
        row = []
        for j in range(NP):
            phi = 2 * math.pi * j / NP - math.pi
            row.append(bm.verts.new(shape(phi, (i + 1) / NT * th_max(phi))))
        grid.append(row)
    def keep(i, j):
        phi = 2 * math.pi * (j + 0.5) / NP - math.pi
        th = (i + 1.5) / NT * th_max(phi)
        return not in_port(phi, th)
    for j in range(NP):
        bm.faces.new([pole, grid[0][(j + 1) % NP], grid[0][j]])
    for i in range(NT - 1):
        for j in range(NP):
            if keep(i, j):
                j2 = (j + 1) % NP
                bm.faces.new([grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # make normals point outward
    f0 = bm.faces[0]
    if f0.normal.dot(f0.calc_center_median() - C) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new("shell_src")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("shell_src", me)
    col.objects.link(ob)
    for mat in (HELM_BLACK, HELM_PAD, HELM_MATTE):
        me.materials.append(mat)
    so = ob.modifiers.new("Solid", "SOLIDIFY")
    so.thickness = 0.016
    so.offset = -1.0
    so.use_rim = True
    so.use_even_offset = True
    so.material_offset = 1
    so.material_offset_rim = 2
    ss = ob.modifiers.new("Sub", "SUBSURF")
    ss.levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    em = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    p.add_mesh(em, [HELM_BLACK, HELM_PAD, HELM_MATTE], matrix=Mr)
    bpy.data.objects.remove(ob, do_unlink=True)

    def L(v):
        return Mr @ v

    def slot(phi0, phi1, th0, th1, mat=HELM_VENT, g0=0.0004, g1=0.0016, n=5):
        pts = [L(grow(shape(D(phi0 + (phi1 - phi0) * a / n), D(th0 + (th1 - th0) * b / n)), g))
               for a in range(n + 1) for b in range(n + 1) for g in (g0, g1)]
        p.hull(pts, mat, smooth=False)

    # ---- vents: chin, cheeks, crown, rear
    for ph in (-13, 0, 13):
        slot(ph - 3.5, ph + 3.5, 118, 138)
    for sg in (-1, 1):
        slot(sg * 30 - 5, sg * 30 + 5, 124, 140)
        slot(sg * 18 - 6, sg * 18 + 6, 22, 44)
        slot(sg * 44 - 6, sg * 44 + 6, 34, 50)
        slot(sg * 165 - 6, sg * 165 + 6, 70, 96)

    # ---- peak
    NU, NV = 16, 7
    def peak_pt(u, v):
        phi = D(80 * u)
        th = D(63 + 15 * u * u)
        base = grow(shape(phi, th), 0.002)
        d = Vector((math.sin(phi) * 0.75, -0.02, math.cos(phi))).normalized()
        L_ = 0.105 * (1.0 - 0.55 * u * u)
        q = base + d * L_ * v
        q.y += 0.010 * (1 - u * u) * v - 0.008 * v * v
        return q
    bm = bmesh.new()
    pg = [[bm.verts.new(peak_pt(-1 + 2 * a / NU, b / NV)) for b in range(NV + 1)] for a in range(NU + 1)]
    for a in range(NU):
        for b in range(NV):
            bm.faces.new([pg[a][b], pg[a + 1][b], pg[a + 1][b + 1], pg[a][b + 1]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.faces[NU * NV // 2].normal.y < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new("peak_src")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(HELM_BLACK)
    ob = bpy.data.objects.new("peak_src", me)
    col.objects.link(ob)
    so = ob.modifiers.new("Solid", "SOLIDIFY")
    so.thickness = 0.006
    so.offset = 0.0
    ss = ob.modifiers.new("Sub", "SUBSURF")
    ss.levels = 1
    dg = bpy.context.evaluated_depsgraph_get()
    em = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    p.add_mesh(em, [HELM_MATTE], matrix=Mr)
    bpy.data.objects.remove(ob, do_unlink=True)
    up = Vector((0, 1, 0))
    for (u0, u1) in ((-0.42, -0.18), (0.18, 0.42)):        # vent cut-outs in the peak
        p.hull([L(peak_pt(u0 + (u1 - u0) * a / 3, 0.30 + 0.4 * b / 3) + up * g)
                for a in range(4) for b in range(4) for g in (0.0032, 0.0048)], HELM_VENT, smooth=False)
    p.hull([L(peak_pt(-0.08 + 0.16 * a / 3, 0.15 + 0.7 * b / 3) + up * g)
            for a in range(4) for b in range(4) for g in (0.0032, 0.0048)], HELM_GREY, smooth=False)
    for sg in (-1, 1):                                       # peak screws at the temples
        c = peak_pt(sg * 0.97, 0.12)
        n = (c - C).normalized()
        p.tube(L(c - n * 0.004), L(c + n * 0.006), 0.0075, mat=HELM_GREY, seg=12)

    # ---- goggles sitting in the eye port, strap round the shell
    def gsec(phi, th0, th1, r0, r1):
        sec = []
        for k in range(12):
            a = 2 * math.pi * k / 12
            cu = 0.5 + 0.5 * max(-1.0, min(1.0, 1.35 * math.cos(a)))
            cv = 0.5 + 0.5 * max(-1.0, min(1.0, 1.35 * math.sin(a)))
            th = th0 + (th1 - th0) * cv
            base = shape(phi, th)
            r = r0 + (r1 - r0) * cu
            sec.append(L(C + (base - C) * r))
        return sec
    p.loft([gsec(D(-60 + 120 * k / 30), D(69.5), D(106.5), 0.950, 1.008) for k in range(31)], GOG_FRAME)
    p.loft([gsec(D(-51 + 102 * k / 24), D(76), D(100), 1.004, 1.012) for k in range(25)], GOG_LENS)
    p.loft([[L(grow(q, 0.0)) for q in []] or gsec(D(58 + 244 * k / 40), D(83), D(94), 1.008, 1.024)
            for k in range(41)], GOG_STRAP)
    ob = p.build()
    vg = ob.vertex_groups.new(name="head")
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


parts = [body, shoe("R", 1), shoe("L", -1), glove("R", 1), glove("L", -1), helmet()]
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
