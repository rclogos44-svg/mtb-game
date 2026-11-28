class_name BigLine
extends Node3D
## The big slope line from design/big_line_blueprint.html: a start tower on a
## 12% hillside with five big jumps down it, a berm and a run-out at the
## bottom. The design numbers live in assets/big_line.json, which the
## blueprint page reads too, and the profile is built exactly the same way.
##
## Plan coordinates: u along the line (downhill), v to the rider's left.
## World: x = ORIGIN.x - v, z = ORIGIN.y - u (the line runs toward -Z).

const DESIGN := "res://assets/big_line.json"
const ORIGIN := Vector2(0.0, -120.0)
const FINE := 0.375                 # cell size along the riding line and berm
const COARSE := 1.5                 # cell size on the hill's big sides
const TRACK_HALF := 2.0
const GRAV := 9.81
const AIR_CDA := 0.5            # rider + bike in the air (between tucked and sitting up)

var D: Dictionary
var S := 0.12
var H0 := 26.0
var us := PackedFloat32Array()     # centre-line profile
var ys := PackedFloat32Array()
var jumps := []                     # dictionaries with lip/knuckle/window info
var line_end := 0.0
var berm := {}


static func to_world(u: float, v: float, h := 0.0) -> Vector3:
	return Vector3(ORIGIN.x - v, h, ORIGIN.y - u)


## On the start tower, facing down the line.
func start_xform() -> Transform3D:
	var dk: Dictionary = D["deck"]
	return Transform3D(Basis(), to_world(-float(dk["len"]) * 0.5, 0.0, float(dk["y"]) + 0.05))


func _ready() -> void:
	D = JSON.parse_string(FileAccess.get_file_as_string(DESIGN))
	S = D["slope"]
	H0 = D["hill_top"]
	_build_profile()
	for j in jumps:
		j["win"] = _window(j)
		j["win_pop"] = _window(j, float(D.get("pop", 0.0)))
	_terrain()
	_signs()


# ------------------------------------------------------------------ profile
## The bare hillside under the line: flat top, 12% down, easing into the flat.
func ground(u: float) -> float:
	var k := 3.0
	var y := H0 - S * maxf(u, 0.0)
	var g := y if y >= k else (0.0 if y <= -k else (y + k) * (y + k) / (4.0 * k))
	var back := -float(D["deck"]["len"]) - 4.0
	if u < back:
		g = maxf(H0 - (back - u), 0.0)            # back of the hill, 45 deg
	return g


func _build_profile() -> void:
	var P := PackedVector2Array()
	var dk: Dictionary = D["deck"]
	var dl: float = dk["len"]
	var dy: float = dk["y"]
	var roll: float = dk["rollin"]
	P.append(Vector2(-dl - 4.0 - H0, 0.0))
	P.append(Vector2(-dl - 4.0, H0))
	P.append(Vector2(-dl, dy))
	P.append(Vector2(0.0, dy))
	var y1 := ground(roll)
	for i in range(1, 41):
		var t := i / 40.0
		var h00 := 2.0 * t * t * t - 3.0 * t * t + 1.0
		var h01 := -2.0 * t * t * t + 3.0 * t * t
		var h11 := t * t * t - t * t
		P.append(Vector2(roll * t, h00 * dy + h01 * y1 + h11 * roll * -S))
	var u := roll
	var back := tan(deg_to_rad(60.0))
	for src in D["jumps"]:
		var j: Dictionary = src.duplicate()
		u += float(j["run"])
		P.append(Vector2(u, ground(u)))
		j["u0"] = u
		var a0 := -atan(S)
		var th := deg_to_rad(j["ang"])
		var R := float(j["h"]) / ((cos(a0) - cos(th)) + S * (sin(th) - sin(a0)))
		var yb := ground(u)
		for i in range(1, 21):
			var a := a0 + (th - a0) * i / 20.0
			P.append(Vector2(u + R * (sin(a) - sin(a0)), yb + R * (cos(a0) - cos(a))))
		var lip := P[P.size() - 1]
		j["lip_u"] = lip.x
		j["lip_y"] = lip.y
		var ub := lip.x
		while lip.y - (ub - lip.x) * back > ground(ub):
			ub += 0.05
		P.append(Vector2(ub, ground(ub)))
		var kn_u: float = lip.x + float(j["gap"])
		var kn_y: float = ground(kn_u) + float(j["hk"])
		j["kn_u"] = kn_u
		j["kn_y"] = kn_y
		var uf := kn_u
		while kn_y - (kn_u - uf) * back > ground(uf):
			uf -= 0.05
		P.append(Vector2(uf, ground(uf)))
		P.append(Vector2(kn_u, kn_y))
		u = _landing(P, kn_u, kn_y, tan(deg_to_rad(j["land_ang"])), j)
		jumps.append(j)
	line_end = u + float(D["runout"])
	var x := u + 4.0
	while x <= line_end:
		P.append(Vector2(x, ground(x)))
		x += 4.0
	P.append(Vector2(line_end, ground(line_end)))
	for p in P:
		us.append(p.x)
		ys.append(p.y)
	var br: Dictionary = D["berm"]
	berm = {"c": Vector2(line_end, -float(br["r"])), "r": float(br["r"]), "wall": float(br["wall"])}


