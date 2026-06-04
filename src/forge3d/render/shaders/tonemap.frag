#version 330 core
out vec4 frag_color;
in vec2 v_uv;
uniform sampler2D u_hdr;
uniform sampler2D u_bloom;
uniform float u_exposure;
uniform float u_bloom_strength;

// ACES Filmic tonemap (简略 Narkowicz 近似)
vec3 aces(vec3 x) {
    float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x*(a*x+b))/(x*(c*x+d)+e), 0.0, 1.0);
}

void main() {
    vec3 hdr   = texture(u_hdr,   v_uv).rgb;
    vec3 bloom = texture(u_bloom, v_uv).rgb;
    vec3 color = hdr + bloom * u_bloom_strength;
    color = aces(color * u_exposure);
    // sRGB 감마 보정 (2.2)
    color = pow(color, vec3(1.0 / 2.2));
    frag_color = vec4(color, 1.0);
}
