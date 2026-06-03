"""Example 03 — UR5 robot arm joint sweep (P7 gate).

Demonstrates forge3d.robot API:
  - Load UR5 arm, add to world
  - Set joint angles programmatically (= slider simulation in headless)
  - Record joint sweep as HQ video → robot_sweep.mp4

Run: python examples/03_robot_interactive.py
"""

import imageio
import numpy as np

import forge3d as f3d
import forge3d.robot as f3r
from forge3d.render.hq.renderer import HQRenderer

# ── World setup ───────────────────────────────────────────────────────────────

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground"))
arm = f3r.load("ur5", base_position=(0, 0, 0))
world.add(arm)
world.set_camera(position=(1.5, -2.0, 1.2), target=(0.0, 0.0, 0.5))

# ── Slider simulation: sweep joint angles ─────────────────────────────────────

N_FRAMES = 48
renderer = HQRenderer(width=480, height=320, samples=2)
frames = []

for i in range(N_FRAMES):
    t = i / N_FRAMES
    arm.set_joint(0, t * np.pi)  # base: 0 → π
    arm.set_joint(1, -np.pi / 2 + t * np.pi / 3)  # shoulder: -90° → -30°
    world.step(dt=1 / 60)
    frame = renderer.render(world.snapshot())
    frames.append(frame)

renderer.close()

# ── Save video ────────────────────────────────────────────────────────────────

writer = imageio.get_writer("robot_sweep.mp4", fps=24)
for f in frames:
    writer.append_data(f)
writer.close()

ee_pos, _ = arm.ee_pose()
print(f"Done — {N_FRAMES} frames → robot_sweep.mp4")
print(f"Final EE: ({ee_pos[0]:.3f}, {ee_pos[1]:.3f}, {ee_pos[2]:.3f}) m")
