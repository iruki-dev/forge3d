"""Windowed glfw + moderngl renderer.

Used automatically by :class:`~forge3d.viewer.Viewer` when a window title
is provided::

    viewer = f3d.Viewer(world, width=1280, height=720, title="My Game")

Key design choices
------------------
* **Deferred flip** — ``render()`` flips the *previous* frame at its start,
  so ``draw_text()`` calls that follow ``render()`` appear on the same frame.
* **Cached HUD text** — ``draw_text()`` keys GL resources on
  ``(text, x, y, size, color, anchor)``.  Unchanged elements reuse the cached
  texture/VAO — zero texture upload.  Changed text creates a new texture once.
* **Camera-relative shadow** — the shadow frustum is centred on the camera
  target so shadows follow the viewer across a large world.
* **Terrain excluded from shadow pass** — saves ~18 000 triangle renders /
  frame with negligible visual difference on flat-lit terrain.
"""

from __future__ import annotations

import contextlib
import math
from typing import Any

import glfw
import moderngl
import numpy as np

from forge3d.input import EMPTY_INPUT, Input, InputBuilder
from forge3d.render.realtime.meshes import (
    grid_lines,
    heightfield_mesh,
    mesh_from_data,
    unit_box,
    unit_sphere,
)
from forge3d.render.realtime.renderer import _col_major
from forge3d.render.realtime.shaders import (
    FLAT_FRAG,
    FLAT_VERT,
    MAIN_FRAG,
    MAIN_VERT,
    SHADOW_FRAG,
    SHADOW_VERT,
)
from forge3d.render.snapshot import BUILTIN_MATERIALS, CameraSnapshot

# HUD overlay shaders — 2-D textured quad in pixel space
_HUD_V = """
#version 330 core
uniform vec2 u_screen;
in vec2 in_pos; in vec2 in_uv; out vec2 v_uv;
void main() {
    vec2 ndc = (in_pos / u_screen) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
}
"""
_HUD_F = """
#version 330 core
uniform sampler2D u_tex;
in vec2 v_uv; out vec4 fc;
void main() {
    vec4 c = texture(u_tex, v_uv);
    if (c.a < 0.02) discard;
    fc = c;
}
"""

_WHITE_PIXEL = np.array([255, 255, 255], dtype=np.uint8).tobytes()

# Shadow settings
_SHADOW_SIZE = 1024  # shadow map resolution (raised from 512 for quality)
_SHADOW_HALF = 150.0  # half-extent of shadow orthographic frustum (m)
_SHADOW_DEPTH = 500.0  # far plane of shadow frustum

# Sky colour — daytime blue (can be overridden via constructor)
_SKY_DEFAULT = (0.42, 0.62, 0.88)

# HUD flat-color shaders (no UV — for filled rects, bars, overlays)
_HUD_FLAT_V = """
#version 330 core
uniform vec2 u_screen;
in vec2 in_pos;
void main() {
    vec2 ndc = (in_pos / u_screen) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
}
"""
_HUD_FLAT_F = """
#version 330 core
uniform vec4 u_rect_color;
out vec4 fc;
void main() { fc = u_rect_color; }
"""

