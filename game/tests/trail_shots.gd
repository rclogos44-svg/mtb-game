extends SceneTree
var out := "user://"
var mode := "trail"
func pilot(_b, t):
	if mode == "crouch":
		return {"pedal": 0.6, "hop": true}
	var off: float = _b.global_position.x - Trail.X0
	var yaw_err: float = (-_b.global_transform.basis.z).x
	return {"pedal": 1.0 if t < 1.5 else 0.4, "steer": clampf(off * 0.6 + yaw_err * 3.0, -1.0, 1.0)}
func _initialize():
	out = OS.get_cmdline_user_args()[0]
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred(main)
func snap(n):
	await process_frame
	root.get_viewport().get_texture().get_image().save_png(out.path_join(n + ".png"))
func _run(main):
	await process_frame
	var bike: Bike = main.bike
	var cam = main.cam
	bike.autopilot = pilot
	bike.reset_bike(Trail.start_xform())
	bike.sim_time = 0.0
	var shot := {"top": false, "rocks": false, "air": false, "land": false}
	for i in 1400:
		await process_frame
		var z := bike.global_position.z
		if not shot.top and z < 12.0: shot.top = true; await snap("t1_top")
		if not shot.rocks and z < -3.0: shot.rocks = true; await snap("t2_rocks")
		if not shot.air and z < -27.5: shot.air = true; await snap("t3_air")
		if not shot.land and z < -33.0: shot.land = true; await snap("t4_land")
		if z < -38: break
	# overview from the side
	cam.mode = 2
	cam.yaw = -1.35
	cam.pitch = -0.25
	cam.dist = 30.0
	bike.reset_bike(Transform3D(Basis(), Vector3(22, 3.05, -26.5)))
	bike.autopilot = func(_b, _t): return {}
	for i in 90: await process_frame
	await snap("t5_overview")
	cam.dist = 9.0
	cam.yaw = -0.5
	bike.reset_bike(Transform3D(Basis(), Vector3(22, 4.0, -2.0)))
	for i in 90: await process_frame
	await snap("t6_rockgarden")
	mode = "crouch"
	bike.autopilot = pilot
	cam.mode = 1
	bike.reset_bike(Transform3D(Basis(), Vector3(-60, 0.05, 60)))
	for i in 200: await process_frame
	await snap("t7_crouch_pedal")
	cam.mode = 2
	cam.yaw = 1.75
	cam.pitch = -0.1
	cam.dist = 2.2
	for i in 60: await process_frame
	await snap("t8_crouch_close")
	quit()
