extends SceneTree
## Renders the phone layout:  xvfb-run godot --path game -s tests/touch_shot.gd -- OUT.png --touch
func _initialize():
	var main: Node = load("res://main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred(main)
func _run(main):
	for i in 120: await process_frame
	# press PEDAL and LEFT with two fingers, as a player would
	var tc = main.get_node("TouchControls")
	for n in ["pedal", "left"]:
		var b: TouchScreenButton = tc.buttons[n]
		var ev := InputEventScreenTouch.new()
		ev.index = 0 if n == "pedal" else 1
		ev.pressed = true
		ev.position = b.position + b.texture_normal.get_size() * 0.5
		ev.position = root.get_final_transform() * ev.position
		Input.parse_input_event(ev)
	for i in 150: await process_frame
	print("pedal pressed: ", Input.is_action_pressed("pedal"), " steer_left: ", Input.is_action_pressed("steer_left"), " speed ", main.bike.speed_kmh(), " steer ", main.bike.steer_angle)
	root.get_viewport().get_texture().get_image().save_png(OS.get_cmdline_user_args()[0])
	quit()
