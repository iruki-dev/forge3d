# forge3d.animation — Skeletal Animation

forge3d's animation system provides skeletal animation with keyframe blending,
blend trees, and FABRIK inverse kinematics.

---

## Core classes

::: forge3d.animation.Bone

::: forge3d.animation.Skeleton

::: forge3d.animation.AnimationClip

::: forge3d.animation.AnimationPlayer

::: forge3d.animation.BlendTree

::: forge3d.animation.IKTarget

::: forge3d.animation.FABRIKSolver

::: forge3d.animation.AnimationSystem

---

## Usage examples

### Define a skeleton

```python
from forge3d import Bone, Skeleton

bones = [
    Bone(name="root",       parent_idx=None),
    Bone(name="hip",        parent_idx=0),
    Bone(name="spine",      parent_idx=1),
    Bone(name="l_shoulder", parent_idx=2),
    Bone(name="l_elbow",    parent_idx=3),
    Bone(name="l_wrist",    parent_idx=4),
]
skeleton = Skeleton(bones=bones)
```

### Load and play an animation clip

```python
import numpy as np
from forge3d import AnimationClip, AnimationPlayer

# Create a clip with keyframes
clip = AnimationClip(
    name="wave",
    duration=1.0,
    keyframes={
        "l_shoulder": [(0.0, np.zeros(3), np.array([1,0,0,0])),   # (time, pos, quat)
                        (0.5, np.zeros(3), np.array([0.707,0,0,0.707])),
                        (1.0, np.zeros(3), np.array([1,0,0,0]))],
    }
)

player = AnimationPlayer(skeleton=skeleton)
player.play(clip, loop=True)

# Advance by one frame
player.update(dt=1/60)
pose = player.current_pose()   # dict[bone_name, (pos, quat, scale)]
```

### Blend tree (locomotion)

```python
from forge3d import BlendTree

# Blend between idle and walk clips based on speed
blend = BlendTree(clip_a=idle_clip, clip_b=walk_clip)
blend.parameter = 0.6    # 0=idle, 1=walk

player = AnimationPlayer(skeleton=skeleton, blend_tree=blend)
player.update(dt=1/60)
```

### FABRIK inverse kinematics

```python
from forge3d import FABRIKSolver, IKTarget

solver = FABRIKSolver(
    skeleton=skeleton,
    chain=["l_shoulder", "l_elbow", "l_wrist"],   # bone chain
    iterations=10,
    tolerance=0.001,   # 1 mm
)

target = IKTarget(
    position=np.array([0.4, 0.1, 1.2]),   # world-space target
    weight=1.0,
)

pose = player.current_pose()
solved_pose = solver.solve(pose, target)
```

### AnimationSystem (ECS integration)

```python
import forge3d as f3d

ew = f3d.EntityWorld()
anim_system = f3d.AnimationSystem()
ew.add_system(anim_system)

# Attach player to an entity
entity = ew.create()
ew.add(entity, player)

ew.step(dt=1/60)    # AnimationSystem.update() called automatically
```
