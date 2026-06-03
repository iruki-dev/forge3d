"""Tests for SE3, quaternion, and spatial algebra — both backends."""

from __future__ import annotations

import numpy as np
import pytest

from forge3d.math.quaternion import (
    quat_from_aa,
    quat_from_rot,
    quat_inv,
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
    rot_x,
    rot_y,
    rot_z,
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
    spatial_inertia,
)

# ── SE3 ──────────────────────────────────────────────────────────────────────


class TestSkew:
    def test_antisymmetry(self) -> None:
        v = np.array([1.0, 2.0, 3.0])
        S = skew(v)
        np.testing.assert_allclose(S, -S.T, atol=1e-14)

    def test_cross_product(self) -> None:
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(skew(a) @ b, np.cross(a, b), atol=1e-14)

    def test_round_trip(self) -> None:
        v = np.array([4.0, -2.0, 7.0])
        np.testing.assert_allclose(unskew(skew(v)), v, atol=1e-14)


class TestRotationMatrices:
    @pytest.mark.parametrize("fn", [rot_x, rot_y, rot_z])
    def test_orthogonal(self, fn) -> None:
        R = fn(1.23)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-14)
        np.testing.assert_allclose(np.linalg.det(R), 1.0, atol=1e-14)

    def test_rot_z_known(self) -> None:
        R = rot_z(np.pi / 2)
        # [1,0,0] → [0,1,0]
        np.testing.assert_allclose(R @ [1, 0, 0], [0, 1, 0], atol=1e-14)

    def test_aa_to_rot_consistency(self) -> None:
        R_z = rot_z(0.7)
        R_aa = aa_to_rot([0, 0, 1], 0.7)
        np.testing.assert_allclose(R_z, R_aa, atol=1e-13)


class TestSE3:
    def test_exp_log_roundtrip(self) -> None:
        xi = np.array([0.1, -0.2, 0.3, 0.5, -0.1, 0.4])
        T = exp_se3(xi)
        xi2 = log_se3(T)
        np.testing.assert_allclose(xi2, xi, atol=1e-10)

    def test_exp_identity(self) -> None:
        T = exp_se3(np.zeros(6))
        np.testing.assert_allclose(T, np.eye(4), atol=1e-14)

    def test_inv_se3(self) -> None:
        xi = np.array([0.5, 0.3, -0.2, 1.0, -0.5, 0.8])
        T = exp_se3(xi)
        T_inv = inv_se3(T)
        np.testing.assert_allclose(T @ T_inv, np.eye(4), atol=1e-13)
        np.testing.assert_allclose(T_inv @ T, np.eye(4), atol=1e-13)

    def test_rotation_only_exp(self) -> None:
        # Pure rotation about z by pi/4
        xi = np.array([0.0, 0.0, np.pi / 4, 0.0, 0.0, 0.0])
        T = exp_se3(xi)
        R = rot_of(T)
        np.testing.assert_allclose(R, rot_z(np.pi / 4), atol=1e-13)
        np.testing.assert_allclose(trans_of(T), np.zeros(3), atol=1e-13)

    def test_adjoint_shape(self) -> None:
        T = exp_se3(np.array([0.1, 0.2, 0.3, 1.0, 0.0, 0.0]))
        Ad = adjoint_se3(T)
        assert Ad.shape == (6, 6)

    def test_make_inv_identity(self) -> None:
        T = make_se3(np.eye(3), np.array([1.0, 2.0, 3.0]))
        T_inv = inv_se3(T)
        np.testing.assert_allclose(T @ T_inv, np.eye(4), atol=1e-14)


# ── Quaternion ────────────────────────────────────────────────────────────────


