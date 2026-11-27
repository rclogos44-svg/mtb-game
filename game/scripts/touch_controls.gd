extends CanvasLayer
## On-screen controls for phones and tablets. Every button is a
## TouchScreenButton bound to the same input action as the keyboard, so the
## bike and camera don't know the difference, and several fingers work at once
## (steer with the left thumb while pedalling and hopping with the right).
##
## Layout (landscape):
##   top right  : CAM  TRAIL  BASE  RESET
##   left thumb : steer left / right (slide between them)
##   right thumb: PEDAL (big), BRAKE, HOP

const MARGIN := 46.0

var buttons := {}          # name -> TouchScreenButton


func _ready() -> void:
	layer = 5
	_add("left", "steer_left", 118.0, "arrow_left", "", true)
	_add("right", "steer_right", 118.0, "arrow_right", "", true)
	_add("pedal", "pedal", 128.0, "circle", "PEDAL", true)
	_add("brake", "brake", 98.0, "circle", "BRAKE", true)
	_add("hop", "hop", 98.0, "circle", "HOP", true)
	for b in [["cam", "camera", "CAM"], ["trail", "goto_trail", "TRAIL"], ["base", "goto_base", "BASE"], ["reset", "reset", "RESET"]]:
		_add(b[0], b[1], 0.0, "pill", b[2], false)
	get_viewport().size_changed.connect(_layout)
	_layout()


func _layout() -> void:
	var sz := get_viewport().get_visible_rect().size
	var w := sz.x
	var h := sz.y
	_place("left", Vector2(MARGIN + 130.0, h - MARGIN - 135.0))
	_place("right", Vector2(MARGIN + 395.0, h - MARGIN - 135.0))
	_place("pedal", Vector2(w - MARGIN - 145.0, h - MARGIN - 150.0))
	_place("brake", Vector2(w - MARGIN - 400.0, h - MARGIN - 105.0))
	_place("hop", Vector2(w - MARGIN - 175.0, h - MARGIN - 420.0))
	var x := w - MARGIN - 85.0
	for n in ["reset", "base", "trail", "cam"]:
		_place(n, Vector2(x, MARGIN + 40.0))
		x -= 190.0


func _place(n: String, center: Vector2) -> void:
	var b: TouchScreenButton = buttons[n]
	b.position = center - b.texture_normal.get_size() * 0.5


func _add(n: String, action: String, radius: float, kind: String, text: String, passby: bool) -> void:
	var b := TouchScreenButton.new()
	var size := Vector2(radius * 2.0, radius * 2.0) if kind != "pill" else Vector2(170, 80)
	b.texture_normal = _texture(size, kind, false)
	b.texture_pressed = _texture(size, kind, true)
	b.action = action
	b.passby_press = passby                 # a thumb can slide from one button to the next
	var shape: Shape2D
	if kind == "pill":
		var r := RectangleShape2D.new()
		r.size = size
		shape = r
	else:
		var c := CircleShape2D.new()
		c.radius = radius * 1.08             # a little more generous than it looks
		shape = c
	b.shape = shape
	b.shape_centered = true
	if text != "":
		var l := Label.new()
		l.text = text
		l.add_theme_font_size_override("font_size", 30 if kind != "pill" else 26)
		l.add_theme_color_override("font_color", Color(1, 1, 1, 0.92))
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.size = size
		l.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(l)
	add_child(b)
	buttons[n] = b


## Translucent button art drawn at runtime: a soft disc (or pill) with a ring,
## and an arrow for the steering buttons. Brighter while pressed.
static func _texture(size: Vector2, kind: String, pressed: bool) -> ImageTexture:
	var w := int(size.x)
	var h := int(size.y)
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var fill := Color(1, 1, 1, 0.30 if pressed else 0.14)
	var ring := Color(1, 1, 1, 0.75 if pressed else 0.45)
	var dark := Color(0.08, 0.07, 0.06, 0.22)
	var c := Vector2(w, h) * 0.5
	for y in h:
		for x in w:
			var p := Vector2(x + 0.5, y + 0.5)
			var d := 0.0            # signed distance to the edge (negative inside)
			if kind == "pill":
				var rr := h * 0.5
				var q := Vector2(maxf(absf(p.x - c.x) - (w * 0.5 - rr), 0.0), absf(p.y - c.y))
				d = q.length() - rr
			else:
				d = p.distance_to(c) - w * 0.5
			if d > 0.0:
				continue
			var col := dark.blend(fill)
			if d > -4.0:
				col = ring
			# antialias the outer edge
			col.a *= clampf(-d, 0.0, 1.0)
			if kind.begins_with("arrow"):
				var s := -1.0 if kind == "arrow_left" else 1.0
				var lx := (p.x - c.x) * s / (w * 0.5)       # -1..1, + toward the arrow tip
				var ly := absf(p.y - c.y) / (h * 0.5)
				if lx < 0.42 and lx > -0.30 and ly < (0.42 - lx) * 0.75:
					col = Color(1, 1, 1, 0.95 if pressed else 0.8)
			img.set_pixel(x, y, col)
	return ImageTexture.create_from_image(img)
