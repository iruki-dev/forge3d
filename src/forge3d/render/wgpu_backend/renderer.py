"""WgpuRenderer — wgpu-py (WebGPU/Vulkan) 기반 렌더러.

SceneSnapshot 계약을 유지한다: 물리 코어는 이 파일을 import하지 않는다.
"""

from __future__ import annotations

import asyncio

import numpy as np

from forge3d.render.base import Frame, Renderer
from forge3d.render.snapshot import BUILTIN_MATERIALS, CameraSnapshot, SceneSnapshot


def _has_wgpu() -> bool:
    try:
        import wgpu  # noqa: F401

        return True
    except ImportError:
        return False


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    M = np.zeros((4, 4), dtype=np.float32)
    M[0, 0] = f / aspect
    M[1, 1] = f
    M[2, 2] = -(far + near) / (far - near)
    M[2, 3] = -2.0 * far * near / (far - near)
    M[3, 2] = -1.0
    return M


def _lookat(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    f = target - eye
    f /= np.linalg.norm(f) + 1e-12
    s = np.cross(f, up)
    s /= np.linalg.norm(s) + 1e-12
    u = np.cross(s, f)
    M = np.eye(4, dtype=np.float32)
    M[0, :3] = s
    M[1, :3] = u
    M[2, :3] = -f
    M[0, 3] = -float(s.dot(eye))
    M[1, 3] = -float(u.dot(eye))
    M[2, 3] = float(f.dot(eye))
    return M


def _unit_box_wgpu() -> np.ndarray:
    """단위 박스 정점 — (N, 6) float32: pos(3) + normal(3)."""
    from forge3d.render.realtime.meshes import unit_box

    verts, idxs = unit_box()
    # verts 레이아웃: pos(3) + normal(3) + uv(2) = 8 floats
    # 처음 6개만 추출
    pos_norm = verts.reshape(-1, 8)[:, :6]
    indexed = pos_norm[idxs.flatten()]
    return indexed.astype(np.float32)


def _unit_sphere_wgpu() -> np.ndarray:
    from forge3d.render.realtime.meshes import unit_sphere

    verts, idxs = unit_sphere()
    pos_norm = verts.reshape(-1, 8)[:, :6]
    return pos_norm[idxs.flatten()].astype(np.float32)


_MESH_CACHE: dict[str, np.ndarray] = {}


def _get_mesh(shape_type: str) -> np.ndarray:
    if shape_type not in _MESH_CACHE:
        if shape_type == "sphere":
            _MESH_CACHE[shape_type] = _unit_sphere_wgpu()
        else:
            _MESH_CACHE[shape_type] = _unit_box_wgpu()
    return _MESH_CACHE[shape_type]


class WgpuRenderer(Renderer):
    """wgpu-py 기반 오프스크린 렌더러.

    wgpu를 사용할 수 없는 환경에서는 DeferredRenderer(GL)로 폴백한다.
    """

    def __init__(
        self,
        width: int = 320,
        height: int = 240,
        headless: bool = True,
    ) -> None:
        self.width = width
        self.height = height
        self._camera: CameraSnapshot | None = None
        self._wgpu_available = _has_wgpu()
        self._fallback: Renderer | None = None

        if self._wgpu_available:
            self._init_wgpu()
        else:
            self._init_fallback()

    def _init_wgpu(self) -> None:
        import wgpu as _wgpu

        self._wgpu = _wgpu
        adapter = _wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        self._device = adapter.request_device_sync()
        from forge3d.render.wgpu_backend.pipeline import create_pipeline

        self._res = create_pipeline(self._device, self.width, self.height, _wgpu)

    def _init_fallback(self) -> None:
        from forge3d.render.deferred.renderer import DeferredRenderer

        self._fallback = DeferredRenderer(width=self.width, height=self.height)

    # ── 렌더 ─────────────────────────────────────────────────────────────────

    def render(self, snapshot: SceneSnapshot) -> Frame:
        if not self._wgpu_available:
            assert self._fallback is not None
            if self._camera:
                self._fallback.set_camera(self._camera)
            return self._fallback.render(snapshot)

        return self._render_wgpu(snapshot)

    def _render_wgpu(self, snapshot: SceneSnapshot) -> np.ndarray:
        wgpu = self._wgpu
        device = self._device
        res = self._res
        W, H = self.width, self.height

        cam = snapshot.camera or CameraSnapshot(
            position=np.array([5.0, -8.0, 5.0]),
            target=np.zeros(3),
            up=np.array([0.0, 0.0, 1.0]),
        )
        if self._camera:
            cam = self._camera

        eye = np.asarray(cam.position, dtype=np.float32)
        view = _lookat(eye, np.asarray(cam.target), np.asarray(cam.up))
        proj = _perspective(cam.fov_deg, W / H, cam.near, cam.far)
        view_proj = (proj @ view).astype(np.float32)

        # Camera 유니폼: view_proj(64) + cam_pos(12) + pad(4) = 80
        cam_data = bytearray(80)
        cam_data[0:64] = view_proj.T.astype(np.float32).tobytes()
        cam_data[64:76] = eye.astype(np.float32).tobytes()
        device.queue.write_buffer(res["cam_buf"], 0, bytes(cam_data))

        # Light 유니폼
        if snapshot.lights:
            ld = np.asarray(snapshot.lights[0].direction, dtype=np.float32)
            lc = np.asarray(snapshot.lights[0].color, dtype=np.float32)
            lint = float(snapshot.lights[0].intensity)
        else:
            ld = np.array([0.0, 0.0, -1.0], dtype=np.float32)
            lc = np.ones(3, dtype=np.float32)
            lint = 1.0
        light_data = bytearray(32)
        light_data[0:12] = ld.tobytes()
        light_data[12:16] = np.float32(lint).tobytes()
        light_data[16:28] = lc.tobytes()
        device.queue.write_buffer(res["light_buf"], 0, bytes(light_data))

        # 렌더 패스
        encoder = device.create_command_encoder()
        rp = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": res["color_tex"].create_view(),
                    "resolve_target": None,
                    "clear_value": (0.12, 0.14, 0.18, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
            depth_stencil_attachment={
                "view": res["depth_tex"].create_view(),
                "depth_clear_value": 1.0,
                "depth_load_op": wgpu.LoadOp.clear,
                "depth_store_op": wgpu.StoreOp.store,
            },
        )
        rp.set_pipeline(res["pipeline"])
        rp.set_bind_group(0, res["bg0"])

        for body in snapshot.bodies:
            mesh_verts = _get_mesh(body.shape_type)
            if len(mesh_verts) == 0:
                continue

            # 모델 행렬 (128 bytes: model + normal_mat)
            pos = np.asarray(body.transform.position, dtype=np.float32)
            rot = np.asarray(body.transform.rotation, dtype=np.float32)
            st = body.shape_type
            sp = body.shape_params
            if st == "box":
                he = np.asarray(sp["half_extents"], dtype=np.float32)
                S = np.diag([he[0] * 2, he[1] * 2, he[2] * 2, 1.0]).astype(np.float32)
            elif st == "sphere":
                r = float(sp["radius"]) * 2
                S = np.diag([r, r, r, 1.0]).astype(np.float32)
            else:
                S = np.eye(4, dtype=np.float32)

            model = np.eye(4, dtype=np.float32)
            model[:3, :3] = rot @ S[:3, :3]
            model[:3, 3] = pos

            normal_mat = np.linalg.inv(model).T.astype(np.float32)

            # Model 유니폼 버퍼 (128 bytes)
            model_data = (
                np.concatenate([model.T.flatten(), normal_mat.T.flatten()])
                .astype(np.float32)
                .tobytes()
            )
            model_buf = device.create_buffer_with_data(
                data=model_data,
                usage=wgpu.BufferUsage.UNIFORM,
            )

            # Material 유니폼 버퍼 (32 bytes)
            mat = snapshot.materials.get(body.material_id) or BUILTIN_MATERIALS.get(
                body.material_id, BUILTIN_MATERIALS["default"]
            )
            albedo = np.asarray(mat.color[:3], dtype=np.float32)
            mat_arr = np.array(
                [
                    albedo[0],
                    albedo[1],
                    albedo[2],
                    float(mat.roughness),
                    float(mat.metallic),
                    0.0,
                    0.0,
                    0.0,
                ],
                dtype=np.float32,
            )
            mat_buf = device.create_buffer_with_data(
                data=mat_arr.tobytes(),
                usage=wgpu.BufferUsage.UNIFORM,
            )

            bg1 = device.create_bind_group(
                layout=res["bgl1"],
                entries=[
                    {"binding": 0, "resource": {"buffer": model_buf, "offset": 0, "size": 128}},
                    {"binding": 1, "resource": {"buffer": mat_buf, "offset": 0, "size": 32}},
                ],
            )
            rp.set_bind_group(1, bg1)

            # 정점 버퍼
            vbo = device.create_buffer_with_data(
                data=mesh_verts.tobytes(),
                usage=wgpu.BufferUsage.VERTEX,
            )
            rp.set_vertex_buffer(0, vbo)
            rp.draw(len(mesh_verts))

        rp.end()

        # 픽셀 readback
        aligned_row = res["aligned_row"]
        encoder.copy_texture_to_buffer(
            {"texture": res["color_tex"], "mip_level": 0, "origin": (0, 0, 0)},
            {
                "buffer": res["readback_buf"],
                "offset": 0,
                "bytes_per_row": aligned_row,
                "rows_per_image": H,
            },
            (W, H, 1),
        )
        device.queue.submit([encoder.finish()])

        # 비동기 map → 동기 읽기
        async def _read() -> np.ndarray:
            await res["readback_buf"].map_async(wgpu.MapMode.READ)
            raw = res["readback_buf"].read_mapped()
            data = np.frombuffer(raw, dtype=np.uint8).copy()
            res["readback_buf"].unmap()
            # 정렬 패딩 제거
            rows = []
            for row_idx in range(H):
                start = row_idx * aligned_row
                rows.append(data[start : start + W * 4])
            return np.stack(rows).reshape(H, W, 4)

        return asyncio.run(_read())

    def set_camera(self, camera: CameraSnapshot) -> None:
        self._camera = camera
        if self._fallback:
            self._fallback.set_camera(camera)

    def close(self) -> None:
        if self._fallback:
            self._fallback.close()

    @property
    def is_wgpu(self) -> bool:
        return self._wgpu_available
