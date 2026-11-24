extends SceneTree
## Headless ride test:  godot --headless --path game -s tests/sim_test.gd
## Drives the bike with an autopilot and checks the physics behaves like a bike.

var bike: Bike
var fails := 0
var phase := "settle"
var t0 := 0.0


func check(name: String, ok: bool, detail: String) -> void:
	print(("PASS " if ok else "FAIL ") + name + "  " + detail)
	if not ok:
		fails += 1


func pilot(_b, _t) -> Dictionary:
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
		"hopload":
			return {"hop": true}
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
	check("steers left", yaw > 30.0, "turned %.0f deg" % yaw)
	check("leans into the turn (left)", roll_deg() > 4.0 and roll_deg() < 45.0, "roll %.1f deg" % roll_deg())
	check("still on two wheels", bike.rear.contact and bike.front.contact, "")

	phase = "turnbrake"
	await wait(1.5)
	check("brakes mid-corner without crashing", absf(roll_deg()) < 40.0 and bike.rear.contact and bike.front.contact,
		"roll %.1f, %.1f km/h" % [roll_deg(), bike.linear_velocity.length() * 3.6])
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
	for i in int(1.5 * Engine.physics_ticks_per_second):
		await physics_frame
		max_y = maxf(max_y, bike.global_position.y - y0)
	check("bunny hop leaves the ground", max_y > 0.10, "%.2f m" % max_y)
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

	print("RESULT: %s (%d failed)" % ["OK" if fails == 0 else "FAILED", fails])
	quit(1 if fails else 0)
