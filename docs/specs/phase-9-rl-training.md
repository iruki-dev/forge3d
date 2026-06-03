# Phase 9 — Reaching RL 완주 + 학습 대시보드

> Source of truth: `docs/ROADMAP.md §9 P9`  
> 이전 게이트: P8 ✅ (Gymnasium 환경)

---

## 목표

PPO로 Reaching 태스크를 학습하고, 성공률 곡선 상승을 시각적으로 확인한다.  
학습 핫루프는 렌더러 OFF(headless). SB3(torch) 사용.  
`Recorder.run_policy()` 구현으로 학습 결과 영상화.

---

## 범위

| 파일 | 역할 |
|------|------|
| `src/forge3d/facade.py` | `World.teleport()` 추가 |
| `apps/robot_rl/envs/reach_env.py` | reset 최적화(월드 재사용) |
| `src/forge3d/recorder.py` | `run_policy()` 구현 |
| `apps/robot_rl/training/__init__.py` | 패키지 |
| `apps/robot_rl/training/train_reach.py` | SB3 PPO 학습 스크립트 |
| `apps/robot_rl/training/callbacks.py` | 성공률·보상 CSV 콜백 |
| `apps/robot_rl/dashboard.py` | matplotlib 학습 곡선 |
| `tests/test_p9_training.py` | 인프라 검증 |

---

## 설계

### 환경 최적화

현재 `ReachEnv.reset()`이 매 에피소드 새 World를 생성 → 느림.  
→ `World.teleport(body, pos)` 추가, reset에서 월드를 재사용하고 목표 위치만 이동.  
→ 기대 속도: ~136 → ~1000+ steps/sec

### 학습

| 파라미터 | 값 |
|---------|---|
| 알고리즘 | PPO (stable-baselines3) |
| 총 스텝 | 200,000 |
| n_envs | 1 (CPU 단일) |
| n_steps | 1024 |
| batch_size | 128 |
| n_epochs | 10 |
| learning_rate | 3e-4 |
| gamma | 0.99 |

### 로깅 및 대시보드

- `SuccessRateCallback`: 100 에피소드마다 성공률 계산 → CSV 저장
- `dashboard.py`: CSV 읽어 matplotlib 3-subplot 출력
  - subplot 1: 에피소드 평균 보상
  - subplot 2: 성공률 (0→ 상승 확인)
  - subplot 3: 에피소드 평균 길이

### Recorder.run_policy()

```python
rec.run_policy(model, env, duration=5.0, fps=24)
```

env의 `reset()`, `step()`, `render("rgb_array")` 를 duck-typing으로 사용.  
라이브러리가 apps을 import하지 않도록 env는 파라미터로 받음.

---

## Task 체크리스트

- [x] T1: P9 SPEC 작성
- [ ] T2: `World.teleport()`, `ReachEnv` reset 최적화
- [ ] T3: `Recorder.run_policy()` 구현
- [ ] T4: `training/train_reach.py` + `callbacks.py`
- [ ] T5: `dashboard.py`
- [ ] T6: `tests/test_p9_training.py`
- [ ] T7: 실제 학습 실행 → `dashboard.png` + `reaching_rollout.mp4`
- [ ] T8: pytest ✅ ruff ✅ mypy ✅

---

## 검증 기준 (게이트)

### G1. 성공률 곡선 상승
- `dashboard.png`에서 성공률 subplot이 0%에서 시작해 상승.

### G2. 학습 인프라
- 200k step 학습이 완주함 (crash 없음).
- CSV 로그 + checkpoint 저장.

### G3. 롤아웃 영상
- `rec.run_policy(model, env, ...)` → `reaching_rollout.mp4` 산출.
