"""Window renderer for Forge Ball.

Uses pygame (SDL2) for window + input handling, moderngl (OpenGL 3.3) for
real-time rendering.

Key notes:
  * No pixel readback  — renders directly to the pygame window (display.flip).
  * Shadow VAOs pre-built per shape type — no per-frame GPU allocations.
  * Smaller shadow map (512²) tuned for software GL (Mesa llvmpipe).
  * Capsule rendered as a scaled sphere (visual approximation).
  * HUD rendered via pygame font → GL texture quad.
  * Vertex layout: [px, py, pz,  nx, ny, nz,  u, v]  — 8 floats (matches
    forge3d v0.2 renderer).
"""

from __future__ import annotations

import math
from typing import Any

import moderngl
import numpy as np
import pygame

from forge3d.render.realtime.meshes import grid_lines, unit_box, unit_sphere
from forge3d.render.realtime.shaders import (
    FLAT_FRAG,
    FLAT_VERT,
    MAIN_FRAG,
    MAIN_VERT,
    SHADOW_FRAG,
    SHADOW_VERT,
)
from forge3d.render.snapshot import BUILTIN_MATERIALS, SceneSnapshot

# ── GLSL for 2-D HUD overlay ──────────────────────────────────────────────────

_HUD_VERT = """
#version 330 core
uniform vec2 u_screen;          // (width, height) in pixels
in vec2 in_pos;                 // pixel-space top-left origin
in vec2 in_uv;
out vec2 v_uv;
void main() {
    vec2 ndc = (in_pos / u_screen) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
}
"""

_HUD_FRAG = """
#version 330 core
uniform sampler2D u_tex;
in vec2 v_uv;
out vec4 frag_color;
void main() {
    vec4 c = texture(u_tex, v_uv);
    if (c.a < 0.02) discard;
    frag_color = c;
}
"""

# 1×1 white pixel for dummy albedo texture (no colour-texture in game mode)
_WHITE_PIXEL = np.array([255, 255, 255], dtype=np.uint8).tobytes()


# ── Matrix helpers ─────────────────────────────────────────────────────────────


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
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
    dist = np.linalg.norm(fwd)
    fwd = fwd / (dist + 1e-12)
    right = np.cross(fwd, up)
    rn = np.linalg.norm(right)
    right = right / (rn + 1e-12)
    u = np.cross(right, fwd)
    M = np.eye(4, dtype=np.float32)
    M[0, :3] = right
    M[0, 3] = -right.dot(eye)
    M[1, :3] = u
    M[1, 3] = -u.dot(eye)
    M[2, :3] = -fwd
    M[2, 3] = fwd.dot(eye)
    return M


def _mat_bytes(M: np.ndarray) -> bytes:
    return M.T.astype(np.float32).tobytes()


# ── WindowRenderer ─────────────────────────────────────────────────────────────


