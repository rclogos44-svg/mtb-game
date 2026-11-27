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
var pedal_anim: Animation
var pose_tracks := []        # [track, bone, type]
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
	for n in $Rider.find_children("*", "Skeleton3D", true, false):
		skel = n
	anim = $Rider.find_child("AnimationPlayer", true, false)
	if skel:
		for s in ["R", "L"]:
			var ids := [skel.find_bone("upperarm." + s), skel.find_bone("forearm." + s), skel.find_bone("hand." + s)]
			if not ids.has(-1):
				arm_bones.append(ids)
	if anim:
		# we sample the pedalling animation ourselves (at the crank angle) every
		# tick, so each frame starts from the clean pose before the body is adjusted
		anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		anim.active = false
		var names := anim.get_animation_list()
		var pick := "Pedal" if anim.has_animation("Pedal") else (names[0] if names.size() > 0 else "")
		if pick != "":
			pedal_anim = anim.get_animation(pick)
			anim_len = pedal_anim.length
			if skel:
				for ti in pedal_anim.get_track_count():
					var bone := skel.find_bone(String(pedal_anim.track_get_path(ti).get_concatenated_subnames()))
					var ty := pedal_anim.track_get_type(ti)
					if bone >= 0 and (ty == Animation.TYPE_POSITION_3D or ty == Animation.TYPE_ROTATION_3D):
						pose_tracks.append([ti, bone, ty])
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


func _physics_process(dt: float) -> void:
	# on the physics tick, so the bike's interpolation carries every part smoothly
	if bike == null or bike.linkage == null:
		return
	_rear()
	_front()
	_drivetrain(dt)


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
		t.basis = t.basis * Basis(Vector3.UP, bike.bar_angle)
		parts["Steer"].transform = t
	if parts.has("ForkLower"):
		var t2: Transform3D = rest["ForkLower"]
		t2.origin += Vector3(0.0, bike.front.s, 0.0)
		parts["ForkLower"].transform = t2
	if parts.has("FrontWheel"):
		var t3: Transform3D = rest["FrontWheel"]
		t3.basis = t3.basis * Basis(Vector3.RIGHT, -bike.front.spin)
		parts["FrontWheel"].transform = t3


func _drivetrain(dt: float) -> void:
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
	if pedal_anim and skel:
		var t := fposmod(a, TAU) / TAU * anim_len
		# start from the rest pose: the animation only keys rotations (and the
		# hips' position), so anything the body solver moved must be cleared
		skel.reset_bone_poses()
		for tr in pose_tracks:
			if tr[2] == Animation.TYPE_POSITION_3D:
				skel.set_bone_pose_position(tr[1], pedal_anim.position_track_interpolate(tr[0], t))
			else:
				skel.set_bone_pose_rotation(tr[1], pedal_anim.rotation_track_interpolate(tr[0], t))
	_rider_body(dt)


## Rider body. The baked animation is the pedalling stroke with the bike level
## and the bars straight. On top of it the hips are a sprung, damped mass that
## reacts to the bike (sinking on landings, surging and bracing under braking,
## crouching to load a hop), then the legs are re-solved so the feet stay on
## the pedals and the arms so the hands stay on the (steered) grips.
var hip_off := Vector3.ZERO          # in the bike's local frame (m)
var hip_vel := Vector3.ZERO
var _v_prev := Vector3.ZERO
var leg_bones := []                  # [[thigh, shin, foot], ...]
var hips_bone := -1
var spine_bone := -1
var foot_miss := 0.0
var hand_miss := 0.0                 # how far the hands ended from the grips last tick (m)

const HIP_FREQ := 1.7                # Hz, rider's legs/arms as a suspension
const HIP_DAMP := 0.65
const HIP_MIN := Vector3(-0.05, -0.13, -0.08)
const HIP_MAX := Vector3(0.05, 0.05, 0.24)


