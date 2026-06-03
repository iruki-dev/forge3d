# validation/

Reference-engine comparison scripts.

**Allowed here only**: `pybullet`, `mujoco` imports for ground-truth comparison.
These packages must NEVER appear inside `src/forge3d/`.

Scripts added per phase:
- P2: `pybullet_compare.py` — RNEA acceleration vs PyBullet (n-DOF gate)
- P5: `contact_compare.py` — contact forces vs MuJoCo
