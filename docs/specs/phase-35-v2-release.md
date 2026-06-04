# SPEC: Phase 35 — v2.0.0 릴리즈

> 파생: `docs/ROADMAP_v2.md` P35. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

P25~P33의 모든 검증 기준을 통과하고 **forge3d v2.0.0**을 PyPI에 공식 배포하며, 마이그레이션 가이드와 전체 벤치마크 리포트를 게시한다.

---

## 2. 범위

### 포함

- **버전 2.0.0 선언**: `__version__`, `pyproject.toml`, CHANGELOG
- **v1 → v2 마이그레이션 가이드** (`docs_src/migration_v2.md`)
- **전체 벤치마크 리포트** (`docs/benchmarks/v2_summary.md`)
  - 물리 스텝: NumPy vs JAX vs Rust (P25 결과)
  - 렌더링 FPS: 지연 PBR (P26 결과)
  - ECS 쿼리 처리량 (P27 결과)
- **API 안정성 선언**: v2 stable/experimental 목록
- **maturin 기반 PyPI 배포**: Linux x86_64 + pure Python 휠 두 가지
- **문서 사이트 갱신**: MkDocs v2 API 레퍼런스, 튜토리얼, 예제

### 제외 (Out of scope)

- P34(wgpu) — 선택 Phase, v2.0 필수 아님
- Windows/macOS Rust 휠 크로스컴파일 — v2.1에서 추가

---

## 3. 영향 파일

| 파일 | 변경 |
|------|------|
| `src/forge3d/__init__.py` | `__version__ = "2.0.0"` |
| `pyproject.toml` | version 2.0.0, maturin 빌드, v2 의존성 |
| `CHANGELOG.md` | v2.0.0 항목 (P25~P33 변경 정리) |
| `docs_src/migration_v2.md` | v1 → v2 마이그레이션 가이드 |
| `docs/benchmarks/v2_summary.md` | 전체 벤치마크 결과 |
| `docs_src/api/` | ECS, Audio, Animation, Scene, Particle, UI API 레퍼런스 추가 |
| `README.md` | v2 기능 목록, 벤치마크 배지, 설치 명령 갱신 |

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. 릴리즈 체크리스트 전 게이트 확인** — P25~P33 모든 게이트 PASS 확인
- [ ] **T2. CHANGELOG v2.0.0 작성** — P25~P33 변경 요약
- [ ] **T3. 마이그레이션 가이드** — 완료 조건: v1 예제 → v2 동등 코드 매핑
- [ ] **T4. 벤치마크 리포트 작성** — 완료 조건: 수치 결과 + 비교 표
- [ ] **T5. API 안정성 선언** — stable/experimental 목록 문서화
- [ ] **T6. `maturin build --release`** — Linux x86_64 + pure Python 휠 생성
- [ ] **T7. `twine check dist/*`** — PASSED
- [ ] **T8. MkDocs 빌드** — `mkdocs build` 성공
- [ ] **T9. TestPyPI 배포** — `pip install --index-url ... forge3d==2.0.0` 성공
- [ ] **T10. `docs/PROGRESS.md` 최종 갱신**

---

## 5. v2 API 안정성 선언

### Stable (Breaking change 없음, v3까지 보장)

```
# v1 계승 (변경 없음)
forge3d.World, forge3d.Body, forge3d.Shape, forge3d.Material
forge3d.App, forge3d.Viewer, forge3d.Recorder
forge3d.Input, forge3d.OrbitCamera

# v2 신규 stable
forge3d.EntityWorld, forge3d.Entity
forge3d.Transform, forge3d.Rigidbody, forge3d.Collider
forge3d.MeshRenderer, forge3d.Script
forge3d.PhysicsSystem, forge3d.RenderSystem, forge3d.AudioSystem
forge3d.AnimationPlayer, forge3d.FABRIKSolver
forge3d.SceneManager, forge3d.Prefab
forge3d.ParticleEmitter
forge3d.DebugPanel, forge3d.Canvas
```

### Experimental (v2.x에서 변경 가능)

```
forge3d._core         # Rust 확장 직접 접근
forge3d.render.wgpu   # wgpu 백엔드
forge3d.editor        # 씬 에디터 (P33)
forge3d.ecs.query     # 고급 쿼리 API
```

---

## 6. 릴리즈 체크리스트

- [ ] `cargo test --workspace` — 0 failures
- [ ] `pytest tests/ -q` — 0 failures
- [ ] `ruff check . && ruff format --check .` — 0 errors
- [ ] `mypy src/` — 0 errors
- [ ] `mkdocs build` — 성공
- [ ] `maturin build --release` — `dist/` 생성
- [ ] `twine check dist/*` — PASSED
- [ ] `pip install dist/forge3d-2.0.0-*.whl` → `import forge3d; forge3d.__version__ == "2.0.0"` ✅
- [ ] v1 예제(`examples/01_falling_box_realtime.py`) 수정 없이 동작
- [ ] CHANGELOG.md v2.0.0 항목 완성
- [ ] GitHub release 태그 `v2.0.0`

---

## 7. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `pip install forge3d==2.0.0` 성공 | pip 설치 확인 |
| G2 | v1 예제가 v2에서 수정 없이 동작 | `python examples/01_falling_box_realtime.py --headless` |
| G3 | `forge3d.__version__ == "2.0.0"` | Python 확인 |
| G4 | 전체 테스트 PASS (cargo + pytest) | CI 확인 |
| G5 | 문서 사이트 빌드 성공 | `mkdocs build` |
| G6 | 벤치마크 리포트 `docs/benchmarks/v2_summary.md` 존재 | 파일 존재 확인 |
