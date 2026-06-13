"""FORGE RUNNER — third-person camera rig.

Thin wrapper kept for backward-compat; all logic lives in OrbitCamera now.
"""

from __future__ import annotations

import numpy as np
import settings as S

import forge3d as f3d


class CameraRig:
    def __init__(self, world: f3d.World, target: np.ndarray):
        self.world = world
        self.cam = f3d.OrbitCamera(
            target=tuple(target + np.array([0, 0, 1.2])),
            distance=S.CAM_DISTANCE,
            azimuth=180.0,
            elevation=S.CAM_ELEVATION,
            fov_deg=55.0,
        )

    @property
    def yaw_deg(self) -> float:
        return self.cam.forward_azimuth

    def update(self, inp, dt: float, player_pos: np.ndarray) -> None:
        (
            self.cam.handle_input(
                inp,
                dt,
                mouse_sensitivity=S.CAM_MOUSE_SENS,
                key_deg_per_s=S.CAM_KEY_DEG_PER_S,
                min_distance=S.CAM_MIN_DIST,
                max_distance=S.CAM_MAX_DIST,
                min_elevation=S.CAM_MIN_ELEV,
                max_elevation=S.CAM_MAX_ELEV,
            )
            .follow(player_pos, head_height=1.2, smooth_hz=S.CAM_TARGET_SMOOTH_HZ, dt=dt)
            .occlude(self.world, min_distance=1.6, layer_mask=f3d.CollisionLayer.DEFAULT)
        )

    def snapshot(self):
        return self.cam.to_snapshot()
