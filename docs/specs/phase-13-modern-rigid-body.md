# Phase 13 SPEC — Modern Rigid-Body Physics

> Source of truth for P13. Only changes described here are permitted.

## 목표

현재 물리 엔진을 현대 강체 물리엔진 수준으로 업그레이드한다.
핵심 결함 3가지를 해결한다:

1. **관성 텐서 없음** — 현재 `_Body`는 mass만 있고 I(관성 텐서)가 없어 접촉에서 회전 반응이 전혀 없다.
2. **1회 임펄스** — 현재 솔버는 접촉당 1회 임펄스만 적용한다. 다중 물체 쌓기가 불안정하다.
3. **구 충돌 반쪽만** — `_sphere_vs_box_halfspace`는 박스의 윗면(z+)만 처리한다. 옆면에 공을 던지면 그냥 통과한다.

## 범위 (이 Phase에서 할 것)

| # | 내용 | 파일 |
|---|------|------|
| T1 | 관성 텐서 헬퍼 함수 | `src/forge3d/math/inertia.py` (신규) |
| T2 | `_Body`에 `inertia_local` 필드 추가; `add_box`/`add_sphere`에서 계산 | `src/forge3d/sim/world.py` |
| T3 | 캡슐 형상 추가 (`add_capsule`) | `src/forge3d/sim/world.py` |
| T4 | 구 vs OBB 일반 충돌 (`_sphere_vs_obb`) | `src/forge3d/collision/detection.py` |
| T5 | 캡슐 충돌 페어 추가 | `src/forge3d/collision/detection.py` |
| T6 | **PGS 반복 솔버** — 10회 반복, 누적 임펄스 클램핑 | `src/forge3d/contact/solver.py` |
| T7 | **각 임펄스** — 오프센터 접촉이 omega를 갱신 | `src/forge3d/contact/solver.py` |
| T8 | 기존 마찰 테스트를 올바른 구르기 물리로 갱신 | `tests/test_contact_physics.py` |
| T9 | P13 물리 게이트 테스트 | `tests/test_p13_rigid_body.py` (신규) |

## 범위 밖 (P13에서 하지 않을 것)

- CCD (연속 충돌 감지)
- 조인트/구속 (힌지, 프리즈매틱)
- 슬리핑 (비활성 물체 최적화)
- 광역 위상 BVH (100개 이하 물체에서 O(n²) 충분)
- EPA (GJK는 P12에서 구현, 심도 계산은 SAT로 충분)

## 핵심 물리 알고리즘

### 관성 텐서

- **박스** (half_extents = [a, b, c]): `I = m/12 * diag(4b²+4c², 4a²+4c², 4a²+4b²)`
- **구** (radius = r): `I = 2/5 * m * r² * I₃`
- **캡슐** (radius = r, half_length = l): 원통 + 반구 근사

### 접촉점 유효 질량 (회전 포함)

```
m_eff = 1 / (1/m_a + 1/m_b + (r_a×n)·I_a⁻¹·(r_a×n) + (r_b×n)·I_b⁻¹·(r_b×n))
```

`r_a = contact_pos - body_a.pos` (레버 암)

### 각 임펄스

```
Δω_a = I_a_world⁻¹ * (r_a × J)
I_a_world⁻¹ = R_a * diag(1/I_local) * R_a^T
```

### PGS (Projected Gauss-Seidel)

10회 반복. 각 반복마다:
1. 법선 임펄스: `Δλ_n = -(v_n + bias) / K_n`, `λ_n = max(0, λ_n + Δλ_n)`
2. 마찰 임펄스: `Δλ_t = -v_t / K_t`, `λ_t = clip(λ_t + Δλ_t, -μλ_n, μλ_n)`

Baumgarte 속도 바이어스: `bias = -β/dt * max(0, depth - slop)`, β=0.2, slop=1mm

## 구 vs OBB 일반 충돌

```
d_local = R_b^T * (sphere.pos - box.pos)          # 구 중심, 박스 로컬 프레임
closest_local = clip(d_local, -h_b, h_b)           # OBB 내 최근접점
closest_world = box.pos + R_b * closest_local
diff = sphere.pos - closest_world
depth = radius - |diff|
normal = diff / |diff|   (구 안쪽인 경우 별도 처리)
```

## 캡슐 형상

`shape_type = "capsule"`, `shape_params = {"radius": r, "half_length": l}`
캡슐 축 = body quat으로 회전한 z축.

지원 페어:
- capsule vs sphere
- capsule vs box (구 vs OBB 로 근사: 캡슐 축 위 최근접점을 구 중심으로)
- capsule vs capsule (선분-선분 최근접점)
- capsule vs static plane

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 오프센터 충돌 후 물체가 회전 | 구가 박스 측면 하단에 충돌 → box.omega[2] ≠ 0 |
| G2 | 캡슐 충돌 동작 | 캡슐 vs 구, 캡슐 vs 박스 접촉점 반환 |
| G3 | 구 vs 박스 측면 접촉 | 구가 박스 x+ 면에 접촉 → normal ≈ [-1,0,0] |
| G4 | 3단 박스 쌓기 안정 | 10초 시뮬레이션 후 모든 박스 정지 (vmax < 0.1 m/s) |
| G5 | 에너지 보존 (자유 회전) | 마찰 없는 회전 강체, 1000 스텝 후 에너지 오차 < 1% |
| G6 | pytest + ruff + mypy 통과 |  |
