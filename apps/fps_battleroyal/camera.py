"""First-person camera with yaw/pitch mouse look."""
from __future__ import annotations

import math

import numpy as np

from forge3d.render.snapshot import CameraSnapshot


class FPSCamera:
    """Yaw/pitch first-person camera attached to a world position.

    Usage::

        cam = FPSCamera()
        cam.update(mouse_dx, mouse_dy, body_position)
        viewer.set_camera(cam.to_snapshot())
    """

    def __init__(
        self,
        sensitivity: float = 0.0018,
        fov_deg: float = 72.0,
        near: float = 0.08,
        far: float = 1200.0,
    ) -> None:
        self.sensitivity = sensitivity
        self.fov_deg     = fov_deg
        self.near        = near
        self.far         = far

        self.yaw:   float = 0.0     # radians, horizontal look (about Z)
        self.pitch: float = 0.0     # radians, vertical look (+ = look up)

        self._eye = np.zeros(3, dtype=np.float64)

    # ── Camera state ──────────────────────────────────────────────────────────

    @property
    def forward(self) -> np.ndarray:
        """Unit forward vector in world space."""
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        return np.array([cy * cp, sy * cp, sp], dtype=np.float64)

    @property
    def right(self) -> np.ndarray:
        """Unit right vector (perpendicular to forward, in horizontal plane)."""
        return np.array([math.sin(self.yaw), -math.cos(self.yaw), 0.0])

    # ── Update ────────────────────────────────────────────────────────────────

    def update(
        self,
        mouse_dx: float,
        mouse_dy: float,
        foot_position: np.ndarray,
        eye_height: float = 1.65,
    ) -> None:
        """Apply mouse delta and sync eye position to body feet."""
        self.yaw   -= mouse_dx * self.sensitivity
        self.pitch  = float(np.clip(
            self.pitch - mouse_dy * self.sensitivity,
            -math.pi / 2 + 0.01,
            math.pi / 2 - 0.01,
        ))
        self._eye = np.asarray(foot_position, dtype=np.float64).copy()
        self._eye[2] += eye_height

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def to_snapshot(self) -> CameraSnapshot:
        fwd    = self.forward
        target = self._eye + fwd
        # Choose up vector: world-Z unless looking straight up/down
        up = np.array([0.0, 0.0, 1.0])
        if abs(fwd[2]) > 0.98:
            up = np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0])
        return CameraSnapshot(
            position=self._eye.copy(),
            target=target,
            up=up,
            fov_deg=self.fov_deg,
            near=self.near,
            far=self.far,
        )
