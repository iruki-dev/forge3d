"""demos/training_watch.py — RL 학습 실시간 시각화 + 기존 텍스트 모드 학습.

모드 1 (기본): 텍스트 터미널로 진행 표시, 구간마다 영상 저장
모드 2 (--live): pygame 창에서 로봇 팔 학습 모습을 실시간으로 관찰

필요 패키지: stable-baselines3  (pip install stable-baselines3)

사용법
------
    python demos/training_watch.py                       # 텍스트 모드, 200k 스텝
    python demos/training_watch.py --steps 50000         # 빠른 데모
    python demos/training_watch.py --live                # 실시간 뷰어 (권장 ✨)
    python demos/training_watch.py --live --steps 100000
    python demos/training_watch.py --use-existing        # 기존 모델 영상만 생성

실시간 뷰어 조작
--------------
    좌클릭 드래그 → 카메라 orbit (회전)
    우클릭 드래그 → 카메라 pan (이동)
    마우스 휠     → zoom (거리 조절)
    R             → 카메라 초기화
    SPACE         → 일시정지 / 재개
    ESC           → 학습 중단 + 종료
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
#  LiveViewer — pygame + moderngl orbit-camera viewer
# ══════════════════════════════════════════════════════════════════════════════

class LiveViewer:
    """실시간 로봇 학습 시각화 뷰어.

    SceneSnapshot을 받아 그림자맵 + Phong 셰이딩으로 렌더링합니다.
    마우스로 카메라를 자유롭게 조작할 수 있습니다.
    """

    SHADOW_SIZE = 512

    def __init__(self, width: int = 1280, height: int = 720,
                 title: str = "forge3d — 실시간 학습") -> None:
        import pygame
        import moderngl

        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
        pygame.display.set_caption(title)

        self.width  = width
        self.height = height
        self._ctx   = moderngl.create_context()
        self._pygame = pygame

        # ── Orbit camera ─────────────────────────────────────────────────────
        self._az    = 30.0                           # azimuth  (degrees)
        self._el    = 22.0                           # elevation (degrees)
        self._dist  = 2.2                            # distance from target
        self._target = np.array([0.0, 0.0, 0.35])   # look-at point

        # ── Mouse state ───────────────────────────────────────────────────────
        self._lmb   = False   # left-drag  → orbit
        self._rmb   = False   # right-drag → pan
        self._mpos  = (0, 0)

        # ── HUD font ──────────────────────────────────────────────────────────
        self._font_sm  = pygame.font.SysFont("monospace", 18, bold=True)

        # ── Paused flag ───────────────────────────────────────────────────────
        self.paused   = False
        self.should_stop = False

        self._init_gl()

    # ── GL initialisation ─────────────────────────────────────────────────────

    def _init_gl(self) -> None:
        from forge3d.render.realtime.meshes import grid_lines, unit_box, unit_sphere
        from forge3d.render.realtime.shaders import (
            FLAT_FRAG,
            FLAT_VERT,
            MAIN_FRAG,
            MAIN_VERT,
            SHADOW_FRAG,
            SHADOW_VERT,
        )
        import moderngl

        ctx = self._ctx

        self._shadow_prog = ctx.program(vertex_shader=SHADOW_VERT, fragment_shader=SHADOW_FRAG)
        self._main_prog = ctx.program(vertex_shader=MAIN_VERT, fragment_shader=MAIN_FRAG)
        self._flat_prog = ctx.program(vertex_shader=FLAT_VERT, fragment_shader=FLAT_FRAG)

        # HUD shader (2-D quad overlay)
        hud_vert = """
        #version 330 core
        uniform vec2 u_screen;
        in vec2 in_pos; in vec2 in_uv; out vec2 v_uv;
        void main() {
            vec2 ndc = (in_pos / u_screen) * 2.0 - 1.0;
            ndc.y = -ndc.y;
            gl_Position = vec4(ndc, 0.0, 1.0);
            v_uv = in_uv;
        }"""
        hud_frag = """
        #version 330 core
        uniform sampler2D u_tex; in vec2 v_uv; out vec4 frag_color;
        void main() {
            vec4 c = texture(u_tex, v_uv);
            if (c.a < 0.02) discard;
            frag_color = c;
        }"""
        self._hud_prog = ctx.program(vertex_shader=hud_vert, fragment_shader=hud_frag)

        # Shadow FBO
        self._shadow_tex = ctx.depth_texture((self.SHADOW_SIZE, self.SHADOW_SIZE))
        self._shadow_fbo = ctx.framebuffer(depth_attachment=self._shadow_tex)

        # Dummy 1×1 white texture bound to albedo unit (PBR shader expects it at unit 1)
        self._white_tex = ctx.texture((1, 1), 3, np.array([255, 255, 255], dtype=np.uint8).tobytes())

        # Geometry VAOs (box + sphere for main & shadow pass).
        # Vertex layout: 8 floats [pos.xyz, normal.xyz, u, v] (forge3d v0.2)
        self._vaos: dict[str, Any] = {}
        for key, mesh_fn in [("box", unit_box), ("sphere", unit_sphere)]:
            verts, idx = mesh_fn()                       # verts: (N, 8) float32
            vbo_m = ctx.buffer(verts.tobytes())
            ibo = ctx.buffer(idx.tobytes())
            self._vaos[key] = (
                ctx.vertex_array(
                    self._main_prog,
                    [(vbo_m, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
                    index_buffer=ibo,
                ),
                len(idx),
            )
            # Shadow VAO: position-only (first 3 of 8 floats per vertex)
            pos_only = np.ascontiguousarray(verts.reshape(-1, 8)[:, :3])
            vbo_s = ctx.buffer(pos_only.tobytes())
            self._vaos[f"{key}_shadow"] = (
                ctx.vertex_array(
                    self._shadow_prog,
                    [(vbo_s, "3f", "in_position")],
                    index_buffer=ibo,
                ),
                len(idx),
            )

        # Grid
        gv = grid_lines(half_size=12.0, step=0.5)
        self._grid_vao = ctx.vertex_array(
            self._flat_prog, [(ctx.buffer(gv.tobytes()), "3f", "in_position")]
        )
        self._grid_n = len(gv)

    # ── Camera helpers ────────────────────────────────────────────────────────

    def _eye(self) -> np.ndarray:
        az = math.radians(self._az)
        el = math.radians(self._el)
        return self._target + np.array([
            self._dist * math.cos(el) * math.cos(az),
            self._dist * math.cos(el) * math.sin(az),
            self._dist * math.sin(el),
        ])

    def reset_camera(self) -> None:
        self._az = 30.0; self._el = 22.0; self._dist = 2.2
        self._target = np.array([0.0, 0.0, 0.35])

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        """pygame 이벤트 처리. False 반환 시 종료."""
        pg = self._pygame
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                self.should_stop = True; return False
            elif ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE:
                    self.should_stop = True; return False
                elif ev.key == pg.K_r:
                    self.reset_camera()
                elif ev.key == pg.K_SPACE:
                    self.paused = not self.paused
            elif ev.type == pg.MOUSEBUTTONDOWN:
                if ev.button == 1: self._lmb = True;  self._mpos = ev.pos
                if ev.button == 3: self._rmb = True;  self._mpos = ev.pos
            elif ev.type == pg.MOUSEBUTTONUP:
                if ev.button == 1: self._lmb = False
                if ev.button == 3: self._rmb = False
            elif ev.type == pg.MOUSEMOTION:
                dx = ev.pos[0] - self._mpos[0]
                dy = ev.pos[1] - self._mpos[1]
                if self._lmb:                    # orbit
                    self._az = (self._az - dx * 0.35) % 360
                    self._el = float(np.clip(self._el - dy * 0.35, -89, 89))
                elif self._rmb:                  # pan
                    az = math.radians(self._az)
                    right = np.array([math.cos(az + math.pi/2),
                                      math.sin(az + math.pi/2), 0.0])
                    self._target -= right * dx * 0.002 * self._dist
                    self._target[2] += dy * 0.002 * self._dist
                self._mpos = ev.pos
            elif ev.type == pg.MOUSEWHEEL:
                self._dist = float(np.clip(self._dist - ev.y * 0.15, 0.2, 15.0))
        return True

    # ── Matrix helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _look_at(eye: np.ndarray, tgt: np.ndarray, up: np.ndarray) -> np.ndarray:
        fwd = tgt - eye; fwd /= np.linalg.norm(fwd) + 1e-12
        right = np.cross(fwd, up); right /= np.linalg.norm(right) + 1e-12
        u = np.cross(right, fwd)
        M = np.eye(4, dtype=np.float32)
        M[0, :3]=right; M[0,3]=-right.dot(eye)
        M[1, :3]=u;     M[1,3]=-u.dot(eye)
        M[2, :3]=-fwd;  M[2,3]=fwd.dot(eye)
        return M

    @staticmethod
    def _perspective(fov: float, aspect: float, near: float, far: float) -> np.ndarray:
        f = 1.0 / math.tan(math.radians(fov) / 2)
        M = np.zeros((4,4), dtype=np.float32)
        M[0,0]=f/aspect; M[1,1]=f
        M[2,2]=-(far+near)/(far-near); M[2,3]=-2*far*near/(far-near)
        M[3,2]=-1.0
        return M

    @staticmethod
    def _ortho(l:float,r:float,b:float,t:float,n:float,f:float) -> np.ndarray:
        M = np.zeros((4,4), dtype=np.float32)
        M[0,0]=2/(r-l); M[0,3]=-(r+l)/(r-l)
        M[1,1]=2/(t-b); M[1,3]=-(t+b)/(t-b)
        M[2,2]=-2/(f-n); M[2,3]=-(f+n)/(f-n)
        M[3,3]=1.0
        return M

    @staticmethod
    def _mb(M: np.ndarray) -> bytes:
        return M.T.astype(np.float32).tobytes()

    # ── Per-body helpers ──────────────────────────────────────────────────────

    def _body_scale(self, body: Any) -> np.ndarray:
        st, sp = body.shape_type, body.shape_params
        if st == "box":
            he = sp["half_extents"]
            return np.array([he[0]*2, he[1]*2, he[2]*2], dtype=np.float32)
        if st in ("sphere", "capsule"):
            r = float(sp["radius"])
            return np.array([r, r, r], dtype=np.float32)
        return np.ones(3, dtype=np.float32)

    def _model_mat(self, body: Any, scale: np.ndarray) -> np.ndarray:
        M = np.zeros((4,4), dtype=np.float32)
        M[:3,:3] = body.transform.rotation.astype(np.float32) * scale
        M[:3, 3] = body.transform.position.astype(np.float32)
        M[3,  3] = 1.0
        return M

    def _vao_key(self, body: Any) -> str:
        return "sphere" if body.shape_type in ("sphere","capsule") else "box"

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self, snapshot: Any, hud_lines: list[str] | None = None) -> None:
        """SceneSnapshot 1프레임 렌더 후 display.flip."""
        from forge3d.render.snapshot import BUILTIN_MATERIALS

        ctx   = self._ctx
        W, H  = self.width, self.height
        eye   = self._eye()
        up    = np.array([0., 0., 1.])
        fwd_v = self._target - eye
        if abs(fwd_v[2]) / (np.linalg.norm(fwd_v) + 1e-12) > 0.98:
            up = np.array([0., 1., 0.])

        V  = self._look_at(eye, self._target, up)
        P  = self._perspective(50.0, W/H, 0.02, 200.0)

        # Light (fixed directional)
        ld = np.array([-0.5, -0.7, -0.8]); ld /= np.linalg.norm(ld)
        le = -60.0 * ld
        up_l = np.array([0.,0.,1.])
        if abs(np.dot(ld, up_l)) > 0.95: up_l = np.array([0.,1.,0.])
        LV = self._look_at(le, np.zeros(3), up_l)
        LP = self._ortho(-10, 10, -10, 10, 0.1, 150.0)
        light_VP = LP @ LV

        # ── Shadow pass ───────────────────────────────────────────────────────
        self._shadow_fbo.use()
        ctx.viewport = (0, 0, self.SHADOW_SIZE, self.SHADOW_SIZE)
        self._shadow_fbo.clear(depth=1.0)
        ctx.enable(ctx.DEPTH_TEST); ctx.depth_func = "<"
        for body in snapshot.bodies:
            sk = self._vao_key(body) + "_shadow"
            if sk not in self._vaos: continue
            sc = self._body_scale(body)
            M  = self._model_mat(body, sc)
            svao, sn = self._vaos[sk]
            try: self._shadow_prog["u_light_MVP"].write(self._mb((light_VP @ M).astype(np.float32)))
            except KeyError: pass
            svao.render(mode=ctx.TRIANGLES, vertices=sn)

        # ── Main PBR pass ─────────────────────────────────────────────────────
        ctx.screen.use()
        ctx.viewport = (0, 0, W, H)
        ctx.screen.clear(red=0.05, green=0.07, blue=0.12, depth=1.0)
        ctx.enable(ctx.DEPTH_TEST)
        ctx.depth_func = "<"
        # Shadow map → unit 0; dummy white albedo → unit 1
        self._shadow_tex.use(location=0)
        self._white_tex.use(location=1)

        prog = self._main_prog
        amb = np.array([0.10, 0.10, 0.14], dtype=np.float32)
        ldir = (-ld).astype(np.float32)
        mat_lookup = {**BUILTIN_MATERIALS, **snapshot.materials}
        try:
            prog["u_shadow_map"] = 0
            prog["u_albedo_map"] = 1
            prog["u_light_dir"].write(ldir.tobytes())
            prog["u_light_color"].write(
                np.array([1.0, 0.95, 0.85], dtype=np.float32).tobytes()
            )
            prog["u_ambient_color"].write(amb.tobytes())
            prog["u_eye"].write(eye.astype(np.float32).tobytes())
        except KeyError:
            pass

        for body in snapshot.bodies:
            vk = self._vao_key(body)
            if vk not in self._vaos:
                continue
            sc = self._body_scale(body)
            M = self._model_mat(body, sc)
            MVP = (P @ V @ M).astype(np.float32)
            NM = (body.transform.rotation.astype(np.float32) / (sc + 1e-12)).astype(np.float32)
            mat = mat_lookup.get(body.material_id) or mat_lookup.get("default")
            col = np.array(mat.color if mat else (0.75, 0.75, 0.75), dtype=np.float32)
            roughness = float(mat.roughness) if mat else 0.5
            metallic = float(mat.metallic) if mat else 0.0
            try:
                prog["u_MVP"].write(self._mb(MVP))
                prog["u_M"].write(self._mb(M.astype(np.float32)))
                prog["u_NM"].write(NM.T.tobytes())
                prog["u_light_MVP"].write(self._mb((light_VP @ M).astype(np.float32)))
                prog["u_mat_color"].write(col.tobytes())
                prog["u_roughness"].value = roughness
                prog["u_metallic"].value = metallic
                prog["u_has_texture"].value = 0  # no textures in training viewer
            except KeyError:
                pass
            vao, n_idx = self._vaos[vk]
            vao.render(mode=ctx.TRIANGLES, vertices=n_idx)

        # ── Grid ──────────────────────────────────────────────────────────────
        VP = (P @ V).astype(np.float32)
        ctx.disable(ctx.DEPTH_TEST)
        try:
            self._flat_prog["u_VP"].write(self._mb(VP))
            self._flat_prog["u_color"].write(
                np.array([0.22,0.28,0.22,0.35], dtype=np.float32).tobytes())
        except KeyError: pass
        self._grid_vao.render(mode=ctx.LINES, vertices=self._grid_n)
        ctx.enable(ctx.DEPTH_TEST)

        # ── HUD ───────────────────────────────────────────────────────────────
        if hud_lines:
            self._draw_hud(hud_lines)

        self._pygame.display.flip()

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self, lines: list[str]) -> None:
        """HUD 줄마다 GPU 텍스처를 생성→렌더→즉시 해제 (단순·정확)."""
        ctx = self._ctx
        pg  = self._pygame
        W, H = self.width, self.height
        ctx.disable(ctx.DEPTH_TEST)
        ctx.enable(ctx.BLEND)
        ctx.blend_func = ctx.SRC_ALPHA, ctx.ONE_MINUS_SRC_ALPHA

        import moderngl
        scrn = np.array([W, H], dtype=np.float32).tobytes()
        y = 12
        for text in lines:
            surf = self._font_sm.render(text, True, (220, 230, 255))
            pad  = 5
            tw   = surf.get_size()[0] + pad * 2
            th   = surf.get_size()[1] + pad * 2
            bg   = pg.Surface((tw, th), pg.SRCALPHA)
            bg.fill((0, 0, 0, 150))
            bg.blit(surf, (pad, pad))

            tex = ctx.texture((tw, th), 4, pg.image.tostring(bg, "RGBA", True))
            tex.filter = moderngl.NEAREST, moderngl.NEAREST

            x0, x1 = 12, 12 + tw
            y0, y1 = y, y + th
            verts = np.array([[x0,y0,0,0],[x1,y0,1,0],[x0,y1,0,1],
                               [x1,y0,1,0],[x1,y1,1,1],[x0,y1,0,1]], dtype=np.float32)
            vbo = ctx.buffer(verts.tobytes())
            vao = ctx.vertex_array(self._hud_prog, [(vbo, "2f 2f", "in_pos", "in_uv")])

            tex.use(location=0)
            try:
                self._hud_prog["u_tex"] = 0
                self._hud_prog["u_screen"].write(scrn)
            except KeyError:
                pass
            vao.render()

            vao.release(); vbo.release(); tex.release()
            y += th + 3

        ctx.disable(ctx.BLEND)
        ctx.enable(ctx.DEPTH_TEST)

    def close(self) -> None:
        for val in self._vaos.values():
            if isinstance(val, tuple):
                val[0].release()
        if hasattr(self, "_grid_vao"):
            self._grid_vao.release()
        if hasattr(self, "_white_tex") and self._white_tex is not None:
            self._white_tex.release()
        self._ctx.release()
        self._pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
#  LiveTrainingCallback — SB3 callback that feeds LiveViewer
# ══════════════════════════════════════════════════════════════════════════════

class LiveTrainingCallback:
    """SB3-compatible callback that renders each rollout step to LiveViewer."""

    def __init__(
        self,
        viewer: LiveViewer,
        eval_env: Any,
        render_freq: int = 1024,   # policy steps between render episodes
        target_fps: float = 30.0,
    ) -> None:
        self._viewer    = viewer
        self._eval_env  = eval_env
        self._render_freq = render_freq
        self._frame_dt  = 1.0 / target_fps
        self._last_render = 0.0
        self._last_step = 0

        # Stats
        self._ep_successes: list[int] = []
        self._ep_distances: list[float] = []
        self._ep_rewards: list[float] = []
        self._train_start = time.perf_counter()
        self._step_count  = 0
        self._total_steps = 1

        # SB3 BaseCallback interface stubs
        self.n_calls = 0
        self.num_timesteps = 0
        self.model = None
        self.training_env = None
        self.locals: dict = {}
        self.globals: dict = {}
        self.logger = None
        self.parent = None

    def init_callback(self, model: Any) -> None:
        self.model = model

    def on_training_start(self, locals_: dict, globals_: dict) -> None:
        self.locals = locals_
        self._train_start = time.perf_counter()

    def on_step(self) -> bool:
        self.n_calls     += 1
        self.num_timesteps = self.n_calls

        # Always handle pygame events
        if not self._viewer.handle_events():
            return False  # stop training

        now = time.perf_counter()

        # Render at limited FPS during live rollout display
        if now - self._last_render >= self._frame_dt:
            self._last_render = now
            if self.n_calls - self._last_step >= self._render_freq:
                self._last_step = self.n_calls
                self._run_eval_episode()

        return True

    def on_rollout_end(self) -> None:
        pass

    def on_training_end(self) -> None:
        pass

    # ── Eval episode ──────────────────────────────────────────────────────────

    def _run_eval_episode(self) -> None:
        if self.model is None:
            return
        env = self._eval_env
        obs, _ = env.reset()
        ep_reward = 0.0

        for step in range(200):
            if not self._viewer.handle_events():
                self._viewer.should_stop = True
                return

            if self._viewer.paused:
                # Stay paused until SPACE pressed
                while self._viewer.paused:
                    if not self._viewer.handle_events():
                        self._viewer.should_stop = True
                        return
                    time.sleep(0.016)

            action, _ = self.model.predict(obs, deterministic=True)
            obs, reward, done, trunc, info = env.step(action)
            ep_reward += float(reward)

            dist = info.get("distance", info.get("dist", 1.0))
            success = info.get("success", False)

            snap = env._world.snapshot()
            self._viewer.render(snap, self._hud(step, dist, success, ep_reward))

            # Target FPS throttle
            elapsed = time.perf_counter() - self._last_render
            sleep_t = self._frame_dt - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
            self._last_render = time.perf_counter()

            if done or trunc:
                self._ep_successes.append(int(success))
                self._ep_distances.append(float(dist))
                self._ep_rewards.append(ep_reward)
                break

    def _hud(self, step: int, dist: float, success: bool, ep_reward: float) -> list[str]:
        elapsed = time.perf_counter() - self._train_start
        sps = self.n_calls / max(elapsed, 0.1)
        sr  = np.mean(self._ep_successes[-50:]) if self._ep_successes else 0.0

        dist_bar  = _bar(max(0.0, 1.0 - dist / 0.8), 20)
        steps_pct = min(1.0, self.n_calls / max(self._total_steps, 1))
        train_bar = _bar(steps_pct, 20)

        status = "✓ 도달!" if success else f"  거리 {dist:.3f}m"
        pause  = "  [SPACE=일시정지]" if not self._viewer.paused else "  ⏸ 일시정지 [SPACE=재개]"

        return [
            f"  학습 [{train_bar}] {self.n_calls:>7,} / {self._total_steps:,}   {sps:6.0f} sps",
            f"  성공률 {sr:5.1%}   (최근 {min(len(self._ep_successes),50)}화)",
            f"  거리  [{dist_bar}] {status}",
            f"  보상  {ep_reward:+.2f}   스텝 {step+1:>3}/200",
            f"  R=카메라초기화  좌드래그=orbit  우드래그=pan  휠=zoom",
            pause,
        ]


def _bar(ratio: float, width: int) -> str:
    n = int(np.clip(ratio, 0.0, 1.0) * width)
    return "█" * n + "░" * (width - n)


# ══════════════════════════════════════════════════════════════════════════════
#  Live training entry point
# ══════════════════════════════════════════════════════════════════════════════

def run_training_live(
    total_steps: int,
    out_dir: str,
    viewer_width: int = 1280,
    viewer_height: int = 720,
) -> None:
    """실시간 뷰어로 RL 학습."""
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback
        from stable_baselines3.common.monitor import Monitor
    except ImportError:
        print("  ❌ stable-baselines3 미설치.  pip install stable-baselines3")
        sys.exit(1)

    from apps.robot_rl.envs.reach_env import ReachEnv

    os.makedirs(out_dir, exist_ok=True)

    train_env = Monitor(ReachEnv(render_mode=None))
    eval_env  = ReachEnv(render_mode=None)

    model = PPO(
        "MlpPolicy", train_env,
        n_steps=1024, batch_size=128, n_epochs=10,
        learning_rate=3e-4, ent_coef=0.005,
        gamma=0.99, gae_lambda=0.95,
        verbose=0,
    )

    viewer = LiveViewer(width=viewer_width, height=viewer_height)
    live_cb = LiveTrainingCallback(viewer, eval_env, render_freq=1024)
    live_cb._total_steps = total_steps

    # SB3 BaseCallback 상속 어댑터 — SB3 내부 인터페이스와 완전 호환
    class _Adapter(BaseCallback):
        def __init__(self) -> None:
            super().__init__(verbose=0)

        def _on_step(self) -> bool:
            live_cb.num_timesteps = self.num_timesteps
            return live_cb.on_step()

        def _on_training_start(self) -> None:
            live_cb.model = self.model
            live_cb.on_training_start(self.locals, self.globals)

        def _on_training_end(self) -> None:
            live_cb.on_training_end()

        def _on_rollout_end(self) -> None:
            live_cb.on_rollout_end()

    print(f"  학습 시작: {total_steps:,} 스텝")
    print(f"  뷰어: {viewer_width}×{viewer_height}")
    print()
    print("  ┌─ 뷰어 조작 ──────────────────────────────────────┐")
    print("  │  좌클릭 드래그   → 카메라 orbit (회전)            │")
    print("  │  우클릭 드래그   → 카메라 pan  (이동)             │")
    print("  │  마우스 휠       → zoom (거리 조절)               │")
    print("  │  R               → 카메라 초기화                  │")
    print("  │  SPACE           → 일시정지 / 재개                │")
    print("  │  ESC             → 학습 중단 + 종료               │")
    print("  └───────────────────────────────────────────────────┘")
    print()

    t0 = time.perf_counter()
    try:
        model.learn(
            total_timesteps=total_steps,
            callback=_Adapter(),
            progress_bar=False,
            reset_num_timesteps=True,
        )
    except KeyboardInterrupt:
        print("\n  학습 중단 (Ctrl+C)")
    finally:
        save_path = os.path.join(out_dir, "final_model")
        model.save(save_path)
        elapsed = time.perf_counter() - t0
        sr = float(np.mean(live_cb._ep_successes[-50:])) if live_cb._ep_successes else 0.0
        print(f"\n  최종 성공률: {sr:.1%}   학습 시간: {elapsed:.0f}s")
        print(f"  모델 저장 → {save_path}.zip")
        viewer.close()
        train_env.close()
        eval_env.close()


# ══════════════════════════════════════════════════════════════════════════════
#  기존 텍스트 모드 (변경 없음)
# ══════════════════════════════════════════════════════════════════════════════

def _banner() -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║      forge3d — 강화학습 실시간 트레이닝 뷰어 🤖       ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  UR5 로봇 팔이 목표 지점에 도달하는 방법을 학습       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


def record_rollout(
    model: Any,
    out_path: str,
    n_episodes: int = 3,
    fps: int = 20,
    label: str = "",
) -> dict:
    import imageio
    from apps.robot_rl.envs.reach_env import ReachEnv

    env = ReachEnv(render_mode="rgb_array", max_steps=150)
    frames = []
    stats: dict = {"successes": 0, "distances": [], "steps": []}

    for ep in range(n_episodes):
        obs, _ = env.reset(seed=ep * 17)
        for step in range(150):
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            frame = env.render()
            if frame is not None: frames.append(frame)
            if terminated or truncated:
                stats["successes"] += int(terminated)
                stats["distances"].append(info.get("dist", info.get("distance", 1.0)))
                stats["steps"].append(step + 1)
                break

    env.close()
    writer = imageio.get_writer(out_path, fps=fps, quality=7)
    for f in frames: writer.append_data(f)
    writer.close()

    stats["success_rate"] = stats["successes"] / n_episodes
    stats["mean_dist"]  = float(np.mean(stats["distances"])) if stats["distances"] else 1.0
    stats["mean_steps"] = float(np.mean(stats["steps"])) if stats["steps"] else 150
    return stats


class TrainingDisplay:
    def __init__(self, total_steps: int) -> None:
        self.total_steps = total_steps
        self.snapshots: list[dict] = []
        self.start_time = time.perf_counter()

    def update(self, step: int, success_rate: float, mean_reward: float) -> None:
        elapsed = time.perf_counter() - self.start_time
        sps = step / max(elapsed, 0.1)
        remaining = (self.total_steps - step) / max(sps, 1)
        bar_w = 40
        bar = "█" * int(bar_w * step / self.total_steps) + "░" * (bar_w - int(bar_w * step / self.total_steps))
        emoji = "🎯" if success_rate >= 0.5 else ("📈" if success_rate >= 0.2 else ("🔄" if success_rate >= 0.05 else "🌱"))
        print(f"\r  [{bar}] {100*step/self.total_steps:5.1f}%  스텝: {step:>7,}  "
              f"성공률: {success_rate:5.1%} {emoji}  보상: {mean_reward:7.2f}  "
              f"남은 시간: {remaining:4.0f}s", end="", flush=True)

    def record_snapshot(self, step: int, stats: dict) -> None:
        self.snapshots.append({"step": step, **stats})
        print(f"\n  📹 롤아웃 저장 — 스텝 {step:,} | 성공률 {stats['success_rate']:.0%}")


def run_training(total_steps: int, out_dir: str, snapshot_steps: list[int]) -> tuple:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.monitor import Monitor
    except ImportError:
        print("  ❌ stable-baselines3 미설치.  pip install stable-baselines3")
        sys.exit(1)
    from apps.robot_rl.envs.reach_env import ReachEnv
    from apps.robot_rl.training.callbacks import SuccessRateCallback

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "rollouts"), exist_ok=True)

    env   = Monitor(ReachEnv())
    model = PPO("MlpPolicy", env, n_steps=1024, batch_size=128, n_epochs=10,
                learning_rate=3e-4, ent_coef=0.005, gamma=0.99, gae_lambda=0.95, verbose=0)
    cb    = SuccessRateCallback(log_path=os.path.join(out_dir, "progress.csv"), log_freq=2048)
    disp  = TrainingDisplay(total_steps)

    snap_points = sorted(snapshot_steps) + [total_steps]
    trained = 0
    snapshot_results: list[dict] = []

    print(f"  총 {total_steps:,} 스텝 학습 시작…\n")
    for target in snap_points:
        delta = target - trained
        if delta <= 0: continue
        model.learn(total_timesteps=delta, reset_num_timesteps=(trained == 0),
                    callback=cb, progress_bar=False)
        trained = target
        disp.update(trained, cb.latest_success_rate,
                    getattr(cb, "latest_mean_reward", 0.0))
        if target in sorted(snapshot_steps):
            rp = os.path.join(out_dir, "rollouts", f"step_{target:07d}.mp4")
            print(f"\n\n  ── 스텝 {target:,} 롤아웃 렌더링 중 ──")
            s = record_rollout(model, rp, n_episodes=2)
            disp.record_snapshot(target, s)
            snapshot_results.append({"step": target, "file": rp, **s})

    print("\n")
    env.close()
    model.save(os.path.join(out_dir, "final_model"))
    return model, disp, snapshot_results


def assemble_progress_video(snapshot_results: list[dict], out_path: str, fps: int = 20) -> None:
    import imageio
    if not snapshot_results: return
    print("  📼 비교 영상 조립 중…")
    all_frames: list[Any] = []
    for snap in snapshot_results:
        if not os.path.exists(snap["file"]): continue
        reader = imageio.get_reader(snap["file"])
        clip = list(reader); reader.close()
        if clip:
            h, w = clip[0].shape[:2]
            title = np.zeros((h, w, 3), dtype=np.uint8)
            title[:] = [30, 30, 50]
            all_frames.extend([title] * (fps // 2))
        all_frames.extend(clip)
    if not all_frames: return
    writer = imageio.get_writer(out_path, fps=fps, quality=7)
    for f in all_frames: writer.append_data(f)
    writer.close()
    print(f"  ✅ 비교 영상 → {out_path}")


def print_summary(out_dir: str, snapshot_results: list[dict]) -> None:
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║                  학습 완료! 🎓                        ║")
    print("╠══════════════════════════════════════════════════════╣")
    if snapshot_results:
        first, last = snapshot_results[0], snapshot_results[-1]
        delta = last["success_rate"] - first["success_rate"]
        sign  = "+" if delta >= 0 else ""
        print(f"║  첫 스냅샷 성공률:  {first['success_rate']:5.1%} ({first['step']:>7,} 스텝)  ║")
        print(f"║  최종 스냅샷 성공률:{last['success_rate']:5.1%} ({last['step']:>7,} 스텝)  ║")
        print(f"║  향상폭:           {sign}{delta:.1%}{'':<30}║")
    print(f"║  출력 폴더: {out_dir:<41}║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    final_zip = os.path.join(out_dir, "final_model.zip")
    print(f"  다음 단계:")
    print(f"    모델 테스트: python demos/interactive_robot.py --model {final_zip}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="forge3d RL 학습 + 시각화")
    parser.add_argument("--steps",   type=int, default=200_000)
    parser.add_argument("--out",     type=str, default="training_output/demo_run")
    parser.add_argument("--live",    action="store_true",
                        help="실시간 3D 뷰어로 학습 관찰 (pygame 창)")
    parser.add_argument("--width",   type=int, default=1280,  help="뷰어 가로 (--live 전용)")
    parser.add_argument("--height",  type=int, default=720,   help="뷰어 세로 (--live 전용)")
    parser.add_argument("--use-existing", action="store_true")
    parser.add_argument("--model",   type=str, default=None)
    args = parser.parse_args()

    _banner()

    if args.use_existing:
        try:
            from stable_baselines3 import PPO
        except ImportError:
            print("  ❌ stable-baselines3 미설치"); sys.exit(1)
        path = args.model or "training_output/reach_ppo/final_model.zip"
        if not os.path.exists(path):
            print(f"  ❌ 모델 없음: {path}"); sys.exit(1)
        model = PPO.load(path)
        rd = os.path.join(args.out, "rollouts"); os.makedirs(rd, exist_ok=True)
        s = record_rollout(model, os.path.join(rd, "existing_rollout.mp4"), n_episodes=3)
        print(f"  성공률: {s['success_rate']:.0%} | 평균 거리: {s['mean_dist']:.3f}m")
        return

    if args.live:
        print(f"  🎮 실시간 뷰어 모드  ({args.width}×{args.height})")
        print(f"  학습: {args.steps:,} 스텝  →  {args.out}/")
        print()
        run_training_live(args.steps, args.out, args.width, args.height)
        return

    # 텍스트 모드
    total = args.steps
    snap_pcts = [0.25, 0.50, 0.75]
    snap_steps = [int(total * p) for p in snap_pcts]
    print(f"  학습 설정: {total:,} 스텝 | 스냅샷: {snap_steps} | 출력: {args.out}/")
    print()

    model, disp, results = run_training(total, args.out, snap_steps)
    rp_final = os.path.join(args.out, "rollouts", f"step_{total:07d}_final.mp4")
    fs = record_rollout(model, rp_final, n_episodes=3)
    results.append({"step": total, "file": rp_final, **fs})
    assemble_progress_video(results, os.path.join(args.out, "training_progress.mp4"))
    print_summary(args.out, results)


if __name__ == "__main__":
    main()
