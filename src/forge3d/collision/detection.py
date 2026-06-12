"""Narrow-phase collision detection for primitive shape pairs.

Returns ContactPoint lists — pure data, no side effects, no renderer imports.

Supported pairs:
  sphere  vs. box/OBB  (general: any face, any orientation)
  sphere  vs. sphere   (dynamic-dynamic)
  box     vs. box      (SAT: all 6 faces, any orientation)
  capsule vs. sphere
  capsule vs. box
  capsule vs. capsule
  mesh    vs. plane    (convex-hull vertices vs. half-space)
  mesh    vs. sphere   (GJK + EPA)
  mesh    vs. box      (GJK + EPA)
  mesh    vs. mesh     (GJK + EPA)
  * vs. static plane   (half-space at z=0)

Legacy helpers _sphere_vs_box_halfspace and _box_vs_box_halfspace are kept
for direct test imports (backward compat).

Convention: ContactPoint.normal points from body_b toward body_a.
Positive depth means penetration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

# ── Fast 3-vector helpers (avoids np.cross moveaxis overhead on tiny arrays) ──


def _cross3(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Inline 3D cross product for (3,) vectors — 10× faster than np.cross."""
    return np.array(
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]
    )


def _quat_to_rot_unit(q: np.ndarray) -> np.ndarray:
    """quat → rot matrix assuming q is already unit (skips normalization)."""
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


if TYPE_CHECKING:
    pass  # _Body is duck-typed to avoid circular imports


@dataclass
class ContactPoint:
    """One contact between two bodies (pure data)."""

    body_a_idx: int  # index of dynamic body (always dynamic)
    body_b_idx: int  # index of other body (static or dynamic; -1 = infinite plane)
    pos: np.ndarray  # contact point in world frame
    normal: np.ndarray  # unit normal b → a (pushes a away)
    depth: float  # penetration depth > 0


# ── Public entry point ────────────────────────────────────────────────────────


_MAX_CONTACTS_PER_PAIR = 4  # reduce manifold: 4 pts sufficient for stability


def _aabb_half_extents(body: Any, R: np.ndarray | None) -> np.ndarray:
    """Axis-aligned bounding-box half-extents for a body (broadphase only)."""
    st = body.shape_type
    if st == "sphere":
        r = float(body.shape_params["radius"])
        return np.array([r, r, r])
    if st == "capsule":
        r = float(body.shape_params["radius"])
        hl = float(body.shape_params["half_length"])
        return np.array([r + hl, r + hl, r + hl])
    if st == "box":
        h = body.shape_params["half_extents"]
        if R is not None:
            return np.abs(R).dot(h)  # exact AABB of rotated OBB
        # Static box: check if it has a non-identity quat
        q = body.quat
        if abs(float(q[0])) > 0.9999:
            return np.asarray(h, dtype=float)
        return np.abs(_quat_to_rot_unit(q)).dot(np.asarray(h, dtype=float))
    if st == "mesh":
        hull_verts = body.shape_params["hull_vertices"]  # (K, 3) local
        if R is not None:
            world_verts = hull_verts @ R.T  # (K, 3) world
        else:
            Rm = _quat_to_rot_unit(body.quat)
            world_verts = hull_verts @ Rm.T
        return (world_verts.max(axis=0) - world_verts.min(axis=0)) * 0.5 + 0.01
    # plane or unknown: no culling
    return np.full(3, 1e9)


