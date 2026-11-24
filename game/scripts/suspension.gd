class_name Suspension
extends RefCounted
## Spring and damper models used by both ends of the bike.


## Air spring with a positive and a negative chamber, like a modern air shock
## or fork. The negative chamber cancels the positive one at top-out, so the
## start of the stroke is supple; the positive chamber ramps up hard near the
## end, so it resists bottoming. Force is along the shaft.
class AirSpring:
	var stroke: float           ## m
	var l_pos: float            ## equivalent length of the positive chamber (m)
	var l_neg: float            ## equivalent length of the negative chamber (m)
	var piston_area: float      ## m^2, only used to report a pressure
	var gamma := 1.3            ## polytropic exponent (between isothermal and adiabatic)
	var p0a := 1000.0           ## pressure * area (N); set from the rider's weight

	func _init(p_stroke: float, p_l_pos: float, p_l_neg: float, p_area: float) -> void:
		stroke = p_stroke
		l_pos = p_l_pos
		l_neg = p_l_neg
		piston_area = p_area

	## Dimensionless force curve; force = p0a * shape(x)
	func shape(x: float) -> float:
		x = clampf(x, 0.0, stroke)
		return pow(l_pos / (l_pos - x), gamma) - pow(l_neg / (l_neg + x), gamma)

	func force(x: float) -> float:
		var f := p0a * shape(x)
		# bottom-out bumper over the last 4 mm
		var bump := x - (stroke - 0.004)
		if bump > 0.0:
			f += 2.5e7 * bump * bump
		return f

	## Spring rate (N/m) at x, by finite difference.
	func rate(x: float) -> float:
		var h := 0.0005
		return (force(x + h) - force(x - h)) / (2.0 * h)

	## Air pressure the rider would set, in psi.
	func psi() -> float:
		return p0a / piston_area / 6894.76


## Coil spring (steel), as on the reference bike's shock. Linear rate set from
## the rider's sag, plus the shock's progressive bottom-out bumper over the
## last part of the stroke.
class CoilSpring:
	var stroke: float
	var rate := 80000.0         ## N/m
	var preload_force := 0.0    ## N
	var bumper := 0.012         ## m of stroke where the bumper works

	func _init(p_stroke: float) -> void:
		stroke = p_stroke

	func force(x: float) -> float:
		x = clampf(x, 0.0, stroke)
		var f := preload_force + rate * x
		var b := x - (stroke - bumper)
		if b > 0.0:
			f += rate * 8.0 * b * b / bumper + rate * 0.5 * b
		return f

	func rate_at(x: float) -> float:
		var h := 0.0005
		return (force(x + h) - force(x - h)) / (2.0 * h)

	## Spring rate as printed on a real spring (lbs/in).
	func lbs_per_in() -> int:
		return int(round(rate / 175.127))


## Two-stage damper: separate low- and high-speed slopes for compression and
## rebound, with a knee between them (the high-speed circuit blows off so big
## hits don't spike). Velocity is shaft speed, positive = compressing.
class Damper:
	var lsc := 1000.0
	var hsc := 400.0
	var lsr := 2000.0
	var hsr := 1200.0
	var knee := 0.15

	func force(v: float) -> float:
		if v >= 0.0:
			return _curve(v, lsc, hsc)
		return -_curve(-v, lsr, hsr)

	func _curve(v: float, c_low: float, c_high: float) -> float:
		if v < knee:
			return c_low * v
		return c_low * knee + c_high * (v - knee)

	## Rebound speed the damper allows when pushed by force f (inverse of the
	## rebound curve). Used for how fast an unloaded wheel can extend.
	func rebound_speed(f: float) -> float:
		if f <= 0.0:
			return 0.0
		var f_knee := lsr * knee
		if f < f_knee:
			return f / lsr
		return knee + (f - f_knee) / hsr
