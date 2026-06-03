"""RNEA correctness tests for the 2-DOF planar arm.

Verification gates:
1. RNEA = SymPy Lagrangian derivation (hand-derived equations of motion).
2. Mass matrix is symmetric positive-definite.
3. Backend parity: numpy ≈ jax results (via backend fixture).
"""

from __future__ import annotations

import importlib

import numpy as np
import pytest
import sympy as sp

from forge3d.dynamics.model import make_2dof_arm
from forge3d.dynamics.rnea import compute_mass_matrix, inverse_dynamics

# ── SymPy analytical EOM ──────────────────────────────────────────────────────
# We derive M(q)*qdd + C(q,qd)*qd + G(q) = tau using the Lagrangian method.
# The arm is in the x-y plane; gravity acts in -y direction.
# Joint 1 is at origin; joint 2 is at end of link 1.


def _sympy_eom_2dof(
    L1: float,
    L2: float,
    m1: float,
    m2: float,
    Izz1: float,
    Izz2: float,
    q_num,
    qd_num,
    qdd_num,
    g_num: float,
):
    """Compute tau analytically via SymPy Lagrangian for given numeric q,qd,qdd."""
    q1, q2 = sp.symbols("q1 q2")
    dq1, dq2 = sp.symbols("dq1 dq2")
    ddq1, ddq2 = sp.symbols("ddq1 ddq2")
    g_sym = sp.Symbol("g")

    # CoM positions (x, y) — gravity in -y
    L1c = sp.Rational(1, 2) * L1
    L2c = sp.Rational(1, 2) * L2

    cx1 = L1c * sp.cos(q1)
    cy1 = L1c * sp.sin(q1)
    cx2 = L1 * sp.cos(q1) + L2c * sp.cos(q1 + q2)
    cy2 = L1 * sp.sin(q1) + L2c * sp.sin(q1 + q2)

    # CoM velocities
    vcx1 = sp.diff(cx1, q1) * dq1
    vcy1 = sp.diff(cy1, q1) * dq1
    vcx2 = sp.diff(cx2, q1) * dq1 + sp.diff(cx2, q2) * dq2
    vcy2 = sp.diff(cy2, q1) * dq1 + sp.diff(cy2, q2) * dq2

    # Kinetic energy
    I1_cm_z = Izz1  # already in kg*m^2
    I2_cm_z = Izz2
    T = (
        sp.Rational(1, 2) * m1 * (vcx1**2 + vcy1**2)
        + sp.Rational(1, 2) * I1_cm_z * dq1**2
        + sp.Rational(1, 2) * m2 * (vcx2**2 + vcy2**2)
        + sp.Rational(1, 2) * I2_cm_z * (dq1 + dq2) ** 2
    )
    T = sp.trigsimp(sp.expand(T))

    # Potential energy (gravity in -y)
    V = m1 * g_sym * cy1 + m2 * g_sym * cy2

    # Lagrangian
    L = T - V

    # Equations of motion via Euler-Lagrange
    qs = [q1, q2]
    dqs = [dq1, dq2]
    ddqs = [ddq1, ddq2]
    tau_sym = []
    for qi, dqi, _ddqi in zip(qs, dqs, ddqs, strict=True):
        dL_dqi = sp.diff(L, qi)
        dL_ddqi = sp.diff(L, dqi)
        d_dt_dL_ddqi = sum(
            sp.diff(dL_ddqi, qj) * dqj + sp.diff(dL_ddqi, dqj) * ddqj
            for qj, dqj, ddqj in zip(qs, dqs, ddqs, strict=True)
        )
        eom_i = d_dt_dL_ddqi - dL_dqi
        tau_sym.append(sp.simplify(eom_i))

    # Substitute numeric values
    subs = {
        q1: q_num[0],
        q2: q_num[1],
        dq1: qd_num[0],
        dq2: qd_num[1],
        ddq1: qdd_num[0],
        ddq2: qdd_num[1],
        g_sym: g_num,
    }
    tau_vals = np.array([float(t.subs(subs).evalf()) for t in tau_sym])
    return tau_vals


# ── Parameters for the test arm ───────────────────────────────────────────────

L1, L2 = 1.0, 0.8
m1, m2 = 1.0, 0.8
Izz1_frac, Izz2_frac = 1.0 / 12.0, 1.0 / 12.0
G_VAL = 9.81  # magnitude

