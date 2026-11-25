class_name Trail
extends Node3D
## A short dirt trail on its own hill, ridden toward -Z:
##   climb (fire-road grade) -> top -> descent with a rock garden in the
##   steep middle -> short flat -> tabletop jump -> landing that runs down
##   the hill to the ground.
## The hill is a terrain mesh (exact same triangles for the collision), so the
## tyres feel every shape the eye sees. Rocks are separate convex bodies.

const X0 := 22.0                # trail centre line (world x)
const Z_MIN := -40.0
const Z_MAX := 58.0
const X_HALF := 15.0
const CELL := 0.2
const TOP_H := 5.0
const TRACK_HALF := 2.4         # half width of the ridden surface (m)

# key points along the trail (world z, descending = riding direction)
const Z_CLIMB0 := 55.0
const Z_TOP0 := 16.0
const Z_TOP1 := 10.0
const Z_DESC1 := -16.0          # bottom of the descent
const DESC_H := 2.0             # height the descent ends at
const Z_LIP0 := -21.0           # takeoff starts rising
const LIP_H := 1.0              # takeoff height above the run-in
const LIP_ANGLE := deg_to_rad(28.0)
const TABLE_LEN := 2.6
const LAND_ANGLE := deg_to_rad(30.0)
const ROCK_Z := Vector2(4.0, -9.0)

## Where to put the bike for "start of the descent".
static func start_xform() -> Transform3D:
	return Transform3D(Basis(), Vector3(X0, TOP_H + 0.05, Z_TOP0 - 1.5))


