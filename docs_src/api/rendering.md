# forge3d.Viewer & Recorder

## Viewer — realtime rendering

::: forge3d.viewer.Viewer
    options:
      members:
        - __init__
        - is_open
        - frame_count
        - input
        - dt
        - draw
        - draw_text
        - set_camera
        - run
        - step_once
        - pause
        - resume
        - close

---

## Windowed mode (v2.0)

Pass `title` to open a real OS window instead of rendering offscreen.
Everything else — `is_open`, `input`, `draw()`, `draw_text()` — works
identically between windowed and headless modes.

```python
viewer = f3d.Viewer(world, width=1280, height=720, title="My Game")
```

### Shadow resolution

The windowed renderer uses `shadow_resolution=1024` by default (raised from 512 in v2.1).
Pass a higher value for sharper close-up shadows:

```python
viewer = f3d.Viewer(
    world,
    width=1920, height=1080,
    title="High Quality",
    shadow_resolution=2048,   # 2K shadow map
)
```

| `shadow_resolution` | Quality | Cost |
|--------------------|---------|------|
| 512 | Low (old default) | Fast |
| 1024 | Medium **(default)** | Moderate |
| 2048 | High | Noticeable on old GPUs |

| Without `title` | With `title` |
|-----------------|--------------|
| Offscreen FBO (headless, CI-safe) | Real OS window via glfw |
| `draw()` returns `(H,W,3)` frame | `draw()` returns `None`, flips to screen |
| `dt` = fixed 1/60 s | `dt` = real measured wall time |
| `is_open` = False after `max_frames` (default 300) | `is_open` = False when window closed **or** `max_frames` reached |
| `input` = always empty | `input` = live keyboard + mouse |

### Game loop with windowed Viewer

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
car = world.add_box(size=(4, 2, 0.5), position=(0, 0, 0.3), mass=1200)
cam = f3d.FollowCamera(car, offset=(-10, 0, 3.5), frame="local")

viewer = f3d.Viewer(world, width=1280, height=720, title="Drive")
while viewer.is_open:
    inp = viewer.input                           # real keyboard / mouse
    if inp.key_held(f3d.Key.W):
        car.apply_force((8000, 0, 0))            # engine force
    world.step(dt=viewer.dt)                     # real wall-clock dt
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
    viewer.draw()                                # render 3D + flip
    viewer.draw_text(f"Speed: {speed:.0f} km/h",
                     x=640, y=660, size=32, anchor="center")
```

**ESC** or the window close button automatically sets `viewer.is_open = False`.

### draw_text caching

`draw_text()` caches GPU resources keyed by `(text, x, y, size, color, anchor)`.
Unchanged elements cost virtually nothing on repeated frames.  Dynamic text
(counters, timers) creates a new texture each frame — keep the number of
changing lines small for maximum performance.

---

## Usage examples

### Simple render loop (headless)

```python
world = f3d.World()
world.add_ground()
world.add_box(size=(1,1,1), position=(0,0,3), mass=1,
              material=f3d.Material(color="red"))

viewer = f3d.Viewer(world, width=1280, height=720)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()
```

### HUD text overlay

```python
while viewer.is_open:
    world.step()
    viewer.draw()                       # 3D scene first

    viewer.draw_text(f"Score: {score}", x=10, y=10, size=24)
    viewer.draw_text("PAUSED", x=640, y=360, size=48,
                     color=(1.0, 0.8, 0.2), anchor="center")
    viewer.draw_text(f"Speed: {speed:.0f} km/h",
                     x=1270, y=10, size=20, anchor="topright")
```

### Terrain rendering

```python
import numpy as np

heights = np.sin(np.linspace(0, 4*np.pi, 32)).reshape(32, 1) \
        * np.ones((1, 32)) * 2
heights = heights.astype(np.float32)

world.add_terrain(heights=heights, cell_size=2.0, origin=(-32,-32,0),
                  material=f3d.Material(color=(0.28, 0.45, 0.18)))

viewer = f3d.Viewer(world)
while viewer.is_open:
    world.step()
    viewer.draw()
```

### Camera control

```python
cam = f3d.OrbitCamera(target=(0,0,1), distance=10, elevation=30)

while viewer.is_open:
    inp = viewer.input
    if inp.mouse_button(1):
        dx, dy = inp.mouse_delta()
        cam.rotate(d_azimuth=dx*0.5, d_elevation=-dy*0.5)
    cam.zoom(inp.scroll_delta() * 0.5)
    viewer.set_camera(cam.to_snapshot())
    world.step()
    viewer.draw()
```

### HQ video recording

```python
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(
    world,
    mode="hq",
    resolution=(1920, 1080),
    samples=64,
    output="scene.mp4",
)
rec.run(duration=5.0, dt=1/240, fps=60)
```

---

## Recorder — offline video capture

::: forge3d.recorder.Recorder
