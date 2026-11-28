extends Node3D
## Test ground: a big flat baseplate with a few rollers and a small drop off to
## one side so the suspension has something to do. Builds the bike, camera and
## HUD and sets up keyboard + controller bindings.

const BikeScript := preload("res://scripts/bike.gd")
const VisualScript := preload("res://scripts/bike_visual.gd")
const CameraScript := preload("res://scripts/camera_rig.gd")
const HudScript := preload("res://scripts/hud.gd")

var bike: Bike
var cam: Node3D


func _ready() -> void:
	_bind_inputs()
	_environment()
	_ground()
	_features()
	bike = make_bike(Transform3D(Basis(), Vector3(0, 0.05, 0)))
	add_child(bike)
	cam = Node3D.new()
	cam.set_script(CameraScript)
	cam.name = "CameraRig"
	cam.set("target_path", bike.get_path())
	add_child(cam)
	var touch := is_touch()
	var hud := CanvasLayer.new()
	hud.set_script(HudScript)
	hud.set("bike_path", bike.get_path())
	hud.set("compact", touch)
	add_child(hud)
	if touch:
		var tc := CanvasLayer.new()
		tc.set_script(load("res://scripts/touch_controls.gd"))
		tc.name = "TouchControls"
		add_child(tc)
		# phones: lighter shadows so it keeps a steady frame rate
		RenderingServer.directional_shadow_atlas_set_size(2048, true)


## Phones and tablets (or --touch on the command line, for testing).
static func is_touch() -> bool:
	return DisplayServer.is_touchscreen_available() or OS.has_feature("web_android") \
		or OS.has_feature("web_ios") or OS.get_cmdline_user_args().has("--touch")


func _unhandled_input(e: InputEvent) -> void:
	if e.is_action_pressed("goto_trail"):
		bike.reset_bike(Trail.start_xform())
	elif e.is_action_pressed("goto_park"):
		bike.reset_bike(Park.start_xform("pro"))
	elif e.is_action_pressed("goto_park_easy"):
		bike.reset_bike(Park.start_xform("beginner"))
	elif e.is_action_pressed("goto_base"):
		bike.reset_bike(Transform3D(Basis(), Vector3(0, 0.05, 0)))


static func make_bike(xform: Transform3D) -> Bike:
	var b := RigidBody3D.new()
	b.set_script(BikeScript)
	b.name = "Bike"
	b.transform = xform
	# body collider: only touches the ground when you crash
	var col := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.35, 0.55, 0.95)
	col.shape = box
	col.position = Vector3(0, 0.95, -0.05)
	b.add_child(col)
	var pm := PhysicsMaterial.new()
	pm.friction = 0.6
	pm.bounce = 0.05
	b.physics_material_override = pm
	var vis := Node3D.new()
	vis.name = "Visual"
	vis.set_script(VisualScript)
	var model: Node3D = load("res://assets/bike.glb").instantiate()
	model.name = "BikeModel"
	vis.add_child(model)
	var rider: Node3D = load("res://assets/rider.glb").instantiate()
	rider.name = "Rider"
	vis.add_child(rider)
	b.add_child(vis)
	return b


func _bind_inputs() -> void:
	var keys := {
		"pedal": [KEY_W], "brake": [KEY_S],
		"tilt_back": [KEY_DOWN], "tilt_forward": [KEY_UP],
		"steer_left": [KEY_A, KEY_LEFT], "steer_right": [KEY_D, KEY_RIGHT],
		"hop": [KEY_SPACE], "reset": [KEY_R], "camera": [KEY_C], "slowmo": [KEY_T],
		"goto_trail": [KEY_2, KEY_G], "goto_base": [KEY_1],
		"goto_park": [KEY_3, KEY_P], "goto_park_easy": [KEY_4],
	}
	for action in keys:
		if not InputMap.has_action(action):
			InputMap.add_action(action, 0.15)
		for k in keys[action]:
			var e := InputEventKey.new()
			e.physical_keycode = k
			InputMap.action_add_event(action, e)
	var axes := {"pedal": [JOY_AXIS_TRIGGER_RIGHT, 1.0], "brake": [JOY_AXIS_TRIGGER_LEFT, 1.0],
		"steer_left": [JOY_AXIS_LEFT_X, -1.0], "steer_right": [JOY_AXIS_LEFT_X, 1.0],
		"tilt_back": [JOY_AXIS_RIGHT_Y, 1.0], "tilt_forward": [JOY_AXIS_RIGHT_Y, -1.0]}
	for action in axes:
		var j := InputEventJoypadMotion.new()
		j.axis = axes[action][0]
		j.axis_value = axes[action][1]
		InputMap.action_add_event(action, j)
	var buttons := {"hop": JOY_BUTTON_A, "reset": JOY_BUTTON_Y, "camera": JOY_BUTTON_X, "slowmo": JOY_BUTTON_BACK}
	for action in buttons:
		var jb := InputEventJoypadButton.new()
		jb.button_index = buttons[action]
		InputMap.action_add_event(action, jb)


