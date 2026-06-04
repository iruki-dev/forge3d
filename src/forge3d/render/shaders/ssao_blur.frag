#version 330 core
out float frag_ao;
in vec2 v_uv;
uniform sampler2D u_ssao_raw;

void main() {
    vec2 texel_size = 1.0 / textureSize(u_ssao_raw, 0);
    float result = 0.0;
    for (int x = -2; x <= 2; x++) {
        for (int y = -2; y <= 2; y++) {
            result += texture(u_ssao_raw, v_uv + vec2(x, y) * texel_size).r;
        }
    }
    frag_ao = result / 25.0;
}
