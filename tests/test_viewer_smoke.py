"""Smoke tests for forge3d.Viewer and forge3d.Recorder (P4).

Require OpenGL (Xvfb).  Skipped if unavailable.
"""

from __future__ import annotations

import numpy as np
import pytest

import forge3d as f3d
from forge3d.render.realtime.context import check_opengl_available

HAS_GL = check_opengl_available()
skip_no_gl = pytest.mark.skipif(not HAS_GL, reason="OpenGL not available")


def _make_world() -> f3d.World:
    w = f3d.World()
    w.add_ground()
    w.add_box(size=(1, 1, 1), position=(0, 0, 4), material="red")
    return w


# ── Viewer ────────────────────────────────────────────────────────────────────


@skip_no_gl
class TestViewerSmoke:
    def test_draw_returns_frame(self) -> None:
        w = _make_world()
        with f3d.Viewer(w, max_frames=5) as v:
            w.step()
            frame = v.draw()
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.dtype == np.uint8
        assert frame.ndim == 3 and frame.shape[2] == 3

    def test_is_open_closes_after_max_frames(self) -> None:
        w = _make_world()
        v = f3d.Viewer(w, max_frames=3)
        count = 0
        while v.is_open:
            w.step()
            v.draw()
            count += 1
        assert count == 3
        assert not v.is_open
        v.close()

    def test_run_convenience(self) -> None:
        w = _make_world()
        v = f3d.Viewer(w, max_frames=10)
        v.run(dt=1 / 60)
        assert v.frame_count == 10

    def test_run_collect_frames(self) -> None:
        w = _make_world()
        v = f3d.Viewer(w, max_frames=5)
        frames = v.run(collect_frames=True)
        assert frames is not None
        assert len(frames) == 5
        for f in frames:
            assert f.shape == (600, 800, 3)

    def test_context_manager_closes_cleanly(self) -> None:
        w = _make_world()
        with f3d.Viewer(w, max_frames=5) as v:
            while v.is_open:
                w.step()
                v.draw()
        assert not v.is_open

    def test_viewer_repr(self) -> None:
        w = _make_world()
        v = f3d.Viewer(w, max_frames=3)
        r = repr(v)
        assert "Viewer" in r
        v.close()

    def test_step_once(self) -> None:
        w = _make_world()
        v = f3d.Viewer(w, max_frames=10)
        t0 = w.time
        frame = v.step_once(dt=1 / 60)
        assert frame is not None
        assert w.time > t0
        v.close()

    def test_default_headless_frames_terminates(self) -> None:
        """Viewer without explicit max_frames should still terminate."""
        w = _make_world()
        v = f3d.Viewer(w)
        # DEFAULT_HEADLESS_FRAMES should be finite
        assert f3d.Viewer.DEFAULT_HEADLESS_FRAMES < float("inf")
        v.close()


# ── Recorder ──────────────────────────────────────────────────────────────────


@skip_no_gl
class TestRecorderSmoke:
    def test_realtime_recorder_run(self, tmp_path) -> None:
        w = _make_world()
        out = str(tmp_path / "test.mp4")
        rec = f3d.Recorder(w, mode="realtime", resolution=(320, 240), output=out)
        rec.run(duration=0.1, dt=1 / 240, fps=30)
        # Saved as image sequence when imageio-ffmpeg not available
        # Check either mp4 or sequence directory was created
        from pathlib import Path

        seq_dir = Path(str(tmp_path / "test"))
        mp4 = Path(out)
        assert mp4.exists() or seq_dir.exists(), "Recorder produced no output"

    def test_hq_runs(self) -> None:
        """HQ mode is implemented in P6 — should run and produce output."""
        w = _make_world()
        rec = f3d.Recorder(w, mode="hq", resolution=(32, 24), samples=1, output="/tmp/test_hq.mp4")
        rec.run(duration=0.05, dt=1 / 60, fps=10)
        from pathlib import Path

        assert Path("/tmp/test_hq.mp4").exists() or Path("/tmp/test_hq").exists()

    def test_run_policy_needs_env(self) -> None:
        """run_policy(policy, env, ...) — env is now required (P9 implementation)."""
        import inspect

        w = _make_world()
        rec = f3d.Recorder(w, mode="realtime", output="/tmp/test.mp4")
        sig = inspect.signature(rec.run_policy)
        # Verify the new signature includes 'env' parameter
        assert "env" in sig.parameters


# ── Gate test: §6.1 example (headless) ───────────────────────────────────────


@skip_no_gl
def test_roadmap_section_6_1_example() -> None:
    """ROADMAP §6.1 target example runs end-to-end (headless)."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    viewer = f3d.Viewer(world, mode="realtime", max_frames=10)
    while viewer.is_open:
        world.step(dt=1 / 60)
        viewer.draw()
    assert not viewer.is_open
    assert box.position[2] < 5.0  # box fell
    assert world.time > 0.0
