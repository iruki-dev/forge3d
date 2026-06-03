# Phase 15 SPEC — MkDocs 문서 사이트

> Source of truth for P15. Only changes described here are permitted.

## 목표

`pip install forge3d` 설치 후 사용자가 처음 방문할 **공식 문서 사이트**를 구축한다.  
Pymunk·Panda3D처럼 ReadTheDocs 또는 GitHub Pages에서 자동 배포된다.

### 참조
- **Pymunk**: MkDocs + Material 테마, mkdocstrings, ReadTheDocs
- **Panda3D**: Sphinx + autodoc, 예제 중심
- **Godot**: 언어별 탭, 인터랙티브 예제

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | MkDocs + Material 테마 설치 + `mkdocs.yml` | `mkdocs.yml` |
| T2 | `mkdocstrings[python]` 연동 (자동 API 레퍼런스) | `mkdocs.yml`, `docs_src/` |
| T3 | 공개 API 전체 docstring 작성 (`World`, `Body`, `App`, `Viewer`, `Recorder`, `Input`, `Camera`) | `src/forge3d/*.py` |
| T4 | 튜토리얼 페이지 4종 작성 | `docs_src/tutorials/` |
| T5 | 아키텍처 개요 페이지 | `docs_src/architecture.md` |
| T6 | ReadTheDocs 설정 파일 | `.readthedocs.yaml` |
| T7 | GitHub Actions 문서 빌드 워크플로우 | `.github/workflows/docs.yml` |
| T8 | `docs/PROGRESS.md` P15 완료 기록 | `docs/PROGRESS.md` |

---

## 문서 구조

```
docs_src/
├── index.md                # 홈 (한눈에 보기)
├── quickstart.md           # 15줄 예제 3종
├── tutorials/
│   ├── 01_physics.md       # 물리 시뮬레이션 튜토리얼
│   ├── 02_rendering.md     # 실시간/HQ 렌더링
│   ├── 03_robot.md         # 로봇 팔 FK/IK
│   └── 04_rl.md            # 강화학습 환경
├── architecture.md         # 아키텍처 + SceneSnapshot 계약
├── api/
│   ├── world.md            # World API (mkdocstrings)
│   ├── body.md             # Body API
│   ├── rendering.md        # Viewer, Recorder
│   ├── input.md            # Input, Key
│   ├── camera.md           # OrbitCamera, FollowCamera
│   ├── shapes.md           # Shape, Material
│   ├── robot.md            # forge3d.robot
│   └── backends.md         # NumPy ↔ JAX 스위치
├── contributing.md         # CONTRIBUTING.md 미러
└── changelog.md            # CHANGELOG.md 미러
```

---

## mkdocs.yml 핵심 설정

```yaml
site_name: forge3d
site_url: https://forge3d.readthedocs.io
theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
  features:
    - navigation.tabs
    - content.code.copy
    - search.suggest
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true
            show_root_heading: true
markdown_extensions:
  - admonition
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
```

---

## docstring 스타일 (Google style)

```python
def add_box(
    self,
    size: tuple[float, float, float] = (1.0, 1.0, 1.0),
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    mass: float = 1.0,
) -> Body:
    """Add a dynamic box-shaped rigid body to the world.

    Args:
        size: Half-extents (width, depth, height) in metres.
        position: Initial centre position (x, y, z) in world frame.
        mass: Mass in kilograms. Must be positive.

    Returns:
        A :class:`Body` handle that tracks the body's state.

    Raises:
        ValueError: If ``mass`` ≤ 0 or any ``size`` component ≤ 0.

    Example::

        world = forge3d.World()
        box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    """
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `mkdocs build` 성공 → `site/` 생성 | `ls site/index.html` |
| G2 | API 레퍼런스 페이지 자동 생성 (`World`, `Body` 최소 2개) | `grep "add_box" site/api/world/index.html` |
| G3 | 튜토리얼 4종 모두 존재 | `ls docs_src/tutorials/` |
| G4 | `mkdocs serve` 로컬 서버 기동 후 홈 페이지 200 OK | 브라우저 확인 |
| G5 | `.readthedocs.yaml` 유효 | 파일 존재 확인 |
| G6 | GitHub Actions `docs.yml` 존재 | 파일 존재 확인 |