# Gravity in -y for the 2-DOF arm test (arm moves in x-y plane, gravity pulls down)
GRAVITY = np.array([0.0, -G_VAL, 0.0])


def _make_arm():
    return make_2dof_arm(
        L1=L1,
        L2=L2,
        m1=m1,
        m2=m2,
        Izz1=Izz1_frac,
        Izz2=Izz2_frac,
        gravity=GRAVITY,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRNEAvsSympy:
    @pytest.mark.parametrize(
        "q, qd, qdd",
        [
            ([0.0, 0.0], [0.0, 0.0], [0.0, 0.0]),
            ([np.pi / 4, np.pi / 6], [1.0, -0.5], [0.5, -0.2]),
            ([-0.3, 0.8], [2.0, -1.0], [-1.0, 0.5]),
            ([np.pi / 2, -np.pi / 3], [0.0, 0.0], [1.0, 1.0]),
        ],
    )
    def test_rnea_equals_sympy(self, q, qd, qdd) -> None:
        """RNEA tau must match SymPy Lagrangian derivation within 1e-8."""
        model = _make_arm()
        q_arr = np.array(q, dtype=float)
        qd_arr = np.array(qd, dtype=float)
        qdd_arr = np.array(qdd, dtype=float)

        tau_rnea = inverse_dynamics(model, q_arr, qd_arr, qdd_arr)
        tau_sym = _sympy_eom_2dof(
            L1,
            L2,
            m1,
            m2,
            Izz1_frac * m1 * L1**2,
            Izz2_frac * m2 * L2**2,
            q_arr,
            qd_arr,
            qdd_arr,
            G_VAL,
        )
        np.testing.assert_allclose(
            tau_rnea, tau_sym, rtol=1e-6, atol=1e-8, err_msg=f"q={q}, qd={qd}, qdd={qdd}"
        )


class TestMassMatrix:
    def test_symmetric(self) -> None:
        model = _make_arm()
        q = np.array([0.3, -0.5])
        M = compute_mass_matrix(model, q)
        np.testing.assert_allclose(M, M.T, atol=1e-12)

    def test_positive_definite(self) -> None:
        model = _make_arm()
        q = np.array([1.0, 0.5])
        M = compute_mass_matrix(model, q)
        eigvals = np.linalg.eigvalsh(M)
        assert np.all(eigvals > 0), f"Mass matrix not PD: eigvals={eigvals}"

    def test_matches_sympy_mass_matrix(self) -> None:
        """M(q) from RNEA matches SymPy mass matrix."""
        model = _make_arm()
        q = np.array([0.4, -0.6])

        # Extract M via SymPy (columns via tau = M*e_j when qd=qdd=0 except qdd_j=1)
        M_rnea = compute_mass_matrix(model, q)

        I1_cm_z = Izz1_frac * m1 * L1**2
        I2_cm_z = Izz2_frac * m2 * L2**2

        M_sym_cols = []
        for j in range(2):
            qdd_j = np.zeros(2)
            qdd_j[j] = 1.0
            col = _sympy_eom_2dof(
                L1,
                L2,
                m1,
                m2,
                I1_cm_z,
                I2_cm_z,
                q,
                np.zeros(2),
                qdd_j,
                0.0,
            )
            M_sym_cols.append(col)
        M_sym = np.column_stack(M_sym_cols)
        np.testing.assert_allclose(M_rnea, M_sym, rtol=1e-6, atol=1e-9)


class TestBackendParity:
    """numpy and jax backends must give identical tau within float64 tolerance."""

    def test_tau_backend_parity(self, backend: str) -> None:
        import forge3d.backend as bk

        importlib.reload(bk)

        model = _make_arm()
        q = np.array([0.5, -0.3])
        qd = np.array([1.2, -0.4])
        qdd = np.array([0.8, 0.1])

        tau_rnea = inverse_dynamics(model, q, qd, qdd)
        tau_sym = _sympy_eom_2dof(
            L1,
            L2,
            m1,
            m2,
            Izz1_frac * m1 * L1**2,
            Izz2_frac * m2 * L2**2,
            q,
            qd,
            qdd,
            G_VAL,
        )
        np.testing.assert_allclose(
            tau_rnea, tau_sym, rtol=1e-6, atol=1e-8, err_msg=f"backend={backend}"
        )
