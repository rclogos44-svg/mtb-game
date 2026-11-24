class_name Bike
extends RigidBody3D
## Bike + rider as one rigid body riding on two simulated wheels.
##
## Each wheel finds the ground with a ray, works out how far its suspension
## must compress to sit on it (using a torus-shaped tyre, so leaning is right),
## and pushes back with the real spring + damper force:
##   rear  : coil shock driven through the linkage (leverage from geometry.json)
##   front : air fork along the steering axis
## Tyre grip uses a friction circle, so braking, pedalling and cornering share
## the same limit. Pedalling torque, cadence and crank angle are tracked so the
## rider's legs can follow the real cranks.

const GEO_PATH := "res://assets/geometry.json"
const TYRE_TUBE := 0.0275          # tyre cross-section radius (m)
const TYRE_RATE := 110000.0
const TYRE_RELAX_LEN := 0.25      # m
const MAX_LEAN := 0.35            # rad (20 deg)
const STEER_LAT_G := 0.25         # g of cornering at full steering (wide, gentle turns)
const LEAN_RATE := 1.3            # rad/s the rider can roll the bike
const MAX_LEAN_TORQUE := 1300.0   # N m
const MAX_ROLL_RATE_GROUND := 1.8 # rad/s        # tyre vertical stiffness once the suspension bottoms (N/m)
const GRAV := 9.81
## Ray angles round the tyre from straight down (+ = ahead of the axle).
const WHEEL_RAY_ANGLES := [-0.9, -0.6, -0.35, -0.15, 0.0, 0.15, 0.35, 0.6, 0.9]

@export_group("Rider")
@export var rider_mass := 75.0
@export var bike_mass := 15.0
@export_group("Suspension")
@export_range(0.1, 0.4) var rear_sag := 0.28
@export_range(0.1, 0.35) var fork_sag := 0.20
@export_range(0.05, 1.0) var compression_damping := 0.30   ## fraction of critical (low speed)
@export_range(0.1, 1.5) var rebound_damping := 0.60
@export_group("Tyres and drive")
@export var tyre_grip := 1.05
@export var max_drive_force := 330.0
@export var max_power := 750.0
@export var brake_force := 1150.0
@export_group("Handling")
@export var lean_stiffness := 2600.0
@export var lean_damping := 480.0
@export var rider_pitch_damping := 160.0
@export_group("Air")
@export var air_roll_stiffness := 450.0
@export var air_roll_damping := 90.0
@export var air_yaw_damping := 30.0
@export var air_pitch_stiffness := 220.0
@export var air_pitch_damping := 40.0
@export var one_wheel_recovery := 900.0
## A rider can't spin the bike faster than this about its roll / yaw axes (rad/s).
@export var max_twist_rate := 5.0

var geo: Dictionary
var linkage: RearLinkage
var shock: Suspension.CoilSpring
var shock_damper := Suspension.Damper.new()
var fork: Suspension.AirSpring
var fork_damper := Suspension.Damper.new()

var wheel_r := 0.335
var rear := Wheel.new()
var front := Wheel.new()

# rest geometry in the bike's local space (Godot axes: forward = -Z)
var rear_axle_local: Vector3
var front_axle_local: Vector3
var steer_axis_local: Vector3
var steer_origin_local: Vector3
var rear_static_load := 0.0
var front_static_load := 0.0

# controls
var in_pedal := 0.0
var in_brake := 0.0
var in_steer := 0.0
var in_hop := false
## Set to a Callable(bike, time) -> Dictionary to drive the bike without input (tests).
var autopilot: Callable

var steer_angle := 0.0
var crank_angle := 0.0
var cadence_rpm := 0.0
var hop_charge := 0.0
var lean_target := 0.0     ## rad, + = leaning left
var weight_back := 0.0      ## 0..1, rider shifting back under braking
var sim_time := 0.0
var upside_down_time := 0.0
var spawn_xform: Transform3D
var _reset_pending := false


