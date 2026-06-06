# forge3d.Shape & Material

## Shape

Shape descriptors define the collision geometry of a body.

::: forge3d.facade.Shape

---

## Material

Material describes the visual appearance (PBR).

::: forge3d.facade.Material

### Material parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color` | `str \| tuple` | `"default"` | Preset name or `(R, G, B)` in [0, 1] |
| `roughness` | `float` | `0.5` | 0 = mirror, 1 = fully diffuse |
| `metallic` | `float` | `0.0` | 0 = dielectric, 1 = conductor |
| `emissive` | `float` | `0.0` | Emissive glow intensity (0 = no glow) |
| `texture_path` | `str \| None` | `None` | Path to albedo PNG/JPEG |
| `normal_map_path` | `str \| None` | `None` | Path to tangent-space normal map |

```python
# Standard PBR material
f3d.Material(color=(0.1, 0.5, 0.9), roughness=0.2, metallic=0.8)

# Glowing object (e.g. lava, neon sign)
f3d.Material(color=(1.0, 0.3, 0.0), emissive=3.0)

# Textured surface
f3d.Material(texture_path="assets/sand.png", roughness=0.9)
```

---

## Built-in colour presets

| Name | RGB |
|------|-----|
| `"default"` | (0.75, 0.75, 0.75) |
| `"red"` | (0.90, 0.20, 0.10) |
| `"blue"` | (0.15, 0.35, 0.90) |
| `"green"` | (0.15, 0.70, 0.25) |
| `"orange"` | (0.95, 0.55, 0.05) |
| `"gold"` | (0.83, 0.68, 0.21) metallic=1 |
| `"white"` | (0.95, 0.95, 0.95) |
| `"ground"` | (0.30, 0.48, 0.28) |

---

## CollisionLayer

Bit-field constants for collision filtering.

::: forge3d.collision.layers.CollisionLayer

### Layer table

| Constant | Value | Typical use |
|----------|-------|-------------|
| `DEFAULT` | 0x0001 | Generic objects |
| `PLAYER`  | 0x0002 | Player character |
| `ENEMY`   | 0x0004 | Enemy bodies |
| `TERRAIN` | 0x0008 | Heightfield terrain |
| `TRIGGER` | 0x0010 | Trigger zones |
| `BULLET`  | 0x0020 | Projectiles |
| `DEBRIS`  | 0x0040 | Breakable pieces |
| `SENSOR`  | 0x0080 | Sensor-only bodies |
| `NONE`    | 0x0000 | Disable all collision |
| `ALL`     | 0xFFFF | Collide with everything |

### Collision rule

Bodies A and B collide **if and only if**:

```
(A.collision_layer & B.collision_mask) != 0
AND
(B.collision_layer & A.collision_mask) != 0
```

### Usage

```python
from forge3d import CollisionLayer

player = world.add_capsule(radius=0.3, half_length=0.9, name="player")
player.collision_layer = CollisionLayer.PLAYER
player.collision_mask  = CollisionLayer.mask_for(
    CollisionLayer.TERRAIN,
    CollisionLayer.ENEMY,
)  # player collides with terrain and enemies only

bullet = world.add_sphere(radius=0.05, mass=0.01)
bullet.collision_layer = CollisionLayer.BULLET
bullet.collision_mask  = CollisionLayer.mask_for(
    CollisionLayer.ENEMY,
    CollisionLayer.DEFAULT,
)  # bullets hit enemies and default objects, not other bullets

# Filter overlap / raycast queries by layer
hits = world.raycast_all(origin, direction,
                          layer_mask=CollisionLayer.ENEMY)
```

---

## JointType

Type-safe enumeration for `world.add_joint()`.

::: forge3d.constraints.joint_type.JointType

```python
from forge3d import JointType

hinge = world.add_joint(
    JointType.HINGE, door, frame,
    anchor_a=(-0.5, 0, 0), anchor_b=(0.5, 0, 0),
    axis=(0, 0, 1), limits=(-1.5, 0.0),
)
spring = world.add_joint(
    JointType.SPRING, box, ceiling,
    stiffness=200.0, damping=10.0, rest_length=2.0,
)
```

| Value | Alias | DOF | Typical use |
|-------|-------|-----|-------------|
| `FIXED` | — | 0 | Rigid weld |
| `BALL` | — | 3 rot | Shoulder, ball-socket |
| `HINGE` | `REVOLUTE` | 1 rot | Door hinge, wheel |
| `PRISMATIC` | `SLIDER` | 1 lin | Piston, elevator |
| `DISTANCE` | — | — | Keep anchor distance |
| `SPRING` | — | — | Elastic tether |
