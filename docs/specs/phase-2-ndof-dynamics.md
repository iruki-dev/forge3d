# SPEC: Phase 2 — n-DOF 직렬 매니퓰레이터 일반화

> 파생: ROADMAP §5.2(계층 2), §9 P2. 검증 게이트: PyBullet/MuJoCo 6-DOF 팔과 가속도 대조(허용오차 내).

## 1. 목표 (한 문장)
2-DOF 동역학을 **n-DOF 직렬 팔**로 일반화한다: RNEA → CRBA(관성행렬) → 순동역학 → ABA, 그리고 6-DOF 팔을 기준 엔진과 대조해 정확성을 확정한다.

## 2. 범위
- **포함**: `crba.py`(질량행렬 M), 순동역학(`M·qdd = tau − C − g` 풀이), `aba.py`(Articulated Body Algorithm), URDF-유사 로더로 6-DOF 팔 적재, `validation/`의 기준엔진 대조 스크립트.
- **제외**: 충돌·접촉(P4), 그리퍼(P3), 시각화(P3), RL(P5+).

## 3. 영향 파일 / 인터페이스
- `src/forge3d/dynamics/crba.py` — `mass_matrix(model, q) -> M`.
- `src/forge3d/dynamics/aba.py` — `forward_dynamics(model, q, qd, tau) -> qdd`.
- `src/forge3d/model/urdf_loader.py` — URDF-유사 정의 → 내부 모델(링크/관절/관성).
- `src/forge3d/model/kinematics.py` — 순기구학(필요 시 자코비안).
- `assets/arm_6dof.*` — 6-DOF 팔 정의(기준 엔진과 동일 파라미터).
- `validation/pybullet_compare.py`, `validation/mujoco_compare.py` — **대조 전용**(엔진 미포함).
- `tests/test_crba.py`, `tests/test_aba.py`, `tests/test_fd_id_roundtrip.py`.

## 4. 구현 작업
- [ ] **T1.** URDF-유사 로더로 6-DOF 팔 적재(P1 모델 구조 확장).
- [ ] **T2.** CRBA로 질량행렬 M — 완료 조건: M 대칭·양정부호, `M·qdd` 검산이 RNEA와 일치.
- [ ] **T3.** 순동역학(M 풀이) + **ABA** 구현 — 완료 조건: `forward_dynamics(inverse_dynamics(...))` 왕복이 항등(허용오차 내).
- [ ] **T4.** `validation/`에서 동일 팔·동일 (q,qd,tau)를 PyBullet/MuJoCo에 올려 `qdd` 대조 스크립트 작성.
- [ ] **T5.** 무작위 입력 배치로 기준엔진 대조 자동화(허용오차 통계 리포트).

## 5. 엣지 케이스 / 제약
- 좌표계·관절축 규약을 기준 엔진과 정확히 맞춰야 비교가 의미 있음(불일치 시 규약 차이부터 점검).
- 특이자세(singular)·관절 한계 근방 수치 안정성.
- `validation/` 외부에서 `pybullet`/`mujoco` import 금지(CLAUDE.md §0).

## 6. 검증 (게이트)
- **기준 엔진 대조**: 6-DOF 팔, 다수의 무작위 (q,qd,tau)에서 우리 `qdd`가 PyBullet/MuJoCo와 허용오차 내 일치(상대오차 한계 명시).
- **내적 일관성**: ID↔FD 왕복 항등, CRBA의 M과 RNEA 검산 일치.
- **보존 법칙**: 무토크·무감쇠 6-DOF 자유낙하/스윙에서 에너지 보존.
- **백엔드 일치**: np/jnp 결과 허용오차 내 일치.
- **통과 기준**: `pytest tests/ -q`(두 백엔드) + `python validation/pybullet_compare.py`가 허용오차 내 PASS.

## 7. 완료 후 리뷰
- 서브에이전트: "ABA와 CRBA-순동역학이 같은 답을 주는가? 기준엔진과의 잔차가 규약 차이인가 버그인가? `src/`에 외부 엔진 import가 없는가?"
