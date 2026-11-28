extends SceneTree
## Headless ride test:  godot --headless --path game -s tests/sim_test.gd
## Drives the bike with an autopilot and checks the physics behaves like a bike.

var bike: Bike
var fails := 0
var phase := "settle"
var t0 := 0.0
var line_speed := 6.0
var flip_period := 1.5
var flip_pedal := 1.0
var flip_brake := 0.0
var trail_effort := 0.3
var trick := {}
var park_x := 0.0
var park_dir := -1.0
var park_effort := 1.0
var trick_rot := Vector3.ZERO


func check(name: String, ok: bool, detail: String) -> void:
	print(("PASS " if ok else "FAIL ") + name + "  " + detail)
	if not ok:
		fails += 1


func pilot(_b, _t: float) -> Dictionary:
	match phase:
		"pedal":
			return {"pedal": 1.0}
		"turn":
			return {"pedal": 0.6, "steer": 0.5}
		"brake":
			return {"brake": 1.0}
		"straight":
			return {"pedal": 1.0}
		"turnbrake":
			return {"steer": 0.5, "brake": 0.7}
		"wild":
			var k := int(_t * 2.5)
			return {"pedal": 1.0, "steer": 1.0 if k % 2 == 0 else -1.0, "hop": int(_t * 1.3) % 3 == 0}
		"steerstill":
			return {"steer": 1.0}
		"holdturn":
			return {"pedal": 0.6 if _b.linear_velocity.length() < 7.0 else 0.0, "steer": 1.0}
		"flip":
			# hold W+A, then switch to W+D (or S+A -> S+D), back and forth
			var dir := 1.0 if int(_t / flip_period) % 2 == 0 else -1.0
			return {"pedal": flip_pedal, "brake": flip_brake, "steer": dir}
		"line":
			return {"pedal": 1.0 if _b.linear_velocity.length() < line_speed else 0.0, "steer": 0.25 * sin(_t * 2.3)}
		"hopload":
			return {"hop": true}
		"pedalhop":
			return {"pedal": 1.0, "hop": true}
		"park":
			var off2: float = (_b.global_position.x - park_x) * -park_dir
			var yaw2: float = (-_b.global_transform.basis.z).x * -park_dir
			return {"pedal": 1.0 if _t < 1.0 else park_effort, "steer": clampf(off2 * 0.6 + yaw2 * 3.0, -1.0, 1.0)}
		"trail":
			var off: float = _b.global_position.x - Trail.X0
			var yaw_err: float = (-_b.global_transform.basis.z).x
			var c := {"pedal": 1.0 if _t < 1.5 else trail_effort, "steer": clampf(off * 0.6 + yaw_err * 3.0, -1.0, 1.0)}
			# trick off the tabletop: hold it until nearly round, then let go (like a player)
			if not trick.is_empty() and not (_b.rear.contact or _b.front.contact) and _b.global_position.z < -24.0 \
					and maxf(absf(trick_rot.x), absf(trick_rot.y)) < deg_to_rad(290.0):
				c.merge(trick, true)
			return c
		"sprint":
			return {"pedal": 1.0}
		"wheelie_in":
			return {"pedal": 1.0 if _b.linear_velocity.length() < 4.0 else 0.0}
		"wheelie":
			return {"pedal": 1.0 if _b.linear_velocity.length() < 4.5 else 0.4, "tilt": 1.0}
	return {}


func wait(seconds: float) -> void:
	var n := int(seconds * Engine.physics_ticks_per_second)
	for i in n:
		await physics_frame


func roll_deg() -> float:
	var up := bike.global_transform.basis.y
	var fwd := -bike.global_transform.basis.z
	return rad_to_deg(asin(clampf(up.cross(Vector3.UP).dot(fwd), -1.0, 1.0)))


func _initialize() -> void:
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred(main)