class Wheel:
	var s := 0.0              ## suspension travel (m)
	var s_vel := 0.0          ## m/s, + = compressing
	var travel := 0.1
	var contact := false
	var point := Vector3.ZERO
	var normal := Vector3.UP
	var load := 0.0           ## ground normal force (N)
	var axle := Vector3.ZERO  ## global axle position
	var spin := 0.0           ## rad
	var omega := 0.0          ## rad/s
	var skid := false
	var max_s := 0.0          ## deepest travel used (for the HUD)
	var brake_fx := 0.0       ## brake force applied this step (N)
	var fy := 0.0             ## cornering force, lagged by the relaxation length (N)


static func uv3(p) -> Vector3:
	return Vector3(0.0, p[1], -p[0])


func _ready() -> void:
	geo = JSON.parse_string(FileAccess.get_file_as_string(GEO_PATH))
	wheel_r = geo["wheel_radius"]
	linkage = RearLinkage.new(geo)
	rear_axle_local = uv3(geo["rear_axle"])
	front_axle_local = uv3(geo["front_axle"])
	steer_axis_local = Vector3(0.0, geo["steer_axis"][1], -geo["steer_axis"][0]).normalized()
	steer_origin_local = uv3(geo["head_tube_bottom"])
	rear.travel = linkage.max_travel
	front.travel = geo["fork_travel"]

	mass = rider_mass + bike_mass
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	center_of_mass = Vector3(0.0, 1.0, 0.0)
	inertia = Vector3(14.0, 9.0, 11.0)        # pitch, yaw, roll (kg m^2)
	can_sleep = false
	linear_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	angular_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	linear_damp = 0.0
	angular_damp = 0.05
	_setup_suspension()
	spawn_xform = global_transform


## Sets air pressures for the rider's weight (sag) and damping as a fraction of
## critical, the way you would set up a real bike.
func _setup_suspension() -> void:
	var com_u := -center_of_mass.z
	var ru: float = geo["rear_axle"][0]
	var fu: float = geo["front_axle"][0]
	var front_frac := (com_u - ru) / (fu - ru)
	front_static_load = mass * GRAV * front_frac
	rear_static_load = mass * GRAV * (1.0 - front_frac)

	# rear: 210 x 55 coil shock; spring rate picked for the sag, like choosing a spring
	var stroke: float = geo["shock_stroke"]
	shock = Suspension.CoilSpring.new(stroke)
	var s_sag := rear_sag * rear.travel
	var lr := linkage.leverage_at(s_sag)
	shock.rate = rear_static_load * lr / linkage.stroke_at(s_sag)
	var kw := shock.rate_at(linkage.stroke_at(s_sag)) / (lr * lr)
	var c_crit := 2.0 * sqrt(kw * rear_static_load / GRAV)       # at the wheel
	shock_damper.lsc = compression_damping * c_crit * lr * lr  # at the shaft
	shock_damper.lsr = rebound_damping * c_crit * lr * lr
	shock_damper.hsc = shock_damper.lsc * 0.35
	shock_damper.hsr = shock_damper.lsr * 0.60
	shock_damper.knee = 0.10

	# front: 160 mm air fork, ~32 mm air piston, force along the steering axis
	var cos_a := steer_axis_local.dot(Vector3.UP)
	fork = Suspension.AirSpring.new(front.travel, 0.40, 0.21, 0.0008)
	var f_sag := fork_sag * front.travel
	fork.p0a = front_static_load * cos_a / fork.shape(f_sag)
	var kf := fork.rate(f_sag)
	var cf := 2.0 * sqrt(kf * front_static_load / GRAV)
	fork_damper.lsc = compression_damping * cf
	fork_damper.lsr = rebound_damping * cf
	fork_damper.hsc = fork_damper.lsc * 0.35
	fork_damper.hsr = fork_damper.lsr * 0.60
	fork_damper.knee = 0.25


# ------------------------------------------------------------------ forces
func _wheel_force(w: Wheel, is_rear: bool, s: float, s_vel: float) -> float:
	## Force along the suspension axis at the wheel.
	if is_rear:
		var lr := linkage.leverage_at(s)
		return (shock.force(linkage.stroke_at(s)) + shock_damper.force(s_vel / lr)) / lr
	return fork.force(s) + fork_damper.force(s_vel)


