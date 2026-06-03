# Phase 14 SPEC — Git · CI/CD · PyPI 배포 인프라

> Source of truth for P14. Only changes described here are permitted.

## 목표

"토이 프로젝트"를 실제 PyPI 패키지로 전환한다.  
사용자가 `pip install forge3d` 한 줄로 설치하고, PR마다 자동으로 테스트가 실행된다.

### 참조 라이브러리
- **Pymunk**: GitHub Actions CI + ReadTheDocs + PyPI Trusted Publisher
- **Panda3D**: makepanda 빌드 + 상세 CHANGELOG + 멀티-파이썬 CI 매트릭스

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `git init` + `.gitignore` 정비 + 초기 커밋 | 루트 |
| T2 | GitHub Actions **CI** 워크플로우 (push/PR) | `.github/workflows/ci.yml` |
| T3 | GitHub Actions **Release** 워크플로우 (tag → PyPI) | `.github/workflows/release.yml` |
| T4 | `pyproject.toml` 메타데이터 최종 정비 | `pyproject.toml` |
| T5 | 버전 `0.4.0`으로 올리기 + `CHANGELOG.md` 갱신 | `src/forge3d/__init__.py`, `CHANGELOG.md` |
| T6 | `python -m build` 로컬 빌드 검증 | — |
| T7 | TestPyPI 업로드 스모크 테스트 | — |
| T8 | `docs/PROGRESS.md` P14 완료 기록 | `docs/PROGRESS.md` |

---

## CI 워크플로우 설계 (`.github/workflows/ci.yml`)

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
        os: [ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --ignore=tests/test_p9_training.py -q
      - run: ruff check .
      - run: mypy src/
```

## Release 워크플로우 설계 (`.github/workflows/release.yml`)

```yaml
name: Release
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write   # Trusted Publisher (OIDC)
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://upload.pypi.org/legacy/  # 실 PyPI
```

---

## pyproject.toml 정비 사항

- `version` → `0.4.0`
- `authors` → 실제 이름·이메일
- `urls.Homepage` → 실제 GitHub repo URL
- `urls.Documentation` → 실제 ReadTheDocs URL
- classifiers: `Development Status :: 4 - Beta` 유지
- `[tool.hatch.build]` — `exclude` 패턴 (`.github/`, `docs/`, `tests/`, `apps/`, `validation/`)
- `[project.optional-dependencies]` 검토

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `git log --oneline` 에 초기 커밋 존재 | `git log` |
| G2 | `.github/workflows/ci.yml` 존재 & 문법 유효 | `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` |
| G3 | `python -m build` 성공 → `dist/` 에 `.whl` + `.tar.gz` 생성 | `ls dist/` |
| G4 | `pip install dist/forge3d-0.4.0-py3-none-any.whl` 성공 → `import forge3d` 동작 | 직접 실행 |
| G5 | TestPyPI 업로드 성공 (또는 dry-run OK) | `twine check dist/*` |
| G6 | `CHANGELOG.md` 에 `0.4.0` 항목 존재 | 확인 |
