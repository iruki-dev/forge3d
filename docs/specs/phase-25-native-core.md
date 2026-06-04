# SPEC: Phase 25 — Rust 네이티브 확장 (PyO3 + maturin)

> Claude가 이 작업을 진행하는 **단일 기준**이다. 자기완결적으로 작성한다.  
> 파생: `docs/ROADMAP_v2.md` P25. 규칙: 루트 `CLAUDE.md`. 절차: `docs/WORKFLOW.md`.

---

## 1. 목표 (한 문장)

물리 솔버 핫루프(GJK/EPA, BVH, PGS, SE3 수학)를 Rust(PyO3 + glam + rayon)로 재구현하여 **물리 스텝 ≥10× 속도 향상**을 달성하고, Python 폴백을 유지해 빌드 불가 환경에서도 동작하게 한다.

---

## 2. 범위

### 포함

- **Rust crate 골격** (`src/forge3d_core/` Cargo 워크스페이스)
- **SIMD 수학** (`math_simd.rs`): SE3, 쿼터니언, 공간벡터 — `glam` crate 기반
- **BVH 광역단계** (`bvh.rs`): AABB 트리, 후보쌍 생성 — `rayon` 병렬
- **GJK/EPA** (`gjk_epa.rs`): 볼록 충돌 좁은단계
- **PGS 접촉 솔버** (`pgs_solver.rs`): 10회 반복, 마찰 포함
- **PyO3 바인딩** (`lib.rs`): `forge3d._core` 모듈로 노출
- **maturin 빌드** (`pyproject.toml` 교체, `Cargo.toml` 루트)
- **Python 폴백 자동 선택** (`forge3d/backend.py` 확장)
- **criterion 벤치마크** (`benches/physics_bench.rs`)
- **CI 갱신** (`.github/workflows/ci.yml`: `cargo test` + `maturin build` 추가)

### 제외 (Out of scope)

- 동역학 알고리즘(RNEA/CRBA/ABA) Rust 이식 — JAX JIT으로 충분, P11에서 확인됨
- GPU CUDA 커널 — CPU 전용 환경 제약 유지
- Windows/macOS 크로스컴파일 휠 — CI에 추가하지 않음 (Linux 우선)
- Rust 렌더러 — 렌더링은 Python/GLSL 책임

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d_core/Cargo.toml` | Rust crate 의존성 (pyo3, glam, rayon) |
| `src/forge3d_core/src/lib.rs` | PyO3 모듈 진입점 |
| `src/forge3d_core/src/math_simd.rs` | SIMD SE3/쿼터니언 |
| `src/forge3d_core/src/bvh.rs` | AABB BVH 트리 |
| `src/forge3d_core/src/gjk_epa.rs` | GJK + EPA |
| `src/forge3d_core/src/pgs_solver.rs` | PGS 접촉 솔버 |
| `src/forge3d_core/benches/physics_bench.rs` | criterion 벤치 |
| `Cargo.toml` | 워크스페이스 루트 |
| `rust-toolchain.toml` | stable 채널 고정 |
| `src/forge3d/_core.pyi` | Python 타입 스텁 |

### 수정

| 경로 | 변경 |
|------|------|
| `pyproject.toml` | build-backend: `hatchling` → `maturin`, `[tool.maturin]` 추가 |
| `src/forge3d/backend.py` | `USE_RUST_CORE` 플래그, Rust 임포트 실패 시 Python 폴백 |
| `src/forge3d/collision/detection.py` | Rust `_core.gjk_epa` 우선 호출, 폴백 유지 |
| `src/forge3d/collision/bvh.py` (신규) | Python BVH 폴백 구현 |
| `src/forge3d/contact/solver.py` | Rust `_core.pgs_solve` 우선 호출, 폴백 유지 |
| `.github/workflows/ci.yml` | `cargo test` + `maturin develop` 스텝 추가 |

### 인터페이스 (PyO3 노출 함수)

```python
# forge3d._core (Rust 구현)
def gjk_query(
    verts_a: np.ndarray,  # (N, 3) float64
    verts_b: np.ndarray,  # (M, 3) float64
) -> tuple[bool, np.ndarray, float]:
    """충돌 여부, 접촉법선(3,), 관입깊이"""

def bvh_build(
    aabbs: np.ndarray,   # (N, 6) float64: [min_x..max_z]
) -> object:             # BvhHandle (불투명 핸들)

def bvh_query_pairs(handle: object) -> np.ndarray:
    """충돌 후보쌍 인덱스 (K, 2) int32"""

def pgs_solve(
    contacts: np.ndarray,  # (C, 10) float64: [pos(3), norm(3), pen, mu, m_a, m_b]
    velocities: np.ndarray,  # (N, 6) float64: [v(3), w(3)]
    masses: np.ndarray,  # (N,) float64
    dt: float,
    iterations: int,
) -> np.ndarray:
    """갱신된 속도 (N, 6) float64"""
