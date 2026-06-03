"""PyBullet comparison — validation/pybullet_compare.py.

Both our engine and PyBullet load the SAME URDF file (arm_6dof.urdf generated
by urdf_gen.py).  This guarantees identical geometry and inertial parameters.

Comparison metric: joint accelerations qdd under the same (q, qd, tau).

  Our engine  : ABA forward dynamics
  PyBullet    : calculateInverseDynamics (bias) + calculateMassMatrix → solve

Usage:
    python validation/pybullet_compare.py

IMPORTANT: pybullet is only imported here, never in src/forge3d/.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))

import pybullet  # noqa: E402 (only in validation/)
import pybullet_data  # noqa: E402

from forge3d.dynamics.aba import forward_dynamics_aba  # noqa: E402
from forge3d.model.urdf_loader import load_urdf  # noqa: E402

URDF_PATH = os.path.join(os.path.dirname(__file__), "arm_6dof.urdf")


# ── PyBullet setup ────────────────────────────────────────────────────────────


def setup_pybullet() -> tuple[int, int]:
    """Create headless PyBullet client, load the arm URDF, and override inertia.

    PyBullet's loadURDF ignores the <inertia> tag when there are no collision
    shapes. We override the inertia tensors via changeDynamics after loading.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))
    from arm_6dof import _INERTIAS, _MASSES  # noqa: PLC0415

    phys = pybullet.connect(pybullet.DIRECT)
    pybullet.setGravity(0, 0, -9.81, physicsClientId=phys)
    pybullet.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=phys)

    robot_id = pybullet.loadURDF(
        URDF_PATH,
        basePosition=[0, 0, 0],
        baseOrientation=[0, 0, 0, 1],
        useFixedBase=True,
        physicsClientId=phys,
    )

    # Override link inertia (PyBullet doesn't read <inertia> without collision shapes)
    n = len(_INERTIAS)
    for i in range(n):
        Idiag = np.diag(_INERTIAS[i]).tolist()
        pybullet.changeDynamics(
            robot_id,
            i,
            mass=float(_MASSES[i]),
            localInertiaDiagonal=Idiag,
            physicsClientId=phys,
        )

    return phys, robot_id


def pybullet_qdd(
    phys: int,
    robot_id: int,
    q: np.ndarray,
    qd: np.ndarray,
    tau: np.ndarray,
) -> np.ndarray:
    """Compute forward dynamics qdd via PyBullet.

    Method: qdd = M^{-1} * (tau - C_G)
    where C_G = calculateInverseDynamics(q, qd, 0)  (Coriolis + gravity)
          M   = calculateMassMatrix(q)
    """
    n = len(q)

    for i in range(n):
        pybullet.resetJointState(robot_id, i, float(q[i]), float(qd[i]), physicsClientId=phys)

    C_G = np.array(
        pybullet.calculateInverseDynamics(
            robot_id,
            q.tolist(),
            qd.tolist(),
            [0.0] * n,
            physicsClientId=phys,
        )
    )
    M = np.array(
        pybullet.calculateMassMatrix(
            robot_id,
            q.tolist(),
            physicsClientId=phys,
        )
    )
    return np.linalg.solve(M, tau - C_G)


# ── Comparison ────────────────────────────────────────────────────────────────


def run_validation(n_random: int = 50, atol: float = 1e-3, rtol: float = 1e-2) -> bool:
    """Compare qdd between our ABA and PyBullet over n_random random configs.

    Returns True if all samples pass within (atol, rtol) tolerances.
    """
    if not os.path.exists(URDF_PATH):
        print(f"ERROR: URDF not found at {URDF_PATH}")
        print("Run: python validation/urdf_gen.py  first.")
        return False

    # Load arm into our engine from the same URDF
    model = load_urdf(URDF_PATH, gravity=np.array([0.0, 0.0, -9.81]))
    n = model.n_links
    print(f"Loaded arm: {n} DOF")

    phys, robot_id = setup_pybullet()
    print(f"PyBullet robot ID: {robot_id}")

    rng = np.random.default_rng(2026)
    n_pass = 0

    print(f"\nRunning {n_random} random comparisons (atol={atol}, rtol={rtol}) ...")
    print(f"{'Sample':>6}  {'max_abs':>10}  {'max_rel':>10}  {'status':>6}")
    print("-" * 42)

    for i in range(n_random):
        q = rng.uniform(-np.pi, np.pi, n)
        qd = rng.uniform(-1.0, 1.0, n)
        tau = rng.uniform(-5.0, 5.0, n)

        qdd_ours = forward_dynamics_aba(model, q, qd, tau)
        qdd_pb = pybullet_qdd(phys, robot_id, q, qd, tau)

        diff = np.abs(qdd_ours - qdd_pb)
        denom = np.abs(qdd_pb) + 1e-6
        max_abs = float(diff.max())
        max_rel = float((diff / denom).max())
        ok = max_abs < atol and max_rel < rtol

        status = "PASS" if ok else "FAIL"
        print(f"{i:>6}  {max_abs:>10.4e}  {max_rel:>10.4e}  {status:>6}")

        if ok:
            n_pass += 1
        else:
            print(f"         ours: {np.round(qdd_ours, 3)}")
            print(f"         pb:   {np.round(qdd_pb, 3)}")

    pybullet.disconnect(phys)

    n_fail = n_random - n_pass
    print("-" * 42)
    print(f"\nResult: {n_pass}/{n_random} passed, {n_fail} failed.")
    print(f"Status: {'PASS ✓' if n_fail == 0 else 'FAIL ✗'}")
    return n_fail == 0


if __name__ == "__main__":
    ok = run_validation()
    sys.exit(0 if ok else 1)
