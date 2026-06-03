# Phase 23 SPEC — 성능 최적화 (BVH + 아일랜드 슬리핑)

> Source of truth for P23. Only changes described here are permitted.

## 목표

물체 수 100~1000개 씬에서 **시뮬레이션 속도 10배 향상**.  
현재 O(n²) 충돌 브로드페이즈를 O(n log n)으로 교체하고, 정지한 물체를 슬리핑으로 건너뛴다.

### 참조
- **Bullet**: `btDbvtBroadphase` (Dynamic AABB BVH); 아일랜드 분리; 슬리핑 임계값
- **Godot**: `BVH broadphase`; `can_sleep` 프로퍼티
- **Box2D**: 인크리멘탈 AABB 트리; `b2Body::SetAwake`
- **MuJoCo**: 단순 AABB sort (행 기반 축 스윕)

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | AABB 축 스윕 브로드페이즈 (`SortAndSweep`) | `src/forge3d/collision/broadphase.py` (신규) |
| T2 | 동적 AABB BVH 트리 (선택: 고성능 대형 씬) | `src/forge3d/collision/bvh.py` (신규) |
| T3 | `PhysicsWorld._broad_phase()` 교체 | `src/forge3d/sim/world.py` |
| T4 | 바디 슬리핑 — 속도 임계값 이하 N스텝 연속 → sleep 상태 | `src/forge3d/sim/world.py` |
| T5 | 슬리핑 바디는 step()에서 스킵 | `src/forge3d/sim/world.py` |
| T6 | 슬리핑 바디를 충돌하는 다른 바디가 깨움 (wake on contact) | `src/forge3d/sim/world.py` |
| T7 | `Body.is_sleeping` 프로퍼티 | `src/forge3d/facade.py` |
| T8 | 벤치마크 스크립트 | `tests/bench_p23_performance.py` (신규) |
| T9 | 테스트 5종 | `tests/test_p23_performance.py` (신규) |

---

## Sort-and-Sweep 브로드페이즈

```
1. 모든 바디의 AABB 계산
2. x축 기준 min_x 정렬
3. 활성 목록 (active list) 순회:
   - 새 바디 진입: active에 추가
   - 활성 바디 중 max_x < 현재 min_x → 제거
   - 활성 목록 내 모든 쌍 → 잠재 충돌 후보
4. 후보 쌍에 대해서만 냅스킵 충돌 감지 실행
```

O(n log n) 정렬 + O(k) 냅스킵 (k = 실제 충돌 쌍 수, 보통 << n²).

---

## 슬리핑 알고리즘

```
sleep_threshold_velocity = 0.01 m/s
sleep_threshold_omega    = 0.01 rad/s
sleep_frames_required    = 60  (1초 @ 60Hz)

매 스텝:
  if |v| < threshold AND |ω| < threshold:
      body.sleep_count += 1
      if body.sleep_count >= sleep_frames_required:
          body.is_sleeping = True
  else:
      body.sleep_count = 0
      body.is_sleeping = False

wake_up 조건:
  - 충돌 솔버가 해당 바디에 임펄스 적용할 때
  - 사용자 apply_force/apply_impulse/teleport 호출 시
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 브로드페이즈 교체 후 기존 테스트 전부 통과 | 전체 pytest |
| G2 | 100개 바디 씬: 브로드페이즈 교체 후 **2× 이상 향상** | 벤치마크 비교 |
| G3 | 정지 물체 `is_sleeping == True` → step 시 CPU 기여 없음 | `test_sleeping_body_skipped` |
| G4 | 슬리핑 바디에 물체 충돌 시 즉시 `is_sleeping == False` | `test_wake_on_contact` |
| G5 | 에너지 보존 (슬리핑 켜진 상태에서 이전과 동일) | 에너지 비교 |
| G6 | pytest + ruff + mypy 통과 | — |
