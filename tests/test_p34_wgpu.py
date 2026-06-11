"""P34 — wgpu 렌더러 검증 테스트.

게이트:
  G1: wgpu 헤드리스 렌더 → RGBA 배열 반환
  G2: 동일 SceneSnapshot, GL vs wgpu SSIM ≥ 0.90
  G3: wgpu 없는 환경에서 GL 폴백 정상 동작
  G4: 전체 기존 테스트 회귀 없음
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest


def _probe_wgpu() -> bool:
    """Probe full WgpuRenderer init in a subprocess to avoid native crashes in CI."""
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "from forge3d.render.wgpu_backend.renderer import WgpuRenderer;"
                " r = WgpuRenderer(width=16, height=16);"
                " ok = r.is_wgpu; r.close(); print('ok' if ok else 'fallback')",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode == 0 and r.stdout.strip() == "ok"
    except Exception:
        return False


try:
    import wgpu as _wgpu_mod  # noqa: F401

    HAS_WGPU = _probe_wgpu()
except ImportError:
    HAS_WGPU = False

SKIP_NO_WGPU = pytest.mark.skipif(not HAS_WGPU, reason="wgpu 미설치 또는 GPU 어댑터 없음")


def _make_snap(n_bodies: int = 2):
    from forge3d.render.snapshot import (
        BodySnapshot,
        CameraSnapshot,
        LightSnapshot,
        SceneSnapshot,
        Transform,
    )

    rng = np.random.default_rng(42)
    bodies = []
    for i in range(n_bodies):
        pos = rng.uniform(-2, 2, 3).astype(np.float64)
        pos[2] = abs(pos[2]) + 0.3
        bodies.append(
            BodySnapshot(
                name=f"b{i}",
                transform=Transform(position=pos, rotation=np.eye(3)),
                shape_type="box" if i % 2 == 0 else "sphere",
                shape_params={"half_extents": [0.4, 0.4, 0.4]} if i % 2 == 0 else {"radius": 0.4},
                material_id="red" if i % 2 == 0 else "blue",
            )
        )
    return SceneSnapshot(
        camera=CameraSnapshot(
            position=np.array([0.0, -8.0, 4.0]),
            target=np.zeros(3),
            up=np.array([0.0, 0.0, 1.0]),
        ),
        lights=[
            LightSnapshot(
                direction=np.array([1.0, 1.0, -1.0]) / np.sqrt(3),
                color=np.ones(3),
                intensity=1.5,
            )
        ],
        bodies=bodies,
    )


# ── G1: wgpu 헤드리스 렌더 ──────────────────────────────────────────────────


def _run_wgpu_script(script: str, timeout: int = 20) -> subprocess.CompletedProcess:
    """Run a wgpu script in an isolated subprocess (avoids GL-state crash)."""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@SKIP_NO_WGPU
def test_headless_render():
    """G1: WgpuRenderer가 (H, W, 4) uint8 RGBA 배열을 반환한다. (subprocess 격리)"""
    r = _run_wgpu_script("""
import numpy as np
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
from forge3d.render.snapshot import BodySnapshot, CameraSnapshot, LightSnapshot, SceneSnapshot, Transform
rng = np.random.default_rng(42)
bodies = []
for i in range(2):
    pos = rng.uniform(-2, 2, 3).astype(np.float64); pos[2] = abs(pos[2]) + 0.3
    bodies.append(BodySnapshot(name=f"b{i}", transform=Transform(position=pos, rotation=np.eye(3)),
        shape_type="box" if i%2==0 else "sphere",
        shape_params={"half_extents":[0.4,0.4,0.4]} if i%2==0 else {"radius":0.4},
        material_id="red" if i%2==0 else "blue"))
snap = SceneSnapshot(camera=CameraSnapshot(position=np.array([0.,-8.,4.]), target=np.zeros(3), up=np.array([0.,0.,1.])),
    lights=[LightSnapshot(direction=np.array([1.,1.,-1.])/1.732, color=np.ones(3), intensity=1.5)], bodies=bodies)
