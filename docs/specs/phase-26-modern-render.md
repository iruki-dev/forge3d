# SPEC: Phase 26 — 모던 렌더링 파이프라인 (지연 PBR + CSM + SSAO + HDR)

> Claude가 이 작업을 진행하는 **단일 기준**이다. 자기완결적으로 작성한다.  
> 파생: `docs/ROADMAP_v2.md` P26. 규칙: 루트 `CLAUDE.md`. 절차: `docs/WORKFLOW.md`.

---

## 1. 목표 (한 문장)

`RealtimeRenderer`를 OpenGL 4.3 기반 **지연 렌더링(Deferred Rendering)** 파이프라인으로 교체하여 PBR 머티리얼, 4단계 CSM(Cascaded Shadow Maps), SSAO, HDR + ACES 톤맵, 블룸을 제공하고, 동일한 `SceneSnapshot` 계약을 유지한다.

---

## 2. 범위

### 포함

- **지연 렌더링 G-Buffer 패스** (위치·법선·알베도·Roughness/Metallic)
- **PBR 조명 패스** (GGX-Cook-Torrance, 포인트·방향·스팟 광원)
- **Cascaded Shadow Maps** (CSM 4단계, PCF 9-탭 소프트 그림자)
- **SSAO** (반구 64샘플, blur 패스)
- **HDR 프레임버퍼 + ACES 톤맵 + 블룸 (Kawase 다운샘플)**
- **인스턴스 렌더링** (동일 메시 N개 → 단일 드로우콜)
- **RenderPass 추상** (`render/passes/base.py`)
- **셰이더 파일 분리** (`render/shaders/*.glsl`)
- **기존 `HQRenderer` 계약 유지** (SceneSnapshot → Frame)
- **골든 이미지 회귀 테스트**

### 제외 (Out of scope)

- Vulkan/wgpu 백엔드 — P34 별도 Phase
- 레이트레이싱 — HQ 레이트레이서(P6)가 담당, 건드리지 않음
- 스킨드 메시 / 골격 렌더링 — P29 애니메이션 Phase
- 투명체(순서 독립 투명도 OIT) — v2.1 이후
- 동적 큐브맵 반사 — v2.1 이후

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/render/passes/base.py` | `RenderPass` ABC |
| `src/forge3d/render/passes/gbuffer_pass.py` | G-Buffer 기록 패스 |
| `src/forge3d/render/passes/lighting_pass.py` | PBR 조명 패스 |
| `src/forge3d/render/passes/shadow_pass.py` | CSM 섀도맵 패스 |
| `src/forge3d/render/passes/ssao_pass.py` | SSAO + blur 패스 |
| `src/forge3d/render/passes/postprocess_pass.py` | HDR 톤맵 + 블룸 패스 |
| `src/forge3d/render/deferred/renderer.py` | `DeferredRenderer(Renderer)` |
| `src/forge3d/render/shaders/gbuffer.vert` | G-Buffer 정점 셰이더 |
| `src/forge3d/render/shaders/gbuffer.frag` | G-Buffer 프래그먼트 셰이더 |
| `src/forge3d/render/shaders/lighting.vert` | 풀스크린 쿼드 |
| `src/forge3d/render/shaders/lighting.frag` | PBR 조명 계산 |
| `src/forge3d/render/shaders/shadow.vert` | CSM 깊이 패스 |
| `src/forge3d/render/shaders/ssao.frag` | SSAO 계산 |
| `src/forge3d/render/shaders/ssao_blur.frag` | SSAO blur |
| `src/forge3d/render/shaders/bloom_down.frag` | Kawase 다운샘플 |
| `src/forge3d/render/shaders/bloom_up.frag` | Kawase 업샘플 |
| `src/forge3d/render/shaders/tonemap.frag` | ACES + 감마 보정 |
| `tests/test_p26_deferred_render.py` | 회귀 + 골든 이미지 테스트 |
| `docs/benchmarks/p26.md` | 렌더 FPS 벤치마크 기록 |

### 수정

| 경로 | 변경 |
|------|------|
| `src/forge3d/render/realtime/renderer.py` | `DeferredRenderer`로 위임 또는 교체 |
| `src/forge3d/render/base.py` | `Renderer.mode` = `"deferred"` 추가 |
| `src/forge3d/render/__init__.py` | `DeferredRenderer` 공개 |
| `src/forge3d/viewer.py` | `mode="realtime"` → 내부적으로 `DeferredRenderer` 사용 |

### 핵심 인터페이스

```python
# RenderPass ABC
class RenderPass(ABC):
    def setup(self, ctx: moderngl.Context, size: tuple[int, int]) -> None: ...
    def render(self, ctx: moderngl.Context, scene: SceneSnapshot) -> None: ...
    def resize(self, size: tuple[int, int]) -> None: ...

