# Phase 11 — all-JAX 성능화(JIT+vmap) + SHAC

## 목표

현재 NumPy 기반 ReachEnv(~584 steps/s)를 JAX JIT+vmap으로 재구현해 처리량을 수십~수백배
향상시킨다. SHAC(Short Horizon Actor-Critic)로 해석적(analytic) 정책 그래디언트를 시연한다.

라이브러리 신규 파일은 `src/forge3d/sim/jax_batch.py` 하나뿐이다. 기존 NumPy 경로를 절대
변경하지 않는다.

---

## 범위 — 확정 파일

| 파일 | 역할 |
|------|------|
| `src/forge3d/sim/jax_batch.py` | JAX JIT UR5 FK + vmap reaching step |
| `apps/robot_rl/training/shac_reach.py` | SHAC 학습 루프 (pure-JAX MLP + optax Adam) |
| `apps/robot_rl/training/benchmark_jax.py` | NumPy vs JAX 처리량 벤치마크 |
| `tests/test_p11_jax.py` | FK 정확성 · 배치 형상 · 그래디언트 흐름 · 처리량 |
| `pyproject.toml` | `optax>=0.2` 선택의존성 추가 |

---

## 설계 원칙

### JAX FK 구현
- `JAX_ENABLE_X64=1` 사용 — NumPy float64와 수치 일치 보장.
- 모듈 로드 시 UR5 DH 변환행렬 `_UR5_R_TREES(6,3,3)`, `_UR5_P_TREES(6,3)`을
  NumPy로 사전계산(1회)해 JAX 상수 배열로 변환.
- `@jax.jit def ur5_fk_ee(q)`: Python `for i in range(6)` → JIT 추적 시 언롤링.
  업데이트 순서: `p ← p + R @ P[i]` (부모 R 사용) → `R ← R @ R_tree[i] @ Rz(q[i])`.
- `ur5_fk_ee_batch = jax.jit(jax.vmap(ur5_fk_ee))`: B × (6,) → B × (3,).

### Reaching step (JAX)
- `reach_step_jax(q, target, action)` → `(new_q, obs(12), reward, terminated)`.
- `batch_reach_step = jax.jit(jax.vmap(reach_step_jax))`: 전체 환경 배치를
  단일 JAX 커널로 처리.

### SHAC (Short Horizon Actor-Critic)
- pure-JAX MLP (He 초기화) + optax Adam.
- `actor_loss_fn(actor_params, critic_params, q_batch, target_batch, key, H=16)`:
  `jax.lax.scan`으로 H스텝 롤아웃 → 총 보상 + 비평자 가치 → 음수 반환.
- `jax.grad(actor_loss_fn, argnums=0)`: FK가 미분 가능(삼각함수)하므로
  H스텝에 걸쳐 해석적 그래디언트 계산.
- 비평자는 TD(1) 독립 업데이트.

---

## 완료 기준 (게이트)

### G1 FK 정확성
`ur5_fk_ee(q)` 결과가 NumPy `forward_kinematics(model, q)` 결과와 `atol=1e-5` 내 일치.
(실제 기대: < 1e-10, x64 사용 시 기계 정밀도)

### G2 배치 처리량
`batch_reach_step(B=256)` 처리량(환경-스텝/초) ≥ NumPy 단일환경 처리량 × 100배.

### G3 SHAC 그래디언트 흐름
`jax.grad(actor_loss_fn)` 결과의 그래디언트 norm > 0.
(FK 미분 가능성 ↔ SHAC의 핵심 전제 검증)

### G4 테스트·린트·타입
`pytest tests/test_p11_jax.py -q` + `ruff check .` + `mypy src/` 전부 통과.

---

## Tasks

- [ ] T1 `src/forge3d/sim/jax_batch.py` 구현 (FK + batch step + reset)
- [ ] T2 `apps/robot_rl/training/shac_reach.py` 구현 (MLP + SHAC loss + 학습루프)
- [ ] T3 `apps/robot_rl/training/benchmark_jax.py` 구현 (NumPy vs JAX 처리량)
- [ ] T4 `tests/test_p11_jax.py` 작성
- [ ] T5 `pyproject.toml` optax 추가
- [ ] T6 검증 실행 (pytest · ruff · mypy · benchmark)
- [ ] T7 `docs/PROGRESS.md` 갱신
