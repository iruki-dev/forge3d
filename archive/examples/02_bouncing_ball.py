"""Example 02 — Bouncing ball with restitution and friction.

Demonstrates P5 collision/contact: sphere bounces on ground, settles.
Run: python examples/02_bouncing_ball.py
"""

import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
ball = world.add_sphere(
    radius=0.3,
    position=(0, 0, 5),
    mass=1.0,
    restitution=0.7,
    friction=0.4,
    material=f3d.Material(color="blue"),
)
viewer = f3d.Viewer(world, mode="realtime", max_frames=180)
while viewer.is_open:
    world.step(dt=1 / 120)
    viewer.draw()
print(f"Done — {viewer.frame_count} frames, ball z = {ball.position[2]:.3f} m")
