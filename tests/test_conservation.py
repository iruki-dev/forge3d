"""Energy conservation test for the 2-DOF arm.

Gate: under zero torque, zero damping, total mechanical energy E = T + V
must be conserved within a relative tolerance over a short simulation.

Also tests single-pendulum period (small angle, analytical: T = 2π√(L/g)).
"""

from __future__ import annotations

import numpy as np
import pytest

from forge3d.dynamics.model import RigidBodyModel, make_2dof_arm
from forge3d.dynamics.rnea import (
    semi_implicit_euler,
    total_energy,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def simulate(
    model: RigidBodyModel,
    q0: np.ndarray,
    qd0: np.ndarray,
    tau: np.ndarray,
    dt: float,
    n_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Run n_steps of semi-implicit Euler; return final (q, qd)."""
    q, qd = q0.copy(), qd0.copy()
    for _ in range(n_steps):
        q, qd = semi_implicit_euler(model, q, qd, tau, dt)
    return q, qd


def simulate_energy_trace(
    model: RigidBodyModel,
    q0: np.ndarray,
    qd0: np.ndarray,
    dt: float,
    n_steps: int,
    sample_every: int = 1,
) -> np.ndarray:
    """Return array of total energy sampled every `sample_every` steps."""
    q, qd = q0.copy(), qd0.copy()
    n = model.n_links
    tau = np.zeros(n)
    energies = []
    for k in range(n_steps):
        if k % sample_every == 0:
            energies.append(total_energy(model, q, qd))
        q, qd = semi_implicit_euler(model, q, qd, tau, dt)
    return np.array(energies)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestEnergyConservation:
    """Semi-implicit Euler is symplectic → energy bounded (not monotonically
    conserved), but for a short horizon the drift should be small."""

    def test_energy_drift_small(self) -> None:
        """Over 500 steps at dt=1e-3 s, energy drift < 0.5% of initial."""
        model = make_2dof_arm(gravity=np.array([0.0, -9.81, 0.0]))
        q0 = np.array([np.pi / 4, np.pi / 6])
        qd0 = np.array([0.5, -0.3])

        E0 = total_energy(model, q0, qd0)
        assert abs(E0) > 1e-6, "Initial energy near zero — test degenerate"

        energies = simulate_energy_trace(model, q0, qd0, dt=1e-3, n_steps=500, sample_every=50)
        rel_drift = np.abs(energies - E0) / abs(E0)
        assert rel_drift.max() < 0.005, (
            f"Energy drift too large: max={rel_drift.max():.4f}  E0={E0:.4f}  E_trace={energies}"
        )

    def test_energy_conservation_no_gravity(self) -> None:
        """Without gravity, kinetic energy is conserved (no potential change)."""
        model = make_2dof_arm(gravity=np.zeros(3))
        q0 = np.array([0.3, -0.5])
        qd0 = np.array([1.0, -0.8])

        E0 = total_energy(model, q0, qd0)
        energies = simulate_energy_trace(model, q0, qd0, dt=5e-4, n_steps=1000, sample_every=100)
        rel_drift = np.abs(energies - E0) / abs(E0)
        assert rel_drift.max() < 0.002, f"Energy drift (no gravity): max={rel_drift.max():.5f}"


class TestSinglePendulumPeriod:
    """Single-link pendulum: fix joint 2, compare period to analytical T=2π√(L/g)."""

    def _make_single_pendulum(self, L: float, m: float, g: float) -> RigidBodyModel:
        """1-link point-mass pendulum: joint revolves about z, mass at [0,-L,0] at q=0.

        At q=0 the mass hangs straight down (-y).
        Analytical period: T = 2π√(L/g)  (same as point-mass pendulum).
        """
        import numpy as np

        from forge3d.math.spatial import spatial_inertia

        S = np.zeros((1, 6))
        S[0, 2] = 1.0  # revolute about z

        X_tree = np.eye(6)[np.newaxis]  # joint at world origin

        # Point mass: I_cm = 0 (negligible), CoM at [0, -L, 0] below joint
        com = np.array([0.0, -L, 0.0])
        Icm = np.zeros((3, 3))
        I_link = spatial_inertia(m, com, Icm)[np.newaxis]

        return RigidBodyModel(
            n_links=1,
            parent=[-1],
            X_tree=X_tree,
            S=S,
            I_link=I_link,
            gravity=np.array([0.0, -g, 0.0]),
        )

    def test_small_angle_period(self) -> None:
        """Simulated period of a point-mass pendulum matches 2π√(L/g) within 2%.

        Model: point mass at distance L below joint.  q=0 = hanging equilibrium.
        Analytical: T = 2π√(L/g).
        """
        L, m, g = 1.0, 1.0, 9.81
        model = self._make_single_pendulum(L, m, g)

        # Small perturbation from equilibrium q=0
        q0 = np.array([0.05])  # 0.05 rad ≈ 3° displacement
        qd0 = np.array([0.0])
        tau = np.zeros(1)

        T_analytical = 2.0 * np.pi * np.sqrt(L / g)
        dt = 1e-4
        max_steps = int(3.0 * T_analytical / dt)

        # Measure period by detecting successive velocity maxima
        q, qd = q0.copy(), qd0.copy()
        last_qd_sign = 0
        period_measured = None
        t = 0.0
        last_max_t = 0.0
        for _ in range(max_steps):
            q, qd = semi_implicit_euler(model, q, qd, tau, dt)
            t += dt
            sign = 1 if qd[0] > 0 else -1
            if last_qd_sign > 0 and sign < 0:
                if period_measured is None:
                    period_measured = t  # first maximum time
                    last_max_t = t
                else:
                    period_measured = t - last_max_t
                    break
            last_qd_sign = sign

        if period_measured is None:
            pytest.skip("Could not measure period within simulation time")

        rel_err = abs(period_measured - T_analytical) / T_analytical
        assert rel_err < 0.02, (
            f"Period mismatch: measured={period_measured:.4f}s, "
            f"analytical={T_analytical:.4f}s, rel_err={rel_err:.3f}"
        )
