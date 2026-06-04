# forge3d v2 — 마스터 로드맵 (P25~P35)

> **이 문서의 역할**: v1.0.0(P0~P24) 완료 이후 forge3d를 "Python-first 고성능 게임/시뮬레이션 엔진"으로 전환하는 *정식 기준(source of truth)*.  
> v1 로드맵은 `docs/ROADMAP.md` 유지. 이 문서는 그 위에 쌓인다.  
> 작업 규칙은 루트 `CLAUDE.md`, 개별 작업은 `docs/specs/phase-NN-*.md` SPEC을 따른다.

---

## 1. v2 비전: "Python idioms, native speed"

v1은 순수 Python(NumPy/JAX)으로 물리 코어와 렌더러를 직접 구현하는 데 성공했다.  
v2의 목표는 세 가지 축으로 엔진을 고도화하는 것이다:

| 축 | 목표 | 핵심 수단 |
|----|------|-----------|
| **① 런타임 성능** | 물리 스텝 ≥10×, 렌더 드로우콜 ≥5× | Rust 확장 (PyO3 + maturin) |
| **② 그래픽 파이프라인** | 지연 PBR + CSM + SSAO + HDR | GLSL 4.3 컴퓨트 셰이더 + 모던 OpenGL |
| **③ API 생태계** | ECS 씬 그래프 + 오디오 + 애니메이션 + UI | Python 고수준 API + 컴포넌트 시스템 |

판단 기준은 변하지 않는다: **"동역학과 접촉을 누가 푸는가?" → 답은 언제나 우리 코드.**  
단, 그 코드가 Python이 아닌 Rust로 작성될 수 있다.

---

## 2. 아키텍처 벤치마킹 — Unity vs Pygame vs forge3d

### 2.1 Unity 핵심 설계 언어 (채택 대상)

| Unity 구조 | 설명 | forge3d v2가 채택할 것 |
|------------|------|----------------------|
| **ECS/DOTS** | Entity+Component+System. 데이터 지향 메모리 레이아웃 | ECS 씬 그래프 (P27) |
| **Burst Compiler** | C# → SIMD native 코드 AOT 컴파일 | Rust + PyO3 (P25) |
| **Job System** | 멀티스레드 작업 큐 (IJob, IJobParallelFor) | Rust rayon 스레드풀 (P25) |
| **SRP (URP/HDRP)** | 교체 가능한 렌더 파이프라인 | Renderer ABC (이미 구현) + 지연 PBR (P26) |
| **Scriptable Pass** | RenderPass 단위 파이프라인 구성 | RenderPass 추상 (P26) |
| **Shader Graph** | 노드 기반 GLSL 생성 | (P35 이후 선택) |
| **OnCollision* 콜백** | 충돌 이벤트를 컴포넌트에서 처리 | 이미 P17 구현, ECS 연동 (P27) |
| **AnimationClip + Blend Tree** | 골격 애니메이션 + 블렌딩 | P29 |
| **Package Manager** | 모듈 의존성 분리 | maturin + pip extra (P25) |

### 2.2 Pygame 핵심 설계 언어 (유지할 것)

| Pygame 구조 | 설명 | forge3d v2 대응 |
|------------|------|----------------|
| **모듈 API** | `pygame.display`, `pygame.event` 등 플랫 API | `forge3d.World`, `forge3d.App` 플랫 퍼사드 유지 |
| **Event loop** | `while running: for e in pygame.event.get()` | `App.on_update()` 루프 유지 |
| **Surface** | 픽셀 버퍼 직접 접근 | `Recorder.frame_buffer` NumPy 배열 유지 |
| **Group/Sprite** | 오브젝트 그룹 관리 | ECS `World.query()` (P27) |
| **진입 15줄 규칙** | 쉬운 온보딩 | API 최상위 개념 ≤8개 유지 |

