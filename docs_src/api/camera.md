# forge3d.Camera

Two camera controllers that produce `CameraSnapshot` for the `Viewer`.

---

## OrbitCamera

::: forge3d.camera.OrbitCamera

---

## FollowCamera

::: forge3d.camera.FollowCamera

---

## Usage examples

### OrbitCamera — orbit around a target

```python
cam = f3d.OrbitCamera(target=(0, 0, 1), distance=10, elevation=30)

while viewer.is_open:
    inp = viewer.input
    if inp.mouse_button(1):                     # right-drag to orbit
        dx, dy = inp.mouse_delta()
        cam.rotate(d_azimuth=dx * 0.4, d_elevation=-dy * 0.4)
    cam.zoom(inp.scroll_delta() * 0.5)
    viewer.set_camera(cam.to_snapshot())
    world.step()
    viewer.draw()
```

### FollowCamera — world-frame offset (default)

```python
ball = world.add_sphere(radius=0.5, position=(0,0,3), mass=1)

cam = f3d.FollowCamera(ball, offset=(0, -8, 4), smoothing_hz=6)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
    viewer.draw()
```

### FollowCamera — local frame (vehicle camera) (v1.1.0)

```python
car = world.add_box(size=(2, 1, 0.5), position=(0, 0, 0.3), mass=20)

# Camera always sits 10 m behind and 3 m above the car,
# regardless of which direction the car is facing.
cam = f3d.FollowCamera(
    car,
    offset=(-10, 0, 3),   # local-frame: X=back, Z=up
    frame="local",
    smoothing_hz=8.0,      # snappier (default: 6.0)
    fov_deg=60.0,
)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))
    viewer.draw()
```

### Smoothing comparison

| Parameter | Meaning | Best for |
|-----------|---------|----------|
| `frame="world"` | Offset stays world-aligned | Ball, spacecraft, top-down |
| `frame="local"` | Offset rotates with the body | Car, plane, FPS |
| `smoothing_hz=2` | Slow, cinematic lag | Cutscenes |
| `smoothing_hz=6` | Default, natural | Most games |
| `smoothing_hz=20` | Near-instant snap | Action games |
