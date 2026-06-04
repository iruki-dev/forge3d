#version 330 core
out vec4 frag_color;
in vec2 v_uv;

uniform sampler2D g_position;
uniform sampler2D g_normal;
uniform sampler2D g_albedo_rough;
uniform sampler2D g_emissive_metal;
uniform sampler2D u_ssao;
uniform sampler2D u_shadow0;
uniform sampler2D u_shadow1;
uniform sampler2D u_shadow2;
uniform sampler2D u_shadow3;

uniform vec3  u_cam_pos;
uniform vec3  u_light_dir;       // normalized, world-space, FROM scene TOWARD light
uniform vec3  u_light_color;
uniform float u_light_intensity;

// CSM
uniform mat4 u_light_vp[4];
uniform float u_cascade_splits[4];  // view-space Z splits
uniform mat4 u_view;
uniform bool u_has_shadow;

const float PI = 3.14159265359;

// ── Fresnel (Schlick) ──
vec3 fresnel(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

// ── NDF (GGX Trowbridge-Reitz) ──
float ndf_ggx(float NdotH, float roughness) {
    float a  = roughness * roughness;
    float a2 = a * a;
    float d  = NdotH * NdotH * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d + 1e-7);
}

// ── Geometry (Smith-GGX) ──
float geo_schlick(float NdotV, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;
    return NdotV / (NdotV * (1.0 - k) + k + 1e-7);
}
float geo_smith(float NdotV, float NdotL, float roughness) {
    return geo_schlick(NdotV, roughness) * geo_schlick(NdotL, roughness);
}

// ── PCF shadow ──
float shadow_pcf(sampler2D shadow_map, vec4 light_space_pos) {
    vec3 proj = light_space_pos.xyz / light_space_pos.w;
    proj = proj * 0.5 + 0.5;
    if (proj.z > 1.0 || proj.x < 0.0 || proj.x > 1.0 || proj.y < 0.0 || proj.y > 1.0)
        return 1.0;  // outside shadow map → lit
    float bias    = 0.003;
    float shadow  = 0.0;
    vec2  texel   = 1.0 / textureSize(shadow_map, 0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float d = texture(shadow_map, proj.xy + vec2(x, y) * texel).r;
            shadow += (proj.z - bias > d) ? 0.0 : 1.0;
        }
    }
    return shadow / 9.0;
}

void main() {
    vec3  pos       = texture(g_position,      v_uv).rgb;
    vec3  N         = normalize(texture(g_normal, v_uv).rgb);
    vec4  ar        = texture(g_albedo_rough,   v_uv);
    vec4  em        = texture(g_emissive_metal,  v_uv);
    vec3  albedo    = ar.rgb;
    float roughness = ar.a;
    float metallic  = em.a;
    vec3  emissive  = em.rgb;
    float ao        = texture(u_ssao, v_uv).r;

    // 배경 (position==0 일 때)
    if (dot(N, N) < 0.1) {
        frag_color = vec4(0.12, 0.14, 0.18, 1.0);
        return;
    }

    vec3 V     = normalize(u_cam_pos - pos);
    vec3 L     = normalize(u_light_dir);
    vec3 H     = normalize(V + L);
    float NdotL = max(dot(N, L), 0.0);
    float NdotV = max(dot(N, V), 0.0);
    float NdotH = max(dot(N, H), 0.0);
    float HdotV = max(dot(H, V), 0.0);

    // PBR 베이스 반사율
    vec3 F0  = mix(vec3(0.04), albedo, metallic);
    vec3 F   = fresnel(HdotV, F0);
    float NDF = ndf_ggx(NdotH, roughness);
    float G   = geo_smith(NdotV, NdotL, roughness);

    // Cook-Torrance 스펙큘러
    vec3 spec  = (NDF * G * F) / (4.0 * NdotV * NdotL + 1e-7);

    // diffuse (에너지 보존)
    vec3 kD = (1.0 - F) * (1.0 - metallic);
    vec3 diffuse = kD * albedo / PI;

    // CSM 그림자 선택
    float shadow = 1.0;
    if (u_has_shadow) {
        // view-space Z
        float viewZ = abs((u_view * vec4(pos, 1.0)).z);
        vec4 lpos;
        if      (viewZ < u_cascade_splits[0]) { lpos = u_light_vp[0] * vec4(pos, 1.0); shadow = shadow_pcf(u_shadow0, lpos); }
        else if (viewZ < u_cascade_splits[1]) { lpos = u_light_vp[1] * vec4(pos, 1.0); shadow = shadow_pcf(u_shadow1, lpos); }
        else if (viewZ < u_cascade_splits[2]) { lpos = u_light_vp[2] * vec4(pos, 1.0); shadow = shadow_pcf(u_shadow2, lpos); }
        else                                  { lpos = u_light_vp[3] * vec4(pos, 1.0); shadow = shadow_pcf(u_shadow3, lpos); }
    }

    vec3 Lo = (diffuse + spec) * u_light_color * u_light_intensity * NdotL * shadow;

    // 주변광 (image-based 근사: constant ambient)
    vec3 ambient = 0.03 * albedo * ao;

    vec3 color = ambient + Lo + emissive;
    frag_color = vec4(color, 1.0);
}
