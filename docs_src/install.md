# Installation

## Requirements

- Python **3.12** or newer
- NumPy ≥ 1.26, SciPy ≥ 1.12, JAX (CPU wheel)

forge3d runs entirely on **CPU** — no CUDA, no GPU required for physics or training.

---

## pip (recommended)

```bash
# Physics core only (no rendering)
pip install pyforge3d

# + Real-time OpenGL and HQ ray-tracer
pip install "pyforge3d[render]"

# + Gymnasium + Stable-Baselines3 RL
pip install "pyforge3d[rl]"

# Everything (for development / research)
pip install "pyforge3d[all]"
```

> **Note:** The PyPI distribution is named `pyforge3d`, but the import name remains `forge3d`:
> ```python
> import forge3d as f3d   # same as always
> ```

---

## Development install

```bash
git clone https://github.com/iruki-dev/forge3d.git
cd forge3d
pip install -e ".[dev]"
```

---

## Headless / server environments

If you run forge3d on a headless server (no display), the realtime renderer uses **Xvfb + Mesa llvmpipe** (software OpenGL):

```bash
sudo apt-get install xvfb libgl1-mesa-dri
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &
python my_script.py
```

The HQ ray-tracer has no display dependency — it outputs PNG/MP4 directly.

---

## Docker

```bash
docker compose run --rm dev python examples/01_falling_box_realtime.py
```

See `.devcontainer/docker-compose.yml` for the full CPU-only service definition.

---

## Verify

```python
import forge3d
print(forge3d.__version__)  # → 0.4.0
```
