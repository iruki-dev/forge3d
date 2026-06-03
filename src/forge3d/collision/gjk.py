"""Gilbert-Johnson-Keerthi (GJK) distance algorithm.

Determines whether two convex shapes intersect and, if not, computes the
minimum distance between them.

Supported shapes:
  sphere       — represented by (center, radius)
  box OBB      — represented by (position, rotation, half_extents)
  mesh/capsule — convex hull support via hull_vertices in shape_params

Algorithm:
  Build a simplex in the Minkowski difference A ⊖ B.  If the simplex encloses
  the origin, the shapes intersect.  Otherwise, the distance equals the length
  of the nearest-point vector from the simplex to the origin.

Convention:
  Normal points from shape_b toward shape_a (consistent with ContactPoint).
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ── Support functions ─────────────────────────────────────────────────────────


def _support_sphere(center: np.ndarray, radius: float, d: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(d)
    if n < 1e-12:
        return center + np.array([radius, 0.0, 0.0])
    return center + (radius / n) * d


def _support_box(pos: np.ndarray, R: np.ndarray, he: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Furthest point of an OBB in direction d."""
    d_local = R.T @ d
    s_local = np.where(d_local >= 0, he, -he)
    return pos + R @ s_local


def _support_convex_hull(
    pos: np.ndarray, R: np.ndarray, hull_verts: np.ndarray, d: np.ndarray
) -> np.ndarray:
    """Furthest point of a convex hull in world-frame direction d.

    hull_verts is (K, 3) in LOCAL frame.  O(K) — fast for small hulls.
    """
    d_local = R.T @ d          # direction in local frame
    dots = hull_verts @ d_local  # (K,) — vectorised
    return pos + R @ hull_verts[int(np.argmax(dots))]


def _body_support(body: Any, d: np.ndarray) -> np.ndarray:
    """Dispatch to the correct support function for a body."""
    from forge3d.math.quaternion import quat_to_rot

    if body.shape_type == "sphere":
        return _support_sphere(body.pos, float(body.shape_params["radius"]), d)
    if body.shape_type == "box":
        R = quat_to_rot(body.quat)
        return _support_box(body.pos, R, body.shape_params["half_extents"], d)
    if body.shape_type in ("mesh", "capsule"):
        R = quat_to_rot(body.quat)
        hull_verts = body.shape_params["hull_vertices"]
        return _support_convex_hull(body.pos, R, hull_verts, d)
    raise ValueError(f"GJK: unsupported shape '{body.shape_type}'")


def _cso_support(a: Any, b: Any, d: np.ndarray) -> np.ndarray:
    """Minkowski difference support: support_a(d) - support_b(-d)."""
    return _body_support(a, d) - _body_support(b, -d)


# ── Simplex nearest-point helpers ─────────────────────────────────────────────


def _nearest_on_line(p0: np.ndarray, p1: np.ndarray) -> tuple[list[np.ndarray], np.ndarray]:
    """Nearest point on segment [p0, p1] to origin.  p1 is the newest vertex."""
    p01 = p0 - p1
    t = float(np.dot(-p1, p01)) / float(np.dot(p01, p01) + 1e-300)
    t = max(0.0, min(1.0, t))
    nearest = p1 + t * p01
    return [p0, p1] if t > 0.0 else [p1], -nearest


def _nearest_on_triangle(
    p0: np.ndarray, p1: np.ndarray, p2: np.ndarray
) -> tuple[list[np.ndarray], np.ndarray] | None:
    """Nearest feature of triangle [p0, p1, p2] to origin (p2 newest).

    Returns (reduced_simplex, direction) or None if origin inside the infinite
    prism defined by the triangle (used when testing tetrahedron faces).
    """
    ab = p1 - p2
    ac = p0 - p2
    ao = -p2
    n = np.cross(ab, ac)

    # Check if origin is outside each edge (in the plane of the triangle)
    if np.dot(np.cross(ab, n), ao) > 0:
        # Outside edge AB (between p2 and p1)
        if np.dot(ab, ao) > 0:
            d = np.cross(np.cross(ab, ao), ab)
            # parenthesise to avoid 3-tuple mis-parse
            return ([p1, p2], d) if float(np.dot(d, d)) > 1e-20 else ([p1, p2], ao)
        return _nearest_on_line(p2, p2)  # fallback: just vertex p2

    if np.dot(np.cross(n, ac), ao) > 0:
        # Outside edge AC (between p2 and p0)
        if np.dot(ac, ao) > 0:
            d = np.cross(np.cross(ac, ao), ac)
            return ([p0, p2], d) if float(np.dot(d, d)) > 1e-20 else ([p0, p2], ao)
        return [p2], ao

    # Inside the triangle in the plane — check above/below face
    dn = float(np.dot(n, ao))
    if dn > 0:
        return [p0, p1, p2], n
    if dn < 0:
        # Flip winding so normal points toward origin
        return [p1, p0, p2], -n
    # Origin ON the face
    return None  # contained


