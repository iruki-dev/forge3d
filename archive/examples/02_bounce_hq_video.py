"""Example 02 — Bouncing ball, high-quality raytraced video (P6 gate).

Produces bounce.mp4 using the software ray tracer.
Run: python examples/02_bounce_hq_video.py
"""

import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
world.add_sphere(
    radius=0.4,
    position=(0, 0, 4.4),
    mass=1.0,
    restitution=0.75,
    friction=0.4,
    material=f3d.Material(color="orange"),
)
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))
rec = f3d.Recorder(world, mode="hq", resolution=(480, 320), samples=4, output="bounce.mp4")
rec.run(duration=2.5, dt=1 / 240, fps=24)
print("bounce.mp4 saved.")
