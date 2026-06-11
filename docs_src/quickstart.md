# Quickstart

Three 15-line examples to get you running immediately.

---

## 1. Falling box (headless viewer)

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=180)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()

print(f"Box landed at z = {box.position[2]:.3f} m")
```

**What happens:** A 1 m cube falls under gravity and lands on the ground plane.
`Viewer` runs headless (no window) by default; each `draw()` call returns an
`(H, W, 3)` uint8 ndarray you can process or save.

---

## 2. App-style game loop (windowed window)

```python
import forge3d as f3d

app = f3d.App("Physics Sandbox", width=1280, height=720, fps=60)
ball = None

@app.on_start
def setup(world: f3d.World) -> None:
    global ball
    world.add_ground()
    ball = world.add_sphere(radius=0.4, position=(0, 0, 6),
                             material=f3d.Material(color="orange"))

@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 8))

app.run()
```

**What happens:** An OS window opens. Press **Space** to kick the ball upward.
`App` manages the game loop, world, viewer, and input automatically.

---

## 3. High-quality offline video

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
world.add_sphere(
    radius=0.4, position=(0, 0, 4.4), mass=1.0, restitution=0.8,
    material=f3d.Material(color="orange"),
)
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(world, mode="hq", resolution=(1280, 720),
                   samples=16, output="bounce.mp4")
rec.run(duration=3.0, dt=1/240, fps=60)
```

**What happens:** 3 seconds of simulation are rendered offline at full quality
using forge3d's NumPy ray-tracer (no GPU needed) and saved to `bounce.mp4`.
`samples=16` is fast preview; `samples=64` is cinema quality.

---

## 4. ECS (Entity-Component System)

```python
import forge3d as f3d

ew = f3d.EntityWorld()

# Create a dynamic box entity with all components at once
e = ew.create_entity(
    f3d.Transform(position=[0, 0, 5]),
    f3d.Rigidbody(mass=1.0),
    f3d.MeshRenderer(shape="box", size=(1, 1, 1)),
)

# Step physics
for _ in range(60):
    ew.step(dt=1/60)

tf = ew.get_component(e, f3d.Transform)
print(f"Entity z = {tf.position[2]:.3f}")
```

---

## Next steps

- [Physics tutorial](tutorials/01_physics.md) — gravity, collisions, friction, joints, raycasts
- [Rendering tutorial](tutorials/02_rendering.md) — cameras, lights, materials, HUD, terrain
- [Robot tutorial](tutorials/03_robot.md) — UR5 FK/IK, joint control, Jacobian
- [RL tutorial](tutorials/04_rl.md) — Gymnasium env, PPO training, JAX batch stepping
- [API Reference](api/world.md) — complete class and method docs
