"""GLSL shader source strings for the realtime renderer.

All shaders target GLSL 330 core (OpenGL 3.3).
Coordinate system: z-up, right-handed.

Vertex layout: [px, py, pz,  nx, ny, nz,  u, v]  — 8 floats per vertex.
"""

from __future__ import annotations

# ── Shadow depth pass ─────────────────────────────────────────────────────────

SHADOW_VERT = """
#version 330 core
uniform mat4 u_light_MVP;
in vec3 in_position;
void main() {
    gl_Position = u_light_MVP * vec4(in_position, 1.0);
}
"""

SHADOW_FRAG = """
#version 330 core
void main() { }   // depth written automatically
"""

# ── Main PBR pass (Cook-Torrance BRDF + PCF shadows + optional texture) ──────

MAIN_VERT = """
#version 330 core
uniform mat4 u_MVP;            // proj * view * model
uniform mat4 u_M;              // model (world transform)
uniform mat3 u_NM;             // normal matrix = transpose(inverse(M[:3,:3]))
uniform mat4 u_light_MVP;      // light proj * light_view * model

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;
out vec4 v_shadow_coord;

void main() {
    vec4 world     = u_M * vec4(in_position, 1.0);
    v_world_pos    = world.xyz;
    v_normal       = normalize(u_NM * in_normal);
    v_uv           = in_uv;
    v_shadow_coord = u_light_MVP * vec4(in_position, 1.0);
    gl_Position    = u_MVP * vec4(in_position, 1.0);
}
"""

MAIN_FRAG = """
#version 330 core
const float PI = 3.14159265359;

// Lighting
uniform vec3 u_light_dir;        // unit vector FROM scene TOWARD light (= -L_world)
uniform vec3 u_light_color;      // light RGB * intensity
uniform vec3 u_ambient_color;    // ambient RGB

// Material
uniform vec3  u_mat_color;       // base albedo (linear RGB [0,1])
uniform float u_metallic;        // 0 = dielectric, 1 = metal
uniform float u_roughness;       // 0 = mirror, 1 = fully diffuse

// Camera
uniform vec3  u_eye;

// Textures
uniform sampler2D u_shadow_map;
uniform sampler2D u_albedo_map;
uniform int       u_has_texture; // 1 = sample albedo_map, 0 = use u_mat_color

in vec3 v_world_pos;
in vec3 v_normal;
in vec2 v_uv;
in vec4 v_shadow_coord;

out vec4 frag_color;

// ── PCF shadow factor ─────────────────────────────────────────────────────────
float shadow_factor() {
    vec3 proj = v_shadow_coord.xyz / v_shadow_coord.w;
    proj = proj * 0.5 + 0.5;
    if (proj.x < 0.0 || proj.x > 1.0 || proj.y < 0.0 || proj.y > 1.0 || proj.z > 1.0)
        return 1.0;
    float shadow = 0.0;
    float texel  = 1.0 / 2048.0;
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            float closest = texture(u_shadow_map,
                                    proj.xy + vec2(float(dx), float(dy)) * texel).r;
            shadow += (proj.z - 0.003 > closest) ? 0.0 : 1.0;
        }
    }
    return shadow / 9.0;
}

// ── GGX normal distribution ───────────────────────────────────────────────────
float D_GGX(float NdotH, float rough) {
    float a  = rough * rough;
    float a2 = a * a;
    float d  = NdotH * NdotH * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d);
}

// ── Schlick-GGX geometry term (Smith formulation) ─────────────────────────────
float G_SchlickGGX(float NdotX, float rough) {
    float r = rough + 1.0;
    float k = (r * r) / 8.0;
    return NdotX / (NdotX * (1.0 - k) + k);
}

float G_Smith(float NdotV, float NdotL, float rough) {
    return G_SchlickGGX(NdotV, rough) * G_SchlickGGX(NdotL, rough);
}

// ── Fresnel-Schlick ───────────────────────────────────────────────────────────
vec3 F_Schlick(float HdotV, vec3 F0) {
    float x = clamp(1.0 - HdotV, 0.0, 1.0);
    float x2 = x * x;
    return F0 + (1.0 - F0) * (x2 * x2 * x);
}

void main() {
    // Base colour
    vec3 albedo = (u_has_texture != 0)
        ? pow(texture(u_albedo_map, v_uv).rgb, vec3(2.2))  // sRGB → linear
        : u_mat_color;

    float metallic  = u_metallic;
    float roughness = max(u_roughness, 0.04);  // prevent division by zero

    vec3 N = normalize(v_normal);
    vec3 V = normalize(u_eye - v_world_pos);
    vec3 L = normalize(u_light_dir);
    vec3 H = normalize(V + L);

    float NdotL = max(dot(N, L), 0.0);
    float NdotV = max(dot(N, V), 0.0001);
    float NdotH = max(dot(N, H), 0.0);
    float HdotV = max(dot(H, V), 0.0);

    // Fresnel base reflectance
    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // Cook-Torrance specular BRDF
    float D = D_GGX(NdotH, roughness);
    float G = G_Smith(NdotV, NdotL, roughness);
    vec3  F = F_Schlick(HdotV, F0);

    vec3 kS = F;
    vec3 kD = (1.0 - kS) * (1.0 - metallic);
    vec3 specular = D * G * F / max(4.0 * NdotV * NdotL, 0.001);

    float sf  = shadow_factor();
    vec3  Lo  = (kD * albedo / PI + specular) * u_light_color * NdotL * sf;

    // Ambient: simple Lambertian (no IBL in this pass)
    vec3 ambient = u_ambient_color * albedo * (0.2 + 0.8 * (1.0 - metallic));

    vec3 color = ambient + Lo;

    // Reinhard HDR tone mapping + gamma correction
    color = color / (color + vec3(1.0));
    color = pow(clamp(color, 0.0, 1.0), vec3(1.0 / 2.2));

    frag_color = vec4(color, 1.0);
}
"""

# ── Grid / axes (flat colour, no lighting) ────────────────────────────────────

FLAT_VERT = """
#version 330 core
uniform mat4 u_VP;   // proj * view (no model — already in world space)
in vec3 in_position;
void main() {
    gl_Position = u_VP * vec4(in_position, 1.0);
}
"""

FLAT_FRAG = """
#version 330 core
uniform vec4 u_color;
out vec4 frag_color;
void main() {
    frag_color = u_color;
}
"""
