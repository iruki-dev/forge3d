"""MeshData — shared pure-data type for 3D mesh assets.

Physics uses hull_vertices (convex hull points in local frame).
Renderer uses the interleaved vertex/index arrays.
This object is intentionally immutable after creation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class MeshData:
    """Triangle mesh ready for both physics (convex hull) and rendering.

    All arrays are in the mesh's LOCAL frame (origin = mesh centre).
    The renderer uses ``interleaved()``; the physics uses ``hull_vertices``.

    Vertex layout: [px, py, pz,  nx, ny, nz,  u, v]  — 8 floats, float32.
    """

    # Rendering geometry (local frame, float32)
    vertices: Any  # (N, 3) float32 — vertex positions
    normals: Any  # (N, 3) float32 — per-vertex normals
    uvs: Any  # (N, 2) float32 — texture UV coordinates
    indices: Any  # (M,)   uint32  — triangle vertex indices (3 per triangle)

    # Physics geometry — convex hull of the mesh (local frame, float64)
    hull_vertices: Any  # (K, 3) float64 — convex hull vertices
    hull_faces: Any  # (F, 3) int32   — convex hull triangle face indices

    # Material assignment per face group [(name, first_tri_idx, n_triangles)]
    material_groups: list[tuple[str, int, int]] = field(default_factory=list)

    # Unique ID for VAO / texture caching in the renderer (set at creation time)
    mesh_id: int = field(default=0)

    def __post_init__(self) -> None:
        if self.mesh_id == 0:
            object.__setattr__(self, "mesh_id", id(self))

    def interleaved(self) -> np.ndarray:
        """Return (N, 8) float32 array [pos.xyz, normal.xyz, uv.xy] for GPU upload."""
        return np.concatenate(
            [
                np.asarray(self.vertices, dtype=np.float32),
                np.asarray(self.normals, dtype=np.float32),
                np.asarray(self.uvs, dtype=np.float32),
            ],
            axis=1,
        )

    @property
    def n_vertices(self) -> int:
        return len(self.vertices)

    @property
    def n_triangles(self) -> int:
        return len(self.indices) // 3

    @staticmethod
    def from_arrays(
        positions: np.ndarray,
        normals: np.ndarray,
        uvs: np.ndarray | None,
        indices: np.ndarray,
    ) -> MeshData:
        """Construct MeshData and compute convex hull automatically."""
        pos = np.asarray(positions, dtype=np.float32)
        nrm = np.asarray(normals, dtype=np.float32)
        uv = (
            np.zeros((len(pos), 2), dtype=np.float32)
            if uvs is None
            else np.asarray(uvs, dtype=np.float32)
        )
        idx = np.asarray(indices, dtype=np.uint32)

        hull_verts, hull_faces = _compute_convex_hull(pos.astype(np.float64))
        return MeshData(
            vertices=pos,
            normals=nrm,
            uvs=uv,
            indices=idx,
            hull_vertices=hull_verts,
            hull_faces=hull_faces,
        )


# ── Convex hull computation ────────────────────────────────────────────────────


def _compute_convex_hull(positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute convex hull from a point cloud.

    Uses scipy.spatial.ConvexHull (scipy is a math library, not a physics engine).
    Returns (hull_vertices (K,3), hull_face_indices (F,3)).
    """
    try:
        from scipy.spatial import ConvexHull

        hull = ConvexHull(positions)
        hull_verts = positions[hull.vertices].astype(np.float64)
        # Remap simplices to the reduced vertex set
        old_to_new = {old: new for new, old in enumerate(hull.vertices)}
        faces = np.array(
            [[old_to_new[v] for v in face] for face in hull.simplices],
            dtype=np.int32,
        )
        return hull_verts, faces
    except Exception:
        # Degenerate mesh — return all vertices as "hull"
        return positions.astype(np.float64), np.empty((0, 3), dtype=np.int32)


# ── Inertia for convex hull ────────────────────────────────────────────────────


def convex_hull_inertia(
    mass: float, hull_vertices: np.ndarray, hull_faces: np.ndarray
) -> np.ndarray:
    """Inertia tensor (3×3 diagonal) for a convex hull via signed tetrahedra.

    Uses the divergence-theorem approach (Polyhedral Mass Properties).
    Returns a 3×3 diagonal numpy array suitable for _Body.inertia_local.
    """
    if len(hull_faces) == 0 or mass <= 0.0:
        # Fallback: bounding-box approximation
        lo, hi = hull_vertices.min(0), hull_vertices.max(0)
        he = (hi - lo) / 2.0
        from forge3d.math.inertia import box_inertia

        return box_inertia(mass, he)

    # Polynomial sub-expressions for integration
    v = hull_vertices
    Ixx = Iyy = Izz = 0.0
    total_vol = 0.0

    for face in hull_faces:
        v0, v1, v2 = v[face[0]], v[face[1]], v[face[2]]
        # Signed volume of tetrahedron formed with origin
        d = np.dot(v0, np.cross(v1, v2))
        vol = d / 6.0
        total_vol += vol

        # Accumulate second moments
        for a, b, c in [(v0, v1, v2), (v1, v2, v0), (v2, v0, v1)]:
            Ixx += vol * (
                a[1] ** 2
                + a[1] * b[1]
                + b[1] ** 2
                + a[1] * c[1]
                + b[1] * c[1]
                + c[1] ** 2
                + a[2] ** 2
                + a[2] * b[2]
                + b[2] ** 2
                + a[2] * c[2]
                + b[2] * c[2]
                + c[2] ** 2
            )
            Iyy += vol * (
                a[0] ** 2
                + a[0] * b[0]
                + b[0] ** 2
                + a[0] * c[0]
                + b[0] * c[0]
                + c[0] ** 2
                + a[2] ** 2
                + a[2] * b[2]
                + b[2] ** 2
                + a[2] * c[2]
                + b[2] * c[2]
                + c[2] ** 2
            )
            Izz += vol * (
                a[0] ** 2
                + a[0] * b[0]
                + b[0] ** 2
                + a[0] * c[0]
                + b[0] * c[0]
                + c[0] ** 2
                + a[1] ** 2
                + a[1] * b[1]
                + b[1] ** 2
                + a[1] * c[1]
                + b[1] * c[1]
                + c[1] ** 2
            )

    if abs(total_vol) < 1e-12:
        from forge3d.math.inertia import box_inertia

        lo, hi = hull_vertices.min(0), hull_vertices.max(0)
        return box_inertia(mass, (hi - lo) / 2.0)

    scale = mass / (total_vol * 60.0)
    Ixx *= scale
    Iyy *= scale
    Izz *= scale

    return np.diag([Ixx, Iyy, Izz])
