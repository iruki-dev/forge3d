"""Heightfield terrain collision shape.

Represents a terrain as a 2D grid of height values.
Supports sphere and box collision against the terrain surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.collision.detection import ContactPoint


@dataclass
class Heightfield:
    """A 2D grid of height values representing terrain.

    Attributes:
        heights: 2D float32 array of shape (rows, cols). heights[r, c] is
            the terrain height (z) at grid cell (r, c).
        cell_size: World-space size of each grid cell (m).
        origin: World-space position of the (0, 0) grid corner (x, y, z).
        material_id: Material identifier for rendering (default: "ground").
    """

    heights: np.ndarray  # (rows, cols) float32
    cell_size: float
    origin: np.ndarray  # (3,) float64 — world position of grid corner
    material_id: str = "ground"
    friction: float = 0.8
    collision_layer: int = 0x0008  # CollisionLayer.TERRAIN = 1 << 3

    @property
    def rows(self) -> int:
        return self.heights.shape[0]

    @property
    def cols(self) -> int:
        return self.heights.shape[1]

    @property
    def total_width(self) -> float:
        return self.cell_size * (self.cols - 1)

    @property
    def total_depth(self) -> float:
        return self.cell_size * (self.rows - 1)

    def height_at(self, x: float, y: float) -> float:
        """Bilinearly interpolated height at world-space (x, y)."""
        lx = x - self.origin[0]
        ly = y - self.origin[1]

        # Grid coordinates (float)
        gx = lx / self.cell_size
        gy = ly / self.cell_size

        # Integer cell indices
        c0 = int(np.floor(gx))
        r0 = int(np.floor(gy))

        # Clamp to valid range
        c0 = max(0, min(c0, self.cols - 2))
        r0 = max(0, min(r0, self.rows - 2))
        c1 = c0 + 1
        r1 = r0 + 1

        # Bilinear interpolation weights
        tx = gx - c0
        ty = gy - r0
        tx = max(0.0, min(1.0, tx))
        ty = max(0.0, min(1.0, ty))

        h00 = float(self.heights[r0, c0])
        h10 = float(self.heights[r1, c0])
        h01 = float(self.heights[r0, c1])
        h11 = float(self.heights[r1, c1])

        return (
            h00 * (1 - tx) * (1 - ty) + h01 * tx * (1 - ty) + h10 * (1 - tx) * ty + h11 * tx * ty
        ) + float(self.origin[2])

    def normal_at(self, x: float, y: float) -> np.ndarray:
        """Approximate surface normal at (x, y) from finite differences."""
        dx = self.cell_size
        hx0 = self.height_at(x - dx, y)
        hx1 = self.height_at(x + dx, y)
        hy0 = self.height_at(x, y - dx)
        hy1 = self.height_at(x, y + dx)

        dhx = (hx1 - hx0) / (2 * dx)
        dhy = (hy1 - hy0) / (2 * dx)

        n = np.array([-dhx, -dhy, 1.0])
        norm = np.linalg.norm(n)
        return n / norm if norm > 1e-10 else np.array([0.0, 0.0, 1.0])


def sphere_vs_heightfield(
    sphere_body: Any,
    sphere_idx: int,
    hf: Heightfield,
) -> list[ContactPoint]:
    """Collision between a sphere and a heightfield terrain.

    Args:
        sphere_body: A ``_Body`` with ``shape_type == "sphere"``.
        sphere_idx: List index of the sphere body.
        hf: The heightfield to test against.

    Returns:
        List of ``ContactPoint`` objects (0 or 1 contacts).
    """
    from forge3d.collision.detection import ContactPoint

    pos = sphere_body.pos
    radius = float(sphere_body.shape_params["radius"])

    x, y = float(pos[0]), float(pos[1])
    h_terrain = hf.height_at(x, y)
    depth = h_terrain + radius - float(pos[2])

    if depth <= 0:
        return []

    normal = hf.normal_at(x, y)  # points up (z+)
    contact_pos = np.array([x, y, h_terrain])

    return [
        ContactPoint(
            body_a_idx=sphere_idx,
            body_b_idx=-1,  # static terrain
            pos=contact_pos,
            normal=normal,  # pushes sphere up
            depth=depth,
        )
    ]


def box_vs_heightfield(
    box_body: Any,
    box_idx: int,
    hf: Heightfield,
) -> list[ContactPoint]:
    """Collision between a box and a heightfield terrain.

    Approximates the box as 8 corner point samples against the heightfield.

    Args:
        box_body: A ``_Body`` with ``shape_type == "box"``.
        box_idx: List index of the box body.
        hf: The heightfield to test against.

    Returns:
        List of ``ContactPoint`` objects (0 to 4 contacts, highest penetration).
    """
    from forge3d.collision.detection import ContactPoint
    from forge3d.math.quaternion import quat_to_rot

    he = box_body.shape_params["half_extents"]
    R = quat_to_rot(box_body.quat)
    pos = box_body.pos

    # 8 corners of the box in world frame
    sx = [-1, 1]
    corners_local = [
        np.array([x * he[0], y * he[1], z * he[2]]) for x in sx for y in sx for z in sx
    ]
    corners_world = [pos + R @ c for c in corners_local]

    contacts: list[ContactPoint] = []
    for corner in corners_world:
        x, y = float(corner[0]), float(corner[1])
        h = hf.height_at(x, y)
        depth = h - float(corner[2])
        if depth > 0:
            normal = hf.normal_at(x, y)
            contacts.append(
                ContactPoint(
                    body_a_idx=box_idx,
                    body_b_idx=-1,
                    pos=np.array([x, y, h]),
                    normal=normal,
                    depth=depth,
                )
            )

    # Return up to 4 deepest contacts
    if len(contacts) > 4:
        contacts.sort(key=lambda c: -c.depth)
        contacts = contacts[:4]
    return contacts


def capsule_vs_heightfield(
    capsule_body: Any,
    capsule_idx: int,
    hf: Heightfield,
) -> list[ContactPoint]:
    """Collision between a capsule and a heightfield terrain.

    Samples three sphere centres along the capsule axis (bottom, middle, top)
    and returns the contact with the deepest penetration (if any).
    """
    from forge3d.collision.detection import ContactPoint
    from forge3d.math.quaternion import quat_to_rot

    radius = float(capsule_body.shape_params["radius"])
    half_len = float(capsule_body.shape_params["half_length"])
    R = quat_to_rot(capsule_body.quat)
    pos = capsule_body.pos
    axis = R @ np.array([0.0, 0.0, 1.0])

    best: ContactPoint | None = None
    for t in (-half_len, 0.0, half_len):
        sphere_center = pos + axis * t
        x, y = float(sphere_center[0]), float(sphere_center[1])
        h_terrain = hf.height_at(x, y)
        depth = h_terrain + radius - float(sphere_center[2])
        if depth > 0:
            normal = hf.normal_at(x, y)
            cp = ContactPoint(
                body_a_idx=capsule_idx,
                body_b_idx=-1,
                pos=np.array([x, y, h_terrain]),
                normal=normal,
                depth=depth,
            )
            if best is None or depth > best.depth:
                best = cp

    return [best] if best is not None else []


def ray_vs_heightfield(
    ro: np.ndarray,
    rd: np.ndarray,
    max_dist: float,
    hf: Heightfield,
    steps: int = 64,
) -> tuple[float, np.ndarray, np.ndarray] | None:
    """Ray vs heightfield intersection.

    Marches along the ray and bisects once a terrain crossing is detected.

    Returns
    -------
    ``(t, hit_point, normal)`` or ``None`` if no hit within *max_dist*.
    """
    step = max_dist / max(steps, 1)
    prev_h_rel: float | None = None
    prev_t: float = 0.0

    for i in range(steps + 1):
        t = i * step
        if t > max_dist:
            break
        p = ro + rd * t
        terrain_h = hf.height_at(float(p[0]), float(p[1]))
        h_rel = float(p[2]) - terrain_h

        if prev_h_rel is not None and prev_h_rel >= 0.0 and h_rel < 0.0:
            # Binary search for crossing point
            t0, t1 = prev_t, t
            for _ in range(6):
                tm = (t0 + t1) * 0.5
                pm = ro + rd * tm
                hm = hf.height_at(float(pm[0]), float(pm[1]))
                if float(pm[2]) >= hm:
                    t0 = tm
                else:
                    t1 = tm
            t_hit = (t0 + t1) * 0.5
            p_hit = ro + rd * t_hit
            hit_x, hit_y = float(p_hit[0]), float(p_hit[1])
            hit_pt = np.array([hit_x, hit_y, hf.height_at(hit_x, hit_y)])
            normal = hf.normal_at(hit_x, hit_y)
            return t_hit, hit_pt, normal

        prev_h_rel = h_rel
        prev_t = t

    return None