def detect_contacts(
    bodies: list[Any],
    ignored_pairs: set[frozenset[int]] | None = None,
) -> list[ContactPoint]:
    """Detect all contacts in the current body list.

    Iterates all (a, b) pairs where a is dynamic.
    Dynamic-dynamic pairs are checked once (i < j).
    Per-step optimisations:
      * R matrices pre-computed once per body (reused across all pairs).
      * AABB broadphase: skip pairs whose world-frame bounding boxes don't
        overlap — eliminates >80% of SAT calls in typical scenes.
      * Contact manifold capped at _MAX_CONTACTS_PER_PAIR.
    """
    contacts: list[ContactPoint] = []
    n = len(bodies)

    # Pre-compute rotation matrices and AABB half-extents once per step
    R_cache: list[np.ndarray | None] = [
        None if b.static else _quat_to_rot_unit(b.quat) for b in bodies
    ]
    aabb: list[np.ndarray] = [_aabb_half_extents(b, R_cache[i]) for i, b in enumerate(bodies)]

    for i in range(n):
        a = bodies[i]
        if a.static:
            continue
        aabb_a = aabb[i]
        pos_a = a.pos
        for j in range(n):
            if i == j:
                continue
            b = bodies[j]
            if not b.static and j < i:
                continue

            # ── Layer/mask filter ──────────────────────────────────────────────
            layer_a = getattr(a, "collision_layer", 0x0001)
            mask_a = getattr(a, "collision_mask", 0xFFFF)
            layer_b = getattr(b, "collision_layer", 0x0001)
            mask_b = getattr(b, "collision_mask", 0xFFFF)
            if not ((layer_a & mask_b) and (layer_b & mask_a)):
                continue

            # ── Pair-based ignore ──────────────────────────────────────────────
            if ignored_pairs:
                pair_key = frozenset({a.body_id, b.body_id})
                if pair_key in ignored_pairs:
                    continue

            # ── AABB broadphase ────────────────────────────────────────────────
            # If the axis-aligned bounding boxes don't overlap, no contact possible.
            diff = pos_a - b.pos
            if (
                abs(diff[0]) > aabb_a[0] + aabb[j][0]
                or abs(diff[1]) > aabb_a[1] + aabb[j][1]
                or abs(diff[2]) > aabb_a[2] + aabb[j][2]
            ):
                continue

            pts = _dispatch(a, i, b, j, R_cache[i], R_cache[j])
            if len(pts) > _MAX_CONTACTS_PER_PAIR:
                pts.sort(key=lambda c: -c.depth)
                pts = pts[:_MAX_CONTACTS_PER_PAIR]
            contacts.extend(pts)
    return contacts


# ── Dispatcher ────────────────────────────────────────────────────────────────


def _dispatch(
    a: Any,
    ia: int,
    b: Any,
    ib: int,
    R_a: np.ndarray | None,
    R_b: np.ndarray | None,
) -> list[ContactPoint]:
    """Route to the correct detection function based on shape types."""
    st_a = a.shape_type
    st_b = b.shape_type

    # ── sphere ────────────────────────────────────────────────────────────────
    if st_a == "sphere" and st_b == "box":
        return _sphere_vs_obb(a, ia, b, ib, R_b)
    if st_a == "sphere" and st_b == "sphere":
        return _sphere_vs_sphere(a, ia, b, ib)
    if st_a == "sphere" and st_b == "plane":
        return _sphere_vs_plane(a, ia, b, ib)

    # ── box ───────────────────────────────────────────────────────────────────
    if st_a == "box" and st_b == "sphere":
        pts = _sphere_vs_obb(b, ib, a, ia, R_a)
        return [ContactPoint(ia, ib, p.pos, -p.normal, p.depth) for p in pts]
    if st_a == "box" and st_b == "box":
        return _box_vs_box_sat(a, ia, b, ib, R_a, R_b)
    if st_a == "box" and st_b == "plane":
        return _box_vs_plane(a, ia, b, ib, R_a)

    # ── capsule ───────────────────────────────────────────────────────────────
    if st_a == "capsule" and st_b == "sphere":
        return _capsule_vs_sphere(a, ia, b, ib)
    if st_a == "capsule" and st_b == "box":
        return _capsule_vs_box(a, ia, b, ib, R_b)
    if st_a == "capsule" and st_b == "capsule":
        return _capsule_vs_capsule(a, ia, b, ib)
    if st_a == "capsule" and st_b == "plane":
        return _capsule_vs_plane(a, ia, b, ib)

    # ── mesh (convex hull) ────────────────────────────────────────────────────
    if st_a == "mesh" and st_b == "plane":
        return _mesh_vs_plane(a, ia, b, ib, R_a)
    if st_b == "mesh" and st_a == "plane":
        pts = _mesh_vs_plane(b, ib, a, ia, R_b)
        return [ContactPoint(ia, ib, p.pos, -p.normal, p.depth) for p in pts]
    # Mesh vs static box: test each hull vertex against the box faces for a
    # well-conditioned multi-point contact manifold (GJK contact points are
    # unreliable when one box has large aspect ratios, e.g. the ground plane).
    if st_a == "mesh" and st_b == "box" and b.static:
        return _mesh_vs_static_box(a, ia, b, ib, R_a)
    if st_b == "mesh" and st_a == "box" and a.static:
        pts = _mesh_vs_static_box(b, ib, a, ia, R_b)
        return [ContactPoint(ia, ib, p.pos, -p.normal, p.depth) for p in pts]
    if st_a == "mesh" or st_b == "mesh":
        return _gjk_epa_pair(a, ia, b, ib)

    # ── reverse-order: if b is dynamic and a is static/different shape ────────
    if st_b == "sphere" and st_a == "capsule":
        pts = _capsule_vs_sphere(b, ib, a, ia)
        return [ContactPoint(ia, ib, p.pos, -p.normal, p.depth) for p in pts]

    return []


