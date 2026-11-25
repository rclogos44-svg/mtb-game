"""Builds the 29er trail / enduro bike in Blender and exports bike.glb.

Every moving part is its own object with its origin on its real pivot, so the
game can drive it straight from the suspension kinematics:

  Frame                      fixed
  Chainstay  (pivot P)       -> RearWheel (axle)
  Seatstay   (pivot H)       floating link
  Rocker     (pivot R)
  ShockBody  (front eye F)   -> ShockSpring (coil, scaled along its axis)
  ShockShaft (rear eye C)
  Steer      (steering axis) -> ForkUpper, ForkLower (slides) -> FrontWheel
  Cranks     (BB)            -> PedalL, PedalR
  ChainTop / ChainBot        unit-length chain runs, stretched by the game

Run with Blender's Python:  python build_bike.py
(The earlier dirt-jump bike is kept in legacy/build_bike_dirtjump.py.)
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


def lerp2(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


mk.clear_scene()

# ------------------------------------------------------------------ materials
FRAME = mk.material("FrameLight", (0.66, 0.67, 0.69), metallic=0.35, roughness=0.32)
FRAME_DK = mk.material("FrameDark", (0.16, 0.17, 0.18), metallic=0.35, roughness=0.35)
BLACK = mk.material("GlossBlack", (0.012, 0.012, 0.013), metallic=0.3, roughness=0.3)
MATTE = mk.material("MatteBlack", (0.02, 0.02, 0.021), metallic=0.1, roughness=0.65)
RUBBER = mk.material("Rubber", (0.018, 0.018, 0.018), roughness=0.92)
ALLOY = mk.material("Alloy", (0.62, 0.62, 0.64), metallic=1.0, roughness=0.28)
STEEL = mk.material("Steel", (0.55, 0.56, 0.58), metallic=1.0, roughness=0.35)
FORK_GREY = mk.material("ForkGrey", (0.33, 0.34, 0.36), metallic=0.5, roughness=0.35)
SPRING = mk.material("Spring", (0.86, 0.85, 0.80), metallic=0.2, roughness=0.35)
LIME = mk.material("Lime", (0.55, 0.78, 0.05), roughness=0.4)
GUM = mk.material("SidewallGrey", (0.30, 0.30, 0.31), roughness=0.85)
CHAIN = mk.material("Chain", (0.35, 0.35, 0.36), metallic=1.0, roughness=0.45)

g = GEO
WR = g["wheel_radius"]
BB = g["bb"]
RA = g["rear_axle"]
FA = g["front_axle"]
P, H0, R, B0, C0, F = (g[k] for k in ("P", "H0", "R", "B0", "C0", "F"))
AX = g["steer_axis"]
NRM = g["steer_normal"]

# seat tube: straight line from the BB to the clamp (dropper post lowered)
SEAT_LOW = (-0.005, 0.370)
SEAT_TOP = (-0.058, 0.790)      # shorter, steeper seat tube, as in the photo
ST_DIR = Vector((0, SEAT_TOP[0] - SEAT_LOW[0], SEAT_TOP[1] - SEAT_LOW[1])).normalized()


def st_at(v):
    t = (v - SEAT_LOW[1]) / (SEAT_TOP[1] - SEAT_LOW[1])
    return lerp2(SEAT_LOW, SEAT_TOP, t)


# ================================================================== FRAME
frame = Part("Frame")
ht_b, ht_t = g["head_tube_bottom"], g["head_tube_top"]
frame.tube(S(uv_add(ht_b, AX, -0.010)), S(uv_add(ht_t, AX, 0.006)), 0.031, 0.027, FRAME, seg=28)
# top tube: straight, head tube to seat tube
tt_front = uv_add(ht_t, AX, -0.028)
tt_rear = st_at(0.665)      # low at the seat tube: steep, aggressive top tube (traced)
frame.tube(S(tt_front), S(tt_rear), 0.025, 0.020, FRAME, seg=26, sy=1.15)
frame.sphere(S(tt_rear), 0.021, FRAME_DK)


def tt_at(u):
    t = (u - tt_front[0]) / (tt_rear[0] - tt_front[0])
    return lerp2(tt_front, tt_rear, t)


# down tube: big and slightly flattened, light grey, darker at the BB
dt_front = uv_add(ht_b, AX, 0.020)
dt_rear = (0.050, 0.395)
dt_mid = lerp2(dt_front, dt_rear, 0.82)
frame.tube(S(dt_front), S(dt_mid), 0.035, 0.032, FRAME, seg=30, sy=1.22, caps=False)
frame.tube(S(dt_mid), S(dt_rear), 0.032, 0.030, FRAME_DK, seg=30, sy=1.22, caps=False)
# head-tube junction gusset
frame.hull([S(uv_add(ht_t, AX, -0.02), x) for x in (-0.022, 0.022)] +
           [S(uv_add(ht_b, AX, 0.0), x) for x in (-0.03, 0.03)] +
           [S(lerp2(tt_front, tt_rear, 0.12), x) for x in (-0.02, 0.02)] +
           [S(lerp2(dt_front, dt_rear, 0.12), x) for x in (-0.03, 0.03)], FRAME)
# seat tube: light at the bottom, dark grey above the rocker
st_split = st_at(0.640)
frame.tube(S(SEAT_LOW), S(st_split), 0.020, 0.019, FRAME, seg=24)
frame.tube(S(st_split), S(SEAT_TOP), 0.019, 0.0185, FRAME_DK, seg=24)
frame.sphere(S(st_split), 0.0192, FRAME_DK)
# seat clamp + dropper post (lowered) + saddle
frame.tube(S(SEAT_TOP) - ST_DIR * 0.004, S(SEAT_TOP) + ST_DIR * 0.016, 0.021, mat=MATTE, seg=20)
# dropper slammed all the way down: the rider pedals standing, clear of the saddle
post_top = S(SEAT_TOP) + ST_DIR * 0.018
frame.tube(S(SEAT_TOP), post_top, 0.0158, mat=MATTE, seg=20)
pt = (post_top.y, post_top.z)
frame.hull([S(uv_add(pt, (-0.035, 0.008)), x) for x in (-0.013, 0.013)] +
           [S(uv_add(pt, (0.03, 0.009)), x) for x in (-0.013, 0.013)] +
           [S(pt, x) for x in (-0.017, 0.017)], MATTE)
saddle = []
for (du, dv, w) in ((-0.135, 0.026, 0.068), (-0.105, 0.023, 0.072), (-0.05, 0.019, 0.058),
                    (0.02, 0.016, 0.030), (0.105, 0.020, 0.021)):
    for k in range(10):
        a = 2 * math.pi * k / 10
        saddle.append(S((pt[0] + du, pt[1] + dv + 0.010 * math.sin(a)), w * math.cos(a)))
frame.hull(saddle, MATTE)
# BB shell and the cluster that carries the main pivot
frame.tube(S(BB, -0.037), S(BB, 0.037), 0.024, mat=FRAME_DK, seg=28)
frame.hull([S(BB, x) for x in (-0.03, 0.03)] + [S(SEAT_LOW, x) for x in (-0.02, 0.02)] +
           [S(dt_rear, x) for x in (-0.03, 0.03)] + [S(uv_add(P, (0.012, 0.012)), x) for x in (-0.03, 0.03)] +
           [S((0.06, 0.37), x) for x in (-0.026, 0.026)], FRAME_DK)
frame.tube(S(P, -0.05), S(P, 0.05), 0.016, mat=FRAME_DK, seg=24)
# rocker pivot boss: plate from the seat tube forward to R
r_st = st_at(R[1])
frame.hull([S(R, x) for x in (-0.017, 0.017)] + [S(r_st, x) for x in (-0.018, 0.018)] +
           [S(st_at(R[1] - 0.05), x) for x in (-0.018, 0.018)] + [S(uv_add(R, (-0.01, -0.02)), x) for x in (-0.017, 0.017)],
           FRAME_DK)
frame.tube(S(R, -0.037), S(R, 0.037), 0.0135, mat=FRAME_DK, seg=20)
# brace from the down tube up to the top tube; the shock's front eye bolts to it
br_lo = (F[0] + 0.030, 0.548)
br_hi = (F[0] - 0.028, None)
br_hi = (br_hi[0], tt_at(br_hi[0])[1] - 0.005)
frame.tube(S(br_lo), S(br_hi), 0.016, 0.014, FRAME, seg=20, sy=1.25)
frame.sphere(S(br_hi), 0.0165, FRAME)
for x in (-0.017, 0.017):
    frame.hull([S(uv_add(F, (math.cos(a) * 0.013, math.sin(a) * 0.013)), x + d)
                for a in [k * math.pi / 4 for k in range(8)] for d in (-0.003, 0.003)] +
               [S(lerp2(br_lo, br_hi, 0.35), x + d) for d in (-0.003, 0.003)] +
               [S(lerp2(br_lo, br_hi, 0.75), x + d) for d in (-0.003, 0.003)], FRAME)
frame.tube(S(F, -0.021), S(F, 0.021), 0.006, mat=STEEL, seg=12)
# chain wrap around the chainring
ring_r = g["chainring_teeth"] * 0.0127 / (2 * math.pi)
frame.torus(S(BB, 0.050), (1, 0, 0), ring_r + 0.002, 0.0035, CHAIN, seg=44, rseg=6, sy=1.4)
# hoses / cables along the down tube
for i, x in enumerate((-0.028, -0.034)):
    frame.polytube([S(uv_add(ht_b, (0.04, 0.03 + 0.02 * i)), x), S(uv_add(dt_front, (-0.012, -0.035)), x),
                    S(lerp2(dt_front, dt_rear, 0.8), x * 1.1), S((0.02, 0.35), x * 1.2), S((-0.04, 0.40), -0.05)], 0.0028, MATTE, seg=8)
frame_ob = frame.build()

# ================================================================== CHAINSTAY (+ rear wheel)
cs = Part("Chainstay")
for side in (-1, 1):
    x_p = 0.045 * side
    x_a = 0.072 * side
    mid = lerp2(P, RA, 0.55)
    mid = (mid[0], mid[1] - 0.01)
    cs.tube(S(P, x_p), S(mid, 0.066 * side), 0.019, 0.015, BLACK, seg=20, sy=1.45)
    cs.tube(S(mid, 0.066 * side), S(RA, x_a), 0.015, 0.012, BLACK, seg=20, sy=1.3)
    cs.sphere(S(mid, 0.066 * side), 0.0152, BLACK, scale=(1, 1, 1.4))
    cs.hull([S(uv_add(RA, (math.cos(a) * 0.024, math.sin(a) * 0.024)), x_a + d)
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.004, 0.004)] +
            [S(uv_add(H0, (math.cos(a) * 0.015, math.sin(a) * 0.015)), x_a + d)
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.004, 0.004)] +
            [S(uv_add(RA, (0.07, 0.004)), 0.068 * side)], BLACK)
    cs.tube(S(H0, 0.079 * side), S(H0, 0.064 * side), 0.007, mat=STEEL, seg=12)
# chainstay protector (drive side) with a light graphic block
cs.hull([S(lerp2(P, RA, t), 0.066) + Vector((0.006, 0, d)) for t in (0.18, 0.78) for d in (-0.017, 0.017)] +
        [S(lerp2(P, RA, t), 0.066) + Vector((0.012, 0, d)) for t in (0.18, 0.78) for d in (-0.015, 0.015)], RUBBER)
cs.hull([S(lerp2(P, RA, t), 0.066) + Vector((0.0125, 0, d)) for t in (0.40, 0.55) for d in (-0.008, 0.008)] +
        [S(lerp2(P, RA, t), 0.066) + Vector((0.0135, 0, d)) for t in (0.40, 0.55) for d in (-0.008, 0.008)], ALLOY, smooth=False)
# yoke behind the BB
cs.hull([S(P, x) for x in (-0.05, 0.05)] + [S((P[0] - 0.08, P[1] - 0.012), x) for x in (-0.066, 0.066)] +
        [S((P[0] - 0.08, P[1] + 0.024), x) for x in (-0.06, 0.06)] + [S((P[0] - 0.01, P[1] - 0.026), x) for x in (-0.045, 0.045)], BLACK)
cs.tube(S(P, -0.053), S(P, 0.053), 0.008, mat=STEEL, seg=12)
# rear brake caliper (left)
cal_dir = (math.cos(math.radians(24)), math.sin(math.radians(24)))
cal_c = uv_add(RA, cal_dir, 0.092)
cal_t = (-cal_dir[1], cal_dir[0])
cs.hull([S(uv_add(cal_c, cal_t, s * 0.032), -0.066 + d) for s in (-1, 1) for d in (-0.013, 0.013)] +
        [S(uv_add(uv_add(cal_c, cal_dir, 0.017), cal_t, s * 0.026), -0.066 + d) for s in (-1, 1) for d in (-0.013, 0.013)], MATTE)
# long-cage derailleur (right)
up_j = uv_add(RA, (-0.022, -0.075))
lo_j = uv_add(RA, (0.020, -0.170))
cs.hull([S(uv_add(RA, (0.0, -0.012)), 0.074), S(uv_add(RA, (0.0, -0.012)), 0.084),
         S(uv_add(RA, (-0.045, -0.04)), 0.084), S(uv_add(RA, (-0.045, -0.04)), 0.074),
         S(uv_add(RA, (-0.03, -0.065)), 0.08)], MATTE)
for j in (up_j, lo_j):
    cs.tube(S(j, 0.050), S(j, 0.060), 0.017, mat=MATTE, seg=16)
for xx in (0.045, 0.064):
    cs.hull([S(uv_add(up_j, (math.cos(a) * 0.02, math.sin(a) * 0.02)), xx) for a in [k * 0.5 for k in range(13)]] +
            [S(uv_add(lo_j, (math.cos(a) * 0.022, math.sin(a) * 0.022)), xx) for a in [k * 0.5 for k in range(13)]] +
            [S(uv_add(up_j, (math.cos(a) * 0.02, math.sin(a) * 0.02)), xx + 0.003) for a in [k * 0.5 for k in range(13)]], MATTE)
cog_r = g["cog_teeth"] * 0.0127 / (2 * math.pi)
cs.torus(S(RA, 0.052), (1, 0, 0), cog_r + 0.002, 0.0035, CHAIN, seg=28, rseg=6, sy=1.4)
cs.tube(S(uv_add(RA, (0.004, -cog_r)), 0.054), S(uv_add(up_j, (0.017, 0.0)), 0.055), 0.0035, mat=CHAIN, seg=6)
cs.tube(S(uv_add(up_j, (-0.017, 0.0)), 0.055), S(uv_add(lo_j, (-0.018, 0.0)), 0.055), 0.0035, mat=CHAIN, seg=6)
cs_ob = cs.build(origin=S(P))


def wheel(name, rotor_x, rotor_r, cassette=False):
    w = Part(name)
    c = Vector((0, 0, 0))
    TUBE = 0.031
    tyre_R = WR - TUBE
    w.torus(c, (1, 0, 0), tyre_R, TUBE, RUBBER, seg=84, rseg=16, sy=1.0)
    # blocky enduro tread: paired centre blocks, transition and shoulder knobs
    rows = ((-9, 46, (0.016, 0.011, 0.0055), 0.0), (9, 46, (0.016, 0.011, 0.0055), 0.0),
            (-34, 46, (0.012, 0.012, 0.0055), 0.5), (34, 46, (0.012, 0.012, 0.0055), 0.5),
            (-60, 46, (0.010, 0.016, 0.006), 0.0), (60, 46, (0.010, 0.016, 0.006), 0.0))
    for b_deg, n, sz, off in rows:
        b = math.radians(b_deg)
        for k in range(n):
            a = 2 * math.pi * (k + off) / n
            rr = tyre_R + TUBE * math.cos(b)
            x = TUBE * math.sin(b)
            p = Vector((x, rr * math.cos(a), rr * math.sin(a)))
            radial = Vector((0, math.cos(a), math.sin(a)))
            nrm = (radial * math.cos(b) + Vector((math.sin(b), 0, 0))).normalized()
            M = mk.frame_from(nrm, up=Vector((1, 0, 0)))
            w.box(p + nrm * 0.002, (sz[1], sz[0], sz[2]), RUBBER, rot=M)
    # grey sidewall lettering band
    for side in (-1, 1):
        for k in range(2):
            a0 = math.pi * k + 0.6
            w.hull([Vector((side * 0.030, (WR - 0.045) * math.cos(a0 + t * 0.025), (WR - 0.045) * math.sin(a0 + t * 0.025))) for t in range(-10, 11)] +
                   [Vector((side * 0.0285, (WR - 0.054) * math.cos(a0 + t * 0.025), (WR - 0.054) * math.sin(a0 + t * 0.025))) for t in range(-10, 11)], GUM, smooth=False)
    # rim (29", wide)
    w.disc(c, (1, 0, 0), 0.3195, 0.296, 0.034, BLACK, seg=84)
    w.torus(c, (1, 0, 0), 0.3185, 0.0035, BLACK, seg=84, rseg=6, sy=4.5)
    # hub
    w.tube(Vector((-0.055, 0, 0)), Vector((0.055, 0, 0)), 0.012, mat=MATTE, seg=20)
    w.tube(Vector((-0.038, 0, 0)), Vector((0.038, 0, 0)), 0.020, 0.020, MATTE, seg=20)
    for xf in (-0.036, 0.032):
        w.disc(Vector((xf, 0, 0)), (1, 0, 0), 0.031, 0.012, 0.004, MATTE, seg=24)
    # 32 spokes
    for k in range(32):
        side = 1 if k % 2 else -1
        a_h = 2 * math.pi * k / 32
        lead = 1 if (k // 2) % 2 else -1
        a_r = a_h + lead * math.radians(34)
        hub = Vector((side * 0.034, 0.029 * math.cos(a_h), 0.029 * math.sin(a_h)))
        rim = Vector((side * 0.004, 0.298 * math.cos(a_r), 0.298 * math.sin(a_r)))
        w.tube(hub, rim, 0.0011, mat=STEEL, seg=5, caps=False)
    # rotor + spider
    w.disc(Vector((rotor_x, 0, 0)), (1, 0, 0), rotor_r, rotor_r - 0.018, 0.0018, STEEL, seg=56)
    for k in range(6):
        a = 2 * math.pi * k / 6
        w.hull([Vector((rotor_x + d, r * math.cos(a + s), r * math.sin(a + s)))
                for d in (-0.001, 0.001) for (r, s) in ((0.023, -0.25), (0.023, 0.25), (rotor_r - 0.014, -0.07), (rotor_r - 0.014, 0.07))], STEEL, smooth=False)
    if cassette:   # 10-51 wide range
        teeth = (51, 45, 39, 33, 28, 24, 21, 18, 16, 14, 12, 10)
        for i, t in enumerate(teeth):
            r = t * 0.0127 / (2 * math.pi)
            w.disc(Vector((0.026 + i * 0.0039, 0, 0)), (1, 0, 0), r, 0.017, 0.0018, ALLOY if i > 2 else MATTE, seg=max(t, 16))
    w.tube(Vector((-0.08, 0, 0)), Vector((0.08, 0, 0)), 0.006, mat=STEEL, seg=12)
    return w


rw_ob = wheel("RearWheel", -0.062, 0.090, cassette=True).build()
rw_ob.location = S(RA)
mk.parent_keep(rw_ob, cs_ob)

# ================================================================== SEATSTAY
ss = Part("Seatstay")
for side in (-1, 1):
    a = S(H0, 0.071 * side)
    b = S(B0, 0.054 * side)
    mid = (a + b) / 2 + Vector((0.008 * side, 0, 0))
    ss.tube(a, mid, 0.0115, 0.0135, FRAME_DK, seg=18, sy=1.35)
    ss.tube(mid, b, 0.0135, 0.0125, FRAME_DK, seg=18, sy=1.35)
    ss.sphere(mid, 0.0135, FRAME_DK, scale=(1, 1, 1.35))
    ss.sphere(a, 0.013, FRAME_DK)
    ss.sphere(b, 0.013, FRAME_DK)
br = lerp2(H0, B0, 0.90)
ss.tube(S(br, -0.058), S(br, 0.058), 0.009, mat=FRAME_DK, seg=14, sy=1.3)
ss_ob = ss.build(origin=S(H0))

# ================================================================== ROCKER
rk = Part("Rocker")
for side in (-1, 1):
    pts = []
    for (c, r) in ((R, 0.018), (B0, 0.014), (C0, 0.014)):
        for k in range(14):
            a = 2 * math.pi * k / 14
            for d in (-0.005, 0.005):
                pts.append(S(uv_add(c, (math.cos(a) * r, math.sin(a) * r)), 0.043 * side + d))
    rk.hull(pts, FRAME_DK)
for c, w_ in ((R, 0.05), (B0, 0.062), (C0, 0.05)):
    rk.tube(S(c, -w_), S(c, w_), 0.0065, mat=STEEL, seg=12)
rk_ob = rk.build(origin=S(R))

# ================================================================== COIL SHOCK
sdir = Vector((0, C0[0] - F[0], C0[1] - F[1])).normalized()   # front eye -> rear eye
Fv, Cv = S(F), S(C0)
up_s = Vector((0, -sdir.z, sdir.y))                              # perpendicular, roughly up
sb = Part("ShockBody")
sb.tube(Fv + Vector((-0.011, 0, 0)), Fv + Vector((0.011, 0, 0)), 0.012, mat=MATTE, seg=18)
sb.tube(Fv + sdir * 0.010, Fv + sdir * 0.100, 0.0195, mat=MATTE, seg=24)            # damper body
sb.tube(Fv + sdir * 0.030, Fv + sdir * 0.036, 0.030, mat=ALLOY, seg=28)             # preload collar
sb.tube(Fv + sdir * 0.100, Fv + sdir * 0.106, 0.0125, mat=MATTE, seg=18)            # seal head
# piggyback reservoir above the body
res0 = Fv + up_s * 0.034 + sdir * 0.012
sb.tube(res0, res0 + sdir * 0.075, 0.0165, mat=MATTE, seg=22)
sb.tube(res0 + sdir * 0.075, res0 + sdir * 0.085, 0.017, mat=LIME, seg=22)
sb.hull([Fv + sdir * 0.012 + up_s * 0.012 + Vector((x, 0, 0)) for x in (-0.01, 0.01)] +
        [res0 + up_s * -0.01 + Vector((x, 0, 0)) for x in (-0.01, 0.01)] +
        [res0 + sdir * 0.02 + up_s * -0.012 + Vector((x, 0, 0)) for x in (-0.01, 0.01)], MATTE)
sb.tube(Fv + sdir * 0.045 + up_s * 0.020, Fv + sdir * 0.045 + up_s * 0.026, 0.006, mat=LIME, seg=12)
sb_ob = sb.build(origin=Fv)

# coil spring: its own object whose local Z runs along the shock, so the game
# can squash it by scaling one axis. Origin at the preload collar.
SPRING_START = 0.036
SPRING_END = g["shock_eye"] - 0.024                  # retainer on the shaft end
spring_len = SPRING_END - SPRING_START
sp = Part("ShockSpring")
coils, wire, rad = 9.5, 0.0048, 0.0265
pts = []
nseg = int(coils * 22)
for i in range(nseg + 1):
    t = i / nseg
    a = 2 * math.pi * coils * t
    pts.append(Vector((rad * math.cos(a), rad * math.sin(a), spring_len * t)))
for a, b in zip(pts, pts[1:]):
    sp.tube(a, b, wire, mat=SPRING, seg=7, caps=False)
spring_ob = sp.build()
Mspring = mk.frame_from(sdir)
spring_ob.matrix_world = Matrix.Translation(Fv + sdir * SPRING_START) @ Mspring
mk.parent_keep(spring_ob, sb_ob)

sh = Part("ShockShaft")
sh.tube(Cv + Vector((-0.011, 0, 0)), Cv + Vector((0.011, 0, 0)), 0.012, mat=MATTE, seg=18)
sh.tube(Cv - sdir * 0.008, Cv - sdir * 0.022, 0.014, mat=MATTE, seg=20)
sh.tube(Cv - sdir * 0.022, Cv - sdir * 0.027, 0.031, mat=MATTE, seg=28)            # spring retainer
sh.tube(Cv - sdir * 0.027, Cv - sdir * 0.120, 0.0068, mat=STEEL, seg=16)           # shaft into the body
sh.tube(Cv - sdir * 0.040, Cv - sdir * 0.052, 0.0135, mat=RUBBER, seg=16)          # bottom-out bumper
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

leg_spacing = 0.0620
crown_pt = S(g["fork_crown"])
leg_top = S(FA) + axis * g["fork_a2c"]
fu = Part("ForkUpper")
fu.tube(crown_pt, S(g["stem_clamp"]) + axis * 0.024, 0.0172, mat=MATTE, seg=20)
fu.tube(S(g["head_tube_top"]), S(g["stem_clamp"]) - axis * 0.020, 0.0185, mat=MATTE, seg=20)
for p in (S(g["head_tube_top"]) + axis * 0.004, S(g["head_tube_bottom"]) - axis * 0.004):
    fu.tube(p - axis * 0.004, p + axis * 0.004, 0.0315, mat=MATTE, seg=24)
crown = []
for side in (-1, 1):
    for k in range(12):
        a = 2 * math.pi * k / 12
        ring = Vector((math.cos(a) * 0.028, 0, 0)) + nrm * math.sin(a) * 0.028
        for d in (-0.014, 0.018):
            crown.append(leg_top + Vector((side * leg_spacing, 0, 0)) + ring + axis * d)
for k in range(12):
    a = 2 * math.pi * k / 12
    ring = Vector((math.cos(a) * 0.026, 0, 0)) + nrm * math.sin(a) * 0.026
    for d in (-0.012, 0.022):
        crown.append(crown_pt + ring + axis * d)
fu.hull(crown, FORK_GREY)
STANCH_LEN = 0.36
for side in (-1, 1):
    top = leg_top + Vector((side * leg_spacing, 0, 0))
    fu.tube(top + axis * 0.016, top - axis * STANCH_LEN, 0.019, mat=BLACK, seg=24)
    fu.tube(top + axis * 0.016, top + axis * 0.03, 0.017, mat=FORK_GREY, seg=20)     # top caps
fu.tube(leg_top + Vector((0.062, 0, 0)) + axis * 0.03, leg_top + Vector((0.062, 0, 0)) + axis * 0.038, 0.012, mat=LIME, seg=14)
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
grip = g["grip"]
hw = g["bar_width"] / 2
bar_pts = [
    S(grip, -hw), S(uv_add(grip, (0.006, -0.002)), -0.22), S(uv_add(g["bar_clamp"], (0.0, 0.008)), -0.11),
    S(g["bar_clamp"], -0.04), S(g["bar_clamp"], 0.04), S(uv_add(g["bar_clamp"], (0.0, 0.008)), 0.11),
    S(uv_add(grip, (0.006, -0.002)), 0.22), S(grip, hw)]
for i, (a, b) in enumerate(zip(bar_pts, bar_pts[1:])):
    r0 = 0.0175 if i in (2, 3, 4) else 0.0111
    r1 = 0.0175 if i in (1, 2, 3) else 0.0111
    fu.tube(a, b, r0, r1, MATTE, seg=18)
for p in bar_pts[1:-1]:
    fu.sphere(p, 0.0112, MATTE, seg=12, rings=8)
for side in (-1, 1):
    g0 = S(grip, side * (hw - 0.135))
    g1 = S(grip, side * hw)
    fu.tube(g0, g1, 0.0165, mat=RUBBER, seg=20)
    fu.tube(g0 - Vector((side * 0.008, 0, 0)), g0, 0.0175, mat=MATTE, seg=20)
    lc = S(uv_add(grip, (0.002, -0.002)), side * (hw - 0.165))
    fu.tube(lc - Vector((0.012, 0, 0)), lc + Vector((0.012, 0, 0)), 0.016, mat=MATTE, seg=14)
    fu.hull([lc + Vector((side * 0.006, 0, 0)) + Vector((0, 0.010, 0.012)),
             lc + Vector((-side * 0.006, 0, 0)) + Vector((0, 0.010, 0.012)),
             lc + Vector((side * 0.01, 0.045, 0.020)), lc + Vector((-side * 0.01, 0.045, 0.020)),
             lc + Vector((side * 0.028, 0.035, 0.026)), lc + Vector((side * 0.012, 0.025, 0.005))], MATTE)
    fu.hull([lc + Vector((side * 0.004, 0.030, 0.0)), lc + Vector((side * 0.006, 0.040, -0.004)),
             lc + Vector((side * 0.075, 0.048, -0.030)), lc + Vector((side * 0.078, 0.042, -0.034)),
             lc + Vector((side * 0.004, 0.034, -0.006)), lc + Vector((side * 0.076, 0.052, -0.026))], MATTE)
    # shifter / dropper lever under the bar
    sl = S(uv_add(grip, (-0.01, -0.02)), side * (hw - 0.19))
    fu.hull([sl + Vector((x, y, z)) for x in (-0.01, 0.01) for y in (-0.02, 0.02) for z in (-0.008, 0.008)], MATTE, smooth=False)
# cables: from the levers, a short loop down in front of the head tube
for side in (-1, 1):
    fu.polytube([S(uv_add(grip, (0.01, -0.012)), side * (hw - 0.17)),
                 S(uv_add(g["bar_clamp"], (0.03, -0.05)), side * 0.11),
                 S(uv_add(g["head_tube_top"], (0.07, -0.05)), side * 0.05),
                 S(uv_add(g["head_tube_bottom"], (0.045, 0.02)), side * 0.034)], 0.0028, MATTE, seg=8)
fu_ob = fu.build(origin=steer_origin)

fl = Part("ForkLower")
fa = S(FA)
SEAL_T = g["fork_a2c"] - 0.016 - 0.028 - g["fork_travel"] - 0.022
for side in (-1, 1):
    base = fa + Vector((side * leg_spacing, 0, 0))
    fl.tube(base - axis * 0.014, base + axis * SEAL_T, 0.0255, 0.0265, FORK_GREY, seg=24)
    fl.tube(base + axis * (SEAL_T - 0.001), base + axis * (SEAL_T + 0.014), 0.0235, 0.021, MATTE, seg=24)
    fl.hull([base + Vector((d, 0, 0)) + Vector((0, math.cos(a) * 0.023, math.sin(a) * 0.023))
             for a in [k * math.pi / 6 for k in range(12)] for d in (-0.009, 0.009)] +
            [base + axis * 0.07 + Vector((d, 0, 0)) + nrm * s for d in (-0.013, 0.013) for s in (-0.022, 0.022)], FORK_GREY)
    # graphic panel on the lowers
    fl.hull([base + axis * t + nrm * 0.0255 + Vector((side * 0.0, 0, 0)) + Vector((x, 0, 0))
             for t in (0.10, 0.28) for x in (-0.010, 0.010)] +
            [base + axis * t + nrm * 0.0262 + Vector((x, 0, 0)) for t in (0.10, 0.28) for x in (-0.010, 0.010)], MATTE, smooth=False)
arch = []
for i in range(9):
    t = i / 8
    x = -leg_spacing + 2 * leg_spacing * t
    lift = math.sin(math.pi * t)
    arch.append(fa + Vector((x * (1 - 0.12 * lift), 0, 0)) + axis * (SEAL_T - 0.07 + 0.05 * lift) - nrm * (0.02 + 0.022 * lift))
fl.polytube(arch, 0.012, FORK_GREY, seg=14)
fdir = (-nrm * 0.55 + axis * 0.835).normalized()
fcal = fa + Vector((-0.068, 0, 0)) + fdir * 0.10
ftan = Vector((1, 0, 0)).cross(fdir)
fl.hull([fcal + ftan * s * 0.032 + Vector((d, 0, 0)) for s in (-1, 1) for d in (-0.013, 0.013)] +
        [fcal + fdir * 0.017 + ftan * s * 0.026 + Vector((d, 0, 0)) for s in (-1, 1) for d in (-0.013, 0.013)], MATTE)
# mudguard over the top-front of the tyre, bolted to the arch
mg = []
for i in range(13):
    a = math.radians(48 + i * 7.5)        # angle round the wheel, from forward
    rr = WR + 0.022
    prof = []
    for k in range(9):
        t = -1 + 2 * k / 8
        prof.append(fa + Vector((t * 0.040, rr * math.cos(a) * (1 - 0.06 * t * t), rr * math.sin(a) * (1 - 0.06 * t * t))))
    for k in range(8, -1, -1):
        t = -1 + 2 * k / 8
        prof.append(fa + Vector((t * 0.038, (rr - 0.004) * math.cos(a) * (1 - 0.06 * t * t), (rr - 0.004) * math.sin(a) * (1 - 0.06 * t * t))))
    mg.append(prof)
fl.loft(mg, MATTE)
fl_ob = fl.build(origin=fa)

fw_ob = wheel("FrontWheel", -0.062, 0.100).build()
fw_ob.location = fa
mk.parent_keep(fu_ob, steer)
mk.parent_keep(fl_ob, steer)
mk.parent_keep(fw_ob, fl_ob)

# ================================================================== CRANKS + PEDALS
L = g["crank_len"]
cr = Part("Cranks")
cr.tube(S(BB, -0.078), S(BB, 0.078), 0.012, mat=STEEL, seg=16)
cr.disc(S(BB, 0.050), (1, 0, 0), ring_r - 0.002, ring_r - 0.013, 0.0035, MATTE, seg=64)
nt = g["chainring_teeth"]
for k in range(nt):
    a = 2 * math.pi * k / nt
    p = S(uv_add(BB, (math.cos(a) * (ring_r + 0.001), math.sin(a) * (ring_r + 0.001))), 0.050)
    M = mk.frame_from(Vector((0, math.cos(a), math.sin(a))), up=Vector((1, 0, 0)))
    cr.box(p, (0.0035, 0.006, 0.007), MATTE, rot=M)
cr.disc(S(BB, 0.046), (1, 0, 0), ring_r - 0.010, 0.016, 0.004, MATTE, seg=40)
for side, ang in ((1, 0.0), (-1, math.pi)):
    end = uv_add(BB, (math.cos(ang) * L, math.sin(ang) * L))
    pts = []
    for (c, r) in ((BB, 0.021), (end, 0.012)):
        for k in range(14):
            a = 2 * math.pi * k / 14
            for d in (-0.009, 0.009):
                pts.append(S(uv_add(c, (math.cos(a) * r, math.sin(a) * r * 1.1)), side * 0.074 + d))
    cr.hull(pts, MATTE)
cr_ob = cr.build(origin=S(BB))


def pedal(name, side):
    end = (BB[0] + side * L, BB[1])
    p = Part(name)
    o = S(end, side * 0.083)
    p.tube(o - Vector((side * 0.002, 0, 0)), o + Vector((side * 0.11, 0, 0)), 0.006, mat=STEEL, seg=10)
    c = o + Vector((side * 0.060, 0, 0))
    p.hull([c + Vector((x, y, z)) for x in (-0.05, 0.05) for y in (-0.055, 0.055) for z in (-0.009, 0.009)], MATTE, smooth=False)
    for x in (-0.042, -0.014, 0.014, 0.042):
        for y in (-0.047, 0.047):
            for z in (-1, 1):
                p.tube(c + Vector((x, y, z * 0.009)), c + Vector((x, y, z * 0.0135)), 0.0017, mat=STEEL, seg=6)
    return p.build(origin=o)


pr_ob = pedal("PedalR", 1)
pl_ob = pedal("PedalL", -1)
mk.parent_keep(pr_ob, cr_ob)
mk.parent_keep(pl_ob, cr_ob)

for name in ("ChainTop", "ChainBot"):
    c = Part(name)
    n = 70
    for k in range(n):
        y0 = k / n
        y1 = (k + 0.55) / n
        c.box(Vector((0.0, (y0 + y1) / 2, 0.0)), (0.0075 if k % 2 else 0.0058, (y1 - y0) * 1.6, 0.0072), CHAIN)
    ob = c.build()
    ob.location = S(BB, 0.052)

bpy.context.view_layer.update()
out_glb = os.path.join(HERE, "..", "game", "assets", "bike.glb")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_apply=True,
                          export_yup=True, export_animations=False, export_lights=False, export_cameras=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "bike.blend"))
print("exported", os.path.normpath(out_glb))
