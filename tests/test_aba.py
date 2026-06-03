"""ABA tests: O(n) forward dynamics agrees with CRBA-based forward_dynamics."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))
from arm_6dof import make_arm_6dof

from forge3d.dynamics.aba import forward_dynamics_aba
from forge3d.dynamics.model import make_2dof_arm
from forge3d.dynamics.rnea import forward_dynamics

RNG = np.random.default_rng(7)


@pytest.fixture
def arm2():
    return make_2dof_arm()


@pytest.fixture
def arm6():
    return make_arm_6dof()


class TestABA2DOF:
    @pytest.mark.parametrize("seed", [0, 1, 2, 3])
    def test_matches_crba_fd(self, arm2, seed) -> None:
        rng = np.random.default_rng(seed)
        q = rng.uniform(-np.pi, np.pi, 2)
        qd = rng.uniform(-2.0, 2.0, 2)
        tau = rng.uniform(-5.0, 5.0, 2)

        qdd_aba = forward_dynamics_aba(arm2, q, qd, tau)
        qdd_crba = forward_dynamics(arm2, q, qd, tau)
        np.testing.assert_allclose(qdd_aba, qdd_crba, rtol=1e-9, atol=1e-11, err_msg=f"seed={seed}")

    def test_zero_tau_gives_gravity_response(self, arm2) -> None:
        """At rest (qd=0) with zero torque, acceleration should be gravity-driven."""
        q = np.array([np.pi / 4, np.pi / 6])
        qd = np.zeros(2)
        tau = np.zeros(2)
        qdd = forward_dynamics_aba(arm2, q, qd, tau)
        # Should not be zero for arm in non-trivial pose under gravity
        assert not np.allclose(qdd, 0.0, atol=1e-3), "Expected non-zero gravity response"


class TestABA6DOF:
    @pytest.mark.parametrize("seed", [100, 200, 300])
    def test_matches_crba_fd(self, arm6, seed) -> None:
        rng = np.random.default_rng(seed)
        q = rng.uniform(-np.pi, np.pi, 6)
        qd = rng.uniform(-2.0, 2.0, 6)
        tau = rng.uniform(-10.0, 10.0, 6)

        qdd_aba = forward_dynamics_aba(arm6, q, qd, tau)
        qdd_crba = forward_dynamics(arm6, q, qd, tau)
        np.testing.assert_allclose(qdd_aba, qdd_crba, rtol=1e-8, atol=1e-10, err_msg=f"seed={seed}")

    def test_matches_crba_fd_zero_grav(self, arm6) -> None:
        """Same as above but with zero gravity (cleaner test)."""
        import copy

        arm6_ng = copy.deepcopy(arm6)
        arm6_ng.gravity = np.zeros(3)

        rng = np.random.default_rng(42)
        q = rng.uniform(-np.pi, np.pi, 6)
        qd = rng.uniform(-2.0, 2.0, 6)
        tau = rng.uniform(-10.0, 10.0, 6)

        qdd_aba = forward_dynamics_aba(arm6_ng, q, qd, tau)
        qdd_crba = forward_dynamics(arm6_ng, q, qd, tau)
        np.testing.assert_allclose(qdd_aba, qdd_crba, rtol=1e-9, atol=1e-11)