# ── Half-space helpers ────────────────────────────────────────────────────────


def _box_top_z(body: Any) -> float:
    """Top face z of an axis-aligned box (assumes identity rotation for static)."""
    return float(body.pos[2] + body.shape_params["half_extents"][2])


# ── Primitive detectors ───────────────────────────────────────────────────────


def _sphere_vs_box_halfspace(sphere: Any, ia: int, box: Any, ib: int) -> list[ContactPoint]:
    """Sphere vs. static box treated as an infinite half-space (top face)."""
    plane_z = _box_top_z(box)
    r = float(sphere.shape_params["radius"])
    depth = r - (float(sphere.pos[2]) - plane_z)
    if depth <= 0.0:
        return []
    normal = np.array([0.0, 0.0, 1.0])
    pos = np.array([float(sphere.pos[0]), float(sphere.pos[1]), plane_z])
    return [ContactPoint(ia, ib, pos, normal, depth)]


def _box_vs_box_halfspace(dyn_box: Any, ia: int, static_box: Any, ib: int) -> list[ContactPoint]:
    """Dynamic box (possibly rotated) vs. static box half-space.

    Checks all 8 corners of the dynamic box against the plane.
    """
    plane_z = _box_top_z(static_box)
    he = dyn_box.shape_params["half_extents"]
    R = _quat_to_rot_unit(dyn_box.quat)

    signs = np.array(
        [
            [1, 1, 1],
            [1, 1, -1],
            [1, -1, 1],
            [1, -1, -1],
            [-1, 1, 1],
            [-1, 1, -1],
            [-1, -1, 1],
            [-1, -1, -1],
        ],
        dtype=float,
    )
    corners_world = dyn_box.pos + (signs * he) @ R.T  # (8, 3)
    depths = plane_z - corners_world[:, 2]
    penetrating = depths > 0.0
    normal = np.array([0.0, 0.0, 1.0])
    return [
        ContactPoint(
            ia,
            ib,
            np.array([corners_world[k, 0], corners_world[k, 1], plane_z]),
            normal.copy(),
            float(depths[k]),
        )
        for k in np.where(penetrating)[0]
    ]


def _sphere_vs_sphere(a: Any, ia: int, b: Any, ib: int) -> list[ContactPoint]:
    """Dynamic sphere vs. dynamic sphere."""
    diff = a.pos - b.pos
    dist = float(np.linalg.norm(diff))
    r_sum = float(a.shape_params["radius"]) + float(b.shape_params["radius"])
    depth = r_sum - dist
    if depth <= 0.0 or dist < 1e-10:
        return []
    # normal: b → a (push a away from b)
    normal = diff / dist
    contact_pos = b.pos + float(b.shape_params["radius"]) * (-normal)
    return [ContactPoint(ia, ib, contact_pos, normal.copy(), float(depth))]


