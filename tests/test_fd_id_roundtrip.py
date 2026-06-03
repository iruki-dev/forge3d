"""Forward dynamics ↔ inverse dynamics roundtrip + energy conservation for 6-DOF."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))
from arm_6dof import make_arm_6dof

from forge3d.dynamics.aba import forward_dynamics_aba
from forge3d.dynamics.crba import mass_matrix
from forge3d.dynamics.model import make_2dof_arm
from forge3d.dynamics.rnea import (
    forward_dynamics,
    inverse_dynamics,
    semi_implicit_euler,
    total_energy,
)

RNG = np.random.default_rng(99)


@pytest.fixture
def arm2():
    return make_2dof_arm()


@pytest.fixture
def arm6():
    return make_arm_6dof()


# ── ID ↔ FD roundtrip ─────────────────────────────────────────────────────────


class TestRoundtrip:
    @pytest.mark.parametrize("seed", range(5))
    def test_2dof_id_fd_roundtrip(self, arm2, seed) -> None:
        """tau = ID(q, qd, qdd)  →  qdd2 = FD(q, qd, tau)  →  qdd2 ≈ qdd."""
        rng = np.random.default_rng(seed)
        q = rng.uniform(-np.pi, np.pi, 2)
        qd = rng.uniform(-2.0, 2.0, 2)
        qdd = rng.uniform(-5.0, 5.0, 2)

        tau = inverse_dynamics(arm2, q, qd, qdd)
        qdd2 = forward_dynamics(arm2, q, qd, tau)
        np.testing.assert_allclose(qdd2, qdd, rtol=1e-10, atol=1e-12)

    @pytest.mark.parametrize("seed", range(5))
    def test_6dof_id_fd_roundtrip_aba(self, arm6, seed) -> None:
        """Same roundtrip but using ABA for forward dynamics."""
        rng = np.random.default_rng(seed + 50)
        q = rng.uniform(-np.pi, np.pi, 6)
        qd = rng.uniform(-2.0, 2.0, 6)
        qdd = rng.uniform(-5.0, 5.0, 6)

        tau = inverse_dynamics(arm6, q, qd, qdd)
        qdd2 = forward_dynamics_aba(arm6, q, qd, tau)
        np.testing.assert_allclose(qdd2, qdd, rtol=1e-8, atol=1e-10)

    def test_mass_matrix_qdd_equals_rnea(self, arm6) -> None:
        """M(q)*qdd = ID(q, 0, qdd) (no velocity, no gravity)."""
        q = RNG.uniform(-np.pi, np.pi, 6)
        qdd = RNG.uniform(-5.0, 5.0, 6)

        M = mass_matrix(arm6, q)
        tau_m = M @ qdd
        tau_id = inverse_dynamics(arm6, q, np.zeros(6), qdd, gravity=np.zeros(3))
        np.testing.assert_allclose(tau_m, tau_id, rtol=1e-9, atol=1e-11)


# ── Energy conservation for 6-DOF ─────────────────────────────────────────────


class TestEnergyConservation6DOF:
    def test_energy_drift_small_no_gravity(self) -> None:
        """Without gravity, energy is purely kinetic and must stay ~constant."""
        arm6 = make_arm_6dof(gravity=np.zeros(3))
        q = np.array([0.3, -0.5, 0.7, -0.2, 0.4, -0.1])
        qd = np.array([0.5, -0.3, 0.2, -0.4, 0.1, 0.3])
        tau = np.zeros(6)

        E0 = total_energy(arm6, q, qd)
        for _ in range(200):
            q, qd = semi_implicit_euler(arm6, q, qd, tau, dt=5e-4)
        E1 = total_energy(arm6, q, qd)

        rel_drift = abs(E1 - E0) / abs(E0)
        assert rel_drift < 0.005, f"Energy drift: {rel_drift:.4f}"

    def test_energy_drift_small_with_gravity(self) -> None:
        """With gravity, semi-implicit Euler should keep energy bounded."""
        arm6 = make_arm_6dof()
        q = np.array([0.3, -0.5, 0.7, -0.2, 0.4, -0.1])
        qd = np.array([0.5, -0.3, 0.2, -0.4, 0.1, 0.3])
        tau = np.zeros(6)

        E0 = total_energy(arm6, q, qd)
        for _ in range(300):
            q, qd = semi_implicit_euler(arm6, q, qd, tau, dt=5e-4)
        E1 = total_energy(arm6, q, qd)

        rel_drift = abs(E1 - E0) / abs(E0)
        # 2 % tolerance: symplectic Euler bounds energy growth, not conserves exactly
        assert rel_drift < 0.02, f"Energy drift with gravity: {rel_drift:.4f}"


# ── Kinematics sanity ────────────────────────────────────────────────────────


class TestKinematics6DOF:
    def test_fk_at_zero_pose(self, arm6) -> None:
        from forge3d.model.kinematics import forward_kinematics

        pos, R = forward_kinematics(arm6, np.zeros(6))
        # End-effector should be somewhere in front of base
        assert np.isfinite(pos).all()
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)

    def test_jacobian_shape(self, arm6) -> None:
        from forge3d.model.kinematics import jacobian

        J = jacobian(arm6, np.zeros(6))
        assert J.shape == (6, 6)

    def test_jacobian_finite_difference(self, arm6) -> None:
        """Numerical FD Jacobian ≈ analytical Jacobian (linear part)."""
        from forge3d.model.kinematics import forward_kinematics, jacobian

        q = RNG.uniform(-0.5, 0.5, 6)
        J = jacobian(arm6, q)

        eps = 1e-6
        J_fd = np.zeros((3, 6))  # only linear (position) part
        pos0, _ = forward_kinematics(arm6, q)
        for j in range(6):
            dq = np.zeros(6)
            dq[j] = eps
            pos1, _ = forward_kinematics(arm6, q + dq)
            J_fd[:, j] = (pos1 - pos0) / eps

        np.testing.assert_allclose(J[3:, :], J_fd, rtol=1e-4, atol=1e-6)