## A landing shaped the way builders shape them: a short flat knuckle that
## rolls over into the landing angle, a straight steep section, then a curve
## whose slope eases evenly from the landing angle down to the trail, so there
## is no kink where the landing meets the run-out. Returns where the trail
## carries on.
func _landing(P: PackedVector2Array, kn_u: float, kn_y: float, tp: float, j: Dictionary) -> float:
	var KF := 0.4                         # flat top of the knuckle
	var KR := 1.4                         # knuckle roll-over length
	P.append(Vector2(kn_u + KF, kn_y))
	for i in range(1, 8):                 # knuckle: slope goes 0 -> landing angle
		var x := KR * i / 7.0
		P.append(Vector2(kn_u + KF + x, kn_y - tp * x * x / (2.0 * KR)))
	var u1 := kn_u + KF + KR
	var y1 := kn_y - tp * KR * 0.5
	var h1 := y1 - ground(u1)
	var ht := 0.55 * h1                   # height left when the curve starts
	var ls := maxf((h1 - ht) / (tp - S), 0.0)
	for i in range(1, 5):                 # straight, steep part
		var x := ls * i / 4.0
		P.append(Vector2(u1 + x, y1 - tp * x))
	var ua := u1 + ls
	var ya := y1 - tp * ls
	var l2 := 2.0 * ht / (tp - S)         # transition: slope eases linearly to the hill's
	for i in range(1, 17):
		var x := l2 * i / 16.0
		P.append(Vector2(ua + x, ya - tp * x + (tp - S) * x * x / (2.0 * l2)))
	j["land_end"] = ua + l2 * 0.5         # past here it's the run-out, not the landing
	j["curve_end"] = ua + l2
	return ua + l2 + 2.0


func profile(u: float) -> float:
	if u <= us[0]:
		return 0.0
	if u >= us[us.size() - 1]:
		return ground(u)
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
		return maxf(ys[lo], ys[hi])
	return ys[lo] + (ys[hi] - ys[lo]) * (u - us[lo]) / du


## Lip speeds (km/h) that touch down on the landing, as on the blueprint,
## with a pop off the lip of `pop` m/s (0 = just rolling off it).
func _window(j: Dictionary, pop := 0.0) -> Vector2i:
	var lo := -1
	var hi := -1
	for k in range(15, 91):
		var r := _fly(j, k / 3.6, pop)
		if r == "land":
			if lo < 0:
				lo = k
			hi = k
	return Vector2i(lo, hi)


## Where a flight off this jump's lip touches down (u), for calibration.
func landing_u(j: Dictionary, v: float, pop: float) -> float:
	var r := _flight(j, v, pop)
	return r[0]


