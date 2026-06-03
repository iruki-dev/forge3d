"""CRBA tests: mass matrix properties and agreement with RNEA column-by-column."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))
from arm_6dof import make_arm_6dof

from forge3d.dynamics.crba import mass_matrix
from forge3d.dynamics.model import make_2dof_arm
from forge3d.dynamics.rnea import compute_mass_matrix as rnea_mass_matrix

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def arm2():
    return make_2dof_arm()


@pytest.fixture
def arm6():
    return make_arm_6dof()


RNG = np.random.default_rng(42)


def _rand_q(n: int) -> np.ndarray:
    return RNG.uniform(-np.pi, np.pi, n)


# ── 2-DOF tests ───────────────────────────────────────────────────────────────


class TestCRBA2DOF:
    def test_symmetric(self, arm2) -> None:
        M = mass_matrix(arm2, np.array([0.3, -0.7]))
        np.testing.assert_allclose(M, M.T, atol=1e-13)

    def test_positive_definite(self, arm2) -> None:
        M = mass_matrix(arm2, np.array([1.0, 0.5]))
        assert np.all(np.linalg.eigvalsh(M) > 0)

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_matches_rnea_column(self, arm2, seed) -> None:
        q = np.random.default_rng(seed).uniform(-np.pi, np.pi, 2)
        M_crba = mass_matrix(arm2, q)
        M_rnea = rnea_mass_matrix(arm2, q)
        np.testing.assert_allclose(M_crba, M_rnea, rtol=1e-10, atol=1e-12)


# ── 6-DOF tests ───────────────────────────────────────────────────────────────


class TestCRBA6DOF:
    def test_shape(self, arm6) -> None:
        M = mass_matrix(arm6, np.zeros(6))
        assert M.shape == (6, 6)

    def test_symmetric(self, arm6) -> None:
        q = _rand_q(6)
        M = mass_matrix(arm6, q)
        np.testing.assert_allclose(M, M.T, atol=1e-12)

    def test_positive_definite(self, arm6) -> None:
        q = _rand_q(6)
        M = mass_matrix(arm6, q)
        assert np.all(np.linalg.eigvalsh(M) > 0)

    @pytest.mark.parametrize("seed", [10, 20, 30])
    def test_matches_rnea_column(self, arm6, seed) -> None:
        q = np.random.default_rng(seed).uniform(-np.pi, np.pi, 6)
        M_crba = mass_matrix(arm6, q)
        M_rnea = rnea_mass_matrix(arm6, q)
        np.testing.assert_allclose(M_crba, M_rnea, rtol=1e-9, atol=1e-11)

    def test_identity_at_zero(self, arm6) -> None:
        """M(0) should be a specific positive-definite matrix — just check PD + symmetry."""
        M = mass_matrix(arm6, np.zeros(6))
        np.testing.assert_allclose(M, M.T, atol=1e-12)
        assert np.all(np.linalg.eigvalsh(M) > 0)
