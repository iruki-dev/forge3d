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

# Emissive glow (lava, neon, sci-fi energy cores)
f3d.Material(color=(1.0, 0.3, 0.0), emissive=3.0)  # glowing orange

# Texture
f3d.Material(texture_path="assets/textures/brick.png")
```

`emissive` is a scalar intensity multiplier on the material colour.
Set to `0.0` (default) for no emission; typical values are `1.0` – `5.0`.

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
from stable_baselines3 import PPO
from forge3d.sim.jax_batch import make_reach_env

env   = make_reach_env()
model = PPO.load("reach_policy")

rec = f3d.Recorder(world, mode="hq", output="rollout.mp4")
rec.run_policy(model, env, duration=5.0)
```

---

## Heightfield terrain rendering (v1.1.0)

Before v1.1.0, `world.add_terrain()` was collision-only — the terrain was invisible.
In v1.1.0, terrain automatically appears as a shaded triangle mesh with shadow casting:

```python
import numpy as np

rng = np.random.default_rng(42)
heights = (
    3.0 * np.sin(np.linspace(0, 2*np.pi, 48))[:, None] *
          np.cos(np.linspace(0, 3*np.pi, 48))[None, :] +
    rng.uniform(-0.3, 0.3, (48, 48))
).astype(np.float32)
heights = np.clip(heights - heights.min(), 0, 8)

world.add_terrain(
    heights=heights,
    cell_size=2.5,
    origin=(-60, -60, 0),
    material=f3d.Material(color=(0.28, 0.42, 0.16), roughness=0.95),
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    world.step()
    viewer.draw()    # terrain rendered as smooth mesh with normals and shadows
```

The terrain mesh is generated lazily on the first render call, cached, and reused every frame.

---

## HUD text overlay (v1.1.0)

`Viewer.draw_text()` renders a text overlay after the 3D scene:

```python
score = 0
while viewer.is_open:
    world.step()
    viewer.draw()                                 # 3D scene

    viewer.draw_text(f"Score: {score}", x=10, y=10, size=24)
    viewer.draw_text("PAUSE", x=640, y=360,
                     size=48, color=(1, 0.8, 0), anchor="center")
    viewer.draw_text("ESC to quit", x=1270, y=10,
                     size=18, anchor="topright")
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `x, y` | `10, 10` | Pixel position |
| `size` | `20` | Font size (px) |
| `color` | `(1,1,1)` | RGB in [0,1] |
| `bg_alpha` | `0.6` | Background box opacity |
| `anchor` | `"topleft"` | `"topleft"` / `"center"` / `"topright"` |

---

## FollowCamera — local frame (v1.1.0)

For vehicle games, use `frame="local"` so the camera always stays behind the body:

```python
car = world.add_box(size=(2, 1, 0.5), position=(0, 0, 0.3), mass=20)

cam = f3d.FollowCamera(
    car,
    offset=(-8, 0, 3),      # 8 m behind, 3 m up (car's local frame)
    frame="local",
    smoothing_hz=8,          # snappy tracking
    fov_deg=60,
)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
    viewer.draw()
```

With `frame="world"` (default), the camera offset is always world-aligned regardless
of where the car points. With `frame="local"`, the camera rotates with the car.

---

## Windowed game viewer (v2.0)

Pass `title` to open a real OS window. The API is identical to the headless
viewer — only the rendering backend changes.

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
car = world.add_box(size=(4, 2, 0.55), position=(0, 0, 0.4), mass=1200,
                    friction=0.05,
                    material=f3d.Material(color=(0.1, 0.4, 0.9)))
car.angular_damping = 4.0

cam = f3d.FollowCamera(car, offset=(-10, 0, 3.5), frame="local",
                       smoothing_hz=9, fov_deg=65)

viewer = f3d.Viewer(world, width=1280, height=720, title="Drive")
while viewer.is_open:
    inp = viewer.input
    if inp.key_held(f3d.Key.W):
        # rotate forward direction by quaternion, project to XY
        import numpy as np
        w, x, y, z = car.orientation
        fwd = np.array([1-2*(y*y+z*z), 2*(x*y+w*z), 0.0])
        fwd /= max(np.linalg.norm(fwd), 1e-6)
        car.apply_force(fwd * 9000)
    if inp.key_held(f3d.Key.A):
        car.apply_torque((0, 0,  8000))
    if inp.key_held(f3d.Key.D):
        car.apply_torque((0, 0, -8000))

    world.step(dt=viewer.dt)
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
    viewer.draw()

    speed = float(np.linalg.norm(car.velocity[:2])) * 3.6
    viewer.draw_text(f"{speed:5.0f} km/h", x=640, y=680, size=32,
                     color=(1, 1, 1), anchor="center")
    viewer.draw_text("W/A/D to drive  ESC to quit",
                     x=10, y=10, size=16, color=(0.8, 0.8, 0.8))
```

**What changes with `title`:**

| Property | Headless (no title) | Windowed (with title) |
|----------|--------------------|-----------------------|
| `viewer.dt` | Fixed `1/60` s | Real wall-clock frame time |
| `viewer.input` | Always empty | Live keyboard + mouse |
| `viewer.is_open` | Frame-count limit | Window open + ESC not pressed |
| `viewer.draw()` | Returns `(H,W,3)` ndarray | Returns `None`, flips display |
| `draw_text()` | One-shot texture per call | Cached; unchanged text is free |

**ESC** and the window close button automatically end the loop.

---

## Next: [Robot arm tutorial](03_robot.md)
