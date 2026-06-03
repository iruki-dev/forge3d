"""Renderer ABC — shared contract for realtime and HQ renderers.

Physics code NEVER imports this module.
The one-way coupling is: physics → SceneSnapshot → Renderer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from forge3d.render.snapshot import CameraSnapshot, SceneSnapshot

Frame = Any  # ndarray shape (H, W, 3), uint8


class Renderer(ABC):
    """Abstract base for all forge3d renderers."""

    @abstractmethod
    def render(self, snapshot: SceneSnapshot) -> Frame | None:
        """Render one frame from snapshot. Returns RGB uint8 array or None."""

    @abstractmethod
    def set_camera(self, camera: CameraSnapshot) -> None:
        """Update camera pose for subsequent frames."""

    @abstractmethod
    def close(self) -> None:
        """Release all GPU / window resources."""

    def __enter__(self) -> Renderer:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
