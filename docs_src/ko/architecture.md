# 아키텍처

forge3d는 하나의 원칙을 기반으로 구축됩니다: **물리와 렌더러는 서로를 알지 못합니다**.

---

## SceneSnapshot 계약

```
world.step()               # 순수 물리 — 렌더러 임포트 없음
snap = world.snapshot()    # SceneSnapshot — 순수 데이터, 물리 없음
frame = renderer.render(snap)  # 렌더러는 데이터만 알면 됩니다
```

`SceneSnapshot`은 물리와 렌더링 사이의 유일한 다리입니다. 다음을 포함합니다:

- 바디별 트랜스폼 (위치 + 3×3 회전 행렬)
- 형상 디스크립터 (박스 / 구 / 캡슐 / 메시)
- 재질 파라미터 (색상, 거칠기, 금속성, 발광, 텍스처 경로)
- 카메라 및 조명 설정
- 지형 높이맵 데이터

즉, 렌더러를 교체하거나 렌더링을 완전히 건너뛸 수(헤드리스 학습) 있으며, 물리 코드는 전혀 건드리지 않아도 됩니다.

```
물리 코어                  → SceneSnapshot →  RealtimeRenderer   (OpenGL 3.3, PBR)
(RNEA / CRBA / ABA)                       →  DeferredRenderer   (OpenGL 4.3, G-버퍼)
                                           →  HQRenderer         (NumPy 레이트레이서)
                                           →  헤드리스 / 학습      (스냅샷 불필요)
```

---

## 모듈 맵

```
src/forge3d/
├── facade.py          # World, Body — 공개 API 진입점
├── math/              # 벡터, 쿼터니언, SE(3) 수학
├── dynamics/          # RNEA, CRBA, ABA, semi-implicit Euler
├── collision/         # GJK, EPA, SAT, 구/캡슐 해석해
├── contact/           # PGS 솔버, Baumgarte, 쿨롱 마찰
├── model/             # RigidBody, Shape, Material 데이터 모델
├── sim/               # World 구현, 이벤트, 직렬화, JAX 배치
├── render/            # RealtimeRenderer, DeferredRenderer, HQRenderer
│   └── shaders/       # GLSL 셰이더 소스
├── robot/             # UR5 모델, FK, IK, 야코비안
├── ecs/               # EntityWorld, 컴포넌트, 시스템
├── animation/         # Skeleton, AnimationClip, FABRIK IK
├── audio/             # AudioSystem, AudioClip (WAV/OGG)
├── particle/          # ParticleEmitter, ParticleSystem
├── scene/             # SceneNode, Prefab, SceneManager
├── ui/                # Canvas, DebugPanel, ImGui 바인딩
└── editor/            # EditorApp, 기즈모, EditorLayout
```

Rust 코어 (선택):
```
src/forge3d_core/      # PyO3 크레이트 — GJK/EPA, PGS, BVH, SE(3) 수학
```

---

## 설계 규칙

### 1. 물리 ↔ 렌더 격리

`math/`, `dynamics/`, `collision/`, `contact/`, `model/`, `sim/` 안의 코드는
렌더러를 절대 임포트하지 않습니다. 물리↔렌더 연결은 `SceneSnapshot` 단 하나뿐입니다.

### 2. 함수형 코어

상태는 입력 → 출력으로 전달됩니다. 배열은 불변으로 다룹니다. 이 덕분에 동일 코드가
NumPy와 JAX 백엔드 모두에서 동작합니다.

### 3. 백엔드 독립성

```bash
ENGINE_BACKEND=numpy python sim.py   # 기본값
ENGINE_BACKEND=jax   python sim.py   # JIT 컴파일 + vmap
```

모든 물리 코드는 두 백엔드에서 동일하게 동작해야 합니다.

### 4. 라이브러리 ↔ 응용 분리

`src/forge3d/` — 라이브러리 (1급 산출물)  
`apps/robot_rl/` — 응용 (라이브러리를 외부처럼 임포트만 함)

### 5. 공개 API는 작게

처음 만나는 개념 5~6개(`World/Body/Joint/Shape/Viewer/Recorder`) 이내,
진입 예제 15줄 이내, 스마트 기본값, z-up·SI 단위.

---

## 데이터 흐름

```
사용자 코드
    │
    ▼
World.step(dt)
    │  세미-임플리시트 오일러
    │  충돌 감지 (SAT / GJK+EPA / BVH)
    │  접촉 해결 (PGS + Baumgarte)
    │  이벤트 디스패치
    ▼
Body.position, Body.velocity, ...  (업데이트됨)
    │
    ▼
world.snapshot()  →  SceneSnapshot
    │
    ├──▶ renderer.render(snap)  →  np.ndarray (H, W, 3)
    ├──▶ viewer.draw()
    └──▶ recorder.record_frame()
```

---

## 성능 경로

| 경로 | 스택 | 적합한 용도 |
|------|------|------------|
| CPU NumPy | Python + NumPy | 개발, 디버깅, 소규모 씬 |
| CPU JAX JIT | Python + JAX JIT | 단일 환경 + 더 빠른 루프 |
| CPU JAX vmap | JAX JIT + vmap | 배치 RL (수천 개 환경 병렬) |
| Rust 코어 | PyO3 핫루프 | GJK/EPA, PGS, BVH ≥10× 가속 |

---

## 검증 전략

`validation/` 디렉터리는 PyBullet과 MuJoCo를 **기준값 대조 전용**으로만 사용합니다.
forge3d 코어에는 외부 물리 엔진 의존성이 없습니다.

```
tests/
├── test_dynamics.py      # 에너지·운동량 보존
├── test_collision.py     # SAT, GJK, EPA 수치 정확도
├── test_contact.py       # PGS 솔버 수렴
├── test_robot.py         # UR5 FK vs 해석해
├── test_backends.py      # np ↔ jnp 출력 일치
└── ...
validation/
├── compare_pybullet.py   # 동일 입력 → 허용오차 내 비교
└── compare_mujoco.py
```
