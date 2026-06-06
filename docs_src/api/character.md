# forge3d.CharacterController

A character controller built on a capsule rigid body with ground detection via
downward raycast. Use `world.add_character()` to create one.

---

## Class reference

::: forge3d.character.CharacterController
    options:
      members:
        - position
        - velocity
        - is_grounded
        - is_airborne
        - move
        - jump
        - glide
        - set_position

---

## Creating a character

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()

cc = world.add_character(
    position=(0, 0, 2),
    height=1.8,       # capsule height (m)
    radius=0.3,       # capsule radius (m)
    mass=70.0,        # kg
    name="player",
    ground_layer_mask=f3d.CollisionLayer.TERRAIN,
)
```

---

## Game loop integration

```python
viewer = f3d.Viewer(world, width=1280, height=720, title="Character Demo")
cam = f3d.FollowCamera(cc._body, offset=(-5, 0, 2.5), frame="local")

while viewer.is_open:
    inp = viewer.input
    dt = viewer.dt

    # Horizontal movement
    dx = float(inp.key_held(f3d.Key.D)) - float(inp.key_held(f3d.Key.A))
    dy = float(inp.key_held(f3d.Key.W)) - float(inp.key_held(f3d.Key.S))

    cc.move(direction=(dx, dy, 0), speed=5.5, dt=dt)

    # Jump only if on the ground
    if inp.key_pressed(f3d.Key.SPACE) and cc.is_grounded:
        cc.jump(impulse=6.0)

    # Slow fall when holding CTRL
    if inp.key_held(f3d.Key.CTRL) and cc.is_airborne:
        cc.glide(target_fall_speed=1.0, dt=dt)

    world.step(dt)
    viewer.set_camera(cam.to_snapshot(dt=dt))
    viewer.draw()

    viewer.draw_text(
        f"Grounded: {cc.is_grounded}  Speed: {cc.velocity[0]:.1f} m/s",
        x=10, y=10, size=18,
    )
```

---

## Properties reference

| Property | Type | Description |
|----------|------|-------------|
| `position` | `ndarray (3,)` | World-space capsule base position |
| `velocity` | `ndarray (3,)` | Linear velocity (m/s) |
| `is_grounded` | `bool` | True when standing on a surface |
| `is_airborne` | `bool` | `not is_grounded` |

---

## Method reference

| Method | Description |
|--------|-------------|
| `move(direction, speed, dt)` | Apply horizontal velocity; direction is automatically normalized |
| `jump(impulse)` | Apply an upward velocity impulse; only effective when grounded |
| `glide(target_fall_speed, dt)` | Dampen downward velocity for a glide / slow-fall effect |
| `set_position(pos)` | Teleport the character to a new world position |

---

## Ground detection

The controller shoots a downward ray of length `height/2 + radius + 0.15 m`
from the capsule centre. `is_grounded` is `True` when this ray hits a body
matching `ground_layer_mask` (default: `CollisionLayer.TERRAIN | CollisionLayer.DEFAULT`).

To stand on non-terrain bodies, adjust the mask:

```python
cc = world.add_character(
    position=(0, 0, 2),
    ground_layer_mask=(
        f3d.CollisionLayer.TERRAIN |
        f3d.CollisionLayer.DEFAULT |
        f3d.CollisionLayer.ENEMY   # can stand on top of enemies
    ),
)
```
