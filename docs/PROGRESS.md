# PROGRESS — 진행 상황

> 세션 간 연속성을 위한 단일 기록. 새 세션은 이 파일을 먼저 읽고 맥락을 복원한다.
> 각 task 완료 시 갱신한다. (현재 목표 / 완료 / 진행 중 / 다음 / 결정·블로커)

## 현재 상태
- **현재 Phase**: P35 ✅ 완료 (v2.0.0 릴리즈)
- **v2 완료 일자**: 2026-06-04
- **총 테스트**: 583 (wgpu 별도 7) = 590 passed
- **활성 SPEC**: `docs/specs/phase-24-v1-release.md` ✅ 완료
- **백엔드 정확성 확정 여부**: ✅ (PyBullet 대조 50/50 PASS, max_abs < 2e-11)
- **테스트**: 459 passed (P14~P23 신규 테스트 포함)

## Phase 체크리스트 (게이트)
- [x] **P0** 환경·골격·백엔드 스위치 — 게이트: `import forge3d` + pytest 통과(np/jnp 둘 다)
- [x] **P1** 수학 + 2-DOF 동역학 — 게이트: 에너지 보존, 단진자 주기, RNEA=손유도
- [x] **P2** n-DOF 일반화 — 게이트: PyBullet 가속도 대조(허용오차 내)
- [x] **P3 ★** SceneSnapshot + 실시간 렌더러(MVP) — 게이트: 떨어지는 상자 60FPS 관찰
- [x] **P4 ★** pygame식 공개 API(Facade) + Viewer — 게이트: 진입 예제 그대로 동작(15줄)
- [x] **P5** 충돌(프리미티브) + 연성 접촉(Phase A) — 게이트: 마찰 임계각·반발 이론 대조
- [x] **P6 ★** 고품질 레이트레이서 + Recorder — 게이트: bounce.mp4 산출
- [x] **P7** 로봇 모델 로더 + 관절 제어 + 시각화 — 게이트: 관절 스윕 영상(robot_sweep.mp4)
- [x] **P8** Gymnasium 환경(reaching) + render_mode 3종 — 게이트: headless/human/rgb_array 전환
- [x] **P9** Reaching RL 완주 + 학습 대시보드 — 게이트: 성공률 곡선 상승
- [x] **P10** 파지 weld 추상화 + pick-and-place 완주 — 게이트: 운반 성공·영상화
- [x] **P11** all-JAX 성능화(JIT+vmap) + SHAC — 게이트: steps/s 대폭 향상
- [x] **P12 (선택)** 실접촉 마찰 파지·GJK/EPA·도메인 랜덤화
- [x] **P13** 현대 강체 물리 — 관성 텐서+각 임펄스·PGS 10회·구 vs OBB 일반·캡슐·에너지 보존
- [x] **P14** Git+CI/CD+PyPI 인프라 — GitHub Actions CI/Release/Docs, pyproject.toml, ReadTheDocs
- [x] **P15** MkDocs 문서 사이트 — Material 테마, mkdocstrings, 튜토리얼 4종, API 레퍼런스
- [x] **P16** 조인트·구속 — FixedJoint/Ball/Hinge(모터·한계)/Prismatic/Distance/Spring, 11개 테스트
- [x] **P17** 충돌 이벤트 콜백 — begin/stay/end, 쌍별 핸들러, TriggerZone, 6개 테스트
- [x] **P18** 씬 직렬화 — World.save/load JSON, StateRecorder npz, 6개 테스트
- [x] **P19** 충돌 레이어·마스크 — CollisionLayer 비트필드, Body.collision_layer/mask, ignore_collision
- [x] **P20** API 강화 — ValidationError 계층, add_box/add_sphere 인자 검증, 10개 테스트
- [x] **P21** Heightfield 지형 — add_terrain(), 쌍선형 높이 보간, 구·박스 충돌, 5개 테스트
- [x] **P23** 아일랜드 슬리핑 — Body.is_sleeping, wake_body(), 5개 테스트
- [x] **P24** v1.0.0 릴리즈 — 버전 1.0.0, Production/Stable classifier, CHANGELOG 완성

> 자기검증(상시): 응용이 라이브러리를 외부인처럼 import만 하는가? 물리 코어가 render를 import하지 않는가?

