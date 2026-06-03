# Phase 24 SPEC — v1.0.0 제품 릴리즈

> Source of truth for P24. Only changes described here are permitted.

## 목표

P14~P23 완료 후, 모든 검증을 통과하고 PyPI에 **v1.0.0**을 공식 배포한다.

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | API 안정성 선언 — `__version__ = "1.0.0"`, `STABLE_API` 목록 문서화 | `src/forge3d/__init__.py`, `docs_src/api_stability.md` |
| T2 | 최종 벤치마크 실행 및 결과 README에 업데이트 | `README.md` |
| T3 | `CHANGELOG.md` v1.0.0 항목 작성 (P14~P23 변경 정리) | `CHANGELOG.md` |
| T4 | 전체 테스트 스위트 통과 확인 (slow 포함) | — |
| T5 | `pyproject.toml` classifier `Development Status :: 5 - Production/Stable` | `pyproject.toml` |
| T6 | `python -m build` → `dist/forge3d-1.0.0-py3-none-any.whl` | 로컬 빌드 |
| T7 | GitHub tag `v1.0.0` 생성 → Actions release 워크플로우 트리거 | git tag |
| T8 | PyPI 배포 확인 → `pip install forge3d==1.0.0` 검증 | TestPyPI 또는 실 PyPI |
| T9 | `docs/PROGRESS.md` 최종 업데이트 | `docs/PROGRESS.md` |

---

## API 안정성 선언

v1.0.0에서 안정(Breaking change 없음)으로 선언하는 공개 API:

```
forge3d.World        — 모든 add_* / step / snapshot / weld / teleport
forge3d.Body         — position / orientation / velocity / apply_force / apply_impulse
forge3d.Shape        — box / sphere / capsule / convex_mesh
forge3d.Material     — color / roughness / metallic / texture_path
forge3d.App          — on_start / on_update / on_render / run
forge3d.Viewer       — draw / is_open / input / set_camera
forge3d.Recorder     — run / run_policy
forge3d.Input        — key_held / key_pressed / mouse_pos / scroll_delta
forge3d.OrbitCamera  — rotate / zoom / pan / to_snapshot
forge3d.Joint        — (P16에서 추가된 모든 조인트 종류)
```

실험적(v2.0에서 변경 가능):
```
forge3d.sim.jax_batch   — JAX 배치 API (성능 실험적)
forge3d.render.hq       — HQ 레이트레이서 내부 API
```

---

## 릴리즈 체크리스트

- [ ] `pytest tests/ -q` — 0 failures
- [ ] `ruff check . && ruff format --check .` — 0 errors
- [ ] `mypy src/` — 0 errors
- [ ] `mkdocs build` — 성공
- [ ] `python -m build` — `dist/` 생성
- [ ] `twine check dist/*` — PASSED
- [ ] `pip install dist/forge3d-1.0.0-py3-none-any.whl` → `import forge3d; forge3d.__version__ == "1.0.0"` ✅
- [ ] README 예제 코드가 그대로 동작
- [ ] CHANGELOG.md v1.0.0 항목 완성
- [ ] GitHub release 태그 `v1.0.0`

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `pip install forge3d==1.0.0` 성공 (TestPyPI 또는 실 PyPI) | pip 설치 확인 |
| G2 | 설치 후 퀵스타트 예제 동작 | 실행 확인 |
| G3 | `forge3d.__version__ == "1.0.0"` | Python 확인 |
| G4 | 전체 테스트 통과 | — |
| G5 | 문서 사이트 빌드 성공 | `mkdocs build` |
