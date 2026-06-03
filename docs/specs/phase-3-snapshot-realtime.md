# SPEC: Phase 3 — SceneSnapshot 계약 + 실시간 렌더러(MVP)

> 파생: ROADMAP §5.1, §7, §9 P3. 검증 게이트: 떨어지는 상자를 창에서 60FPS로 관찰.
> 이 Phase의 목적은 "예쁜 그림"이 아니라 **물리↔렌더 분리의 계약(SceneSnapshot)을 세우고**, 이후 모든 단계를 눈으로 디버깅할 발판을 만드는 것이다.

## 1. 목표 (한 문장)
물리 코어가 렌더러 비의존 `SceneSnapshot`을 생성하고, 그 스냅샷만 받아 그리는 **실시간 OpenGL 렌더러 MVP**로 떨어지는 상자를 60FPS로 표시한다.

## 2. 범위
- **포함**: `SceneSnapshot` 데이터 계약, `Renderer` ABC, `Camera`/`Light`/`Material` 장면 기술, `RealtimeRenderer`(moderngl 래스터화 + 기본 셰이딩 + 그림자맵 1개 + 그리드/축), 헤드리스 오프스크린(EGL/Xvfb) 캡처 경로.
- **제외**: 고품질 레이트레이서(P6), pygame식 Facade·Viewer 인터랙션(P4 — 여기선 최소 구동 스크립트만), 로봇 모델/슬라이더 UI(P7), PBR 풀세트.

## 3. 영향 파일 / 인터페이스
- `src/forge3d/render/snapshot.py` — `SceneSnapshot`(순수 데이터): 바디별 `(transform 4x4, shape_handle, material_id)` 배열 + `Camera` + `Light` 목록. **물리 타입·백엔드(jnp 배열)에 의존하지 않도록** 일반 float 배열로 정규화.
- `src/forge3d/render/base.py` — `Renderer(ABC)`: `render(snapshot) -> Frame | None`, `set_camera(camera)`; `Camera`(eye/target/fov/near/far), `Light`(dir/point/intensity), `Material`(color/roughness/metallic).
- `src/forge3d/render/realtime/__init__.py`, `renderer.py` — moderngl 컨텍스트, 셰이더(Phong/PBR-lite), 그림자맵 패스, 그리드·축 헬퍼, `Frame`(rgb ndarray) 반환.
- `src/forge3d/render/realtime/context.py` — 윈도우(glfw/pyglet) vs 오프스크린(EGL) 컨텍스트 생성 추상화.
- `src/forge3d/sim/world.py`(확장) — `world.snapshot() -> SceneSnapshot` 생성 메서드. **`world`는 `render`를 import하지 않는다**(스냅샷은 순수 데이터만 반환).
- `examples/01_falling_box_realtime.py` — MVP 구동 스크립트(임시; 정식 Facade는 P4).
- `tests/test_snapshot.py`, `tests/test_realtime_smoke.py`.

## 4. 구현 작업
- [ ] **T1.** `SceneSnapshot` 정의 + `world.snapshot()` — 완료 조건: 물리 상태에서 순수 데이터 스냅샷 생성, `render` 모듈 import 없음.
- [ ] **T2.** `Renderer` ABC + `Camera`/`Light`/`Material` 장면 기술 타입 정의.
- [ ] **T3.** 컨텍스트 추상화: 창 모드(glfw) + 오프스크린 모드(EGL). — 완료 조건: 헤드리스에서 OpenGL 컨텍스트 생성 가부를 런타임에 판별, 불가 시 명확한 에러.
- [ ] **T4.** `RealtimeRenderer`: 메시 업로드, 기본 셰이딩, 그림자맵 1패스, 그리드/축. — 완료 조건: 스냅샷 1장을 RGB 프레임으로 렌더.
- [ ] **T5.** 떨어지는 상자 루프(step→snapshot→render)로 60FPS 표시 + 오프스크린 프레임 캡처. `examples/01_*` 작성.

## 5. 엣지 케이스 / 제약
- **헤드리스 OpenGL 가용성 불확실**(ROADMAP §4.1, §14): 컨테이너에서 EGL/Xvfb 오프스크린이 되는지 **T3에서 먼저 확인**. 불가하면 멈추고 보고 — 소프트 래스터라이저 폴백을 별도 task로 분리(이 SPEC 범위 밖).
- 좌표계 **z-up, SI 단위** 고정(렌더러도 동일 규약).
- 스냅샷은 jnp/np 어느 백엔드 상태에서 만들어도 동일한 순수 배열이어야 함.
- 렌더링은 물리 dt와 독립(표시 fps ≠ 물리 dt).

## 6. 검증 (게이트)
- **렌더러 계약**: `world.snapshot()`이 `render` import 없이 동작, 동일 스냅샷을 반복 렌더 시 결정적 프레임(골든 이미지 비교, 허용오차 내).
- **분리 강제**: `grep`/AST로 `src/forge3d/sim/`·`dynamics/`·`contact/` 등 물리 코어가 `forge3d.render`를 import하지 않음을 테스트로 확인.
- **기능**: 떨어지는 상자 예제가 창에서 ~60FPS, 또는 헤드리스에서 N프레임 PNG 캡처 성공.
- **백엔드**: 스냅샷 생성이 `ENGINE_BACKEND=numpy`/`=jax` 양쪽에서 동일 결과.
- **통과 기준**: `pytest tests/test_snapshot.py tests/test_realtime_smoke.py -q` 통과(헤드리스), `python examples/01_falling_box_realtime.py --headless --frames 30`이 PNG 산출.

## 7. 완료 후 리뷰
- 서브에이전트: "물리 코어가 render를 전혀 모르는가(import·타입 의존 없음)? 스냅샷이 백엔드 중립인가? 헤드리스 가용성 판별이 견고한가? 외부 물리엔진 미사용?"
