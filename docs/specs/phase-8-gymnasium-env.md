# Phase 8 — Gymnasium 환경(Reaching) + render_mode 3종

> Source of truth: `docs/ROADMAP.md §9 P8`  
> 이전 게이트: P7 ✅ (로봇 모델 + 관절 제어)

---

## 목표

UR5 팔로 목표 위치에 EE를 이동시키는 Gymnasium 환경 구현.  
`render_mode` 3종(None/human/rgb_array) 전환을 지원.  
응용 레이어(`apps/robot_rl/`)에서 라이브러리를 **외부인처럼 import해서만** 사용.

---

## 범위

| 파일 | 역할 |
|------|------|
| `apps/robot_rl/envs/reach_env.py` | `ReachEnv(gymnasium.Env)` |
| `apps/robot_rl/envs/__init__.py` | `ReachEnv` export |
| `src/forge3d/sim/world.py` | `add_sphere(static=True)` 지원 |
| `src/forge3d/facade.py` | `World.add_sphere(static=True)` 노출 |
| `tests/test_reach_env.py` | render_mode 게이트 + obs/action space |

---

## 설계

### 환경

```python
env = ReachEnv(render_mode=None)  # headless (학습용)
env = ReachEnv(render_mode="rgb_array")  # 프레임 배열 반환
env = ReachEnv(render_mode="human")    # 실시간 렌더(headless라면 offscreen)
```

**Observation (12,)**: `q[6] + ee_pos[3] + target_pos[3]`  
**Action (6,)**: delta-q ∈ [-1, 1], 적용: `q += action * 0.05`  
**Reward**: `-dist(EE, target) - 0.01 * ||action||² + 10 * success`  
**Success**: `dist < 0.05 m`  
**Episode 종료**: success (terminated) 또는 max_steps (truncated)

### render_mode 구현
- `None`: `render()` → `None`
- `"rgb_array"`: HQRenderer(samples=1) → (H, W, 3) uint8
- `"human"`: RealtimeRenderer → offscreen frame (헤드리스 호환)

### 타겟 시각화
- 정적 구(`static=True, mass=0`)를 월드에 추가 → 렌더러가 마커로 표시

---

## Task 체크리스트

- [x] T1: P8 SPEC 작성
- [ ] T2: `add_sphere(static=True)` in world.py + facade.py
- [ ] T3: `apps/robot_rl/envs/reach_env.py`
- [ ] T4: `tests/test_reach_env.py`
- [ ] T5: pytest ✅ ruff ✅ mypy ✅ + 세 render_mode 검증

---

## 검증 기준 (게이트)

### G1. render_mode 전환
- `render_mode=None` → `env.render()` returns `None`
- `render_mode="rgb_array"` → returns `(H, W, 3) uint8` array
- `render_mode="human"` → returns array (headless) or None

### G2. Gymnasium API 준수
- `gymnasium.utils.env_checker.check_env(env)` 통과 (경고 허용, 오류 불가)
- `obs, info = env.reset(seed=42)` → obs.shape == (12,)
- `obs, reward, term, trunc, info = env.step(env.action_space.sample())`
- `info["distance"] >= 0`, `info["success"]` bool