# ── GLFW → forge3d key name mapping ──────────────────────────────────────────
# Letters / digits: glfw.get_key_name() returns a lowercase string directly.
# Special keys need a manual lookup.
_GLFW_SPECIAL: dict[int, str] = {
    glfw.KEY_SPACE: "space",
    glfw.KEY_ESCAPE: "escape",
    glfw.KEY_ENTER: "enter",
    glfw.KEY_KP_ENTER: "enter",
    glfw.KEY_BACKSPACE: "backspace",
    glfw.KEY_DELETE: "delete",
    glfw.KEY_TAB: "tab",
    glfw.KEY_INSERT: "insert",
    glfw.KEY_UP: "up",
    glfw.KEY_DOWN: "down",
    glfw.KEY_LEFT: "left",
    glfw.KEY_RIGHT: "right",
    glfw.KEY_PAGE_UP: "pageup",
    glfw.KEY_PAGE_DOWN: "pagedown",
    glfw.KEY_HOME: "home",
    glfw.KEY_END: "end",
    glfw.KEY_LEFT_SHIFT: "shift",
    glfw.KEY_RIGHT_SHIFT: "shift",
    glfw.KEY_LEFT_CONTROL: "ctrl",
    glfw.KEY_RIGHT_CONTROL: "ctrl",
    glfw.KEY_LEFT_ALT: "alt",
    glfw.KEY_RIGHT_ALT: "alt",
    glfw.KEY_LEFT_SUPER: "super",
    glfw.KEY_RIGHT_SUPER: "super",
    glfw.KEY_F1: "f1",
    glfw.KEY_F2: "f2",
    glfw.KEY_F3: "f3",
    glfw.KEY_F4: "f4",
    glfw.KEY_F5: "f5",
    glfw.KEY_F6: "f6",
    glfw.KEY_F7: "f7",
    glfw.KEY_F8: "f8",
    glfw.KEY_F9: "f9",
    glfw.KEY_F10: "f10",
    glfw.KEY_F11: "f11",
    glfw.KEY_F12: "f12",
    glfw.KEY_KP_0: "kp0",
    glfw.KEY_KP_1: "kp1",
    glfw.KEY_KP_2: "kp2",
    glfw.KEY_KP_3: "kp3",
    glfw.KEY_KP_4: "kp4",
    glfw.KEY_KP_5: "kp5",
    glfw.KEY_KP_6: "kp6",
    glfw.KEY_KP_7: "kp7",
    glfw.KEY_KP_8: "kp8",
    glfw.KEY_KP_9: "kp9",
    glfw.KEY_KP_ADD: "kp_plus",
    glfw.KEY_KP_SUBTRACT: "kp_minus",
    glfw.KEY_KP_MULTIPLY: "kp_multiply",
    glfw.KEY_KP_DIVIDE: "kp_divide",
}


def _glfw_key_name(key: int, scancode: int) -> str | None:
    """Return a forge3d key name string for a GLFW key code."""
    special = _GLFW_SPECIAL.get(key)
    if special is not None:
        return special
    name = glfw.get_key_name(key, scancode)
    return name.lower() if name else None


# ── Pillow font helper ────────────────────────────────────────────────────────

_FONT_CACHE: dict[int, Any] = {}  # size → PIL font object
_FONT_PATH: str | None = None


def _pil_font(size: int) -> Any:
    """Return a cached Pillow font at the given pixel size."""
    global _FONT_PATH
    if size not in _FONT_CACHE:
        if _FONT_PATH is None:
            import os

            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
                "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
            ]
            _FONT_PATH = next((p for p in candidates if os.path.exists(p)), "")
        from PIL import ImageFont

        if _FONT_PATH:
            _FONT_CACHE[size] = ImageFont.truetype(_FONT_PATH, size)
        else:
            _FONT_CACHE[size] = ImageFont.load_default(size=size)
    return _FONT_CACHE[size]


def _render_text_rgba(
    text: str,
    size: int,
    color: tuple,
    bg_alpha: float,
    pad: int = 5,
) -> tuple[bytes, int, int]:
    """Render *text* into an RGBA byte buffer using Pillow.

    Returns ``(raw_bytes, width, height)``.
    """
    from PIL import Image, ImageDraw

    font = _pil_font(size)
    # Measure text bounding box
    dummy = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0] + pad * 2
    th = bbox[3] - bbox[1] + pad * 2

    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, tw - 1, th - 1], fill=(0, 0, 0, int(bg_alpha * 255)))
    r_int = tuple(max(0, min(255, int(c * 255))) for c in color)
    draw.text((pad - bbox[0], pad - bbox[1]), text, fill=r_int + (255,), font=font)
    return img.tobytes(), tw, th


# ── Matrix helpers ────────────────────────────────────────────────────────────


def _perspective(fov: float, asp: float, n: float, f: float) -> np.ndarray:
    t = 1.0 / math.tan(math.radians(fov) / 2.0)
    M = np.zeros((4, 4), np.float32)
    M[0, 0] = t / asp
    M[1, 1] = t
    M[2, 2] = -(f + n) / (f - n)
    M[2, 3] = -2.0 * f * n / (f - n)
    M[3, 2] = -1.0
    return M


