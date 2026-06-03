"""HQ scene representation — SceneSnapshot → raytracer data.

Pure data conversion.  No physics, no OpenGL, no side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class HQPrimitive:
    """Raytracer-ready primitive (sphere or OBB box)."""

    ptype: str  # "sphere" | "box"
    center: np.ndarray  # (3,) world-frame
    # sphere
    radius: float = 0.0
    # box
    half_extents: np.ndarray = field(default_factory=lambda: np.zeros(3))
    R: np.ndarray = field(default_factory=lambda: np.eye(3))  # body-to-world
    # material
    color: np.ndarray = field(default_factory=lambda: np.array([0.75, 0.75, 0.75]))
    roughness: float = 0.5
    metallic: float = 0.0


@dataclass
class HQLight:
    """Directional light for Phong shading.

    `toward_light`: unit vector from scene surface TOWARD the light source.
    (i.e. the negation of LightSnapshot.direction which points scene-ward.)
    """

    toward_light: np.ndarray  # (3,) unit
    color: np.ndarray  # (3,) RGB [0,1]
    intensity: float


@dataclass
class HQCamera:
    position: np.ndarray  # (3,)
    target: np.ndarray  # (3,)
    up: np.ndarray  # (3,)
    fov_deg: float


@dataclass
class HQScene:
    primitives: list[HQPrimitive]
    lights: list[HQLight]
    camera: HQCamera
    background_top: np.ndarray = field(default_factory=lambda: np.array([0.40, 0.60, 0.90]))
    background_bot: np.ndarray = field(default_factory=lambda: np.array([1.00, 1.00, 1.00]))


# ── Conversion ────────────────────────────────────────────────────────────────


def build_hq_scene(snapshot: Any) -> HQScene:
    """Convert a SceneSnapshot to an HQScene for the raytracer."""

    primitives: list[HQPrimitive] = []
    for body in snapshot.bodies:
        color, roughness, metallic = _resolve_material(body.material_id, snapshot.materials)
        R = np.asarray(body.transform.rotation, dtype=float)
        pos = np.asarray(body.transform.position, dtype=float)

        if body.shape_type == "sphere":
            r = float(body.shape_params["radius"])
            primitives.append(
                HQPrimitive(
                    ptype="sphere",
                    center=pos,
                    radius=r,
                    R=R,
                    color=color,
                    roughness=roughness,
                    metallic=metallic,
                )
            )
        elif body.shape_type == "box":
            he = np.asarray(body.shape_params["half_extents"], dtype=float)
            primitives.append(
                HQPrimitive(
                    ptype="box",
                    center=pos,
                    half_extents=he,
                    R=R,
                    color=color,
                    roughness=roughness,
                    metallic=metallic,
                )
            )
        # Other shapes: silently skip (not implemented in P6)

    lights: list[HQLight] = []
    for ls in snapshot.lights:
        # LightSnapshot.direction points scene-ward (downward); negate for "toward light"
        toward = -np.asarray(ls.direction, dtype=float)
        toward = toward / (np.linalg.norm(toward) + 1e-10)
        lights.append(
            HQLight(
                toward_light=toward,
                color=np.asarray(ls.color, dtype=float),
                intensity=float(ls.intensity),
            )
        )

    cam = snapshot.camera
    camera = HQCamera(
        position=np.asarray(cam.position, dtype=float),
        target=np.asarray(cam.target, dtype=float),
        up=np.asarray(cam.up, dtype=float),
        fov_deg=float(cam.fov_deg),
    )

    return HQScene(primitives=primitives, lights=lights, camera=camera)


def _resolve_material(mat_id: str, materials: dict[str, Any]) -> tuple[np.ndarray, float, float]:
    """Return (color_rgb, roughness, metallic) for a material ID."""
    from forge3d.render.snapshot import BUILTIN_MATERIALS

    mat = materials.get(mat_id) or BUILTIN_MATERIALS.get("default")
    if mat is None:
        return np.array([0.75, 0.75, 0.75]), 0.5, 0.0

    color_raw = mat.color
    if isinstance(color_raw, str):
        fallback = BUILTIN_MATERIALS.get(color_raw) or BUILTIN_MATERIALS.get("default")
        color_raw = fallback.color if fallback else (0.75, 0.75, 0.75)

    return np.array(color_raw, dtype=float), float(mat.roughness), float(mat.metallic)
