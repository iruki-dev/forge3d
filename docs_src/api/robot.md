# forge3d.robot

Robot arm loading, FK, IK, and Jacobian.

::: forge3d.robot.robot.Robot

---

## Loading a preset

```python
import forge3d.robot as f3r

arm = f3r.load("ur5", base_position=(0, 0, 0))
```

Available presets: `"ur5"` (UR5 6-DOF)