func _free_extension_speed(w: Wheel, is_rear: bool) -> float:
	## How fast an unloaded wheel can drop out, limited by rebound damping.
	if is_rear:
		var lr := linkage.leverage_at(w.s)
		var f_shaft := shock.force(linkage.stroke_at(w.s))
		return shock_damper.rebound_speed(f_shaft) * lr
	return fork_damper.rebound_speed(fork.force(w.s))


func _physics_process(dt: float) -> void:
	sim_time += dt
	_read_input()
	var xf := global_transform
	var up_b := xf.basis.y
	var right_b := xf.basis.x
	var fwd_b := -xf.basis.z
	var com_g := xf * center_of_mass

	# steering: lock shrinks with speed
	var speed := linear_velocity.length()
	# full steering asks for a firm but realistic turn: about STEER_LAT_G of
	# sideways acceleration at any speed (tan(steer) = a * wheelbase / v^2)
	var wb: float = geo["wheelbase"]
	var max_steer := minf(0.45, atan(STEER_LAT_G * GRAV * wb / maxf(speed * speed, 0.01)))
	steer_angle = move_toward(steer_angle, in_steer * max_steer, 2.0 * dt)
	var axis_g := (xf.basis * steer_axis_local).normalized()
	var steer_rot := Basis(axis_g, steer_angle)

	_wheel_step(rear, xf * rear_axle_local, up_b, right_b, true, dt, com_g, fwd_b)
	var so_g := xf * steer_origin_local
	var fa_g := so_g + steer_rot * (xf * front_axle_local - so_g)
	_wheel_step(front, fa_g, axis_g, steer_rot * right_b, false, dt, com_g, fwd_b)

	# rider weight shift: hips go back when braking
	weight_back = move_toward(weight_back, in_brake * clampf(linear_velocity.length() / 3.0, 0.0, 1.0), 3.0 * dt)
	# (centre of mass kept fixed: moving it at runtime destabilises the solver)
	var grounded := rear.contact or front.contact
	var both := rear.contact and front.contact
	if grounded:
		# on one wheel the lone tyre can't hold a full lean, so ease off
		# on one wheel the lone tyre can't hold a full lean, so ease off - unless
		# the bike is already well over, where the rider keeps full control
		var leaned := absf(up_b.cross(Vector3.UP).dot(fwd_b)) > sin(deg_to_rad(15.0))
		_lean_assist(up_b, fwd_b, 1.0 if (both or leaned) else 0.35)
		if not both:
			_one_wheel_balance(fwd_b, right_b)
		# the rider's arms and legs soak up fast pitching (braking dive, landings)
		apply_torque(right_b * (-angular_velocity.dot(right_b) * rider_pitch_damping))
	else:
		_air_control(up_b, fwd_b, right_b)
	# aerodynamic drag (rider + bike CdA ~0.55 m^2)
	var v := linear_velocity
	apply_central_force(-0.5 * 1.2 * 0.55 * v.length() * v)
	_hop(grounded, up_b, fwd_b, com_g, dt)
	_cranks(dt)
	_crash_check(up_b, dt)


