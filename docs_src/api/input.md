# forge3d.Input & Key

## Input

Per-frame keyboard and mouse state snapshot.

::: forge3d.input.Input

---

## Key

Named constants for keyboard keys.

::: forge3d.input.Key

---

## Example

```python
viewer = f3d.Viewer(world)
while viewer.is_open:
    inp = viewer.input
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 5))
    if inp.key_held(f3d.Key.RIGHT):
        world.apply_impulse(ball, (0.1, 0, 0))
    dx, dy = inp.mouse_delta()
    cam.rotate(d_azimuth=dx * 0.3)
    world.step()
    viewer.draw()
```