def _box_vs_box_sat(
    dyn_box: Any,
    ia: int,
    other_box: Any,
    ib: int,
    R_a: np.ndarray | None = None,
    R_b: np.ndarray | None = None,
) -> list[ContactPoint]:
    """OBB-vs-OBB via Separating Axis Theorem (SAT) with contact manifold.

    Fully vectorized: all 15 axes projected and tested with batch NumPy ops.

    Algorithm:
      1. Test 15 potential separating axes (A faces × B faces × edge pairs).
      2. If any axis separates: no contact.
      3. Otherwise, the axis with minimum overlap is the contact normal.
      4. Collect all corners of ``dyn_box`` that lie inside ``other_box``
         as the contact manifold (multi-point for stability).
    """
    if R_a is None:
        R_a = _quat_to_rot_unit(dyn_box.quat)
    if R_b is None:
        R_b = _quat_to_rot_unit(other_box.quat)
    h_a = dyn_box.shape_params["half_extents"]
    h_b = other_box.shape_params["half_extents"]

    # Vector from dyn_box center to other_box center
    T = other_box.pos - dyn_box.pos

    # ── 6 face axes (columns of R_a and R_b) — shape (6, 3) ─────────────────
    face_axes = np.concatenate([R_a.T, R_b.T], axis=0)  # (6, 3)

    # ── 9 edge-edge cross products via broadcasting — no tile/repeat ──────────
    Ra3 = R_a.T[:, None, :]  # (3, 1, 3)
    Rb3 = R_b.T[None, :, :]  # (1, 3, 3)
    # Inline cross: result (3, 3, 3) → reshape to (9, 3)
    ec = np.empty((3, 3, 3))
    ec[..., 0] = Ra3[..., 1] * Rb3[..., 2] - Ra3[..., 2] * Rb3[..., 1]
    ec[..., 1] = Ra3[..., 2] * Rb3[..., 0] - Ra3[..., 0] * Rb3[..., 2]
    ec[..., 2] = Ra3[..., 0] * Rb3[..., 1] - Ra3[..., 1] * Rb3[..., 0]
    edge_axes = ec.reshape(9, 3)
    edge_lens_sq = (edge_axes**2).sum(axis=1)  # (9,) — avoid sqrt when possible
    valid_edge = edge_lens_sq > 1e-16
    if valid_edge.any():
        edge_lens = np.sqrt(edge_lens_sq[valid_edge])
        norm_edge = edge_axes[valid_edge] / edge_lens[:, None]
        all_axes = np.concatenate([face_axes, norm_edge], axis=0)  # (6+K, 3)
    else:
        all_axes = face_axes  # (6, 3)

    # ── Batch SAT projection ──────────────────────────────────────────────────
    # r_a[k] = sum_i |axes[k] · R_a[:,i]| * h_a[i]
    r_a_all = (np.abs(all_axes @ R_a) * h_a).sum(axis=1)  # (N,)
    r_b_all = (np.abs(all_axes @ R_b) * h_b).sum(axis=1)  # (N,)
    t_proj_all = all_axes @ T  # (N,)
    depths_all = r_a_all + r_b_all - np.abs(t_proj_all)  # (N,)

    if (depths_all < 0.0).any():
        return []  # separating axis found — no contact

    min_idx = int(np.argmin(depths_all))
    min_depth = float(depths_all[min_idx])
    axis = all_axes[min_idx]
    t_proj = float(t_proj_all[min_idx])
    # Convention: normal points from other_box (b) toward dyn_box (a)
    contact_normal = (-np.sign(t_proj) * axis) if abs(t_proj) > 1e-10 else axis.copy()

    # ── Contact manifold: corners of dyn_box inside other_box (vectorized) ───
    # 8 corners of dyn_box in world frame
    signs = np.array(
        [
            [-1, -1, -1],
            [-1, -1, 1],
            [-1, 1, -1],
            [-1, 1, 1],
            [1, -1, -1],
            [1, -1, 1],
            [1, 1, -1],
            [1, 1, 1],
        ],
        dtype=float,
    )
    corners_world = dyn_box.pos + (signs * h_a) @ R_a.T  # (8, 3)
    c_locals = (corners_world - other_box.pos) @ R_b  # (8, 3) world→body
    inside = np.all(np.abs(c_locals) <= h_b + 1e-6, axis=1)  # (8,)

    if inside.any():
        return [
            ContactPoint(ia, ib, corners_world[k].copy(), contact_normal.copy(), min_depth)
            for k in np.where(inside)[0]
        ]

    # Fallback: midpoint contact (edge-edge penetration)
    return [
        ContactPoint(
            ia,
            ib,
            (dyn_box.pos + other_box.pos) * 0.5,
            contact_normal.copy(),
            min_depth,
        )
    ]


# ── General sphere vs OBB ─────────────────────────────────────────────────────


