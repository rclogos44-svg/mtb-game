class_name Park
extends Node3D
## The dirt jump park from design/dirt_jump_blueprint.html, built on the
## baseplate behind the rollers. Three lines off one two-deck start hill:
##   pro      : table P1, double P2, step-up P3, step-down P4, berm B1
##   beginner : table C1, two rollers, table C2, transfer T1, berm B2
##   flow     : (after B1) four rollers, hip H1, table F1, berm B3
## plus transfer T2 off P1's lip onto a pad that runs into the beginner line.
##
## Everything is laid out in "plan" coordinates (px along the pro line, py to
## the rider's left, metres, as on the blueprint) and becomes one terrain mesh
## whose triangles are also the collision, like the trail hill.
## World position of a plan point: x = ORIGIN.x - py, z = ORIGIN.y - px.

const ORIGIN := Vector2(0.0, -100.0)     # world (x, z) of plan (0, 0): front of the pro deck
const CELL := 0.2
const HALF := 1.2                        # track half width
const KN := 0.3                          # flat knuckle on every landing
const BACK := deg_to_rad(60.0)           # back face of takeoffs / front face of landings
const Y_PRO := 0.0
const Y_BEG := 8.0
const Y_FLOW := -13.0

# lines (same numbers as the blueprint)
const PRO := [
	{"type": "start", "top": 3.8, "deck": 3.0, "rollin": 10.0},
	{"type": "table", "id": "P1", "run": 4.0, "h": 0.9, "ang": 28.0, "len": 4.2, "land_ang": 20.0},
	{"type": "double", "id": "P2", "run": 5.0, "h": 1.1, "ang": 32.0, "len": 2.4, "land_h": 1.3, "land_ang": 30.0},
	{"type": "stepup", "id": "P3", "run": 5.0, "h": 1.0, "ang": 33.0, "len": 1.8, "land_h": 1.3, "deck": 2.6, "land_ang": 24.0},
	{"type": "stepdown", "id": "P4", "run": 5.0, "h": 1.3, "ang": 24.0, "len": 3.0, "land_h": 1.0, "land_ang": 20.0},
	{"type": "flat", "len": 4.0},
]
const BEG := [
	{"type": "start", "top": 2.0, "deck": 2.0, "rollin": 7.0},
	{"type": "table", "id": "C1", "run": 3.5, "h": 0.6, "ang": 25.0, "len": 1.6, "land_ang": 20.0},
	{"type": "rollers", "run": 3.0, "n": 2, "h": 0.35, "spacing": 3.6},
	{"type": "table", "id": "C2", "run": 2.5, "h": 0.8, "ang": 27.0, "len": 2.0, "land_ang": 22.0},
	{"type": "transfer", "id": "T1", "run": 3.0, "h": 0.9, "ang": 30.0, "len": 2.6, "land_h": 1.0, "land_ang": 25.0, "turn": -30.0},
	{"type": "flat", "len": 4.0},
]
const FLOW := [
	{"type": "flat", "len": 3.0},
	{"type": "rollers", "run": 0.0, "n": 4, "h": 0.4, "spacing": 4.0},
	{"type": "hip", "id": "H1", "run": 3.0, "h": 1.0, "ang": 30.0, "len": 2.2, "land_ang": 25.0, "turn": 30.0},
	{"type": "table", "id": "F1", "run": 4.0, "h": 0.8, "ang": 28.0, "len": 2.2, "land_ang": 24.0},
	{"type": "flat", "len": 3.0},
]

var elems := []          # ramps: {o: Vector2, d: Vector2, us, hs, umin, umax, hmax}
var berms := []          # {c: Vector2, r, a0, a1, wall}
var pro_len := 0.0
var beg_len := 0.0
var flow_len := 0.0
var lips := []           # [id, plan point of the lip, needed speed m/s (0 = table)]


static func plan_to_world(p: Vector2, h := 0.0) -> Vector3:
	return Vector3(ORIGIN.x - p.y, h, ORIGIN.y - p.x)


## Start transforms: on the pro deck / the beginner deck, facing down the line.
static func start_xform(line := "pro") -> Transform3D:
	var p := Vector2(1.6, Y_PRO) if line == "pro" else Vector2(1.0, Y_BEG)
	var h := 3.8 if line == "pro" else 2.0
	return Transform3D(Basis(), plan_to_world(p, h + 0.05))


