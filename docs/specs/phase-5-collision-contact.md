# Phase 5 — 충돌(프리미티브) + 연성 접촉 (Phase A)

> Source of truth: `docs/ROADMAP.md §9 P5`  
> 이전 게이트: P4 ✅ (pygame식 공개 API + Viewer)

---

## 목표

프리미티브 형상 간 충돌 감지와 임펄스 기반 접촉 해석을 구현한다.  
물리 코어(`collision/`, `contact/`)는 렌더러를 import하지 않는다.  
외부 물리엔진(PyBullet 등)은 이 코드에 사용하지 않는다.

---

## 범위

### 파일 목록

| 파일 | 역할 |
|------|------|
| `src/forge3d/collision/detection.py` | 충돌 감지: sphere-plane, box-plane, sphere-sphere |
| `src/forge3d/contact/solver.py` | 임펄스 솔버: 반발계수, 쿨롱 마찰 |
| `src/forge3d/sim/world.py` | `_Body`에 restitution/friction 추가, `step()`에 접촉 통합 |
| `src/forge3d/facade.py` | `add_box/add_sphere`에 `restitution`, `friction` 노출 |
| `tests/test_collision.py` | 충돌 감지 단위 테스트 |
| `tests/test_contact_physics.py` | 물리 검증: 반발 거동, 마찰 임계각 |
| `examples/02_bouncing_ball.py` | 공 튀기기 예제 (≤15줄) |

---

## 설계 결정

### 충돌 감지 (Narrow Phase)

`ContactPoint` — 순수 데이터:
- `body_a_idx`: 동적 바디 인덱스
- `body_b_idx`: 접촉 상대 인덱스 (-1 = 정적 반공간)
- `pos`: 접촉점 (월드 좌표)
- `normal`: 단위 법선 (b → a 방향, 즉 a를 밀어내는 방향)
- `depth`: 침투 깊이 (> 0)

프리미티브 페어:
- **sphere vs. 정적 box (반공간)**: `depth = r - (center_z - plane_z)`
- **box vs. 정적 box (반공간)**: 8개 모서리 각각 검사
- **sphere vs. sphere**: `depth = r1 + r2 - |c1 - c2|`

경사면 테스트는 중력 벡터를 기울여 수평 지면으로 등가 변환.

### 접촉 솔버 (Impulse-Based)

세미 임플리시트 오일러 후 접촉 처리:
1. 외력(중력) 적분 → 속도·위치 갱신
2. 충돌 감지
3. 법선 임펄스 적용 (반발계수 `e`):
   - `v_n_eff = e if |v_n| > threshold else 0` (Zeno 방지)
   - `J_n = -(1 + e_eff) * v_n * m_eff`
4. 마찰 임펄스 (쿨롱 한계):
   - `J_t = -min(mu * J_n, m_eff * |v_t|)`
5. 위치 보정 (Baumgarte, beta=0.3):
   - `Δpos = beta * max(0, depth - slop) * normal`

정적 바디와의 접촉: 동적 바디만 수정.  
동적 바디끼리: 역질량 비율로 임펄스 분배.

---

## Task 체크리스트

- [x] T1: P5 SPEC 작성
- [ ] T2: `collision/detection.py` — `ContactPoint` + 3종 페어 감지
- [ ] T3: `contact/solver.py` — 임펄스 솔버 (반발 + 마찰 + 위치 보정)
- [ ] T4: `sim/world.py` 갱신 — `_Body.restitution/friction`, `step()` 접촉 통합
- [ ] T5: `facade.py` 갱신 — 공개 API에 `restitution`, `friction` 파라미터
- [ ] T6: `tests/test_collision.py` — 단위 테스트
- [ ] T7: `tests/test_contact_physics.py` — 물리 검증 테스트
- [ ] T8: `examples/02_bouncing_ball.py`
- [ ] T9: pytest ✅ + ruff ✅ + mypy ✅

---

## 검증 기준 (게이트)

### G1. 반발 거동

```
공 낙하 높이 h, 반발계수 e → 첫 반발 높이 h' = e² * h (허용오차 5%)
```

검증:
- `h = 5.0 m`, `e = 0.8` → `h_expected = 0.64 * 5 = 3.2 m`
- `h = 5.0 m`, `e = 0.5` → `h_expected = 0.25 * 5 = 1.25 m`
- 반발계수 `e = 0` → 첫 튀김 후 지면에 안착

### G2. 마찰 임계각

경사면 등가 중력 `g = (g·sin θ, 0, -g·cos θ)`:
- `tan θ < μ` → 공이 이동하지 않음 (v < 0.01 m/s)
- `tan θ > μ` → 공이 이동 (v > 0 단조 증가)

검증:
- `μ = 0.5`: θ = 25° (tan < μ) → 정지, θ = 30° (tan > μ) → 미끄러짐

---

## 완료 조건

- [ ] pytest 전체 통과 (기존 161개 + 신규 ≥10개)
- [ ] ruff check ✅, mypy ✅
- [ ] G1 반발 거동 이론 대조 통과 (5% 이내)
- [ ] G2 마찰 임계각 이론 대조 통과
- [ ] `examples/02_bouncing_ball.py` 동작 확인 (실행 + 결과 출력)