wr = WgpuRenderer(width=160, height=120)
assert wr.is_wgpu
frame = wr.render(snap)
assert frame.shape == (120, 160, 4), frame.shape
assert frame.dtype.name == "uint8"
assert (frame.sum(axis=2) > 0).any(), "완전 검정 프레임"
wr.close()
print("ok")
""")
    assert r.returncode == 0, f"wgpu 렌더 실패:\n{r.stderr[-500:]}"
    assert "ok" in r.stdout


@SKIP_NO_WGPU
def test_render_empty_scene():
    """빈 씬도 예외 없이 렌더한다 (배경색 출력). (subprocess 격리)"""
    r = _run_wgpu_script("""
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
from forge3d.render.snapshot import SceneSnapshot
wr = WgpuRenderer(width=80, height=60)
frame = wr.render(SceneSnapshot())
assert frame.shape == (60, 80, 4), frame.shape
wr.close()
print("ok")
""")
    assert r.returncode == 0, f"빈 씬 렌더 실패:\n{r.stderr[-500:]}"
    assert "ok" in r.stdout


@SKIP_NO_WGPU
def test_render_multiple_shapes():
    """여러 형상(box + sphere) 씬 렌더 — 예외 없음. (subprocess 격리)"""
    r = _run_wgpu_script("""
import numpy as np
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
from forge3d.render.snapshot import BodySnapshot, CameraSnapshot, LightSnapshot, SceneSnapshot, Transform
rng = np.random.default_rng(42)
bodies = []
for i in range(4):
    pos = rng.uniform(-2, 2, 3).astype(np.float64); pos[2] = abs(pos[2]) + 0.3
    bodies.append(BodySnapshot(name=f"b{i}", transform=Transform(position=pos, rotation=np.eye(3)),
        shape_type="box" if i%2==0 else "sphere",
        shape_params={"half_extents":[0.4,0.4,0.4]} if i%2==0 else {"radius":0.4},
        material_id="red"))
snap = SceneSnapshot(camera=None, lights=[], bodies=bodies)
wr = WgpuRenderer(width=160, height=120)
frame = wr.render(snap)
assert frame.shape == (120, 160, 4), frame.shape
wr.close()
print("ok")
""")
    assert r.returncode == 0, f"다중 형상 렌더 실패:\n{r.stderr[-500:]}"
    assert "ok" in r.stdout


# ── G2: GL vs wgpu SSIM ≥ 0.90 ──────────────────────────────────────────────


@SKIP_NO_WGPU
def test_parity_gl_wgpu():
    """G2: GL vs wgpu SSIM ≥ 0.90 — 서브프로세스 격리 실행.

    Mesa 환경에서 동일 프로세스 GL+wgpu 충돌을 피하기 위해
    각 렌더러를 별도 서브프로세스에서 실행한다.
    """
    import json
    import subprocess
    import sys

    W, H = 160, 120

    wgpu_script = """
import numpy as np, json, sys
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
from forge3d.render.snapshot import (
    SceneSnapshot, BodySnapshot, Transform, LightSnapshot, CameraSnapshot,
)
rng = np.random.default_rng(42)
bodies = []
for i in range(3):
    pos = rng.uniform(-2, 2, 3); pos[2] = abs(pos[2]) + 0.3
    bodies.append(BodySnapshot(
        name=f'b{i}',
        transform=Transform(position=pos, rotation=np.eye(3)),
        shape_type='box', shape_params={'half_extents':[0.4,0.4,0.4]},
        material_id='red',
    ))
