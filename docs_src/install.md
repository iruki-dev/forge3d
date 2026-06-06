# Installation

## Requirements

- Python **3.12** or newer
- NumPy ≥ 1.26, SciPy ≥ 1.12, JAX[cpu] ≥ 0.4.25

forge3d runs entirely on **CPU** — no CUDA, no GPU required for physics or training.

---

## pip (recommended)

```bash
# Physics core only (no rendering)
pip install pyforge3d

# + Realtime OpenGL viewer, HQ ray-tracer, terrain rendering, HUD text
pip install "pyforge3d[render]"

# + Gymnasium + Stable-Baselines3 RL environments
pip install "pyforge3d[rl]"

# Everything
pip install "pyforge3d[all]"
```

!!! note "Package name vs import name"
    The PyPI distribution is named **`pyforge3d`**, but the import is always:
    ```python
    import forge3d as f3d
    ```

---

## Optional extras

| Extra | Packages installed | Needed for |
|-------|-------------------|------------|
| `render` | moderngl, glfw, Pillow, imageio, imageio-ffmpeg | `Viewer`, `Recorder`, terrain rendering, HUD text |
| `rl` | gymnasium, stable-baselines3, optax | Gymnasium environments, SB3 training |
| `dev` | pytest, ruff, mypy + render deps | Development and testing |
| `docs` | mkdocs-material, mkdocstrings | Building this documentation |
| `all` | render + rl + dev | Everything except docs |

---

## Headless / server environments

The realtime renderer uses **Xvfb + Mesa llvmpipe** (software OpenGL) on headless servers.
forge3d detects the environment and starts Xvfb automatically if needed.

```bash
# Install system deps (Ubuntu / Debian)
sudo apt-get install xvfb libgl1-mesa-glx libglib2.0-0

# Or run with an explicit virtual display
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &
python my_script.py
```

The HQ ray-tracer has no display dependency — it writes PNG/MP4 directly.

---

## Development install

```bash
git clone https://github.com/iruki-dev/forge3d.git
cd forge3d
pip install -e ".[dev]"

# Run test suite
pytest tests/ -q

# Lint + type-check
ruff check src/ && mypy src/
```

## Optional Rust core

The Rust extension (`forge3d._core`) accelerates the PGS contact solver, GJK/EPA,
and BVH broadphase. It is **optional** — forge3d falls back to pure Python automatically.

```bash
pip install maturin
maturin develop           # development build
cargo test --workspace    # run Rust tests

# Check whether the extension loaded
python -c "from forge3d.backend import USE_RUST_CORE; print('Rust core:', USE_RUST_CORE)"
```

---

## Docker

```bash
docker compose run --rm dev python -c "import forge3d; print(forge3d.__version__)"
```

---

## Verify

```python
import forge3d
print(forge3d.__version__)   # → 2.1.0
```
