# 설치

## 요구 사항

- Python **3.12** 이상
- NumPy ≥ 1.26, SciPy ≥ 1.12, JAX[cpu] ≥ 0.4.25

forge3d는 **CPU 전용**으로 완전히 동작합니다 — 물리 연산이나 학습에 CUDA나 GPU가 필요하지 않습니다.

---

## pip (권장)

```bash
# 물리 코어만 (렌더링 없음)
pip install pyforge3d

# + 실시간 OpenGL 뷰어, HQ 레이트레이서, 지형 렌더링, HUD 텍스트
pip install "pyforge3d[render]"

# + Gymnasium + Stable-Baselines3 RL 환경
pip install "pyforge3d[rl]"

# 전체
pip install "pyforge3d[all]"
```

!!! note "패키지명 vs 임포트명"
    PyPI 배포명은 **`pyforge3d`**이지만, 코드에서는 항상 다음처럼 임포트합니다:
    ```python
    import forge3d as f3d
    ```

---

## 선택적 extras

| Extra | 설치 패키지 | 필요한 경우 |
|-------|------------|------------|
| `render` | moderngl, glfw, Pillow, imageio, imageio-ffmpeg | `Viewer`, `Recorder`, 지형 렌더링, HUD 텍스트 |
| `rl` | gymnasium, stable-baselines3, optax | Gymnasium 환경, SB3 학습 |
| `dev` | pytest, ruff, mypy + render 의존성 | 개발 및 테스트 |
| `docs` | mkdocs-material, mkdocstrings | 이 문서 빌드 |
| `all` | render + rl + dev | docs 제외 전체 |

---

## 헤드리스 / 서버 환경

실시간 렌더러는 헤드리스 서버에서 **Xvfb + Mesa llvmpipe** (소프트웨어 OpenGL)를 사용합니다.
forge3d는 환경을 자동으로 감지하여 필요 시 Xvfb를 자동으로 시작합니다.

```bash
# 시스템 의존성 설치 (Ubuntu / Debian)
sudo apt-get install xvfb libgl1-mesa-glx libglib2.0-0

# 또는 가상 디스플레이를 명시적으로 지정
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &
python my_script.py
```

HQ 레이트레이서는 디스플레이 의존성이 없으며 PNG/MP4를 직접 저장합니다.

---

## 개발용 설치

```bash
git clone https://github.com/iruki-dev/forge3d.git
cd forge3d
pip install -e ".[dev]"

# 테스트 실행
pytest tests/ -q

# 린트 + 타입 체크
ruff check src/ && mypy src/
```

## 선택적 Rust 코어

Rust 확장 (`forge3d._core`)은 PGS 접촉 솔버, GJK/EPA, BVH 광역 단계를 가속합니다.
**선택 사항**이며 — forge3d는 순수 Python으로 자동 폴백합니다.

```bash
pip install maturin
maturin develop           # 개발 빌드
cargo test --workspace    # Rust 테스트 실행

# 확장 로드 여부 확인
python -c "from forge3d.backend import USE_RUST_CORE; print('Rust 코어:', USE_RUST_CORE)"
```

---

## Docker

```bash
docker compose run --rm dev python -c "import forge3d; print(forge3d.__version__)"
```

---

## 확인

```python
import forge3d
print(forge3d.__version__)   # → 2.1.0
```
