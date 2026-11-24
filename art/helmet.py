"""Mountain-bike full-face helmet, built in the head bone's frame.

Construction follows real downhill / enduro full-face helmets (see the
reference notes in the README): one moulded shell that runs from the crown
round the cheeks into the chin bar, a big open eye port for separate goggles,
a bolt-on peak, a chin bar with a large mouth vent backed by mesh, real
ventilation openings that show the black foam liner, rubber trim on the eye
port and neck opening, and padding inside.

    build_helmet(part, Mr, stage)   stage: "blockout" | "final"

Head-local axes: X = rider's right, Y = up from the top of the neck,
Z = forward. Units are metres.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import meshkit as mk

D = math.radians

# ------------------------------------------------------------------ dimensions
# Size M downhill lid: ~300 mm long without the chin bar, ~250 mm wide,
# top ~25 mm above the head, chin bar ~45 mm clear of the mouth.
CY, CZ = 0.106, -0.010           # shell centre (above the neck joint, slightly back)
RX, RY, RZ = 0.124, 0.140, 0.162  # half width, half height, half length
SHELL_T = 0.024                  # shell + EPS liner thickness


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def base_shape(phi, th):
    """Smooth underlying form of the shell. phi: angle round the head (0 = front, +90 = right).
    th: angle down from the crown (0 = top)."""
    sp, cp = math.sin(phi), math.cos(phi)
    st, ct = math.sin(th), math.cos(th)
    front = max(0.0, cp)
    wc = front ** 1.2 * smooth(D(100), D(138), th)
    # chin bar stays wide right down to its underside (no V at the bottom)
    st_w = st + (max(st, 0.86) - st) * wc
    x = RX * st_w * sp
    y = CY + RY * ct
    z = CZ + RZ * st * cp
    # flatter crown: pull the top down a little (superellipse-ish profile)
    y -= 0.010 * max(0.0, ct) ** 3
    # flatter cheeks low on the sides (real shells are not round there)
    side = abs(sp)
    x *= 1.0 - 0.07 * side * smooth(D(95), D(135), th)
    # rear lip: the back of the shell kicks out a little over the nape
    back = max(0.0, -cp)
    lip = back ** 3 * smooth(D(95), D(118), th)
    z -= 0.014 * lip
    # chin bar: front-lower region pushed forward and down, narrowed, with a
    # forward-sloping lower face
    w = wc
    z += 0.122 * w
    y -= 0.036 * w
    x *= 1.0 - 0.04 * w
    # chin bar prow: a V-shaped front (two flat facets meeting on the centre line)
    zf = CZ + RZ + 0.102 - 0.55 * abs(x)
    if w > 0.0 and z > zf - 0.012:
        z = zf - 0.012 + 0.012 * math.tanh((z - (zf - 0.012)) / 0.012)
    # underside of the chin bar runs nearly level back toward the jaw
    y_floor = -0.090
    if y < y_floor + 0.02 and w > 0.0:
        y = y + (y_floor + 0.02 - 0.02 * math.exp((y - (y_floor + 0.02)) / 0.02) - y) * w
    return Vector((x, y, z))


def step(x, width):
    return 0.5 * (1.0 + math.tanh(x / width))


def features(phi, th):
    """Moulded detail on the smooth form, as raised height (m): a side
    character line, cheek creases, a lip along the lower edge and two low
    crown ridges. Kept clear of the openings' edges."""
    pd, td = math.degrees(phi), math.degrees(th)
    apd = abs(pd)
    h = 0.0
    tb = 66.0 + 0.15 * apd
    side = step(apd - 64.0, 5.0) * (1.0 - step(apd - 165.0, 5.0))
    h += 0.0045 * step(tb - td, 2.0) * side
    if 30.0 < apd < 120.0 and td > 100.0:
        line = 66.0 + (td - 110.0) * 1.1
        h += 0.0045 * step(line - apd, 2.0) * step(td - 106.0, 2.0)
    tm = math.degrees(th_max(phi))
    h += 0.0045 * step(td - (tm - 5.0), 1.0)
    for pc in (-8.5, 8.5):
        if 6.0 < td < 66.0:
            fade = step(td - 12.0, 3.0) * (1.0 - step(td - 58.0, 3.0))
            h += 0.0055 * fade * (1.0 - step(abs(pd - pc) - 3.0, 1.0))
    return h


def shape(phi, th):
    """Outer shell surface: smooth form + moulded detail (raised radially)."""
    return grow(base_shape(phi, th), features(phi, th))


def th_max(phi):
    """Lower edge: low behind (covers the base of the skull), rising along the
    jaw, lowest again under the chin bar."""
    f = (1 + math.cos(phi)) / 2
    ear = math.exp(-((abs(phi) - D(102)) / D(24)) ** 2)
    return D(119 + 31 * f ** 1.6 - 7 * ear)


