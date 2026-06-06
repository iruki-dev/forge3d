# forge3d.scene — Scene Management

The scene module provides hierarchical scene nodes, prefab templates, and a scene
manager for organizing complex game worlds.

---

## Classes

::: forge3d.scene.SceneNode

::: forge3d.scene.Prefab

::: forge3d.scene.SceneManager

---

## Usage examples

### Build a scene hierarchy

```python
import forge3d as f3d
import numpy as np

sm = f3d.SceneManager()
world = f3d.World()

# Root node (the scene root is always implicitly present)
root = sm.root

# Create a car node
car_node = f3d.SceneNode(name="car")
car_node.position = np.array([0.0, 0.0, 0.5])
sm.add(car_node, parent=root)

# Attach wheels as children — they inherit the car's transform
for i, offset in enumerate([( 1.2, 0.6, 0), ( 1.2, -0.6, 0),
                              (-1.2, 0.6, 0), (-1.2, -0.6, 0)]):
    wheel = f3d.SceneNode(name=f"wheel_{i}")
    wheel.position = np.array(offset)
    sm.add(wheel, parent=car_node)
```

### Prefab — reusable entity template

```python
# Define a tree prefab once
tree_prefab = f3d.Prefab(name="pine_tree")
tree_prefab.add_body(
    shape=f3d.Shape.box(size=(0.3, 0.3, 3.0)),
    material=f3d.Material(color=(0.4, 0.25, 0.1)),  # trunk
)
tree_prefab.add_body(
    shape=f3d.Shape.box(size=(2.0, 2.0, 2.5)),
    material=f3d.Material(color=(0.1, 0.5, 0.15)),  # canopy
    offset=(0, 0, 2.5),
)
sm.register_prefab(tree_prefab)

# Instantiate many trees
for i in range(20):
    x = np.random.uniform(-30, 30)
    y = np.random.uniform(-30, 30)
    sm.instantiate("pine_tree", position=(x, y, 0), world=world)
```

### Scene manager queries

```python
# Find a node by name
car = sm.find("car")
print(car.world_position)    # absolute world-space position

# Find all nodes matching a tag
enemies = sm.find_all_by_tag("enemy")

# Destroy a node (and its children)
sm.destroy(car)
```

### Scene serialization

```python
# Save the scene graph
sm.save("scene.json")

# Load it back
sm2 = f3d.SceneManager()
sm2.load("scene.json")
```
