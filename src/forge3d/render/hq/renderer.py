"""HQRenderer — software ray-traced renderer implementing the Renderer ABC."""

from __future__ import annotations

import numpy as np

from forge3d.render.base import Renderer
from forge3d.render.snapshot import CameraSnapshot, SceneSnapshot


class HQRenderer(Renderer):
    """Offline software ray-tracer.

    Parameters
    ----------
    width, height : Output frame dimensions.
    samples       : Ray samples per pixel (AA quality).  Default: 4.
    max_bounces   : Recursive reflection depth (0 = direct illumination only).
    """

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        samples: int = 4,
        max_bounces: int = 0,
    ) -> None:
        self._width = width
        self._height = height
        self._samples = samples
        self._max_bounces = max_bounces
        self._camera_override: CameraSnapshot | None = None
        self._frame_count = 0

    # ── Renderer ABC ──────────────────────────────────────────────────────────

    def render(self, snapshot: SceneSnapshot) -> np.ndarray:
        """Render a frame. Returns (H, W, 3) uint8."""
        from forge3d.render.hq.raytracer import render_frame
        from forge3d.render.hq.scene import build_hq_scene

        # Optional camera override (e.g. from Viewer.set_camera)
        snap = snapshot
        if self._camera_override is not None:
            snap = _with_camera(snapshot, self._camera_override)

        scene = build_hq_scene(snap)
        frame = render_frame(
            scene,
            self._width,
            self._height,
            samples=self._samples,
            rng_seed=self._frame_count,
        )
        self._frame_count += 1
        return frame

    def set_camera(self, camera: CameraSnapshot) -> None:
        self._camera_override = camera

    def close(self) -> None:
        pass  # CPU renderer: nothing to release


# ── Helpers ───────────────────────────────────────────────────────────────────


def _with_camera(snap: SceneSnapshot, cam: CameraSnapshot) -> SceneSnapshot:
    """Return a shallow copy of snap with camera replaced."""
    from dataclasses import replace

    return replace(snap, camera=cam)
