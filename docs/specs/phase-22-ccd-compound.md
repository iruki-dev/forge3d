# Phase 22 SPEC — CCD (연속 충돌 감지) + 복합 형상

> Source of truth for P22. Only changes described here are permitted.

## 목표

**빠른 물체가 얇은 벽을 뚫고 지나가는 터널링**을 방지한다.  
하나의 바디에 **여러 충돌 형상**을 붙여 복잡한 물체를 표현한다.

### 참조
- **Bullet**: `btContinuousConvexCollision`; Swept-sphere CCD; `btCompoundShape`
- **Godot**: CCD mode (Cast Shape / Cast Ray); `CompoundShape3D`
- **Unity**: `Rigidbody.collisionDetectionMode = Continuous`; primitive 조합

---

## 범위 — CCD

| # | 내용 | 파일 |
|---|------|------|
| T1 | `Body.ccd_enabled: bool` 필드 | `src/forge3d/sim/world.py` |
| T2 | Swept-sphere CCD — 구 형상 바디 대상 | `src/forge3d/collision/ccd.py` (신규) |
| T3 | 광선 캐스트 CCD — 박스/캡슐 바디용 AABB sweeping | `src/forge3d/collision/ccd.py` |
| T4 | `step()` 에서 CCD-enabled 바디에 대해 TOI 계산 후 위치 보정 | `src/forge3d/sim/world.py` |
| T5 | 테스트 3종 | `tests/test_p22_ccd.py` (신규) |

## 범위 — 복합 형상 (Compound Shape)

| # | 내용 | 파일 |
|---|------|------|
| T6 | `CompoundShape` — `(shape, local_offset, local_quat)` 리스트 | `src/forge3d/collision/compound.py` (신규) |
| T7 | `World.add_compound(shapes, ...)` | `src/forge3d/facade.py` |
| T8 | 복합 형상 충돌 감지 — 각 하위 형상에 대해 기존 감지 함수 호출 | `src/forge3d/collision/detection.py` |
| T9 | 테스트 2종 | `tests/test_p22_ccd.py` |

---

## Swept-Sphere CCD 알고리즘

```
현재 위치 p0, 다음 스텝 예상 위치 p1 = p0 + v * dt
구 반지름 r

정적 구와의 TOI:
  d = p1 - p0
  f(t) = |p0 + t*d - q|² = (r_a + r_b)²
  → 이차방정식 풀기 → 가장 작은 양의 t_hit

TOI < 1이면 충돌 발생:
  position = p0 + t_hit * d   (충돌 위치)
  impulse 처리 후 잔여 시간(1 - t_hit)*dt 재통합
```

---

## 공개 API

```python
# CCD 활성화
bullet = world.add_sphere(radius=0.02, mass=0.01, position=(0, 0, 5))
bullet.ccd_enabled = True
bullet.set_velocity((0, 0, -200))  # 초고속

# 복합 형상 — L자 구조물
shapes = [
    (forge3d.Shape.box(size=(2, 0.2, 0.2)), offset=(0, 0, 0)),
    (forge3d.Shape.box(size=(0.2, 0.2, 1)), offset=(-0.9, 0, 0.5)),
]
l_body = world.add_compound(shapes, position=(0, 0, 3), mass=2.0)
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | CCD OFF — 초고속 구가 얇은 벽을 통과 (터널링 확인) | `test_tunneling_without_ccd` |
| G2 | CCD ON — 동일 상황에서 충돌 감지 | `test_no_tunneling_with_ccd` |
| G3 | 복합 형상 — 각 하위 형상이 독립적으로 충돌 반응 | `test_compound_collision` |
| G4 | pytest + ruff + mypy 통과 | — |