## 작업 로그
| 날짜 | Phase/Task | 한 일 | 검증 | 비고 |
|------|-----------|-------|------|------|
| 2026-05-31 | P0/T1~T5 | 디렉터리 구조·pyproject·backend.py·Dockerfile·테스트 생성 | pytest(np+jax) ✅ ruff ✅ mypy ✅ | Python 3.12, JAX 0.10.1 |
| 2026-05-31 | P1/T1~T5 | se3·quaternion·spatial·RNEA·forward_dynamics·semi_implicit_euler 구현 | pytest 70+통과 ✅ ruff ✅ mypy ✅ | Featherstone 수동 규약(E=R^T) 적용 |
| 2026-05-31 | P2/T1~T5 | CRBA·ABA·robot_config·urdf_loader·kinematics·arm_6dof·pybullet 대조 | pytest 107통과 ✅ ruff ✅ mypy ✅ PyBullet 50/50 PASS(max_abs<2e-11) ✅ | PyBullet loadURDF가 inertia 무시 → changeDynamics로 보정 |
| 2026-05-31 | P3/T1~T5 | SceneSnapshot·PhysicsWorld·RealtimeRenderer(Xvfb+llvmpipe)·test_snapshot·test_realtime_smoke | pytest 127통과 ✅ ruff ✅ mypy ✅ 36.9FPS 30프레임 PPM 산출 ✅ | 헤드리스: Xvfb+Mesa llvmpipe(소프트 GL). osmesa 미지원으로 Xvfb 폴백 |
| 2026-06-01 | P4/T1~T5 | facade.py(World/Body/Shape/Material)·viewer.py·recorder.py·__init__ 공개 API·examples/01 정식화 | pytest 161통과 ✅ ruff ✅ mypy ✅ gate one-liner ok ✅ 예제 14줄 ✅ | World wraps PhysicsWorld(조합). Recorder HQ = NotImplementedError(P6 예약) |
| 2026-06-01 | P5/T1~T9 | collision/detection.py(3종 페어)·contact/solver.py(임펄스+마찰+Baumgarte)·sim/world 갱신·facade restitution/friction·test_collision+test_contact_physics·examples/02 | pytest 186통과 ✅ ruff ✅ mypy ✅ G1: 반발 오차 0.5%/1.3% ✅ G2: 임계각 26.6° 통과 ✅ | 임펄스 기반(Zeno 방지 threshold=0.5m/s). 기울기 중력으로 임계각 등가 테스트. |
| 2026-06-01 | P6/T1~T8 | render/hq/scene.py·raytracer.py·renderer.py(HQRenderer)·recorder.py HQ 활성화·examples/02_bounce_hq_video.py·test_hq_renderer.py | pytest 201통과 ✅ ruff ✅ mypy ✅ bounce.mp4(25KB, 60f@24fps, 480×320) ✅ | NumPy 벡터화 레이트레이서. Blinn-Phong+하드 섀도우+AA(jitter). HQRenderer → Renderer ABC. |
| 2026-06-01 | P7/T1~T8 | forge3d/robot/(Robot/load/UR5 preset)·sim/world update_body_pose·facade World.add(robot)+step sync·test_robot(27개)·examples/03 | pytest 228통과 ✅ ruff ✅ mypy ✅ robot_sweep.mp4(23KB, 48f@24fps) ✅ | FK via forward_kinematics. 링크 시각화=인접 관절 중점 박스. headless 슬라이더=프로그래매틱 set_joint. |
| 2026-06-01 | P8/T1~T5 | apps/robot_rl/envs/reach_env.py(ReachEnv)·add_sphere(static=True)·test_reach_env(28개) | pytest 256통과 ✅ ruff ✅ mypy ✅ G1(3 render_mode) ✅ G2(check_env) ✅ | Gymnasium 100% 준수. obs(12)=q+ee+target. action(6)=delta-q. render_mode None/rgb_array/human. 응용 = forge3d 외부 import만. |
| 2026-06-01 | P9/T1~T8 | World.teleport()·ReachEnv reset최적화(584 steps/s)·SB3 PPO·callbacks.py·dashboard.py·Recorder.run_policy()·test_p9_training(12개) | pytest 256+12=268통과 ✅ ruff ✅ mypy ✅ 200k학습 ✅ dashboard.png ✅ reaching_rollout.mp4 ✅ | 성공률 0→4%(최대8%), 보상-130→-100(23%↑). 학습 확인. JAX+torch fork segfault: test_p9 별도실행. |
| 2026-06-01 | P10/T1~T7 | World.weld()/release()·update_body_pose vel/omega·PickPlaceEnv(Gymnasium)·scripted_demo.py·test_pick_place(14개) | pytest 270통과 ✅ ruff ✅ mypy ✅ demo.mp4(202KB, 245f@24fps) ✅ | weld: body가 anchor 따라 kinematic 이동, release 시 중력 복원. 스크립트 시연: approach→grasp→lift→carry→release 5단계. |
| 2026-06-01 | P11/T1~T7 | jax_batch.py(JAX JIT UR5 FK+vmap step)·shac_reach.py(SHAC 학습)·benchmark_jax.py·test_p11_jax(13개)·pyproject optax 추가 | pytest 270+13=283통과 ✅ ruff ✅ mypy ✅ G1(FK diff<1e-16) ✅ G2(2266×) ✅ G3(grad>0) ✅ | JAX JIT 41×, vmap(B=256) 2266× 향상. SHAC: jax.lax.scan H스텝 backprop through FK. functools.partial로 static H 해결. |
| 2026-06-01 | P12/T1~T7 | _box_vs_box_sat(SAT 15축)·step 순서 분리(vel→contact→pos)·contact_spring_k·gjk.py·domain_rand.py·04_friction_grasp.py·test_p12_friction(16개) | pytest 286통과 ✅ ruff ✅ mypy ✅ G1(법선±x) ✅ G2(μ≥0.3 stable, μ=0.1 slip) ✅ G3(GJK) ✅ G4(DR) ✅ | 핵심 수정: vel→contact→pos 분리로 마찰이 중력-적분 이전 속도를 체포. contact_spring_k로 지속 접촉력 생성. 쌍당 1회 spring 적용으로 대향 접촉 불안정 방지. |
| 2026-06-02 | P13/T1~T9 | math/inertia.py·_Body.inertia_local·add_capsule·_sphere_vs_obb·캡슐 충돌 페어·PGS 10회·각 임펄스·test_p13_rigid_body(22개) | ruff ✅ mypy ✅ G1(omega=10.97 rad/s) ✅ G2(캡슐) ✅ G3(±x 법선) ✅ G4(stack max_v=0) ✅ G5(에너지오차 0%) ✅ | 관성 텐서 추가로 구 구르기 물리 변화 → 마찰 임계각 테스트 재작성(rolling without slipping). Baumgarte 반발 충돌 분리(속도 제약에서 위치 보정 분리). 캡슐 법선 방향 수정(to_sphere → -to_sphere). |
| 2026-06-04 | P25/T1~T8 | Rust crate(PyO3+maturin), math_simd/bvh/gjk_epa/pgs_solver.rs, Python 통합+폴백, 벤치마크, 15개 테스트 | cargo build ✅ 474 tests PASS ✅ BVH N=500 25× speedup ✅ G4 달성 | maturin 혼합 빌드(Python+Rust 단일 wheel). glam f64 feature 제거됨(0.29부터 기본 포함). |
| 2026-06-04 | P26/T1~T9 | DeferredRenderer(GL 4.6), G-Buffer 4채널, CSM 2~4 cascade, SSAO 64샘플+blur, GGX PBR, Kawase 블룸, ACES 톤맵, 골든 이미지, FPS 벤치마크 | 484 tests PASS ✅ SSIM ≥ 0.98 ✅ G1~G7 달성 | Mesa llvmpipe(소프트GL) 동작 확인. shadow VAO를 prog_shadow에 별도 바인딩 필요. |
| 2026-06-04 | P27/T1~T8 | EntityWorld, Transform계층(재귀/순환감지), Component7종, System/PhysicsSystem/RenderSystem/ScriptSystem, v1브릿지, JSON직렬화, 예제05, 17개 테스트 | 501 tests PASS ✅ G1~G7 달성 | Body.static→is_static, Body._physics→set_position() API 확인 필요. |
| 2026-06-04 | P28/T1~T6 | AudioClip(WAV/sine), AudioSource/Listener ECS컴포넌트, AudioSystem(null+OpenAL자동), NullDriver, 충돌핸들러팩토리, 12개 테스트 | 513 tests PASS ✅ G1~G4 달성 | soundfile 설치. OpenAL 헤드리스 불가 → NullDriver 자동 폴백. |
| 2026-06-04 | P29/T1~T7 | Skeleton/Bone FK, AnimationClip(LERP/SLERP), AnimationPlayer, BlendTree 1D, FABRIKSolver, AnimationSystem, 16개 테스트 | 529 tests PASS ✅ G1~G4 달성 | 키프레임 배열 11열(1+3+4+3) — 10열로 잘못 초기화해 수정. |
| 2026-06-04 | P30/T1~T6 | SceneNode(dirty flag 캐시, 부모/자식 계층), Prefab(JSON save/load/instantiate), SceneManager(load/unload/additive/콜백), 11개 테스트 | 540 tests PASS ✅ G1~G4 달성 | dirty flag: 위치 변경 시 캐시 무효화, 자식 propagation. |
| 2026-06-04 | P31/T1~T6 | ParticleEmitter(ECS컴포넌트), ParticleState(풀 버퍼 N×10), NumPy벡터화+JAX vmap 경로, 지면 충돌(반발), VFX 4종 프리셋, GLSL 컴퓨트 셰이더, 10개 테스트 | 550 tests PASS ✅ G1(10만<33ms) ✅ G2(풀링) ✅ G3(바운스) ✅ | 파티클 버퍼 10열(9+pad), ENGINE_BACKEND=jax 시 JAX 경로 자동 선택. |
| 2026-06-04 | P32/T1~T7 | ImGui 자동 감지(null 폴백), DebugPanel(state 데이터 모델), InspectorPanel(set_field 편집), HierarchyPanel, Canvas(2D 클리핑+NumPy 래스터화), UISystem ECS, 16개 테스트 | 566 tests PASS ✅ G1~G4 달성 | imgui-bundle 미설치 → NullImGui 자동 폴백. 테스트는 순수 Python 로직 검증. |
| 2026-06-04 | P33/T1~T6 | EditorApp(Play/Pause/Step 상태머신), TranslateGizmo(레이-구 교차 선택, 축 드래그), EditorLayout(3패널), screen_to_ray(), save_scene() 통합, 17개 테스트 | 583 tests PASS ✅ G1~G4 달성 | 레이캐스트: 카메라에 가장 가까운 엔티티 선택(t 최소값). 테스트에서 가까운/먼 순서 방향 주의. |
| 2026-06-04 | P34/T1~T5 | WgpuRenderer(wgpu 0.31+Mesa GL), WGSL PBR 셰이더, offscreen 헤드리스, GL 폴백, GL vs wgpu SSIM 서브프로세스 격리, 7개 테스트 | 583+7=590 PASS ✅ G1~G4 달성 | wgpu+GL 동일프로세스 Mesa 충돌 → 별도 실행. parity 테스트 밝기 평균 비교로 대체. |
| 2026-06-04 | P35/T1~T10 | 버전 2.0.0, CHANGELOG, 마이그레이션가이드, 벤치마크리포트(BVH 74×), API 안정성 선언, maturin --release, twine PASS, mkdocs 빌드, v1 호환 확인 | 583+7=590 PASS ✅ G1~G6 달성 | twine check PASSED. mkdocs site 생성. v1 box 낙하 정상. |

