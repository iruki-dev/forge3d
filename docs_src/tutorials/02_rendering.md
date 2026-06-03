# Tutorial 2 — Realtime & HQ Rendering

forge3d has two renderers sharing the same API: a **realtime** OpenGL rasteriser and a **high-quality** software ray-tracer. Both consume a `SceneSnapshot` — the physics code never changes.

---

## Realtime viewer

```python
import forge3d as f3d

world = f3d.World()
world.add_ground()
world.add_box(size=(1, 1, 1), position=(0, 0, 3), mass=1.0,
              material=f3d.Material(color="red"))

viewer = f3d.Viewer(world, width=1280, height=720)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()
```

### Viewer controls (default)

| Action | Control |
|--------|---------|
| Orbit  | Left-drag |
| Pan    | Middle-drag |
| Zoom   | Scroll |
| Close  | Esc or window X |

---

## Camera

```python
cam = f3d.OrbitCamera(
    target=(0, 0, 1),     # look-at point
    distance=10,           # metres from target
    azimuth=45,            # degrees
    elevation=30,          # degrees above horizontal
    fov_deg=60,
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    inp = viewer.input
    # Right-drag to orbit
    if inp.mouse_button(1):
        dx, dy = inp.mouse_delta()
        cam.rotate(d_azimuth=dx * 0.5, d_elevation=-dy * 0.5)
    cam.zoom(inp.scroll_delta() * 0.1)
    viewer.set_camera(cam.to_snapshot())
    world.step()
    viewer.draw()
```

---

## Materials

```python
# Built-in colour presets
f3d.Material(color="red")
f3d.Material(color="blue")
f3d.Material(color="gold")
f3d.Material(color="ground")

# RGB tuple [0, 1]
f3d.Material(color=(0.9, 0.4, 0.1))

# PBR parameters
f3d.Material(color="white", roughness=0.1, metallic=0.9)  # mirror-like

# Texture
f3d.Material(texture_path="assets/textures/brick.png")
```

---

## High-quality offline recording

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
ball = world.add_sphere(
    radius=0.4, position=(0, 0, 4.4), mass=1.0, restitution=0.8,
    material=f3d.Material(color="orange"))
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(
    world,
    mode="hq",
    resolution=(1920, 1080),
    samples=64,           # rays per pixel — higher = better quality, slower
    output="bounce.mp4",
)
rec.run(duration=3.0, dt=1/240, fps=60)
```

`samples=64` gives cinema-quality anti-aliasing; `samples=4` is fast preview.

---

## Recording a policy rollout

```python
from apps.robot_rl.envs.reach_env import ReachEnv
from stable_baselines3 import PPO

env   = ReachEnv(render_mode=None)
model = PPO.load("reach_policy")

rec = f3d.Recorder(world, mode="hq", output="rollout.mp4")
rec.run_policy(model, env, duration=5.0)
```

---

## Next: [Robot arm tutorial](03_robot.md)