## Flies a lip speed (and pop) over the profile with air drag; returns
## [touchdown u, time, trajectory angle deg, ground slope deg].
func _flight(j: Dictionary, v: float, pop: float) -> Array:
	var th := deg_to_rad(j["ang"])
	var vx := v * cos(th) - pop * sin(th)
	var vy := v * sin(th) + pop * cos(th)
	var x: float = j["lip_u"]
	var y: float = j["lip_y"]
	var t := 0.0
	var dt := 0.004
	var k := 0.5 * 1.2 * AIR_CDA / 90.0
	while t < 6.0:
		var sp := sqrt(vx * vx + vy * vy)
		vx -= k * sp * vx * dt
		vy -= (GRAV + k * sp * vy) * dt
		x += vx * dt
		y += vy * dt
		t += dt
		if t > 0.08 and y <= profile(x):
			var slope := rad_to_deg(atan2(profile(x - 0.1) - profile(x + 0.1), 0.2))
			return [x, t, rad_to_deg(atan2(-vy, vx)), slope]
	return [1e9, t, 0.0, 0.0]


func _fly(j: Dictionary, v: float, pop := 0.0) -> String:
	var r := _flight(j, v, pop)
	var x: float = r[0]
	if x < float(j["kn_u"]) - 0.05:
		return "case"
	if x <= float(j["land_end"]) and absf(float(r[2]) - float(r[3])) < 20.0:
		return "land"
	return "over"


