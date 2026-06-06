"""SceneSnapshot — pure-data contract between physics core and renderers.

Physics core produces SceneSnapshot; renderers consume it.
No physics or rendering code lives here — only data classes.
All arrays are plain numpy float64 (backend-neutral after snapshot creation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transform:
    """6-DOF pose: position (3,) and rotation matrix (3, 3).

    Convenience properties::

        transform.quaternion   # → ndarray [w, x, y, z]
        transform.matrix4      # → ndarray (4, 4) column-major model matrix
    """

    position: Any  # ndarray (3,) float64
    rotation: Any  # ndarray (3, 3) float64

    @property
    def quaternion(self) -> Any:
        """Orientation as a unit quaternion ``[w, x, y, z]``."""
        import numpy as _np

        R = self.rotation
        trace = R[0, 0] + R[1, 1] + R[2, 2]
        if trace > 0.0:
            s = 0.5 / _np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * _np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * _np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * _np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
        return _np.array([w, x, y, z], dtype=_np.float64)

    @property
    def matrix4(self) -> Any:
        """4×4 homogeneous model matrix in column-major order."""
        import numpy as _np

        M = _np.eye(4, dtype=_np.float64)
        M[:3, :3] = self.rotation
        M[:3, 3] = self.position
        return M


@dataclass
class BodySnapshot:
    """Renderable state of one rigid body."""

    name: str
    transform: Transform
    shape_type: str  # 'box' | 'sphere' | 'capsule' | 'plane' | 'mesh'
    shape_params: dict[str, Any]  # e.g. {'half_extents': [.5,.5,.5]}, {'radius': .5}
    material_id: str = "default"
    material: Material | None = None  # resolved material object (takes priority over material_id)


@dataclass
class CameraSnapshot:
    """Camera description (z-up world, perspective)."""

    position: Any  # (3,) float64
    target: Any  # (3,) float64
    up: Any  # (3,) float64  — default (0,0,1) for z-up
    fov_deg: float = 45.0
    near: float = 0.1
    far: float = 200.0


@dataclass
class LightSnapshot:
    """Directional light description."""

    direction: Any  # (3,) float64, normalised, points FROM light TOWARD scene
    color: Any  # (3,) RGB in [0, 1]
    intensity: float = 1.0
    cast_shadow: bool = True


@dataclass
class Material:
    """Surface appearance (renderer-independent description)."""

    color: Any = field(default_factory=lambda: (0.8, 0.8, 0.8))  # RGB [0,1]
    roughness: float = 0.5
    metallic: float = 0.0
    emissive: float = 0.0  # emissive intensity (0 = no glow)
    texture_path: str | None = None  # path to albedo image file (PNG/JPEG)
    normal_map_path: str | None = None  # path to tangent-space normal map


# Built-in material palette: renderers fall back to these when material_id is unknown
BUILTIN_MATERIALS: dict[str, Material] = {
    "default": Material(color=(0.75, 0.75, 0.75), roughness=0.5),
    "red": Material(color=(0.90, 0.20, 0.10), roughness=0.3),
    "blue": Material(color=(0.15, 0.35, 0.90), roughness=0.4),
    "green": Material(color=(0.15, 0.70, 0.25), roughness=0.5),
    "orange": Material(color=(0.95, 0.55, 0.05), roughness=0.3),
    "ground": Material(color=(0.30, 0.48, 0.28), roughness=0.9),
    "gold": Material(color=(0.83, 0.68, 0.21), roughness=0.2, metallic=1.0),
    "white": Material(color=(0.95, 0.95, 0.95), roughness=0.8),
}


@dataclass
class TerrainSnapshot:
    """Pure-data description of a heightfield terrain for renderers.

    Attributes:
        heights: 2D float32 array of shape (rows, cols).
        cell_size: World-space size of each grid cell (m).
        origin: World-space (x, y, z) of the grid (0, 0) corner.
        material_id: Key into SceneSnapshot.materials (backward-compat).
        material: Resolved material object — use this instead of material_id
                  so renderers don't need to look up BUILTIN_MATERIALS.
    """

    heights: Any  # np.ndarray (rows, cols) float32
    cell_size: float
    origin: Any  # np.ndarray (3,) float64
    material_id: str = "ground"
    material: Material | None = None  # resolved material object


@dataclass
class SceneSnapshot:
    """Pure-data frame description.

    Physics core produces this once per sim step; any renderer consumes it.
    Generation can be disabled (return None / skip) for headless training.
    """

    bodies: list[BodySnapshot] = field(default_factory=list)
    terrains: list[TerrainSnapshot] = field(default_factory=list)
    camera: CameraSnapshot | None = None
    lights: list[LightSnapshot] = field(default_factory=list)
    materials: dict[str, Material] = field(default_factory=dict)
    time: float = 0.0
