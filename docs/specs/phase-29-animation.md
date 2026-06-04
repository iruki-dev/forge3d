# SPEC: Phase 29 — 애니메이션 시스템 (골격 + FABRIK IK)

> 파생: `docs/ROADMAP_v2.md` P29. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

골격(Bone/Skin) 애니메이션과 FABRIK IK 솔버를 구현하여 로봇 팔 제어와 캐릭터 블렌드 트리를 ECS 컴포넌트로 제공한다.

---

## 2. 범위

### 포함

- **Skeleton**: 본(Bone) 계층, 로컬/월드 행렬, 바인드 포즈
- **AnimationClip**: 키프레임(위치·회전·스케일) 선형/구면선형 보간(SLERP)
- **AnimationPlayer** 컴포넌트: 클립 재생, 루프, 속도 배율
- **BlendTree**: 두 클립 가중 블렌딩 (1D 파라미터 기반)
- **FABRIK IK 솔버**: N링크 체인, 목표 위치 수렴 (UR5 로봇 팔 적용)
- **IKTarget** 컴포넌트: 목표 Transform을 ECS 엔티티로 지정
- **AnimationSystem**: ECS 시스템, 본 행렬 일괄 업데이트

### 제외 (Out of scope)

- 모프 타깃(블렌드 쉐이프) — v2.2 이후
- 역운동학 이외 구속(IK+Joint Limit 조합) — P16 조인트 제약 활용
- BVH/FBX 파일 로더 — v2.2 이후 (JSON 클립 포맷 우선)

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/animation/__init__.py` | 공개 애니메이션 API |
| `src/forge3d/animation/skeleton.py` | `Bone`, `Skeleton` |
| `src/forge3d/animation/clip.py` | `AnimationClip`, 키프레임 보간 |
| `src/forge3d/animation/player.py` | `AnimationPlayer` 컴포넌트 |
| `src/forge3d/animation/blend_tree.py` | `BlendTree` 1D 블렌딩 |
| `src/forge3d/animation/ik_fabrik.py` | FABRIK IK 솔버 |
| `src/forge3d/animation/system.py` | `AnimationSystem` |
| `tests/test_p29_animation.py` | 단위 + 통합 테스트 |

### 핵심 인터페이스

```python
@dataclass
class Bone:
    name: str
    local_matrix: np.ndarray   # (4, 4) 로컬 변환
    parent_idx: int | None     # -1 = 루트

@dataclass
class Skeleton:
    bones: list[Bone]
    def world_matrices(self) -> np.ndarray:
        """(N, 4, 4) 월드 행렬 배열"""

@dataclass
class AnimationClip:
    duration: float
    fps: float
    keyframes: dict[str, np.ndarray]  # bone_name → (T, 10) [t, pos(3), quat(4), scale(3)]
    def sample(self, t: float) -> dict[str, np.ndarray]:
        """t 시각의 본 로컬 행렬 딕셔너리"""

@dataclass
class AnimationPlayer(Component):
    skeleton: Skeleton
    clip: AnimationClip | None = None
    blend_tree: BlendTree | None = None
    speed: float = 1.0
    loop: bool = True
    _time: float = 0.0

class FABRIKSolver:
    def solve(
        self,
        chain: list[np.ndarray],  # [(3,)] 링크 위치 리스트
        target: np.ndarray,       # (3,) 목표 위치
        max_iterations: int = 20,
        tolerance: float = 1e-4,
    ) -> list[np.ndarray]:
        """수렴된 링크 위치 리스트"""
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. Skeleton + Bone 계층** — 완료 조건: 루트→자식 월드 행렬 재귀 계산 정확
- [ ] **T2. AnimationClip + 보간** — 완료 조건: SLERP 쿼터니언 보간 오차 < 1e-6
- [ ] **T3. AnimationPlayer + AnimationSystem** — 완료 조건: `dt` 누적으로 클립 재생
- [ ] **T4. BlendTree 1D** — 완료 조건: 파라미터 0.0→1.0에서 두 클립 가중 평균 행렬
- [ ] **T5. FABRIK IK 솔버** — 완료 조건: 3링크 체인 목표 수렴 ≤ 20 반복, 오차 < 1e-4m
- [ ] **T6. UR5 IK 연동** — 완료 조건: ECS `IKTarget` 이동 시 UR5 본 체인 추종
- [ ] **T7. 테스트** — 완료 조건: 10개 테스트 PASS

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 골격 월드 행렬 정확성 (FK vs 수동 계산) | `test_p29_animation::test_skeleton_fk` |
| G2 | FABRIK 수렴: 3링크 체인 오차 < 1e-4m | `test_p29_animation::test_fabrik_convergence` |
| G3 | BlendTree 중간 파라미터에서 보간 행렬 검증 | `test_p29_animation::test_blend_tree` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