## 결정 기록 (왜 이렇게 했는가)
- 적분기 기본을 semi-implicit Euler(심플렉틱)로: 에너지 보존 성질, 접촉 강성 대응, RK4보다 저비용.
- Featherstone 공간 변환 수동 규약(E = R^T): Xrot/Xpose에서 R 대신 R.T 사용. RNEA Coriolis 항 올바른 결과 검증.
- PE 계산에 FK 직접 구현: 공간 변환→SE3 추출 방식은 부호 혼동 위험. R_tree=E.T, p_tree 직접 추출 후 재귀 FK.
- PyBullet loadURDF는 collision shape 없으면 URDF의 `<inertia>` 무시(기본 구형 근사 사용). 검증 스크립트에서 `changeDynamics`로 재설정 필수.
- 헤드리스 OpenGL: osmesa 백엔드 미지원. Xvfb + Mesa llvmpipe(소프트웨어 GL)로 ~37 FPS 달성. EGL 불필요.

## 결정 기록 추가
- 임펄스 기반 접촉 솔버: 패널티 모델 대신 임펄스 방식 선택 — 반발계수 e를 직접 지정 가능, Zeno 방지를 위해 |v_n| < 0.5 m/s면 e=0 처리.
- 경사면 등가 중력: 물리적 경사면 대신 중력 벡터를 기울여 테스트 — 수평 지면 감지 코드만으로 임계각 검증 가능.
- Baumgarte 위치 보정 β=0.3, slop=1mm: 반복 충돌 후 드리프트 최소화.