# ------------------------------------------------------------------ surface
static func _smooth(e0: float, e1: float, x: float) -> float:
	var t := clampf((x - e0) / (e1 - e0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


## Height at plan point (u, v), and how much it's on the ridden line.
func height(u: float, v: float) -> Vector2:
	var hw: float = D["hill_half_width"]
	var av := absf(v)
	var g := ground(u)
	# hill: flat crest, then 45 deg sides with a rounded shoulder
	var side := av - hw
	var hill := g
	if side > 0.0:
		var r := 2.0
		hill = g - (side * side / (2.0 * r) if side < r else side - r * 0.5)
	# features (tower, takeoffs, landings) stand on the crest, across the riding line
	var feat := profile(u) - g
	var h := hill
	var on := 0.0
	if feat > 0.0:
		var fall := 1.0 - _smooth(TRACK_HALF, TRACK_HALF + 1.0 + 1.2 * feat, av)
		h = maxf(h, hill + feat * fall)
	if u > -float(D["deck"]["len"]) and u < line_end:
		on = 1.0 - _smooth(TRACK_HALF - 0.4, TRACK_HALF + 0.6, av)
	# berm at the bottom: banked 180 to the right
	var b := _berm(u, v)
	if b.x > h:
		h = b.x
	on = maxf(on, b.y)
	return Vector2(maxf(h, 0.0), on)


func _berm(u: float, v: float) -> Vector2:
	var rel: Vector2 = Vector2(u, v) - (berm["c"] as Vector2)
	if rel.x < -3.0:
		return Vector2.ZERO
	var taper := 1.0 if rel.x >= 0.0 else 1.0 - _smooth(0.0, 3.0, -rel.x)
	var d: float = rel.length() - float(berm["r"])
	var wall: float = berm["wall"]
	var h := 0.0
	if d <= 2.0:
		h = wall * pow(clampf((d + 1.8) / 3.8, 0.0, 1.0), 1.8)
	else:
		h = wall * (1.0 - _smooth(2.0, 3.0 + wall, d))
	var on := 1.0 - _smooth(TRACK_HALF - 0.4, TRACK_HALF + 0.6, absf(d))
	return Vector2(h * taper, on * taper)


## One grid of terrain over a plan rectangle. Quads whose centre falls inside
## any of `skip` rects are left out (a finer grid covers them).
func _patch(u0: float, u1: float, v0: float, v1: float, cell: float, skip: Array, tris: PackedVector3Array, st: SurfaceTool) -> void:
	var nu := roundi((u1 - u0) / cell) + 1
	var nv := roundi((v1 - v0) / cell) + 1
	var pos := PackedVector3Array()
	var trk := PackedFloat32Array()
	pos.resize(nu * nv)
	trk.resize(nu * nv)
	for a in nu:
		var u := u0 + a * cell
		for b in nv:
			var v := v0 + b * cell
			var r := height(u, v)
			var h := r.x - 0.06 * (1.0 - _smooth(0.0, 0.14, r.x))     # tuck feet under the baseplate
			pos[a * nv + b] = to_world(u, v, h)
			trk[a * nv + b] = r.y
	for a in nu - 1:
		for b in nv - 1:
			var cu := u0 + (a + 0.5) * cell
			var cv := v0 + (b + 0.5) * cell
			var skipped := false
			for rc in skip:
				if cu > rc[0] and cu < rc[1] and cv > rc[2] and cv < rc[3]:
					skipped = true
					break
			if skipped:
				continue
			var i00 := a * nv + b
			var i01 := i00 + 1
			var i10 := i00 + nv
			var i11 := i10 + 1
			if pos[i00].y <= 0.0 and pos[i01].y <= 0.0 and pos[i10].y <= 0.0 and pos[i11].y <= 0.0:
				continue
			# world x grows with -v and z with -u: wind so the faces point up
			for k in [i00, i01, i10, i01, i11, i10]:
				st.set_color(Color(trk[k], 0.0, 0.0))
				st.add_vertex(pos[k])
				tris.append(pos[k])


func _terrain() -> void:
	# All patch edges sit on coarse grid lines (and FINE divides COARSE), so
	# the fine strip, the berm patch and the coarse sides join without seams.
	var hw: float = D["hill_half_width"]
	var c := COARSE
	var strip := hw + 0.5                                   # 7.5 = 5 coarse cells
	var cu0 := us[0] - 4.0 - 30.0                           # coarse grid origin in u
	var snap_u := func(x: float) -> float: return cu0 + c * roundf((x - cu0) / c)
	var u_min: float = snap_u.call(us[0] - 4.0)
	var bu0: float = snap_u.call(line_end - 4.0)
	var u_max: float = snap_u.call(line_end + float(berm["r"]) + 8.0)
	var bv0 := -strip - c * ceilf((2.0 * float(berm["r"]) + 7.0 - strip) / c)
	var reach := strip + c * ceilf((hw + 4.0 + float(D["deck"]["y"]) - strip) / c)
	var fine_rects := [[u_min, bu0, -strip, strip], [bu0, u_max, bv0, strip]]
	var tris := PackedVector3Array()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_patch(u_min, bu0, -strip, strip, FINE, [], tris, st)
	_patch(bu0, u_max, bv0, strip, FINE, [], tris, st)
	_patch(cu0, u_max, -reach, reach, COARSE, fine_rects, tris, st)
	st.index()                      # share vertices so the hill shades smoothly
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.name = "BigLineTerrain"
	mi.mesh = st.commit()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://scripts/terrain.gdshader")
	mi.material_override = mat
	var body := StaticBody3D.new()
	body.name = "BigLineGround"
	var col := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(tris)
	col.shape = shape
	body.add_child(col)
	body.add_child(mi)
	add_child(body)
	print("big line: %d triangles, windows %s, with a pop %s" % [tris.size() / 3, jumps.map(func(j): return "%s %d-%d" % [j["id"], j["win"].x, j["win"].y]), jumps.map(func(j): return "%s %d-%d" % [j["id"], j["win_pop"].x, j["win_pop"].y])])


## A speed sign beside each takeoff, on the rider's right.
func _signs() -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.36, 0.26, 0.17)
	wood.roughness = 0.9
	var face := StandardMaterial3D.new()
	face.albedo_color = Color(0.93, 0.92, 0.88)
	for j in jumps:
		var u: float = float(j["u0"]) - 6.0
		var v := -TRACK_HALF - 1.6
		var base := ground(u)
		var post := MeshInstance3D.new()
		var pm := BoxMesh.new()
		pm.size = Vector3(0.1, 1.8, 0.1)
		post.mesh = pm
		post.material_override = wood
		post.position = to_world(u, v, base + 0.9)
		add_child(post)
		var board := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1.3, 0.8, 0.05)
		board.mesh = bm
		board.material_override = face
		board.position = to_world(u, v, base + 1.75)
		add_child(board)
		var lab := Label3D.new()
		var w: Vector2i = j["win_pop"]
		lab.text = "%s %s\npedal + pop\n%d-%d km/h" % [j["id"], j["name"], w.x, w.y]
		lab.font_size = 44
		lab.pixel_size = 0.0045
		lab.modulate = Color(0.12, 0.1, 0.08)
		lab.outline_size = 0
		lab.position = to_world(u, v, base + 1.75) + Vector3(0, 0, 0.03)
		add_child(lab)