def grow(v, g):
    c = Vector((0, CY, CZ))
    d = v - c
    return c + d * (1.0 + g / d.length)


def superellipse(phi, th, c_phi, c_th, h_phi, h_th, n=4.0):
    return (abs(phi - c_phi) / h_phi) ** n + (abs(th - c_th) / h_th) ** n < 1.0


# ------------------------------------------------------------------ openings
EYE_PORT = (0.0, D(92), D(58), D(16.5), 5.0)            # phi, th, half-w, half-h, roundness
MOUTH = (0.0, D(126), D(18), D(8.5), 3.0)


def openings(stage):
    """Holes cut through the shell: (c_phi, c_th, h_phi, h_th, n)."""
    holes = [EYE_PORT]
    if stage == "final":
        holes.append(MOUTH)
        for s in (-1, 1):
            holes += [
                (s * D(19), D(34), D(3.2), D(10), 2.5),      # crown vents outside the ridges
                (s * D(44), D(46), D(5), D(6), 2.5),
                (s * D(160), D(86), D(5), D(3.5), 2.5),      # rear exhausts
                (s * D(141), D(72), D(4), D(5), 2.5),
                (s * D(37), D(128), D(3.5), D(6.5), 2.5),    # chin bar side vents
            ]
        holes.append((0.0, D(36), D(2.6), D(10), 2.5))     # centre crown vent
    return holes


# ------------------------------------------------------------------ materials
def materials(stage):
    if stage == "blockout":
        clay = mk.material("HelmetClay", (0.45, 0.45, 0.46), roughness=0.7)
        return {k: clay for k in ("shell", "peak", "trim", "liner", "pad", "mesh", "bolt", "graphic", "pin")}
    return {
        "shell": mk.material("HelmetPaint", (0.010, 0.010, 0.012), roughness=0.16),
        "peak": mk.material("HelmetPeak", (0.014, 0.014, 0.016), roughness=0.45),
        "trim": mk.material("HelmetRubber", (0.006, 0.006, 0.007), roughness=0.9),
        "liner": mk.material("HelmetEPS", (0.045, 0.045, 0.05), roughness=0.95),
        "pad": mk.material("HelmetPad", (0.10, 0.10, 0.11), roughness=1.0),
        "mesh": mk.material("HelmetMesh", (0.035, 0.035, 0.04), metallic=0.4, roughness=0.55),
        "bolt": mk.material("HelmetBolt", (0.45, 0.46, 0.48), metallic=1.0, roughness=0.3),
        "graphic": mk.material("HelmetGraphicGrey", (0.11, 0.115, 0.125), roughness=0.3),
        "pin": mk.material("HelmetPinstripe", (0.70, 0.70, 0.70), roughness=0.35),
    }


# ------------------------------------------------------------------ builders
def _solidify(bm, name, mats, thickness, offset, levels, outward=None, rim_mat_offset=2):
    """bmesh surface -> solidify (inner / rim materials) -> subdivision -> mesh."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if outward is not None:
        bm.faces.ensure_lookup_table()
        f0 = bm.faces[len(bm.faces) // 3]
        if f0.normal.dot(outward(f0.calc_center_median())) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    so = ob.modifiers.new("Solid", "SOLIDIFY")
    so.thickness = thickness
    so.offset = offset
    so.use_rim = True
    so.use_even_offset = False
    so.use_quality_normals = True
    so.material_offset = 1
    so.material_offset_rim = rim_mat_offset
    if levels:
        ss = ob.modifiers.new("Sub", "SUBSURF")
        ss.levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    em = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    return em


def _hole_value(phi, th, h):
    c_phi, c_th, h_phi, h_th, n = h
    return (abs(phi - c_phi) / h_phi) ** n + (abs(th - c_th) / h_th) ** n


def build_shell(p, Mr, stage, M):
    """One closed, seamless moulded shell (grid wraps all the way round and
    closes at a pole on the crown). Openings are cut, then their edge
    vertices are snapped onto the opening's smooth outline."""
    holes = openings(stage)
    NP, NT = 200, 100
    bm = bmesh.new()
    par = {}

    def ang(i, j):
        phi = 2 * math.pi * i / NP - math.pi
        return phi, (j + 1) / NT * th_max(phi)

    pole = bm.verts.new(shape(0.0, 0.0))
    par[pole] = (0.0, 0.0)
    rows = []
    for j in range(NT):
        row = []
        for i in range(NP):
            phi, th = ang(i, j)
            v = bm.verts.new(shape(phi, th))
            par[v] = (phi, th)
            row.append(v)
        rows.append(row)

    def keep(fi, fj):
        phi = 2 * math.pi * fi / NP - math.pi
        th = (fj + 1) / NT * th_max(phi)
        return not any(_hole_value(phi, th, h) < 1.0 for h in holes)

    for i in range(NP):
        bm.faces.new([pole, rows[0][(i + 1) % NP], rows[0][i]])
    for j in range(NT - 1):
        for i in range(NP):
            if keep(i + 0.5, j + 0.5):
                i2 = (i + 1) % NP
                bm.faces.new([rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]])
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    # snap opening edges onto the smooth outline
    rim = set(rows[NT - 1])
    for v in bm.verts:
        if v in rim or not v.is_boundary:
            continue
        phi, th = par[v]
        hbest = min(holes, key=lambda h: abs(_hole_value(phi, th, h) - 1.0))
        c_phi, c_th, h_phi, h_th, n = hbest
        du, dv = (phi - c_phi) / h_phi, (th - c_th) / h_th
        # move along the grid line that crosses the edge (keeps faces from folding)
        if abs(dv) >= abs(du):
            r = max(0.0, 1.0 - abs(du) ** n) ** (1.0 / n)
            th = c_th + math.copysign(h_th * r, dv)
        else:
            r = max(0.0, 1.0 - abs(dv) ** n) ** (1.0 / n)
            phi = c_phi + math.copysign(h_phi * r, du)
        v.co = shape(phi, th)
    em = _solidify(bm, "helmet_shell", [M["shell"], M["liner"], M["trim"]], SHELL_T, -1.0, 1,
                   outward=lambda c: c - Vector((0, CY, CZ)))
    p.add_mesh(em, [M["shell"], M["liner"], M["trim"]], matrix=Mr)