class WindowRenderer:
    """pygame + moderngl real-time PBR renderer.

    Usage::

        r = WindowRenderer(1024, 768, "My Game")
        r.init()
        while running:
            snap = world.snapshot()
            r.render(snap, cam_eye, cam_target)
            r.render_hud("Score: 42  Time: 30s", game_over=False)
            pygame.display.flip()  # called inside render()
        r.close()
    """

    SHADOW_SIZE = 512

    def __init__(self, width: int = 1024, height: int = 768, title: str = "Forge3D") -> None:
        self.width = width
        self.height = height
        self.title = title
        self._ctx: Any = None
        self._font_sm: Any = None
        self._font_lg: Any = None
        self._hud_prog: Any = None
        self._vaos: dict[str, Any] = {}
        self._grid_vao: Any = None
        self._grid_n: int = 0
        self._shadow_fbo: Any = None
        self._shadow_tex: Any = None
        self._shadow_prog: Any = None
        self._main_prog: Any = None
        self._flat_prog: Any = None
        self._white_tex: Any = None
        # HUD texture cache: avoid GPU allocations every frame
        self._hud_cache: dict[str, Any] = {}  # text → (tex, vbo, vao, tw, th, x0, y0)

    # ── Initialisation ─────────────────────────────────────────────────────────

    def init(self) -> None:
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode(
            (self.width, self.height),
            pygame.OPENGL | pygame.DOUBLEBUF,
        )
        pygame.display.set_caption(self.title)
        self._ctx = moderngl.create_context()
        self._init_gl()

    def _init_gl(self) -> None:
        ctx = self._ctx

        # Shader programs (PBR shaders from forge3d v0.2)
        self._shadow_prog = ctx.program(vertex_shader=SHADOW_VERT, fragment_shader=SHADOW_FRAG)
        self._main_prog = ctx.program(vertex_shader=MAIN_VERT, fragment_shader=MAIN_FRAG)
        self._flat_prog = ctx.program(vertex_shader=FLAT_VERT, fragment_shader=FLAT_FRAG)
        self._hud_prog = ctx.program(vertex_shader=_HUD_VERT, fragment_shader=_HUD_FRAG)

        # Shadow FBO (offscreen depth map)
        self._shadow_tex = ctx.depth_texture((self.SHADOW_SIZE, self.SHADOW_SIZE))
        self._shadow_fbo = ctx.framebuffer(depth_attachment=self._shadow_tex)

        # Dummy 1×1 white texture bound to albedo unit so the PBR shader
        # does not sample undefined memory when u_has_texture == 0.
        self._white_tex = ctx.texture((1, 1), 3, _WHITE_PIXEL)

        # Pre-build solid + shadow VAOs per primitive.
        # Vertex layout: 8 floats [pos.xyz, normal.xyz, u, v] (forge3d v0.2).
        for key, mesh_fn in [("box", unit_box), ("sphere", unit_sphere)]:
            verts, idx = mesh_fn()          # verts: (N, 8) float32
            vbo_main = ctx.buffer(verts.tobytes())
            ibo = ctx.buffer(idx.tobytes())

            # Shadow VAO: position-only (first 3 floats of each 8-float vertex)
            pos_only = np.ascontiguousarray(verts.reshape(-1, 8)[:, :3])
            vbo_shadow = ctx.buffer(pos_only.tobytes())

            self._vaos[key] = (
                ctx.vertex_array(
                    self._main_prog,
                    [(vbo_main, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                    index_buffer=ibo,
                ),
                len(idx),
            )
            self._vaos[f"{key}_shadow"] = (
                ctx.vertex_array(
                    self._shadow_prog,
                    [(vbo_shadow, "3f", "in_position")],
                    index_buffer=ibo,
                ),
                len(idx),
            )

        # Grid
        grid_v = grid_lines(half_size=20.0, step=1.0)
        gvbo = ctx.buffer(grid_v.tobytes())
        self._grid_vao = ctx.vertex_array(self._flat_prog, [(gvbo, "3f", "in_position")])
        self._grid_n = len(grid_v)

        # HUD font
        self._font_sm = pygame.font.SysFont("monospace", 20, bold=True)
        self._font_lg = pygame.font.SysFont("monospace", 48, bold=True)

    # ── Shape helpers ──────────────────────────────────────────────────────────

    def _body_scale(self, body: Any) -> np.ndarray:
        st, sp = body.shape_type, body.shape_params
        if st == "box":
            he = sp["half_extents"]
            return np.array([he[0] * 2, he[1] * 2, he[2] * 2], dtype=np.float32)
        if st == "sphere":
            r = float(sp["radius"])
            return np.array([r, r, r], dtype=np.float32)
        if st == "capsule":
            r = float(sp["radius"])
            hl = float(sp["half_length"])
            # Visual approximation: stretch sphere to cover capsule extent
            return np.array([r, r, hl + r], dtype=np.float32)
        return np.ones(3, dtype=np.float32)

    def _vao_key(self, body: Any) -> str:
        # capsule rendered as stretched sphere (visual approx)
        return "sphere" if body.shape_type in ("sphere", "capsule") else "box"

    def _model_matrix(self, body: Any, scale: np.ndarray) -> np.ndarray:
        M = np.zeros((4, 4), dtype=np.float32)
        R33 = body.transform.rotation.astype(np.float32)
        M[:3, :3] = R33 * scale
        M[:3, 3] = body.transform.position.astype(np.float32)
        M[3, 3] = 1.0
        return M

    # ── Render ─────────────────────────────────────────────────────────────────

    def render(
        self,
        snapshot: SceneSnapshot,
        cam_eye: np.ndarray,
        cam_target: np.ndarray,
        *,
        fov: float = 50.0,
    ) -> None:
        """Render one frame to the pygame window.

        Does NOT call pygame.display.flip() — the caller must do so after
        any HUD overlays via render_hud().
        """
        ctx = self._ctx
        W, H = self.width, self.height

        up = np.array([0.0, 0.0, 1.0])
        fwd = cam_target - cam_eye
        if abs(fwd[2]) / (np.linalg.norm(fwd) + 1e-12) > 0.98:
            up = np.array([0.0, 1.0, 0.0])

        V = _look_at(cam_eye, cam_target, up)
        P = _perspective(fov, W / H, 0.05, 500.0)

        # Directional light
        ld = np.array([-0.5, -0.7, -0.8], dtype=float)
        ld /= np.linalg.norm(ld)
        light_eye = -60.0 * ld
        up_l = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(ld, up_l)) > 0.95:
            up_l = np.array([0.0, 1.0, 0.0])
        LV = _look_at(light_eye, np.zeros(3), up_l)
        LP = _ortho(-30, 30, -30, 30, 0.1, 200.0)
        light_VP = LP @ LV

        # ── Shadow pass ────────────────────────────────────────────────────────
        self._shadow_fbo.use()
        ctx.viewport = (0, 0, self.SHADOW_SIZE, self.SHADOW_SIZE)
        self._shadow_fbo.clear(depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        for body in snapshot.bodies:
            sk = self._vao_key(body) + "_shadow"
            if sk not in self._vaos:
                continue
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale)
            light_MVP = (light_VP @ M).astype(np.float32)
            svao, sn = self._vaos[sk]
            try:
                self._shadow_prog["u_light_MVP"].write(_mat_bytes(light_MVP))
            except KeyError:
                pass
            svao.render(mode=ctx.TRIANGLES, vertices=sn)

        # ── Main PBR pass (to screen) ──────────────────────────────────────────
        ctx.screen.use()
        ctx.viewport = (0, 0, W, H)
        ctx.screen.clear(red=0.05, green=0.07, blue=0.12, depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        # Shadow map → texture unit 0; dummy albedo → texture unit 1
        self._shadow_tex.use(location=0)
        self._white_tex.use(location=1)

        prog = self._main_prog
        ambient = np.array([0.10, 0.10, 0.14], dtype=np.float32)
        light_to = (-ld).astype(np.float32)
        try:
            prog["u_shadow_map"] = 0
            prog["u_albedo_map"] = 1
            prog["u_light_dir"].write(light_to.tobytes())
            prog["u_light_color"].write(
                np.array([1.0, 0.95, 0.85], dtype=np.float32).tobytes()
            )
            prog["u_ambient_color"].write(ambient.tobytes())
            prog["u_eye"].write(cam_eye.astype(np.float32).tobytes())
        except KeyError:
            pass

        mat_lookup = {**BUILTIN_MATERIALS, **snapshot.materials}

        for body in snapshot.bodies:
            vk = self._vao_key(body)
            if vk not in self._vaos:
                continue
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale)
            MVP = (P @ V @ M).astype(np.float32)
            NM = (body.transform.rotation.astype(np.float32) / (scale + 1e-12)).astype(
                np.float32
            )
            light_M = (light_VP @ M).astype(np.float32)
            mat = mat_lookup.get(body.material_id) or mat_lookup.get("default")
            color = np.array(
                mat.color if mat else (0.75, 0.75, 0.75), dtype=np.float32
            )
            roughness = float(mat.roughness) if mat else 0.5
            metallic = float(mat.metallic) if mat else 0.0
            try:
                prog["u_MVP"].write(_mat_bytes(MVP))
                prog["u_M"].write(_mat_bytes(M.astype(np.float32)))
                prog["u_NM"].write(NM.T.tobytes())
                prog["u_light_MVP"].write(_mat_bytes(light_M))
                prog["u_mat_color"].write(color.tobytes())
                prog["u_roughness"].value = roughness
                prog["u_metallic"].value = metallic
                prog["u_has_texture"].value = 0   # no per-body textures in game mode
            except KeyError:
                pass
            vao, n_idx = self._vaos[vk]
            vao.render(mode=ctx.TRIANGLES, vertices=n_idx)

        # Grid (no depth test so it's always visible)
        VP = (P @ V).astype(np.float32)
        ctx.disable(ctx.DEPTH_TEST)
        try:
            self._flat_prog["u_VP"].write(_mat_bytes(VP))
            self._flat_prog["u_color"].write(
                np.array([0.20, 0.26, 0.20, 0.4], dtype=np.float32).tobytes()
            )
        except KeyError:
            pass
        self._grid_vao.render(mode=ctx.LINES, vertices=self._grid_n)
        ctx.enable(ctx.DEPTH_TEST)

    def _make_hud_entry(self, text: str, font: Any, cx: int, cy: int, centered: bool) -> dict:
        """Build GPU resources for one HUD text line and cache them."""
        txt_surf = font.render(text, True, (255, 255, 255))
        pad = 6
        tw = txt_surf.get_size()[0] + pad * 2
        th = txt_surf.get_size()[1] + pad * 2
        bg = pygame.Surface((tw, th), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        bg.blit(txt_surf, (pad, pad))
        raw = pygame.image.tostring(bg, "RGBA", False)
        tex = self._ctx.texture((tw, th), 4, raw)
        tex.filter = moderngl.NEAREST, moderngl.NEAREST

        x0 = cx - tw // 2 if centered else cx
        y0 = cy - th // 2 if centered else cy
        x1, y1 = x0 + tw, y0 + th
        verts = np.array(
            [
                [x0, y0, 0.0, 0.0],
                [x1, y0, 1.0, 0.0],
                [x0, y1, 0.0, 1.0],
                [x1, y0, 1.0, 0.0],
                [x1, y1, 1.0, 1.0],
                [x0, y1, 0.0, 1.0],
            ],
            dtype=np.float32,
        )
        vbo = self._ctx.buffer(verts.tobytes())
        vao = self._ctx.vertex_array(self._hud_prog, [(vbo, "2f 2f", "in_pos", "in_uv")])
        return {"tex": tex, "vbo": vbo, "vao": vao}

    def _release_hud_cache(self) -> None:
        for entry in self._hud_cache.values():
            entry["vao"].release()
            entry["vbo"].release()
            entry["tex"].release()
        self._hud_cache.clear()

    def render_hud(self, hud_text: str, game_over: bool = False) -> None:
        """Render 2-D text overlay.  GPU resources are cached per unique text."""
        ctx = self._ctx
        W, H = self.width, self.height

        lines: list[tuple[str, Any, int, int, bool]] = []
        if game_over:
            lines.append(("GAME OVER!", self._font_lg, W // 2, H // 2 - 40, True))
            lines.append((hud_text, self._font_sm, W // 2, H // 2 + 30, True))
            lines.append(
                (
                    "Press R to restart  |  ESC to quit",
                    self._font_sm,
                    W // 2,
                    H // 2 + 60,
                    True,
                )
            )
        else:
            lines.append((hud_text, self._font_sm, 10, 10, False))

        ctx.disable(ctx.DEPTH_TEST)
        ctx.enable(ctx.BLEND)
        ctx.blend_func = ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA

        screen_bytes = np.array([W, H], dtype=np.float32).tobytes()
        needed_keys: set[str] = set()

        for text, font, cx, cy, centered in lines:
            key = f"{text}|{id(font)}|{cx},{cy}"
            needed_keys.add(key)
            if key not in self._hud_cache:
                self._hud_cache[key] = self._make_hud_entry(text, font, cx, cy, centered)
            entry = self._hud_cache[key]
            entry["tex"].use(location=0)
            try:
                self._hud_prog["u_tex"] = 0
                self._hud_prog["u_screen"].write(screen_bytes)
            except KeyError:
                pass
            entry["vao"].render()

        # Evict stale entries
        stale = [k for k in self._hud_cache if k not in needed_keys]
        for k in stale:
            self._hud_cache[k]["vao"].release()
            self._hud_cache[k]["vbo"].release()
            self._hud_cache[k]["tex"].release()
            del self._hud_cache[k]

        ctx.disable(ctx.BLEND)
        ctx.enable(ctx.DEPTH_TEST)

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._ctx is not None:
            self._release_hud_cache()
            if self._grid_vao is not None:
                self._grid_vao.release()
            for val in self._vaos.values():
                if isinstance(val, tuple):
                    val[0].release()
            if self._white_tex is not None:
                self._white_tex.release()
            self._vaos.clear()
            self._ctx.release()
            self._ctx = None
        pygame.quit()