func _wheel_step(w: Wheel, axle_ext: Vector3, sus_axis: Vector3, wheel_axis: Vector3,
		is_rear: bool, dt: float, com_g: Vector3, fwd_b: Vector3) -> void:
	# Probe the ground with a fan of rays round the lower half of the tyre, so
	# a bump is felt by the leading edge of the tyre (as on a real wheel), not
	# only once it is under the axle. For each hit, work out how far the axle
	# must rise along the suspension axis for the tyre to just touch that point.
	var space := get_world_3d().direct_space_state
	var down := -global_transform.basis.y
	var wfwd := down.cross(wheel_axis).normalized()          # wheel's forward, in its plane
	var top := axle_ext + sus_axis * (w.travel + 0.06)        # rays start above full travel
	var overlap := -1.0
	var n := Vector3.UP
	var a_dot_n := 1.0
	var n_ip := Vector3.ZERO
	for ang in WHEEL_RAY_ANGLES:
		var dir := (down * cos(ang) + wfwd * sin(ang)).normalized()
		var q := PhysicsRayQueryParameters3D.create(top, axle_ext + dir * (wheel_r + 0.35))
		q.exclude = [get_rid()]
		var hit := space.intersect_ray(q)
		if hit.is_empty():
			continue
		var hp: Vector3 = hit["position"]
		var hn: Vector3 = hit["normal"]
		var adn := sus_axis.dot(hn)
		if adn < 0.25:
			continue                                   # a wall: the frame collider handles that
		# tyre (a torus) against the tangent plane at this hit: exact on flat
		# ground at any lean, and on curved bumps it's touched by the leading edge
		var nip := hn - wheel_axis * hn.dot(wheel_axis)
		var h_req := (wheel_r - TYRE_TUBE) * clampf(nip.length(), 0.0, 1.0) + TYRE_TUBE
		var h_ext := (axle_ext - hp).dot(hn)
		var t := (h_req - h_ext) / adn                  # axle rise needed to sit on it
		if t > overlap:
			overlap = t
			n = hn
			n_ip = nip
			a_dot_n = adn

	# the wheel can only drop out as fast as rebound damping lets it
	var s_min := maxf(w.s - _free_extension_speed(w, is_rear) * dt - 0.0005, 0.0)
	var s_new := s_min
	w.contact = overlap > s_min
	if w.contact:
		s_new = minf(overlap, w.travel)
	w.s_vel = (s_new - w.s) / dt
	w.s = s_new
	w.max_s = maxf(w.max_s, w.s)
	w.axle = axle_ext + sus_axis * w.s
	w.skid = false
	if not w.contact:
		w.load = 0.0
		w.brake_fx = 0.0
		w.fy = 0.0
		w.omega *= 0.995
		w.spin += w.omega * dt
		return

	var f_axis := _wheel_force(w, is_rear, w.s, w.s_vel)
	# past full travel the tyre squashes; beyond ~4 cm the wheel is really
	# hitting a step/wall, which the frame collider has to deal with
	var tyre := clampf(overlap - w.travel, 0.0, 0.04)
	f_axis += tyre * TYRE_RATE
	var N := clampf(f_axis / a_dot_n, 0.0, 14000.0)
	w.load = N
	w.normal = n
	var nipn := n_ip.normalized() if n_ip.length() > 0.01 else n
	w.point = w.axle - nipn * (wheel_r - TYRE_TUBE) - n * TYRE_TUBE

	# tyre forces in the contact patch frame
	var fwd := n.cross(wheel_axis).normalized()
	var side := fwd.cross(n)
	var vel := linear_velocity + angular_velocity.cross(w.point - com_g)
	var v_long := vel.dot(fwd)
	var v_lat := vel.dot(side)
	var m_eff := N / GRAV
	var lim := tyre_grip * N
	# cornering force from slip angle (~0.12 of load per degree, saturating at
	# the grip limit near 8-9 degrees); low speeds use a floor so it stays stable
	var slip := v_lat / maxf(absf(v_long), 1.5)
	var fy_target := -clampf(slip * 7.0, -1.0, 1.0) * lim
	# a tyre builds cornering force over ~25 cm of rolling (relaxation length),
	# so landings and sudden loads don't snap the bike round
	var relax := clampf((absf(v_long) + 1.0) * dt / TYRE_RELAX_LEN, 0.0, 1.0)
	w.fy = lerpf(w.fy, fy_target, relax)
	var fy := clampf(w.fy, -lim, lim)
	var fx := -signf(v_long) * minf(0.012 * N, absf(v_long) * m_eff / dt)       # rolling resistance
	if is_rear and in_pedal > 0.0:
		var cadence_fade := 1.0 - clampf((cadence_rpm - 115.0) / 35.0, 0.0, 1.0)
		fx += minf(max_drive_force, max_power / maxf(absf(v_long), 0.6)) * in_pedal * cadence_fade
	if in_brake > 0.0:
		var share := 0.55 if not is_rear else 0.45
		var fb := brake_force * share * 2.0 * in_brake
		if not is_rear:
			# a rider modulates the front brake just short of going over the bars:
			# endo when deceleration exceeds g * (COM ahead-distance / COM height)
			var to_com := com_g - w.point
			var h := maxf(to_com.dot(n), 0.3)
			var d := maxf(-to_com.dot(fwd_b), 0.05)
			var limit := mass * GRAV * d / h * 0.62 - absf(rear.brake_fx)
			fb = clampf(fb, 0.0, maxf(limit, 0.0))
		# ...and holds each brake short of a skid, leaving the grip the corner needs
		var corner_need := maxf(absf(fy), minf(m_eff * absf(angular_velocity.dot(n) * v_long), lim))
		fb = minf(fb, 0.85 * sqrt(maxf(lim * lim - corner_need * corner_need, 0.0)))
		var applied := minf(fb, absf(v_long) * m_eff / dt * 0.9)
		fx -= signf(v_long) * applied
		w.brake_fx = applied
	else:
		w.brake_fx = 0.0
	var tot := sqrt(fx * fx + fy * fy)
	if tot > lim:
		fx *= lim / tot
		fy *= lim / tot
		w.skid = true
	apply_force(n * N + side * fy, w.point - global_position)
	# brake / drive forces act in line with the bike's centre plane: a real
	# tyre's steering geometry cancels the yaw a leaned contact patch would add
	var lat_off := (w.point - com_g).dot(side)
	apply_force(fwd * fx, w.point - side * lat_off - global_position)

	var locked := in_brake > 0.9 and w.skid
	w.omega = 0.0 if locked else v_long / wheel_r
	w.spin += w.omega * dt


