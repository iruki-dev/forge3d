"""RealtimeRenderer — moderngl (OpenGL 3.3) rasterisation renderer.

Features:
  • PBR shading (Cook-Torrance BRDF): metallic / roughness workflow
  • PCF shadow map (2K, 3×3 kernel)
  • Albedo texture support (PNG/JPEG via imageio)
  • Shapes: box, sphere, capsule, convex-hull mesh
  • Grid, world axes overlay
  • Headless: Xvfb + Mesa llvmpipe (software GL) via context.py

Vertex layout: [px, py, pz,  nx, ny, nz,  u, v]  — 8 floats per vertex.

Usage::

    with RealtimeRenderer(width=800, height=600) as r:
        for snap in snapshots:
            frame = r.render(snap)   # ndarray (H, W, 3) uint8
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.render.base import Frame, Renderer
from forge3d.render.realtime.context import XvfbProcess, create_standalone_context
from forge3d.render.realtime.meshes import (
    axes_lines,
    grid_lines,
    mesh_from_data,
    unit_box,
    unit_capsule,
    unit_sphere,
)
from forge3d.render.realtime.shaders import (
    FLAT_FRAG,
    FLAT_VERT,
    MAIN_FRAG,
    MAIN_VERT,
    SHADOW_FRAG,
    SHADOW_VERT,
)
from forge3d.render.snapshot import BUILTIN_MATERIALS, CameraSnapshot, SceneSnapshot

# ── Matrix helpers ─────────────────────────────────────────────────────────────


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    M = np.zeros((4, 4), dtype=np.float32)
    M[0, 0] = f / aspect
    M[1, 1] = f
    M[2, 2] = -(far + near) / (far - near)
    M[2, 3] = -2.0 * far * near / (far - near)
    M[3, 2] = -1.0
    return M


def _ortho(lo: float, hi: float, b: float, t: float, n: float, f: float) -> np.ndarray:
    M = np.zeros((4, 4), dtype=np.float32)
    M[0, 0] = 2.0 / (hi - lo)
    M[0, 3] = -(hi + lo) / (hi - lo)
    M[1, 1] = 2.0 / (t - b)
    M[1, 3] = -(t + b) / (t - b)
    M[2, 2] = -2.0 / (f - n)
    M[2, 3] = -(f + n) / (f - n)
    M[3, 3] = 1.0
    return M


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    fwd = target - eye
    fwd /= np.linalg.norm(fwd) + 1e-12
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right) + 1e-12
    u = np.cross(right, fwd)
    M = np.eye(4, dtype=np.float32)
    M[0, :3] = right
    M[0, 3] = -right.dot(eye)
    M[1, :3] = u
    M[1, 3] = -u.dot(eye)
    M[2, :3] = -fwd
    M[2, 3] = fwd.dot(eye)
    return M


def _scale_mat(scale: np.ndarray) -> np.ndarray:
    M = np.eye(4, dtype=np.float32)
    M[0, 0], M[1, 1], M[2, 2] = scale
    return M


def _rotation_mat(R: np.ndarray) -> np.ndarray:
    M = np.eye(4, dtype=np.float32)
    M[:3, :3] = R.astype(np.float32)
    return M


def _translate_mat(pos: np.ndarray) -> np.ndarray:
    M = np.eye(4, dtype=np.float32)
    M[:3, 3] = pos.astype(np.float32)
    return M


def _col_major(M: np.ndarray) -> bytes:
    """Row-major float32 matrix → column-major bytes (OpenGL convention)."""
    return M.T.astype(np.float32).tobytes()


# ── Default 1×1 white texture bytes ──────────────────────────────────────────

_WHITE_PIXEL = np.array([255, 255, 255], dtype=np.uint8).tobytes()


# ── RealtimeRenderer ──────────────────────────────────────────────────────────


class RealtimeRenderer(Renderer):
    """OpenGL PBR rasterisation renderer.

    Parameters
    ----------
    width, height : frame dimensions in pixels.
    bg_color      : (R, G, B) background colour in [0, 1].
    shadow_size   : shadow map resolution (square; default 2048).
    """

    SHADOW_SIZE = 2048

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        bg_color: tuple = (0.05, 0.07, 0.10),
        shadow_size: int = 2048,
    ) -> None:
        self._width = width
        self._height = height
        self._bg = bg_color
        self._shadow_size = shadow_size
        self._xvfb: XvfbProcess | None = None

        # Lazily initialised on first render
        self._ctx: Any = None
        self._shadow_prog: Any = None
        self._main_prog: Any = None
        self._flat_prog: Any = None
        self._shadow_fbo: Any = None
        self._shadow_tex: Any = None
        self._render_fbo: Any = None
        self._render_tex: Any = None
        self._camera: CameraSnapshot | None = None

        # VAO caches
        # unit shapes: "box", "sphere"
        self._vaos: dict[str, Any] = {}
        # capsule VAOs keyed by (radius, half_length) rounded to 4 decimals
        self._capsule_vaos: dict[tuple, Any] = {}
        # mesh VAOs keyed by mesh_id (int)
        self._mesh_vaos: dict[int, Any] = {}
        # texture objects keyed by path
        self._textures: dict[str, Any] = {}
        # default white texture (used when no albedo texture is specified)
        self._white_tex: Any = None

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> RealtimeRenderer:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Lazy init ─────────────────────────────────────────────────────────────

    def _ensure_init(self) -> None:
        if self._ctx is not None:
            return
        self._ctx, self._xvfb = create_standalone_context(self._width, self._height)
        ctx = self._ctx

        self._shadow_prog = ctx.program(vertex_shader=SHADOW_VERT, fragment_shader=SHADOW_FRAG)
        self._main_prog = ctx.program(vertex_shader=MAIN_VERT, fragment_shader=MAIN_FRAG)
        self._flat_prog = ctx.program(vertex_shader=FLAT_VERT, fragment_shader=FLAT_FRAG)

        # Shadow FBO (2K depth texture for sharper shadows)
        self._shadow_tex = ctx.depth_texture((self._shadow_size, self._shadow_size))
        self._shadow_fbo = ctx.framebuffer(depth_attachment=self._shadow_tex)

        # Render FBO
        self._render_tex = ctx.texture((self._width, self._height), 3)
        _depth_buf = ctx.depth_renderbuffer((self._width, self._height))
        self._render_fbo = ctx.framebuffer(
            color_attachments=[self._render_tex],
            depth_attachment=_depth_buf,
        )

        # Default 1×1 white texture (bound when no albedo texture is needed)
        self._white_tex = ctx.texture((1, 1), 3, _WHITE_PIXEL)

        self._init_geometry(ctx)

    def _init_geometry(self, ctx: Any) -> None:
        """Pre-build cached VAOs for unit primitives."""
        for key, mesh_fn in [("box", unit_box), ("sphere", unit_sphere)]:
            verts, idx = mesh_fn()
            self._vaos[key] = self._make_solid_vao(ctx, verts, idx)
            self._vaos[key + "_shd"] = self._make_shadow_vao(ctx, verts, idx)

        # Grid
        grid_v = grid_lines(half_size=10.0, step=1.0)
        grid_vbo = ctx.buffer(grid_v.tobytes())
        self._vaos["grid"] = (
            ctx.vertex_array(self._flat_prog, [(grid_vbo, "3f", "in_position")]),
            len(grid_v),
        )

        # Axes
        ax_v, ax_c = axes_lines(1.5)
        ax_vbo = ctx.buffer(ax_v.tobytes())
        self._vaos["axes"] = (
            ctx.vertex_array(self._flat_prog, [(ax_vbo, "3f", "in_position")]),
            len(ax_v),
            ax_c,
        )

    def _make_solid_vao(self, ctx: Any, verts: np.ndarray, idx: np.ndarray) -> Any:
        """Build a main-pass VAO with 8-float vertex layout [pos, normal, uv]."""
        vbo = ctx.buffer(verts.astype(np.float32).tobytes())
        ibo = ctx.buffer(idx.astype(np.uint32).tobytes())
        vao = ctx.vertex_array(
            self._main_prog,
            [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
            index_buffer=ibo,
        )
        return (vao, len(idx))

    def _make_shadow_vao(self, ctx: Any, verts: np.ndarray, idx: np.ndarray) -> Any:
        """Build a shadow-pass VAO (position-only, stride 8 floats)."""
        # Extract positions only: first 3 floats of each 8-float vertex
        v8 = verts.reshape(-1, 8)
        pos_only = np.ascontiguousarray(v8[:, :3], dtype=np.float32)
        vbo = ctx.buffer(pos_only.tobytes())
        ibo = ctx.buffer(idx.astype(np.uint32).tobytes())
        vao = ctx.vertex_array(
            self._shadow_prog,
            [(vbo, "3f", "in_position")],
            index_buffer=ibo,
        )
        return (vao, len(idx))

    # ── Capsule VAO (cached by shape parameters) ──────────────────────────────

    def _get_capsule_vaos(self, radius: float, half_length: float) -> tuple[Any, Any]:
        key = (round(radius, 4), round(half_length, 4))
        if key not in self._capsule_vaos:
            verts, idx = unit_capsule(radius=radius, half_length=half_length)
            solid = self._make_solid_vao(self._ctx, verts, idx)
            shadow = self._make_shadow_vao(self._ctx, verts, idx)
            self._capsule_vaos[key] = (solid, shadow)
        return self._capsule_vaos[key]

    # ── Mesh VAO (cached by mesh_id) ──────────────────────────────────────────

    def _get_mesh_vaos(self, mesh_data: Any) -> tuple[Any, Any]:
        mid = mesh_data.mesh_id
        if mid not in self._mesh_vaos:
            verts, idx = mesh_from_data(mesh_data)
            solid = self._make_solid_vao(self._ctx, verts, idx)
            shadow = self._make_shadow_vao(self._ctx, verts, idx)
            self._mesh_vaos[mid] = (solid, shadow)
        return self._mesh_vaos[mid]

    # ── Texture loading (cached by path) ─────────────────────────────────────

    def _get_texture(self, path: str) -> Any:
        if path in self._textures:
            return self._textures[path]
        try:
            import imageio.v3 as iio

            img = iio.imread(path)
            if img.ndim == 2:
                img = np.stack([img, img, img], axis=-1)
            if img.shape[2] == 4:
                img = img[:, :, :3]
            img = np.ascontiguousarray(np.flipud(img).astype(np.uint8))
            h, w = img.shape[:2]
            tex = self._ctx.texture((w, h), 3, img.tobytes())
            tex.filter = (self._ctx.LINEAR_MIPMAP_LINEAR, self._ctx.LINEAR)
            tex.build_mipmaps()
            self._textures[path] = tex
            return tex
        except Exception:
            return None

    # ── Camera helpers ────────────────────────────────────────────────────────

    def set_camera(self, camera: CameraSnapshot) -> None:
        self._camera = camera

    def _active_camera(self, snapshot: SceneSnapshot) -> CameraSnapshot:
        if self._camera is not None:
            return self._camera
        if snapshot.camera is not None:
            return snapshot.camera
        return CameraSnapshot(
            position=np.array([5.0, -8.0, 4.0]),
            target=np.array([0.0, 0.0, 0.0]),
            up=np.array([0.0, 0.0, 1.0]),
            fov_deg=45.0,
        )

    # ── Model matrix helpers ──────────────────────────────────────────────────

    def _model_matrix(self, body: Any, scale: np.ndarray) -> np.ndarray:
        S = _scale_mat(scale)
        R = _rotation_mat(body.transform.rotation)
        T = _translate_mat(body.transform.position)
        return T @ R @ S

    def _body_scale(self, body: Any) -> np.ndarray:
        st = body.shape_type
        sp = body.shape_params
        if st == "box":
            he = sp["half_extents"]
            return np.array([he[0] * 2, he[1] * 2, he[2] * 2], dtype=np.float32)
        if st == "sphere":
            r = float(sp["radius"])
            return np.array([r, r, r], dtype=np.float32)
        # capsule and mesh: mesh built at actual size, no extra scale needed
        return np.ones(3, dtype=np.float32)

    # ── Light helpers ─────────────────────────────────────────────────────────

    def _light_matrices(self, light: Any) -> tuple[np.ndarray, np.ndarray]:
        ld = np.asarray(light.direction, dtype=float)
        ld = ld / (np.linalg.norm(ld) + 1e-12)
        light_eye = -50.0 * ld
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(ld, up)) > 0.95:
            up = np.array([0.0, 1.0, 0.0])
        LV = _look_at(light_eye, np.zeros(3), up)
        LP = _ortho(-25, 25, -25, 25, n=0.1, f=150.0)
        return LP, LV

    # ── Per-body render helpers ───────────────────────────────────────────────

    def _get_body_vaos(self, body: Any) -> tuple[Any, Any] | None:
        """Return (solid_vao_tuple, shadow_vao_tuple) or None if unsupported."""
        st = body.shape_type
        if st in ("box", "sphere"):
            return self._vaos[st], self._vaos[st + "_shd"]
        if st == "capsule":
            r = float(body.shape_params["radius"])
            hl = float(body.shape_params["half_length"])
            return self._get_capsule_vaos(r, hl)
        if st == "mesh":
            mesh_data = body.shape_params.get("mesh_data")
            if mesh_data is None:
                return None
            return self._get_mesh_vaos(mesh_data)
        return None

    def _set_material_uniforms(
        self,
        prog: Any,
        mat: Any | None,
        texture_path: str | None,
    ) -> Any:
        """Set material-related uniforms and bind texture. Returns the bound texture."""
        color = np.array(mat.color, dtype=np.float32) if mat else np.ones(3, np.float32)
        roughness = float(mat.roughness) if mat else 0.5
        metallic = float(mat.metallic) if mat else 0.0

        tex = None
        has_tex = 0
        if texture_path:
            tex = self._get_texture(texture_path)
            if tex is not None:
                has_tex = 1

        try:
            prog["u_mat_color"].write(color.tobytes())
            prog["u_roughness"].value = roughness
            prog["u_metallic"].value = metallic
            prog["u_has_texture"].value = has_tex
        except KeyError:
            pass
        return tex

    # ── Main render method ────────────────────────────────────────────────────

    def render(self, snapshot: SceneSnapshot) -> Frame | None:
        self._ensure_init()
        ctx = self._ctx

        cam = self._active_camera(snapshot)
        aspect = self._width / self._height
        V = _look_at(
            np.array(cam.position, dtype=float),
            np.array(cam.target, dtype=float),
            np.array(cam.up, dtype=float),
        )
        P = _perspective(cam.fov_deg, aspect, cam.near, cam.far)
        VP = P @ V

        # Light (first or default)
        light = snapshot.lights[0] if snapshot.lights else None
        if light is None:
            from forge3d.render.snapshot import LightSnapshot

            light = LightSnapshot(
                direction=np.array([-0.4, -0.6, -0.7]) / np.sqrt(0.4**2 + 0.6**2 + 0.7**2),
                color=np.array([1.0, 0.95, 0.85]),
                intensity=1.0,
                cast_shadow=True,
            )

        LP, LV = self._light_matrices(light)
        light_VP = LP @ LV

        mat_lookup = {**BUILTIN_MATERIALS, **snapshot.materials}

        # ── Shadow pass ───────────────────────────────────────────────────────
        self._shadow_fbo.use()
        self._shadow_fbo.clear(depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        for body in snapshot.bodies:
            vaos = self._get_body_vaos(body)
            if vaos is None:
                continue
            _, shadow_vao_t = vaos
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale).astype(np.float32)
            light_MVP = (light_VP @ M).astype(np.float32)
            svao, sn = shadow_vao_t
            try:
                self._shadow_prog["u_light_MVP"].write(_col_major(light_MVP))
            except KeyError:
                pass
            svao.render(mode=ctx.TRIANGLES, vertices=sn)

        # ── Main PBR pass ─────────────────────────────────────────────────────
        self._render_fbo.use()
        self._render_fbo.clear(red=self._bg[0], green=self._bg[1], blue=self._bg[2], depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        # Bind shadow texture to unit 0; albedo texture to unit 1
        self._shadow_tex.use(location=0)

        light_dir = np.asarray(light.direction, dtype=float)
        light_dir_norm = -light_dir / (np.linalg.norm(light_dir) + 1e-12)
        ambient = np.array([0.08, 0.09, 0.12], dtype=np.float32)

        prog = self._main_prog
        try:
            prog["u_shadow_map"] = 0
            prog["u_albedo_map"] = 1
            prog["u_light_dir"].write(light_dir_norm.astype(np.float32).tobytes())
            prog["u_light_color"].write(
                (np.asarray(light.color, dtype=np.float32) * float(light.intensity)).tobytes()
            )
            prog["u_ambient_color"].write(ambient.tobytes())
            prog["u_eye"].write(np.array(cam.position, dtype=np.float32).tobytes())
        except KeyError:
            pass

        for body in snapshot.bodies:
            vaos = self._get_body_vaos(body)
            if vaos is None:
                continue
            solid_vao_t, _ = vaos
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale).astype(np.float32)
            MVP = (P @ V @ M).astype(np.float32)

            # Normal matrix: inv(M[:3,:3]).T = R / scale (avoids np.linalg.inv)
            R33 = body.transform.rotation.astype(np.float32)
            NM = (R33 / (scale[None, :] + 1e-12)).astype(np.float32)

            light_MVP_body = (light_VP @ M).astype(np.float32)

            mat_obj = mat_lookup.get(body.material_id, mat_lookup.get("default"))

            # Texture: check snapshot materials for texture path
            snap_mat = snapshot.materials.get(body.material_id)
            tex_path = getattr(snap_mat, "texture_path", None)

            bound_tex = self._set_material_uniforms(prog, mat_obj, tex_path)

            # Bind albedo texture (or white default)
            if bound_tex is not None:
                bound_tex.use(location=1)
            else:
                self._white_tex.use(location=1)

            try:
                prog["u_MVP"].write(_col_major(MVP))
                prog["u_M"].write(_col_major(M))
                prog["u_NM"].write(NM.T.tobytes())
                prog["u_light_MVP"].write(_col_major(light_MVP_body))
            except KeyError:
                pass

            vao, n_idx = solid_vao_t
            vao.render(mode=ctx.TRIANGLES, vertices=n_idx)

        # ── Grid ──────────────────────────────────────────────────────────────
        grid_vao, grid_n = self._vaos["grid"]
        ctx.disable(ctx.DEPTH_TEST)
        try:
            self._flat_prog["u_VP"].write(_col_major(VP.astype(np.float32)))
            self._flat_prog["u_color"].write(
                np.array([0.20, 0.25, 0.20, 0.5], dtype=np.float32).tobytes()
            )
        except KeyError:
            pass
        grid_vao.render(mode=ctx.LINES, vertices=grid_n)

        # ── Axes ──────────────────────────────────────────────────────────────
        ax_vao, ax_n, ax_colors = self._vaos["axes"]
        for i in range(3):
            try:
                self._flat_prog["u_color"].write(ax_colors[i * 2].tobytes())
            except KeyError:
                pass
            ax_vao.render(mode=ctx.LINES, vertices=2, first=i * 2)

        ctx.enable(ctx.DEPTH_TEST)

        # ── Read back pixels ──────────────────────────────────────────────────
        data = self._render_fbo.read(components=3, dtype="f1")
        frame = np.frombuffer(data, dtype=np.uint8).reshape(self._height, self._width, 3)
        return frame[::-1].copy()  # flip: OpenGL origin is bottom-left

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._ctx is not None:
            for val in self._vaos.values():
                if hasattr(val[0], "release"):
                    val[0].release()
            for val in self._capsule_vaos.values():
                for vao_t in val:
                    if hasattr(vao_t[0], "release"):
                        vao_t[0].release()
            for val in self._mesh_vaos.values():
                for vao_t in val:
                    if hasattr(vao_t[0], "release"):
                        vao_t[0].release()
            for tex in self._textures.values():
                if hasattr(tex, "release"):
                    tex.release()
            if self._white_tex is not None:
                self._white_tex.release()
            self._ctx.release()
            self._ctx = None
        if self._xvfb is not None:
            self._xvfb.stop()
            self._xvfb = None
