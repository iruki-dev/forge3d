# Tutorial 3 — Robot Arm (FK / IK)

forge3d includes a UR5 6-DOF robot arm preset with forward kinematics, inverse kinematics, and Jacobian computation.

---

## Loading a robot

```python
import numpy as np
import forge3d as f3d
import forge3d.robot as f3r

world = f3d.World()
world.add_ground()

arm = f3r.load("ur5", base_position=(0, 0, 0))
world.add(arm)
```

`f3r.load("ur5")` creates a UR5 with DH parameters matching the real robot.

---

## Setting joint angles

```python
# Home position
arm.set_joints([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
world.step()

# Read end-effector pose
ee_pos, ee_rot = arm.ee_pose()
print(f"End-effector position: {ee_pos.round(4)}")
print(f"End-effector orientation (quat): {ee_rot.round(4)}")
```

---

## Forward kinematics

```python
q = np.array([0.5, -1.0, 1.5, -0.5, -0.5, 0.0])
arm.set_joints(q)
world.step()

pos, rot = arm.ee_pose()
```

The FK uses the Denavit-Hartenberg convention with all 6 joints.

---

## Jacobian

```python
q = arm.joint_angles()
J = arm.jacobian(q)         # (6, 6) geometric Jacobian
J_pos = J[:3, :]            # (3, 6) position Jacobian
J_rot = J[3:, :]            # (3, 6) rotation Jacobian
```

---

## Velocity control

```python
# Move end-effector at 0.1 m/s in +z
target_ee_vel = np.array([0, 0, 0.1, 0, 0, 0])  # [vx, vy, vz, wx, wy, wz]
q = arm.joint_angles()
J = arm.jacobian(q)

# Pseudoinverse joint velocity
J_pinv = np.linalg.pinv(J)
dq = J_pinv @ target_ee_vel
arm.set_joints(q + dq * 0.01)   # dt = 0.01 s
```

---

## Sweeping joints (video)

```python
rec = f3d.Recorder(world, mode="hq", output="sweep.mp4")

def sweep_policy(obs):
    t = world.time
    q = np.zeros(6)
    q[0] = np.sin(t)      # shoulder pan
    q[1] = -np.pi/2 + 0.5 * np.sin(2 * t)
    return q

rec.run_policy(sweep_policy, env=None, duration=5.0)
```

---

## Next: [RL tutorial](04_rl.md)