# DeferredRenderer
class DeferredRenderer(Renderer):
    def __init__(
        self,
        ctx: moderngl.Context,
        size: tuple[int, int] = (1280, 720),
        shadow_cascades: int = 4,
        ssao_samples: int = 64,
        bloom_threshold: float = 1.0,
    ) -> None: ...

    def render(self, snapshot: SceneSnapshot) -> np.ndarray:
        """(H, W, 4) uint8 RGBA 프레임 반환"""

# 머티리얼 확장 (기존 Material에 추가)
@dataclass
class Material:
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    roughness: float = 0.5
    metallic: float = 0.0          # v2 신규
    emissive: tuple[float, float, float] = (0.0, 0.0, 0.0)  # v2 신규
    texture_path: str | None = None
    normal_map_path: str | None = None  # v2 신규
```

### G-Buffer 레이아웃

| 어태치먼트 | 포맷 | 내용 |
|-----------|------|------|
| `gPosition` | `RGB32F` | 월드 공간 위치 |
| `gNormal` | `RGB16F` | 월드 공간 법선 (정규화) |
| `gAlbedoRough` | `RGBA8` | RGB=알베도, A=roughness |
| `gEmissiveMetal` | `RGBA8` | RGB=emissive, A=metallic |
| `gDepth` | `DEPTH24` | 깊이 버퍼 |

### CSM 분할 전략

```
cascade[0]: near ~ 0.05 * far   ← 가장 세밀
cascade[1]: 0.05 * far ~ 0.15 * far
cascade[2]: 0.15 * far ~ 0.40 * far
cascade[3]: 0.40 * far ~ far    ← 가장 거침
```

각 cascade마다 2048×2048 섀도맵, 라이트 시점 orthogonal projection.

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. RenderPass 추상 + 파이프라인 골격** — 완료 조건: `DeferredRenderer` import, `render()` 빈 구현
  - `render/passes/base.py`: `RenderPass` ABC
  - `render/deferred/renderer.py`: 패스 목록 초기화, `render()` 순차 호출 루프

- [ ] **T2. G-Buffer 패스** — 완료 조건: moderngl FBO에 4채널 어태치먼트 기록, 텍스처 샘플링 확인
  - `gbuffer.vert`: MVP 변환, 월드 법선 출력
  - `gbuffer.frag`: 머티리얼 데이터 → G-Buffer 어태치먼트 기록
  - `gbuffer_pass.py`: FBO 생성, `setup()` + `render()` 구현

- [ ] **T3. CSM 섀도맵 패스** — 완료 조건: 4 cascade 섀도맵 텍스처 배열 생성, 그림자 있음/없음 시각 구분
  - `shadow.vert`: 라이트 공간 변환
  - `shadow_pass.py`: cascade 분할, 4회 렌더, 텍스처 배열 바인딩

- [ ] **T4. PBR 조명 패스** — 완료 조건: 구/박스 물체에서 diffuse+specular 분리, 금속·비금속 차이 시각 구분
  - `lighting.frag`: G-Buffer 샘플링, GGX-Cook-Torrance BRDF, Fresnel(Schlick), CSM 섀도 조회
  - 포인트 광원(감쇠), 방향광 지원

- [ ] **T5. SSAO 패스** — 완료 조건: AO 텍스처가 오목 면에서 어두움, 평면에서 1.0
  - `ssao.frag`: 반구 샘플 64개, 깊이 비교, blur 패스
  - `ssao_pass.py`: 랜덤 커널 SSBO 업로드

- [ ] **T6. HDR + 블룸 + 톤맵 패스** — 완료 조건: 밝은 광원 주변 블룸 헤일로, ACES 컬러 응답 확인
  - `bloom_down/up.frag`: Kawase 다운/업샘플 4단계
  - `tonemap.frag`: ACES Filmic + 감마(sRGB 2.2) 변환

- [ ] **T7. 인스턴스 렌더링** — 완료 조건: 동일 메시 500개를 단일 드로우콜, FPS 저하 없음
  - G-Buffer 패스에 `glDrawElementsInstanced` 경로 추가
  - 인스턴스 모델 행렬을 VBO 어트리뷰트로 업로드

- [ ] **T8. 골든 이미지 회귀 테스트** — 완료 조건: SSIM ≥ 0.98, 기준 이미지 `tests/golden/` 저장
  - 표준 씬 (구 3개 + 박스 + 방향광) → RGBA 렌더 → SSIM 비교
  - `UPDATE_GOLDEN=1 pytest` 시 기준 이미지 갱신

- [ ] **T9. FPS 벤치마크 기록** — 완료 조건: `docs/benchmarks/p26.md` 에 결과 기재
  - 씬 복잡도별(10/50/200 오브젝트) FPS, 1280×720 Xvfb 기준

---

## 5. 엣지 케이스 / 제약

- **OpenGL 4.3 필수**: 컴퓨트 셰이더·SSBO·텍스처 배열이 4.3부터. `moderngl` 컨텍스트 생성 시 `require_version=(4, 3)` 명시. 구형 환경 미지원은 에러로 명확히 알림.
- **헤드리스**: Xvfb + Mesa llvmpipe가 GL 4.3을 지원하는지 확인 필요 (llvmpipe는 4.5까지 소프트 지원). 테스트에서 버전 감지 후 skip.
- **SceneSnapshot 불변**: 물리 코어는 렌더러를 import하지 않는다. 신규 `metallic`/`emissive` 필드는 `SceneSnapshot.materials` 딕셔너리 확장으로 추가.
- **HQRenderer 영향 없음**: HQ 레이트레이서는 소프트웨어 경로. G-Buffer 패스와 무관. 기존 테스트 통과 필수.
- **Material 하위 호환**: 기존 `Material(color=..., roughness=...)` 호출 그대로 동작. `metallic=0.0` 기본값.

---

## 6. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | G-Buffer 4채널 어태치먼트 정상 기록 | `tests/test_p26_deferred_render.py::test_gbuffer_outputs` |
| G2 | CSM 4 cascade 섀도맵 텍스처 생성 | `tests/test_p26_deferred_render.py::test_shadow_maps` |
| G3 | 동일 SceneSnapshot → 지연 렌더 vs HQ 렌더 둘 다 PASS | `tests/test_p26_deferred_render.py::test_snapshot_contract` |
| G4 | SSIM ≥ 0.98 (골든 이미지 비교) | `tests/test_p26_deferred_render.py::test_golden_image` |
| G5 | 200 오브젝트 씬에서 ≥ 30 FPS (Xvfb) | `docs/benchmarks/p26.md` 기록 |
| G6 | 기존 테스트 회귀 없음 (`pytest tests/ -q`) | 전체 스위트 PASS |
| G7 | `examples/01_falling_box_realtime.py` 수정 없이 동작 | v1 API 호환 확인 |

---

## 7. 완료 후 리뷰

- GLSL 셰이더가 물리 코어를 import하지 않음 확인.
- `SceneSnapshot` 필드 확장이 기존 HQRenderer를 깨지 않음 확인.
- P27(ECS) 착수 전 G1~G7 전부 통과 필수.