def _sphere_vs_obb(
    sphere: Any,
    ia: int,
    box: Any,
    ib: int,
    R_b: np.ndarray | None = None,
) -> list[ContactPoint]:
    """General sphere vs. OBB (any orientation, any face).

    Algorithm:
      1. Transform sphere center to box local frame.
      2. Clamp to box half-extents → closest point on box surface.
      3. If distance < radius: contact.
      4. Special case: sphere center inside box → push out along min-overlap axis.
    """
    r = float(sphere.shape_params["radius"])
    if R_b is None:
        R_b = _quat_to_rot_unit(box.quat)
    h_b = box.shape_params["half_extents"]

    d = sphere.pos - box.pos
    d_local = R_b.T @ d

    # Closest point on box to sphere center (in local frame)
    closest_local = np.clip(d_local, -h_b, h_b)
    closest_world = box.pos + R_b @ closest_local

    diff = sphere.pos - closest_world
    dist = float(np.linalg.norm(diff))
    depth = r - dist

    if depth <= 0.0:
        return []

    if dist < 1e-10:
        # Sphere center is inside the box: push out along min-overlap axis
        overlap = h_b - np.abs(d_local)
        min_ax = int(np.argmin(overlap))
        axis_local = np.zeros(3)
        axis_local[min_ax] = np.sign(d_local[min_ax]) if abs(d_local[min_ax]) > 1e-10 else 1.0
        normal = R_b @ axis_local
        depth = float(overlap[min_ax]) + r
    else:
        normal = diff / dist

    contact_pos = closest_world
    return [ContactPoint(ia, ib, contact_pos.copy(), normal.copy(), float(depth))]


# ── Static plane ──────────────────────────────────────────────────────────────


def _sphere_vs_plane(sphere: Any, ia: int, plane: Any, ib: int) -> list[ContactPoint]:
    """Sphere vs. infinite half-space defined by plane.normal and plane.pos."""
    n = plane.shape_params["normal"]  # unit normal pointing "up" (into free space)
    offset = float(np.dot(plane.shape_params["normal"], plane.pos))
    r = float(sphere.shape_params["radius"])
    signed_dist = float(np.dot(n, sphere.pos)) - offset
    depth = r - signed_dist
    if depth <= 0.0:
        return []
    contact_pos = sphere.pos - signed_dist * n
    n_arr = np.asarray(n, dtype=float)
    return [ContactPoint(ia, ib, contact_pos.copy(), n_arr.copy(), float(depth))]


def _box_vs_plane(
    box: Any,
    ia: int,
    plane: Any,
    ib: int,
    R: np.ndarray | None = None,
) -> list[ContactPoint]:
    """Box corners vs. infinite half-space plane."""
    n = np.asarray(plane.shape_params["normal"], dtype=float)
    offset = float(np.dot(n, plane.pos))
    if R is None:
        R = _quat_to_rot_unit(box.quat)
    h = box.shape_params["half_extents"]
    signs = np.array(
        [
            [-1, -1, -1],
            [-1, -1, 1],
            [-1, 1, -1],
            [-1, 1, 1],
            [1, -1, -1],
            [1, -1, 1],
            [1, 1, -1],
            [1, 1, 1],
        ],
        dtype=float,
    )
    corners = box.pos + (signs * h) @ R.T  # (8, 3)
    signed_dists = corners @ n - offset  # (8,)
    penetrating = signed_dists < 0.0
    return [
        ContactPoint(ia, ib, corners[k].copy(), n.copy(), float(-signed_dists[k]))
        for k in np.where(penetrating)[0]
    ]


# ── Capsule helpers ───────────────────────────────────────────────────────────


def _capsule_endpoints(cap: Any) -> tuple[np.ndarray, np.ndarray]:
    """Return (p1, p2) world-frame endpoints of the capsule segment."""
    R = _quat_to_rot_unit(cap.quat)
    axis = R @ np.array([0.0, 0.0, 1.0])
    half_len = float(cap.shape_params["half_length"])
    return cap.pos - half_len * axis, cap.pos + half_len * axis


