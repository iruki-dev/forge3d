# SPEC: Phase 1 — 수학(SE3·공간대수) & 2-DOF 평면 팔 동역학

> 파생: ROADMAP §5.2(계층 1~2), §9 P1. 검증 게이트: 에너지 보존 + 단진자 주기 해석값 일치 + RNEA=손유도.

## 1. 목표 (한 문장)
SE3·쿼터니언·Featherstone 공간 벡터 대수를 구현하고, 그 위에서 **2-DOF 평면 팔**의 동역학(RNEA)을 *정확하게* 푼다.

## 2. 범위
- **포함**: `math/se3.py`, `quaternion.py`, `spatial.py`(6D 공간 운동/힘 벡터, 공간 변환·관성), 2-DOF 평면 팔 모델, RNEA로 역동역학, 간단 적분으로 전진 시뮬.
- **제외**: n-DOF 일반화(P2의 CRBA/ABA), 충돌·접촉, 그리퍼, RL.

## 3. 영향 파일 / 인터페이스
- `src/forge3d/math/se3.py` — `exp`, `log`, `adjoint`, 변환 합성.
- `src/forge3d/math/quaternion.py` — 정규화, 곱, 회전 적용, 보간.
- `src/forge3d/math/spatial.py` — 공간 운동/힘 벡터, 공간 관성 행렬, 공간 변환(`Ad`, `ad`).
- `src/forge3d/dynamics/rnea.py` — `inverse_dynamics(model, q, qd, qdd) -> tau`.
- `assets/arm_2dof.py`(또는 유사 로더) — 2-DOF 평면 팔 파라미터(링크 길이·질량·관성).
- `tests/test_math.py`, `tests/test_rnea_2dof.py`, `tests/test_conservation.py`.

## 4. 구현 작업
- [ ] **T1.** SE3/쿼터니언 구현 + 항등식 테스트(`exp∘log=id`, 회전 합성, 단위 쿼터니언 유지). 함수형·불변 준수.
- [ ] **T2.** 공간 벡터 대수(`spatial.py`): 운동/힘 6-벡터, 공간 관성, `Ad`/`ad` 연산자 + 단위 테스트.
- [ ] **T3.** 2-DOF 평면 팔 모델 정의(파라미터, 트리/링크 구조).
- [ ] **T4.** RNEA 역동역학 구현 — 완료 조건: `tau = ID(q,qd,qdd)`가 SymPy 손유도 결과와 허용오차 내 일치.
- [ ] **T5.** semi-implicit Euler로 전진 시뮬 + 에너지/주기 측정 유틸.

## 5. 엣지 케이스 / 제약
- 쿼터니언은 매 스텝 정규화(드리프트 방지).
- 무토크·무감쇠 시뮬에서 수치 적분 오차 한계를 dt로 통제.
- 모든 함수는 `jax.lax`/벡터화 친화(P8 JIT 대비), in-place 변형 금지.

## 6. 검증 (게이트)
- **해석해 대조**: 단진자(2-DOF의 1관절 고정)의 소진폭 주기가 해석값과 일치, 이중진자 짧은 구간 궤적이 닫힌 해/고정밀 RK4와 일치.
- **RNEA = 손유도**: SymPy로 2-DOF 운동방정식을 손유도해 `tau` 비교(허용오차 내).
- **보존 법칙**: 무토크·무감쇠 시 총 에너지 보존(상대오차 한계 내).
- **백엔드 일치**: `ENGINE_BACKEND=numpy` 와 `=jax`에서 `tau`·궤적이 수치 허용오차 내 일치.
- **통과 기준**: `pytest tests/test_math.py tests/test_rnea_2dof.py tests/test_conservation.py -q`가 두 백엔드 모두 통과.

## 7. 완료 후 리뷰
- 서브에이전트: "RNEA가 공간대수 규약(좌표계·부호)을 일관되게 쓰는가? 손유도와 불일치가 있으면 어느 항인가? 외부 물리엔진을 쓰지 않았는가?"
