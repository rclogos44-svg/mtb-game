extends CanvasLayer
## Live readout of the suspension so you can see what it is doing.

@export var bike_path: NodePath
## Phones: just speed and the two travel bars, in bigger type, no key hints.
@export var compact := false
var bike: Bike
var label: Label
var bars := {}
var help: Label


func _ready() -> void:
	var panel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0.45)
	sb.set_corner_radius_all(8)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 10
	sb.content_margin_bottom = 10
	panel.add_theme_stylebox_override("panel", sb)
	panel.position = Vector2(16, 16)
	add_child(panel)
	var vb := VBoxContainer.new()
	panel.add_child(vb)
	label = Label.new()
	label.add_theme_font_size_override("font_size", 28 if compact else 15)
	vb.add_child(label)
	for k in ["Fork", "Shock"]:
		var row := HBoxContainer.new()
		var l := Label.new()
		l.text = k
		l.custom_minimum_size = Vector2(52, 0)
		if compact:
			l.add_theme_font_size_override("font_size", 24)
			l.custom_minimum_size = Vector2(90, 0)
		row.add_child(l)
		var pb := ProgressBar.new()
		pb.custom_minimum_size = Vector2(240, 22) if compact else Vector2(180, 14)
		pb.show_percentage = false
		pb.max_value = 100
		row.add_child(pb)
		vb.add_child(row)
		bars[k] = pb
	help = Label.new()
	help.text = "W pedal   S brake   A/D steer   Space hold+release hop\nR reset   2 trail   1 baseplate   C camera   T slow-mo   right-drag look   wheel zoom"
	help.add_theme_font_size_override("font_size", 13)
	help.modulate = Color(1, 1, 1, 0.8)
	help.anchor_top = 1.0
	help.anchor_bottom = 1.0
	help.position = Vector2(16, -60)
	add_child(help)
	help.visible = not compact
	if compact:
		panel.position = Vector2(40, 30)
	bike = get_node_or_null(bike_path)


func _process(_dt: float) -> void:
	if bike == null or bike.shock == null:
		bike = get_node_or_null(bike_path)
		return
	help.position.y = get_viewport().get_visible_rect().size.y - 56
	var rt := bike.rear.travel * 1000.0
	var ft := bike.front.travel * 1000.0
	if compact:
		label.text = "%2d km/h" % int(round(bike.speed_kmh())) + ("   SLOW-MO" if Engine.time_scale < 0.9 else "")
		bars["Fork"].value = bike.front.s / bike.front.travel * 100.0
		bars["Shock"].value = bike.rear.s / bike.rear.travel * 100.0
		return
	label.text = "%4.1f km/h   cadence %3d rpm\n" % [bike.speed_kmh(), int(bike.cadence_rpm)] \
		+ "Fork   %5.1f / %d mm   %d psi\n" % [bike.fork_travel_mm(), int(ft), int(bike.fork.psi())] \
		+ "Shock  %4.1f / %d mm stroke   %d lb/in coil\n" % [bike.shock_stroke_mm(), int(bike.geo["shock_stroke"] * 1000), bike.shock.lbs_per_in()] \
		+ "Rear wheel %5.1f / %d mm   (max used %d)\n" % [bike.rear.s * 1000.0, int(rt), int(bike.rear.max_s * 1000.0)] \
		+ "Leverage %.2f" % bike.linkage.leverage_at(bike.rear.s) \
		+ ("   SLOW-MO" if Engine.time_scale < 0.9 else "")
	bars["Fork"].value = bike.front.s / bike.front.travel * 100.0
	bars["Shock"].value = bike.rear.s / bike.rear.travel * 100.0
