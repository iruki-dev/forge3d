# Phase 6 — 고품질 레이트레이서(MVP) + Recorder HQ

> Source of truth: `docs/ROADMAP.md §9 P6`  
> 이전 게이트: P5 ✅ (충돌 + 연성 접촉)

---

## 목표

순수 Python 소프트웨어 레이트레이서를 직접 구현하고, `Recorder(mode='hq')`를 완성한다.  
결과물: `bounce.mp4` — 공이 튀기는 고품질 렌더링 영상.  
외부 렌더러(Open3D, Blender API 등) 사용 금지. NumPy 벡터화로 직접 구현.

---

## 범위

### 파일 목록

| 파일 | 역할 |
|------|------|
| `src/forge3d/render/hq/scene.py` | `SceneSnapshot` → `HQScene` 변환 |
| `src/forge3d/render/hq/raytracer.py` | 핵심 레이 트레이싱: 교차, 셰이딩, AA |
| `src/forge3d/render/hq/renderer.py` | `HQRenderer(Renderer)` 클래스 |
| `src/forge3d/recorder.py` | `mode='hq'` 활성화 |
| `examples/02_bounce_hq_video.py` | 게이트 예제: bounce.mp4 산출 |
| `tests/test_hq_renderer.py` | 단위 + 스모크 테스트 |

---

## 설계 결정

### 레이 트레이서 설계

**벡터화 전략**: 전체 픽셀 × 샘플 수의 광선을 NumPy 배열 `(N, 3)`으로 묶어 한 번에 처리.  
프리미티브 루프(`K`개)만 직렬 — 각 패스에서 N개 광선을 동시 처리.

**지원 프리미티브(MVP)**:
- `sphere`: 이차 방정식 교차 (정확해)
- `box (OBB)`: Slab 방법 + 쿼터니언→R 로컬 좌표 변환

**셰이딩 모델**:
- Ambient(0.05) + Diffuse + Blinn-Phong Specular
- Hard shadow (그림자 광선)
- 재귀 반사/굴절 없음 (MVP; P12 이후 추가)

**안티앨리어싱**: 픽셀 내 stratified jitter, `samples`개 평균.

**감마 보정**: `color^(1/2.2)` 최종 출력 전 적용.

**카메라**: 핀홀 퍼스펙티브, FOV(y), z-up 월드 → right-hand 뷰 좌표계.

### 광원 방향 규약

`LightSnapshot.direction` = 광원에서 씬을 향하는 방향 (하향).  
셰이더 내 부호: `toward_light = -light.direction` 으로 변환 후 `dot(N, toward_light)`.

---

## Task 체크리스트

- [x] T1: P6 SPEC 작성
- [ ] T2: `render/hq/scene.py` — SceneSnapshot → HQScene 변환
- [ ] T3: `render/hq/raytracer.py` — 벡터화 레이 트레이서
- [ ] T4: `render/hq/renderer.py` — HQRenderer(Renderer)
- [ ] T5: `recorder.py` — HQ 모드 활성화
- [ ] T6: `examples/02_bounce_hq_video.py`
- [ ] T7: `tests/test_hq_renderer.py`
- [ ] T8: pytest ✅ + ruff ✅ + mypy ✅ + bounce.mp4 실제 산출

---

## 검증 기준 (게이트)

### G1. bounce.mp4 산출
```python
rec = f3d.Recorder(world, mode="hq", resolution=(480, 320), samples=4, output="bounce.mp4")
rec.run(duration=2.0, dt=1/240, fps=24)
```
- `bounce.mp4` 파일이 생성되어야 한다.
- 공이 지면에서 튀는 장면이 시각적으로 올바르게 렌더링되어야 한다.

### G2. 렌더러 계약 (SceneSnapshot 동일 입력)
- 동일 SceneSnapshot을 실시간·HQ 두 렌더러에 넣었을 때 둘 다 같은 물체를 렌더링 (회귀 테스트).

---

## 완료 조건

- [ ] pytest 전체 통과 (기존 186개 + 신규 ≥6개)
- [ ] ruff ✅ mypy ✅
- [ ] `bounce.mp4` 실제 산출 및 확인
- [ ] 렌더러 계약 테스트 통과
