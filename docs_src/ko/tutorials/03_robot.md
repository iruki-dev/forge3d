# 튜토리얼 3 — 로봇 팔 (FK / IK)

forge3d에는 순방향 운동학, 역방향 운동학, 야코비안 계산을 포함한 UR5 6자유도 로봇 팔 프리셋이 내장되어 있습니다.

---

## 로봇 로드

```python
import numpy as np
import forge3d as f3d
import forge3d.robot as f3r

world = f3d.World()
world.add_ground()

arm = f3r.load("ur5", base_position=(0, 0, 0))
world.add(arm)
```

`f3r.load("ur5")`는 실제 로봇과 일치하는 DH 파라미터로 UR5를 생성합니다.

---

## 조인트 각도 설정

```python
# 홈 포지션
arm.set_joints([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
world.step()

# 엔드이펙터 포즈 읽기
ee_pos, ee_rot = arm.ee_pose()
print(f"엔드이펙터 위치: {ee_pos.round(4)}")
print(f"엔드이펙터 방향 (쿼터니언): {ee_rot.round(4)}")
```

---

## 순방향 운동학

```python
q = np.array([0.5, -1.0, 1.5, -0.5, -0.5, 0.0])
arm.set_joints(q)
world.step()

pos, rot = arm.ee_pose()
```

FK는 6개 조인트 전체에 Denavit-Hartenberg 규약을 사용합니다.

---

## 야코비안

```python
q = arm.joint_angles()
J = arm.jacobian(q)         # (6, 6) 기하학적 야코비안
J_pos = J[:3, :]            # (3, 6) 위치 야코비안
J_rot = J[3:, :]            # (3, 6) 회전 야코비안
```

---

## 속도 제어

```python
# 엔드이펙터를 +z 방향으로 0.1 m/s 이동
target_ee_vel = np.array([0, 0, 0.1, 0, 0, 0])  # [vx, vy, vz, wx, wy, wz]
q = arm.joint_angles()
J = arm.jacobian(q)

# 유사역행렬 조인트 속도
J_pinv = np.linalg.pinv(J)
dq = J_pinv @ target_ee_vel
arm.set_joints(q + dq * 0.01)   # dt = 0.01 s
```

---

## 조인트 스윕 (비디오 저장)

```python
rec = f3d.Recorder(world, mode="hq", output="sweep.mp4")

def sweep_policy(obs):
    t = world.time
    q = np.zeros(6)
    q[0] = np.sin(t)      # 숄더 팬
    q[1] = -np.pi/2 + 0.5 * np.sin(2 * t)
    return q

rec.run_policy(sweep_policy, env=None, duration=5.0)
```

---

## 다음: [RL 튜토리얼](04_rl.md)