def _closest_point_on_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Closest point on line segment [a,b] to point p."""
    ab = b - a
    ab_sq = float(np.dot(ab, ab))
    if ab_sq < 1e-14:
        return a.copy()
    t = float(np.dot(p - a, ab)) / ab_sq
    return a + np.clip(t, 0.0, 1.0) * ab


def _closest_points_segment_segment(
    a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Closest point pair between two line segments."""
    d1 = a2 - a1
    d2 = b2 - b1
    r = a1 - b1
    e = float(np.dot(d2, d2))
    f = float(np.dot(d2, r))

    if e < 1e-14:
        tc = 0.0
        sc = float(np.dot(d1, r)) / max(float(np.dot(d1, d1)), 1e-14)
        sc = np.clip(sc, 0.0, 1.0)
    else:
        c_val = float(np.dot(d1, r))
        b_val = float(np.dot(d1, d2))
        a_val = float(np.dot(d1, d1))
        denom = a_val * e - b_val * b_val

        sc = 0.0 if abs(denom) < 1e-14 else np.clip((b_val * f - c_val * e) / denom, 0.0, 1.0)

        tc = np.clip((b_val * sc + f) / e, 0.0, 1.0)
        sc = np.clip((b_val * tc - c_val) / max(a_val, 1e-14), 0.0, 1.0)

    pa = a1 + sc * d1
    pb = b1 + tc * d2
    return pa, pb


# ── Capsule collision pairs ───────────────────────────────────────────────────


def _capsule_vs_sphere(cap: Any, ia: int, sph: Any, ib: int) -> list[ContactPoint]:
    """Capsule vs. sphere.

    Convention: body_a=cap (ia), body_b=sph (ib).
    Normal points from body_b (sphere) toward body_a (capsule).
    """
    p1, p2 = _capsule_endpoints(cap)
    closest = _closest_point_on_segment(sph.pos, p1, p2)
    to_sphere = sph.pos - closest  # from capsule axis toward sphere
    dist = float(np.linalg.norm(to_sphere))
    r_sum = float(cap.shape_params["radius"]) + float(sph.shape_params["radius"])
    depth = r_sum - dist
    if depth <= 0.0:
        return []
    # Normal from body_b (sphere) to body_a (capsule) = opposite of to_sphere
    normal = -to_sphere / dist if dist > 1e-10 else np.array([0.0, 0.0, 1.0])
    # Contact position on capsule surface in direction of sphere
    contact_pos = closest + float(cap.shape_params["radius"]) * (-normal)
    return [ContactPoint(ia, ib, contact_pos.copy(), normal.copy(), float(depth))]


def _capsule_vs_box(
    cap: Any,
    ia: int,
    box: Any,
    ib: int,
    R_b: np.ndarray | None = None,
) -> list[ContactPoint]:
    """Capsule vs. OBB — approximate via closest point on capsule axis to box."""
    p1, p2 = _capsule_endpoints(cap)
    if R_b is None:
        R_b = _quat_to_rot_unit(box.quat)
    h_b = box.shape_params["half_extents"]

    # Sample points along capsule axis (endpoints + midpoint)
    samples = [p1, (p1 + p2) * 0.5, p2]
    contacts: list[ContactPoint] = []
    seen_depth: set[float] = set()

    for pt in samples:
        d_local = R_b.T @ (pt - box.pos)
        closest_local = np.clip(d_local, -h_b, h_b)
        closest_world = box.pos + R_b @ closest_local
        diff = pt - closest_world
        dist = float(np.linalg.norm(diff))
        r = float(cap.shape_params["radius"])
        depth = r - dist
        if depth <= 0.0:
            continue
        if dist < 1e-10:
            overlap = h_b - np.abs(d_local)
            min_ax = int(np.argmin(overlap))
            axis_local = np.zeros(3)
            axis_local[min_ax] = np.sign(d_local[min_ax]) if abs(d_local[min_ax]) > 1e-10 else 1.0
            normal = R_b @ axis_local
            depth = float(overlap[min_ax]) + r
        else:
            normal = diff / dist
        key = round(depth, 6)
        if key not in seen_depth:
            seen_depth.add(key)
            contact_pos = closest_world
            contacts.append(ContactPoint(ia, ib, contact_pos.copy(), normal.copy(), float(depth)))

    return contacts


def _capsule_vs_capsule(cap_a: Any, ia: int, cap_b: Any, ib: int) -> list[ContactPoint]:
    """Capsule vs. capsule via segment-segment closest points."""
    a1, a2 = _capsule_endpoints(cap_a)
    b1, b2 = _capsule_endpoints(cap_b)
    pa, pb = _closest_points_segment_segment(a1, a2, b1, b2)
    diff = pa - pb
    dist = float(np.linalg.norm(diff))
    r_sum = float(cap_a.shape_params["radius"]) + float(cap_b.shape_params["radius"])
    depth = r_sum - dist
    if depth <= 0.0:
        return []
    normal = diff / dist if dist > 1e-10 else np.array([0.0, 0.0, 1.0])
    contact_pos = pb + float(cap_b.shape_params["radius"]) * normal
    return [ContactPoint(ia, ib, contact_pos.copy(), normal.copy(), float(depth))]


