"""JointType enum — type-safe joint type constants for world.add_joint()."""

from __future__ import annotations

from enum import StrEnum


class JointType(StrEnum):
    """Enumeration of supported joint types.

    Pass to :meth:`forge3d.World.add_joint` as ``joint_type``::

        hinge = world.add_joint(JointType.HINGE, door, frame,
                                anchor_a=(-0.5, 0, 0),
                                anchor_b=( 0.5, 0, 0),
                                axis=(0, 0, 1))

    All values are also accepted as plain strings (case-insensitive):
    ``"hinge"`` == ``JointType.HINGE``.
    """

    FIXED = "fixed"  # 0-DOF rigid weld
    BALL = "ball"  # 3-DOF ball-and-socket (shoulder, ball-socket)
    HINGE = "hinge"  # 1-DOF revolute (door hinge, wheel)
    PRISMATIC = "prismatic"  # 1-DOF linear slider (piston)
    DISTANCE = "distance"  # maintains a fixed distance between anchors
    SPRING = "spring"  # spring-damper elastic force

    # Aliases
    REVOLUTE = "hinge"
    SLIDER = "prismatic"
