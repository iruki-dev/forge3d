# Quickstart

Three 15-line examples to get you running immediately.

---

## 1. Falling box (realtime)

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

---

## 2. Bouncing ball — high-quality video

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
world.add_sphere(radius=0.4, position=(0, 0, 4.4), mass=1.0,
                 restitution=0.8, material=f3d.Material(color="orange"))
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(world, mode="hq", resolution=(1280, 720),
                   samples=16, output="bounce.mp4")
rec.run(duration=3.0, dt=1/240, fps=60)
```

Same `World` code — only the renderer changes. That is the SceneSnapshot contract.

---

## 3. App-style game loop

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

---

## Next steps

- [Physics tutorial](tutorials/01_physics.md) — gravity, collisions, friction
- [Rendering tutorial](tutorials/02_rendering.md) — cameras, lights, materials
- [Robot tutorial](tutorials/03_robot.md) — UR5 FK/IK, joint control
- [RL tutorial](tutorials/04_rl.md) — Gymnasium env, PPO training
