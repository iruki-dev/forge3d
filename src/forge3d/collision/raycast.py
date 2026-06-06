"""Ray-vs-body intersection tests for forge3d.

Supports: sphere, box (OBB), capsule (approximate).
Returns the closest hit along the ray within max_dist.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _ray_sphere(
    ro: np.ndarray,
    rd: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> float | None:
    """Ray-sphere intersection. Returns t ≥ 0 or None."""
    oc = ro - center
    b = float(np.dot(oc, rd))
    c = float(np.dot(oc, oc)) - radius * radius
    disc = b * b - c
    if disc < 0:
        return None
    sq = disc**0.5
    t1 = -b - sq
    t2 = -b + sq
    if t2 < 0:
        return None
    return t1 if t1 >= 0 else t2


def _ray_box_obb(
    ro: np.ndarray,
    rd: np.ndarray,
    center: np.ndarray,
    half_extents: np.ndarray,
    R: np.ndarray,
) -> float | None:
    """Ray vs OBB intersection (slab method in box local frame)."""
    # Transform ray into box local frame
    d = ro - center
    ro_l = R.T @ d
    rd_l = R.T @ rd

    t_min = 0.0
    t_max = float("inf")
    for i in range(3):
        if abs(rd_l[i]) < 1e-12:
            if abs(ro_l[i]) > half_extents[i]:
                return None
        else:
            t1 = (-half_extents[i] - ro_l[i]) / rd_l[i]
            t2 = (half_extents[i] - ro_l[i]) / rd_l[i]
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return None
    return t_min if t_min >= 0 else (t_max if t_max >= 0 else None)


def _box_normal(hit_local: np.ndarray, half: np.ndarray) -> np.ndarray:
    """Normal of closest face in box local frame."""
    n = np.zeros(3)
    best = -1.0
    for i in range(3):
        d = abs(abs(hit_local[i]) - half[i])
        if best < 0 or d < best:
            best = d
            n = np.zeros(3)
            n[i] = 1.0 if hit_local[i] > 0 else -1.0
    return n


def ray_cast(
    ro: np.ndarray,
    direction: np.ndarray,
    max_dist: float,
    bodies: list[Any],
) -> tuple[int, np.ndarray, np.ndarray, float] | None:
    """Cast a ray and return (body_id, hit_point, normal, distance) or None."""
    from forge3d.math.quaternion import quat_to_rot

    rd_norm = np.linalg.norm(direction)
    if rd_norm < 1e-12:
        return None
    rd = direction / rd_norm

    best_t: float = max_dist
    best: tuple[int, np.ndarray, np.ndarray, float] | None = None

    for body in bodies:
        st = body.shape_type
        sp = body.shape_params
        center = body.pos
        R = quat_to_rot(body.quat)

        t: float | None = None
        hit_n = np.array([0.0, 0.0, 1.0])

        if st == "sphere":
            r = float(sp["radius"])
            t = _ray_sphere(ro, rd, center, r)
            if t is not None:
                hit_p = ro + rd * t
                hit_n = (hit_p - center) / (np.linalg.norm(hit_p - center) + 1e-12)

        elif st == "box":
            he = np.asarray(sp["half_extents"], dtype=float)
            t = _ray_box_obb(ro, rd, center, he, R)
            if t is not None:
                hit_p = ro + rd * t
                local = R.T @ (hit_p - center)
                hit_n = R @ _box_normal(local, he)

        elif st == "capsule":
            # Approximate capsule as sphere at center (fast but coarse)
            r = float(sp["radius"]) + float(sp.get("half_length", 0.5))
            t = _ray_sphere(ro, rd, center, r)
            if t is not None:
                hit_p = ro + rd * t
                hit_n = (hit_p - center) / (np.linalg.norm(hit_p - center) + 1e-12)

        if t is not None and 0 <= t < best_t:
            best_t = t
            hit_p = ro + rd * t
            best = (body.body_id, hit_p, hit_n, t)

    return best


def ray_cast_all(
    ro: np.ndarray,
    direction: np.ndarray,
    max_dist: float,
    bodies: list[Any],
) -> list[tuple[int, np.ndarray, np.ndarray, float]]:
    """Cast a ray and return **all** hits sorted by distance (closest first)."""
    from forge3d.math.quaternion import quat_to_rot

    rd_norm = np.linalg.norm(direction)
    if rd_norm < 1e-12:
        return []
    rd = direction / rd_norm

    hits: list[tuple[float, int, np.ndarray, np.ndarray]] = []

    for body in bodies:
        st = body.shape_type
        sp = body.shape_params
        center = body.pos
        R = quat_to_rot(body.quat)

        t: float | None = None
        hit_n = np.array([0.0, 0.0, 1.0])

        if st == "sphere":
            r = float(sp["radius"])
            t = _ray_sphere(ro, rd, center, r)
            if t is not None:
                hit_p = ro + rd * t
                hit_n = (hit_p - center) / (np.linalg.norm(hit_p - center) + 1e-12)

        elif st == "box":
            he = np.asarray(sp["half_extents"], dtype=float)
            t = _ray_box_obb(ro, rd, center, he, R)
            if t is not None:
                hit_p = ro + rd * t
                local = R.T @ (hit_p - center)
                hit_n = R @ _box_normal(local, he)

        elif st == "capsule":
            r = float(sp["radius"]) + float(sp.get("half_length", 0.5))
            t = _ray_sphere(ro, rd, center, r)
            if t is not None:
                hit_p = ro + rd * t
                hit_n = (hit_p - center) / (np.linalg.norm(hit_p - center) + 1e-12)

        if t is not None and 0 <= t <= max_dist:
            hit_p = ro + rd * t
            hits.append((t, body.body_id, hit_p, hit_n))

    hits.sort(key=lambda x: x[0])
    return [(bid, pt, n, dist) for dist, bid, pt, n in hits]
