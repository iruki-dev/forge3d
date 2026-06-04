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
        - add_static_box
        - add_sphere
        - add_capsule
        - add_mesh
        - add_terrain
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
        - add_joint
        - remove_joint
        - set_camera
        - time
        - raycast
        - save
        - load
        - on_collision_begin
        - on_collision_stay
        - on_collision_end
        - add_collision_handler
        - ignore_collision
        - add_trigger_zone

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

### Static bodies (v1.1.0)

```python
# All three create non-moving, collidable geometry — no mass needed
wall  = world.add_box(size=(10, 0.5, 3), position=(0, 5, 1.5), static=True)
cap   = world.add_capsule(radius=0.2, half_length=2, position=(0, 0, 3), static=True)
shelf = world.add_static_box(size=(4, 0.2, 0.1), position=(0, 0, 2))
```

### Managing bodies

```python
world.remove(box)
world.clear(keep_statics=True)   # remove dynamics only
print(world.time)                # elapsed simulation time (s)
```

### Weld constraints with rotation (v1.1.0)

```python
parent = world.add_box(size=(2, 2, 1), position=(0, 0, 2), mass=10)
child  = world.add_box(size=(0.5, 0.5, 0.5), position=(1, 0, 2), mass=0.5)

# Classic weld — child follows parent position and orientation
world.weld(child, parent)

# Weld with fixed relative rotation (e.g. angled windmill blade at 90°)
world.weld(blade, hub, local_rotation=[0.707, 0, 0, 0.707])  # [w, x, y, z]
```

### Raycast (v1.1.0)

```python
hit = world.raycast(origin=(0, 0, 10), direction=(0, 0, -1), max_dist=15)
if hit:
    print(f"Hit {hit.body.name} at distance {hit.distance:.2f} m")
    print(f"Contact point: {hit.point}")
    print(f"Surface normal: {hit.normal}")
```

### Heightfield terrain

```python
import numpy as np

heights = np.random.default_rng(42).uniform(0, 3, (32, 32)).astype(np.float32)
terrain = world.add_terrain(
    heights=heights,
    cell_size=2.0,
    origin=(-32, -32, 0),
    material=f3d.Material(color=(0.3, 0.45, 0.2), roughness=0.9),
)
# terrain is now visible in Viewer (v1.1.0) and collidable (sphere+box vs heightfield).
```

### Joints

```python
hinge = world.add_joint(
    "hinge", door, frame,
    anchor_a=(-0.5, 0, 0), anchor_b=(0, 0, 0),
    axis=(0, 0, 1),
    limits=(-1.5, 0.0),
    motor_velocity=1.0,
    motor_max_torque=30.0,
)
spring = world.add_joint(
    "spring", box, ceiling,
    stiffness=200.0, damping=10.0, rest_length=2.0,
)
world.remove_joint(hinge)
```

### Collision events

```python
@world.on_collision_begin
def hit(event: f3d.CollisionEvent) -> None:
    print(event.body_a.name, "->", event.body_b.name,
          f"impact={event.relative_speed:.1f} m/s")

goal = world.add_trigger_zone(position=(5, 0, 0.5), size=(1, 1, 1))

@goal.on_enter
def scored(body: f3d.Body) -> None:
    print(f"Goal: {body.name}")
```

### Serialization (joints included since v1.1.0)

```python
world.save("checkpoint.json")          # bodies + joints
world2 = f3d.World.load("checkpoint.json")
```