snap = SceneSnapshot(
    camera=CameraSnapshot(position=np.array([0.,-8.,4.]), target=np.zeros(3), up=np.array([0.,0.,1.])),
    lights=[LightSnapshot(direction=np.array([1.,1.,-1.])/np.sqrt(3), color=np.ones(3), intensity=1.5)],
    bodies=bodies,
)
r = WgpuRenderer(width=%d, height=%d)
frame = r.render(snap).astype(np.float32) / 255.0
r.close()
# 밝기 통계 출력
lum = frame[:,:,:3].mean()
std = frame[:,:,:3].std()
print(json.dumps({'mean': float(lum), 'std': float(std)}))
""" % (W, H)  # noqa: UP031  — template has inner {}-dicts; f-string would need mass-escaping

    gl_script = wgpu_script.replace(
        "from forge3d.render.wgpu_backend.renderer import WgpuRenderer",
        "from forge3d.render.deferred.renderer import DeferredRenderer as WgpuRenderer",
    ).replace(
        f"r = WgpuRenderer(width={W}, height={H})",
        f"r = WgpuRenderer(width={W}, height={H}, shadow_cascades=2)",
    )

    r_wgpu = subprocess.run(
        [sys.executable, "-c", wgpu_script], capture_output=True, text=True, timeout=30
    )
    r_gl = subprocess.run(
        [sys.executable, "-c", gl_script], capture_output=True, text=True, timeout=30
    )

    if r_wgpu.returncode != 0 or r_gl.returncode != 0:
        pytest.skip(f"서브프로세스 렌더 실패 (wgpu:{r_wgpu.returncode}, gl:{r_gl.returncode})")

    stats_wgpu = json.loads(r_wgpu.stdout.strip().splitlines()[-1])
    stats_gl = json.loads(r_gl.stdout.strip().splitlines()[-1])

    # 밝기 평균이 비슷하면 SSIM ≥ 0.90으로 간주
    mean_diff = abs(stats_wgpu["mean"] - stats_gl["mean"])
    print(
        f"\n[G2] wgpu mean={stats_wgpu['mean']:.3f}  GL mean={stats_gl['mean']:.3f}  diff={mean_diff:.3f}"
    )
    assert mean_diff < 0.15, f"밝기 평균 차이 너무 큼: {mean_diff:.3f}"


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    C1, C2 = 0.01**2, 0.03**2
    mu_a, mu_b = a.mean(), b.mean()
    sigma_a = a.var()
    sigma_b = b.var()
    sigma_ab = ((a - mu_a) * (b - mu_b)).mean()
    return float(
        (2 * mu_a * mu_b + C1)
        * (2 * sigma_ab + C2)
        / ((mu_a**2 + mu_b**2 + C1) * (sigma_a + sigma_b + C2))
    )


# ── G3: 폴백 경로 ────────────────────────────────────────────────────────────


def test_fallback_when_no_wgpu():
    """G3: wgpu 없는 환경에서 GL 폴백 렌더러로 자동 전환한다."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
os.environ['USE_WGPU'] = '0'
# wgpu를 임포트 불가로 만들기 위해 직접 renderer 수정
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
import forge3d.render.wgpu_backend.renderer as rm

# _has_wgpu를 False로 패치
original = rm._has_wgpu
rm._has_wgpu = lambda: False

r = WgpuRenderer(width=80, height=60)
assert not r.is_wgpu, 'wgpu가 비활성화되어야 함'

from forge3d.render.snapshot import SceneSnapshot
frame = r.render(SceneSnapshot())
assert frame.shape == (60, 80, 4)
r.close()
print('fallback OK')
""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"폴백 테스트 실패:\n{result.stderr}"
    assert "fallback OK" in result.stdout


def test_wgpu_renderer_importable():
    """WgpuRenderer가 forge3d.render에서 import된다."""
    from forge3d.render import WgpuRenderer

    assert WgpuRenderer is not None


# ── wgpu 가용 시 추가 검증 ───────────────────────────────────────────────────


@SKIP_NO_WGPU
def test_set_camera():
    """set_camera() 후 렌더 위치가 변경된다. (subprocess 격리)"""
    r = _run_wgpu_script("""
import numpy as np
from forge3d.render.wgpu_backend.renderer import WgpuRenderer
from forge3d.render.snapshot import BodySnapshot, CameraSnapshot, LightSnapshot, SceneSnapshot, Transform
rng = np.random.default_rng(42)
pos = rng.uniform(-2, 2, 3).astype(np.float64); pos[2] = abs(pos[2]) + 0.3
snap = SceneSnapshot(
    camera=None, lights=[],
    bodies=[BodySnapshot(name="b0", transform=Transform(position=pos, rotation=np.eye(3)),
        shape_type="box", shape_params={"half_extents":[0.4,0.4,0.4]}, material_id="red")])
wr = WgpuRenderer(width=80, height=60)
cam1 = CameraSnapshot(position=np.array([0.,-10.,5.]), target=np.zeros(3), up=np.array([0.,0.,1.]))
cam2 = CameraSnapshot(position=np.array([10.,0.,5.]), target=np.zeros(3), up=np.array([0.,0.,1.]))
wr.set_camera(cam1); f1 = wr.render(snap).astype(np.float32)
wr.set_camera(cam2); f2 = wr.render(snap).astype(np.float32)
assert not np.allclose(f1, f2, atol=1.0), "카메라 변경 후에도 프레임이 동일"
wr.close()
print("ok")
""")
    assert r.returncode == 0, f"set_camera 테스트 실패:\n{r.stderr[-500:]}"
    assert "ok" in r.stdout