## In the air the rider keeps the bike level and stops it twisting; pitch is
## left mostly free (that's where flips will come from).
func _air_control(up_b: Vector3, fwd_b: Vector3, right_b: Vector3) -> void:
	var level_err := up_b.cross(Vector3.UP).dot(fwd_b)
	var w := angular_velocity
	apply_torque(fwd_b * (air_roll_stiffness * level_err - air_roll_damping * w.dot(fwd_b)))
	apply_torque(up_b * (-air_yaw_damping * w.dot(up_b)))
	# rider keeps the bike lined up with the flight path (soft, so flips can override)
	var pitch_err := 0.0
	var v := linear_velocity
	if v.length() > 2.0:
		pitch_err = fwd_b.cross(v.normalized()).dot(right_b)
	apply_torque(right_b * (air_pitch_stiffness * pitch_err - air_pitch_damping * w.dot(right_b)))


## On one wheel the rider stops a wheelie or a nose-wheelie from going over:
## past ~12 degrees off the ground's slope they push the bike back toward level.
func _one_wheel_balance(fwd_b: Vector3, right_b: Vector3) -> void:
	var w := rear if rear.contact else front
	var tilt := fwd_b.dot(w.normal)            # + nose up relative to the ground under the wheel
	var lim := sin(deg_to_rad(12.0))
	var excess := 0.0
	if rear.contact and tilt > lim:
		excess = tilt - lim
	elif front.contact and tilt < -lim:
		excess = tilt + lim
	if excess != 0.0:
		var pitch_rate := angular_velocity.dot(right_b)
		apply_torque(right_b * (-one_wheel_recovery * excess - 60.0 * pitch_rate))


func _lean_assist(up_b: Vector3, fwd_b: Vector3, strength := 1.0) -> void:
	## Holds the bike at the lean a real rider would use for the current turn.
	# lean for the turn being steered (bicycle geometry), not for whatever yaw a
	# bump just caused: tan(lean) = v^2 tan(steer) / (g * wheelbase)
	var v := linear_velocity
	var v_f := v.dot(fwd_b)
	var wb: float = geo["wheelbase"]
	var a_lat := v_f * v_f * tan(steer_angle) / wb
	var want := clampf(atan(a_lat / GRAV), -MAX_LEAN, MAX_LEAN)
	# a rider rolls the bike from one lean to the other over ~half a second;
	# flipping the target instantly would yank the tyres out from under it
	lean_target = move_toward(lean_target, want, LEAN_RATE * get_physics_process_delta_time())
	var hfwd := Vector3(fwd_b.x, 0.0, fwd_b.z).normalized()
	var target_up := Vector3.UP.rotated(hfwd, -lean_target)
	var err := up_b.cross(target_up).dot(fwd_b)
	var roll_rate := angular_velocity.dot(fwd_b)
	var tq := strength * (lean_stiffness * err - lean_damping * roll_rate)
	apply_torque(fwd_b * clampf(tq, -MAX_LEAN_TORQUE, MAX_LEAN_TORQUE))


