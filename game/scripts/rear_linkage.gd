class_name RearLinkage
extends RefCounted
## Rear suspension kinematics, read from the table in geometry.json (solved in
## art/geometry.py). Everything is indexed by vertical wheel travel s (m).
##
## Side-view points are Vector2(u, v): u forward, v up, origin on the ground
## under the bottom bracket.

var travel: PackedFloat32Array = []
var stroke: PackedFloat32Array = []
var theta: PackedFloat32Array = []     # chainstay rotation about P (rad)
var phi: PackedFloat32Array = []       # rocker rotation about R (rad)
var axle: PackedVector2Array = []
var h_pts: PackedVector2Array = []
var b_pts: PackedVector2Array = []
var c_pts: PackedVector2Array = []
var max_travel := 0.0


func _init(geo: Dictionary) -> void:
	for row in geo["rear_table"]:
		travel.append(row["wheel_travel"])
		stroke.append(row["stroke"])
		theta.append(row["theta"])
		phi.append(row["phi"])
		axle.append(_v2(row["axle"]))
		h_pts.append(_v2(row["H"]))
		b_pts.append(_v2(row["B"]))
		c_pts.append(_v2(row["C"]))
	# trim at full shock stroke
	var full: float = geo["shock_stroke"]
	var n := stroke.size()
	var last := n - 1
	if stroke[last] > full:
		var t := (full - stroke[last - 1]) / (stroke[last] - stroke[last - 1])
		max_travel = lerpf(travel[last - 1], travel[last], t)
	else:
		max_travel = travel[last]


static func _v2(a) -> Vector2:
	return Vector2(a[0], a[1])


func _locate(s: float) -> Vector2:
	## Returns (index, fraction) for wheel travel s.
	s = clampf(s, 0.0, travel[travel.size() - 1])
	var lo := 0
	var hi := travel.size() - 1
	while hi - lo > 1:
		var mid := (lo + hi) >> 1
		if travel[mid] <= s:
			lo = mid
		else:
			hi = mid
	var span := travel[hi] - travel[lo]
	var f := 0.0 if span <= 0.0 else (s - travel[lo]) / span
	return Vector2(lo, f)


func stroke_at(s: float) -> float:
	var k := _locate(s)
	var i := int(k.x)
	return lerpf(stroke[i], stroke[i + 1], k.y)


## Leverage ratio: wheel travel per unit of shock stroke at travel s.
func leverage_at(s: float) -> float:
	var k := _locate(s)
	var i := int(k.x)
	var ds := travel[i + 1] - travel[i]
	var dx := stroke[i + 1] - stroke[i]
	return ds / maxf(dx, 1e-6)


## Full linkage state for drawing.
func pose_at(s: float) -> Dictionary:
	var k := _locate(s)
	var i := int(k.x)
	var f := k.y
	return {
		"theta": lerpf(theta[i], theta[i + 1], f),
		"phi": lerpf(phi[i], phi[i + 1], f),
		"axle": axle[i].lerp(axle[i + 1], f),
		"H": h_pts[i].lerp(h_pts[i + 1], f),
		"B": b_pts[i].lerp(b_pts[i + 1], f),
		"C": c_pts[i].lerp(c_pts[i + 1], f),
	}
