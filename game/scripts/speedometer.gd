extends Control
## Analogue speedometer: a 240-degree dial from 0 to 80 km/h with a needle,
## minor ticks every 5, numbers every 20, a red zone past 60, and a big
## digital readout and the gear underneath.

var speed := 0.0          # km/h, smoothed
var gear_text := ""
const MAX_KMH := 80.0
const A0 := deg_to_rad(150.0)    # 0 km/h (lower left)
const A1 := deg_to_rad(390.0)    # 80 km/h (lower right)


func set_speed(kmh: float, gear: String, dt: float) -> void:
	speed = lerpf(speed, kmh, 1.0 - exp(-10.0 * dt))
	gear_text = gear
	queue_redraw()


func _angle(kmh: float) -> float:
	return lerpf(A0, A1, clampf(kmh / MAX_KMH, 0.0, 1.0))


func _draw() -> void:
	var r := minf(size.x, size.y) * 0.5
	var c := size * 0.5
	var font := ThemeDB.fallback_font
	draw_circle(c, r, Color(0.05, 0.05, 0.06, 0.62))
	draw_arc(c, r - 3.0, 0.0, TAU, 64, Color(1, 1, 1, 0.25), 2.0, true)
	# red zone, then the speed swept so far
	draw_arc(c, r * 0.86, _angle(60.0), A1, 32, Color(0.95, 0.3, 0.25, 0.75), r * 0.07, true)
	draw_arc(c, r * 0.86, A0, _angle(speed), 48, Color(1.0, 0.62, 0.25, 0.85), r * 0.07, true)
	for k in range(0, 81, 5):
		var a := _angle(k)
		var dir := Vector2(cos(a), sin(a))
		var major := k % 20 == 0
		draw_line(c + dir * r * (0.70 if major else 0.76), c + dir * r * 0.80, Color(1, 1, 1, 0.9 if major else 0.55), 3.0 if major else 1.5, true)
		if major:
			var txt := str(k)
			var fs := int(r * 0.16)
			var tw := font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
			draw_string(font, c + dir * r * 0.55 - Vector2(tw.x * 0.5, -fs * 0.35), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(1, 1, 1, 0.85))
	# needle
	var an := _angle(speed)
	var nd := Vector2(cos(an), sin(an))
	draw_line(c - nd * r * 0.12, c + nd * r * 0.78, Color(1.0, 0.45, 0.3), maxf(3.0, r * 0.035), true)
	draw_circle(c, r * 0.07, Color(0.92, 0.92, 0.92))
	# digital readout and gear
	var big := str(int(round(speed)))
	var bfs := int(r * 0.36)
	var bw := font.get_string_size(big, HORIZONTAL_ALIGNMENT_LEFT, -1, bfs)
	draw_string(font, c + Vector2(-bw.x * 0.5, r * 0.52), big, HORIZONTAL_ALIGNMENT_LEFT, -1, bfs, Color(1, 1, 1))
	var unit := "km/h  " + gear_text
	var ufs := int(r * 0.13)
	var uw := font.get_string_size(unit, HORIZONTAL_ALIGNMENT_LEFT, -1, ufs)
	draw_string(font, c + Vector2(-uw.x * 0.5, r * 0.74), unit, HORIZONTAL_ALIGNMENT_LEFT, -1, ufs, Color(1, 1, 1, 0.7))
