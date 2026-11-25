shader_type spatial;
// Trail hill: packed, slightly darker dirt on the ridden line (COLOR.r = 1),
// looser, lighter earth with scattered dry grass on the shoulders.

uniform vec3 track_a : source_color = vec3(0.47, 0.34, 0.22);
uniform vec3 track_b : source_color = vec3(0.39, 0.28, 0.18);
uniform vec3 dirt_a : source_color = vec3(0.50, 0.39, 0.27);   // same as the baseplate
uniform vec3 dirt_b : source_color = vec3(0.42, 0.32, 0.22);
uniform vec3 grass : source_color = vec3(0.33, 0.35, 0.19);

varying vec3 wpos;
varying float track;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	track = COLOR.r;
}

void fragment() {
	vec2 p = wpos.xz;
	float n = noise(p * 0.5) * 0.5 + noise(p * 2.3) * 0.3 + noise(p * 11.0) * 0.2;
	vec3 t = mix(track_b, track_a, n);
	// tyre-worn streaks along the line
	t *= 0.92 + 0.08 * noise(vec2(wpos.x * 6.0, wpos.z * 0.4));
	// shoulders: baseplate dirt at the foot, patchy dry grass higher up
	float g = smoothstep(0.5, 0.72, noise(p * 0.9) * 0.6 + noise(p * 4.0) * 0.4);
	g *= smoothstep(0.15, 0.8, wpos.y);
	vec3 s = mix(mix(dirt_b, dirt_a, n), grass, g * 0.75);
	ALBEDO = mix(s, t, track);
	ROUGHNESS = 0.95;
}
