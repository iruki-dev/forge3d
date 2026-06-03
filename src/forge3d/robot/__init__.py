"""forge3d.robot — kinematic robot arm loader.

Usage::

    import forge3d.robot as f3r
    arm = f3r.load("ur5")
    arm.set_joints([0, -1.57, 0, -1.57, 0, 0])
    pos, R = arm.ee_pose()
"""

from forge3d.robot.presets import make_ur5
from forge3d.robot.robot import Robot

__all__ = ["Robot", "load"]

_REGISTRY: dict[str, object] = {
    "ur5": make_ur5,
}


def load(name: str, **kwargs: object) -> Robot:
    """Load a built-in robot by name.

    Parameters
    ----------
    name   : Robot name (case-insensitive). Currently: ``'ur5'``.
    kwargs : Passed to the robot constructor (e.g. ``base_position``).

    Returns
    -------
    Robot instance with default joint angles q = 0.
    """
    key = name.lower().replace("-", "_")
    if key not in _REGISTRY:
        available = ", ".join(f"'{k}'" for k in _REGISTRY)
        raise ValueError(f"Unknown robot {name!r}. Available: {available}")
    factory = _REGISTRY[key]
    return factory(**kwargs)  # type: ignore[operator]