func _ready() -> void:
	pro_len = _line(PRO, Vector2(0, Y_PRO), Vector2(1, 0))
	beg_len = _line(BEG, Vector2(0, Y_BEG), Vector2(1, 0))
	flow_len = _line(FLOW, Vector2(pro_len, Y_FLOW), Vector2(-1, 0))
	var r1 := (Y_PRO - Y_FLOW) * 0.5
	berms.append({"c": Vector2(pro_len, (Y_PRO + Y_FLOW) * 0.5), "r": r1, "a0": -PI / 2, "a1": PI / 2, "wall": 1.6})
	berms.append({"c": Vector2(beg_len, Y_BEG + 4.0), "r": 4.0, "a0": -PI / 2, "a1": PI / 2, "wall": 1.1})
	berms.append({"c": Vector2(pro_len - flow_len, Y_FLOW - 4.0), "r": 4.0, "a0": PI / 2, "a1": PI, "wall": 1.2})
	_terrain()


# ------------------------------------------------------------------ layout
static func _smooth(e0: float, e1: float, x: float) -> float:
	var t := clampf((x - e0) / (e1 - e0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


func _add_elem(o: Vector2, d: Vector2, pts: PackedVector2Array) -> void:
	var us := PackedFloat32Array()
	var hs := PackedFloat32Array()
	var hmax := 0.0
	for p in pts:
		us.append(p.x)
		hs.append(p.y)
		hmax = maxf(hmax, p.y)
	elems.append({"o": o, "d": d.normalized(), "us": us, "hs": hs, "umin": pts[0].x, "umax": pts[pts.size() - 1].x, "hmax": hmax})


## A landing pad on its own heading (transfers and the hip): an optional
## front face, flat knuckle, then the slope down.
func _pad(o: Vector2, d: Vector2, land_h: float, land_ang: float, front: bool, table_len := 0.0) -> void:
	var pts := PackedVector2Array()
	var u := 0.0
	if front:
		pts.append(Vector2(-land_h / tan(BACK), 0.0))
		pts.append(Vector2(0.0, land_h))
	else:
		pts.append(Vector2(0.0, land_h))
	u = table_len + KN
	pts.append(Vector2(u, land_h))
	u += land_h / tan(deg_to_rad(land_ang))
	pts.append(Vector2(u, 0.0))
	pts.append(Vector2(u + 0.5, 0.0))
	_add_elem(o, d, pts)


## Builds one line's profile (as an element) plus any pads it throws off.
## Returns its length.
func _line(feats: Array, o: Vector2, d: Vector2) -> float:
	var pts := PackedVector2Array()
	var x := 0.0
	var side := Vector2(-d.y, d.x)        # rider's left
	for f in feats:
		match f["type"]:
			"start":
				var top: float = f["top"]
				pts.append(Vector2(-top * 4.0, 0.0))           # ride-up ramp behind the deck (1 in 4)
				pts.append(Vector2(0.0, top))
				pts.append(Vector2(f["deck"], top))
				for i in range(1, 25):
					var t := i / 24.0
					pts.append(Vector2(f["deck"] + f["rollin"] * t, top * (1.0 - t * t * (3.0 - 2.0 * t))))
				x = f["deck"] + f["rollin"]
			"flat":
				x += f["len"]
				pts.append(Vector2(x, 0.0))
			"rollers":
				x += f["run"]
				pts.append(Vector2(x, 0.0))
				var n: int = f["n"]
				var sp: float = f["spacing"]
				for i in range(1, 20 * n + 1):
					var u := i / 20.0 * sp
					pts.append(Vector2(x + u, f["h"] * 0.5 * (1.0 - cos(TAU * u / sp))))
				x += n * sp
			_:
				x += f["run"]
				pts.append(Vector2(x, 0.0))
				var h: float = f["h"]
				var th := deg_to_rad(f["ang"])
				var R := h / (1.0 - cos(th))
				for i in range(1, 15):
					var a := th * i / 14.0
					pts.append(Vector2(x + R * sin(a), R * (1.0 - cos(a))))
				x += R * sin(th)
				var lip := x
				lips.append([f["id"], o + d * lip, _v_needed(f)])
				if f["id"] == "P1":
					# T2: a second exit off P1's lip, 40 deg to the left, onto a pad
					# that runs into the beginner line
					var dir2 := d.rotated(deg_to_rad(40.0))
					_pad(o + d * lip + dir2 * 3.6, dir2, 0.9, 25.0, true)
				match f["type"]:
					"table":
						x += f["len"]
						pts.append(Vector2(x, h))
						x += KN
						pts.append(Vector2(x, h))
						x += h / tan(deg_to_rad(f["land_ang"]))
						pts.append(Vector2(x, 0.0))
					"hip":
						# landing turned to one side: a table and landing on the new heading
						pts.append(Vector2(x + h / tan(BACK), 0.0))
						x += h / tan(BACK)
						var dirh := d.rotated(deg_to_rad(f["turn"]))
						_pad(o + d * lip, dirh, h, f["land_ang"], false, f["len"])
						x += f["len"] + 2.0
						pts.append(Vector2(x, 0.0))
					"transfer":
						pts.append(Vector2(x + h / tan(BACK), 0.0))
						x += h / tan(BACK) + 0.5
						pts.append(Vector2(x, 0.0))
						var dirt := d.rotated(deg_to_rad(f["turn"]))
						_pad(o + d * lip + dirt * f["len"], dirt, f["land_h"], f["land_ang"], true)
					_:
						# double / step-up / step-down: open gap between two faces
						pts.append(Vector2(x + h / tan(BACK), 0.0))
						x += f["len"]
						var lh: float = f["land_h"]
						pts.append(Vector2(x - lh / tan(BACK), 0.0))
						pts.append(Vector2(x, lh))
						if f["type"] == "stepup":
							x += f["deck"]
							pts.append(Vector2(x, lh))
						x += KN
						pts.append(Vector2(x, lh))
						x += lh / tan(deg_to_rad(f["land_ang"]))
						pts.append(Vector2(x, 0.0))
	pts.append(Vector2(x + 0.01, 0.0))
	_add_elem(o, d, pts)
	return x


## Slowest lip speed that clears the landing's knuckle (0 for tables / hips).
static func _v_needed(f: Dictionary) -> float:
	if not f.has("land_h"):
		return 0.0
	var th := deg_to_rad(f["ang"])
	var dx: float = f["len"]
	var dy: float = f["land_h"] - f["h"]
	return sqrt(9.81 * dx * dx / (2.0 * cos(th) * cos(th) * (dx * tan(th) - dy)))


# ------------------------------------------------------------------ heights
static func _interp(us: PackedFloat32Array, hs: PackedFloat32Array, u: float) -> float:
	if u <= us[0] or u >= us[us.size() - 1]:
		return 0.0
	var lo := 0
	var hi := us.size() - 1
	while hi - lo > 1:
		var mid := (lo + hi) >> 1
		if us[mid] <= u:
			lo = mid
		else:
			hi = mid
	var du := us[hi] - us[lo]
	if du <= 1e-6:
		return maxf(hs[lo], hs[hi])
	return hs[lo] + (hs[hi] - hs[lo]) * (u - us[lo]) / du


## Height of a ramp element at plan point q (0 off it), and how much q is on
## the ridden track (for colour).
func _elem_h(e: Dictionary, q: Vector2) -> Vector2:
	var rel: Vector2 = q - e["o"]
	var u := rel.dot(e["d"])
	if u < e["umin"] or u > e["umax"]:
		return Vector2.ZERO
	var v := absf(rel.cross(e["d"]))
	var hu := _interp(e["us"], e["hs"], u)
	var fall := 1.0 - _smooth(HALF, HALF + 1.0 + 1.3 * hu, v)
	var on := 1.0 - _smooth(HALF - 0.3, HALF + 0.5, v)
	return Vector2(hu * fall, on)


## A banked turn: the surface rises toward the outside of the turn, steepest
## near the top of the wall, then falls away behind it; tapers off at the ends.
func _berm_h(b: Dictionary, q: Vector2) -> Vector2:
	var rel: Vector2 = q - b["c"]
	var r := rel.length()
	var a := rel.angle()
	var a0: float = b["a0"]
	var a1: float = b["a1"]
	var beyond := 0.0
	if a < a0 or a > a1:
		var da := minf(absf(angle_difference(a, a0)), absf(angle_difference(a, a1)))
		beyond = da * r
	var taper := 1.0 - _smooth(0.0, 3.0, beyond)
	if taper <= 0.0:
		return Vector2.ZERO
	var d := r - float(b["r"])
	var wall: float = b["wall"]
	var top_d := 1.8
	var h := 0.0
	if d <= top_d:
		h = wall * pow(clampf((d + 1.6) / (1.6 + top_d), 0.0, 1.0), 1.8)
	else:
		h = wall * (1.0 - _smooth(top_d, top_d + 1.0 + wall, d))
	var on := 1.0 - _smooth(HALF - 0.3, HALF + 0.5, absf(d))
	return Vector2(h * taper, on * taper)


func _terrain() -> void:
	# plan extent -> world grid
	var pmin := Vector2(-16.0, -22.0)
	var pmax := Vector2(pro_len + 12.0, 20.0)
	var wx0 := ORIGIN.x - pmax.y
	var wz0 := ORIGIN.y - pmax.x
	var nx := int((pmax.y - pmin.y) / CELL) + 1
	var nz := int((pmax.x - pmin.x) / CELL) + 1
	var hgt := PackedFloat32Array()
	var trk := PackedFloat32Array()
	hgt.resize(nx * nz)
	trk.resize(nx * nz)
	hgt.fill(-0.04)
	# each element only touches its own bounding box
	var boxes := []
	for e in elems:
		var a: Vector2 = e["o"] + e["d"] * float(e["umin"])
		var b: Vector2 = e["o"] + e["d"] * float(e["umax"])
		var pad := HALF + 1.2 + 1.3 * float(e["hmax"])
		boxes.append([e, Vector2(minf(a.x, b.x) - pad, minf(a.y, b.y) - pad), Vector2(maxf(a.x, b.x) + pad, maxf(a.y, b.y) + pad), false])
	for bm in berms:
		var ext := float(bm["r"]) + 6.0
		boxes.append([bm, bm["c"] - Vector2(ext, ext), bm["c"] + Vector2(ext, ext), true])
	for bx in boxes:
		var lo: Vector2 = bx[1]
		var hi: Vector2 = bx[2]
		# plan (px, py) -> grid: i along world x = ORIGIN.x - py, j along world z = ORIGIN.y - px
		var i0 := clampi(int((ORIGIN.x - hi.y - wx0) / CELL), 0, nx - 1)
		var i1 := clampi(int((ORIGIN.x - lo.y - wx0) / CELL) + 1, 0, nx - 1)
		var j0 := clampi(int((ORIGIN.y - hi.x - wz0) / CELL), 0, nz - 1)
		var j1 := clampi(int((ORIGIN.y - lo.x - wz0) / CELL) + 1, 0, nz - 1)
		for j in range(j0, j1 + 1):
			var px := ORIGIN.y - (wz0 + j * CELL)
			for i in range(i0, i1 + 1):
				var q := Vector2(px, ORIGIN.x - (wx0 + i * CELL))
				var r: Vector2 = _berm_h(bx[0], q) if bx[3] else _elem_h(bx[0], q)
				var k := j * nx + i
				if r.x > hgt[k]:
					hgt[k] = r.x
				if r.y > trk[k]:
					trk[k] = r.y
	# tuck the feet of every mound smoothly under the baseplate, so the edge is
	# a clean contour instead of slivers fighting the ground plane
	for k in hgt.size():
		var h := hgt[k]
		hgt[k] = h - 0.06 * (1.0 - _smooth(0.0, 0.14, h))
	# mesh + identical collision, as in trail.gd
	var verts := PackedVector3Array()
	var cols := PackedColorArray()
	verts.resize(nx * nz)
	cols.resize(nx * nz)
	for j in nz:
		for i in nx:
			var k := j * nx + i
			verts[k] = Vector3(wx0 + i * CELL, hgt[k], wz0 + j * CELL)
			cols[k] = Color(trk[k], 0.0, 0.0)
	var idx := PackedInt32Array()
	var tris := PackedVector3Array()
	for j in nz - 1:
		for i in nx - 1:
			var a := j * nx + i
			var b := a + 1
			var c := a + nx
			var e := c + 1
			if hgt[a] <= 0.0 and hgt[b] <= 0.0 and hgt[c] <= 0.0 and hgt[e] <= 0.0:
				continue
			idx.append_array([a, b, c, b, e, c])
			tris.append_array([verts[a], verts[b], verts[c], verts[b], verts[e], verts[c]])
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_COLOR] = cols
	arrays[Mesh.ARRAY_INDEX] = idx
	st.create_from_arrays(arrays)
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.name = "ParkTerrain"
	mi.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://scripts/terrain.gdshader")
	mi.material_override = mat
	var body := StaticBody3D.new()
	body.name = "ParkGround"
	var col := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(tris)
	col.shape = shape
	body.add_child(col)
	body.add_child(mi)
	add_child(body)
	print("park: %d x %d grid, %d triangles" % [nx, nz, idx.size() / 3])


## Ground height at a world point (for tests and placing things).
func height_at_world(p: Vector3) -> float:
	var q := Vector2(ORIGIN.y - p.z, ORIGIN.x - p.x)
	var h := 0.0
	for e in elems:
		h = maxf(h, _elem_h(e, q).x)
	for b in berms:
		h = maxf(h, _berm_h(b, q).x)
	return h
