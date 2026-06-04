#version 330 core
layout(location = 0) out vec3 g_position;
layout(location = 1) out vec3 g_normal;
layout(location = 2) out vec4 g_albedo_rough;
layout(location = 3) out vec4 g_emissive_metal;

in vec3 v_world_pos;
in vec3 v_normal;
in vec2 v_uv;

uniform vec3  u_albedo;
uniform float u_roughness;
uniform float u_metallic;
uniform vec3  u_emissive;
uniform bool  u_has_texture;
uniform sampler2D u_albedo_tex;

void main() {
    vec3 albedo = u_has_texture ? texture(u_albedo_tex, v_uv).rgb : u_albedo;

    g_position        = v_world_pos;
    g_normal          = normalize(v_normal);
    g_albedo_rough    = vec4(albedo, u_roughness);
    g_emissive_metal  = vec4(u_emissive, u_metallic);
}