def _ortho(lo: float, r: float, b: float, t: float, n: float, f: float) -> np.ndarray:
    M = np.zeros((4, 4), np.float32)
    M[0, 0] = 2.0 / (r - lo)
    M[0, 3] = -(r + lo) / (r - lo)
    M[1, 1] = 2.0 / (t - b)
    M[1, 3] = -(t + b) / (t - b)
    M[2, 2] = -2.0 / (f - n)
    M[2, 3] = -(f + n) / (f - n)
    M[3, 3] = 1.0
    return M


def _look_at(eye: np.ndarray, tgt: np.ndarray, up: np.ndarray) -> np.ndarray:
    fwd = tgt - eye
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


# ── WindowedRealtimeRenderer ──────────────────────────────────────────────────


class WindowedRealtimeRenderer:
    """glfw+moderngl windowed renderer for :class:`~forge3d.viewer.Viewer`.

    Do not instantiate directly — created automatically by
    ``Viewer(title=…)``.
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        fps: int = 60,
        shadow_resolution: int = 0,
        sky_color: tuple = _SKY_DEFAULT,
    ) -> None:
        self._width = width
        self._height = height
        self._title = title
        self._fps = fps
        self._shadow_resolution = shadow_resolution if shadow_resolution > 0 else _SHADOW_SIZE
        self._sky_color = sky_color

        self._ctx: Any = None
        self._window: Any = None  # glfw window handle
        self._shadow_prog: Any = None
        self._main_prog: Any = None
        self._flat_prog: Any = None
        self._hud_prog: Any = None
        self._hud_flat_prog: Any = None
        self._shadow_fbo: Any = None
        self._shadow_tex: Any = None
        self._white_tex: Any = None
        self._vaos: dict[str, Any] = {}
        self._terrain_vaos: dict[Any, tuple] = {}
        self._mesh_vaos: dict[int, tuple] = {}   # mesh_id → (solid_t, shadow_t)
        self._grid_vao: Any = None
        self._grid_n: int = 0
        self._rect_vbo: Any = None
        self._rect_vao: Any = None

        self._cam: CameraSnapshot | None = None

        # Input
        self._inp_builder = InputBuilder()
        self._current_inp: Input = EMPTY_INPUT

        # Window state
        self._is_open = True
        self._dt = 1.0 / fps
        self._prev_time = 0.0
        self._pending_flip = False

        # Cursor capture (FPS mode)
        self._cursor_captured = False

        # Body names to exclude from rendering (e.g. local player body in FPS)
        self._excluded_names: set[str] = set()

        # HUD text cache: key → {"tex", "vbo", "vao", "alive"}
        self._hud_cache: dict[tuple, dict[str, Any]] = {}

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _ensure_init(self) -> None:
        if self._ctx is not None:
            return

        if not glfw.init():
            raise RuntimeError("glfw.init() failed")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.DOUBLEBUFFER, glfw.TRUE)

        self._window = glfw.create_window(self._width, self._height, self._title, None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("glfw.create_window() failed")

        glfw.make_context_current(self._window)
        glfw.swap_interval(0)  # uncapped; we throttle via frame timing

        # Register input callbacks
        glfw.set_key_callback(self._window, self._on_key)
        glfw.set_cursor_pos_callback(self._window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self._window, self._on_mouse_button)
        glfw.set_scroll_callback(self._window, self._on_scroll)
        glfw.set_window_close_callback(self._window, self._on_close)

        self._ctx = moderngl.create_context()
        self._prev_time = glfw.get_time()
        self._init_gl()

    # ── Cursor capture (FPS) ───────────────────────────────────────────────────

    def set_cursor_captured(self, captured: bool) -> None:
        """Lock (hide+raw) or release the OS cursor.

        When captured, ESC releases the cursor instead of closing the window.
        Automatically discards the first mouse-move event after the warp so the
        view doesn't lurch on capture/release.
        """
        if self._window is None:
            return
        if captured:
            glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        else:
            glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_NORMAL)
        self._cursor_captured = captured
        # Discard the delta spike caused by the cursor warp
        self._inp_builder.reset_mouse_delta()

    def set_excluded_names(self, names: set[str]) -> None:
        """Bodies whose names are in *names* will not be rendered (FPS self-exclusion)."""
        self._excluded_names = names

    def _init_gl(self) -> None:
        ctx = self._ctx
        self._shadow_prog = ctx.program(vertex_shader=SHADOW_VERT, fragment_shader=SHADOW_FRAG)
        self._main_prog = ctx.program(vertex_shader=MAIN_VERT, fragment_shader=MAIN_FRAG)
        self._flat_prog = ctx.program(vertex_shader=FLAT_VERT, fragment_shader=FLAT_FRAG)
        self._hud_prog = ctx.program(vertex_shader=_HUD_V, fragment_shader=_HUD_F)

        sz = self._shadow_resolution
        self._shadow_tex = ctx.depth_texture((sz, sz))
        self._shadow_fbo = ctx.framebuffer(depth_attachment=self._shadow_tex)
        self._white_tex = ctx.texture((1, 1), 3, _WHITE_PIXEL)

        self._hud_flat_prog = ctx.program(vertex_shader=_HUD_FLAT_V, fragment_shader=_HUD_FLAT_F)
        # Dynamic rect VBO: 6 vertices × 2 floats = 48 bytes
        self._rect_vbo = ctx.buffer(reserve=48)
        self._rect_vao = ctx.vertex_array(
            self._hud_flat_prog, [(self._rect_vbo, "2f", "in_pos")]
        )

        for key, mesh_fn in [("box", unit_box), ("sphere", unit_sphere)]:
            verts, idx = mesh_fn()
            vbo_main = ctx.buffer(verts.tobytes())
            ibo = ctx.buffer(idx.tobytes())
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
                    self._shadow_prog, [(vbo_shadow, "3f", "in_position")], index_buffer=ibo
                ),
                len(idx),
            )

        grid_v = grid_lines(half_size=30.0, step=5.0)
        gvbo = ctx.buffer(grid_v.tobytes())
        self._grid_vao = ctx.vertex_array(self._flat_prog, [(gvbo, "3f", "in_position")])
        self._grid_n = len(grid_v)

    # ── GLFW event callbacks ───────────────────────────────────────────────────

    def _on_key(self, window: Any, key: int, scancode: int, action: int, mods: int) -> None:
        name = _glfw_key_name(key, scancode)
        if name is None:
            return
        if action == glfw.PRESS or action == glfw.REPEAT:
            self._inp_builder.on_key_down(name)
        elif action == glfw.RELEASE:
            self._inp_builder.on_key_up(name)

    def _on_cursor_pos(self, window: Any, x: float, y: float) -> None:
        self._inp_builder.on_mouse_move(x, y)

    def _on_mouse_button(self, window: Any, button: int, action: int, mods: int) -> None:
        # GLFW: 0=left, 1=right, 2=middle — matches forge3d convention
        if action == glfw.PRESS:
            self._inp_builder.on_mouse_down(button)
        elif action == glfw.RELEASE:
            self._inp_builder.on_mouse_up(button)

    def _on_scroll(self, window: Any, x_off: float, y_off: float) -> None:
        self._inp_builder.on_scroll(float(y_off))

    def _on_close(self, window: Any) -> None:
        self._is_open = False

    # ── Terrain VAO helpers ────────────────────────────────────────────────────

    def _terrain_main_vao(self, terrain: Any) -> tuple:
        key = (id(terrain.heights), "main")
        if key not in self._terrain_vaos:
            verts, idx = heightfield_mesh(terrain.heights, terrain.cell_size, terrain.origin)
            vbo = self._ctx.buffer(verts.tobytes())
            ibo = self._ctx.buffer(idx.tobytes())
            vao = self._ctx.vertex_array(
                self._main_prog,
                [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                index_buffer=ibo,
            )
            self._terrain_vaos[key] = (vao, len(idx))
        return self._terrain_vaos[key]

    # ── Mesh VAO helpers ───────────────────────────────────────────────────────

    def _get_mesh_vaos(self, mesh_data: Any) -> tuple[tuple, tuple]:
        """Return (solid_vao_tuple, shadow_vao_tuple) for a custom mesh, cached."""
        mid = mesh_data.mesh_id
        if mid not in self._mesh_vaos:
            verts, idx = mesh_from_data(mesh_data)
            ctx = self._ctx
            vbo_main   = ctx.buffer(verts.tobytes())
            ibo        = ctx.buffer(idx.tobytes())
            pos_only   = np.ascontiguousarray(verts.reshape(-1, 8)[:, :3])
            vbo_shadow = ctx.buffer(pos_only.tobytes())
            main_vao = ctx.vertex_array(
                self._main_prog,
                [(vbo_main, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                index_buffer=ibo,
            )
            shadow_vao = ctx.vertex_array(
                self._shadow_prog, [(vbo_shadow, "3f", "in_position")], index_buffer=ibo
            )
            n = len(idx)
            self._mesh_vaos[mid] = ((main_vao, n), (shadow_vao, n))
        return self._mesh_vaos[mid]

    # ── Shape helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _vao_key(body: Any) -> str:
        return "sphere" if body.shape_type in ("sphere", "capsule") else "box"

    @staticmethod
    def _body_scale(body: Any) -> np.ndarray:
        st, sp = body.shape_type, body.shape_params
        if st == "box":
            he = sp["half_extents"]
            return np.array([he[0] * 2, he[1] * 2, he[2] * 2], np.float32)
        if st == "sphere":
            r = float(sp["radius"])
            return np.array([r, r, r], np.float32)
        if st == "capsule":
            r = float(sp["radius"])
            hl = float(sp["half_length"])
            return np.array([r, r, hl + r], np.float32)
        return np.ones(3, np.float32)

    @staticmethod
    def _model_matrix(body: Any, scale: np.ndarray) -> np.ndarray:
        M = np.zeros((4, 4), np.float32)
        R33 = body.transform.rotation.astype(np.float32)
        M[:3, :3] = R33 * scale
        M[:3, 3] = body.transform.position.astype(np.float32)
        M[3, 3] = 1.0
        return M

    # ── Camera ─────────────────────────────────────────────────────────────────

    def set_camera(self, cam: CameraSnapshot) -> None:
        self._cam = cam

    # ── Main render ────────────────────────────────────────────────────────────

    def render(self, snapshot: Any) -> None:
        """Process events, flip previous frame, render new 3-D frame.

        ``draw_text()`` calls after this paint on the same frame; the frame
        is flipped at the start of the *next* ``render()`` call.
        """
        self._ensure_init()

        # Flip the previous frame (so draw_text() in the last iteration
        # was included) and reset per-frame input state
        if self._pending_flip:
            glfw.swap_buffers(self._window)
            self._pending_flip = False
            self._inp_builder.end_frame()

        # Poll OS events — callbacks fire synchronously here
        glfw.poll_events()

        # Check ESC: release cursor when captured, close window otherwise
        if glfw.get_key(self._window, glfw.KEY_ESCAPE) == glfw.PRESS:
            if self._cursor_captured:
                self.set_cursor_captured(False)
            else:
                self._is_open = False
        if glfw.window_should_close(self._window):
            self._is_open = False

        self._current_inp = self._inp_builder.build()

        # Measure real frame time, cap to prevent spiral-of-death
        now = glfw.get_time()
        self._dt = min(now - self._prev_time, 0.05)
        self._prev_time = now

        # Evict stale HUD cache entries
        self._evict_hud_cache()

        if not self._is_open:
            return

        cam = self._cam
        if cam is None:
            return

        self._render_scene(snapshot, cam)
        self._pending_flip = True

    def _render_scene(self, snapshot: Any, cam: CameraSnapshot) -> None:
        ctx = self._ctx
        W, H = self._width, self._height
        I4 = np.eye(4, dtype=np.float32)

        up = np.array([0.0, 0.0, 1.0])
        fwd = cam.target - cam.position
        if abs(fwd[2]) / (np.linalg.norm(fwd) + 1e-12) > 0.98:
            up = np.array([0.0, 1.0, 0.0])

        V = _look_at(cam.position, cam.target, up)
        P = _perspective(cam.fov_deg, W / H, 0.1, 1200.0)

        ld = np.array([-0.45, -0.60, -0.80])
        ld /= np.linalg.norm(ld)
        sc = cam.target.copy()
        sc[2] = 0.0
        lp = sc - ld * 250.0
        up_l = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(ld, up_l)) > 0.95:
            up_l = np.array([0.0, 1.0, 0.0])
        LV = _look_at(lp, sc, up_l)
        LP = _ortho(-_SHADOW_HALF, _SHADOW_HALF, -_SHADOW_HALF, _SHADOW_HALF, 0.5, _SHADOW_DEPTH)
        light_VP = LP @ LV

        # Shadow pass
        self._shadow_fbo.use()
        ctx.viewport = (0, 0, _SHADOW_SIZE, _SHADOW_SIZE)
        self._shadow_fbo.clear(depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        for body in snapshot.bodies:
            if body.name in self._excluded_names:
                continue
            # ── Custom mesh shape ──────────────────────────────────────────────
            if body.shape_type == "mesh":
                mesh_data = body.shape_params.get("mesh_data")
                if mesh_data is None:
                    continue
                _, shadow_t = self._get_mesh_vaos(mesh_data)
                svao, sn = shadow_t
                M = self._model_matrix(body, np.ones(3, np.float32))
                with contextlib.suppress(KeyError):
                    self._shadow_prog["u_light_MVP"].write(
                        _col_major((light_VP @ M).astype(np.float32))
                    )
                svao.render(mode=ctx.TRIANGLES, vertices=sn)
                continue
            # ── Primitive shapes ───────────────────────────────────────────────
            sk = self._vao_key(body) + "_shadow"
            if sk not in self._vaos:
                continue
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale)
            lMVP = (light_VP @ M).astype(np.float32)
            svao, sn = self._vaos[sk]
            with contextlib.suppress(KeyError):
                self._shadow_prog["u_light_MVP"].write(_col_major(lMVP))
            svao.render(mode=ctx.TRIANGLES, vertices=sn)

        # Main PBR pass
        ctx.screen.use()
        ctx.viewport = (0, 0, W, H)
        sky = self._sky_color
        ctx.screen.clear(red=sky[0], green=sky[1], blue=sky[2], depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"

        self._shadow_tex.use(location=0)
        self._white_tex.use(location=1)

        prog = self._main_prog
        light_to = (-ld).astype(np.float32)
        ambient = np.array([0.12, 0.14, 0.18], np.float32)
        try:
            prog["u_shadow_map"] = 0
            prog["u_albedo_map"] = 1
            prog["u_light_dir"].write(light_to.tobytes())
            prog["u_light_color"].write(np.array([1.0, 0.95, 0.86], np.float32).tobytes())
            prog["u_ambient_color"].write(ambient.tobytes())
            prog["u_eye"].write(cam.position.astype(np.float32).tobytes())
            prog["u_fog_density"].value = 0.0040
            prog["u_fog_color"].write(np.array(self._sky_color, np.float32).tobytes())
        except KeyError:
            pass

        mat_lookup = {**BUILTIN_MATERIALS, **snapshot.materials}

        for body in snapshot.bodies:
            if body.name in self._excluded_names:
                continue

            # ── Custom mesh shape ──────────────────────────────────────────────
            if body.shape_type == "mesh":
                mesh_data = body.shape_params.get("mesh_data")
                if mesh_data is None:
                    continue
                solid_t, _ = self._get_mesh_vaos(mesh_data)
                vao, n_idx = solid_t
                scale = np.ones(3, np.float32)
                M   = self._model_matrix(body, scale)
                MVP = (P @ V @ M).astype(np.float32)
                NM  = body.transform.rotation.astype(np.float32)
                lM  = (light_VP @ M).astype(np.float32)
                mat = mat_lookup.get(body.material_id) or mat_lookup.get("default")
                color = np.array(mat.color if mat else (0.75, 0.75, 0.75), np.float32)
                try:
                    prog["u_MVP"].write(_col_major(MVP))
                    prog["u_M"].write(_col_major(M))
                    prog["u_NM"].write(NM.T.tobytes())
                    prog["u_light_MVP"].write(_col_major(lM))
                    prog["u_mat_color"].write(color.tobytes())
                    prog["u_roughness"].value = float(mat.roughness) if mat else 0.5
                    prog["u_metallic"].value  = float(mat.metallic)  if mat else 0.0
                    prog["u_has_texture"].value = 0
                except KeyError:
                    pass
                vao.render(mode=ctx.TRIANGLES, vertices=n_idx)
                continue

            # ── Primitive shapes ───────────────────────────────────────────────
            vk = self._vao_key(body)
            if vk not in self._vaos:
                continue
            scale = self._body_scale(body)
            M = self._model_matrix(body, scale)
            MVP = (P @ V @ M).astype(np.float32)
            NM = body.transform.rotation.astype(np.float32) / (scale + 1e-12)
            lM = (light_VP @ M).astype(np.float32)
            mat = mat_lookup.get(body.material_id) or mat_lookup.get("default")
            color = np.array(mat.color if mat else (0.75, 0.75, 0.75), np.float32)
            try:
                prog["u_MVP"].write(_col_major(MVP))
                prog["u_M"].write(_col_major(M))
                prog["u_NM"].write(NM.T.tobytes())
                prog["u_light_MVP"].write(_col_major(lM))
                prog["u_mat_color"].write(color.tobytes())
                prog["u_roughness"].value = float(mat.roughness) if mat else 0.5
                prog["u_metallic"].value = float(mat.metallic) if mat else 0.0
                prog["u_has_texture"].value = 0
            except KeyError:
                pass
            vao, n_idx = self._vaos[vk]
            vao.render(mode=ctx.TRIANGLES, vertices=n_idx)

        # Terrain (main pass only)
        for terrain in getattr(snapshot, "terrains", []):
            tvao, tn = self._terrain_main_vao(terrain)
            mat = mat_lookup.get(terrain.material_id) or mat_lookup.get("ground")
            color = np.array(mat.color if mat else (0.3, 0.45, 0.2), np.float32)
            try:
                prog["u_MVP"].write(_col_major((P @ V @ I4).astype(np.float32)))
                prog["u_M"].write(_col_major(I4))
                prog["u_NM"].write(np.eye(3, dtype=np.float32).tobytes())
                prog["u_light_MVP"].write(_col_major((light_VP @ I4).astype(np.float32)))
                prog["u_mat_color"].write(color.tobytes())
                prog["u_roughness"].value = float(mat.roughness) if mat else 0.9
                prog["u_metallic"].value = 0.0
                prog["u_has_texture"].value = 0
            except KeyError:
                pass
            tvao.render(mode=ctx.TRIANGLES, vertices=tn)

        # Grid
        VP = (P @ V).astype(np.float32)
        ctx.disable(ctx.DEPTH_TEST)
        try:
            self._flat_prog["u_VP"].write(_col_major(VP))
            self._flat_prog["u_color"].write(
                np.array([0.15, 0.20, 0.15, 0.25], np.float32).tobytes()
            )
        except KeyError:
            pass
        self._grid_vao.render(mode=ctx.LINES, vertices=self._grid_n)
        ctx.enable(ctx.DEPTH_TEST)

    # ── HUD text (cached) ──────────────────────────────────────────────────────

    def draw_text(
        self,
        text: str,
        x: int = 10,
        y: int = 10,
        size: int = 20,
        color: tuple = (1.0, 1.0, 1.0),
        bg_alpha: float = 0.55,
        anchor: str = "topleft",
    ) -> None:
        """Render a HUD text overlay (Pillow-rendered, GPU-cached)."""
        if self._ctx is None:
            return
        key = (text, x, y, size, tuple(color), anchor)
        if key not in self._hud_cache:
            self._hud_cache[key] = self._build_hud_entry(text, x, y, size, color, bg_alpha, anchor)
        entry = self._hud_cache[key]
        entry["alive"] = True
        self._render_hud_entry(entry)

    def _build_hud_entry(
        self,
        text: str,
        x: int,
        y: int,
        size: int,
        color: tuple,
        bg_alpha: float,
        anchor: str,
    ) -> dict:
        raw, tw, th = _render_text_rgba(text, size, color, bg_alpha)

        tex = self._ctx.texture((tw, th), 4, raw)
        tex.filter = moderngl.NEAREST, moderngl.NEAREST

        if anchor == "center":
            x0, y0 = x - tw // 2, y - th // 2
        elif anchor == "topright":
            x0, y0 = x - tw, y
        else:
            x0, y0 = x, y
        x1, y1 = x0 + tw, y0 + th

        W, H = self._width, self._height
        verts = np.array(
            [
                [x0, y0, 0, 0],
                [x1, y0, 1, 0],
                [x0, y1, 0, 1],
                [x1, y0, 1, 0],
                [x1, y1, 1, 1],
                [x0, y1, 0, 1],
            ],
            np.float32,
        )
        vbo = self._ctx.buffer(verts.tobytes())
        vao = self._ctx.vertex_array(self._hud_prog, [(vbo, "2f 2f", "in_pos", "in_uv")])
        return {
            "tex": tex,
            "vbo": vbo,
            "vao": vao,
            "alive": False,
            "screen": np.array([W, H], np.float32),
        }

    def _render_hud_entry(self, entry: dict) -> None:
        ctx = self._ctx
        ctx.disable(ctx.DEPTH_TEST)
        ctx.enable(ctx.BLEND)
        ctx.blend_func = ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA
        entry["tex"].use(0)
        try:
            self._hud_prog["u_tex"] = 0
            self._hud_prog["u_screen"].write(entry["screen"].tobytes())
        except KeyError:
            pass
        entry["vao"].render()
        ctx.disable(ctx.BLEND)
        ctx.enable(ctx.DEPTH_TEST)

    def _evict_hud_cache(self) -> None:
        dead = [k for k, v in self._hud_cache.items() if not v["alive"]]
        for k in dead:
            e = self._hud_cache.pop(k)
            e["vao"].release()
            e["vbo"].release()
            e["tex"].release()
        for v in self._hud_cache.values():
            v["alive"] = False

    # ── Flat-color rect overlay ────────────────────────────────────────────────

    def draw_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple = (1.0, 1.0, 1.0),
        alpha: float = 0.8,
    ) -> None:
        """Draw a filled, flat-colored rectangle on the HUD.

        Coordinates are in pixels from the top-left corner.
        Useful for health bars, zone overlays, and minimap backgrounds.
        """
        if self._ctx is None or self._rect_vbo is None:
            return
        x0, y0, x1, y1 = float(x), float(y), float(x + w), float(y + h)
        verts = np.array(
            [x0, y0, x1, y0, x0, y1, x1, y0, x1, y1, x0, y1], dtype=np.float32
        )
        self._rect_vbo.write(verts.tobytes())

        ctx = self._ctx
        ctx.disable(ctx.DEPTH_TEST)
        ctx.enable(ctx.BLEND)
        ctx.blend_func = ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA
        try:
            self._hud_flat_prog["u_screen"].write(
                np.array([self._width, self._height], np.float32).tobytes()
            )
            self._hud_flat_prog["u_rect_color"].write(
                np.array([*color, alpha], np.float32).tobytes()
            )
        except KeyError:
            pass
        self._rect_vao.render()
        ctx.disable(ctx.BLEND)
        ctx.enable(ctx.DEPTH_TEST)

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def input(self) -> Input:
        return self._current_inp

    @property
    def dt(self) -> float:
        return self._dt

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._is_open = False
        if self._ctx is not None:
            self._evict_hud_cache()
            for v in self._vaos.values():
                if isinstance(v, tuple) and hasattr(v[0], "release"):
                    v[0].release()
            for v in self._terrain_vaos.values():
                if isinstance(v, tuple) and hasattr(v[0], "release"):
                    v[0].release()
            for solid_t, shadow_t in self._mesh_vaos.values():
                if hasattr(solid_t[0], "release"):
                    solid_t[0].release()
                if hasattr(shadow_t[0], "release"):
                    shadow_t[0].release()
            if self._grid_vao:
                self._grid_vao.release()
            if self._rect_vao:
                self._rect_vao.release()
            if self._rect_vbo:
                self._rect_vbo.release()
            if self._white_tex:
                self._white_tex.release()
            self._ctx.release()
            self._ctx = None
        if self._window is not None:
            glfw.destroy_window(self._window)
            self._window = None
            glfw.terminate()
