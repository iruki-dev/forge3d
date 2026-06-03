# Phase 10 — 파지 weld 추상화 + pick-and-place 완주

> Source of truth: `docs/ROADMAP.md §9 P10`  
> 이전 게이트: P9 ✅ (Reaching RL)

---

## 목표

weld 추상화로 UR5가 물체를 집어 목표 위치로 옮기는 태스크를 구현한다.  
실제 마찰 파지(P12) 없이 근접 시 kinematic 부착(weld)으로 물체를 집는다.  
게이트: 물체 집어 옮기기 성공 영상(demo.mp4).

---

## 범위

| 파일 | 역할 |
|------|------|
| `src/forge3d/facade.py` | `World.weld(body, anchor, offset)` / `World.release(body)` |
| `src/forge3d/sim/world.py` | `update_body_pose` vel/omega 옵션 파라미터 |
| `apps/robot_rl/envs/pick_place_env.py` | `PickPlaceEnv(gymnasium.Env)` |
| `apps/robot_rl/envs/scripted_demo.py` | 스크립트 pick-and-place 시연 |
| `tests/test_pick_place.py` | weld 단위 테스트 + env API 테스트 |

---

## 설계

### weld 추상화

```python
world.weld(obj_body, anchor=ee_body)   # EE에 물체 부착
world.release(obj_body)                  # 부착 해제 (물체 낙하)
```

내부 동작:
1. `weld()` 호출 시: anchor와 body의 현재 위치 차이를 anchor 로컬 좌표로 저장.
2. `step()` 에서 물리 계산 후: 부착된 body를 anchor 위치+오프셋으로 teleport (vel=0).
3. `release()` 후: body가 일반 dynamic으로 돌아가 중력 적용.

### PickPlaceEnv

**Observation (16,)**: q(6) + ee_pos(3) + obj_pos(3) + tgt_pos(3) + grasped(1)  
**Action (7,)**: delta-q(6) + grasp_ctrl(1 continuous, ∈[-1,1])  
  - grasp_ctrl > 0.5 AND dist(EE, obj) < grasp_threshold AND not grasped → weld  
  - grasp_ctrl < -0.5 AND grasped → release  

**보상 (단계형)**:
- 미파지: `-dist(EE, obj) * 0.3`  
- 파지 순간: `+5`  
- 파지 중: `-dist(obj, tgt) * 0.5`  
- 배치 성공 (dist < 0.1m): `+20`, terminate

### 스크립트 시연

IK 없이 precomputed joint waypoints:
1. `q_approach`: EE를 물체 위로 이동
2. `q_grasp`: EE를 물체 높이로 하강 + weld 활성화
3. `q_lift`: 물체를 들어올림
4. `q_place`: 목표 위치로 이동
5. release + 물체 낙하

---

## Task 체크리스트

- [x] T1: P10 SPEC 작성
- [ ] T2: `update_body_pose` vel/omega 옵션, `World.weld()/release()`
- [ ] T3: `World.step()` weld sync
- [ ] T4: `PickPlaceEnv`
- [ ] T5: `scripted_demo.py` → `demo.mp4`
- [ ] T6: `tests/test_pick_place.py`
- [ ] T7: pytest ✅ ruff ✅ mypy ✅ + demo.mp4

---

## 검증 기준 (게이트)

### G1. weld 동작
- `world.weld(obj, anchor)` 후 `step()` → obj.position이 anchor를 따라간다.
- `world.release(obj)` 후 → obj가 중력으로 낙하한다.

### G2. pick-and-place 영상
- `demo.mp4`: UR5가 큐브를 집어 목표 위치로 이동 후 내려놓는 장면.
- 큐브가 팔을 따라 이동하는 것이 시각적으로 확인됨.
