shader_type spatial;
// Packed-dirt baseplate with a faint 1 m grid so speed and travel are easy to judge.

uniform vec3 dirt_a : source_color = vec3(0.50, 0.39, 0.27);
uniform vec3 dirt_b : source_color = vec3(0.42, 0.32, 0.22);
uniform vec3 line_col : source_color = vec3(0.34, 0.26, 0.18);

varying vec3 wpos;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = wpos.xz;
	float n = noise(p * 0.35) * 0.5 + noise(p * 1.7) * 0.3 + noise(p * 9.0) * 0.2;
	vec3 col = mix(dirt_b, dirt_a, n);
	vec2 g = abs(fract(p) - 0.5);
	float line = 1.0 - smoothstep(0.0, 0.025, min(g.x, g.y) - 0.47);
	vec2 g5 = abs(fract(p / 5.0) - 0.5);
	float line5 = 1.0 - smoothstep(0.0, 0.01, min(g5.x, g5.y) - 0.494);
	col = mix(col, line_col, max(line * 0.35, line5 * 0.7));
	ALBEDO = col;
	ROUGHNESS = 0.95;
}
