"""forge3d constraint / joint system.

All constraints use velocity-level Sequential Impulse with
Baumgarte position-error stabilization.

Supported joint types
---------------------
FixedJoint      — rigid weld (0 DOF)
BallJoint       — ball-and-socket (3 rotational DOF)
HingeJoint      — revolute (1 rotational DOF) with optional limits + motor
PrismaticJoint  — slider (1 translational DOF) with optional limits + motor
DistanceJoint   — maintain distance between two anchor points
SpringJoint     — spring-damper force element (not a hard constraint)
"""

from forge3d.constraints.base import Constraint, JointHandle
from forge3d.constraints.joint_type import JointType
from forge3d.constraints.joints import (
    BallJoint,
    DistanceJoint,
    FixedJoint,
    HingeJoint,
    PrismaticJoint,
    SpringJoint,
)

__all__ = [
    "Constraint",
    "JointHandle",
    "JointType",
    "FixedJoint",
    "BallJoint",
    "HingeJoint",
    "PrismaticJoint",
    "DistanceJoint",
    "SpringJoint",
]
