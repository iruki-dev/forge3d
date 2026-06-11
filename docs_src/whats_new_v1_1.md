# What's New in v1.1.0 — Game-Ready Release

v1.1.0 significantly improves the **game development experience**.
15 actionable improvements were implemented from 18 feature requests.

---

## 🏗️ Static Bodies Everywhere

Before v1.1.0, creating a non-moving collidable box required calling an internal API:

```python
# Old — exposed internal _physics layer
world._physics.add_static_box(size=..., position=..., ...)
```

Now all body types support `static=True` and auto-register in `world.bodies`:

```python
# v1.1.0 — clean public API
wall  = world.add_box(size=(10, 0.5, 3), position=(0, 5, 1.5), static=True)
post  = world.add_capsule(radius=0.15, half_length=3, position=(2,0,3), static=True)
shelf = world.add_static_box(size=(4, 0.2, 0.1), position=(0, 0, 2))

print(wall.is_static)   # True
print(shelf in world.bodies)  # True
```

Static bodies are excluded from the collision detection outer loop — they don't slow down the simulation.

---

## ⚡ Runtime Physics Property Setters

Change material properties after body creation:

```python
box = world.add_box(size=(1,1,1), position=(0,0,5), mass=1.0)

# All settable at runtime
box.friction    = 0.02   # turn surface to ice
box.restitution = 0.95   # make it very bouncy

# Per-body velocity damping — applied automatically each world.step()
box.linear_damping  = 1.0   # exponential decay: 63% removed per second
box.angular_damping = 2.0   # 86% of spin removed per second
```

Damping is **dt-corrected** (FPS-independent):

```
v_next = v × exp(−linear_damping × dt)
```

---

## 🌍 Heightfield Terrain Rendering

`world.add_terrain()` now renders as a smooth shaded mesh — shadow casting included:

```python
import numpy as np

heights = (np.sin(np.linspace(0, 4*np.pi, 64))[:, None] *
           np.cos(np.linspace(0, 3*np.pi, 64))[None, :] * 3
          ).astype(np.float32)

world.add_terrain(
    heights=np.clip(heights - heights.min(), 0, 8),
    cell_size=2.0,
    origin=(-64, -64, 0),
    material=f3d.Material(color=(0.28, 0.42, 0.16), roughness=0.95),
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    world.step()
    viewer.draw()   # terrain visible as shaded mesh with shadows ✅
```

Both `RealtimeRenderer` (headless/Xvfb) and `WindowRenderer` (glfw) support terrain rendering.

---

## 📷 FollowCamera Local Frame

For vehicle games, the camera should always sit *behind* the car regardless of direction:

```python
# frame="world" (default): offset stays world-aligned
cam = f3d.FollowCamera(car, offset=(0, -8, 4))
# frame="local": offset rotates with the car body
cam = f3d.FollowCamera(car, offset=(-8, 0, 3), frame="local", smoothing_hz=8)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))   # dt-corrected smoothing
    viewer.draw()
```

The `smoothing_hz` parameter replaces the old per-frame `alpha`, making behaviour identical at any frame rate.

---

## 🔦 Raycast API

Cast a ray and find the first body it hits:

```python
# Ground detection (for suspension simulation)
hit = world.raycast(
    origin=car.position + np.array([0, 0, 0.5]),
    direction=(0, 0, -1),
    max_dist=2.0,
)
on_ground = hit is not None and hit.distance < 0.6

# Line-of-sight check
los = world.raycast(origin=player.position, direction=target_dir, max_dist=50)
can_see_target = los is None or los.distance > 49
```

Returns a `RayHit(body, point, normal, distance)` namedtuple or `None`.

---

## 🎮 InputBuilder — custom window bridge

`InputBuilder` exposes `on_key_down`, `on_key_up`, `on_mouse_move`, `on_mouse_down`, `on_mouse_up`, and `on_scroll` callbacks so any windowing library can drive the standard `f3d.Input` / `f3d.Key` system:

```python
import forge3d as f3d

builder = f3d.InputBuilder()

# Wire callbacks to your windowing system (glfw, sdl2, etc.)
# glfw.set_key_callback(win, lambda w, k, s, a, m: ...)

while running:
    # feed events via builder.on_key_down(name), etc.
    inp = builder.build()

    if inp.key_held(f3d.Key.W):
        car.apply_force(forward * 500)
    if inp.key_pressed(f3d.Key.R):
        world.teleport(car, start_pos)

    world.step()
    builder.end_frame()
```

!!! note "Changed in v2.1"
    Starting in v2.1, the `WindowRenderer` window backend was replaced with **glfw**.
    For new code, use `f3d.Viewer` directly — glfw callbacks are wired automatically.

---

## 💬 Viewer HUD Text

Render text overlays without a separate UI library:

```python
while viewer.is_open:
    world.step()
    viewer.draw()   # 3D scene

    viewer.draw_text(f"★ {stars}/20", x=10, y=10, size=28,
                     color=(1.0, 0.9, 0.1))
    viewer.draw_text("GAME OVER", x=640, y=360,
                     size=64, anchor="center")
    viewer.draw_text("ESC to quit", x=1270, y=10,
                     size=18, anchor="topright")
```

---

## 🔗 Weld Relative Rotation

`world.weld()` now preserves relative orientation between child and parent:

```python
hub   = world.add_box(size=(0.5,0.5,0.5), position=(0,0,5), mass=2)
blade = world.add_box(size=(0.3,6,0.2), position=(0,3,5), mass=1)

# Blade spawned at 90° to hub — weld preserves this angle
world.weld(blade, hub)          # relative rotation auto-computed
# Or specify explicitly:
world.weld(blade, hub, local_rotation=[0.707, 0, 0, 0.707])

# Now as hub spins, blades maintain their angles
world.add_joint("hinge", hub, None, axis=(1,0,0), motor_velocity=1.5)
```

---

## 💾 Joint Serialization

`World.save()` / `World.load()` now includes all joints:

```python
# Save everything — bodies AND joints
world.save("scene.json")

# Load and continue — joints restored automatically
world2 = f3d.World.load("scene.json")
```

Supported: `HingeJoint`, `SpringJoint`, `DistanceJoint`, `BallJoint`, `FixedJoint`, `PrismaticJoint`.

---

## ⚡ Performance: No Double Collision Detection

In v1.0.0, `world.step()` called `detect_contacts()` twice — once for physics, once for event dispatch. v1.1.0 caches contacts from the physics step and reuses them for events:

```
Before: step() → detect_contacts() [physics] + detect_contacts() [events]
After:  step() → detect_contacts() [physics] → cache → events [free]
```

This reduces event dispatch overhead by ~50% in event-heavy scenes.

---

## Migration from v1.0.0

All changes are **backward-compatible**. Existing code runs without modification.

| Old pattern | New pattern (v1.1.0) |
|-------------|----------------------|
| `world._physics.add_static_box(...)` | `world.add_static_box(...)` or `world.add_box(static=True)` |
| Manual `car.set_angular_velocity(v * 0.8)` each frame | `car.angular_damping = 1.2` once |
| `FollowCamera(body, offset=(0,-8,4))` (world-frame only) | Add `frame="local"` for vehicle tracking |
| `alpha=0.1` per-frame smoothing (FPS-dependent) | `smoothing_hz=6.0` (FPS-independent) |
| No terrain in Viewer | Automatic — just `world.add_terrain(...)` |
| `World.save()` drops joints | Joints now included |