def _capsule_vs_plane(cap: Any, ia: int, plane: Any, ib: int) -> list[ContactPoint]:
    """Capsule vs. infinite half-space plane."""
    n = np.asarray(plane.shape_params["normal"], dtype=float)
    offset = float(np.dot(n, plane.pos))
    r = float(cap.shape_params["radius"])
    p1, p2 = _capsule_endpoints(cap)
    contacts: list[ContactPoint] = []
    for pt in (p1, p2):
        signed_dist = float(np.dot(n, pt)) - offset
        depth = r - signed_dist
        if depth > 0.0:
            contact_pos = pt - signed_dist * n
            contacts.append(ContactPoint(ia, ib, contact_pos.copy(), n.copy(), float(depth)))
    return contacts


# ── Mesh (convex hull) detectors ──────────────────────────────────────────────


def _mesh_vs_plane(
    mesh: Any, ia: int, plane: Any, ib: int, R: np.ndarray | None = None
) -> list[ContactPoint]:
    """Convex-hull mesh vs. infinite half-space plane.

    Tests all hull vertices against the plane and returns penetrating ones.
    """
    n = np.asarray(plane.shape_params["normal"], dtype=float)
    offset = float(np.dot(n, plane.pos))
    if R is None:
        R = _quat_to_rot_unit(mesh.quat)

    hull_verts = mesh.shape_params["hull_vertices"]  # (K, 3) local frame
    world_verts = mesh.pos + hull_verts @ R.T  # (K, 3) world frame
    signed_dists = world_verts @ n - offset  # (K,)

    penetrating = signed_dists < 0.0
    if not penetrating.any():
        return []

    contacts = [
        ContactPoint(ia, ib, world_verts[k].copy(), n.copy(), float(-signed_dists[k]))
        for k in np.where(penetrating)[0]
    ]
    if len(contacts) > _MAX_CONTACTS_PER_PAIR:
        contacts.sort(key=lambda c: -c.depth)
        contacts = contacts[:_MAX_CONTACTS_PER_PAIR]
    return contacts


def _mesh_vs_static_box(
    mesh: Any,
    ia: int,
    box: Any,
    ib: int,
    R_mesh: np.ndarray | None = None,
) -> list[ContactPoint]:
    """Convex-hull mesh vs. static box — SAT-based multi-point contact manifold.

    Uses the Separating Axis Theorem over the 6 box face axes to find the
    minimum-penetration axis.  Contact points are hull vertices that penetrate
    the chosen face.

    Normal convention: FROM box TOWARD mesh (consistent with ContactPoint).
    """
    he = np.asarray(box.shape_params["half_extents"], dtype=float)
    R_box = _quat_to_rot_unit(box.quat)

    if R_mesh is None:
        R_mesh = _quat_to_rot_unit(mesh.quat)

    hull_verts = mesh.shape_params["hull_vertices"]  # (K, 3) local frame
    world_verts = mesh.pos + hull_verts @ R_mesh.T  # (K, 3) world frame
    d_local = (world_verts - box.pos) @ R_box  # (K, 3) in box local frame

    # SAT: for each of the 3 axes compute the projection overlap.
    # If any axis shows zero or negative overlap, bodies are separated.
    best_overlap = float("inf")
    best_axis = -1
    best_sign = 1.0

    for axis in range(3):
        proj_min = float(d_local[:, axis].min())
        proj_max = float(d_local[:, axis].max())
        overlap = min(proj_max, he[axis]) - max(proj_min, -he[axis])
        if overlap <= 0.0:
            return []  # separating axis found
        if overlap < best_overlap:
            best_overlap = overlap
            best_axis = axis
            # Contact normal points from box toward mesh
            # (direction from box centre to mesh centre projected onto this axis)
            cdir = float(((mesh.pos - box.pos) @ R_box)[axis])
            best_sign = 1.0 if cdir >= 0.0 else -1.0

    if best_axis < 0:
        return []

    # Contact manifold: hull vertices that penetrate the chosen face
    signed_dist = best_sign * d_local[:, best_axis] - he[best_axis]
    pen_mask = signed_dist < 0.0
    if not pen_mask.any():
        return []

    # Require the vertex to lie within the face boundary on the other two axes
    other_axes = [i for i in range(3) if i != best_axis]
    a0, a1 = other_axes
    within = pen_mask & (np.abs(d_local[:, a0]) <= he[a0]) & (np.abs(d_local[:, a1]) <= he[a1])
    if not within.any():
        return []

    pen_verts = world_verts[within]
    pen_depths = -signed_dist[within]
    n_local = np.zeros(3)
    n_local[best_axis] = best_sign
    n_world = R_box @ n_local
    contacts = [
        ContactPoint(ia, ib, v.copy(), n_world.copy(), float(d))
        for v, d in zip(pen_verts, pen_depths, strict=True)
    ]

    if len(contacts) > _MAX_CONTACTS_PER_PAIR:
        contacts.sort(key=lambda c: -c.depth)
        contacts = contacts[:_MAX_CONTACTS_PER_PAIR]
    return contacts


