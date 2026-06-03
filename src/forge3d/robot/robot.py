"""Robot — kinematic robot arm with FK-based link visualization.

Coordinate system: z-up, SI units.
Joint angles: radians. FK uses `forge3d.model.kinematics`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.model.kinematics import forward_kinematics


class Robot:
    """Kinematic robot arm.

    Holds joint angles, computes FK, and exposes link poses for rendering.
    Physics (dynamics) is NOT simulated — the arm is kinematically controlled.

    Parameters
    ----------
    model         : RigidBodyModel (n revolute joints, serial chain).
    link_radii    : Visual cylinder radius per link (m).  Default: 0.04 m.
    name          : Display name.
    material      : Snapshot material ID for link boxes.
    base_position : World-frame position of the robot base.
    """

    def __init__(
        self,
        model: RigidBodyModel,
        link_radii: list[float] | None = None,
        name: str = "robot",
        material: str = "default",
        base_position: Any = (0.0, 0.0, 0.0),
    ) -> None:
        self._model = model
        self._n = model.n_links
        self._q = np.zeros(self._n)
        self._link_radii: list[float] = link_radii if link_radii is not None else [0.04] * self._n
        self.name = name
        self.material = material
        self._base_pos = np.asarray(base_position, dtype=float)
        # Set by World.add() — body IDs in PhysicsWorld for each link
        self._body_ids: list[int] = []

    # ── Joint control ─────────────────────────────────────────────────────────

    @property
    def n_joints(self) -> int:
        return self._n

    @property
    def q(self) -> np.ndarray:
        """Current joint angles (rad), shape (n,)."""
        return self._q.copy()

    @q.setter
    def q(self, value: Any) -> None:
        arr = np.asarray(value, dtype=float)
        if arr.shape != (self._n,):
            raise ValueError(f"q must have shape ({self._n},), got {arr.shape}")
        self._q = arr

    def set_joint(self, idx: int, angle: float) -> None:
        """Set joint `idx` to `angle` (radians)."""
        self._q = self._q.copy()
        self._q[idx] = float(angle)

    def set_joints(self, q: Any) -> None:
        """Set all joint angles at once."""
        self.q = q

    # ── FK ────────────────────────────────────────────────────────────────────

    def link_world_poses(self) -> list[tuple[np.ndarray, np.ndarray]]:
        """FK for all links.

        Returns
        -------
        List of (pos, R) pairs (one per link), world frame.
        pos : (3,) float64 — joint origin position.
        R   : (3,3) float64 — link frame orientation.
        """
        poses = []
        for i in range(self._n):
            pos, R = forward_kinematics(self._model, self._q, link_idx=i)
            pos_world = self._base_pos + pos
            poses.append((pos_world, R))
        return poses

    def ee_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """End-effector pose (last link): (pos, R) in world frame."""
        return self.link_world_poses()[-1]

    # ── Visual representation ─────────────────────────────────────────────────

    def link_visual_boxes(
        self,
    ) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Compute (center, R, half_extents) for each link visual box.

        Each box connects the joint-i origin to the joint-(i+1) origin.
        Box z-axis is aligned along the segment direction.

        Returns
        -------
        List of (center, R, half_extents) tuples.
        """
        # Build list of ALL joint positions: base + FK for each link
        joint_positions = [self._base_pos.copy()]
        for pos, _ in self.link_world_poses():
            joint_positions.append(pos)

        boxes: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for i in range(self._n):
            p0 = joint_positions[i]
            p1 = joint_positions[i + 1]
            diff = p1 - p0
            length = float(np.linalg.norm(diff))

            if length > 1e-4:
                z_axis = diff / length
            else:
                # zero-length link: use FK z-axis
                _, R_link = forward_kinematics(self._model, self._q, link_idx=i)
                z_axis = R_link[:, 2]
                length = 0.05

            center = (p0 + p1) * 0.5
            R_box = _rotation_from_z(z_axis)
            r = self._link_radii[i]
            half_extents = np.array([r, r, length * 0.5])
            boxes.append((center, R_box, half_extents))

        return boxes

    # ── Repr ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        ee_pos, _ = self.ee_pose()
        return (
            f"Robot(name={self.name!r}, n={self._n}, "
            f"ee=({ee_pos[0]:.3f}, {ee_pos[1]:.3f}, {ee_pos[2]:.3f}))"
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _rotation_from_z(z: np.ndarray) -> np.ndarray:
    """Build rotation matrix R where R[:, 2] == z (z-axis aligned with z)."""
    z = z / (np.linalg.norm(z) + 1e-10)
    # Choose a candidate x: avoid near-parallel
    x0 = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = x0 - np.dot(x0, z) * z
    x = x / (np.linalg.norm(x) + 1e-10)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])
