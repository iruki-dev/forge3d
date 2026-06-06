# forge3d.ecs — Entity-Component System

The ECS (Entity-Component System) provides a data-driven architecture for building scenes
with reusable, composable behaviours.

---

## Core concepts

| Concept | Description |
|---------|-------------|
| **Entity** | An integer ID with no data of its own. |
| **Component** | A data class attached to an entity (e.g. `Transform`, `Rigidbody`). |
| **System** | Logic that processes all entities with a specific set of components. |
| **EntityWorld** | The container that holds all entities, components, and systems. |

---

## EntityWorld

::: forge3d.ecs.EntityWorld
    options:
      members:
        - create
        - destroy
        - add
        - get
        - has
        - remove_component
        - query
        - step
        - add_system
        - save
        - load

---

## Built-in components

::: forge3d.ecs.Transform

::: forge3d.ecs.Rigidbody

::: forge3d.ecs.Collider

::: forge3d.ecs.MeshRenderer

::: forge3d.ecs.CameraComponent

::: forge3d.ecs.LightComponent

::: forge3d.ecs.Script

---

## Built-in systems

::: forge3d.ecs.PhysicsSystem

::: forge3d.ecs.RenderSystem

::: forge3d.ecs.ScriptSystem

---

## Utilities

::: forge3d.ecs.body_to_entity

::: forge3d.ecs.save_scene

::: forge3d.ecs.load_scene

---

## Usage examples

### Creating entities

```python
import forge3d as f3d

ew = f3d.EntityWorld()

# A dynamic box at height 5
box = ew.create()
ew.add(box, f3d.Transform(position=[0, 0, 5]))
ew.add(box, f3d.Rigidbody(mass=1.0))
ew.add(box, f3d.MeshRenderer(shape="box", size=(1, 1, 1)))
ew.add(box, f3d.Collider(shape="box", size=(1, 1, 1)))

# A static ground plane
ground = ew.create()
ew.add(ground, f3d.Transform(position=[0, 0, 0]))
ew.add(ground, f3d.Rigidbody(mass=0))  # mass=0 → static
ew.add(ground, f3d.Collider(shape="box", size=(100, 100, 0.1)))
```

### Stepping the world

```python
for _ in range(600):           # 10 seconds at 60 Hz
    ew.step(dt=1/60)

tf = ew.get(box, f3d.Transform)
print(f"Box z = {tf.position[2]:.3f}")
```

### Custom script component

```python
class Spinner(f3d.Script):
    speed: float = 2.0

    def update(self, entity, ew, dt):
        tf = ew.get(entity, f3d.Transform)
        tf.rotation[2] += self.speed * dt   # yaw in place

spinner_e = ew.create()
ew.add(spinner_e, f3d.Transform())
ew.add(spinner_e, Spinner(speed=3.0))
```

Scripts are called by `ScriptSystem` every `ew.step()`.

### Query entities by components

```python
# Find all entities that have both Rigidbody and MeshRenderer
for entity, (rb, mr) in ew.query(f3d.Rigidbody, f3d.MeshRenderer):
    print(f"Entity {entity}: mass={rb.mass}, shape={mr.shape}")
```

### Bridge to physics World

```python
world = f3d.World()
body = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

# Wrap an existing Body as an ECS entity
entity = f3d.body_to_entity(ew, body)
tf = ew.get(entity, f3d.Transform)
print(tf.position)   # synced from Body.position
```

### Scene serialization

```python
# Save current scene state
f3d.save_scene(ew, "scene.json")

# Load into a fresh EntityWorld
ew2 = f3d.EntityWorld()
f3d.load_scene(ew2, "scene.json")
```
