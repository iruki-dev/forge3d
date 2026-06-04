"""wgpu 렌더 파이프라인 설정 — 메시 VAO, 유니폼 버퍼, 바인드 그룹."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

_SHADER_DIR = Path(__file__).parent.parent / "shaders"


def load_wgsl(name: str) -> str:
    return (_SHADER_DIR / name).read_text()


def _mat4(m: np.ndarray) -> bytes:
    """(4,4) float64 → column-major float32 bytes."""
    return m.astype(np.float32).T.tobytes()


def _vec4(v: np.ndarray, pad: float = 0.0) -> bytes:
    arr = np.array([v[0], v[1], v[2], pad], dtype=np.float32)
    return arr.tobytes()


def create_pipeline(device: Any, width: int, height: int, wgpu_mod: Any) -> dict[str, Any]:
    """wgpu 렌더 파이프라인과 관련 리소스를 생성해 딕셔너리로 반환한다."""
    wgpu = wgpu_mod

    # ── 셰이더 ──
    shader_src = load_wgsl("pbr.wgsl")
    shader = device.create_shader_module(code=shader_src)

    # ── 렌더 타겟 텍스처 ──
    color_tex = device.create_texture(
        size=(width, height, 1),
        format=wgpu.TextureFormat.rgba8unorm,
        usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
    )
    depth_tex = device.create_texture(
        size=(width, height, 1),
        format=wgpu.TextureFormat.depth24plus,
        usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
    )

    # ── 유니폼 버퍼 ──
    # Camera: view_proj(64) + cam_pos(12) + pad(4) = 80 bytes
    cam_buf = device.create_buffer(size=80, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
    # Light: dir(12) + intensity(4) + color(12) + pad(4) = 32 bytes
    light_buf = device.create_buffer(size=32, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)

    # ── 바인드 그룹 레이아웃 ──
    bgl0 = device.create_bind_group_layout(entries=[
        {"binding": 0, "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
         "buffer": {"type": wgpu.BufferBindingType.uniform}},
        {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT,
         "buffer": {"type": wgpu.BufferBindingType.uniform}},
    ])
    bgl1 = device.create_bind_group_layout(entries=[
        {"binding": 0, "visibility": wgpu.ShaderStage.VERTEX,
         "buffer": {"type": wgpu.BufferBindingType.uniform}},
        {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT,
         "buffer": {"type": wgpu.BufferBindingType.uniform}},
    ])

    bg0 = device.create_bind_group(layout=bgl0, entries=[
        {"binding": 0, "resource": {"buffer": cam_buf, "offset": 0, "size": 80}},
        {"binding": 1, "resource": {"buffer": light_buf, "offset": 0, "size": 32}},
    ])

    pipeline_layout = device.create_pipeline_layout(bind_group_layouts=[bgl0, bgl1])

    # ── 렌더 파이프라인 ──
    pipeline = device.create_render_pipeline(
        layout=pipeline_layout,
        vertex={
            "module": shader,
            "entry_point": "vs_main",
            "buffers": [{
                "array_stride": 24,  # 6 floats: pos(3) + normal(3)
                "step_mode": wgpu.VertexStepMode.vertex,
                "attributes": [
                    {"format": wgpu.VertexFormat.float32x3, "offset": 0,  "shader_location": 0},
                    {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
                ],
            }],
        },
        primitive={
            "topology": wgpu.PrimitiveTopology.triangle_list,
            "front_face": wgpu.FrontFace.ccw,
            "cull_mode": wgpu.CullMode.back,
        },
        depth_stencil={
            "format": wgpu.TextureFormat.depth24plus,
            "depth_write_enabled": True,
            "depth_compare": wgpu.CompareFunction.less,
        },
        fragment={
            "module": shader,
            "entry_point": "fs_main",
            "targets": [{"format": wgpu.TextureFormat.rgba8unorm}],
        },
    )

    # ── 읽기 버퍼 ──
    row_bytes = width * 4
    # wgpu requires bytes_per_row to be multiple of 256
    aligned_row = ((row_bytes + 255) // 256) * 256
    readback_size = aligned_row * height
    readback_buf = device.create_buffer(
        size=readback_size,
        usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST,
    )

    return {
        "device": device,
        "pipeline": pipeline,
        "bgl1": bgl1,
        "bg0": bg0,
        "cam_buf": cam_buf,
        "light_buf": light_buf,
        "color_tex": color_tex,
        "depth_tex": depth_tex,
        "readback_buf": readback_buf,
        "width": width,
        "height": height,
        "aligned_row": aligned_row,
    }
