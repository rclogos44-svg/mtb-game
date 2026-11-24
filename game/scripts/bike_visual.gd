extends Node3D
## Poses the Blender model from the physics: every linkage part follows the
## solved kinematics for the current rear travel, the fork lowers slide up the
## stanchions, wheels spin, cranks turn and the rider's pedalling animation is
## locked to the real crank angle.

@export var bike_path: NodePath = ^".."

var bike: Bike
var model: Node3D
var parts := {}
var rest := {}
var anim: AnimationPlayer
var skel: Skeleton3D
var arm_bones := []      # [[upperarm, forearm, hand], ...]
var anim_len := 2.0
var g: Dictionary
var ring_r := 0.06
var cog_r := 0.026


func _ready() -> void:
	bike = get_node(bike_path)
	model = $BikeModel
	g = bike.geo if not bike.geo.is_empty() else JSON.parse_string(FileAccess.get_file_as_string(Bike.GEO_PATH))
	for n in ["Chainstay", "Seatstay", "Rocker", "ShockBody", "ShockShaft", "Steer", "ForkLower",
			"FrontWheel", "RearWheel", "Cranks", "PedalL", "PedalR", "ChainTop", "ChainBot", "ShockSpring"]:
		var node := model.find_child(n, true, false) as Node3D
		if node == null:
			push_warning("bike model is missing " + n)
			continue
		parts[n] = node
		rest[n] = node.transform
	ring_r = float(g["chainring_teeth"]) * 0.0127 / TAU
	cog_r = float(g["cog_teeth"]) * 0.0127 / TAU
	anim = $Rider.find_child("AnimationPlayer", true, false)
	for n in $Rider.find_children("*", "Skeleton3D", true, false):
		skel = n
	if skel:
		for s in ["R", "L"]:
			var ids := [skel.find_bone("upperarm." + s), skel.find_bone("forearm." + s), skel.find_bone("hand." + s)]
			if not ids.has(-1):
				arm_bones.append(ids)
	if anim:
		# we drive the animation ourselves (from the crank angle), then fix up the arms
		anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var names := anim.get_animation_list()
		var pick := "Pedal" if anim.has_animation("Pedal") else (names[0] if names.size() > 0 else "")
		if pick != "":
			anim.play(pick)
			anim.speed_scale = 0.0
			anim_len = anim.get_animation(pick).length
	_shadows($Rider)
	_shadows(model)


func _shadows(n: Node) -> void:
	if n is GeometryInstance3D:
		n.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	for c in n.get_children():
		_shadows(c)


static func ang(v: Vector2) -> float:
	return atan2(v.y, v.x)


static func uv(p) -> Vector2:
	return Vector2(p[0], p[1])


func _process(_dt: float) -> void:
	if bike == null or bike.linkage == null:
		return
	_rear()
	_front()
	_drivetrain()


func _set_rot(name: String, angle: float, pos = null) -> void:
	if not parts.has(name):
		return
	var t: Transform3D = rest[name]
	t.basis = Basis(Vector3.RIGHT, angle) * t.basis
	if pos != null:
		t.origin = pos
	parts[name].transform = t


func _rear() -> void:
	var pose := bike.linkage.pose_at(bike.rear.s)
	var P := uv(g["P"])
	var H0 := uv(g["H0"])
	var B0 := uv(g["B0"])
	var C0 := uv(g["C0"])
	var F := uv(g["F"])
	var H: Vector2 = pose["H"]
	var B: Vector2 = pose["B"]
	var C: Vector2 = pose["C"]
	_set_rot("Chainstay", pose["theta"])
	_set_rot("Seatstay", ang(B - H) - ang(B0 - H0), Bike.uv3([H.x, H.y]))
	_set_rot("Rocker", pose["phi"])
	var shock_rot := ang(C - F) - ang(C0 - F)
	_set_rot("ShockBody", shock_rot)
	_set_rot("ShockShaft", shock_rot, Bike.uv3([C.x, C.y]))
	if parts.has("ShockSpring"):
		# spring runs from the preload collar (on the body) to the retainer (on the shaft)
		var free_len: float = float(g["shock_eye"]) - 0.036 - 0.024
		var k := (free_len - bike.linkage.stroke_at(bike.rear.s)) / free_len
		var ts: Transform3D = rest["ShockSpring"]
		ts.basis = ts.basis * Basis.from_scale(Vector3(1.0, k, 1.0))
		parts["ShockSpring"].transform = ts
	if parts.has("RearWheel"):
		var t: Transform3D = rest["RearWheel"]
		t.basis = t.basis * Basis(Vector3.RIGHT, -bike.rear.spin)
		parts["RearWheel"].transform = t


