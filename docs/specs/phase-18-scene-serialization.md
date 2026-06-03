# Phase 18 SPEC — 씬 직렬화 (저장·불러오기·리플레이)

> Source of truth for P18. Only changes described here are permitted.

## 목표

시뮬레이션 상태를 파일로 저장하고 불러온다. 재현 가능한 리플레이를 제공한다.

### 참조
- **Pymunk**: `pickle` 직렬화 (Space 전체)
- **Godot**: `PackedScene` → `tscn` / `scn` 포맷; `get_tree().pack(node)`
- **MuJoCo**: `mj_saveModel` XML + `mj_saveStateToFile` binary state
- **Unity**: `EditorSceneManager.SaveScene`

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `WorldSnapshot` — 전체 월드 상태 데이터클래스 | `src/forge3d/io/world_snapshot.py` (신규) |
| T2 | `World.save(path)` → JSON 파일 | `src/forge3d/facade.py` |
| T3 | `World.load(path)` → World 복원 | `src/forge3d/facade.py` |
| T4 | `StateRecorder` — 스텝마다 state 기록 | `src/forge3d/io/state_recorder.py` (신규) |
| T5 | `StateRecorder.replay(world)` — 기록된 state 재현 | `src/forge3d/io/state_recorder.py` |
| T6 | 테스트 5종 | `tests/test_p18_serialization.py` (신규) |
| T7 | 예제: 저장 후 불러오기, 리플레이 영상 | `examples/07_save_load.py` |

---

## JSON 포맷 (world_snapshot.json)

```json
{
  "version": "0.4.0",
  "gravity": [0, 0, -9.81],
  "time": 1.234,
  "bodies": [
    {
      "id": 0,
      "name": "box_0",
      "shape_type": "box",
      "shape_params": {"size": [1, 1, 1]},
      "position": [0, 0, 0.5],
      "orientation": [1, 0, 0, 0],
      "velocity": [0, 0, 0],
      "angular_velocity": [0, 0, 0],
      "mass": 1.0,
      "restitution": 0.3,
      "friction": 0.5,
      "is_static": false,
      "material": {"color": "red", "roughness": 0.5, "metallic": 0.0}
    }
  ],
  "joints": []
}
```

---

## StateRecorder 설계

```python
rec = StateRecorder(world)
rec.start()

for _ in range(1000):
    world.step()
    rec.record()        # 현재 state 기록

rec.save("sim.states")  # npz 압축 (position/orientation/velocity per body per frame)
```

리플레이:
```python
world2 = World.load("world.json")
rec2 = StateRecorder.load("sim.states")
rec2.replay(world2, dt=1/60)  # viewer와 함께 사용 가능
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `world.save()` → JSON 파일 생성 | 파일 존재 확인 |
| G2 | `World.load()` → 동일 상태 복원 (위치 오차 < 1 μm) | 수치 비교 |
| G3 | 저장→불러오기→스텝 후 결과가 원본과 일치 (determinism) | `test_determinism_after_load` |
| G4 | StateRecorder 리플레이 — 프레임별 위치 재현 | `test_replay_positions` |
| G5 | pytest + ruff + mypy 통과 | — |
