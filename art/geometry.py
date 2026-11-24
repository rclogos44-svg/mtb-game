"""Bike geometry and rear-suspension kinematics.

Single source of truth for the bike's hard points. Both the Blender build
script and the Godot physics read the JSON this writes, so the 3D model and
the suspension maths always agree.

Side-view coordinates: u = forward (m), v = up (m), origin on the ground
directly below the bottom bracket. Lateral offsets (x) are given separately.

Rear suspension is a linkage-driven single pivot (like the reference photo):
  chainstay  : pivots on the frame at P, carries the rear axle and point H
  seatstay   : link from H (on the chainstay) up to B (on the rocker)
  rocker     : pivots on the seat tube at R, carries B and C
  shock      : from C (rocker) down to F (down-tube mount)

Run:  python3 geometry.py   (writes ../game/assets/geometry.json)
"""
import json
import math
import os

# ---------------------------------------------------------------- hard points
WHEEL_R = 0.372          # 29 x 2.4 tyre, outer radius
BB = (0.0, 0.337)        # bottom bracket (unloaded, full extension), 35 mm drop
REAR_AXLE = (-0.440, 0.372)
FRONT_AXLE = (0.830, 0.372)

HEAD_ANGLE = 65.0        # degrees from horizontal
FORK_OFFSET = 0.044      # rake
FORK_A2C = 0.583         # axle-to-crown, along steering axis
FORK_TRAVEL = 0.160
CROWN_TO_HT = 0.015
HEAD_TUBE_LEN = 0.110
STEM_SPACER = 0.020
STEM_LEN = 0.045
BAR_RISE = 0.025
BAR_WIDTH = 0.780

P = (0.000, 0.430)      # main pivot
H0 = (-0.405, 0.425)    # seatstay pivot on chainstay
R = (0.004, 0.630)      # rocker pivot (boss just ahead of the seat tube)
B0 = (-0.1042, 0.6494)  # rocker <-> seatstay
F = None                 # shock front mount: set from C0 below (on the frame brace)

SHOCK_EYE = 0.210        # eye-to-eye (210 x 55 coil shock)
SHOCK_STROKE = 0.055
TARGET_TRAVEL = 0.160    # rear wheel travel we want from that stroke

CRANK_LEN = 0.170
CHAINRING_T = 32
COG_T = 15