func _front() -> void:
	if parts.has("Steer"):
		var t: Transform3D = rest["Steer"]
		t.basis = t.basis * Basis(Vector3.UP, bike.steer_angle)
		parts["Steer"].transform = t
	if parts.has("ForkLower"):
		var t2: Transform3D = rest["ForkLower"]
		t2.origin += Vector3(0.0, bike.front.s, 0.0)
		parts["ForkLower"].transform = t2
	if parts.has("FrontWheel"):
		var t3: Transform3D = rest["FrontWheel"]
		t3.basis = t3.basis * Basis(Vector3.RIGHT, -bike.front.spin)
		parts["FrontWheel"].transform = t3


func _drivetrain() -> void:
	var a := bike.crank_angle
	if parts.has("Cranks"):
		var t: Transform3D = rest["Cranks"]
		t.basis = Basis(Vector3.RIGHT, -a) * t.basis
		parts["Cranks"].transform = t
	for p in ["PedalL", "PedalR"]:
		if parts.has(p):
			var tp: Transform3D = rest[p]
			tp.basis = tp.basis * Basis(Vector3.RIGHT, a)
			parts[p].transform = tp
	# chain runs: chainring (on the frame) to the cog / jockey (on the swingarm)
	var theta: float = bike.linkage.pose_at(bike.rear.s)["theta"]
	var P := uv(g["P"])
	var axle := uv(g["rear_axle"])
	var lo_j := axle + Vector2(0.020, -0.170)
	var bb := uv(g["bb"])
	var axle_now := P + (axle - P).rotated(theta)
	var lo_now := P + (lo_j - P).rotated(theta)
	_chain("ChainTop", bb + Vector2(0, ring_r + 0.002), axle_now + Vector2(0, cog_r + 0.002))
	_chain("ChainBot", bb + Vector2(0, -ring_r - 0.002), lo_now + Vector2(-0.003, -0.018))
	# rider follows the crank
	if anim:
		anim.seek(fposmod(a, TAU) / TAU * anim_len, true)
	_arms_follow_bars()


## The baked animation has the hands on the bars with the steering straight.
## When the bars turn, move each wrist with its grip and re-solve the arm as a
## two-bone chain (keeping the elbow on the same side it bends to).
func _arms_follow_bars() -> void:
	if skel == null or not parts.has("Steer") or arm_bones.is_empty():
		return
	var D: Transform3D = parts["Steer"].transform * (rest["Steer"] as Transform3D).affine_inverse()
	if absf(bike.steer_angle) < 0.002:
		return
	for ids in arm_bones:
		var ua: int = ids[0]
		var fa: int = ids[1]
		var hd: int = ids[2]
		var g_ua := skel.get_bone_global_pose(ua)
		var g_fa := skel.get_bone_global_pose(fa)
		var g_hd := skel.get_bone_global_pose(hd)
		var s := g_ua.origin
		var e0 := g_fa.origin
		var w0 := g_hd.origin
		var wt := D * w0
		var l1 := s.distance_to(e0)
		var l2 := e0.distance_to(w0)
		var d := wt - s
		var dist := clampf(d.length(), absf(l1 - l2) + 0.001, l1 + l2 - 0.001)
		var dir := d.normalized()
		var cos_a := clampf((l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist), -1.0, 1.0)
		var pole := e0 - s
		pole = (pole - dir * pole.dot(dir)).normalized()
		var e1 := s + dir * (l1 * cos_a) + pole * (l1 * sqrt(1.0 - cos_a * cos_a))
		var w1 := s + dir * dist
		var r1 := Basis(Quaternion((e0 - s).normalized(), (e1 - s).normalized()))
		skel.set_bone_global_pose(ua, Transform3D(r1 * g_ua.basis, s))
		var fa_dir0 := (r1 * (w0 - e0)).normalized()
		var r2 := Basis(Quaternion(fa_dir0, (w1 - e1).normalized()))
		skel.set_bone_global_pose(fa, Transform3D(r2 * r1 * g_fa.basis, e1))
		skel.set_bone_global_pose(hd, Transform3D(D.basis * g_hd.basis, w1))


func _chain(name: String, a2: Vector2, b2: Vector2) -> void:
	if not parts.has(name):
		return
	var x := 0.052
	var a := Vector3(x, a2.y, -a2.x)
	var b := Vector3(x, b2.y, -b2.x)
	var d := b - a
	var basis := Basis.looking_at(d.normalized(), Vector3.RIGHT.cross(d.normalized()).normalized())
	basis.z *= d.length()
	parts[name].transform = Transform3D(basis, a)
