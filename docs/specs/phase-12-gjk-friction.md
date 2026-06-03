# Phase 12 — 실접촉 마찰 파지 + GJK + 도메인 랜덤화

## 배경

현재 충돌 감지기(`_box_vs_box_halfspace`)는 정적 박스의 **z 상면 하프스페이스만** 처리한다.
이 때문에 측면 접촉(핀치 그립 등)에서 잘못된 법선이 나와 마찰 기반 파지가 불가능하다.

P12는 이를 SAT(Separating Axis Theorem) 기반 OBB-OBB 감지로 교체해
**모든 6면 접촉**을 올바른 법선·깊이로 처리한다.
GJK는 일반 볼록 형상 쌍에 대한 불리언 교차 판정 기반을 제공한다.

---

## 범위 — 확정 파일

| 파일 | 역할 |
|------|------|
| `src/forge3d/collision/detection.py` | `_box_vs_box_sat()` 추가, dispatch 확장 |
| `src/forge3d/collision/gjk.py` | GJK 불리언 교차 판정 (sphere/box 지원) |
| `src/forge3d/sim/domain_rand.py` | 도메인 랜덤화 유틸리티 |
| `examples/04_friction_grasp.py` | 핀치 파지 시연 |
| `tests/test_p12_friction.py` | SAT 법선 + 마찰 파지 안정성 + DR 테스트 |

---

## 설계

### SAT OBB-OBB (`_box_vs_box_sat`)
- 15축 검사: A의 3 법선 + B의 3 법선 + 9개 모서리 교차
- 최소 관통 축 → 접촉 법선
- 동적 박스 코너 8개를 정적 박스 내부 여부 체크 → 다점 접촉 매니폴드
- 기존 `_box_vs_box_halfspace`를 대체(후방 호환 — z 상면 시나리오도 동일 결과)

### GJK (`gjk.py`)
- Minkowski difference 지원 함수 (sphere / box OBB)
- 단순화된 3D GJK 루프 (점·선·삼각형·사면체 심플렉스 케이스)
- 반환: `(intersecting: bool, distance: float)`
- 기존 analytic 페어보다 느리지만 임의 볼록 형상 쌍에 적용 가능

### 도메인 랜덤화 (`domain_rand.py`)
- `DomainRandConfig` — mass / friction / target_range 범위 설정
- `randomize_body(world, body_id, config, rng)` — 물리 속성 무작위화

---

## 완료 기준 (게이트)

### G1 SAT 법선 정확성
2-finger 핀치 그립 시나리오에서 접촉 법선이 ±x 방향임을 확인.
(기존 코드: [0,0,1] 오류 → 수정 후: [1,0,0] / [-1,0,0])

### G2 마찰 파지 안정성
μ ≥ μ_critical(~0.5)일 때 핀치 그립 물체 낙하 < 1 mm (2초간).
μ < μ_critical(0.1)일 때 물체가 낙하함.

### G3 GJK 교차 판정
알려진 교차/비교차 쌍에 대해 올바른 boolean 반환.

### G4 테스트·린트·타입
`pytest tests/test_p12_friction.py -q` + `ruff check .` + `mypy src/` 전부 통과.
기존 270개 테스트 회귀 없음.

---

## Tasks

- [ ] T1 `_box_vs_box_sat` + dispatch 업데이트 (`detection.py`)
- [ ] T2 `src/forge3d/collision/gjk.py` 구현
- [ ] T3 `src/forge3d/sim/domain_rand.py` 구현
- [ ] T4 `examples/04_friction_grasp.py` 구현
- [ ] T5 `tests/test_p12_friction.py` 작성
- [ ] T6 검증 실행 (pytest · ruff · mypy · gate 증거)
- [ ] T7 `docs/PROGRESS.md` 갱신
