# forge3d.World

The central object of every simulation. It manages rigid bodies, advances physics, and produces `SceneSnapshot`s for rendering.

---

## Class reference

::: forge3d.facade.World
    options:
      members:
        - __init__
        - add_ground
        - add_box
        - add_sphere
        - add_capsule
        - add_mesh
        - add
        - remove
        - clear
        - get_body
        - bodies
        - step
        - snapshot
        - apply_impulse
        - teleport
        - weld
        - release
        - set_camera
        - time

---

## Usage examples

### Basic simulation loop

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
ground = world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

for _ in range(600):        # 10 seconds @ 60 Hz
    world.step(dt=1/60)

print(f"Final z: {box.position[2]:.3f} m")
```

### Managing bodies

```python
bodies_before = len(world.bodies)
world.remove(box)
world.clear()               # remove all dynamic bodies
print(world.time)           # elapsed simulation time (s)
```

### Constraints (weld)

```python
anchor = world.add_box(size=(0.5, 0.5, 0.5), position=(0, 0, 2), mass=1.0)
payload = world.add_sphere(radius=0.3, position=(0, 0, 3), mass=0.5)
world.weld(payload, anchor)     # payload follows anchor
world.step(dt=1/60)
world.release(payload)          # detach
```
