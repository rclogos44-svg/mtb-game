extends Node3D
## Follow camera. C cycles: chase (behind), side (watch the suspension work),
## orbit (right-drag / right stick to look around). Mouse wheel zooms.

@export var target_path: NodePath

enum Mode { CHASE, SIDE, ORBIT }
var mode := Mode.CHASE
var cam: Camera3D
var target: Node3D
var yaw := 0.0
var pitch := -0.18
var dist := 4.3
var _pos := Vector3.ZERO
var _look := Vector3.ZERO
var _heading := Vector3.FORWARD


func _ready() -> void:
	cam = Camera3D.new()
	cam.fov = 62.0
	cam.near = 0.05
	add_child(cam)
	cam.current = true
	cam.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	target = get_node_or_null(target_path)
	if target:
		_pos = target.global_position + Vector3(0, 1.6, 3.4)
		_look = target.global_position


func _unhandled_input(e: InputEvent) -> void:
	if e is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		yaw -= e.relative.x * 0.006
		pitch = clampf(pitch - e.relative.y * 0.005, -1.2, 0.5)
		if mode == Mode.CHASE:
			mode = Mode.ORBIT
	elif e is InputEventMouseButton and e.pressed:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP:
			dist = maxf(1.4, dist * 0.9)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			dist = minf(12.0, dist * 1.1)
	if e.is_action_pressed("camera"):
		mode = (mode + 1) % 3 as Mode
		yaw = 0.0
	if e.is_action_pressed("slowmo"):
		Engine.time_scale = 0.25 if Engine.time_scale > 0.5 else 1.0


func _process(dt: float) -> void:
	if target == null:
		target = get_node_or_null(target_path)
		if target == null:
			return
	var rs := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var t := target.global_transform
	var fwd := -t.basis.z
	fwd.y = 0.0
	# in the air follow the direction of travel, not where the bike points,
	# so a 360 spins in front of the camera instead of swinging it round
	if target is Bike and not (target.rear.contact or target.front.contact):
		var hv: Vector3 = target.linear_velocity
		hv.y = 0.0
		if hv.length() > 1.5:
			fwd = hv
	if fwd.length() > 0.1:
		# ease toward the new heading (lerp + normalise: slerp between two almost
		# equal directions builds a slightly non-unit axis and errors every frame)
		var nh := _heading.lerp(fwd.normalized(), 1.0 - exp(-4.0 * dt))
		if nh.length() > 0.01:
			_heading = nh.normalized()
	var center := t.origin + Vector3(0, 0.85, 0)
	var desired: Vector3
	match mode:
		Mode.CHASE:
			var back := -_heading.rotated(Vector3.UP, yaw)
			desired = center + back * dist * cos(pitch) + Vector3.UP * (0.55 + dist * -sin(pitch))
		Mode.SIDE:
			var side := _heading.cross(Vector3.UP).normalized()
			desired = center + side * 2.4 * dist / 3.4 + Vector3.UP * 0.05 - _heading * 0.15
		Mode.ORBIT:
			var dir := Vector3.BACK.rotated(Vector3.RIGHT, pitch).rotated(Vector3.UP, yaw)
			desired = center + dir * dist
	var k := 1.0 - exp(-(10.0 if mode == Mode.SIDE else 6.0) * dt)
	_pos = _pos.lerp(desired, k)
	_look = _look.lerp(center, 1.0 - exp(-14.0 * dt))
	_pos.y = maxf(_pos.y, 0.25)
	cam.global_position = _pos
	cam.look_at(_look, Vector3.UP)
