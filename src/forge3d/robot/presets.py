"""Built-in robot definitions for forge3d.robot.load().

UR5 parameters:
  Source: Universal Robots UR5 datasheet (simplified DH form).
  DH convention used here: T(q=0) = Trans(x,a) · Trans(z,d) · Rot(x,α)
  Joint rotation: Rz(q) applied after tree transform.
"""

from __future__ import annotations

import numpy as np

from forge3d.model.robot_config import LinkConfig, build_model, dh_joint
from forge3d.robot.robot import Robot

# ── UR5-like 6-DOF arm ────────────────────────────────────────────────────────

# (d, a, alpha) — Modified DH parameters in SI units (Universal Robots UR5)
# alpha_i: twist angle between z_{i-1} and z_i measured about x_{i-1}.
# Joint 0 (base) has alpha=0 so its rotation axis stays aligned with the
# world z-axis — spinning the whole arm horizontally.
# Joint 1 (shoulder) has alpha=π/2 to tilt the arm frame 90° for shoulder pitch.
_UR5_DH = [
    (0.0892,  0.0,     0.0      ),  # joint 0 — base rotation (z)
    (0.0,    -0.4250,  np.pi/2  ),  # joint 1 — shoulder
    (0.0,    -0.3922,  0.0      ),  # joint 2 — elbow
    (0.1093,  0.0,     np.pi/2  ),  # joint 3 — wrist 1
    (0.0950,  0.0,    -np.pi/2  ),  # joint 4 — wrist 2
    (0.0823,  0.0,     0.0      ),  # joint 5 — wrist 3
]
_UR5_MASSES = [7.78, 12.93, 3.87, 1.96, 1.96, 0.20]
_UR5_COMS = [
    np.array([0.0, 0.0, 0.1273]),
    np.array([-0.2125, 0.0, 0.0]),
    np.array([-0.1961, 0.0, 0.0]),
    np.array([0.0, 0.0, 0.0546]),
    np.array([0.0, 0.0, 0.0475]),
    np.array([0.0, 0.0, 0.0]),
]
_UR5_INERTIAS = [
    np.diag([0.0315, 0.0315, 0.0219]),
    np.diag([0.4257, 0.4265, 0.0119]),
    np.diag([0.0267, 0.0267, 0.0119]),
    np.diag([0.0072, 0.0072, 0.0051]),
    np.diag([0.0072, 0.0072, 0.0051]),
    np.diag([0.00018, 0.00018, 0.00013]),
]
_UR5_RADII = [0.05, 0.05, 0.04, 0.04, 0.035, 0.030]


def make_ur5(
    gravity: np.ndarray | None = None,
    base_position: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Robot:
    """Build a UR5-like 6-DOF robot arm.

    Parameters
    ----------
    gravity       : Gravity vector (default: [0, 0, -9.81]).
    base_position : World position of the robot base.

    Returns
    -------
    Robot instance with UR5 kinematics and visual parameters.
    """
    joints = []
    links = []
    for i, (d, a, alpha) in enumerate(_UR5_DH):
        joints.append(dh_joint(parent=i - 1, d=d, a=a, alpha=alpha))
        links.append(LinkConfig(mass=_UR5_MASSES[i], com=_UR5_COMS[i], inertia=_UR5_INERTIAS[i]))

    if gravity is None:
        gravity = np.array([0.0, 0.0, -9.81])

    model = build_model(joints, links, gravity=gravity)
    return Robot(
        model=model,
        link_radii=_UR5_RADII,
        name="ur5",
        material="default",
        base_position=base_position,
    )