func _rider_body(dt: float) -> void:
	if skel == null:
		return
	if hips_bone < 0:
		hips_bone = skel.find_bone("hips")
		spine_bone = skel.find_bone("spine")
		for s in ["R", "L"]:
			var ids := [skel.find_bone("thigh." + s), skel.find_bone("shin." + s), skel.find_bone("foot." + s)]
			if not ids.has(-1):
				leg_bones.append(ids)
		_v_prev = bike.linear_velocity
	if hips_bone < 0:
		return

	# --- hips as a spring-mass riding on the bike
	var basis_inv := bike.global_transform.basis.inverse()
	var acc := (bike.linear_velocity - _v_prev) / maxf(dt, 1e-4)
	_v_prev = bike.linear_velocity
	var felt := basis_inv * (acc - Vector3(0.0, -Bike.GRAV, 0.0))   # specific force, bike frame
	var extra := felt - Vector3(0.0, Bike.GRAV, 0.0)
	if not (bike.rear.contact or bike.front.contact):
		extra = Vector3.ZERO                                           # weightless in the air
	extra = extra.clamp(Vector3(-25, -40, -25), Vector3(25, 40, 25))
	var target := Vector3.ZERO
	target.y -= 0.09 * bike.hop_charge                                  # crouch to load a hop...
	target.z += 0.17 * bike.hop_charge                                  # ...down and back, behind the saddle
	target.z += 0.10 * bike.weight_back                                 # hips back under braking
	if not (bike.rear.contact or bike.front.contact):
		target.y -= 0.06                                                # ready position in the air
	var w := TAU * HIP_FREQ
	var a := -w * w * (hip_off - target) - 2.0 * HIP_DAMP * w * hip_vel - extra * 0.55
	hip_vel += a * dt
	hip_off += hip_vel * dt
	var clamped := hip_off.clamp(HIP_MIN, HIP_MAX)
	if clamped != hip_off:
		hip_vel *= 0.3
		hip_off = clamped

	# --- remember where the animation put the hands and feet, then move the hips
	var feet := []
	for ids in leg_bones:
		feet.append(skel.get_bone_global_pose(ids[2]))
	var hands := []
	for ids in arm_bones:
		hands.append(skel.get_bone_global_pose(ids[2]))
	var hp := skel.get_bone_global_pose(hips_bone)
	# skeleton space is the bike model's space (both sit at the Visual origin)
	var local_off := Vector3(hip_off.x, hip_off.y, hip_off.z + maxf(-hip_off.y, 0.0) * 0.5)
	hp.origin += local_off
	skel.set_bone_global_pose(hips_bone, hp)
	var D := Transform3D.IDENTITY
	if parts.has("Steer"):
		D = parts["Steer"].transform * (rest["Steer"] as Transform3D).affine_inverse()
	if spine_bone >= 0:
		# Upper body: twist with the bars, and fold forward at the hips only as
		# much as needed for both hands to reach their grips (as a rider does
		# when crouching low or reaching for a turned bar).
		var sp0 := skel.get_bone_global_pose(spine_bone)
		var twist := Basis(Vector3.UP, bike.bar_angle * 0.6)
		var fold := clampf(hip_off.y * 0.8, -0.2, 0.05)
		for k in 10:
			var sp := sp0
			sp.basis = (twist * Basis(Vector3.RIGHT, fold) * sp0.basis).orthonormalized()
			skel.set_bone_global_pose(spine_bone, sp)
			var worst := 0.0
			for i in arm_bones.size():
				var ids: Array = arm_bones[i]
				var sh := skel.get_bone_global_pose(ids[0]).origin
				var el := skel.get_bone_global_pose(ids[1]).origin
				var wr := skel.get_bone_global_pose(ids[2]).origin
				var reach := sh.distance_to(el) + el.distance_to(wr)
				var h: Transform3D = hands[i]
				worst = maxf(worst, sh.distance_to(D * h.origin) / reach)
			if worst < 0.97 or fold < -0.7:
				break
			fold -= 0.07

	# --- legs: feet back onto the pedals
	foot_miss = 0.0
	for i in leg_bones.size():
		var f: Transform3D = feet[i]
		# knees always point forward (and a touch out), so a nearly straight
		# standing leg can't flip its knee from frame to frame
		var hip_x := skel.get_bone_global_pose(leg_bones[i][0]).origin.x
		var knee_dir := Vector3(signf(hip_x) * 0.12, 0.0, -1.0)
		foot_miss = maxf(foot_miss, _two_bone(leg_bones[i], f.origin, f.basis, knee_dir, 1.0))
	# --- arms: hands onto the grips, which turn with the steering
	hand_miss = 0.0
	for i in arm_bones.size():
		var h: Transform3D = hands[i]
		var sh_x := skel.get_bone_global_pose(arm_bones[i][0]).origin.x
		var elbow_dir := Vector3(signf(sh_x) * 0.8, 0.0, 0.6)    # elbows out and back
		hand_miss = maxf(hand_miss, _two_bone(arm_bones[i], D * h.origin, D.basis * h.basis, elbow_dir, 0.5))


## Two-bone IK in skeleton space: bend a-b-c so c lands on `target`, keeping the
## middle joint toward `hint` (blended by `hint_w` with the side it already
## bends to); c takes `end_basis`.
func _two_bone(ids: Array, target: Vector3, end_basis: Basis, hint := Vector3.ZERO, hint_w := 0.0) -> float:
	var ia: int = ids[0]
	var ib: int = ids[1]
	var ic: int = ids[2]
	var ga := skel.get_bone_global_pose(ia)
	var gb := skel.get_bone_global_pose(ib)
	var gc := skel.get_bone_global_pose(ic)
	var s := ga.origin
	var m0 := gb.origin
	var e0 := gc.origin
	var l1 := s.distance_to(m0)
	var l2 := m0.distance_to(e0)
	var d := target - s
	if l1 < 1e-4 or l2 < 1e-4 or d.length() < 1e-4:
		return 0.0
	var dist := clampf(d.length(), absf(l1 - l2) + 0.002, l1 + l2 - 0.002)
	var dir := d.normalized()
	var cos_a := clampf((l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist), -1.0, 1.0)
	var pole := m0 - s
	pole -= dir * pole.dot(dir)
	var hp := hint - dir * hint.dot(dir)
	if pole.length() > 1e-4:
		pole = pole.normalized()
	if hint_w > 0.0 and hp.length() > 1e-3:
		pole = pole * (1.0 - hint_w) + hp.normalized() * hint_w
	if pole.length() < 1e-4:
		return 0.0
	pole = pole.normalized()
	var m1 := s + dir * (l1 * cos_a) + pole * (l1 * sqrt(1.0 - cos_a * cos_a))
	var e1 := s + dir * dist
	var r1 := _arc(m0 - s, m1 - s)
	var r2 := _arc(r1 * (e0 - m0), e1 - m1)
	if not (r1.is_finite() and r2.is_finite() and m1.is_finite()):
		return 0.0
	skel.set_bone_global_pose(ia, Transform3D((r1 * ga.basis).orthonormalized(), s))
	skel.set_bone_global_pose(ib, Transform3D((r2 * r1 * gb.basis).orthonormalized(), m1))
	skel.set_bone_global_pose(ic, Transform3D(end_basis.orthonormalized(), e1))
	return e1.distance_to(target)


static func _arc(from: Vector3, to: Vector3) -> Basis:
	var a := from.normalized()
	var b := to.normalized()
	if a.dot(b) > 0.99999:
		return Basis.IDENTITY
	return Basis(Quaternion(a, b))


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
