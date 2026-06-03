# Phase 16 SPEC — 조인트 & 구속 시스템

> Source of truth for P16. Only changes described here are permitted.

## 목표

forge3d에서 가장 크게 빠진 물리 기능: **관절·구속(Joint/Constraint)**을 추가한다.  
체인·로봇 팔·문·스프링·현수교 등 모든 연결된 메커니즘의 기반이다.

### 참조
- **Pymunk**: PinJoint, SlideJoint, PivotJoint, DampedSpring — 간결한 Python API
- **Godot 4**: HingeJoint3D, SliderJoint3D, Generic6DOFJoint3D — 한계·모터 포함
- **Bullet**: btGeneric6DofConstraint — 6자유도 구속 일반화
- **Unity**: HingeJoint(limit·spring·motor), SpringJoint(distance), FixedJoint
- **MuJoCo**: hinge/slide/ball joint + equality constraint

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `Constraint` ABC + `ConstraintManager` | `src/forge3d/constraints/base.py` (신규) |
| T2 | `FixedJoint` — weld 대체 (XPBD position constraint) | `src/forge3d/constraints/fixed.py` |
| T3 | `BallJoint` — 점 일치 (ball-and-socket) | `src/forge3d/constraints/ball.py` |
| T4 | `HingeJoint` — 1축 회전 + 한계각 + 모터 | `src/forge3d/constraints/hinge.py` |
| T5 | `PrismaticJoint` — 1축 슬라이딩 + 한계 + 모터 | `src/forge3d/constraints/prismatic.py` |
| T6 | `DistanceJoint` — 거리 유지 (막대/밧줄) | `src/forge3d/constraints/distance.py` |
| T7 | `SpringJoint` — 스프링·댐퍼 힘 요소 | `src/forge3d/constraints/spring.py` |
| T8 | `PhysicsWorld.step()` 에 constraint 솔버 통합 | `src/forge3d/sim/world.py` |
| T9 | `World` facade에 `add_joint()` 공개 API 추가 | `src/forge3d/facade.py` |
| T10 | 테스트 7종 | `tests/test_p16_joints.py` (신규) |
| T11 | 예제: 진자·도어·스프링 | `examples/05_joints.py` |

---

## 물리 알고리즘

### 임펄스 기반 구속 (Velocity-level)

XPBD/게임엔진 표준 "Sequential Impulse" 패턴:

```
C(q) = 0          # 위치 구속 (홀로노믹)
dC/dt = J * v = 0 # 속도 구속 (Jacobian)

λ = -(J * M⁻¹ * Jᵀ)⁻¹ * (J * v + β/dt * C)   # Lagrange multiplier
Δv = M⁻¹ * Jᵀ * λ                               # 속도 보정
Δω = I⁻¹ * (r × (Jᵀ * λ))                      # 각속도 보정
```

β = 0.2 (Baumgarte 안정화), slop = 1 mm.

### HingeJoint 구속

- **3 선형 구속** (두 앵커가 world에서 일치): `C_lin = p_a + R_a * r_a - p_b - R_b * r_b`
- **2 각도 구속** (힌지 축 직교 두 방향 고정): `C_ang1 = (R_a * axis_a) · (R_b * perp1_b)`, `C_ang2 = ...`
- **1 자유 자유도** (힌지 축 회전) → 선택적 한계·모터

자유도 수: 5개 구속 → 1 DOF 회전.

### PrismaticJoint 구속

- **3 각도 구속** (두 몸체가 상대 회전 없음): `C_ang = R_a^T * R_b ≈ I₃` (소각 근사)
- **2 선형 구속** (슬라이드 축 직교 방향 고정)
- **1 자유 자유도** (슬라이드 방향) → 선택적 한계·모터

자유도 수: 5개 구속 → 1 DOF 슬라이딩.

### BallJoint 구속

- **3 선형 구속** (앵커 일치): `C = p_a + R_a * r_a - p_b - R_b * r_b`
- 0 각도 구속 → 3 DOF 자유 회전

### DistanceJoint 구속

- **1 구속**: `C = |p_a - p_b| - d_target`
- 방향: `n = (p_a - p_b) / |p_a - p_b|`
- 옵션: `min_dist` ≤ d ≤ `max_dist` (밧줄처럼 한쪽만)

### SpringJoint (힘 요소)

구속이 아닌 **힘 적용**:
```
f = -k * (|p_a - p_b| - rest_length) * n  - c * v_rel_n
```
`k` = 스프링 상수, `c` = 댐핑 계수, `v_rel_n` = 법선 방향 상대 속도.

---

## 공개 API

```python
# FixedJoint
joint = world.add_joint("fixed", body_a=box, body_b=wall,
                         anchor_a=(0, 0, 0), anchor_b=(0, 0, 0))

# BallJoint
joint = world.add_joint("ball", body_a=link1, body_b=link2,
                         anchor_a=(0, 0, -0.5), anchor_b=(0, 0, 0.5))

# HingeJoint
joint = world.add_joint("hinge", body_a=door, body_b=frame,
                         anchor_a=(-0.5, 0, 0), anchor_b=(0.5, 0, 0),
                         axis=(0, 0, 1),           # 힌지 축 (body_a 로컬)
                         limits=(-np.pi/2, np.pi/2),
                         motor_velocity=1.0,        # None이면 모터 없음
                         motor_max_torque=10.0)

# PrismaticJoint
joint = world.add_joint("prismatic", body_a=piston, body_b=cylinder,
                         axis=(0, 0, 1),
                         limits=(0.0, 0.5))

# DistanceJoint
joint = world.add_joint("distance", body_a=ball1, body_b=ball2,
                         target_distance=2.0)

# SpringJoint
joint = world.add_joint("spring", body_a=box, body_b=ceiling,
                         anchor_a=(0, 0, 0), anchor_b=(0, 0, 0),
                         stiffness=100.0, damping=5.0, rest_length=2.0)

# 제거
world.remove_joint(joint)
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `FixedJoint` — 고정된 두 물체가 중력에서 상대 이동 < 1 mm | `test_fixed_joint_holds` |
| G2 | `BallJoint` 진자 — 1 DOF 진자처럼 진동, 에너지 드리프트 < 1% | `test_ball_joint_pendulum` |
| G3 | `HingeJoint` 모터 — 지정 속도로 회전 (omega ≈ motor_velocity ± 10%) | `test_hinge_motor` |
| G4 | `HingeJoint` 한계 — 회전 각도가 limits 범위를 벗어나지 않음 | `test_hinge_limits` |
| G5 | `PrismaticJoint` — 슬라이딩 방향 이외 이동 < 1 mm | `test_prismatic_slide` |
| G6 | `DistanceJoint` — 두 물체 간 거리가 target ± 1 cm 유지 | `test_distance_constraint` |
| G7 | `SpringJoint` — 진동 주기가 `2π√(m/k)` ± 5% | `test_spring_period` |
| G8 | pytest + ruff + mypy 통과 | — |
