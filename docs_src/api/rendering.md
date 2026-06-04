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

## Recorder — offline video capture

::: forge3d.recorder.Recorder

---

## Usage examples

### Simple render loop

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

### Viewer controls (default)

| Action | Control |
|--------|---------|
| Orbit  | Left-drag |
| Pan    | Middle-drag |
| Zoom   | Scroll |
| Close  | Esc or window X |

### HUD text overlay (v1.1.0)

```python
while viewer.is_open:
    world.step()
    viewer.draw()                       # render 3D scene first

    viewer.draw_text(f"Score: {score}", x=10, y=10, size=24)
    viewer.draw_text("PAUSED", x=640, y=360, size=48,
                     color=(1.0, 0.8, 0.2), anchor="center")
    viewer.draw_text(f"Speed: {speed:.0f} km/h",
                     x=1270, y=10, size=20, anchor="topright")
```

### Terrain rendering (v1.1.0)

Terrain added via `world.add_terrain()` is now automatically rendered:

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
    viewer.draw()   # terrain visible as shaded mesh with shadows
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
    samples=64,           # rays per pixel (quality)
    output="scene.mp4",
)
rec.run(duration=5.0, dt=1/240, fps=60)
```