### 2.3 forge3d v2 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        공개 API (Python Facade)                           │
│   World · Body · Entity · App · Viewer · Recorder · Audio · Animator     │
│   ← Pygame식 플랫 API                    ECS 씬 그래프 →                 │
└──────────┬───────────────────────────────────────────┬────────────────────┘
           │                                           │
    ┌──────▼──────────────────┐           ┌────────────▼──────────────────┐
    │   물리 코어 (np↔jnp↔rs) │           │    렌더링 계층                │
    │  ┌─────────────────────┐│           │  ┌──────────────────────────┐ │
    │  │  Rust 확장 (PyO3)   ││           │  │  DeferredRenderer (GL4.3)│ │
    │  │  ├ gjk_epa.rs       ││           │  │  ├ GBuffer Pass          │ │
    │  │  ├ bvh.rs           ││           │  │  ├ Lighting Pass (SSAO)  │ │
    │  │  ├ pgs_solver.rs    ││           │  │  ├ PostProcess (HDR/Bloom)│ │
    │  │  └ math_simd.rs     ││           │  │  └ Particle Pass          │ │
    │  └─────────────────────┘│           │  ├──────────────────────────┤ │
    │  Python 레이어           │           │  │  HQRenderer (ray-trace)  │ │
    │  ├ dynamics/ (JAX JIT)  │           │  └──────────────────────────┘ │
    │  ├ contact/ (JAX JIT)   │           └────────────┬──────────────────┘
    │  └ sim/ (World step)    │                        │
    └──────────┬──────────────┘           ┌────────────▼──────────────────┐
               └──────────────────────────►   SceneSnapshot (공유 계약)   │
                                          └───────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │                  ECS 계층 (P27)                                  │
    │   EntityWorld · Component · System · Transform 계층              │
    │   ↕ (Body/World API와 양방향 호환)                               │
    └─────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐  ┌────────────────┐  ┌──────────────────────┐
    │   Audio (P28)    │  │ Animation (P29)│  │  UI / ImGui (P32)    │
    │   OpenAL 3D      │  │ 골격·FABRIK IK │  │  Canvas + Inspector  │
    └──────────────────┘  └────────────────┘  └──────────────────────┘
```

---

## 3. 다중 언어 전략

v2부터 **Python이 핵심 언어**지만 성능 임계 경로는 다른 언어로 구현한다.

### 3.1 언어 역할 분리

| 언어 | 역할 | 도구 |
|------|------|------|
| **Python** | 공개 API, 게임 로직, ML 연동, 설정 | - |
| **Rust** | 물리 솔버 핫루프, BVH, GJK/EPA, SIMD 수학 | PyO3 + maturin |
| **GLSL 4.3** | 렌더링 셰이더 (정점/프래그먼트/컴퓨트) | moderngl |
| **C/C++** | 오디오 백엔드, imgui 바인딩 (필요 시) | CFFI / ctypes |
| **JAX (XLA HLO)** | 다중 환경 vmap, RL 학습 그래디언트 | jax.jit + vmap |

### 3.2 경계 규칙

- **Rust 확장은 `src/forge3d_core/`** (별도 crate)에 둔다. `src/forge3d/`는 Python만.
- Rust 코드는 **PyO3 `#[pymodule]`** 로 `forge3d._core`로 노출; 사용자는 `forge3d._core`를 직접 쓰지 않는다.
- **물리 코어(`dynamics/`, `collision/`, `contact/`)의 Python 구현은 삭제하지 않고 유지**한다 — Rust 불가 환경(ARM, Windows) 폴백.
- 셰이더 파일(`.glsl`, `.vert`, `.frag`, `.comp`)은 `src/forge3d/render/shaders/`에 둔다.

---

## 4. 단계별 로드맵 (P25~P35)

> 각 Phase는 **이전 Phase의 검증 기준 통과**가 전제다.  
> 첫 번째 SPEC 완료 후 다음 Phase 계획을 재검토하는 "게이트 리뷰" 포함.

| Phase | 내용 | 완료 기준 | 우선순위 |
|-------|------|-----------|---------|
| **P25** | Rust 네이티브 확장 (PyO3 + maturin) | 물리 스텝 ≥10× 향상, 전체 테스트 PASS | ★★★ (1위) |
| **P26** | 모던 렌더링 파이프라인 (지연 PBR + CSM + SSAO + HDR) | G-Buffer 렌더링, 60FPS 유지, 골든 이미지 비교 | ★★★ |
| **P27** | Entity Component System (ECS) | `World.query()` + 컴포넌트 아키텍처 동작 | ★★★ |
| **P28** | 오디오 시스템 (3D 공간음) | 충돌 이벤트→사운드, 3D 위치 감쇠 | ★★ |
| **P29** | 애니메이션 시스템 (골격 + FABRIK IK) | 블렌드 트리 동작, IK 팔 제어 | ★★ |
| **P30** | 씬 관리 (부모/자식 Transform 계층) | 부모 이동 → 자식 연동, 씬 로드/언로드 | ★★ |
| **P31** | 파티클 시스템 (GPU 컴퓨트) | 10만 파티클 60FPS, 물리 충돌 반응 | ★ |
| **P32** | UI 시스템 (ImGui + 캔버스) | 인스펙터 패널, HUD 오버레이 | ★ |
| **P33** | 씬 에디터 (ImGui 기반) | 오브젝트 선택/이동, 실시간 인스펙터 | ★ |
| **P34** | Vulkan / wgpu 백엔드 (선택) | wgpu-py 렌더러로 동일 SceneSnapshot 렌더 | 선택 |
| **P35** | v2.0.0 릴리즈 | PyPI v2.0.0, 마이그레이션 가이드, 벤치마크 | ★★★ |

