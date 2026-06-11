# Contributing to forge3d

Thank you for your interest in contributing!

## Quick start

```bash
git clone https://github.com/iruki-dev/forge3d
cd forge3d
pip install -e ".[dev]"
```

!!! note
    PyPI 배포명은 `pyforge3d`이지만 코드에서는 `import forge3d`를 사용합니다.

## Workflow

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Write your changes and corresponding tests
3. Make sure the checks below pass
4. Open a PR — one PR per logical change

## Checks (must all pass)

```bash
ruff check . && ruff format --check .   # lint + format
mypy src/                               # type checking
pytest tests/ -q                        # test suite
```

## Rules

### Physics code

- Every new formula needs a unit test that checks against an analytical solution,
  a conservation law (energy / momentum), or a PyBullet/MuJoCo baseline (`validation/` directory).
- No in-place mutation of arrays. Use `dataclasses.replace(body, vel=new_vel)`.
- Must run correctly under both `ENGINE_BACKEND=numpy` and `ENGINE_BACKEND=jax`.

### Renderer

- Physics core (`math/`, `dynamics/`, `collision/`, `contact/`, `model/`, `sim/`)
  must **never** import renderer code.
- The only allowed bridge is `SceneSnapshot` (pure data).

### Public API

- New public concepts require an entry in `__all__` in `src/forge3d/__init__.py`.
- New public concepts need a usage example in `examples/` (≤ 15 lines).

### Forbidden

- External physics engines in `src/forge3d/` (MuJoCo, PyBullet, Bullet, etc.).
  They are allowed only in `validation/` for baseline comparison.
- GPU/CUDA dependencies for physics or learning code.

## Code style

- [ruff](https://docs.astral.sh/ruff/) for lint and formatting (line length 100).
- Type annotations on all public functions.
- Comments only when the *why* is non-obvious.
- No docstrings for trivial getters / setters.

## Commit style

```
feat(collision): add sweep-and-prune broad-phase
fix(contact): clamp Baumgarte correction to avoid tunnelling
docs(readme): add App-style game loop example
test(physics): add conservation test for capsule-capsule
```

## Questions?

Open an issue or start a Discussion on GitHub.