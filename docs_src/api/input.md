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

### With pygame (via InputBuilder, v1.1.0)

`InputBuilder.feed_pygame_event()` bridges pygame events into the standard `f3d.Input` / `f3d.Key` system, so you can use forge3d's input API in pygame-based games:

```python
import pygame
import forge3d as f3d

builder = f3d.InputBuilder()

clock = pygame.time.Clock()
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            break
        builder.feed_pygame_event(event)   # translate to f3d events

    inp = builder.build()

    # Now use the standard forge3d input API
    if inp.key_held(f3d.Key.W):
        car.apply_force(forward * 500)
    if inp.key_pressed(f3d.Key.R):
        world.teleport(car, start_pos)

    world.step()
    builder.end_frame()
    clock.tick(60)
```

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