---

## 5. 기술 스택 (v2 추가)

| 영역 | v1 스택 | v2 추가 |
|------|---------|--------|
| 물리 코어 | NumPy / JAX | + Rust (PyO3, glam, rayon) |
| 렌더링 | moderngl + Blinn-Phong | + 지연 PBR, GLSL 4.3 컴퓨트 셰이더, CSM, SSAO |
| 빌드 | hatchling (순수 Python) | + maturin (Rust 확장 포함 혼합 빌드) |
| 오디오 | 없음 | OpenAL (python-openal 또는 sounddevice) |
| UI | imgui (기본) | imgui-bundle 풀 통합 |
| 테스트 | pytest | + cargo test (Rust 단위), criterion (Rust 벤치) |
| CI | GitHub Actions (Python) | + `rust-toolchain.toml`, `maturin build` |

---

## 6. 디렉터리 구조 (v2 추가)

```
forge3d-project/
├── src/
│   ├── forge3d/              # Python 라이브러리 (기존 + v2 확장)
│   │   ├── _core.pyi         # Rust 확장 타입 스텁
│   │   ├── ecs/              # Entity Component System (P27)
│   │   ├── audio/            # 오디오 시스템 (P28)
│   │   ├── animation/        # 애니메이션 시스템 (P29)
│   │   ├── scene/            # 씬 관리 (P30)
│   │   ├── particle/         # 파티클 시스템 (P31)
│   │   ├── ui/               # UI 시스템 (P32)
│   │   └── render/
│   │       ├── shaders/      # .vert .frag .comp 파일
│   │       ├── deferred/     # G-Buffer 지연 렌더러 (P26)
│   │       └── passes/       # RenderPass 단위 (P26)
│   │
│   └── forge3d_core/         # Rust crate (PyO3 확장)
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   ├── gjk_epa.rs    # GJK/EPA 구현
│       │   ├── bvh.rs        # BVH 광역단계
│       │   ├── pgs_solver.rs # PGS 접촉 솔버
│       │   └── math_simd.rs  # SIMD 수학 (glam 기반)
│       └── benches/          # criterion 벤치마크
│
├── Cargo.toml                # 워크스페이스 루트
├── rust-toolchain.toml       # stable 채널 고정
└── pyproject.toml            # maturin 빌드 시스템으로 교체
```

---

## 7. API 호환성 약속

- **v1 API는 v2에서 Breaking change 없음**: `World`, `Body`, `Viewer`, `Recorder` 시그니처 동결.
- ECS API는 `v1 Body API`와 **병렬 공존**. 점진적 마이그레이션 지원.
- Rust 확장 실패 시(빌드 불가 환경) Python 폴백 자동 선택.
- `forge3d.__version__` = `"2.0.0"`, 하위 호환 플래그 `forge3d.compat.v1 = True`.

---

## 8. 검증 전략 (v2 추가)

| 레벨 | 도구 | 기준 |
|------|------|------|
| Rust 단위 | `cargo test` | 모든 `#[test]` 통과 |
| Rust 벤치 | `cargo bench` (criterion) | P25: 물리 스텝 ≥10× vs Python |
| Python 통합 | `pytest` | 전체 스위트 PASS (Rust 포함) |
| 렌더 회귀 | 골든 이미지 픽셀 비교 | SSIM ≥ 0.98 |
| 성능 회귀 | `pytest-benchmark` | 전 버전 대비 퇴보 없음 |
| API 호환 | `examples/` 그대로 동작 | v1 예제가 v2에서 수정 없이 실행 |

---

## 9. 주요 위험과 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| Rust 빌드 복잡도 | 높음 | maturin 표준화 + CI 자동 휠 빌드 (Linux/macOS/Windows) |
| Python ↔ Rust GIL 경계 비용 | 중 | 배치 전달(배열 단위), PyO3 no-GIL 모드 실험 |
| GLSL 컴퓨트 셰이더 헤드리스 | 중 | EGL/Xvfb 기존 전략 유지 + 컴퓨트 전용 오프스크린 |
| ECS ↔ Body API 이중 관리 | 높음 | ECS는 Body를 내부적으로 래핑(ECS가 Body를 알지만 역방향 금지) |
| 오디오 헤드리스 | 낮음 | null 오디오 드라이버 폴백 |
| v1 호환 테스트 누락 | 높음 | `tests/compat/` 별도 스위트 유지 |
