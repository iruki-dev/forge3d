"""DeferredRenderer — OpenGL 4.3 지연 렌더링 파이프라인.

패스 순서:
  1. Shadow  — CSM 4단계 깊이맵
  2. GBuffer — 위치/법선/알베도-roughness/emissive-metallic
  3. SSAO    — 반구 AO + blur
  4. Lighting — GGX-Cook-Torrance PBR + CSM 그림자
  5. PostProcess — 블룸 다운/업샘플 + ACES 톤맵

SceneSnapshot 계약 유지: 물리 코어는 이 파일을 import하지 않는다.
"""
from __future__ import annotations

import importlib.resources
import os
from pathlib import Path
from typing import Any

import numpy as np

from forge3d.render.base import Frame, Renderer
from forge3d.render.realtime.context import XvfbProcess, create_standalone_context
from forge3d.render.realtime.meshes import (
    mesh_from_data,
    unit_box,
    unit_capsule,
    unit_sphere,
)
from forge3d.render.snapshot import BUILTIN_MATERIALS, CameraSnapshot, SceneSnapshot

# ── 셰이더 경로 ──────────────────────────────────────────────────────────────

_SHADER_DIR = Path(__file__).parent.parent / "shaders"


def _load_shader(name: str) -> str:
    path = _SHADER_DIR / name
    if path.exists():
        return path.read_text()
    raise FileNotFoundError(f"셰이더 파일 없음: {path}")


# ── 행렬 헬퍼 ────────────────────────────────────────────────────────────────


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
    f_norm = np.linalg.norm(f)
    if f_norm < 1e-10:
        f = np.array([0.0, 0.0, -1.0])
    else:
        f = f / f_norm
    s = np.cross(f, up)
    s_norm = np.linalg.norm(s)
    s = s / (s_norm + 1e-10)
    u2 = np.cross(s, f)
    M = np.eye(4, dtype=np.float32)
    M[0, :3] = s
    M[1, :3] = u2
    M[2, :3] = -f
    M[0, 3] = -float(s.dot(eye))
    M[1, 3] = -float(u2.dot(eye))
    M[2, 3] = float(f.dot(eye))
    return M


def _ortho(left: float, right: float, bottom: float, top: float,
           near: float, far: float) -> np.ndarray:
    M = np.zeros((4, 4), dtype=np.float32)
    M[0, 0] = 2.0 / (right - left)
    M[1, 1] = 2.0 / (top - bottom)
    M[2, 2] = -2.0 / (far - near)
    M[0, 3] = -(right + left) / (right - left)
    M[1, 3] = -(top + bottom) / (top - bottom)
    M[2, 3] = -(far + near) / (far - near)
    M[3, 3] = 1.0
    return M


def _model_matrix(pos: np.ndarray, rot: np.ndarray, scale: np.ndarray) -> np.ndarray:
    M = np.eye(4, dtype=np.float32)
    M[:3, :3] = (rot * scale[None, :]).astype(np.float32)
    M[:3, 3] = pos.astype(np.float32)
    return M


