# SPEC: Phase 4 — pygame식 공개 API(Facade) + Viewer

> 파생: ROADMAP §6, §9 P4. 검증 게이트: §6.1 진입 예제가 그대로(15줄 이내) 동작.
> 목적은 "5분 안에 머릿속 모델이 잡히는" 얇은 표면을 세우는 것. 새 물리 기능을 더하는 단계가 아니다.

## 1. 목표 (한 문장)
물리 코어와 렌더러 위에 **pygame식 Facade**(`World`/`Body`/`Joint`/`Shape`/`Viewer`/`Recorder`)를 얹어, 사용자가 라이브러리 내부를 몰라도 15줄 이내로 장면을 만들고 실시간 관찰하게 한다.

## 2. 범위
- **포함**: `forge3d.__init__`의 공개 표면 확정, `World` 헬퍼(`add_ground/add_box/add_sphere/add/step`), `Body`/`Shape`/`Material` 사용자 표면, `Viewer`(궤도 카메라·줌/팬·일시정지·스텝, `is_open`/`draw()`/`run()`), 똑똑한 기본값(dt·카메라·머티리얼·조명).
- **제외**: `Recorder`의 HQ 경로 실제 구현(P6 — 여기선 인터페이스 자리표시), 로봇 슬라이더/목표 드래그(P7), RL 환경(P8).

## 3. 영향 파일 / 인터페이스
- `src/forge3d/__init__.py` — 공개 심볼만 노출: `World, Body, Joint, Shape, Material, Viewer, Recorder`. **개념 5~6개 한도 준수.**
- `src/forge3d/sim/world.py`(확장) — 한 줄 헬퍼: `add_ground(material=...)`, `add_box(size, position, mass)`, `add_sphere(radius, position, restitution)`, `add(obj)`, `step(dt=기본값)`. 인자 없이도 합리적 동작.
- `src/forge3d/viewer.py` — `Viewer(world, mode="realtime", controls=None)`: `is_open`, `draw()`, `run()`, 궤도 카메라·줌/팬·일시정지·스텝 단위 진행. 내부적으로 `world.snapshot()` → `RealtimeRenderer`.
- `src/forge3d/recorder.py` — `Recorder(world, mode=..., output=...)`: `run(duration, dt, fps)`, `run_policy(policy, duration)` **인터페이스만**(HQ는 P6에서 채움; realtime 캡처는 동작 가능).
- `examples/01_falling_box_realtime.py`(정식화), `examples/03_robot_interactive.py`(자리표시).
- `tests/test_api_usability.py`, `tests/test_viewer_smoke.py`.

## 4. 구현 작업
- [ ] **T1.** 공개 표면 확정: `__init__.py`에서 노출 심볼 5~6개로 제한, 하위 객체는 고급 사용자만 접근하도록 설계.
- [ ] **T2.** `World` 한 줄 헬퍼 + 똑똑한 기본값(dt, 솔버 반복, 카메라/조명/머티리얼). — 완료 조건: 인자 최소로 §6.1 장면 구성.
- [ ] **T3.** `Viewer` 구현(P3 렌더러 위): `is_open`/`draw()` 루프 + `run()` 편의 루프, 궤도 카메라·일시정지·스텝.
- [ ] **T4.** `Recorder` 인터페이스 + realtime 캡처 경로(HQ는 P6 자리표시, `NotImplementedError`로 명확히).
- [ ] **T5.** `examples/01_*` 정식화(15줄 이내), 친절한 에러 메시지(예: "관절 범위 초과")를 공통 예외로.

## 5. 엣지 케이스 / 제약
- **API 비대화 방지**(ROADMAP §14): 새 공개 개념을 늘리기 전 헬퍼·기본값으로 해결되는지 먼저 본다. 노출 심볼이 6개를 넘으면 멈추고 재설계.
- z-up·SI 단위를 공개 문서(docstring) 최상단에 고정.
- 헤드리스에서 `Viewer`는 오프스크린으로 강등되거나 친절한 안내(창 불가)를 내야 함.
- Facade는 물리/렌더 내부 타입을 사용자에게 새지 않게(누수 = 추상화 실패).

## 6. 검증 (게이트)
- **API 사용성(핵심)**: `examples/01_falling_box_realtime.py`가 **라이브러리 내부를 import하지 않고**(오직 `import forge3d`) **15줄 이내**로 동작. 테스트가 줄 수·내부 import 부재를 자동 확인.
- **렌더러 무관 코드**: 같은 `World` 구성 코드가 Viewer(realtime) 경로에서 동작(P6 후 Recorder HQ로 확장 시 물리 코드 불변임을 보장하는 설계).
- **기능**: `Viewer` 스모크(헤드리스 오프스크린)로 N프레임 렌더, 일시정지/스텝 동작.
- **통과 기준**: `pytest tests/test_api_usability.py tests/test_viewer_smoke.py -q` 통과, `python -c "import forge3d; w=forge3d.World(); w.add_ground(); w.add_box(); w.step()"` 무오류.

## 7. 완료 후 리뷰
- 서브에이전트: "처음 보는 사람이 5분 안에 모델을 잡을 만큼 표면이 얇은가? 공개 개념이 6개 이내인가? 내부 타입이 사용자에게 새지 않는가? 예제가 15줄 이내·내부 미접근인가?"
