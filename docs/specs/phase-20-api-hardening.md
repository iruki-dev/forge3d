# Phase 20 SPEC — API 강화 & 오류 메시지

> Source of truth for P20. Only changes described here are permitted.

## 목표

사용자가 잘못된 인자를 넘겼을 때 **무엇이 잘못됐는지 정확하게** 알 수 있다.  
공개 API의 모든 경계에서 입력을 검증하고, 명확한 에러 메시지를 제공한다.

### 참조
- **NumPy**: `ValueError: operands could not be broadcast together with shapes (3,) (4,)`
- **Gymnasium**: `AssertionError: observation_space.contains(obs)`
- **Pydantic**: 자동 타입 검증 + 친절한 에러 위치 표시

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `Forge3dError` 예외 계층 정의 | `src/forge3d/errors.py` (신규) |
| T2 | `World` 메서드 인자 검증 (mass > 0, size > 0, gravity 3-vector 등) | `src/forge3d/facade.py` |
| T3 | `Body` 프로퍼티 setter 검증 | `src/forge3d/facade.py` |
| T4 | `Material` 색상·roughness 범위 검증 | `src/forge3d/facade.py` |
| T5 | `Viewer`·`Recorder` 인자 검증 | `src/forge3d/viewer.py`, `recorder.py` |
| T6 | 모든 공개 모듈에 `__all__` 명시적 선언 | 각 `__init__.py` |
| T7 | `DeprecationWarning` 프레임워크 (`_deprecated` 데코레이터) | `src/forge3d/errors.py` |
| T8 | 테스트 10종 (오류 케이스 전용) | `tests/test_p20_api.py` (신규) |

---

## 예외 계층

```python
class Forge3dError(Exception): ...
class PhysicsError(Forge3dError): ...     # 물리 설정 오류
class ValidationError(Forge3dError): ... # 인자 검증 실패
class RenderError(Forge3dError): ...      # 렌더러 오류
class AssetError(Forge3dError): ...       # 에셋 로드 실패
```

---

## 에러 메시지 예시

```
ValidationError: World.add_box() — mass must be positive, got mass=-1.0
ValidationError: World.add_box() — size components must be positive, got size=(1, 0, 1)
ValidationError: World(gravity=...) — gravity must be a 3-element sequence, got gravity=(0, -9.81)
ValidationError: Material(roughness=...) — roughness must be in [0, 1], got roughness=1.5
```

---

## `__all__` 선언 예시

```python
# src/forge3d/__init__.py
__all__ = [
    "World", "Body", "Shape", "Material",
    "App", "Input", "Key",
    "OrbitCamera", "FollowCamera",
    "Viewer", "Recorder",
    "CollisionEvent",
    "Forge3dError", "ValidationError", "PhysicsError",
    "__version__",
]
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 음수 mass → `ValidationError` + 명확한 메시지 | `pytest.raises(ValidationError)` |
| G2 | 잘못된 gravity 형태 → `ValidationError` | `test_gravity_validation` |
| G3 | 모든 공개 모듈에 `__all__` 존재 | `grep -r "__all__" src/forge3d/` |
| G4 | `import forge3d; forge3d.__all__` 에 의도한 심볼 모두 포함 | 확인 |
| G5 | pytest + ruff + mypy 통과 | — |
