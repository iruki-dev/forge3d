"""Base classes for the constraint / joint system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass

# Baumgarte stabilization — position error fed back as velocity bias
BAUMGARTE_BETA = 0.05  # conservative: avoids instability while still correcting drift
BAUMGARTE_SLOP = 1e-3  # 1 mm dead-zone


@dataclass
class JointHandle:
    """Opaque handle returned by World.add_joint().

    Keep it to later call world.remove_joint(handle).
    """

    joint_id: int
    joint_type: str


class Constraint(ABC):
    """Abstract base for all velocity-level constraints.

    Sub-classes must implement ``apply(bodies, dt)``, which modifies
    the body list in-place (replace immutable _Body with updated copies).
    """

    joint_id: int = field(default=-1)

    @abstractmethod
    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        """Apply constraint impulses to the body list.

        Args:
            bodies: Flat list of ``_Body`` objects (may be mutated via replace).
            id_to_idx: Map from body_id to list index.
            dt: Physics time-step in seconds.
        """

    # ── Helper: compute world-frame inertia inverse ───────────────────────────

    @staticmethod
    def _I_world_inv(b: Any) -> np.ndarray:
        """World-frame inverse inertia (3×3).

        For point masses or static bodies returns zero matrix.
        """
        if b.static or b.inertia_inv_local is None:
            return np.zeros((3, 3))
        R = _quat_to_rot(b.quat)
        I_inv_local = b.inertia_inv_local  # diagonal (3×3)
        return R @ I_inv_local @ R.T

    @staticmethod
    def _effective_mass_ball(b_a: Any, r_a: np.ndarray, b_b: Any, r_b: np.ndarray) -> np.ndarray:
        """Effective mass matrix K (3×3) for a point-to-point constraint.

        K = K_a + K_b  where  K_x = 1/m_x * I + [r_x×] * I_x_world_inv * [r_x×]ᵀ
        """

        def _k(b: Any, r: np.ndarray) -> np.ndarray:
            if b.static:
                return np.zeros((3, 3))
            m_inv = 1.0 / b.mass if b.mass > 0 else 0.0
            I_inv = Constraint._I_world_inv(b)
            rx = _skew(r)
            return m_inv * np.eye(3) + rx @ I_inv @ rx.T

        return _k(b_a, r_a) + _k(b_b, r_b)

    @staticmethod
    def _apply_impulse_pair(
        bodies: list[Any],
        id_to_idx: dict[int, int],
        id_a: int,
        id_b: int,
        impulse: np.ndarray,
        r_a: np.ndarray,
        r_b: np.ndarray,
    ) -> None:
        """Apply linear impulse J and angular reactions to body pair."""
        from dataclasses import replace

        if id_a >= 0:
            idx_a = id_to_idx[id_a]
            ba = bodies[idx_a]
            if not ba.static and ba.mass > 0:
                dv = impulse / ba.mass
                I_inv = Constraint._I_world_inv(ba)
                dw = I_inv @ np.cross(r_a, impulse)
                bodies[idx_a] = replace(ba, vel=ba.vel + dv, omega=ba.omega + dw)

        if id_b >= 0:
            idx_b = id_to_idx[id_b]
            bb = bodies[idx_b]
            if not bb.static and bb.mass > 0:
                dv = -impulse / bb.mass
                I_inv = Constraint._I_world_inv(bb)
                dw = I_inv @ np.cross(r_b, -impulse)
                bodies[idx_b] = replace(bb, vel=bb.vel + dv, omega=bb.omega + dw)


# ── Utility functions ─────────────────────────────────────────────────────────


def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    """Quaternion [w,x,y,z] → 3×3 rotation matrix."""
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def _skew(v: np.ndarray) -> np.ndarray:
    """Skew-symmetric cross-product matrix."""
    return np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ]
    )