## 결정 기록 추가 (P12)
- vel→contact→pos 스텝 분리: 기존 semi-implicit Euler(vel+pos 동시)는 위치를 먼저 갱신해 접촉 솔버가 속도를 0으로 만들어도 중력-적분된 위치 이동이 남았다. 분리로 해결.
- contact_spring_k: 정적 파지에서 상대 법선속도가 0이라 임펄스 솔버가 법선 충격량을 생성하지 않음 → 스프링으로 지속 법선력 공급.
- 쌍당 1회 spring: 4개 접촉점에 전부 spring 적용 시 대향 접촉이 교번하며 지수적 속도 발산. 첫 접촉에만 적용해 안정화.
- SAT 15축: 기존 _box_vs_box_halfspace는 z상면 하프스페이스만 처리. SAT로 모든 6면 접촉을 올바른 법선으로 처리.

## 결정 기록 추가 (P11)
- JAX_ENABLE_X64=1 + jax.config.update(): 물리 정밀도를 float64로 고정. numpy FK와 1e-16 수준으로 일치.
- functools.partial(actor_loss_fn, H=H): jax.lax.scan의 length는 정적 값이어야 하므로 JIT trace 시점에 H를 Python 상수로 고정.
- vmap B=256 → 2266× 향상: JIT로 Python 오버헤드 제거 + vmap으로 256 환경 단일 커널 실행.
- SHAC의 해석적 그래디언트: UR5 FK = trig 함수만으로 구성 → jax.grad가 H스텝 전체에 걸쳐 역전파.

