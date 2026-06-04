// forge3d PBR 셰이더 (WGSL) — forward shading
// Blinn-Phong 근사 PBR (GGX 없이 단순화)

struct CameraUniforms {
    view_proj: mat4x4<f32>,
    cam_pos:   vec3<f32>,
    _pad:      f32,
};

struct LightUniforms {
    direction:  vec3<f32>,
    intensity:  f32,
    color:      vec3<f32>,
    _pad:       f32,
};

struct ModelUniforms {
    model:     mat4x4<f32>,
    normal_mat: mat4x4<f32>,
};

struct MaterialUniforms {
    albedo:    vec3<f32>,
    roughness: f32,
    metallic:  f32,
    _pad0:     f32,
    _pad1:     f32,
    _pad2:     f32,
};

@group(0) @binding(0) var<uniform> camera: CameraUniforms;
@group(0) @binding(1) var<uniform> light:  LightUniforms;
@group(1) @binding(0) var<uniform> model_ub: ModelUniforms;
@group(1) @binding(1) var<uniform> material: MaterialUniforms;

struct VertexIn {
    @location(0) position: vec3<f32>,
    @location(1) normal:   vec3<f32>,
};

struct VertexOut {
    @builtin(position) clip_pos:   vec4<f32>,
    @location(0)       world_pos:  vec3<f32>,
    @location(1)       world_norm: vec3<f32>,
};

@vertex
fn vs_main(vin: VertexIn) -> VertexOut {
    var out: VertexOut;
    let world_pos4 = model_ub.model * vec4<f32>(vin.position, 1.0);
    out.world_pos  = world_pos4.xyz;
    out.clip_pos   = camera.view_proj * world_pos4;
    let world_norm4 = model_ub.normal_mat * vec4<f32>(vin.normal, 0.0);
    out.world_norm = normalize(world_norm4.xyz);
    return out;
}

@fragment
fn fs_main(vin: VertexOut) -> @location(0) vec4<f32> {
    let N  = normalize(vin.world_norm);
    let L  = normalize(-light.direction);
    let V  = normalize(camera.cam_pos - vin.world_pos);
    let H  = normalize(L + V);

    let NdotL = max(dot(N, L), 0.0);
    let NdotH = max(dot(N, H), 0.0);

    // diffuse
    let kD = material.albedo / 3.14159;

    // specular (Blinn-Phong 근사)
    let shininess = (1.0 - material.roughness) * 128.0 + 1.0;
    let spec = pow(NdotH, shininess) * (1.0 - material.roughness);

    // 금속성 보정
    let diffuse_color = mix(material.albedo, vec3<f32>(0.0), material.metallic);
    let spec_color    = mix(vec3<f32>(0.04), material.albedo, material.metallic);

    let Lo = (diffuse_color / 3.14159 + spec * spec_color)
             * light.color * light.intensity * NdotL;

    // ambient
    let ambient = 0.03 * material.albedo;

    let color = ambient + Lo;
    // 간단한 sRGB 감마
    return vec4<f32>(pow(color, vec3<f32>(1.0 / 2.2)), 1.0);
}
