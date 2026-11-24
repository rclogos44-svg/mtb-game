extends SceneTree
## Renders a few frames of the game to PNGs (needs a display, e.g. xvfb-run):
##   godot --path game --rendering-method gl_compatibility -s tests/screenshots.gd -- OUT_DIR

var out := "user://"
var phase := "pedal"


func pilot(_b, t) -> Dictionary:
	if phase == "pedal":
		return {"pedal": 0.7, "steer": 0.15 * sin(t * 0.8)}
	if phase == "steer":
		return {"steer": 1.0}
	if phase == "compress":
		return {"hop": true}
	return {}


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out = args[0]
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred(main)


func snap(name: String) -> void:
	await process_frame
	await process_frame
	root.get_viewport().get_texture().get_image().save_png(out.path_join(name + ".png"))
	print("saved ", name)


func frames(n: int) -> void:
	for i in n:
		await process_frame


func _run(main) -> void:
	await process_frame
	var bike: Bike = main.bike
	var cam = main.cam
	bike.autopilot = pilot
	bike.reset_bike(Transform3D(Basis(), Vector3(20, 0.05, 60)))
	await frames(150)
	await snap("chase")
	cam.mode = 1  # side
	await frames(90)
	await snap("side_pedal")
	phase = "compress"
	await frames(40)
	await snap("side_compressed")
	phase = "coast"
	cam.mode = 2  # orbit
	cam.yaw = 2.3
	cam.pitch = -0.15
	cam.dist = 2.6
	await frames(120)
	await snap("orbit_front")
	phase = "steer"
	bike.reset_bike(Transform3D(Basis(), Vector3(-60, 0.05, 60)))
	cam.mode = 2
	cam.yaw = 2.6
	cam.pitch = -0.35
	cam.dist = 2.2
	await frames(120)
	await snap("steer_hands")
	quit()
