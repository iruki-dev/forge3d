#version 330 core
out vec4 frag_color;
in vec2 v_uv;
uniform sampler2D u_src;
uniform float u_strength;

void main() {
    // 4-tap Kawase 업샘플
    vec2 d = 1.0 / textureSize(u_src, 0);
    vec3 c  = texture(u_src, v_uv + vec2(-d.x,  d.y)).rgb
            + texture(u_src, v_uv + vec2( d.x,  d.y)).rgb
            + texture(u_src, v_uv + vec2(-d.x, -d.y)).rgb
            + texture(u_src, v_uv + vec2( d.x, -d.y)).rgb;
    frag_color = vec4(c * 0.25 * u_strength, 1.0);
}
