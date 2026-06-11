# forge3d.Input & Key

Per-frame keyboard and mouse state snapshots.

---

## Input

::: forge3d.input.Input

---

## Key

::: forge3d.input.Key

---

## InputBuilder (v1.1.0)

::: forge3d.input.InputBuilder

---

## Usage examples

### With `Viewer` (built-in integration)

```python
viewer = f3d.Viewer(world)
while viewer.is_open:
    inp = viewer.input          # updated each draw()
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 8))
    if inp.key_held(f3d.Key.RIGHT):
        world.apply_impulse(ball, (3 * dt, 0, 0))
    dx, dy = inp.mouse_delta()
    cam.rotate(d_azimuth=dx * 0.3)
    world.step()
    viewer.draw()
```

### With a custom window (advanced)

`InputBuilder` exposes low-level callback methods that any windowing library
can drive.  For example, wiring up a raw glfw window manually:

```python
import glfw
import forge3d as f3d

builder = f3d.InputBuilder()

def key_cb(win, key, sc, action, mods):
    from forge3d.render.realtime.window_renderer import _glfw_key_name
    name = _glfw_key_name(key, sc)
    if name:
        if action in (glfw.PRESS, glfw.REPEAT):
            builder.on_key_down(name)
        elif action == glfw.RELEASE:
            builder.on_key_up(name)

glfw.set_key_callback(window, key_cb)

while not glfw.window_should_close(window):
    glfw.poll_events()
    inp = builder.build()

    if inp.key_held(f3d.Key.W):
        car.apply_force(forward * 500)

    world.step()
    builder.end_frame()
```

!!! note "glfw-native input"
    New code should use `f3d.Viewer` directly — glfw callbacks are wired up
    automatically and `InputBuilder` is managed internally.

### Key constants reference

```python
# Letters
f3d.Key.W, f3d.Key.A, f3d.Key.S, f3d.Key.D   # WASD movement

# Arrows
f3d.Key.UP, f3d.Key.DOWN, f3d.Key.LEFT, f3d.Key.RIGHT

# Special
f3d.Key.SPACE, f3d.Key.ESCAPE, f3d.Key.ENTER
f3d.Key.SHIFT, f3d.Key.CTRL, f3d.Key.ALT

# Function keys
f3d.Key.F1 ... f3d.Key.F12

# Raw strings also work
inp.key_held('w')        # same as key_held(f3d.Key.W)
inp.key_pressed('space')
```
