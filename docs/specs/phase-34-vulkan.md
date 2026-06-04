# SPEC: Phase 34 — Vulkan / wgpu 백엔드 (선택)

> 파생: `docs/ROADMAP_v2.md` P34. 규칙: 루트 `CLAUDE.md`.  
> **이 Phase는 선택(Optional)이다.** P35 릴리즈의 전제 조건이 아니다.

---

## 1. 목표 (한 문장)

`wgpu-py` (WebGPU/Vulkan 추상 라이브러리) 기반 렌더러를 `Renderer` ABC 위에 구현하여 동일한 `SceneSnapshot`을 Vulkan 경로로 렌더링하고, 차세대 GPU 기능(compute shader, ray tracing 준비)의 기반을 마련한다.

---

## 2. 범위

### 포함

- **`WgpuRenderer(Renderer)` 클래스**: wgpu-py 스왑체인, 렌더 패스
- **WGSL 셰이더**: PBR 라이팅 (forward shading, G-Buffer 이후 고려)
- **SceneSnapshot 계약 유지**: 기존 OpenGL 렌더러와 동일한 입력/출력
- **헤드리스 오프스크린**: wgpu offscreen texture → NumPy 배열
- **Feature detection**: wgpu 가용 시 자동 선택, 불가 시 OpenGL 폴백

### 제외 (Out of scope)

- 하드웨어 레이 트레이싱 (RTX DXR/VKX) — 이 환경 미지원
- 멀티 GPU / SLI — 실험적
- Metal 백엔드 (macOS) — Linux 우선

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/render/wgpu/renderer.py` | `WgpuRenderer(Renderer)` |
| `src/forge3d/render/wgpu/pipeline.py` | wgpu 렌더 파이프라인 설정 |
| `src/forge3d/render/shaders/pbr.wgsl` | WGSL PBR 셰이더 |
| `tests/test_p34_wgpu.py` | wgpu 렌더러 smoke 테스트 |

### 핵심 인터페이스

```python
class WgpuRenderer(Renderer):
    def __init__(
        self,
        size: tuple[int, int] = (1280, 720),
        headless: bool = True,
    ) -> None: ...

    def render(self, snapshot: SceneSnapshot) -> np.ndarray:
        """(H, W, 4) uint8 RGBA"""

# 백엔드 자동 선택 (viewer.py)
# mode="realtime" → wgpu 가용이면 WgpuRenderer, 아니면 DeferredRenderer(GL)
```

### 의존성

```toml
"wgpu>=0.19"   # wgpu-py (optional extra)
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. wgpu 컨텍스트 + 스왑체인 (헤드리스)** — 완료 조건: offscreen wgpu texture 생성
- [ ] **T2. WGSL 기본 PBR 셰이더** — 완료 조건: 단색 구 렌더 RGBA 배열 반환
- [ ] **T3. SceneSnapshot → WgpuRenderer 렌더** — 완료 조건: 기존 골든 이미지와 SSIM ≥ 0.90
- [ ] **T4. Feature detection + 폴백** — 완료 조건: wgpu 없으면 GL 렌더러로 자동 전환
- [ ] **T5. 테스트** — 완료 조건: wgpu 가용 시 smoke 테스트, 불가 시 skip

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | wgpu 헤드리스 렌더 → RGBA 배열 반환 | `test_p34_wgpu::test_headless_render` |
| G2 | 동일 SceneSnapshot, GL vs wgpu SSIM ≥ 0.90 | `test_p34_wgpu::test_parity` |
| G3 | wgpu 없는 환경에서 GL 폴백 정상 동작 | `test_p34_wgpu::test_fallback` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
