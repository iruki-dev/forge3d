"""forge3d.math — SE3, quaternion, spatial vector algebra."""

from forge3d.math.quaternion import (
    quat_from_aa,
    quat_from_rot,
    quat_multiply,
    quat_normalize,
    quat_rotate,
    quat_slerp,
    quat_to_rot,
)
from forge3d.math.se3 import (
    aa_to_rot,
    adjoint_se3,
    exp_se3,
    inv_se3,
    log_se3,
    make_se3,
    rot_of,
    skew,
    trans_of,
    unskew,
)
from forge3d.math.spatial import (
    Xpose,
    Xrot,
    Xtrans,
    crf,
    crm,
    kinetic_energy_spatial,
    spatial_inertia,
)

__all__ = [
    "quat_from_aa",
    "quat_from_rot",
    "quat_multiply",
    "quat_normalize",
    "quat_rotate",
    "quat_slerp",
    "quat_to_rot",
    "aa_to_rot",
    "adjoint_se3",
    "exp_se3",
    "inv_se3",
    "log_se3",
    "make_se3",
    "rot_of",
    "skew",
    "trans_of",
    "unskew",
    "Xpose",
    "Xrot",
    "Xtrans",
    "crf",
    "crm",
    "kinetic_energy_spatial",
    "spatial_inertia",
]