def build_peak(p, Mr, stage, M):
    """Bolt-on peak: wide, sweeps down at the sides to the temple screws,
    projects well forward with a slight upturn and a raised centre rib; two
    vent cut-outs in the final version."""
    NU, NV = 49, 17

    def base(u):
        phi = D(62 * u)
        th = D(58 + 11 * u * u)
        return grow(shape(phi, th), 0.002), phi

    def pt(i, j):
        u = -1 + 2 * i / (NU - 1)
        v = j / (NV - 1)
        b, phi = base(u)
        d = Vector((math.sin(phi) * 0.22, 0.30, math.cos(phi))).normalized()   # angled up, as on DH lids
        length = 0.124 * (1.0 - 0.30 * u ** 2 - 0.45 * u ** 4)              # squarer corners
        q = b + d * length * v
        q.y += 0.011 * math.exp(-(u / 0.12) ** 2) * min(1.0, v * 2.5)        # raised centre rib
        q.y += 0.007 * v ** 2 * (1 - 0.5 * u * u)                              # lip turns up
        q.y -= 0.014 * max(0.0, abs(u) - 0.65) / 0.35 * v                      # wings sweep down
        return q

    def keep(fi, fj):
        if stage != "final":
            return True
        u = -1 + 2 * fi / (NU - 1)
        v = fj / (NV - 1)
        for c in (-0.40, 0.40):
            if abs((u - c) / 0.13) ** 2.5 + abs((v - 0.52) / 0.20) ** 2.5 < 1.0:
                return False
        return True

    bm = bmesh.new()
    grid = [[bm.verts.new(pt(i, j)) for j in range(NV)] for i in range(NU)]
    for i in range(NU - 1):
        for j in range(NV - 1):
            if keep(i + 0.5, j + 0.5):
                bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    em = _solidify(bm, "helmet_peak", [M["peak"], M["peak"], M["peak"]], 0.005, 0.0, 1,
                   outward=lambda c: Vector((0, 1, 0)))
    p.add_mesh(em, [M["peak"], M["peak"], M["peak"]], matrix=Mr)
    for u in (-0.97, 0.97, 0.0):
        b, _ = base(u)
        n = (b - Vector((0, CY, CZ))).normalized()
        r = 0.009 if u else 0.007
        p.tube(Mr @ (b - n * 0.002), Mr @ (b + n * 0.008), r,
               mat=M["bolt"] if stage == "final" else M["peak"], seg=16)