def _ssao_kernel(n: int = 64, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    samples = []
    for i in range(n):
        s = rng.uniform(-1, 1, 3)
        s[2] = abs(s[2])
        s /= np.linalg.norm(s) + 1e-10
        scale = i / n
        scale = 0.1 + scale * scale * 0.9
        samples.append(s * scale)
    return np.array(samples, dtype=np.float32)


def _ssao_noise(size: int = 4, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.uniform(0, 1, (size * size, 3)).astype(np.float32)
    noise[:, 2] = 0.0
    return noise.reshape(size, size, 3)


# ── DeferredRenderer ──────────────────────────────────────────────────────────


class DeferredRenderer(Renderer):
    """OpenGL 4.3+ 지연 렌더링 파이프라인."""

    SHADOW_SIZE = 2048
    NOISE_SIZE = 4

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        shadow_cascades: int = 4,
        ssao_samples: int = 64,
        bloom_threshold: float = 1.0,
        bloom_strength: float = 0.5,
        exposure: float = 1.0,
        _ctx: Any = None,
    ) -> None:
        self.width = width
        self.height = height
        self.n_cascades = shadow_cascades
        self.ssao_samples = ssao_samples
        self.bloom_threshold = bloom_threshold
        self.bloom_strength = bloom_strength
        self.exposure = exposure

        self._xvfb: XvfbProcess | None = None
        if _ctx is not None:
            self.ctx = _ctx
        else:
            self.ctx, self._xvfb = create_standalone_context(width=width, height=height)

        self._camera: CameraSnapshot | None = None
        self._vao_cache: dict[str, Any] = {}

        self._setup()

    def _setup(self) -> None:
        ctx = self.ctx
        W, H = self.width, self.height
        S = self.SHADOW_SIZE

        # ── G-Buffer FBO ──
        self._g_pos     = ctx.texture((W, H), 3, dtype="f4")
        self._g_norm    = ctx.texture((W, H), 3, dtype="f2")
        self._g_ar      = ctx.texture((W, H), 4)              # albedo+rough RGBA8
        self._g_em      = ctx.texture((W, H), 4)              # emissive+metal RGBA8
        self._g_depth   = ctx.depth_texture((W, H))
        self._gbuffer_fbo = ctx.framebuffer(
            color_attachments=[self._g_pos, self._g_norm, self._g_ar, self._g_em],
            depth_attachment=self._g_depth,
        )

        # ── 섀도맵 FBOs (cascade별) ──
        self._shadow_maps: list[Any] = []
        self._shadow_fbos: list[Any] = []
        for _ in range(self.n_cascades):
            depth_tex = ctx.depth_texture((S, S))
            depth_tex.compare_func = ""  # raw depth read
            fbo = ctx.framebuffer(depth_attachment=depth_tex)
            self._shadow_maps.append(depth_tex)
            self._shadow_fbos.append(fbo)

        # ── SSAO ──
        self._ssao_raw  = ctx.texture((W, H), 1, dtype="f1")
        self._ssao_blur = ctx.texture((W, H), 1, dtype="f1")
        self._ssao_fbo      = ctx.framebuffer(color_attachments=[self._ssao_raw])
        self._ssao_blur_fbo = ctx.framebuffer(color_attachments=[self._ssao_blur])

        kernel = _ssao_kernel(self.ssao_samples)
        noise_data = _ssao_noise(self.NOISE_SIZE)
        self._ssao_noise_tex = ctx.texture(
            (self.NOISE_SIZE, self.NOISE_SIZE), 3, dtype="f4",
            data=noise_data.astype(np.float32).tobytes(),
        )
        self._ssao_noise_tex.repeat_x = True
        self._ssao_noise_tex.repeat_y = True
        self._ssao_kernel = kernel

        # ── HDR + Bloom ──
        self._hdr_color = ctx.texture((W, H), 3, dtype="f2")  # RGB16F HDR
        self._hdr_depth = ctx.depth_texture((W, H))
        self._hdr_fbo   = ctx.framebuffer(
            color_attachments=[self._hdr_color], depth_attachment=self._hdr_depth
        )
        self._bloom_a = ctx.texture((W // 2, H // 2), 3, dtype="f2")
        self._bloom_b = ctx.texture((W // 2, H // 2), 3, dtype="f2")
        self._bloom_fbo_a = ctx.framebuffer(color_attachments=[self._bloom_a])
        self._bloom_fbo_b = ctx.framebuffer(color_attachments=[self._bloom_b])

        # ── 최종 출력 ──
        self._final_color = ctx.texture((W, H), 4)
        self._final_fbo   = ctx.framebuffer(color_attachments=[self._final_color])

        # ── 셰이더 프로그램 ──
        fs_vert = _load_shader("fullscreen.vert")
        self._prog_gbuf = ctx.program(
            vertex_shader=_load_shader("gbuffer.vert"),
            fragment_shader=_load_shader("gbuffer.frag"),
        )
        self._prog_shadow = ctx.program(
            vertex_shader=_load_shader("shadow.vert"),
            fragment_shader=_load_shader("shadow.frag"),
        )
        self._prog_lighting = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("lighting.frag"),
        )
        self._prog_ssao = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("ssao.frag"),
        )
        self._prog_ssao_blur = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("ssao_blur.frag"),
        )
        self._prog_bloom_down = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("bloom_down.frag"),
        )
        self._prog_bloom_up = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("bloom_up.frag"),
        )
        self._prog_tonemap = ctx.program(
            vertex_shader=fs_vert,
            fragment_shader=_load_shader("tonemap.frag"),
        )

        # 풀스크린 VAO (인덱스 없이 4 정점 TRIANGLE_STRIP)
        self._fullscreen_vao = ctx.vertex_array(self._prog_lighting, [])

        # 기본 메시 VAO 캐시
        self._build_mesh_vaos()

    def _build_mesh_vaos(self) -> None:
        ctx = self.ctx
        for key, fn in [("box", unit_box), ("sphere", unit_sphere), ("capsule", unit_capsule)]:
            verts, idxs = fn()
            vbo = ctx.buffer(verts.astype(np.float32).tobytes())
            ibo = ctx.buffer(idxs.astype(np.uint32).tobytes())
            vao = ctx.vertex_array(
                self._prog_gbuf,
                [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                index_buffer=ibo,
            )
            self._vao_cache[key] = (vao, len(idxs))

            # 섀도 전용 VAO (position만, _prog_shadow 바인딩)
            svao = ctx.vertex_array(
                self._prog_shadow,
                [(vbo, "3f 12x", "in_position")],  # normal(12B) + uv(8B) skip
                index_buffer=ibo,
            )
            self._vao_cache[f"shadow_{key}"] = (svao, len(idxs))

    def _get_vao(self, body_snap: Any) -> tuple[Any, int] | None:
        st = body_snap.shape_type
        if st in self._vao_cache:
            return self._vao_cache[st]
        if st == "mesh":
            hull = body_snap.shape_params.get("hull_vertices")
            if hull is None:
                return self._vao_cache.get("box")
            # 메시별 캐시
            key = f"mesh_{id(hull)}"
            if key not in self._vao_cache:
                verts, idxs = mesh_from_data(hull)
                vbo = self.ctx.buffer(verts.astype(np.float32).tobytes())
                ibo = self.ctx.buffer(idxs.astype(np.uint32).tobytes())
                vao = self.ctx.vertex_array(
                    self._prog_gbuf,
                    [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                    index_buffer=ibo,
                )
                self._vao_cache[key] = (vao, len(idxs))
            return self._vao_cache[key]
        return None

    def _body_model_matrix(self, body_snap: Any) -> np.ndarray:
        pos = np.asarray(body_snap.transform.position, dtype=np.float32)
        rot = np.asarray(body_snap.transform.rotation, dtype=np.float32)
        st = body_snap.shape_type
        sp = body_snap.shape_params
        if st == "box":
            he = np.asarray(sp["half_extents"], dtype=np.float32)
            scale = he * 2.0
        elif st == "sphere":
            r = float(sp["radius"])
            scale = np.array([r * 2, r * 2, r * 2], dtype=np.float32)
        elif st == "capsule":
            r = float(sp["radius"])
            hl = float(sp["half_length"])
            scale = np.array([r * 2, r * 2, (hl + r) * 2], dtype=np.float32)
        else:
            scale = np.ones(3, dtype=np.float32)
        return _model_matrix(pos, rot, scale)

    def _cascade_light_vps(
        self, snapshot: SceneSnapshot, view: np.ndarray, proj: np.ndarray,
    ) -> tuple[list[np.ndarray], list[float]]:
        cam = snapshot.camera
        near = cam.near if cam else 0.1
        far = cam.far if cam else 200.0
        ratios = [0.05, 0.15, 0.40, 1.0]
        splits = [near + r * (far - near) for r in ratios]

        light_dir = np.array([0.0, 0.0, -1.0], dtype=np.float64)
        if snapshot.lights:
            d = np.asarray(snapshot.lights[0].direction, dtype=np.float64)
            n = np.linalg.norm(d)
            if n > 1e-10:
                light_dir = d / n

        light_vps: list[np.ndarray] = []
        for i, (z_near, z_far) in enumerate(
            zip([near] + splits[:-1], splits)
        ):
            # frustum corners in world space (approximate via bounding sphere)
            center_z = (z_near + z_far) * 0.5
            radius = (z_far - z_near) * 0.5 * 1.5
            if cam:
                cam_pos = np.asarray(cam.position, dtype=np.float64)
                cam_fwd = np.asarray(cam.target, dtype=np.float64) - cam_pos
                n_ = np.linalg.norm(cam_fwd)
                cam_fwd = cam_fwd / (n_ + 1e-10)
            else:
                cam_pos = np.zeros(3)
                cam_fwd = np.array([0.0, -1.0, 0.0])

            frustum_center = cam_pos + cam_fwd * center_z

            lpos = frustum_center - light_dir * (radius + 1.0)
            ltarget = frustum_center
            lup = np.array([0.0, 0.0, 1.0]) if abs(light_dir[2]) < 0.9 else np.array([0.0, 1.0, 0.0])

            l_view = _lookat(lpos, ltarget, lup)
            l_proj = _ortho(-radius, radius, -radius, radius, 0.1, radius * 2 + 2.0)
            light_vps.append((l_proj @ l_view).astype(np.float32))

        return light_vps, splits

    def render(self, snapshot: SceneSnapshot) -> Frame:
        ctx = self.ctx
        W, H = self.width, self.height

        cam = snapshot.camera or CameraSnapshot(
            position=np.array([5.0, -8.0, 5.0]),
            target=np.zeros(3),
            up=np.array([0.0, 0.0, 1.0]),
        )
        if self._camera is not None:
            cam = self._camera

        eye = np.asarray(cam.position, dtype=np.float64)
        tgt = np.asarray(cam.target, dtype=np.float64)
        up = np.asarray(cam.up, dtype=np.float64)
        view = _lookat(eye, tgt, up)
        proj = _perspective(cam.fov_deg, W / H, cam.near, cam.far)

        light_vps, splits = self._cascade_light_vps(snapshot, view, proj)
        has_light = len(snapshot.lights) > 0
        if has_light:
            ld = np.asarray(snapshot.lights[0].direction, dtype=np.float32)
            ln = np.linalg.norm(ld)
            light_dir = (ld / (ln + 1e-10)).astype(np.float32)
            light_color = np.asarray(snapshot.lights[0].color, dtype=np.float32)
            light_intensity = float(snapshot.lights[0].intensity)
        else:
            light_dir = np.array([0.0, 0.0, 1.0], dtype=np.float32)
            light_color = np.ones(3, dtype=np.float32)
            light_intensity = 0.5

        # ── 1. Shadow pass ──────────────────────────────────────────────
        ctx.enable(ctx.DEPTH_TEST)
        for ci, (shadow_fbo, light_vp) in enumerate(zip(self._shadow_fbos, light_vps)):
            shadow_fbo.use()
            ctx.viewport = (0, 0, self.SHADOW_SIZE, self.SHADOW_SIZE)
            ctx.clear(depth=1.0)
            for body in snapshot.bodies:
                svao_pair = self._get_shadow_vao_pair(body)
                if svao_pair is None:
                    continue
                svao, _n = svao_pair
                M = self._body_model_matrix(body)
                light_mvp = (light_vp @ M).astype(np.float32)
                try:
                    self._prog_shadow["u_light_mvp"].write(light_mvp.T.tobytes())
                except KeyError:
                    pass
                svao.render()

        # ── 2. G-Buffer pass ─────────────────────────────────────────────
        self._gbuffer_fbo.use()
        ctx.viewport = (0, 0, W, H)
        ctx.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        ctx.enable(ctx.CULL_FACE)
        ctx.cull_face = "back"

        for body in snapshot.bodies:
            vao_pair = self._get_vao(body)
            if vao_pair is None:
                continue
            vao, n_idx = vao_pair
            M = self._body_model_matrix(body)
            normal_mat = np.linalg.inv(M[:3, :3]).T.astype(np.float32)

            mat = self._get_material(body.material_id, snapshot)

            try:
                self._prog_gbuf["u_model"].write(M.T.tobytes())
                self._prog_gbuf["u_view"].write(view.T.astype(np.float32).tobytes())
                self._prog_gbuf["u_proj"].write(proj.T.tobytes())
                self._prog_gbuf["u_normal_mat"].write(normal_mat.tobytes())
                self._prog_gbuf["u_albedo"].value = tuple(mat.color[:3])
                self._prog_gbuf["u_roughness"].value = float(mat.roughness)
                self._prog_gbuf["u_metallic"].value = float(mat.metallic)
                emissive = getattr(mat, "emissive", (0.0, 0.0, 0.0))
                self._prog_gbuf["u_emissive"].value = tuple(emissive[:3])
                self._prog_gbuf["u_has_texture"].value = False
            except KeyError:
                pass

            vao.render()

        ctx.disable(ctx.CULL_FACE)

        # ── 3. SSAO pass ─────────────────────────────────────────────────
        self._ssao_fbo.use()
        ctx.viewport = (0, 0, W, H)
        ctx.clear(1.0, 1.0, 1.0, 1.0)
        self._g_pos.use(0)
        self._g_norm.use(1)
        self._ssao_noise_tex.use(2)
        fsq_ssao = ctx.vertex_array(self._prog_ssao, [])
        try:
            self._prog_ssao["g_position"].value = 0
            self._prog_ssao["g_normal"].value = 1
            self._prog_ssao["u_noise"].value = 2
            self._prog_ssao["u_proj"].write(proj.T.tobytes())
            self._prog_ssao["u_noise_scale"].value = (W / self.NOISE_SIZE, H / self.NOISE_SIZE)
            self._prog_ssao["u_radius"].value = 0.5
            self._prog_ssao["u_bias"].value = 0.025
            for i, s in enumerate(self._ssao_kernel):
                self._prog_ssao[f"u_samples[{i}]"].value = tuple(s)
        except KeyError:
            pass
        fsq_ssao.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # SSAO blur
        self._ssao_blur_fbo.use()
        ctx.clear(1.0, 1.0, 1.0, 1.0)
        self._ssao_raw.use(0)
        fsq_blur = ctx.vertex_array(self._prog_ssao_blur, [])
        try:
            self._prog_ssao_blur["u_ssao_raw"].value = 0
        except KeyError:
            pass
        fsq_blur.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # ── 4. Lighting pass (HDR FBO) ───────────────────────────────────
        self._hdr_fbo.use()
        ctx.viewport = (0, 0, W, H)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        self._g_pos.use(0)
        self._g_norm.use(1)
        self._g_ar.use(2)
        self._g_em.use(3)
        self._ssao_blur.use(4)
        for ci, sm in enumerate(self._shadow_maps[:4]):
            sm.use(5 + ci)

        fsq_light = ctx.vertex_array(self._prog_lighting, [])
        try:
            self._prog_lighting["g_position"].value = 0
            self._prog_lighting["g_normal"].value = 1
            self._prog_lighting["g_albedo_rough"].value = 2
            self._prog_lighting["g_emissive_metal"].value = 3
            self._prog_lighting["u_ssao"].value = 4
            for ci in range(self.n_cascades):
                self._prog_lighting[f"u_shadow{ci}"].value = 5 + ci
            self._prog_lighting["u_cam_pos"].value = tuple(eye.astype(np.float32))
            self._prog_lighting["u_light_dir"].value = tuple(-light_dir)
            self._prog_lighting["u_light_color"].value = tuple(light_color)
            self._prog_lighting["u_light_intensity"].value = light_intensity
            self._prog_lighting["u_has_shadow"].value = has_light
            self._prog_lighting["u_view"].write(view.T.astype(np.float32).tobytes())
            for ci, (lvp, sp) in enumerate(zip(light_vps, splits)):
                self._prog_lighting[f"u_light_vp[{ci}]"].write(lvp.T.tobytes())
                self._prog_lighting[f"u_cascade_splits[{ci}]"].value = float(sp)
        except KeyError:
            pass
        fsq_light.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # ── 5. Bloom pass ────────────────────────────────────────────────
        # Downsample → bright filter
        self._bloom_fbo_a.use()
        ctx.viewport = (0, 0, W // 2, H // 2)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        self._hdr_color.use(0)
        fsq_bloom_d = ctx.vertex_array(self._prog_bloom_down, [])
        try:
            self._prog_bloom_down["u_src"].value = 0
            self._prog_bloom_down["u_threshold"].value = self.bloom_threshold
        except KeyError:
            pass
        fsq_bloom_d.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # Upsample
        self._bloom_fbo_b.use()
        ctx.viewport = (0, 0, W // 2, H // 2)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        self._bloom_a.use(0)
        fsq_bloom_u = ctx.vertex_array(self._prog_bloom_up, [])
        try:
            self._prog_bloom_up["u_src"].value = 0
            self._prog_bloom_up["u_strength"].value = 1.0
        except KeyError:
            pass
        fsq_bloom_u.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # ── 6. Tonemap pass ──────────────────────────────────────────────
        self._final_fbo.use()
        ctx.viewport = (0, 0, W, H)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        self._hdr_color.use(0)
        self._bloom_b.use(1)
        fsq_tone = ctx.vertex_array(self._prog_tonemap, [])
        try:
            self._prog_tonemap["u_hdr"].value = 0
            self._prog_tonemap["u_bloom"].value = 1
            self._prog_tonemap["u_exposure"].value = self.exposure
            self._prog_tonemap["u_bloom_strength"].value = self.bloom_strength
        except KeyError:
            pass
        fsq_tone.render(mode=ctx.TRIANGLE_STRIP, vertices=4)

        # ── 7. 프레임 읽기 ─────────────────────────────────────────────
        self._final_fbo.use()
        raw = self._final_fbo.read(components=4, dtype="f1")
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)
        return np.flipud(frame)

    def _get_material(self, material_id: str, snapshot: SceneSnapshot) -> Any:
        if material_id in snapshot.materials:
            return snapshot.materials[material_id]
        return BUILTIN_MATERIALS.get(material_id, BUILTIN_MATERIALS["default"])

    def _get_shadow_vao_pair(self, body_snap: Any) -> tuple[Any, int] | None:
        """그림자 패스용 전용 VAO (shadow_{shape} 캐시)."""
        st = body_snap.shape_type
        key = f"shadow_{st}"
        return self._vao_cache.get(key)

    def set_camera(self, camera: CameraSnapshot) -> None:
        self._camera = camera

    def close(self) -> None:
        if self._xvfb:
            self._xvfb.stop()
            self._xvfb = None

    @property
    def gbuffer_textures(self) -> dict[str, Any]:
        """테스트 접근용: G-Buffer 텍스처 딕셔너리."""
        return {
            "position": self._g_pos,
            "normal": self._g_norm,
            "albedo_rough": self._g_ar,
            "emissive_metal": self._g_em,
        }

    @property
    def shadow_maps(self) -> list[Any]:
        """테스트 접근용: 섀도맵 텍스처 리스트."""
        return self._shadow_maps