def _do_simplex(
    simplex: list[np.ndarray], d: np.ndarray
) -> tuple[list[np.ndarray], np.ndarray] | None:
    """Evolve the GJK simplex toward origin.

    Returns (new_simplex, new_direction) when not yet enclosed, or None when
    the simplex contains the origin (→ intersection).
    """
    n = len(simplex)

    if n == 1:
        return simplex, -simplex[0]

    if n == 2:
        return _nearest_on_line(simplex[0], simplex[1])

    if n == 3:
        result = _nearest_on_triangle(simplex[0], simplex[1], simplex[2])
        return result  # None → origin inside triangle (treat as intersection)

    # n == 4: tetrahedron
    D, C, B, A = simplex
    AB = B - A
    AC = C - A
    AD = D - A
    AO = -A

    # Outward face normals (re-orient so they point away from the opposite vertex)
    ABC = np.cross(AB, AC)
    ACD = np.cross(AC, AD)
    ADB = np.cross(AD, AB)
    if np.dot(ABC, AD) > 0:
        ABC = -ABC
    if np.dot(ACD, AB) > 0:
        ACD = -ACD
    if np.dot(ADB, AC) > 0:
        ADB = -ADB

    in_abc = np.dot(ABC, AO) > 0
    in_acd = np.dot(ACD, AO) > 0
    in_adb = np.dot(ADB, AO) > 0

    if not in_abc and not in_acd and not in_adb:
        return None  # origin inside tetrahedron → intersection!

    # Reduce to the face that the origin is "most in front of"
    if in_abc:
        return _nearest_on_triangle(C, B, A)
    if in_acd:
        return _nearest_on_triangle(D, C, A)
    return _nearest_on_triangle(B, D, A)


# ── Internal GJK returning simplex ───────────────────────────────────────────


def _gjk_internal(
    body_a: Any, body_b: Any, max_iter: int = 64
) -> tuple[bool, float, list[np.ndarray]]:
    """Run GJK and return (intersecting, distance, final_simplex).

    The simplex is needed by EPA when bodies intersect.
    """
    d = body_b.pos - body_a.pos
    if float(np.linalg.norm(d)) < 1e-10:
        d = np.array([1.0, 0.0, 0.0])
    d = d / np.linalg.norm(d)

    s = _cso_support(body_a, body_b, d)
    simplex: list[np.ndarray] = [s]
    d = -s

    for _ in range(max_iter):
        d_len = float(np.linalg.norm(d))
        if d_len < 1e-12:
            return True, 0.0, simplex

        new_pt = _cso_support(body_a, body_b, d / d_len)
        if float(np.dot(new_pt, d)) < 0:
            return False, d_len, simplex

        simplex.append(new_pt)
        result = _do_simplex(simplex, d)

        if result is None:
            return True, 0.0, simplex

        simplex, d = result

    return True, 0.0, simplex


# ── Public GJK interface ──────────────────────────────────────────────────────


def gjk(body_a: Any, body_b: Any, max_iter: int = 64) -> tuple[bool, float]:
    """Run GJK between two convex bodies.

    Parameters
    ----------
    body_a, body_b : bodies with ``shape_type``, ``pos``, ``quat``,
                     ``shape_params`` attributes (duck-typed _Body).
    max_iter       : maximum GJK iterations (default 64).

    Returns
    -------
    intersecting : True if bodies overlap.
    distance     : 0.0 if intersecting; minimum separation otherwise.
    """
    intersecting, dist, _ = _gjk_internal(body_a, body_b, max_iter)
    return intersecting, dist


def gjk_contact(
    body_a: Any, body_b: Any, max_iter: int = 64
) -> tuple[float, np.ndarray] | None:
    """GJK + EPA contact query.

    Returns (depth, normal) where normal points from body_b toward body_a,
    or None if bodies are not intersecting.
    """
    from forge3d.collision.epa import epa

    intersecting, _, simplex = _gjk_internal(body_a, body_b, max_iter)
    if not intersecting:
        return None
    return epa(body_a, body_b, simplex)


def gjk_intersect(body_a: Any, body_b: Any) -> bool:
    """Boolean intersection test. True iff bodies overlap."""
    intersecting, _ = gjk(body_a, body_b)
    return intersecting


def gjk_distance(body_a: Any, body_b: Any) -> float:
    """Minimum separation distance. Returns 0.0 if bodies overlap."""
    _, dist = gjk(body_a, body_b)
    return dist
