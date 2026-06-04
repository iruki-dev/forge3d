#version 330 core
out vec4 frag_color;
in vec2 v_uv;
uniform sampler2D u_src;
uniform float u_threshold;

void main() {
    vec3 color = texture(u_src, v_uv).rgb;
    // 밝기 기준으로 블룸 발생
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
    frag_color = vec4(brightness > u_threshold ? color : vec3(0.0), 1.0);
}
