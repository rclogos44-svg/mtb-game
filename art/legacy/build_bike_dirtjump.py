"""Builds the dirt-jump / slopestyle bike in Blender and exports bike.glb.

Every moving part is its own object with its origin on its real pivot, so the
game can drive it straight from the suspension kinematics:

  Frame                      fixed
  Chainstay  (pivot P)       -> RearWheel (axle)
  Seatstay   (pivot H)       floating link
  Rocker     (pivot R)
  ShockBody  (lower eye F)   ShockShaft (upper eye C)
  Steer      (steering axis) -> ForkUpper, ForkLower (slides) -> FrontWheel
  Cranks     (BB)            -> PedalL, PedalR
  ChainTop / ChainBot        unit-length chain runs, stretched by the game

Run with Blender's Python:  python build_bike.py
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshkit as mk
from meshkit import Part

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = json.load(open(os.path.join(HERE, "..", "game", "assets", "geometry.json")))


def S(uv, x=0.0):
    """Side-view (u, v) + lateral x  ->  Blender (x, y=forward, z=up)."""
    return Vector((x, uv[0], uv[1]))


def uv_add(a, b, s=1.0):
    return (a[0] + b[0] * s, a[1] + b[1] * s)


mk.clear_scene()

# ------------------------------------------------------------------ materials
COPPER = mk.material("Copper", (0.30, 0.085, 0.035), metallic=0.75, roughness=0.28)
COPPER_DK = mk.material("CopperDark", (0.12, 0.035, 0.018), metallic=0.75, roughness=0.3)
BLACK = mk.material("GlossBlack", (0.012, 0.012, 0.013), metallic=0.35, roughness=0.28)
MATTE = mk.material("MatteBlack", (0.02, 0.02, 0.021), metallic=0.1, roughness=0.65)
RUBBER = mk.material("Rubber", (0.018, 0.018, 0.018), roughness=0.92)
ALLOY = mk.material("Alloy", (0.62, 0.62, 0.64), metallic=1.0, roughness=0.28)
STEEL = mk.material("Steel", (0.55, 0.56, 0.58), metallic=1.0, roughness=0.35)
GOLD = mk.material("Kashima", (0.72, 0.52, 0.22), metallic=1.0, roughness=0.25)
RED = mk.material("Red", (0.55, 0.03, 0.02), metallic=0.4, roughness=0.35)
BLUE = mk.material("TyreBlue", (0.05, 0.45, 0.85), roughness=0.6)
CHAIN = mk.material("Chain", (0.35, 0.35, 0.36), metallic=1.0, roughness=0.45)

g = GEO
WR = g["wheel_radius"]
BB = g["bb"]
RA = g["rear_axle"]
FA = g["front_axle"]
P, H0, R, B0, C0, F = (g[k] for k in ("P", "H0", "R", "B0", "C0", "F"))
AX = g["steer_axis"]
NRM = g["steer_normal"]
SEAT_TOP = (-0.080, 0.705)
SEAT_LOW = (-0.006, 0.352)

# ================================================================== FRAME
frame = Part("Frame")
ht_b, ht_t = g["head_tube_bottom"], g["head_tube_top"]
frame.tube(S(uv_add(ht_b, AX, -0.006)), S(uv_add(ht_t, AX, 0.006)), 0.029, 0.026, COPPER, seg=28)
# top tube: one straight tube from the head tube to the seat tube
tt_front = uv_add(ht_t, AX, -0.030)
tt_rear = (-0.072, 0.672)
frame.tube(S(tt_front), S(tt_rear), 0.0225, 0.0195, COPPER, seg=24, sy=1.12)
# down tube: copper at the top fading to black at the BB
dt_front = uv_add(ht_b, AX, 0.022)
dt_rear = (0.045, 0.372)
for i, (t0, t1, m) in enumerate(((0.0, 0.50, COPPER), (0.50, 0.62, COPPER_DK), (0.62, 1.0, BLACK))):
    a = (dt_front[0] + (dt_rear[0] - dt_front[0]) * t0, dt_front[1] + (dt_rear[1] - dt_front[1]) * t0)
    b = (dt_front[0] + (dt_rear[0] - dt_front[0]) * t1, dt_front[1] + (dt_rear[1] - dt_front[1]) * t1)
    r0 = 0.031 - 0.004 * t0
    r1 = 0.031 - 0.004 * t1
    frame.tube(S(a), S(b), r0, r1, m, seg=28, sy=1.22, caps=False)
# head-tube gusset joining TT and DT
frame.hull([S(uv_add(ht_t, AX, -0.02), x) for x in (-0.02, 0.02)] +
           [S(uv_add(ht_b, AX, 0.01), x) for x in (-0.024, 0.024)] +
           [S((0.36, 0.80), x) for x in (-0.018, 0.018)], COPPER)
# seat tube
st_mid = (-0.050, 0.570)
frame.tube(S(SEAT_LOW), S(st_mid), 0.019, 0.018, BLACK, seg=24)
frame.tube(S(st_mid), S(SEAT_TOP), 0.018, 0.0175, COPPER, seg=24)
frame.sphere(S(st_mid), 0.0182, COPPER)
frame.sphere(S(tt_rear), 0.021, COPPER)
# seat clamp + post + saddle
frame.tube(S(uv_add(SEAT_TOP, (0, 0), 1)), S(uv_add(SEAT_TOP, (-0.0035, 0.018))), 0.020, 0.020, MATTE)
post_top = (-0.0855, 0.735)
frame.tube(S(SEAT_TOP), S(post_top), 0.0155, mat=MATTE, seg=20)
frame.hull([S((-0.11, 0.738), x) for x in (-0.012, 0.012)] + [S((-0.06, 0.742), x) for x in (-0.012, 0.012)] +
           [S(post_top, x) for x in (-0.016, 0.016)], MATTE)
saddle = []
for (u, v, w) in ((-0.205, 0.760, 0.068), (-0.17, 0.758, 0.072), (-0.11, 0.755, 0.06),
                  (-0.04, 0.752, 0.030), (0.035, 0.757, 0.022)):
    for k in range(10):
        a = 2 * math.pi * k / 10
        saddle.append(S((u + 0.012 * math.sin(a) * 0, v + 0.016 * math.sin(a)), w * math.cos(a)))
frame.hull(saddle, MATTE)
# BB shell
frame.tube(S(BB, -0.037), S(BB, 0.037), 0.0235, mat=BLACK, seg=28)
frame.hull([S(BB, x) for x in (-0.03, 0.03)] + [S(SEAT_LOW, x) for x in (-0.018, 0.018)] +
           [S(dt_rear, x) for x in (-0.026, 0.026)] + [S((0.0, 0.405), x) for x in (-0.03, 0.03)], BLACK)
# main pivot boss
frame.tube(S(P, -0.05), S(P, 0.05), 0.0155, mat=BLACK, seg=24)
frame.hull([S(P, x) for x in (-0.02, 0.02)] + [S((0.015, 0.39), x) for x in (-0.02, 0.02)] +
           [S((-0.012, 0.44), x) for x in (-0.017, 0.017)], BLACK)
# rocker pivot: boss carried on a brace from the seat tube up to the top tube
frame.tube(S(R, -0.037), S(R, 0.037), 0.013, mat=BLACK, seg=20)
st_at_r = (-0.006 + (R[1] - 0.352) * (-0.074 / 0.353), R[1])
tt_t = (tt_rear[0] - (R[0] + 0.01 - tt_rear[0]) * 0, 0.0)
tt_at = (R[0] + 0.012, tt_front[1] + (R[0] + 0.012 - tt_front[0]) * (tt_rear[1] - tt_front[1]) / (tt_rear[0] - tt_front[0]))
frame.hull([S(R, x) for x in (-0.017, 0.017)] + [S(st_at_r, x) for x in (-0.017, 0.017)] +
           [S((st_at_r[0], st_at_r[1] + 0.03), x) for x in (-0.016, 0.016)] +
           [S((R[0], R[1] - 0.016), x) for x in (-0.017, 0.017)], COPPER)
frame.tube(S((R[0] + 0.004, R[1] + 0.01)), S(tt_at), 0.0135, 0.0145, COPPER, seg=18, sy=1.15)
frame.sphere(S(tt_at), 0.016, COPPER)
# shock lower mount (tabs on the down tube)
for x in (-0.017, 0.017):
    frame.hull([S(F, x + d) for d in (-0.003, 0.003)] +
               [S((F[0] - 0.02, F[1] - 0.03), x + d) for d in (-0.003, 0.003)] +
               [S((F[0] + 0.03, F[1] - 0.025), x + d) for d in (-0.003, 0.003)], BLACK)
frame.tube(S(F, -0.021), S(F, 0.021), 0.006, mat=STEEL, seg=12)
# chain wrap around the chainring (static ring of chain)
ring_r = g["chainring_teeth"] * 0.0127 / (2 * math.pi)
frame.torus(S(BB, 0.050), (1, 0, 0), ring_r + 0.002, 0.0035, CHAIN, seg=40, rseg=6, sy=1.4)
# brake hose along the down tube
hose = [S(uv_add(ht_b, (0.02, 0.06)), -0.03), S(uv_add(dt_front, (-0.01, -0.03)), -0.03),
        S((0.10, 0.36), -0.03), S((0.0, 0.33), -0.03), S((-0.03, 0.385), -0.045)]
frame.polytube(hose, 0.0028, MATTE, seg=8)
frame_ob = frame.build()

# ================================================================== CHAINSTAY (+ rear wheel)
cs = Part("Chainstay")
for side in (-1, 1):
    x_p = 0.040 * side
    x_a = 0.068 * side
    mid = ((P[0] + RA[0]) / 2, (P[1] + RA[1]) / 2 - 0.012)
    cs.tube(S(P, x_p), S(mid, 0.060 * side), 0.017, 0.014, BLACK, seg=20, sy=1.35)
    cs.tube(S(mid, 0.060 * side), S(RA, x_a), 0.014, 0.011, BLACK, seg=20, sy=1.25)
    cs.sphere(S(mid, 0.060 * side), 0.0145, BLACK, scale=(1, 1, 1.25))
    # dropout plate carrying the axle and the seatstay pivot H
    cs.hull([S(uv_add(RA, (math.cos(a) * 0.022, math.sin(a) * 0.022)), x_a + d)
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.004, 0.004)] +
            [S(uv_add(H0, (math.cos(a) * 0.014, math.sin(a) * 0.014)), x_a + d)
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.004, 0.004)] +
            [S(uv_add(RA, (0.06, 0.005)), 0.064 * side)], BLACK)
    cs.tube(S(H0, 0.074 * side), S(H0, 0.06 * side), 0.007, mat=STEEL, seg=12)
# yoke behind the BB
cs.hull([S(P, x) for x in (-0.05, 0.05)] + [S((P[0] - 0.07, P[1] - 0.005), x) for x in (-0.06, 0.06)] +
        [S((P[0] - 0.07, P[1] + 0.025), x) for x in (-0.055, 0.055)] + [S((P[0] - 0.01, P[1] - 0.025), x) for x in (-0.045, 0.045)], BLACK)
cs.tube(S(P, -0.052), S(P, 0.052), 0.008, mat=STEEL, seg=12)
# rear brake caliper (left side, post mount on the chainstay)
cal_dir = (math.cos(math.radians(28)), math.sin(math.radians(28)))
cal_c = uv_add(RA, cal_dir, 0.082)
cal_t = (-cal_dir[1], cal_dir[0])
cs.hull([S(uv_add(cal_c, cal_t, s * 0.03), -0.062 + d) for s in (-1, 1) for d in (-0.012, 0.012)] +
        [S(uv_add(uv_add(cal_c, cal_dir, 0.016), cal_t, s * 0.024), -0.062 + d) for s in (-1, 1) for d in (-0.012, 0.012)], MATTE)
# derailleur (right side)
hanger = uv_add(RA, (0.0, -0.01))
cs.hull([S(hanger, 0.07), S(hanger, 0.078), S(uv_add(RA, (-0.025, -0.035)), 0.078), S(uv_add(RA, (-0.03, -0.03)), 0.07)], MATTE)
up_j = uv_add(RA, (-0.01, -0.048))
lo_j = uv_add(RA, (0.012, -0.112))
cs.hull([S(uv_add(RA, (-0.03, -0.03)), 0.072), S(uv_add(RA, (-0.03, -0.03)), 0.082),
         S(uv_add(up_j, (-0.012, 0.0)), 0.075), S(uv_add(up_j, (-0.012, 0.0)), 0.083)], MATTE)
for j in (up_j, lo_j):
    cs.tube(S(j, 0.052), S(j, 0.060), 0.016, mat=MATTE, seg=16)
for xx in (0.047, 0.065):  # cage plates
    cs.hull([S(uv_add(up_j, (math.cos(a) * 0.018, math.sin(a) * 0.018)), xx) for a in [k * 0.5 for k in range(13)]] +
            [S(uv_add(lo_j, (math.cos(a) * 0.02, math.sin(a) * 0.02)), xx) for a in [k * 0.5 for k in range(13)]] +
            [S(uv_add(up_j, (math.cos(a) * 0.018, math.sin(a) * 0.018)), xx + 0.003) for a in [k * 0.5 for k in range(13)]], MATTE)
# chain: cog -> jockeys -> back to the ring is the moving part (ChainBot); these
# short runs stay with the swingarm
cog_r = g["cog_teeth"] * 0.0127 / (2 * math.pi)
cs.torus(S(RA, 0.052), (1, 0, 0), cog_r + 0.002, 0.0035, CHAIN, seg=24, rseg=6, sy=1.4)
cs.tube(S(uv_add(RA, (0.004, -cog_r)), 0.054), S(uv_add(up_j, (0.016, 0.0)), 0.056), 0.0035, mat=CHAIN, seg=6)
cs.tube(S(uv_add(up_j, (-0.016, 0.0)), 0.056), S(uv_add(lo_j, (-0.016, 0.0)), 0.056), 0.0035, mat=CHAIN, seg=6)
cs_ob = cs.build(origin=S(P))


def wheel(name, rotor_x, cassette=False):
    w = Part(name)
    c = Vector((0, 0, 0))
    # tyre
    tyre_R = WR - 0.0275
    w.torus(c, (1, 0, 0), tyre_R, 0.0275, RUBBER, seg=72, rseg=14, sy=1.06)
    # knobs: centre rows and shoulders
    for row, (b_deg, n, sz) in enumerate(((0, 56, (0.012, 0.009, 0.004)), (24, 56, (0.009, 0.010, 0.004)),
                                          (-24, 56, (0.009, 0.010, 0.004)), (52, 44, (0.008, 0.012, 0.0045)),
                                          (-52, 44, (0.008, 0.012, 0.0045)))):
        b = math.radians(b_deg)
        for k in range(n):
            a = 2 * math.pi * (k + (0.5 if row % 2 else 0.0)) / n
            rr = tyre_R + 0.0275 * math.cos(b)
            x = 0.0275 * 1.06 * math.sin(b)
            p = Vector((x, rr * math.cos(a), rr * math.sin(a)))
            radial = Vector((0, math.cos(a), math.sin(a)))
            nrm = (radial * math.cos(b) + Vector((math.sin(b), 0, 0))).normalized()
            M = mk.frame_from(nrm, up=Vector((1, 0, 0)))
            w.box(p + nrm * 0.0015, (sz[1], sz[0], sz[2]), RUBBER, rot=M)
    # blue sidewall label strip (like the reference tyre graphics)
    for side in (-1, 1):
        for k in range(2):
            a0 = math.pi * k + 0.4
            pts = []
            w.hull([Vector((side * 0.027, (WR - 0.040) * math.cos(a0 + t * 0.03), (WR - 0.040) * math.sin(a0 + t * 0.03))) for t in range(-6, 7)] +
                   [Vector((side * 0.025, (WR - 0.050) * math.cos(a0 + t * 0.03), (WR - 0.050) * math.sin(a0 + t * 0.03))) for t in range(-6, 7)], BLUE, smooth=False)
    # rim
    w.disc(c, (1, 0, 0), 0.2895, 0.268, 0.030, BLACK, seg=72)
    w.torus(c, (1, 0, 0), 0.2885, 0.0035, BLACK, seg=72, rseg=6, sy=4.0)
    # hub
    w.tube(Vector((-0.050, 0, 0)), Vector((0.050, 0, 0)), 0.012, mat=MATTE, seg=20)
    w.tube(Vector((-0.035, 0, 0)), Vector((0.035, 0, 0)), 0.019, 0.019, MATTE, seg=20)
    for xf in (-0.033, 0.030):
        w.disc(Vector((xf, 0, 0)), (1, 0, 0), 0.030, 0.012, 0.004, MATTE, seg=24)
    # spokes: 32, two-cross-ish
    for k in range(32):
        side = 1 if k % 2 else -1
        a_h = 2 * math.pi * k / 32
        lead = 1 if (k // 2) % 2 else -1
        a_r = a_h + lead * math.radians(36)
        hub = Vector((side * 0.031, 0.028 * math.cos(a_h), 0.028 * math.sin(a_h)))
        rim = Vector((side * 0.004, 0.270 * math.cos(a_r), 0.270 * math.sin(a_r)))
        w.tube(hub, rim, 0.0011, mat=STEEL, seg=5, caps=False)
    # disc rotor + spider
    w.disc(Vector((rotor_x, 0, 0)), (1, 0, 0), 0.080, 0.062, 0.0018, STEEL, seg=48)
    for k in range(6):
        a = 2 * math.pi * k / 6
        w.hull([Vector((rotor_x + d, r * math.cos(a + s), r * math.sin(a + s)))
                for d in (-0.001, 0.001) for (r, s) in ((0.022, -0.25), (0.022, 0.25), (0.066, -0.08), (0.066, 0.08))], STEEL, smooth=False)
    if cassette:
        for i in range(7):
            teeth = 13 + i * 3
            r = teeth * 0.0127 / (2 * math.pi)
            w.disc(Vector((0.052 - i * 0.004, 0, 0)), (1, 0, 0), r, 0.016, 0.0018, ALLOY, seg=max(teeth, 16))
    # through axle
    w.tube(Vector((-0.075, 0, 0)), Vector((0.075, 0, 0)), 0.006, mat=STEEL, seg=12)
    return w


rw = wheel("RearWheel", -0.060, cassette=True)
rw_ob = rw.build()
rw_ob.location = S(RA)
mk.parent_keep(rw_ob, cs_ob)

# ================================================================== SEATSTAY
ss = Part("Seatstay")
for side in (-1, 1):
    a = S(H0, 0.067 * side)
    b = S(B0, 0.053 * side)
    mid = (a + b) / 2 + Vector((0.006 * side, 0, 0))
    ss.tube(a, mid, 0.0105, 0.0125, COPPER, seg=18, sy=1.3)
    ss.tube(mid, b, 0.0125, 0.0115, COPPER, seg=18, sy=1.3)
    ss.sphere(mid, 0.0125, COPPER, scale=(1, 1, 1.3))
    ss.sphere(a, 0.012, COPPER)
    ss.sphere(b, 0.012, COPPER)
# bridge near the top, clear of the tyre
br = (H0[0] + (B0[0] - H0[0]) * 0.93, H0[1] + (B0[1] - H0[1]) * 0.93)
ss.tube(S(br, -0.056), S(br, 0.056), 0.0085, mat=COPPER, seg=14, sy=1.3)
ss_ob = ss.build(origin=S(H0))

# ================================================================== ROCKER
rk = Part("Rocker")
for side in (-1, 1):
    pts = []
    for (c, r) in ((R, 0.017), (B0, 0.013), (C0, 0.013)):
        for k in range(14):
            a = 2 * math.pi * k / 14
            for d in (-0.0045, 0.0045):
                pts.append(S(uv_add(c, (math.cos(a) * r, math.sin(a) * r)), 0.044 * side + d))
    rk.hull(pts, BLACK)
for c, w_ in ((R, 0.05), (B0, 0.06), (C0, 0.05)):
    rk.tube(S(c, -w_), S(c, w_), 0.0065, mat=STEEL, seg=12)
rk_ob = rk.build(origin=S(R))

# ================================================================== SHOCK
sdir = Vector((0, C0[0] - F[0], C0[1] - F[1])).normalized()
Fv = S(F)
Cv = S(C0)
sb = Part("ShockBody")
sb.tube(Fv + Vector((-0.011, 0, 0)), Fv + Vector((0.011, 0, 0)), 0.0115, mat=MATTE, seg=18)
sb.tube(Fv + sdir * 0.010, Fv + sdir * 0.062, 0.019, mat=MATTE, seg=24)
sb.tube(Fv + sdir * 0.025, Fv + sdir * 0.045, 0.0215, mat=RED, seg=24)        # rebound / lockout dial
sb.tube(Fv + sdir * 0.062, Fv + sdir * 0.160, 0.0158, mat=GOLD, seg=24)       # air-can stanchion
sb.torus(Fv + sdir * 0.064, sdir, 0.0165, 0.0018, RED, seg=24, rseg=6)          # travel o-ring
sb_ob = sb.build(origin=Fv)

sh = Part("ShockShaft")
sh.tube(Cv + Vector((-0.011, 0, 0)), Cv + Vector((0.011, 0, 0)), 0.0115, mat=MATTE, seg=18)
sh.tube(Cv - sdir * 0.008, Cv - sdir * 0.028, 0.0205, mat=MATTE, seg=24)
sh.tube(Cv - sdir * 0.028, Cv - sdir * 0.103, 0.0225, mat=BLACK, seg=24)       # air sleeve
sh.tube(Cv - sdir * 0.098, Cv - sdir * 0.104, 0.0228, mat=RED, seg=24)
sh_ob = sh.build(origin=Cv)

# ================================================================== STEERING + FORK
axis = Vector((0, AX[0], AX[1]))
nrm = Vector((0, NRM[0], NRM[1]))
steer_origin = S(g["head_tube_bottom"])
steer = bpy.data.objects.new("Steer", None)
steer.empty_display_size = 0.05
steer.location = steer_origin
steer.rotation_euler = (math.atan2(-AX[0], AX[1]), 0, 0)
bpy.context.scene.collection.objects.link(steer)

leg_spacing = 0.0575
crown_pt = S(g["fork_crown"])
leg_top = S(FA) + axis * g["fork_a2c"]          # crown height on the leg line
fu = Part("ForkUpper")
fu.tube(crown_pt, S(g["stem_clamp"]) + axis * 0.024, 0.0172, mat=MATTE, seg=20)            # steerer
fu.tube(S(g["head_tube_top"]), S(g["stem_clamp"]) - axis * 0.020, 0.0185, mat=MATTE, seg=20)  # spacers
for p in (S(g["head_tube_top"]) + axis * 0.004, S(g["head_tube_bottom"]) - axis * 0.004):
    fu.tube(p - axis * 0.004, p + axis * 0.004, 0.0295, mat=MATTE, seg=24)                  # headset cups
crown = []
for side in (-1, 1):
    for k in range(12):
        a = 2 * math.pi * k / 12
        ring = Vector((math.cos(a) * 0.026, 0, 0)) + nrm * math.sin(a) * 0.026
        for d in (-0.012, 0.016):
            crown.append(leg_top + Vector((side * leg_spacing, 0, 0)) + ring + axis * d)
for k in range(12):
    a = 2 * math.pi * k / 12
    ring = Vector((math.cos(a) * 0.024, 0, 0)) + nrm * math.sin(a) * 0.024
    for d in (-0.01, 0.02):
        crown.append(crown_pt + ring + axis * d)
fu.hull(crown, BLACK)
STANCH_LEN = 0.33
for side in (-1, 1):
    top = leg_top + Vector((side * leg_spacing, 0, 0))
    fu.tube(top + axis * 0.012, top - axis * STANCH_LEN, 0.017, mat=BLACK, seg=24)
# stem
sc = S(g["stem_clamp"])
bc = S(g["bar_clamp"])
st = []
for k in range(16):
    a = 2 * math.pi * k / 16
    ring = Vector((math.cos(a) * 0.022, 0, 0)) + nrm * math.sin(a) * 0.022
    for d in (-0.02, 0.02):
        st.append(sc + ring + axis * d)
for k in range(16):
    a = 2 * math.pi * k / 16
    for x in (-0.026, 0.026):
        st.append(bc + Vector((x, 0.021 * math.cos(a), 0.021 * math.sin(a))))
fu.hull(st, MATTE)
# handlebar (riser bar)
grip = g["grip"]
hw = g["bar_width"] / 2
bar_pts = [
    S(grip, -hw), S(uv_add(grip, (0.004, -0.002)), -0.20), S(uv_add(g["bar_clamp"], (0.0, 0.012)), -0.11),
    S(g["bar_clamp"], -0.04), S(g["bar_clamp"], 0.04), S(uv_add(g["bar_clamp"], (0.0, 0.012)), 0.11),
    S(uv_add(grip, (0.004, -0.002)), 0.20), S(grip, hw)]
for i, (a, b) in enumerate(zip(bar_pts, bar_pts[1:])):
    r0 = 0.0159 if i in (2, 3, 4) else 0.0111
    r1 = 0.0159 if i in (1, 2, 3) else 0.0111
    fu.tube(a, b, r0, r1, BLACK, seg=18)
for p in bar_pts[1:-1]:
    fu.sphere(p, 0.0112, BLACK, seg=12, rings=8)
for side in (-1, 1):
    g0 = S(grip, side * (hw - 0.135))
    g1 = S(grip, side * hw)
    fu.tube(g0, g1, 0.0165, mat=RUBBER, seg=20)
    fu.tube(g0 - Vector((side * 0.008, 0, 0)), g0, 0.0175, mat=ALLOY, seg=20)
    fu.tube(g1, g1 + Vector((side * 0.006, 0, 0)), 0.0175, mat=ALLOY, seg=20)
    # brake lever + master cylinder
    lc = S(uv_add(grip, (0.002, -0.002)), side * (hw - 0.165))
    fu.tube(lc - Vector((0.012, 0, 0)), lc + Vector((0.012, 0, 0)), 0.016, mat=MATTE, seg=14)
    fu.hull([lc + Vector((side * 0.006, 0, 0)) + Vector((0, 0.010, 0.012)),
             lc + Vector((-side * 0.006, 0, 0)) + Vector((0, 0.010, 0.012)),
             lc + Vector((side * 0.01, 0.045, 0.020)), lc + Vector((-side * 0.01, 0.045, 0.020)),
             lc + Vector((side * 0.028, 0.035, 0.026)), lc + Vector((side * 0.012, 0.025, 0.005))], MATTE)
    blade = [lc + Vector((side * 0.004, 0.030, 0.0)), lc + Vector((side * 0.006, 0.040, -0.004)),
             lc + Vector((side * 0.075, 0.048, -0.030)), lc + Vector((side * 0.078, 0.042, -0.034)),
             lc + Vector((side * 0.004, 0.034, -0.006)), lc + Vector((side * 0.076, 0.052, -0.026))]
    fu.hull(blade, ALLOY)
# front brake hose from lever round to the crown
fu.polytube([S(uv_add(grip, (0.03, 0.0)), -(hw - 0.17)), S(uv_add(g["bar_clamp"], (0.09, -0.02)), -0.10),
             S(uv_add(g["fork_crown"], (0.08, 0.02)), -0.07), leg_top + Vector((-0.08, 0, 0)) - axis * 0.06], 0.0028, MATTE, seg=8)
fu_ob = fu.build(origin=steer_origin)

# fork lowers (slide along the steering axis)
fl = Part("ForkLower")
fa = S(FA)
SEAL_T = g["fork_a2c"] - 0.012 - 0.026 - g["fork_travel"] - 0.020   # seal height above axle on leg line
for side in (-1, 1):
    base = fa + Vector((side * leg_spacing, 0, 0))
    fl.tube(base - axis * 0.012, base + axis * SEAL_T, 0.0228, 0.0236, BLACK, seg=24)
    fl.tube(base + axis * (SEAL_T - 0.001), base + axis * (SEAL_T + 0.012), 0.0215, 0.019, MATTE, seg=24)
    # dropout
    fl.hull([base + Vector((d, 0, 0)) + Vector((0, math.cos(a) * 0.021, math.sin(a) * 0.021))
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.008, 0.008)] +
            [base + axis * 0.06 + Vector((d, 0, 0)) + nrm * s for d in (-0.012, 0.012) for s in (-0.02, 0.02)], BLACK)
# arch in front of the legs
arch = []
for i in range(9):
    t = i / 8
    x = -leg_spacing + 2 * leg_spacing * t
    lift = math.sin(math.pi * t)
    arch.append(fa + Vector((x * (1 - 0.15 * lift), 0, 0)) + axis * (SEAL_T - 0.08 + 0.05 * lift) + nrm * (0.018 + 0.022 * lift))
fl.polytube(arch, 0.011, BLACK, seg=14)
# front caliper (left, behind the leg)
fcal = fa + Vector((-0.064, 0, 0)) + (-nrm * 0.55 + axis * 0.835).normalized() * 0.082
fdir = (-nrm * 0.55 + axis * 0.835).normalized()
ftan = Vector((1, 0, 0)).cross(fdir)
fl.hull([fcal + ftan * s * 0.03 + Vector((d, 0, 0)) for s in (-1, 1) for d in (-0.012, 0.012)] +
        [fcal + fdir * 0.016 + ftan * s * 0.024 + Vector((d, 0, 0)) for s in (-1, 1) for d in (-0.012, 0.012)], MATTE)
fl_ob = fl.build(origin=fa)

fw = wheel("FrontWheel", -0.060)
fw_ob = fw.build()
fw_ob.location = fa

mk.parent_keep(fu_ob, steer)
mk.parent_keep(fl_ob, steer)
mk.parent_keep(fw_ob, fl_ob)

# ================================================================== CRANKS + PEDALS
L = g["crank_len"]
cr = Part("Cranks")
cr.tube(S(BB, -0.075), S(BB, 0.075), 0.012, mat=STEEL, seg=16)
# chainring (+ teeth) and spider
cr.disc(S(BB, 0.050), (1, 0, 0), ring_r - 0.002, ring_r - 0.012, 0.0035, MATTE, seg=60)
nt = g["chainring_teeth"]
for k in range(nt):
    a = 2 * math.pi * k / nt
    p = S(uv_add(BB, (math.cos(a) * (ring_r + 0.001), math.sin(a) * (ring_r + 0.001))), 0.050)
    M = mk.frame_from(Vector((0, math.cos(a), math.sin(a))), up=Vector((1, 0, 0)))
    cr.box(p, (0.0035, 0.006, 0.007), MATTE, rot=M)
for k in range(4):
    a = 2 * math.pi * k / 4 + 0.4
    cr.hull([S(uv_add(BB, (math.cos(a + s) * r, math.sin(a + s) * r)), 0.050 + d)
             for d in (-0.003, 0.003) for (r, s) in ((0.018, -0.35), (0.018, 0.35), (ring_r - 0.008, -0.12), (ring_r - 0.008, 0.12))], MATTE)
for side, ang in ((1, 0.0), (-1, math.pi)):
    end = uv_add(BB, (math.cos(ang) * L, math.sin(ang) * L))
    pts = []
    for (c, r) in ((BB, 0.020), (end, 0.012)):
        for k in range(14):
            a = 2 * math.pi * k / 14
            for d in (-0.008, 0.008):
                pts.append(S(uv_add(c, (math.cos(a) * r, math.sin(a) * r * 1.1)), side * 0.072 + d))
    cr.hull(pts, MATTE)
cr_ob = cr.build(origin=S(BB))


def pedal(name, side):
    end = (BB[0] + side * L, BB[1])
    p = Part(name)
    o = S(end, side * 0.080)
    p.tube(o - Vector((side * 0.002, 0, 0)), o + Vector((side * 0.11, 0, 0)), 0.006, mat=STEEL, seg=10)
    c = o + Vector((side * 0.060, 0, 0))
    # concave platform: hull of a frame
    p.hull([c + Vector((x, y, z)) for x in (-0.05, 0.05) for y in (-0.052, 0.052) for z in (-0.009, 0.009)], MATTE, smooth=False)
    for x in (-0.042, -0.014, 0.014, 0.042):
        for y in (-0.045, 0.045):
            for z in (-1, 1):
                p.tube(c + Vector((x, y, z * 0.009)), c + Vector((x, y, z * 0.0135)), 0.0017, mat=STEEL, seg=6)
    return p.build(origin=o)


pr_ob = pedal("PedalR", 1)
pl_ob = pedal("PedalL", -1)
mk.parent_keep(pr_ob, cr_ob)
mk.parent_keep(pl_ob, cr_ob)

# ================================================================== CHAIN RUNS (unit length along +Y)
for name in ("ChainTop", "ChainBot"):
    c = Part(name)
    n = 70
    for k in range(n):
        y0 = k / n
        y1 = (k + 0.55) / n
        c.box(Vector((0.0, (y0 + y1) / 2, 0.0)), (0.0075 if k % 2 else 0.0058, (y1 - y0) * 1.6, 0.0072), CHAIN)
    ob = c.build()
    ob.location = S(BB, 0.052)

# ================================================================== export
bpy.context.view_layer.update()
out_glb = os.path.join(HERE, "..", "game", "assets", "bike.glb")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_apply=True,
                          export_yup=True, export_animations=False, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "bike.blend"))
print("exported", os.path.normpath(out_glb))
