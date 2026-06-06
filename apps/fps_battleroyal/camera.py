"""First-person camera with smooth mouse accumulation."""
from __future__ import annotations

import math

import numpy as np

from forge3d.render.snapshot import CameraSnapshot
from apps.fps_battleroyal.config import MOUSE_SENSITIVITY, MOUSE_SMOOTH


class FPSCamera:
    """Yaw/pitch FPS camera.

    Mouse delta is accumulated each frame by calling ``update()``.
    The optional exponential smoothing prevents jitter on low-Hz input.
    """

    def __init__(
        self,
        sensitivity: float = MOUSE_SENSITIVITY,
        fov_deg: float = 72.0,
    ) -> None:
        self.sensitivity = sensitivity
        self.fov_deg     = fov_deg
        self.fov_target  = fov_deg   # ADS smoothly changes this

        self.yaw:   float = 0.0
        self.pitch: float = 0.0

        self._eye = np.zeros(3)

        # Smoothed mouse delta (exponential moving average)
        self._smooth_dx: float = 0.0
        self._smooth_dy: float = 0.0

    # ── Camera vectors ────────────────────────────────────────────────────────

    @property
    def forward(self) -> np.ndarray:
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        return np.array([cy * cp, sy * cp, sp])

    @property
    def forward_flat(self) -> np.ndarray:
        """Forward projected onto the XY plane, normalized."""
        f = np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0])
        return f

    @property
    def right(self) -> np.ndarray:
        return np.array([math.sin(self.yaw), -math.cos(self.yaw), 0.0])

    # ── Update ────────────────────────────────────────────────────────────────

    def update(
        self,
        mouse_dx: float,
        mouse_dy: float,
        foot_position: np.ndarray,
        eye_height: float = 1.65,
        dt: float = 1 / 60,
    ) -> None:
        # Apply optional exponential smoothing
        if MOUSE_SMOOTH > 0:
            a = 1.0 - math.exp(-dt / max(MOUSE_SMOOTH, 1e-6))
            self._smooth_dx = self._smooth_dx + a * (mouse_dx - self._smooth_dx)
            self._smooth_dy = self._smooth_dy + a * (mouse_dy - self._smooth_dy)
            dx, dy = self._smooth_dx, self._smooth_dy
        else:
            dx, dy = mouse_dx, mouse_dy

        self.yaw  -= dx * self.sensitivity
        self.pitch = float(np.clip(
            self.pitch - dy * self.sensitivity,
            -math.pi / 2 + 0.015,
            math.pi / 2 - 0.015,
        ))

        # Smooth FOV change (ADS)
        self.fov_deg += (self.fov_target - self.fov_deg) * min(1.0, dt * 12.0)

        self._eye = np.array(foot_position, dtype=float)
        self._eye[2] += eye_height

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def to_snapshot(self) -> CameraSnapshot:
        fwd    = self.forward
        target = self._eye + fwd
        up     = np.array([0.0, 0.0, 1.0])
        if abs(fwd[2]) > 0.98:
            up = np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0])
        return CameraSnapshot(
            position=self._eye.copy(),
            target=target,
            up=up,
            fov_deg=self.fov_deg,
            near=0.06,
            far=1200.0,
        )