def build_mouth_mesh(p, Mr, stage, M):
    """Stainless/plastic mesh set just inside the mouth opening."""
    if stage != "final":
        return
    c_phi, c_th, h_phi, h_th, _ = MOUTH
    rows = []
    for a in range(9):
        ph = c_phi + h_phi * 1.15 * (a / 4 - 1)
        row = []
        for b in range(7):
            th = c_th + h_th * 1.15 * (b / 3 - 1)
            row.append(Mr @ grow(shape(ph, th), -0.012))
        rows.append(row)
    bm = bmesh.new()
    vs = [[bm.verts.new(v) for v in row] for row in rows]
    for a in range(8):
        for b in range(6):
            bm.faces.new([vs[a][b], vs[a + 1][b], vs[a + 1][b + 1], vs[a][b + 1]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    p._merge(bm, M["mesh"], smooth=True)
    # moulded bars across the opening (part of the shell)
    for k in (-0.35, 0.35):
        th = c_th + h_th * k
        pts = [Mr @ grow(shape(c_phi + h_phi * (t / 5 - 1) * 0.92, th), -0.010) for t in range(11)]
        p.polytube(pts, 0.0032, M["shell"], seg=8)


def build_padding(p, Mr, stage, M):
    """Comfort liner and cheek pads, seen round the eye port, mouth and neck."""
    if stage != "final":
        return
    secs = []
    for k in range(37):
        phi = D(-150 + 300 * k / 36)
        sec = []
        for j in range(8):
            th = D(70 + 50 * j / 7)
            sec.append(Mr @ grow(shape(phi, min(th, th_max(phi) - D(2))), -SHELL_T - 0.004))
        secs.append(sec)
    # skin it as an open sheet (inside surface)
    bm = bmesh.new()
    vs = [[bm.verts.new(v) for v in sec] for sec in secs]
    for a in range(len(vs) - 1):
        phi_c = D(-150 + 300 * (a + 0.5) / 36)
        if abs(phi_c) < D(64):
            continue                      # pads stop at the cheeks: nothing across the face
        for b in range(len(vs[0]) - 1):
            bm.faces.new([vs[a][b], vs[a][b + 1], vs[a + 1][b + 1], vs[a + 1][b]])
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    p._merge(bm, M["pad"], smooth=True)


def build_face(p, Mr, skin):
    """A plain head inside the helmet so the eye port and mouth vent show a face."""
    c = Vector((0.0, 0.088, 0.004))
    pts = []
    for i in range(14):
        th = math.pi * i / 13
        for k in range(20):
            ph = 2 * math.pi * k / 20
            x = 0.074 * math.sin(th) * math.sin(ph)
            y = 0.112 * math.cos(th)
            z = 0.096 * math.sin(th) * math.cos(ph)
            if y < -0.05:
                z *= 0.85                               # jaw narrows
            pts.append(Mr @ (c + Vector((x, y, z))))
    p.hull(pts, skin)
    p.hull([Mr @ Vector(v) for v in ((0, 0.105, 0.098), (0.012, 0.072, 0.108), (-0.012, 0.072, 0.108),
                                     (0, 0.07, 0.122), (0, 0.09, 0.10))], skin)           # nose
    dark = mk.material("Eyes", (0.02, 0.018, 0.016), roughness=0.3)
    for s in (-1, 1):
        p.sphere(Mr @ Vector((s * 0.031, 0.112, 0.090)), 0.0085, dark, seg=12, rings=8)
        p.hull([Mr @ Vector((s * x, 0.127 + 0.002 * (x > 0.03), 0.092 - 0.01 * (x > 0.04))) for x in (0.016, 0.03, 0.046)] +
               [Mr @ Vector((s * x, 0.131, 0.094 - 0.01 * (x > 0.04))) for x in (0.016, 0.03, 0.046)],
               mk.material("Brows", (0.06, 0.04, 0.03), roughness=0.9), smooth=False)


def build_graphics(p, Mr, M):
    """One restrained graphic: a dark-grey sweep along each side, edged with a
    thin light pinstripe, following the shell."""
    def L(v):
        return Mr @ v

    def band(path, mat, g0=0.0006, g1=0.0016):
        secs = []
        for ph, ta, tb in path:
            secs.append([L(grow(shape(D(ph), D(ta)), g0)), L(grow(shape(D(ph), D(tb)), g0)),
                         L(grow(shape(D(ph), D(tb)), g1)), L(grow(shape(D(ph), D(ta)), g1))])
        p.loft(secs, mat, smooth=True)

    for s in (-1, 1):
        sw, pin = [], []
        for k in range(29):
            t = k / 28.0
            ph = 52 + 112 * t
            mid = 118 - 30 * t
            half = 4.0 * (1.0 - t) + 1.0
            sw.append((s * ph, mid - half, mid + half))
            pin.append((s * ph, mid + half + 1.0, mid + half + 1.7))
        band(sw, M["graphic"])
        band(pin, M["pin"])


def build_helmet(p, Mr, stage, skin, graphics=True):
    M = materials(stage)
    build_shell(p, Mr, stage, M)
    build_peak(p, Mr, stage, M)
    build_mouth_mesh(p, Mr, stage, M)
    build_padding(p, Mr, stage, M)
    build_face(p, Mr, skin)
    if stage == "final" and graphics:
        build_graphics(p, Mr, M)