static func _smooth(e0: float, e1: float, x: float) -> float:
	var t := clampf((x - e0) / (e1 - e0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


## Centre-line height of the trail at world z.
static func profile(z: float) -> float:
	var lip_r := LIP_H / (1.0 - cos(LIP_ANGLE))          # radius of the takeoff curve
	var lip_len := lip_r * sin(LIP_ANGLE)
	var z_lip1 := Z_LIP0 - lip_len                        # lip edge
	var z_land0 := z_lip1 - TABLE_LEN                     # landing knuckle
	var top := DESC_H + LIP_H
	if z > Z_TOP0:
		return TOP_H * _smooth(Z_CLIMB0, Z_TOP0, z)
	if z > Z_TOP1:
		return TOP_H
	if z > Z_DESC1:
		return DESC_H + (TOP_H - DESC_H) * (1.0 - _smooth(Z_TOP1, Z_DESC1, z))
	if z > Z_LIP0:
		return DESC_H
	if z > z_lip1:
		var d := Z_LIP0 - z                                 # along the curve's chord
		return DESC_H + lip_r - sqrt(maxf(lip_r * lip_r - d * d, 0.0))
	if z > z_land0:
		return top
	# landing: a rounded knuckle, a straight 30 deg slope, and a curved
	# transition into the run-out (a smooth max with the ground)
	var knuckle := 0.6
	var d2 := z_land0 - z
	var slope := tan(LAND_ANGLE)
	var h := top - slope * (d2 - knuckle * 0.5)
	if d2 < knuckle:
		h = top - slope * d2 * d2 / (2.0 * knuckle)
	var soft := 0.7
	h = 0.5 * (h + sqrt(h * h + soft * soft))
	return maxf(h - 0.015, 0.0)


## Terrain height at a world point: the trail surface across TRACK_HALF, then
## a natural shoulder falling away to the ground.
static func height(x: float, z: float) -> float:
	var p := profile(z)
	var d := absf(x - X0)
	var shoulder := 2.5 + 1.3 * p
	var fall := 1.0 - _smooth(TRACK_HALF, TRACK_HALF + shoulder, d)
	return p * fall - 0.04 * (1.0 - fall)          # edges tuck under the baseplate


func _ready() -> void:
	_terrain()
	_rocks()
	_marker()


func _terrain() -> void:
	var nx := int(X_HALF * 2.0 / CELL) + 1
	var nz := int((Z_MAX - Z_MIN) / CELL) + 1
	var verts := PackedVector3Array()
	var cols := PackedColorArray()
	verts.resize(nx * nz)
	cols.resize(nx * nz)
	for j in nz:
		var z := Z_MIN + j * CELL
		for i in nx:
			var x := X0 - X_HALF + i * CELL
			var h := height(x, z)
			verts[j * nx + i] = Vector3(x, h, z)
			# packed riding surface in the middle, looser earth on the shoulders
			var d := absf(x - X0)
			var on_track := 1.0 - _smooth(TRACK_HALF - 0.4, TRACK_HALF + 0.6, d)
			cols[j * nx + i] = Color(on_track, 0.0, 0.0)
	var idx := PackedInt32Array()
	var tris := PackedVector3Array()
	for j in nz - 1:
		for i in nx - 1:
			var a := j * nx + i
			var b := a + 1
			var c := a + nx
			var e := c + 1
			# skip cells that are entirely under the baseplate
			if verts[a].y < 0.0 and verts[b].y < 0.0 and verts[c].y < 0.0 and verts[e].y < 0.0:
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
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = "TrailTerrain"
	mi.mesh = mesh
	var mat := ShaderMaterial.new()
	mat.shader = load("res://scripts/terrain.gdshader")
	mi.material_override = mat
	var body := StaticBody3D.new()
	body.name = "TrailHill"
	var col := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(tris)
	col.shape = shape
	body.add_child(col)
	body.add_child(mi)
	add_child(body)


## Rock garden: half-buried, angular rocks across the steep part of the descent,
## with a couple of lines through that are rough but rideable.
func _rocks() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7311
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.36, 0.34, 0.31)
	mat.roughness = 1.0
	mat.metallic_specular = 0.15
	mat.vertex_color_use_as_albedo = true
	var z := ROCK_Z.x
	while z > ROCK_Z.y:
		var n := rng.randi_range(2, 4)
		for k in n:
			var x := X0 + rng.randf_range(-TRACK_HALF + 0.2, TRACK_HALF - 0.2)
			var zz := z + rng.randf_range(-0.3, 0.3)
			var size := Vector3(rng.randf_range(0.35, 0.8), rng.randf_range(0.22, 0.4), rng.randf_range(0.35, 0.7))
			var stick_out := rng.randf_range(0.04, 0.11)
			_rock(rng, Vector3(x, height(x, zz) + stick_out - size.y * 0.5, zz), size, mat)
		z -= rng.randf_range(0.7, 1.2)
	# a few bigger boulders off the line, for looks
	for k in 6:
		var side := -1.0 if k % 2 == 0 else 1.0
		var x2 := X0 + side * rng.randf_range(TRACK_HALF + 0.4, TRACK_HALF + 1.6)
		var z2 := rng.randf_range(ROCK_Z.y - 2.0, ROCK_Z.x + 2.0)
		var s2 := Vector3(rng.randf_range(0.7, 1.2), rng.randf_range(0.6, 0.9), rng.randf_range(0.7, 1.2))
		_rock(rng, Vector3(x2, height(x2, z2) + s2.y * 0.15, z2), s2, mat)


func _rock(rng: RandomNumberGenerator, center: Vector3, size: Vector3, mat: Material) -> void:
	# a squashed, faceted blob: jittered points on an ellipsoid, flat shaded
	var rings := 4
	var segs := 7
	var pts := []
	var flat_top := rng.randf_range(0.65, 0.85)       # rocks wear flat on top
	for r in rings + 1:
		var lat := PI * (float(r) / rings - 0.5)
		var row := []
		for sgi in segs:
			var lon := TAU * (sgi + 0.5 * (r % 2)) / segs
			var j := rng.randf_range(0.88, 1.08)
			var p := Vector3(cos(lat) * cos(lon), sin(lat), cos(lat) * sin(lon)) * j
			if r == 0 or r == rings:
				p = Vector3(0, sin(lat), 0)
			p.y = minf(p.y, flat_top)
			row.append(Vector3(p.x * size.x, p.y * size.y, p.z * size.z) * 0.5)
		pts.append(row)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var shade := rng.randf_range(0.7, 1.0)
	st.set_color(Color(shade, shade, shade * 0.97))
	var hull := PackedVector3Array()
	for r in rings:
		for sgi in segs:
			var a: Vector3 = pts[r][sgi]
			var b: Vector3 = pts[r][(sgi + 1) % segs]
			var c: Vector3 = pts[r + 1][sgi]
			var d: Vector3 = pts[r + 1][(sgi + 1) % segs]
			for v in [a, b, c, b, d, c]:
				st.add_vertex(v)
			hull.append_array([a, b, c, d])
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	var body := StaticBody3D.new()
	body.position = center
	body.rotation.y = rng.randf_range(0.0, TAU)
	var col := CollisionShape3D.new()
	var shape := ConvexPolygonShape3D.new()
	shape.points = hull
	col.shape = shape
	body.add_child(col)
	body.add_child(mi)
	add_child(body)


## A plain post with a board at the top of the descent, so it's easy to find.
func _marker() -> void:
	var wood := StandardMaterial3D.new()
	wood.albedo_color = Color(0.36, 0.26, 0.17)
	wood.roughness = 0.9
	var post := MeshInstance3D.new()
	var pm := BoxMesh.new()
	pm.size = Vector3(0.12, 2.0, 0.12)
	post.mesh = pm
	post.material_override = wood
	post.position = Vector3(X0 + TRACK_HALF + 0.6, TOP_H + 1.0, Z_TOP0 - 2.0)
	add_child(post)
	var board := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.9, 0.45, 0.05)
	board.mesh = bm
	board.material_override = wood
	board.position = Vector3(X0 + TRACK_HALF + 0.6, TOP_H + 1.85, Z_TOP0 - 2.0)
	add_child(board)