```

### 의존성

```toml
# Cargo.toml 의존성
[dependencies]
pyo3 = { version = "0.21", features = ["extension-module", "num-complex"] }
numpy = "0.21"   # PyO3 NumPy 브릿지
glam = { version = "0.28", features = ["f64"] }
rayon = "1.10"

[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }
```

---

## 4. 구현 작업 (체크리스트)

- [x] **T1. 빌드 인프라 구축** — 완료 조건: `maturin develop` 성공, `import forge3d._core` 동작
  - `Cargo.toml` (워크스페이스), `rust-toolchain.toml` (stable 채널) 생성
  - `pyproject.toml`: `build-backend = "maturin"`, `[tool.maturin]` 설정
  - `src/forge3d_core/Cargo.toml` + `src/forge3d_core/src/lib.rs` 최소 스텁

- [x] **T2. SIMD 수학 (`math_simd.rs`)** — 완료 조건: Python 결과와 max_abs < 1e-12
  - `glam::DVec3`, `glam::DMat4`로 SE3 곱연산, 쿼터니언 정규화 구현
  - PyO3로 `se3_mul`, `quat_normalize`, `quat_mul`, `quat_rotate_vec`, `se3_inverse` 노출
  - `src/forge3d/_core.pyi` 타입 스텁 작성

- [x] **T3. BVH 광역단계 (`bvh.rs`)** — 완료 조건: `N=500` 바디에서 Python O(N²) 대비 ≥10×
  - 중앙값 분할 AABB 트리 구축
  - PyO3: `bvh_build`, `bvh_query_pairs` 함수 (N=500에서 **22×**, N=1000에서 **25×** 달성)

- [x] **T4. GJK/EPA (`gjk_epa.rs`)** — 완료 조건: 충돌 여부 정확히 감지
  - GJK 볼록 충돌 감지 (simplex + support function)
  - EPA 관입 깊이·법선 계산
  - PyO3: `gjk_query` 함수

- [x] **T5. PGS 접촉 솔버 (`pgs_solver.rs`)** — 완료 조건: 속도 분리 방향 정확, 마찰 클램핑
  - Sequential Impulse (Erin Catto 방식) N회 반복
  - 마찰 원뿔 클램핑 포함
  - PyO3: `pgs_solve` 함수

- [x] **T6. Python 통합 + 폴백** — 완료 조건: `USE_RUST_CORE=0` 시 Python 경로, `=1` 시 Rust 경로
  - `backend.py`에 `USE_RUST_CORE` 자동 감지 (import 실패 시 False)
  - `collision/detection.py`, `contact/solver.py` 분기 처리

- [x] **T7. 벤치마크** — 완료 조건: 결과 표를 `docs/benchmarks/p25.md`에 기록
  - `N=100/500/1000` 바디 씬 물리 스텝 ns 측정
  - Python(NumPy) / Python(JAX) / Rust(PyO3) 세 경로 비교

- [x] **T8. 검증 스위트** — 완료 조건: `pytest tests/ -q` PASS (474 passed) ✅
  - `tests/test_p25_rust_core.py`: GJK 결과 비교, PGS 수렴, BVH 후보쌍 일치
  - 기존 458개 테스트 회귀 없음 확인

---

## 5. 엣지 케이스 / 제약

- `pyo3` GIL 해제(`allow_threads`): BVH 빌드와 PGS 솔버는 Python 객체 접근 없으므로 GIL 해제 가능 → 멀티스레드 호출 가능.
- `float64` 강제: `glam::f64` 피처 필수. glam 기본은 `f32`.
- Rust 패닉 vs Python 예외: `PyErr::new::<PyRuntimeError, _>(msg)` 패턴으로 변환. 패닉이 Python 인터프리터를 죽이지 않도록.
- 헤드리스 CI: Rust 빌드는 렌더러 의존성 없음. `cargo test`는 OpenGL 없이 통과.
- 폴백 경로: `ENGINE_BACKEND=numpy pytest ...` 는 Rust 없이도 통과해야 함.

---

## 6. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `cargo test` 0 failures | `cargo test --workspace` |
| G2 | Python GJK vs Rust GJK: max_abs(법선) < 1e-9 | `tests/test_p25_rust_core.py::test_gjk_parity` |
| G3 | Python PGS vs Rust PGS: max_abs(속도) < 1e-8 | `tests/test_p25_rust_core.py::test_pgs_parity` |
| G4 | 물리 스텝 ≥10× 향상 (N=500 바디) | criterion 벤치 or `tests/test_p25_rust_core.py::test_speedup` |
| G5 | 전체 기존 테스트 PASS (회귀 없음) | `pytest tests/ -q` |
| G6 | `USE_RUST_CORE=0 pytest tests/ -q` PASS (폴백) | 환경변수 토글 테스트 |
| G7 | `import forge3d; forge3d.__version__` 동작 | 스모크 테스트 |

---

## 7. 완료 후 리뷰

- P25 diff를 이 SPEC과 대조: 인터페이스 일치, 폴백 경로 존재, 벤치마크 기록 여부 확인.
- 다음 Phase(P26) 착수 전 게이트 G1~G7 전부 통과 필수.