def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def mul(a, s): return (a[0] * s, a[1] * s)
def length(a): return math.hypot(a[0], a[1])
def rot(a, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (a[0] * c - a[1] * s, a[0] * s + a[1] * c)
def rot_about(p, c, ang): return add(c, rot(sub(p, c), ang))


def circle_intersect(c0, r0, c1, r1, prefer):
    """Intersection of two circles, returning the one closest to `prefer`."""
    d = length(sub(c1, c0))
    if d > r0 + r1 or d < abs(r0 - r1) or d == 0:
        return None
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(max(r0 * r0 - a * a, 0.0))
    ex = mul(sub(c1, c0), 1.0 / d)
    pm = add(c0, mul(ex, a))
    perp = (-ex[1], ex[0])
    p1, p2 = add(pm, mul(perp, h)), add(pm, mul(perp, -h))
    return p1 if length(sub(p1, prefer)) < length(sub(p2, prefer)) else p2


def solve_linkage(theta, C0):
    """Chainstay rotated by theta (negative = axle moves up). Returns state."""
    axle = rot_about(REAR_AXLE, P, theta)
    H = rot_about(H0, P, theta)
    ss_len = length(sub(B0, H0))
    rb = length(sub(B0, R))
    B = circle_intersect(H, ss_len, R, rb, B0)
    if B is None:
        return None
    phi = math.atan2(B[1] - R[1], B[0] - R[0]) - math.atan2(B0[1] - R[1], B0[0] - R[0])
    C = rot_about(C0, R, phi)
    return {"axle": axle, "H": H, "B": B, "C": C, "phi": phi,
            "shock_len": length(sub(C, F))}


def sweep(C0, steps=60, theta_max=-0.45):
    out = []
    for i in range(steps + 1):
        th = theta_max * i / steps
        s = solve_linkage(th, C0)
        if s is None:
            break
        s["theta"] = th
        s["wheel_travel"] = s["axle"][1] - REAR_AXLE[1]
        s["stroke"] = SHOCK_EYE - s["shock_len"]
        out.append(s)
    return out


def downtube_mount_for(C0):
    """Point on the top of the down tube that is one shock length from C0."""
    a = (0.030, 0.395)   # down tube top surface, near the BB
    b = (0.430, 0.830)   # ... near the head tube
    best = None
    for i in range(0, 401):
        t = i / 400.0
        p = add(a, mul(sub(b, a), t))
        err = abs(length(sub(C0, p)) - SHOCK_EYE)
        if best is None or err < best[0]:
            best = (err, p)
    return best[1] if best[0] < 0.001 else None


def choose_C0():
    """Shock eye on the rocker. Found by a wider search over rocker shapes and
    shock angles (shock rising toward the front, clear of the seat tube and
    top tube, ~160 mm travel, progressive leverage). Fixed so builds repeat."""
    global F
    C0 = add(R, (0.060 * math.cos(math.radians(130)), 0.060 * math.sin(math.radians(130))))
    F = add(C0, (SHOCK_EYE * math.cos(math.radians(2)), SHOCK_EYE * math.sin(math.radians(2))))  # near-flat shock
    tab = sweep(C0, steps=90, theta_max=-0.55)
    ws = [s["wheel_travel"] for s in tab]
    st = [s["stroke"] for s in tab]
    k_end = next(i for i, s in enumerate(st) if s >= SHOCK_STROKE)
    lr_s = (ws[4] - ws[0]) / (st[4] - st[0])
    lr_e = (ws[k_end] - ws[k_end - 4]) / (st[k_end] - st[k_end - 4])
    return (0.0, C0, ws[k_end], lr_s, lr_e)


def main():
    best = choose_C0()
    _, C0, travel, lr_s, lr_e = best
    tab = sweep(C0, steps=90, theta_max=-0.55)
    # trim table at full stroke
    table = []
    for s in tab:
        table.append({
            "theta": s["theta"], "phi": s["phi"],
            "wheel_travel": s["wheel_travel"], "stroke": s["stroke"],
            "axle": s["axle"], "H": s["H"], "B": s["B"], "C": s["C"],
        })
        if s["stroke"] >= SHOCK_STROKE:
            break

    # front end
    hr = math.radians(HEAD_ANGLE)
    axis = (-math.cos(hr), math.sin(hr))           # steering axis, pointing up
    normal = (math.sin(hr), math.cos(hr))          # forward, perpendicular to axis
    axis_pt = add(FRONT_AXLE, mul(normal, -FORK_OFFSET))  # axle projected on axis
    crown = add(axis_pt, mul(axis, FORK_A2C))
    ht_bot = add(crown, mul(axis, CROWN_TO_HT))
    ht_top = add(ht_bot, mul(axis, HEAD_TUBE_LEN))
    stem_c = add(ht_top, mul(axis, STEM_SPACER))
    bar = add(stem_c, (STEM_LEN, 0.0))
    grip = add(bar, (-0.015, BAR_RISE))

    geo = {
        "units": "metres; u forward, v up, origin on ground under BB",
        "wheel_radius": WHEEL_R,
        "bb": BB, "rear_axle": REAR_AXLE, "front_axle": FRONT_AXLE,
        "wheelbase": FRONT_AXLE[0] - REAR_AXLE[0],
        "head_angle": HEAD_ANGLE, "fork_offset": FORK_OFFSET,
        "steer_axis": axis, "steer_normal": normal, "steer_axis_point": axis_pt,
        "fork_crown": crown, "head_tube_bottom": ht_bot, "head_tube_top": ht_top,
        "stem_clamp": stem_c, "bar_clamp": bar, "grip": grip, "bar_width": BAR_WIDTH,
        "fork_travel": FORK_TRAVEL, "fork_a2c": FORK_A2C,
        "P": P, "H0": H0, "R": R, "B0": B0, "C0": C0, "F": F,
        "shock_eye": SHOCK_EYE, "shock_stroke": SHOCK_STROKE,
        "rear_travel": table[-1]["wheel_travel"],
        "crank_len": CRANK_LEN, "chainring_teeth": CHAINRING_T, "cog_teeth": COG_T,
        "rear_table": table,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game", "assets", "geometry.json")
    with open(out, "w") as f:
        json.dump(geo, f, indent=1)
    print("C0 =", tuple(round(c, 4) for c in C0))
    print("rear travel %.1f mm, leverage %.2f -> %.2f (%.0f%% progressive)"
          % (table[-1]["wheel_travel"] * 1000, lr_s, lr_e, (lr_s - lr_e) / lr_s * 100))
    print("crown", [round(c, 3) for c in crown], "grip", [round(c, 3) for c in grip])
    print("wrote", os.path.normpath(out))


if __name__ == "__main__":
    main()
