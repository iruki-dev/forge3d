"""Smoke tests for RealtimeRenderer — renders a few frames, checks output shape/dtype.

These tests require OpenGL (Xvfb).  If no OpenGL is available, tests are skipped.
"""

from __future__ import annotations

import numpy as np
import pytest

from forge3d.render.realtime.context import check_opengl_available
from forge3d.render.snapshot import (
    SceneSnapshot,
)
from forge3d.sim.world import PhysicsWorld

HAS_GL = check_opengl_available()

skip_no_gl = pytest.mark.skipif(not HAS_GL, reason="OpenGL not available (no Xvfb / no display)")


def _make_snapshot() -> SceneSnapshot:
    """Minimal snapshot: one red box + camera + light."""
    w = PhysicsWorld()
    w.add_box((1, 1, 1), (0, 0, 3), material="red")
    w.add_static_box((20, 20, 0.2), (0, 0, -0.1), material="ground")
    w.set_camera((5, -8, 4), (0, 0, 0))
    w.step(1 / 60)
    return w.snapshot()


# ── Basic render ──────────────────────────────────────────────────────────────


@skip_no_gl
class TestRealtimeSmoke:
    def test_render_returns_array(self) -> None:
        from forge3d.render.realtime.renderer import RealtimeRenderer

        snap = _make_snapshot()
        with RealtimeRenderer(width=320, height=240) as r:
            frame = r.render(snap)
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8

    def test_frame_not_all_background(self) -> None:
        """At least some pixels should differ from background colour."""
        from forge3d.render.realtime.renderer import RealtimeRenderer

        snap = _make_snapshot()
        bg = (0.15, 0.18, 0.22)
        bg_u8 = np.array([int(c * 255) for c in bg], dtype=np.uint8)
        with RealtimeRenderer(width=320, height=240, bg_color=bg) as r:
            frame = r.render(snap)
        # Most pixels != background → something was drawn
        diff = np.abs(frame.astype(int) - bg_u8).sum(axis=-1)
        n_different = (diff > 10).sum()
        assert n_different > 1000, f"Only {n_different} non-background pixels — nothing rendered?"

    def test_deterministic_output(self) -> None:
        """Same snapshot must produce identical frames."""
        from forge3d.render.realtime.renderer import RealtimeRenderer

        snap = _make_snapshot()
        with RealtimeRenderer(width=320, height=240) as r:
            f1 = r.render(snap)
            f2 = r.render(snap)
        np.testing.assert_array_equal(f1, f2)

    def test_multiple_bodies(self) -> None:
        """Rendering a world with several bodies should succeed."""
        from forge3d.render.realtime.renderer import RealtimeRenderer

        w = PhysicsWorld()
        for i in range(4):
            w.add_box((0.5, 0.5, 0.5), (i * 1.5 - 2, 0, 3 + i), material="blue")
        w.add_static_box((20, 20, 0.2), (0, 0, -0.1), material="ground")
        w.set_camera((5, -8, 4), (0, 0, 3))
        w.step(1 / 60)
        snap = w.snapshot()
        with RealtimeRenderer(width=320, height=240) as r:
            frame = r.render(snap)
        assert frame.shape == (240, 320, 3)

    def test_renderer_context_manager(self) -> None:
        """Renderer should close cleanly as a context manager."""
        from forge3d.render.realtime.renderer import RealtimeRenderer

        snap = _make_snapshot()
        with RealtimeRenderer(width=160, height=120) as r:
            _ = r.render(snap)
        # After exit, calling render again should reinitialise
        # (or raise, either is acceptable — just no crash during __exit__)


# ── FPS estimation ────────────────────────────────────────────────────────────


@skip_no_gl
class TestRealtimeFPS:
    def test_fps_acceptable(self) -> None:
        """Render 30 frames and check average FPS ≥ 10 (llvmpipe is ~30–60)."""
        import time

        from forge3d.render.realtime.renderer import RealtimeRenderer

        w = PhysicsWorld()
        w.add_box((1, 1, 1), (0, 0, 5), material="red")
        w.add_static_box((20, 20, 0.2), (0, 0, -0.1), material="ground")
        w.set_camera((5, -8, 4), (0, 0, 2))
        n_frames = 30
        t0 = time.perf_counter()
        with RealtimeRenderer(width=400, height=300) as r:
            for _ in range(n_frames):
                w.step(1.0 / 60.0)
                snap = w.snapshot()
                r.render(snap)
        fps = n_frames / (time.perf_counter() - t0)
        print(f"\nFPS (llvmpipe, 400×300, {n_frames} frames): {fps:.1f}")
        assert fps >= 10.0, f"FPS too low: {fps:.1f}"
