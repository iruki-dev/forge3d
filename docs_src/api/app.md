# forge3d.App

High-level game-loop abstraction using decorators.

::: forge3d.app.App

---

## Example

```python
import forge3d as f3d

app = f3d.App("My World", width=1280, height=720, fps=60)
ball = None

@app.on_start
def setup(world: f3d.World) -> None:
    global ball
    world.add_ground()
    ball = world.add_sphere(radius=0.4, position=(0, 0, 6))

@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 8))

@app.on_render
def render(world: f3d.World, viewer: f3d.Viewer) -> None:
    pass  # custom overlays if needed

app.run()
```