func _environment() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.32, 0.52, 0.80)
	sm.sky_horizon_color = Color(0.72, 0.80, 0.88)
	sm.ground_horizon_color = Color(0.55, 0.52, 0.47)
	sm.ground_bottom_color = Color(0.30, 0.27, 0.23)
	sky.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.9
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_density = 0.002
	env.fog_light_color = Color(0.72, 0.8, 0.88)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48, -35, 0)
	sun.light_energy = 1.25
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 35.0 if is_touch() else 60.0
	add_child(sun)


func _ground() -> void:
	var body := StaticBody3D.new()
	body.name = "Ground"
	var col := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(600, 2, 600)
	col.shape = box
	col.position = Vector3(0, -1, 0)
	body.add_child(col)
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(600, 600)
	mi.mesh = pm
	var mat := ShaderMaterial.new()
	mat.shader = load("res://scripts/ground.gdshader")
	mi.material_override = mat
	body.add_child(mi)
	add_child(body)


func _dirt() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.46, 0.33, 0.22)
	m.roughness = 0.95
	return m


func _features() -> void:
	# a line of rollers straight ahead of the spawn, off to the right: smooth
	# pump-track humps (a cosine profile, no edges where they meet the ground)
	var rollers := CSGPolygon3D.new()
	var pts := PackedVector2Array()
	var n_rollers := 5
	var length := 4.6
	var height := 0.40
	var steps := 40 * n_rollers
	for k in steps + 1:
		var u := float(k) / steps * n_rollers * length
		pts.append(Vector2(u, height * 0.5 * (1.0 - cos(TAU * u / length))))
	pts.append(Vector2(n_rollers * length, -0.05))
	pts.append(Vector2(0.0, -0.05))
	rollers.polygon = pts
	rollers.depth = 3.5
	rollers.smooth_faces = true
	rollers.use_collision = true
	rollers.material = _dirt()
	rollers.rotation_degrees = Vector3(0, 90, 0)          # profile runs toward -Z
	rollers.position = Vector3(6.75, 0.0, -18.0 + length * 0.5)  # crests at z = -18, -22.6, ...
	add_child(rollers)
	# the trail: climb, rock garden descent, tabletop jump (see trail.gd)
	var trail := Node3D.new()
	trail.set_script(load("res://scripts/trail.gd"))
	trail.name = "Trail"
	add_child(trail)
	# the dirt jump park from the blueprint, behind the rollers (see park.gd)
	var park := Node3D.new()
	park.set_script(load("res://scripts/park.gd"))
	park.name = "Park"
	add_child(park)
	# kicker up onto a platform with a 0.7 m drop off the end
	var deck := CSGBox3D.new()
	deck.size = Vector3(3.5, 0.7, 6.0)
	deck.position = Vector3(-5.0, 0.35, -30.0)
	deck.use_collision = true
	deck.material = _dirt()
	add_child(deck)
	var ramp := CSGPolygon3D.new()
	ramp.polygon = PackedVector2Array([Vector2(0, 0), Vector2(4.0, 0), Vector2(4.0, 0.7)])
	ramp.depth = 3.5
	ramp.use_collision = true
	ramp.material = _dirt()
	# polygon is in XY, extruded along -Z: turn it so it climbs toward -Z
	ramp.rotation_degrees = Vector3(0, 90, 0)
	ramp.position = Vector3(-3.25, 0, -23.0)   # extrudes toward -X, under the deck
	add_child(ramp)
