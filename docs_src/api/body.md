# forge3d.Body

A handle to a single rigid body in the simulation. Returned by every `World.add_*` call.

---

## Class reference

::: forge3d.facade.Body
    options:
      members:
        - position
        - velocity
        - orientation
        - angular_velocity
        - rotation_matrix
        - name
        - is_static
        - is_sleeping
        - mass
        - shape_type
        - shape_params
        - friction
        - restitution
        - linear_damping
        - angular_damping
        - collision_layer
        - collision_mask
        - apply_force
        - apply_torque
        - set_position
        - set_orientation
        - set_velocity
        - set_angular_velocity
        - on_collision_begin
        - on_collision_end

---

## Usage examples

### Reading state

```python
box = world.add_box(size=(1,1,1), position=(0,0,5), mass=2.0)
print(box.position)     # array([0., 0., 5.])
print(box.mass)         # 2.0
print(box.is_static)    # False
print(box.is_sleeping)  # False
```

### Runtime setters (v1.1.0)

```python
# Change physics material at runtime
box.friction    = 0.05   # ice-slippery (default: 0.5)
box.restitution = 0.95   # very bouncy  (default: 0.3)
```

### Velocity damping (v1.1.0)

```python
# Exponential decay — dt-corrected, FPS-independent
box.linear_damping  = 1.0  # removes 63% of speed per second
box.angular_damping = 2.0  # removes 86% of spin per second

# Applied automatically every world.step()
```

| `linear_damping` | Speed remaining after 1 s |
|-----------------|--------------------------|
| 0.0 | 100% (no damping) |
| 0.5 | 61% |
| 1.0 | 37% |
| 2.0 | 14% |

### Applying forces

```python
box.apply_force((0, 0, 50))    # 50 N upward (reset each step)
box.apply_torque((0, 0, 10))   # 10 N·m yaw torque

world.step(dt=1/60)
print(box.velocity)
```

### Runtime name change

```python
head = world.add_sphere(radius=0.21, position=(0,0,1.8), name="head")
head.name = "player_head"   # settable at any time
print(head.name)             # "player_head"
```

### Shape query

```python
capsule = world.add_capsule(radius=0.3, half_length=0.9, position=(0,0,2))
print(capsule.shape_type)     # "capsule"
print(capsule.shape_params)   # {'radius': 0.3, 'half_length': 0.9}

# Rotation as 3×3 matrix (alternative to .orientation quaternion)
R = capsule.rotation_matrix   # np.ndarray (3, 3)
```

### Per-body collision callbacks

```python
player = world.add_capsule(radius=0.3, half_length=0.9, name="player")
floor  = world.add_ground()

@player.on_collision_begin
def hit(other, event):
    print(f"player hit {other.name}  speed={event.relative_speed:.1f} m/s")

@player.on_collision_end
def left(other, event):
    print(f"player separated from {other.name}")

# Callbacks fire automatically inside world.step()
```

### Collision layers

```python
from forge3d import CollisionLayer

player = world.add_sphere(radius=0.5, position=(0,0,3), mass=1)
player.collision_layer = CollisionLayer.PLAYER
player.collision_mask  = CollisionLayer.mask_for(
    CollisionLayer.TERRAIN,
    CollisionLayer.ENEMY,
)  # collide only with terrain and enemies

ghost = world.add_sphere(radius=1.0, position=(5,0,0), mass=0.1)
ghost.collision_layer = CollisionLayer.NONE   # no collision
```
