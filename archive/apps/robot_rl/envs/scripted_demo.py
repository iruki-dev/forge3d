"""Scripted pick-and-place demonstration (P10 gate).

A hand-crafted joint trajectory demonstrates the weld abstraction:
  Phase 1 – approach: move EE toward the object
  Phase 2 – grasp: trigger weld (object attaches to EE)
  Phase 3 – lift: raise the arm
  Phase 4 – carry: move to target area
  Phase 5 – release: drop the object

Produces: demo.mp4

Run: python apps/robot_rl/envs/scripted_demo.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import imageio
import numpy as np
from apps.robot_rl.envs.pick_place_env import _PhysicsBodyHandle

import forge3d as f3d
import forge3d.robot as f3r
from forge3d.render.hq.renderer import HQRenderer

# ── World setup ───────────────────────────────────────────────────────────────

world = f3d.World(gravity=(0.0, 0.0, -9.81))
world.add_ground(material=f3d.Material(color="ground"))
arm = f3r.load("ur5", base_position=(0.0, 0.0, 0.0))
world.add(arm)

# Object to pick (small blue cube on the ground)
OBJ_POS = np.array([0.30, 0.10, 0.04])
obj = world.add_box(
    size=(0.08, 0.08, 0.08),
    position=tuple(OBJ_POS),
    mass=0.3,
    restitution=0.0,
    friction=0.8,
    material=f3d.Material(color="blue"),
)

# Target: green sphere on the other side
TGT_POS = np.array([-0.30, -0.10, 0.06])
world.add_sphere(
    radius=0.06,
    position=tuple(TGT_POS),
    static=True,
    material=f3d.Material(color="green"),
)

world.set_camera(position=(1.2, -1.6, 0.9), target=(0.0, 0.0, 0.3))

# ── Joint waypoints ───────────────────────────────────────────────────────────
# Each waypoint is (joint_angles, n_steps)
# Computed offline to roughly reach the object and target.
# UR5 at home: EE ≈ (-0.34, -0.11, 0.39)

HOME_Q = np.array([0.0, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0])

# Approach the object: rotate base, adjust shoulder/elbow
APPROACH_Q = np.array([0.35, -1.8, 2.2, -1.8, -np.pi / 2, 0.0])

# Lower to grasp height
GRASP_Q = np.array([0.35, -1.6, 2.4, -2.0, -np.pi / 2, 0.0])

# Lift
LIFT_Q = np.array([0.35, -1.3, 2.0, -1.8, -np.pi / 2, 0.0])

# Carry toward target: rotate base toward negative x/y
CARRY_Q = np.array([-0.35, -1.5, 2.2, -1.8, -np.pi / 2, 0.0])

# Lower to drop height
DROP_Q = np.array([-0.35, -1.7, 2.4, -1.9, -np.pi / 2, 0.0])


def interpolate(q_start: np.ndarray, q_end: np.ndarray, n: int) -> list[np.ndarray]:
    return [q_start + (q_end - q_start) * t / max(1, n - 1) for t in range(n)]


# ── Rendering ─────────────────────────────────────────────────────────────────

renderer = HQRenderer(width=480, height=320, samples=2)
frames: list[np.ndarray] = []


def record_steps(waypoints: list[np.ndarray], dt: float = 1 / 30, render_every: int = 1) -> None:
    for i, q in enumerate(waypoints):
        arm.set_joints(q)
        world.step(dt=dt)
        if i % render_every == 0:
            frames.append(renderer.render(world.snapshot()))


# ── Scripted trajectory ───────────────────────────────────────────────────────

print("Phase 1: Approach object …")
record_steps(interpolate(HOME_Q, APPROACH_Q, 40))

print("Phase 2: Lower to grasp …")
record_steps(interpolate(APPROACH_Q, GRASP_Q, 30))

print("Phase 2b: Grasp (weld) …")
# Use the last robot link body as the EE anchor

ee_link_id = arm._body_ids[-1]
ee_handle = _PhysicsBodyHandle(world._physics, ee_link_id)
world.weld(obj, ee_handle)
print(f"  Grasped!  obj.position = {obj.position.round(3)}")
record_steps([GRASP_Q] * 5)

print("Phase 3: Lift …")
record_steps(interpolate(GRASP_Q, LIFT_Q, 30))

print("Phase 4: Carry to target …")
record_steps(interpolate(LIFT_Q, CARRY_Q, 50))

print("Phase 5: Lower to drop …")
record_steps(interpolate(CARRY_Q, DROP_Q, 30))

print("Phase 5b: Release …")
world.release(obj)
print(f"  Released!  obj.position before drop = {obj.position.round(3)}")

# Let object settle
record_steps([DROP_Q] * 20)

# Back to home
record_steps(interpolate(DROP_Q, HOME_Q, 40))

renderer.close()

# ── Save video ────────────────────────────────────────────────────────────────

OUT = "demo.mp4"
writer = imageio.get_writer(OUT, fps=24)
for f in frames:
    writer.append_data(f)
writer.close()

dist_final = float(np.linalg.norm(np.asarray(obj.position) - TGT_POS))
print(f"\nDone!  {len(frames)} frames → {OUT}")
print(f"Final object position: {np.asarray(obj.position).round(3)}")
print(f"Distance to target:    {dist_final:.3f} m")
