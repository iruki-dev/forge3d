#version 330 core
out vec2 v_uv;
void main() {
    // 클립 공간 풀스크린 삼각형 두 개 (인덱스 없이)
    vec2 pos[4] = vec2[](vec2(-1,-1), vec2(1,-1), vec2(-1,1), vec2(1,1));
    vec2 uv[4]  = vec2[](vec2(0,0),   vec2(1,0),  vec2(0,1),  vec2(1,1));
    v_uv        = uv[gl_VertexID];
    gl_Position = vec4(pos[gl_VertexID], 0.0, 1.0);
}