def _gjk_epa_pair(a: Any, ia: int, b: Any, ib: int) -> list[ContactPoint]:
    """Generic convex-body collision via GJK + EPA.

    Prefers Rust _core path when USE_RUST_CORE=True; falls back to Python.
    """
    from forge3d.backend import USE_RUST_CORE, rust_core

    # ── Rust 경로 ──
    if USE_RUST_CORE:
        verts_a = _body_hull_world(a)
        verts_b = _body_hull_world(b)
        if verts_a is not None and verts_b is not None:
            core = rust_core()
            colliding, normal_arr, depth = core.gjk_query(verts_a, verts_b)
            if colliding and depth > 0.0:
                normal = np.asarray(normal_arr)
                pa = _body_support_world(a, normal)
                pb = _body_support_world(b, -normal)
                contact_pos = (pa + pb) * 0.5
                return [ContactPoint(ia, ib, contact_pos, normal.copy(), float(depth))]
            # Rust says no collision — confirm with AABB: if AABBs don't overlap,
            # trust the result; if they DO overlap, fall through to Python GJK
            # (the Rust GJK can fail on very flat/large shapes like the ground box).
            min_a, max_a = verts_a.min(axis=0), verts_a.max(axis=0)
            min_b, max_b = verts_b.min(axis=0), verts_b.max(axis=0)
            if not (np.all(max_a >= min_b) and np.all(max_b >= min_a)):
                return []

    # ── Python 폴백 ──
    from forge3d.collision.gjk import gjk_contact

    result = gjk_contact(a, b)
    if result is None:
        return []

    depth, normal_gjk = result
    if depth <= 0.0:
        return []

    # gjk_contact returns the CSO normal in the A-B Minkowski space, which
    # points from body_a toward body_b.  The rest of the solver uses the
    # "from body_b toward body_a" convention (same as _mesh_vs_plane), so
    # we must negate.
    normal = -normal_gjk
    pa = _body_support_world(a, normal)
    pb = _body_support_world(b, -normal)
    contact_pos = (pa + pb) * 0.5
    return [ContactPoint(ia, ib, contact_pos, normal.copy(), float(depth))]


def _body_hull_world(body: Any) -> np.ndarray | None:
    """볼록 hull 정점을 월드 좌표로 반환. hull 없으면 None."""
    st = body.shape_type
    if st == "mesh":
        hull = body.shape_params.get("hull_vertices")
        if hull is None:
            return None
        R = _quat_to_rot_unit(body.quat)
        return body.pos + hull @ R.T
    if st == "sphere":
        # 구의 경우 단일 정점(중심)만 사용
        return body.pos.reshape(1, 3)
    if st == "box":
        h = np.asarray(body.shape_params["half_extents"], dtype=float)
        corners = np.array(
            [
                [sx * h[0], sy * h[1], sz * h[2]]
                for sx in (-1, 1)
                for sy in (-1, 1)
                for sz in (-1, 1)
            ]
        )
        R = _quat_to_rot_unit(body.quat)
        return body.pos + corners @ R.T
    return None


def _body_support_world(body: Any, d: np.ndarray) -> np.ndarray:
    """World-frame support point for a body in direction d."""
    from forge3d.collision.gjk import _body_support

    return _body_support(body, d)
