"""Example 01 — Falling box, realtime render (P4 gate: ≤15 body lines, import forge3d only)."""

import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(
    size=(1, 1, 1),
    position=(0, 0, 8),
    mass=1.0,
    material=f3d.Material(color="red"),
)
viewer = f3d.Viewer(world, mode="realtime", max_frames=90)
while viewer.is_open:
    world.step(dt=1 / 60)
    viewer.draw()
print(f"Done — {viewer.frame_count} frames, box z = {box.position[2]:.2f} m")