class TestQuaternion:
    def test_normalize(self) -> None:
        q = np.array([2.0, 1.0, 0.0, 0.0])
        q_n = quat_normalize(q)
        np.testing.assert_allclose(np.linalg.norm(q_n), 1.0, atol=1e-14)

    def test_multiply_identity(self) -> None:
        q_id = np.array([1.0, 0.0, 0.0, 0.0])
        q = quat_from_aa([0, 0, 1], 0.5)
        np.testing.assert_allclose(quat_multiply(q_id, q), q, atol=1e-14)
        np.testing.assert_allclose(quat_multiply(q, q_id), q, atol=1e-14)

    def test_rotate_x_axis_by_90_about_z(self) -> None:
        q = quat_from_aa([0, 0, 1], np.pi / 2)
        v = np.array([1.0, 0.0, 0.0])
        v_rot = quat_rotate(q, v)
        np.testing.assert_allclose(v_rot, [0.0, 1.0, 0.0], atol=1e-13)

    def test_quat_from_rot_roundtrip(self) -> None:
        axis = np.array([1.0, 1.0, 0.0]) / np.sqrt(2)
        q = quat_from_aa(axis, 1.2)
        R = quat_to_rot(q)
        q2 = quat_from_rot(R)
        # quaternions can differ by sign and still represent same rotation
        np.testing.assert_allclose(abs(np.dot(q, q2)), 1.0, atol=1e-12)

    def test_quat_to_rot_orthogonal(self) -> None:
        q = quat_from_aa([0, 1, 0], 0.9)
        R = quat_to_rot(q)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-13)
        np.testing.assert_allclose(np.linalg.det(R), 1.0, atol=1e-13)

    def test_slerp_endpoints(self) -> None:
        q1 = quat_from_aa([1, 0, 0], 0.0)
        q2 = quat_from_aa([0, 0, 1], np.pi / 2)
        np.testing.assert_allclose(quat_slerp(q1, q2, 0.0), quat_normalize(q1), atol=1e-12)
        np.testing.assert_allclose(quat_slerp(q1, q2, 1.0), quat_normalize(q2), atol=1e-12)

    def test_inv_times_self_is_identity(self) -> None:
        q = quat_from_aa([1, 2, 3], 1.0)
        q = quat_normalize(q)
        q_id = quat_multiply(q, quat_inv(q))
        np.testing.assert_allclose(q_id[0], 1.0, atol=1e-12)
        np.testing.assert_allclose(q_id[1:], np.zeros(3), atol=1e-12)

    def test_quat_rotate_agrees_with_rot_matrix(self) -> None:
        axis = np.array([1.0, 0.0, 1.0]) / np.sqrt(2)
        angle = 1.1
        q = quat_from_aa(axis, angle)
        R = aa_to_rot(axis, angle)
        v = np.array([3.0, -1.0, 2.0])
        np.testing.assert_allclose(quat_rotate(q, v), R @ v, atol=1e-12)


# ── Spatial algebra ───────────────────────────────────────────────────────────


class TestSpatialTransform:
    def test_Xrot_identity(self) -> None:
        X = Xrot([0, 0, 1], 0.0)
        np.testing.assert_allclose(X, np.eye(6), atol=1e-14)

    def test_Xtrans_structure(self) -> None:
        p = np.array([1.0, 0.0, 0.0])
        X = Xtrans(p)
        # upper-left must be identity
        np.testing.assert_allclose(X[:3, :3], np.eye(3), atol=1e-14)
        # upper-right must be zero
        np.testing.assert_allclose(X[:3, 3:], np.zeros((3, 3)), atol=1e-14)
        # lower-right must be identity
        np.testing.assert_allclose(X[3:, 3:], np.eye(3), atol=1e-14)

    def test_Xpose_rot_only(self) -> None:
        # Featherstone passive convention: X[:3,:3] = E = R^T
        R = rot_z(np.pi / 3)
        X = Xpose(R, np.zeros(3))
        np.testing.assert_allclose(X[:3, :3], R.T, atol=1e-14)
        np.testing.assert_allclose(X[3:, 3:], R.T, atol=1e-14)

    def test_crm_antisymmetry_relation(self) -> None:
        V = np.array([0.3, -0.1, 0.5, 1.0, -0.5, 0.2])
        C = crm(V)
        F = crf(V)
        np.testing.assert_allclose(F, -C.T, atol=1e-14)

    def test_spatial_inertia_symmetry(self) -> None:
        Imat = spatial_inertia(2.0, np.array([0.1, 0.0, 0.0]), np.diag([0.01, 0.02, 0.03]))
        np.testing.assert_allclose(Imat, Imat.T, atol=1e-14)

    def test_spatial_inertia_positive_definite(self) -> None:
        Imat = spatial_inertia(1.0, np.zeros(3), np.diag([0.1, 0.1, 0.1]))
        eigvals = np.linalg.eigvalsh(Imat)
        assert np.all(eigvals > 0), f"Spatial inertia not PD: {eigvals}"

    def test_spatial_inertia_mass_block(self) -> None:
        m = 3.5
        Imat = spatial_inertia(m, np.zeros(3), np.diag([0.1, 0.2, 0.3]))
        np.testing.assert_allclose(Imat[3:, 3:], m * np.eye(3), atol=1e-14)
