# Phase 7 — 로봇 모델 로더 + 관절 제어 + 시각화

> Source of truth: `docs/ROADMAP.md §9 P7`  
> 이전 게이트: P6 ✅ (HQ 레이트레이서 + Recorder)

---

## 목표

- `forge3d.robot` 서브모듈로 UR5-like 6-DOF 팔 로드
- 관절 각도 제어 (프로그래매틱 = 슬라이더 시뮬레이션)
- FK 계산 결과를 실시간 렌더러로 시각화
- 게이트: 관절 스윕 영상 산출 (= 슬라이더 조작 시연)

**헤드리스 제약**: 인터랙티브 슬라이더 UI는 윈도우 표시 장치가 필요하므로  
headless 환경에서는 프로그래매틱 API로 등가 시연.

---

## 범위

| 파일 | 내용 |
|------|------|
| `src/forge3d/robot/__init__.py` | `load`, `Robot` export |
| `src/forge3d/robot/robot.py` | `Robot` 클래스 (FK, 관절 제어, 시각화) |
| `src/forge3d/robot/presets.py` | `make_ur5()` UR5 정의 |
| `src/forge3d/sim/world.py` | `update_body_pose`, `add_static_box` quat 파라미터 |
| `src/forge3d/facade.py` | `World.add(robot)`, `step()` 링크 포즈 갱신 |
| `tests/test_robot.py` | FK 정확성, 관절 제어, 렌더링 smoke |
| `examples/03_robot_interactive.py` | 관절 스윕 영상 gate 예제 |

---

## 설계

### Robot 클래스

```python
arm = f3r.load("ur5")
arm.set_joint(0, np.pi / 2)        # 단일 관절
arm.set_joints([0, -np.pi/2, ...]) # 전체
pos, R = arm.ee_pose()             # FK end-effector
boxes = arm.link_visual_boxes()    # 시각화 박스 목록
```

링크 시각화: 인접 관절 위치를 잇는 박스. 박스 z축 = 연결 방향.

### World 통합

```python
world.add(arm)   # 각 링크 → static box 추가
world.step()     # FK로 박스 포즈 갱신
```

### FK 구현

기존 `kinematics.forward_kinematics(model, q, link_idx=i)` 활용.  
링크 i 시각 박스 = joint_{i} ↔ joint_{i+1} 중점 위치 + 방향 정렬 박스.

---

## Task 체크리스트

- [x] T1: P7 SPEC 작성
- [ ] T2: `robot/__init__.py`, `robot/robot.py`, `robot/presets.py`
- [ ] T3: `sim/world.py` `update_body_pose` + quat 파라미터
- [ ] T4: `facade.py` Robot 통합
- [ ] T5: `tests/test_robot.py`
- [ ] T6: `examples/03_robot_interactive.py`
- [ ] T7: pytest ✅ ruff ✅ mypy ✅ + 영상 산출

---

## 검증 기준

### G1. FK 정확성
- UR5 `q=[0]*6` 에서 EE 위치가 이론값(DH FK 직접계산)과 일치 (≤1mm).
- `q=[π/2, 0, 0, 0, 0, 0]` 회전 후 EE 위치 변화 확인.

### G2. 시각화 렌더링
- `world.add(arm); world.step()` 후 `snapshot()` 에 링크 바디가 포함.
- 링크 박스 수 = 6 (UR5 링크 수).

### G3. 관절 스윕 영상
- `examples/03_robot_interactive.py` 실행 → `robot_sweep.mp4` 산출.
- 팔이 다른 포즈에서 렌더링됨이 육안 확인 가능.
