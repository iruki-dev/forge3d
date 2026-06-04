# Tutorial 1 — Physics Simulation

This tutorial walks through forge3d's physics features: gravity, rigid bodies, collision, and contact.

---

## Creating a world

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))  # z-up, SI units (m, kg, s)
```

The `World` manages all rigid bodies and advances the simulation.  
Coordinate system: **z-up**, right-hand. Units: metres, kilograms, seconds.

---

## Adding bodies

```python
ground = world.add_ground()           # static infinite plane at z=0
box  = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
ball = world.add_sphere(radius=0.5,  position=(1, 0, 5), mass=0.5)
cap  = world.add_capsule(radius=0.2, half_length=0.5, position=(-1, 0, 5))
```

Every `add_*` call returns a `Body` handle you can query and modify later.

---

## Stepping the simulation

```python
dt = 1.0 / 240          # 240 Hz recommended for contact
for _ in range(2400):   # 10 seconds
    world.step(dt=dt)

print(f"Box position: {box.position}")
print(f"Box velocity: {box.velocity}")
```

---

## Materials — friction & restitution

```python
ice_box = world.add_box(
    size=(1, 1, 1),
    position=(0, 0, 3),
    mass=1.0,
    friction=0.05,          # very slippery
    restitution=0.0,        # no bounce
)

rubber_ball = world.add_sphere(
    radius=0.5,
    position=(0, 0, 5),
    mass=0.2,
    friction=0.8,
    restitution=0.9,        # very bouncy
)
```

---

## Applying forces and impulses

```python
# Continuous force (applied every step)
world.step(dt=1/60)
box.apply_force((10, 0, 0))  # 10 N in +x — must be re-applied each step

# Instantaneous impulse (Δv = impulse / mass)
world.apply_impulse(ball, (0, 0, 5))  # kick ball up

# Teleport (instantly move)
world.teleport(box, position=(0, 0, 10))
```

---

## Querying body state

```python
print(box.position)          # (3,) world-frame position
print(box.velocity)          # (3,) linear velocity m/s
print(box.orientation)       # (4,) quaternion [w, x, y, z]
print(box.angular_velocity)  # (3,) angular velocity rad/s
print(box.is_static)         # bool
print(box.mass)              # float, kg
```

---

## Removing bodies

```python
world.remove(box)            # remove specific body
world.clear()                # remove all dynamic bodies
world.clear(keep_statics=False)  # remove everything
```

---

## Energy conservation check

```python
import numpy as np

world = f3d.World(gravity=(0, 0, -9.81))
ball = world.add_sphere(radius=0.5, position=(0, 0, 5), mass=1.0,
                         friction=0.0, restitution=1.0)

KE0 = 0.5 * ball.mass * np.dot(ball.velocity, ball.velocity)
PE0 = ball.mass * 9.81 * ball.position[2]
E0 = KE0 + PE0

for _ in range(600):
    world.step(dt=1/60)

KE = 0.5 * ball.mass * np.dot(ball.velocity, ball.velocity)
PE = ball.mass * 9.81 * ball.position[2]
E = KE + PE

print(f"Energy drift: {abs(E - E0) / E0 * 100:.2f}%")  # < 1%
```

---

## Static bodies (v1.1.0)

All body types now support `static=True`:

```python
# Before v1.1.0 — required internal API
bid = world._physics.add_static_box(size=(10, 0.5, 3), ...)

# v1.1.0 — clean public API
wall  = world.add_box(size=(10, 0.5, 3), position=(0, 5, 1.5), static=True)
post  = world.add_capsule(radius=0.1, half_length=2.0, position=(3, 0, 2),
                          static=True)
shelf = world.add_static_box(size=(4, 0.2, 0.1), position=(0, 0, 2))
```

Static bodies have zero mass, are never moved by physics, and are automatically
excluded from the outer collision loop — they don't slow down the simulation.

---

## Runtime physics properties (v1.1.0)

`friction` and `restitution` can now be changed after creation:

```python
ice = world.add_box(size=(10, 10, 0.1), position=(0, 0, 0), static=True)
ice.friction = 0.02       # near-frictionless

rubber = world.add_sphere(radius=0.5, position=(0, 0, 3), mass=1)
rubber.restitution = 0.95  # very bouncy
```

---

## Per-body velocity damping (v1.1.0)

Instead of manually zeroing velocity each frame, use damping properties:

```python
car = world.add_box(size=(2, 1, 0.5), position=(0, 0, 0.3), mass=20)

# Applied automatically every world.step()
car.linear_damping  = 1.0   # removes 63% of speed per second
car.angular_damping = 3.0   # removes 95% of spin per second
```

The formula is `v_new = v * exp(-damping * dt)`, which is **FPS-independent**.

---

## Raycast (v1.1.0)

Find which body a ray hits:

```python
# Cast downward from above to detect what's below
hit = world.raycast(origin=(0, 0, 10), direction=(0, 0, -1), max_dist=20)
if hit:
    print(f"Hit: {hit.body.name}")
    print(f"Point: {hit.point}")
    print(f"Normal: {hit.normal}")
    print(f"Distance: {hit.distance:.2f} m")
```

Supported shapes: sphere, box (OBB), capsule (approximate).

---

## Next: [Rendering tutorial](02_rendering.md)
