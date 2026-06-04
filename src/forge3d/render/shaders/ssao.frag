#version 330 core
out float frag_ao;
in vec2 v_uv;

uniform sampler2D g_position;
uniform sampler2D g_normal;
uniform sampler2D u_noise;
uniform vec3  u_samples[64];
uniform mat4  u_proj;
uniform vec2  u_noise_scale;  // screen_size / noise_size
uniform float u_radius;
uniform float u_bias;

void main() {
    vec3 pos    = texture(g_position, v_uv).rgb;
    vec3 normal = normalize(texture(g_normal, v_uv).rgb);

    if (dot(normal, normal) < 0.1) { frag_ao = 1.0; return; }

    vec3 rand_vec = normalize(texture(u_noise, v_uv * u_noise_scale).rgb * 2.0 - 1.0);

    // Gram-Schmidt TBN
    vec3 tangent   = normalize(rand_vec - normal * dot(rand_vec, normal));
    vec3 bitangent = cross(normal, tangent);
    mat3 TBN       = mat3(tangent, bitangent, normal);

    float occlusion = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 sample_pos = TBN * u_samples[i];
        sample_pos = pos + sample_pos * u_radius;

        // 클립 공간으로 변환
        vec4 offset = u_proj * vec4(sample_pos, 1.0);
        offset.xyz /= offset.w;
        offset.xyz  = offset.xyz * 0.5 + 0.5;

        float sample_depth = texture(g_position, offset.xy).z;
        float range_check  = smoothstep(0.0, 1.0, u_radius / abs(pos.z - sample_depth + 1e-7));
        occlusion += (sample_depth >= sample_pos.z + u_bias ? 1.0 : 0.0) * range_check;
    }
    frag_ao = 1.0 - (occlusion / 64.0);
}
