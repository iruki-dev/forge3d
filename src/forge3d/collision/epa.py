"""Expanding Polytope Algorithm (EPA) for penetration depth and contact normal.

Given two intersecting convex shapes and a GJK simplex that encloses the
Minkowski-difference origin, EPA expands the simplex into a full polytope
and finds the minimum-penetration-depth contact.

Returns:
  depth  : float — penetration depth (> 0)
  normal : (3,) ndarray — contact normal from body_b toward body_a

Convention: normal points FROM b TOWARD a (same as ContactPoint).
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ── Internal helpers ──────────────────────────────────────────────────────────


def _face_normal_and_dist(
    v0: np.ndarray, v1: np.ndarray, v2: np.ndarray
) -> tuple[np.ndarray, float]:
    """Outward face normal and distance from origin for one triangle.

    'Outward' means pointing AWAY from the interior of the polytope,
    i.e. the signed distance dot(normal, v0) should be positive when
    origin is inside.
    """
    edge1 = v1 - v0
    edge2 = v2 - v0
    n = np.cross(edge1, edge2)
    n_len = float(np.linalg.norm(n))
    if n_len < 1e-14:
        return np.array([0.0, 0.0, 1.0]), 1e9
    n = n / n_len
    d = float(np.dot(n, v0))
    if d < 0.0:  # flip so normal points away from origin
        n = -n
        d = -d
    return n, d


def _closest_face(
    verts: list[np.ndarray], faces: list[tuple[int, int, int]]
) -> tuple[int, np.ndarray, float]:
    """Find the face (index, normal, dist) closest to the origin."""
    min_dist = float("inf")
    min_idx = 0
    min_normal = np.array([0.0, 0.0, 1.0])

    for i, (a, b, c) in enumerate(faces):
        n, d = _face_normal_and_dist(verts[a], verts[b], verts[c])
        if d < min_dist:
            min_dist = d
            min_idx = i
            min_normal = n

    return min_idx, min_normal, min_dist


def _build_initial_polytope(
    simplex: list[np.ndarray],
    cso_fn: Any,  # callable(d) → point on CSO
) -> tuple[list[np.ndarray], list[tuple[int, int, int]]]:
    """Turn a GJK simplex into an initial tetrahedron polytope.

    GJK may return a simplex with fewer than 4 vertices when the origin is
    near a face/edge of the simplex.  We expand it here to a full tetrahedron.
    """
    verts = list(simplex)

    # Expand to at least 4 non-coplanar vertices
    directions = [
        np.array([1.0, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, -1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 0.0, -1.0]),
    ]
    while len(verts) < 4:
        best = None
        best_dist = -1.0
        for d in directions:
            pt = cso_fn(d)
            dist = float(np.dot(pt, d))
            if best is None or dist > best_dist:
                best_dist = dist
                best = pt
        if best is None:
            break
        # Only add if it doesn't duplicate an existing vertex
        if all(float(np.linalg.norm(best - v)) > 1e-7 for v in verts):
            verts.append(best)
        else:
            break

    if len(verts) < 4:
        # Degenerate: can't form a tetrahedron
        return verts, []

    # Build 4 triangular faces from tetrahedron (A, B, C, D).
    # Ensure each face normal points outward (away from opposite vertex).
    A, B, C, D = verts[:4]
    faces: list[tuple[int, int, int]] = []

    def add_face(i0: int, i1: int, i2: int, opposite: np.ndarray) -> None:
        n, _ = _face_normal_and_dist(verts[i0], verts[i1], verts[i2])
        # If normal points TOWARD opposite vertex, flip winding
        if np.dot(n, opposite - verts[i0]) > 0:
            faces.append((i0, i2, i1))  # reversed winding
        else:
            faces.append((i0, i1, i2))

    add_face(0, 1, 2, D)  # ABC, opposite D
    add_face(0, 1, 3, C)  # ABD, opposite C
    add_face(0, 2, 3, B)  # ACD, opposite B
    add_face(1, 2, 3, A)  # BCD, opposite A

    return verts, faces


def _expand_polytope(
    verts: list[np.ndarray],
    faces: list[tuple[int, int, int]],
    new_pt: np.ndarray,
    closest_face_idx: int,
) -> tuple[list[np.ndarray], list[tuple[int, int, int]]]:
    """Remove faces visible from new_pt and fill the hole.

    A face is 'visible' from new_pt if new_pt is on the outward side of the face.
    """
    # Collect edges on the silhouette (border between visible/non-visible faces)
    edge_count: dict[tuple[int, int], int] = {}

    visible: set[int] = set()
    for i, (a, b, c) in enumerate(faces):
        n, _ = _face_normal_and_dist(verts[a], verts[b], verts[c])
        if np.dot(n, new_pt - verts[a]) > 1e-10:
            visible.add(i)
            for ea, eb in [(a, b), (b, c), (c, a)]:
                key = (min(ea, eb), max(ea, eb))
                edge_count[key] = edge_count.get(key, 0) + 1

    silhouette = [edge for edge, cnt in edge_count.items() if cnt == 1]

    new_v_idx = len(verts)
    verts.append(new_pt)

    # Keep non-visible faces
    new_faces = [f for i, f in enumerate(faces) if i not in visible]

    # Add new triangles from silhouette to new_pt
    for ea, eb in silhouette:
        # Find correct winding so normal points away from origin
        n, _ = _face_normal_and_dist(verts[ea], verts[eb], new_pt)
        # normal should have positive dot with vertices (origin is inside polytope)
        if np.dot(n, verts[ea]) < 0:
            new_faces.append((ea, new_v_idx, eb))
        else:
            new_faces.append((ea, eb, new_v_idx))

    return verts, new_faces


# ── Public EPA interface ──────────────────────────────────────────────────────


def epa(
    body_a: Any,
    body_b: Any,
    gjk_simplex: list[np.ndarray],
    max_iter: int = 64,
    tolerance: float = 1e-5,
) -> tuple[float, np.ndarray]:
    """Run EPA to find penetration depth and contact normal.

    Parameters
    ----------
    body_a, body_b : duck-typed bodies with shape_type, pos, quat, shape_params.
    gjk_simplex    : simplex from GJK (must enclose the origin).
    max_iter       : maximum expansion iterations.
    tolerance      : convergence threshold.

    Returns
    -------
    depth  : penetration depth (> 0).
    normal : unit contact normal from body_b toward body_a.
    """
    from forge3d.collision.gjk import _cso_support

    def cso_fn(d: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(d))
        return _cso_support(body_a, body_b, d / n if n > 1e-12 else d)

    verts, faces = _build_initial_polytope(gjk_simplex, cso_fn)

    if len(faces) == 0:
        # Degenerate — return a simple upward normal
        return 0.01, np.array([0.0, 0.0, 1.0])

    for _ in range(max_iter):
        closest_idx, normal, dist = _closest_face(verts, faces)

        new_pt = cso_fn(normal)
        new_dist = float(np.dot(new_pt, normal))

        if new_dist - dist < tolerance:
            return dist, normal

        verts, faces = _expand_polytope(verts, faces, new_pt, closest_idx)

    closest_idx, normal, dist = _closest_face(verts, faces)
    return dist, normal
