"""Generate a URDF file for the 6-DOF arm (validation helper only).

Run once to create arm_6dof.urdf, then load it in both PyBullet and our parser.
This ensures both systems use identical geometry/inertia — removing convention guesses.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))

from arm_6dof import _COMS, _DH, _INERTIAS, _MASSES  # noqa: E402

from forge3d.math.se3 import rot_x  # noqa: E402


def _rpy_from_R(R: np.ndarray) -> tuple[float, float, float]:
    """3x3 rotation → roll-pitch-yaw (ZYX convention, in radians)."""
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-6:
        roll = np.arctan2(R[2, 1], R[2, 2])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:
        roll = np.arctan2(-R[1, 2], R[1, 1])
        pitch = np.arctan2(-R[2, 0], sy)
        yaw = 0.0
    return roll, pitch, yaw


def generate_urdf(output_path: str) -> None:
    """Write arm_6dof.urdf to output_path."""
    n = len(_DH)
    lines = ['<?xml version="1.0"?>', '<robot name="arm_6dof">']

    # ── base link (fixed world frame) ────────────────────────────────────────
    lines += [
        '  <link name="base_link">',
        "    <inertial>",
        '      <mass value="0"/>',
        '      <inertia ixx="0" ixy="0" ixz="0" iyy="0" iyz="0" izz="0"/>',
        "    </inertial>",
        "  </link>",
    ]

    for i in range(n):
        link_name = f"link{i + 1}"
        parent_name = "base_link" if i == 0 else f"link{i}"
        joint_name = f"joint{i + 1}"

        d, a, alpha = _DH[i]
        R_joint = rot_x(alpha)
        r, p, y = _rpy_from_R(R_joint)

        mass = _MASSES[i]
        com = _COMS[i]
        Idiag = np.diag(_INERTIAS[i])  # [Ixx, Iyy, Izz]

        # ── joint (connects parent link to this link) ─────────────────────────
        lines += [
            f'  <joint name="{joint_name}" type="revolute">',
            f'    <parent link="{parent_name}"/>',
            f'    <child link="{link_name}"/>',
            # DH transform at q=0: position=[a, 0, d], orientation=Rx(alpha)
            f'    <origin xyz="{a:.6f} 0.0 {d:.6f}" rpy="{r:.6f} {p:.6f} {y:.6f}"/>',
            # DH joint axis = z in joint frame
            '    <axis xyz="0 0 1"/>',
            '    <limit lower="-3.14159" upper="3.14159" effort="300" velocity="10"/>',
            "  </joint>",
        ]

        # ── link (inertia in joint frame, origin = joint) ─────────────────────
        cx, cy, cz = com
        ixx, iyy, izz = Idiag
        lines += [
            f'  <link name="{link_name}">',
            "    <inertial>",
            f'      <origin xyz="{cx:.6f} {cy:.6f} {cz:.6f}" rpy="0 0 0"/>',
            f'      <mass value="{mass:.6f}"/>',
            # Full symmetric inertia tensor; off-diagonals = 0 (diagonal tensor)
            f'      <inertia ixx="{ixx:.8f}" ixy="0" ixz="0"'
            f' iyy="{iyy:.8f}" iyz="0" izz="{izz:.8f}"/>',
            "    </inertial>",
            "  </link>",
        ]

    lines += ["</robot>", ""]
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Written: {output_path}")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "arm_6dof.urdf")
    generate_urdf(out)