func _hop(grounded: bool, up_b: Vector3, fwd_b: Vector3, com_g: Vector3, dt: float) -> void:
	## Hold to load the suspension (rider pushes down), release to pop.
	if in_hop and grounded:
		hop_charge = minf(hop_charge + dt * 2.2, 1.0)
		apply_central_force(Vector3.DOWN * mass * GRAV * 0.6 * hop_charge)
	elif hop_charge > 0.0:
		if grounded:
			var j := up_b * mass * (1.2 + 1.5 * hop_charge)
			apply_impulse(j, com_g - global_position - fwd_b * 0.05)
		hop_charge = 0.0


func _cranks(dt: float) -> void:
	var ratio := float(geo["cog_teeth"]) / float(geo["chainring_teeth"])
	if in_pedal > 0.05 and rear.contact and rear.omega > 0.0:
		var w := rear.omega * ratio
		crank_angle += w * dt
		cadence_rpm = w * 60.0 / TAU
	else:
		cadence_rpm = 0.0
		# coast with level pedals, right foot forward or back
		var target := roundf(crank_angle / PI) * PI
		crank_angle = move_toward(crank_angle, target, 5.0 * dt)


func _crash_check(up_b: Vector3, dt: float) -> void:
	if up_b.dot(Vector3.UP) < 0.25:
		upside_down_time += dt
		if upside_down_time > 1.5:
			reset_bike()
	else:
		upside_down_time = 0.0


func reset_bike(xform := Transform3D()) -> void:
	if xform == Transform3D():
		xform = spawn_xform
	spawn_xform = xform
	_reset_pending = true


func _integrate_forces(state: PhysicsDirectBodyState3D) -> void:
	# cap roll and yaw spin (pitch stays free for flips)
	var bas := state.transform.basis
	var wl := bas.inverse() * state.angular_velocity
	var lim := max_twist_rate
	# on the ground a rider can't flick the bike from lean to lean faster than ~1.8 rad/s
	var roll_lim := MAX_ROLL_RATE_GROUND if (rear.contact or front.contact) else lim
	if absf(wl.y) > lim or absf(wl.z) > roll_lim:
		wl.y = clampf(wl.y, -lim, lim)
		wl.z = clampf(wl.z, -roll_lim, roll_lim)
		state.angular_velocity = bas * wl
	if _reset_pending:
		state.transform = spawn_xform
		state.linear_velocity = Vector3.ZERO
		state.angular_velocity = Vector3.ZERO
		for w in [rear, front]:
			w.s = 0.0
			w.s_vel = 0.0
			w.omega = 0.0
		steer_angle = 0.0
		lean_target = 0.0
		upside_down_time = 0.0
		_reset_pending = false


func _read_input() -> void:
	if autopilot.is_valid():
		var c: Dictionary = autopilot.call(self, sim_time)
		in_pedal = c.get("pedal", 0.0)
		in_brake = c.get("brake", 0.0)
		in_steer = c.get("steer", 0.0)
		in_hop = c.get("hop", false)
		return
	in_pedal = Input.get_action_strength("pedal")
	in_brake = Input.get_action_strength("brake")
	in_steer = Input.get_action_strength("steer_left") - Input.get_action_strength("steer_right")
	in_hop = Input.is_action_pressed("hop")
	if Input.is_action_just_pressed("reset"):
		reset_bike()


# ------------------------------------------------------------------ readouts
func speed_kmh() -> float:
	return linear_velocity.length() * 3.6


func shock_stroke_mm() -> float:
	return linkage.stroke_at(rear.s) * 1000.0


func fork_travel_mm() -> float:
	return front.s * 1000.0
