# What's New in v2.1.0

v2.1 improves API completeness and developer ergonomics across the board.
All changes are **fully backward-compatible** — existing code runs unchanged.

---

## Bug fixes

### Terrain custom material not passed to renderer

`add_terrain(material=Material(...))` now propagates the material object directly
in the snapshot instead of relying on an ID lookup that could return `None`.

```python
world.add_terrain(
    heights=h,
    cell_size=5.0,
    material=f3d.Material(color=(0.78, 0.60, 0.32), roughness=0.92),
)
snap = world.snapshot()
terrain = snap.terrains[0]
print(terrain.material)   # Material(color=(0.78, 0.60, 0.32), ...)  ← no longer None
```

### Body.name was not settable

```python
head = world.add_sphere(radius=0.21, name="head")
head.name = "player_head"   # now works
```

### world.load() as instance method returned empty world

`World.load(path)` is a classmethod that returns a new `World`. Calling it on
an instance discarded the return value. Use `world.restore(path)` to restore
in-place:

```python
world.restore("checkpoint.json")
print(len(world.bodies))   # bodies from the file
```

---

## New features

### Per-body collision callbacks

Subscribe directly to a body's collision events instead of filtering a global handler.

```python
@player.on_collision_begin
def player_hit(other, event):
    print(f"player hit {other.name}  speed={event.relative_speed:.1f} m/s")

@player.on_collision_end
def player_left(other, event):
    print(f"player separated from {other.name}")
```

### Material.emissive

Materials now carry an emissive intensity that is propagated through the snapshot
to all renderers.

```python
lava  = f3d.Material(color=(1.0, 0.2, 0.0), emissive=4.0)
neon  = f3d.Material(color=(0.0, 0.8, 1.0), emissive=2.5)
steel = f3d.Material(color="default", emissive=0.0)   # default
```

### Transform.quaternion / Transform.matrix4

Access the quaternion and 4×4 model matrix directly from a snapshot body transform,
without manual reconstruction.

```python
snap = world.snapshot()
for body in snap.bodies:
    q = body.transform.quaternion   # [w, x, y, z]
    M = body.transform.matrix4      # (4, 4) column-major model matrix
```

### TriggerZone runtime manipulation

```python
zone = world.add_trigger_zone(position=(0, 0, 0), size=(4, 4, 4))
zone.set_position((10, 20, 0))     # move
zone.set_half_extents((2, 2, 2))   # resize
zone.enabled = False               # pause detection temporarily
```

### Spatial queries

```python
# Multi-hit raycast (sorted by distance)
hits = world.raycast_all(origin=(0, 0, 10), direction=(0, 0, -1), max_dist=20)
for hit in hits:
    print(hit.body.name, f"{hit.distance:.2f} m")

# Sphere overlap
nearby = world.overlap_sphere(center=(5, 0, 1), radius=8.0)
for body in nearby:
    body.apply_force((0, 0, 300))    # explosion push

# Box overlap
in_room = world.overlap_box(center=(0, 0, 2), half_extents=(10, 10, 3))
```

### Fixed timestep accumulator

```python
# Option A — world.update() accumulator (recommended)
world.fixed_dt    = 1 / 120   # physics at 120 Hz
world.max_substeps = 8

while viewer.is_open:
    world.update(viewer.dt)   # physics stable regardless of frame rate
    viewer.draw()

# Option B — explicit substeps
world.step(dt=viewer.dt, substeps=4)   # integrates at dt/4 four times
```

### Character controller

```python
cc = world.add_character(
    position=(0, 0, 2),
    height=1.8,
    radius=0.3,
    mass=70.0,
)

while viewer.is_open:
    inp = viewer.input
    move_x = float(inp.key_held(f3d.Key.D)) - float(inp.key_held(f3d.Key.A))
    move_y = float(inp.key_held(f3d.Key.W)) - float(inp.key_held(f3d.Key.S))
    cc.move(direction=(move_x, move_y, 0), speed=5.5, dt=viewer.dt)
    if inp.key_pressed(f3d.Key.SPACE) and cc.is_grounded:
        cc.jump(impulse=6.0)
    world.step(viewer.dt)
```

### Physics profiler

```python
with world.profiler:
    world.step(dt=1/60)

p = world.profiler.last
print(f"total: {p.total*1000:.2f} ms  contacts: {p.contacts}")

avg = world.profiler.average(n=60)   # 1-second rolling average
```

### JointType enum

```python
from forge3d import JointType

hinge = world.add_joint(
    JointType.HINGE, door, frame,   # equivalent to "hinge" string
    anchor_a=(-0.5, 0, 0), axis=(0, 0, 1),
    limits=(-1.5, 0.0),
)
```

### CollisionLayer.mask_for()

```python
player.collision_mask = f3d.CollisionLayer.mask_for(
    f3d.CollisionLayer.TERRAIN,
    f3d.CollisionLayer.ENEMY,
)
# → player collides only with TERRAIN and ENEMY
```

### Shadow quality improvement

Default shadow map resolution raised from 512² to **1024²** in the windowed renderer.

```python
# Even sharper shadows
viewer = f3d.Viewer(world, title="Demo", shadow_resolution=2048)
```

### Body shape query

```python
capsule = world.add_capsule(radius=0.3, half_length=0.9, position=(0, 0, 2))
print(capsule.shape_type)     # "capsule"
print(capsule.shape_params)   # {'radius': 0.3, 'half_length': 0.9}
R = capsule.rotation_matrix   # (3, 3) rotation matrix (same as orientation quaternion)
```

---

## Migration

All changes are backward-compatible. No code needs to change.

| Old pattern | v2.1 alternative |
|-------------|-----------------|
| `world2 = f3d.World(); world2.load(path)` (broken) | `world2.restore(path)` or `world2 = f3d.World.load(path)` |
| Global callback + manual name filter | `body.on_collision_begin(cb)` |
| `for _ in range(4): world.step(dt/4)` | `world.step(dt, substeps=4)` |
| `"hinge"` string literal | `JointType.HINGE` (strings still work) |
| `terrain_snap.material_id` lookup for custom materials | `terrain_snap.material` (direct object) |