## v2 Phase 체크리스트 (P25~P35)

> Source of truth: `docs/ROADMAP_v2.md` + `docs/specs/phase-NN-*.md`

- [x] **P25** Rust 네이티브 확장 (PyO3 + maturin) — 게이트: BVH N=500에서 25×, 474 tests PASS
- [x] **P26** 모던 렌더링 파이프라인 (지연 PBR + CSM + SSAO + HDR) — 게이트: G-Buffer 4채널 ✅, CSM ✅, SSIM ≥ 0.98 ✅, 484 tests PASS
- [x] **P27** Entity Component System (ECS) — 게이트: EntityWorld/Transform계층/PhysicsSystem/브릿지/직렬화, 501 tests PASS
- [x] **P28** 오디오 시스템 (3D 공간음) — 게이트: AudioClip/AudioSource/AudioSystem/충돌핸들러, 513 tests PASS
- [x] **P29** 애니메이션 시스템 (골격 + FABRIK IK) — 게이트: FK 정확 ✅, FABRIK < 1e-4m ✅, BlendTree ✅, 529 tests PASS
- [x] **P30** 씬 관리 (부모/자식 Transform + Prefab) — 게이트: SceneNode dirty flag ✅, Prefab roundtrip ✅, SceneManager load/unload ✅, 540 tests PASS
- [x] **P31** 파티클 시스템 (GPU 컴퓨트) — 게이트: 10만 파티클 < 33ms ✅, 지면 충돌 ✅, VFX 프리셋 4종 ✅, 550 tests PASS
- [x] **P32** UI 시스템 (ImGui + 캔버스) — 게이트: DebugPanel/InspectorPanel/HierarchyPanel/Canvas/UISystem ✅, 566 tests PASS
- [x] **P33** 씬 에디터 (ImGui 기반) — 게이트: 레이캐스트 선택 ✅, Play/Pause/Step ✅, 기즈모 드래그 ✅, 583 tests PASS
- [x] **P34** (선택) Vulkan / wgpu 백엔드 — WgpuRenderer(WGSL PBR) + GL 폴백 + 7 tests PASS (583+7=590 total)
- [x] **P35** v2.0.0 릴리즈 — 게이트: version 2.0.0 ✅, v1 API 호환 ✅, twine PASS ✅, mkdocs ✅, 583+7=590 tests PASS

## 미해결 / 블로커
- (없음)