func _run(main) -> void:
	await physics_frame
	bike = main.bike
	bike.autopilot = pilot
	bike.reset_bike(Transform3D(Basis(), Vector3(60, 0.05, 80)))   # open ground, away from the features
	await wait(3.0)
	var rs := bike.rear.s / bike.rear.travel
	var fs := bike.front.s / bike.front.travel
	check("rear sag", absf(rs - bike.rear_sag) < 0.05, "%.0f%% (target %.0f%%)" % [rs * 100, bike.rear_sag * 100])
	check("fork sag", absf(fs - bike.fork_sag) < 0.05, "%.0f%% (target %.0f%%)" % [fs * 100, bike.fork_sag * 100])
	check("stands still", bike.linear_velocity.length() < 0.05, "%.3f m/s" % bike.linear_velocity.length())
	check("upright at rest", absf(roll_deg()) < 3.0, "roll %.1f deg" % roll_deg())
	print("   spring %d lb/in, fork %d psi, shock LSC %.0f LSR %.0f N s/m" %
		[bike.shock.lbs_per_in(), int(bike.fork.psi()), bike.shock_damper.lsc, bike.shock_damper.lsr])

	phase = "pedal"
	var crank0 := bike.crank_angle
	await wait(6.0)
	var v := bike.linear_velocity.length()
	check("pedals up to speed", v > 6.0 and v < 14.0, "%.1f km/h after 6 s" % (v * 3.6))
	check("cranks turn", bike.crank_angle - crank0 > TAU * 4.0, "%.1f revs, %d rpm" % [(bike.crank_angle - crank0) / TAU, int(bike.cadence_rpm)])
	check("upright pedalling", absf(roll_deg()) < 5.0, "roll %.1f deg" % roll_deg())
	var heading0 := -bike.global_transform.basis.z

	phase = "turn"
	await wait(3.0)
	var heading1 := -bike.global_transform.basis.z
	var yaw := rad_to_deg(heading0.signed_angle_to(heading1, Vector3.UP))
	check("steers left", yaw > 15.0, "turned %.0f deg" % yaw)
	check("leans into the turn (left)", roll_deg() > 4.0 and roll_deg() < 45.0, "roll %.1f deg" % roll_deg())
	check("still on two wheels", bike.rear.contact and bike.front.contact, "")

	phase = "turnbrake"
	var tb_worst := 0.0
	var tb_flipped := false
	for i in int(1.5 * Engine.physics_ticks_per_second):
		await physics_frame
		tb_worst = maxf(tb_worst, absf(roll_deg()))
		if bike.global_transform.basis.y.dot(Vector3.UP) < 0.3:
			tb_flipped = true
	check("brakes mid-corner without crashing", not tb_flipped and tb_worst < 45.0,
		"max roll %.1f, now %.1f km/h" % [tb_worst, bike.linear_velocity.length() * 3.6])
	phase = "straight"
	await wait(3.0)
	var v0 := bike.linear_velocity.length()
	phase = "brake"
	await wait(0.5)
	var decel := (v0 - bike.linear_velocity.length()) / 0.5
	check("hard braking ~0.5-0.9 g, no endo", decel > 4.5 and decel < 9.5 and bike.rear.contact, "%.1f m/s^2" % decel)
	await wait(3.0)
	check("brakes to a stop", bike.linear_velocity.length() < 0.3, "%.2f m/s" % bike.linear_velocity.length())
	check("upright after stop", absf(roll_deg()) < 5.0, "roll %.1f deg" % roll_deg())

	# 1 m flat drop
	phase = "settle"
	bike.reset_bike(Transform3D(Basis(), Vector3(-60, 1.0, 80)))
	await wait(0.05)
	bike.rear.max_s = 0.0
	bike.front.max_s = 0.0
	var max_v := 0.0
	for i in int(2.5 * Engine.physics_ticks_per_second):
		await physics_frame
		max_v = maxf(max_v, bike.linear_velocity.length())
	check("drop uses most of the travel", bike.rear.max_s / bike.rear.travel > 0.55, "rear %.0f%%, fork %.0f%%" %
		[bike.rear.max_s / bike.rear.travel * 100, bike.front.max_s / bike.front.travel * 100])
	check("drop doesn't explode", max_v < 6.0, "max speed %.1f m/s" % max_v)
	check("lands upright", absf(roll_deg()) < 4.0 and bike.rear.contact and bike.front.contact, "roll %.1f" % roll_deg())

	# bunny hop
	phase = "hopload"
	await wait(0.6)
	phase = "settle"
	var max_y := 0.0
	var y0 := bike.global_position.y
	var land_r := 0.0
	var land_f := 0.0
	var was_air := false
	for i in int(1.5 * Engine.physics_ticks_per_second):
		await physics_frame
		max_y = maxf(max_y, bike.global_position.y - y0)
		if not (bike.rear.contact or bike.front.contact):
			was_air = true
		elif was_air:
			land_r = maxf(land_r, bike.rear.s / bike.rear.travel)
			land_f = maxf(land_f, bike.front.s / bike.front.travel)
	check("bunny hop leaves the ground", max_y > 0.10, "%.2f m" % max_y)
	check("bunny hop landing doesn't bottom out", was_air and land_r < 0.75 and land_f < 0.75,
		"landing used rear %.0f%%, fork %.0f%% (sag included)" % [land_r * 100, land_f * 100])
	await wait(1.5)
	check("upright after hop", absf(roll_deg()) < 5.0, "roll %.1f" % roll_deg())

	# ride into the side of the kicker deck: must not launch the bike
	phase = "pedal"
	bike.reset_bike(Transform3D(Basis(Vector3.UP, PI / 2), Vector3(2.0, 0.05, -30.0)))
	await wait(0.05)
	var vmax := 0.0
	for i in int(4.0 * Engine.physics_ticks_per_second):
		await physics_frame
		vmax = maxf(vmax, bike.linear_velocity.length())
	check("hitting a wall doesn't launch the bike", vmax < 9.0, "max speed %.1f m/s" % vmax)

	# hard, jerky steering with repeated hops (open ground): no wild tumbling
	phase = "wild"
	bike.reset_bike(Transform3D(Basis(), Vector3(120.0, 0.05, 0.0)))
	await wait(0.05)
	var max_twist := 0.0
	var flips := 0
	var was_flipped := false
	for i in int(8.0 * Engine.physics_ticks_per_second):
		await physics_frame
		var wl := bike.global_transform.basis.inverse() * bike.angular_velocity
		max_twist = maxf(max_twist, maxf(absf(wl.y), absf(wl.z)))
		var flipped := bike.global_transform.basis.y.dot(Vector3.UP) < 0.3
		if flipped and not was_flipped:
			flips += 1
		was_flipped = flipped
	check("jerky steering + hops: no tumbling", flips == 0 and max_twist <= 5.01, "flips %d, max roll/yaw rate %.1f rad/s" % [flips, max_twist])

	# rollers and the drop, with a bit of steering, at several speeds: stay up
	for spot in [["rollers", Vector3(5.0, 0.05, -6.0), 7.0], ["drop", Vector3(-5.0, 0.05, -12.0), 6.0]]:
		for spd in [4.0, 6.0, 8.0, 10.0]:
			phase = "line"
			line_speed = spd
			bike.reset_bike(Transform3D(Basis(), spot[1]))
			await wait(0.05)
			var crashed := false
			var worst_roll := 0.0
			var worst_at := Vector3.ZERO
			var worst_hand := 0.0
			var visn = bike.get_node("Visual")
			for i in int(float(spot[2]) * Engine.physics_ticks_per_second):
				await physics_frame
				worst_hand = maxf(worst_hand, visn.hand_miss)
				if absf(roll_deg()) > worst_roll:
					worst_roll = absf(roll_deg())
					worst_at = bike.global_position
				if bike.global_transform.basis.y.dot(Vector3.UP) < 0.3:
					crashed = true
			check("%s at %d km/h stays up, hands on bars" % [spot[0], int(spd * 3.6)], not crashed and worst_roll < 40.0 and worst_hand < 0.02,
				"max roll %.0f deg, hands up to %.1f cm off" % [worst_roll, worst_hand * 100])

	# switching full lock from one side to the other (W+A <-> W+D, S+A <-> S+D)
	for combo in [[1.0, 0.0, 1.5, "W+A <-> W+D"], [1.0, 0.0, 0.6, "W+A <-> W+D quick"], [0.0, 1.0, 1.0, "S+A <-> S+D"], [1.0, 0.0, 3.0, "W+A <-> W+D slow"], [1.0, 0.0, 2.0, "W+A <-> W+D 2 s"], [1.0, 0.0, 1.0, "W+A <-> W+D 1 s"], [1.0, 0.0, 0.4, "W+A <-> W+D weaving"]]:
		phase = "flip"
		flip_pedal = combo[0]
		flip_brake = combo[1]
		flip_period = combo[2]
		bike.reset_bike(Transform3D(Basis(), Vector3(150, 0.05, -150)))
		await wait(0.05)
		if flip_brake > 0.0:
			# get some speed first
			phase = "pedal"
			await wait(3.0)
			phase = "flip"
		bike.sim_time = 0.0
		var worst := 0.0
		var fell := false
		for i in int(8.0 * Engine.physics_ticks_per_second):
			await physics_frame
			worst = maxf(worst, absf(roll_deg()))
			if bike.global_transform.basis.y.dot(Vector3.UP) < 0.4:
				fell = true
		check("steer switch %s: stays up" % combo[3], not fell and worst < 39.0, "max lean %.0f deg, %.0f km/h at end" % [worst, bike.linear_velocity.length() * 3.6])

	# turning tightens the longer the key is held; quick taps stay gentle
	phase = "holdturn"
	bike.reset_bike(Transform3D(Basis(), Vector3(-150, 0.05, 150)))
	await wait(0.05)
	phase = "pedal"
	await wait(4.0)
	phase = "holdturn"
	await wait(0.3)
	var yaw_early := absf(bike.angular_velocity.y)
	await wait(2.0)
	var yaw_late := absf(bike.angular_velocity.y)
	var v_turn := bike.linear_velocity.length()
	check("holding the turn tightens it", yaw_late > yaw_early * 2.0 and yaw_late > 0.6,
		"yaw %.2f rad/s after 0.3 s, %.2f after 2.3 s (radius %.1f m at %.0f km/h)" % [yaw_early, yaw_late, v_turn / maxf(yaw_late, 0.01), v_turn * 3.6])

	# hands follow the bars when steering
	phase = "settle"
	bike.reset_bike(Transform3D(Basis(), Vector3(-80, 0.05, -80)))
	await wait(1.0)
	var vis = bike.get_node("Visual")
	var grip_err := func() -> float:
		var steer: Node3D = vis.parts["Steer"]
		var D: Transform3D = steer.transform * (vis.rest["Steer"] as Transform3D).affine_inverse()
		var g: Array = bike.geo["grip"]
		var worst := 0.0
		for s in [1, -1]:
			var grip := D * Vector3(0.322 * s, g[1], -g[0])
			var hb: int = vis.skel.find_bone("hand." + ("R" if s == 1 else "L"))
			var wrist: Vector3 = vis.skel.get_bone_global_pose(hb).origin
			worst = maxf(worst, wrist.distance_to(grip))
		return worst
	await process_frame
	var e_straight: float = grip_err.call()
	phase = "steerstill"
	await wait(1.0)
	await process_frame
	await process_frame
	var e_turned: float = grip_err.call()
	check("hands stay on the grips when steering", vis.hand_miss < 0.01 and absf(e_turned - e_straight) < 0.02 and absf(bike.bar_angle) > 0.4,
		"bars %.0f deg, hands %.1f cm off target; wrist-to-grip %.3f m straight vs %.3f m turned" % [rad_to_deg(bike.bar_angle), vis.hand_miss * 100, e_straight, e_turned])

	# feet stay on the pedals (ankle a shoe's length from the pedal axle)
	phase = "pedal"
	bike.reset_bike(Transform3D(Basis(), Vector3(-120, 0.05, 0)))
	var worst_foot := 0.0
	for i in 240:
		await physics_frame
		if i < 60:
			continue
		var v2 = bike.get_node("Visual")
		for s in ["R", "L"]:
			var fb: int = v2.skel.find_bone("foot." + s)
			var ankle: Vector3 = v2.skel.get_bone_global_pose(fb).origin
			var pedal: Vector3 = (v2.parts["Pedal" + s] as Node3D).global_position
			var ped_local: Vector3 = (v2.model as Node3D).global_transform.affine_inverse() * pedal
			worst_foot = maxf(worst_foot, ankle.distance_to(ped_local))
	check("feet stay on the pedals", worst_foot < 0.20, "ankle up to %.2f m from the pedal axle" % worst_foot)

	# W + Space (pedalling while crouched to load a hop): knees mustn't flip
	phase = "pedal"
	bike.reset_bike(Transform3D(Basis(), Vector3(-120, 0.05, 60)))
	await wait(1.0)
	phase = "pedalhop"
	var vk = bike.get_node("Visual")
	var knees := [vk.skel.find_bone("shin.L"), vk.skel.find_bone("shin.R")]
	var prev_k := []
	var knee_step := 0.0
	for i in 240:
		await physics_frame
		var cur := []
		for b in knees:
			cur.append(vk.skel.get_bone_global_pose(b).origin)
		if prev_k.size() == 2:
			for k in 2:
				knee_step = maxf(knee_step, (cur[k] as Vector3).distance_to(prev_k[k]))
		prev_k = cur
	check("pedalling while loading a hop: knees don't jump", knee_step < 0.04, "max knee move %.1f cm per tick" % (knee_step * 100.0))

	# rollers: the rear wheel follows the humps instead of chattering
	phase = "line"
	line_speed = 4.0
	bike.reset_bike(Transform3D(Basis(), Vector3(5, 0.05, -5)))
	await wait(0.05)
	var toggles := 0
	var last_c := true
	var hist := []
	var chatter := 0.0
	for i in int(14.0 * Engine.physics_ticks_per_second):
		await physics_frame
		var z := bike.global_position.z
		if z > -12.5:
			continue
		if z < -40.0:
			break
		if bike.rear.contact != last_c:
			toggles += 1
		last_c = bike.rear.contact
		hist.append(bike.rear.s)
		if hist.size() >= 3:
			chatter += absf(hist[-1] - 2.0 * hist[-2] + hist[-3])
	# (pumping adds speed over the crests, so it may float a crest or two)
	check("rollers: rear wheel doesn't chatter", toggles <= 4 and chatter < 0.5, "contact lost %d times, roughness %.2f" % [toggles, chatter])

	# the trail: rock garden and tabletop at a light pedal
	phase = "trail"
	for eff in [0.0, 0.3, 0.6]:
		trail_effort = eff
		bike.reset_bike(Trail.start_xform())
		await wait(0.05)
		bike.sim_time = 0.0
		var worst_tilt := 0.0
		var fell_t := false
		var lip_v := 0.0
		for i in int(14.0 * Engine.physics_ticks_per_second):
			await physics_frame
			var p := bike.global_position
			if p.z < -24.5 and p.z > -25.5:
				lip_v = bike.linear_velocity.length()
			worst_tilt = maxf(worst_tilt, absf(roll_deg()))
			if bike.global_transform.basis.y.dot(Vector3.UP) < 0.4:
				fell_t = true
			if p.z < -45.0:
				break
		var done := bike.global_position.z < -40.0
		check("trail (pedal %.0f%%): rock garden + jump, stays up" % (eff * 100), done and not fell_t and worst_tilt < 40.0,
			"lip %.1f m/s, max lean %.0f deg, reached z %.0f" % [lip_v, worst_tilt, bike.global_position.z])

	# top speed: the rider shifts through the cassette
	phase = "sprint"
	bike.reset_bike(Transform3D(Basis(), Vector3(150, 0.05, 150)))
	await wait(20.0)
	check("top speed with gears", bike.speed_kmh() > 42.0 and bike.gear >= 9, "%.0f km/h after 20 s, gear %d (%dt)" % [bike.speed_kmh(), bike.gear + 1, bike.cog_teeth()])

	# wheelie: pedal + lean back holds the front up without looping out
	phase = "wheelie_in"
	bike.reset_bike(Transform3D(Basis(), Vector3(-150, 0.05, 150)))
	await wait(3.0)
	phase = "wheelie"
	var wmax := -90.0
	var wmin := 90.0
	var up_ticks := 0
	for i in int(5.0 * Engine.physics_ticks_per_second):
		await physics_frame
		var pd := rad_to_deg(asin(clampf((-bike.global_transform.basis.z).y, -1.0, 1.0)))
		wmax = maxf(wmax, pd)
		if i > 120:
			wmin = minf(wmin, pd)
		if bike.rear.contact and not bike.front.contact:
			up_ticks += 1
	check("wheelie holds", wmin > 15.0 and wmax < 40.0 and up_ticks > 4.0 * Engine.physics_ticks_per_second,
		"pitch %.0f-%.0f deg, front up %.1f of 5 s" % [wmin, wmax, up_ticks / Engine.physics_ticks_per_second])

	# tricks off the trail's tabletop
	phase = "trail"
	trail_effort = 0.6
	for tr in [[{"tilt": 1.0}, "backflip", 0], [{"steer": 1.0}, "360 spin", 1], [{"tilt": -1.0}, "frontflip", 0]]:
		trick = tr[0]
		trick_rot = Vector3.ZERO
		bike.reset_bike(Trail.start_xform())
		await wait(0.05)
		bike.sim_time = 0.0
		var prev_b := bike.global_transform.basis
		var airborne := false
		var landed_up := -1.0
		var crashed := false
		for i in int(14.0 * Engine.physics_ticks_per_second):
			await physics_frame
			var in_air := not (bike.rear.contact or bike.front.contact)
			if in_air and bike.global_position.z < -24.0 and landed_up < -0.5:
				airborne = true
				trick_rot += (prev_b.inverse() * bike.global_transform.basis).get_euler()
			elif airborne and landed_up < -0.5:
				landed_up = bike.global_transform.basis.y.dot(Vector3.UP)
			prev_b = bike.global_transform.basis
			# a crash is ending up upside down on the ground (in the air it's the flip)
			if bike.upside_down_time > 0.2 and (bike.rear.contact or bike.front.contact):
				crashed = true
			if bike.global_position.z < -45.0:
				break
		var turned := absf(rad_to_deg(trick_rot.x if tr[2] == 0 else trick_rot.y))
		check("%s off the tabletop lands" % tr[1], turned > 290.0 and landed_up > 0.6 and not crashed and bike.global_position.z < -40.0,
			"rotated %.0f deg, landed with up %.2f" % [turned, landed_up])
	trick = {}

	# the dirt jump park: each line start to finish
	var park: Park = bike.get_parent().get_node("Park")
	var flow_start := Transform3D(Basis(Vector3.UP, PI), Park.plan_to_world(Vector2(park.pro_len + 1.0, Park.Y_FLOW), 0.05))
	var runs := [["pro line, full pedal", Park.start_xform("pro"), 0.0, -1.0, 1.0, Park.ORIGIN.y - park.pro_len + 1.0],
		["pro line, 80% pedal", Park.start_xform("pro"), 0.0, -1.0, 0.8, Park.ORIGIN.y - park.pro_len + 1.0],
		["beginner line", Park.start_xform("beginner"), -8.0, -1.0, 1.0, Park.ORIGIN.y - park.beg_len + 1.0],
		["flow line", flow_start, 13.0, 1.0, 1.0, Park.ORIGIN.y - (park.pro_len - park.flow_len) - 1.0]]
	phase = "park"
	for r in runs:
		park_x = r[2]
		park_dir = r[3]
		park_effort = r[4]
		bike.reset_bike(r[1])
		await wait(0.05)
		bike.sim_time = 0.0
		var fell_p := false
		var done_p := false
		var tilt_p := 0.0
		for i in int(20.0 * Engine.physics_ticks_per_second):
			await physics_frame
			tilt_p = maxf(tilt_p, absf(roll_deg()))
			if bike.global_transform.basis.y.dot(Vector3.UP) < 0.4:
				fell_p = true
			var z := bike.global_position.z
			if (park_dir < 0.0 and z < r[5]) or (park_dir > 0.0 and z > r[5]):
				done_p = true
				break
		check("park: %s, start to finish" % r[0], done_p and not fell_p, "max lean %.0f deg, %.0f km/h at the end" % [tilt_p, bike.speed_kmh()])

	print("RESULT: %s (%d failed)" % ["OK" if fails == 0 else "FAILED", fails])
	quit(1 if fails else 0)
