"""6-DOF serial arm model — simplified UR5-like parameters.

Topology (DH standard convention, z-up world):
  Joint 1: base rotation, z-axis (vertical)
  Joint 2: shoulder, y-axis
  Joint 3: elbow, y-axis
  Joint 4: wrist1, y-axis
  Joint 5: wrist2, x-axis (or y-axis)
  Joint 6: wrist3, z-axis

These parameters are designed so the same arm can be reproduced exactly in
PyBullet via createMultiBody, enabling closed-loop validation without a URDF.

All units: SI (metres, kilograms, seconds).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.model.robot_config import LinkConfig, build_model, dh_joint

# ── Simplified UR5-like DH parameters ────────────────────────────────────────
# (d, a, alpha)  — standard DH at q=0: T = Trans(x,a) * Trans(z,d) * Rot(x,alpha)

_DH = [
    # d       a       alpha
    (0.0892, 0.0, np.pi / 2),  # joint 1 → link 1
    (0.0, -0.4250, 0.0),  # joint 2 → link 2
    (0.0, -0.3922, 0.0),  # joint 3 → link 3
    (0.1093, 0.0, np.pi / 2),  # joint 4 → link 4
    (0.0950, 0.0, -np.pi / 2),  # joint 5 → link 5
    (0.0823, 0.0, 0.0),  # joint 6 → link 6
]

# ── Link masses (kg) ─────────────────────────────────────────────────────────
_MASSES = [7.78, 12.93, 3.87, 1.96, 1.96, 0.20]

# ── Link inertia tensors (Icm, kg·m²) expressed in each link's local frame ──
# Simplified diagonal values derived from UR5 datasheet.
_INERTIAS = [
    np.diag([0.0314743, 0.0314743, 0.0218756]),  # link 1
    np.diag([0.4256780, 0.4265428, 0.0119429]),  # link 2
    np.diag([0.0266700, 0.0266700, 0.0119429]),  # link 3
    np.diag([0.0071930, 0.0071930, 0.0051089]),  # link 4
    np.diag([0.0071930, 0.0071930, 0.0051089]),  # link 5
    np.diag([0.0001760, 0.0001760, 0.0001321]),  # link 6
]

# ── CoM positions in each link's frame (m) ────────────────────────────────────
# Approximated as midpoint along the DH link length.
_COMS = [
    np.array([0.0, 0.0, 0.1273]),  # link 1 (along z, d=0.0892 above + shoulder)
    np.array([-0.2125, 0.0, 0.0]),  # link 2 (along a=-0.425 → midpoint)
    np.array([-0.1961, 0.0, 0.0]),  # link 3
    np.array([0.0, 0.0, 0.0546]),  # link 4
    np.array([0.0, 0.0, 0.0475]),  # link 5
    np.array([0.0, 0.0, 0.0]),  # link 6
]


def make_arm_6dof(gravity: Any = None) -> Any:
    """Build a 6-DOF UR5-like RigidBodyModel.

    Returns
    -------
    model : RigidBodyModel with 6 revolute joints.
    """

    joints = []
    links = []
    for i, (d, a, alpha) in enumerate(_DH):
        parent = i - 1  # -1 for link 0
        joints.append(dh_joint(parent, d, a, alpha))
        links.append(LinkConfig(mass=_MASSES[i], com=_COMS[i], inertia=_INERTIAS[i]))

    if gravity is None:
        gravity = np.array([0.0, 0.0, -9.81])

    return build_model(joints, links, gravity=gravity)
