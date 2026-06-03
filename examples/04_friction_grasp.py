"""Example 04 — Friction-based pinch grasp (P12 gate: μ-dependent stability).

Two static finger boxes squeeze a dynamic box from ±x sides.
With sufficient friction (μ ≥ μ_critical ≈ 0.45), the box is held against
gravity through contact friction forces.

Shows the contrast:
  μ = 0.9 → STABLE (drop < 1 mm over 2 s)
  μ = 0.1 → SLIPPED

Requires: forge3d with SAT box-box collision + contact spring + split-step.

Run: python examples/04_friction_grasp.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forge3d.sim.world import PhysicsWorld

SPRING_K = 2000.0   # N/m — contact spring for active squeeze force
DURATION = 2.0      # seconds
DT       = 1 / 60


def run_grasp(mu: float) -> float:
    """Simulate a pinch grasp with friction coefficient μ.

    Returns the vertical drop (m) after DURATION seconds.
    """
    world = PhysicsWorld(gravity=[0., 0., -9.81], contact_spring_k=SPRING_K)

    obj_id = world.add_box(
        size=(0.10, 0.10, 0.10), position=(0., 0., 0.50),
        mass=0.5, friction=mu, restitution=0.0,
    )
    # Fingers: static boxes, penetrating object by 5 mm in x
    world.add_static_box(
        size=(0.10, 0.20, 0.20), position=(-0.095, 0., 0.50),
        friction=mu, restitution=0.0,
    )
    world.add_static_box(
        size=(0.10, 0.20, 0.20), position=( 0.095, 0., 0.50),
        friction=mu, restitution=0.0,
    )

    for _ in range(int(DURATION / DT)):
        world.step(dt=DT)

    final_z = next(b for b in world._bodies if b.body_id == obj_id).pos[2]
    return 0.50 - final_z


def main() -> None:
    print("=== P12 Gate: Friction-Based Pinch Grasp ===\n")
    print(f"Contact spring k={SPRING_K} N/m, duration={DURATION}s\n")

    results = {}
    for mu in [0.9, 0.7, 0.5, 0.3, 0.1]:
        drop = run_grasp(mu)
        stable = drop < 0.001
        results[mu] = (drop, stable)
        status = "STABLE ✓" if stable else "SLIPPED ✗"
        print(f"  μ = {mu:.1f}  →  drop = {drop:.4f} m  ({status})")

    print()
    # Gate assertion
    assert results[0.9][1], "G2a FAIL: high-μ grasp should be stable"
    assert not results[0.1][1], "G2b FAIL: low-μ grasp should slip"
    print("G2 gate: PASS ✓  (μ=0.9 stable, μ=0.1 slipped)")


if __name__ == "__main__":
    main()
