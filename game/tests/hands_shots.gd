extends SceneTree
var out := "user://"
var steer := 0.0
func pilot(_b, _t) -> Dictionary:
	return {"pedal": 0.6 if _b.linear_velocity.length() < 3.0 else 0.0, "steer": steer}
func _initialize() -> void:
	out = OS.get_cmdline_user_args()[0]
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred(main)
func frames(n: int) -> void:
	for i in n: await process_frame
func _run(main) -> void:
	await process_frame
	var bike: Bike = main.bike
	bike.autopilot = pilot
	bike.reset_bike(Transform3D(Basis(), Vector3(40, 0.05, 40)))
	main.cam.dist = 2.4
	for s in [0.0, 1.0, -1.0]:
		steer = s
		await frames(90)
		await process_frame
		root.get_viewport().get_texture().get_image().save_png(out.path_join("hands_%s.png" % str(s)))
		print("saved ", s)
	quit()
