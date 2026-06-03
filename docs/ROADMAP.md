# forge3d — 프로젝트 로드맵 (마스터 기획안 v2)

> **이 문서의 역할**: 프로젝트의 *정식 기준(source of truth)*. 비전·아키텍처·순서·검증 기준·리스크를 정의한다.
> 개별 작업은 이 문서에서 파생된 `docs/specs/phase-N-*.md` SPEC을 따라 실행한다.
> 작업 규칙·가드레일은 루트 `CLAUDE.md`, 실행 절차는 `docs/WORKFLOW.md` 참조.

---

## 1. 비전과 환경

pygame처럼 **쉽게 쓰는 3D 물리엔진 라이브러리**(가칭 `forge3d`)를 순수 Python으로 만들고, 그 라이브러리 위에서 산업용 로봇 팔의 **pick-and-place 정책을 강화학습**한다. 라이브러리는 **고품질(오프라인) 렌더러**와 **실시간 렌더러**를 모두 제공하며, 로봇 팔 학습은 사용자가 **쉽게 조작·관찰**할 수 있어야 한다.

- **환경**: Ubuntu / Docker. **물리·학습 연산은 GPU 불가(CPU only)**. 백엔드 혼용(NumPy / JAX / PyTorch) 가능.
- **산출물 우선순위**: ① 재사용 가능한 물리엔진 **라이브러리**(1급) → ② 그 위의 로봇 팔 **학습 애플리케이션**.

## 2. 두 개의 산출물, 명확한 분리

이 프로젝트는 **라이브러리**와 **응용**의 2층 구조다.

```
[ 응용: 로봇 팔 RL ]   ← 사용자 코드. 라이브러리의 "고객 1호"
        │  (라이브러리를 import해서 사용)
        ▼
[ 라이브러리: 물리엔진 + 렌더러 ]   ← 재사용 가능한 1급 산출물 (forge3d)
```

가장 중요한 자기검증 질문: **"로봇 팔 코드를 짤 때, 내가 만든 라이브러리를 외부인처럼 import해서 쓰고 있는가?"** 라이브러리 내부를 들여다봐야만 응용을 짤 수 있다면 추상화가 실패한 것이다.

## 3. "온전히 Python" 제약의 운용 원칙

판단 기준 — **"동역학과 접촉을 누가 푸는가?"** 그 답이 항상 우리 코드여야 한다.

- **직접 구현 대상**: 동역학(RNEA/CRBA/ABA), 적분기, 충돌·접촉 해석, 구속 솔버, 기구학, **그리고 고품질 렌더러(소프트웨어 레이트레이서)**.
- **사용 허용 패키지**: NumPy, JAX, PyTorch, SciPy, SymPy, Gymnasium, optax/flax/equinox, stable-baselines3, 그리고 **그래픽 출력용** `moderngl`/`pyglet`/`glfw`, `imgui`, `imageio`/`ffmpeg`.
- **엔진 금지**: 외부 물리엔진(MuJoCo/PyBullet/Bullet/ODE/DART/Isaac/Brax). 단 MuJoCo·PyBullet은 `validation/`에서 *기준값 대조 전용*.

## 4. "고품질 렌더링" vs "실시간 렌더링"의 현실적 정의 ★

| 구분 | 실시간 (Realtime) | 고품질 (High-Quality / Offline) |
|------|-------------------|---------------------------------|
| 용도 | 게임, 인터랙티브 뷰어, 학습 실시간 관찰 | 결과 영상, 논문 그림, 데모 |
| 목표 | 30~60 FPS, 즉각 반응 | 프레임당 수 초~수십 초, 화질 최우선 |
| 방식 | GPU 래스터화(OpenGL via `moderngl`/`pyglet`) | 소프트웨어 레이트레이싱(직접 구현) |
| 화질 | 기본 셰이딩, 그림자맵, 단순 머티리얼 | 그림자, AO, 반사, AA, PBR |
| 출력 | 화면(window) | PNG 시퀀스 → mp4 |

### 4.1 GPU 제약 해석
- "GPU 불가"는 **물리·학습 연산을 GPU에서 돌리지 않는다**로 해석한다(공정한 CPU 벤치마크, 환경 제약).
- **그래픽 출력용 OpenGL은 허용**한다. 화면에 삼각형을 그리는 GPU 래스터화는 물리 연산과 무관하며, 없으면 실시간 렌더링이 성립하지 않는다.
- ⚠️ **확인 필요**: 환경에 GPU가 물리적으로 없어 OpenGL 가속도 불가하면 → 실시간 렌더러도 **CPU 소프트웨어 래스터라이저**로 구현(가능하나 FPS 낮음). 헤드리스 서버면 `EGL`/`Xvfb`로 오프스크린 OpenGL이 되는지부터 확인한다.

### 4.2 "순수 Python" 관점의 고품질 렌더러
- 엔진 철학("직접 만든다")에 맞게 **소프트웨어 레이트레이서를 직접 구현**하는 게 가장 정합적. NumPy 벡터화 + (선택) JAX JIT로 CPU에서 견딘다.
- 화질 우선·속도 부차(오프라인)라 이 선택이 현실적. 보조로 `Open3D` 오프스크린은 *응용 단계 편의*로만 둘 수 있으나 코어 렌더러는 직접 구현 지향.

## 5. 라이브러리 아키텍처 — 물리와 렌더링의 완전 분리

핵심 원칙: **물리 코어는 렌더러를 모른다.** 렌더러는 물리 상태의 "스냅샷"을 받아 그릴 뿐이다. 이래야 (a) headless 고속 학습, (b) 한 장면을 두 렌더러로, (c) 렌더러 교체·추가가 가능하다.

```
┌─────────────────────────────────────────────────────────┐
│                     공개 API (Facade)                     │  ← pygame식 얇은 표면
│   World, Body, Joint, Shape, Robot, Viewer, Recorder      │
└───────────────┬─────────────────────────┬────────────────┘
     ┌──────────▼──────────┐   ┌──────────▼───────────────┐
     │ 물리 코어 (headless) │   │   렌더링 계층 (옵션)      │
     │ math/ dynamics/      │   │ Renderer(ABC)             │
     │ collision/ contact/  │   │  ├ RealtimeRenderer (GL)  │
     │ model/ sim/ (np↔jnp) │   │  └ HQRenderer (raytrace)  │
     └─────────┬────────────┘   └──────────┬───────────────┘
               └────────► SceneSnapshot ◄───┘
                 (위치/자세/형상/머티리얼의 순수 데이터)
```

### 5.1 핵심 계약: `SceneSnapshot`
- 물리 코어는 매 스텝 **렌더러 비의존 스냅샷**(각 바디 변환행렬, 형상 핸들, 머티리얼 id, 카메라/조명)을 생성.
- 렌더러는 이 스냅샷만 받는다 → 물리↔렌더 디커플링의 핵심 계약.
- 학습 시엔 스냅샷 생성을 끄거나(완전 headless) 가볍게 유지.

### 5.2 계층 표 (★=v2 신규)

| 계층 | 내용 | 백엔드 |
|------|------|--------|
| 수학 | SE3, 쿼터니언, 공간 벡터 대수 | np↔jnp |
| 강체 동역학 | RNEA / CRBA / ABA | np↔jnp |
| 적분기 | semi-implicit Euler, RK4 | np↔jnp |
| 충돌 | 프리미티브 → GJK/EPA | np↔jnp |
| 접촉·파지 | 패널티 → weld 추상화 → 마찰 솔버 | np↔jnp |
| 모델 | URDF-유사 로더, 기구학, 그리퍼 | np↔jnp |
| 시뮬레이션 | World, step/reset, 상태관리, snapshot | np↔jnp |
| 렌더링 ★ | Renderer 추상 + 2백엔드, Camera/Light/Material | - |
| 공개 API ★ | pygame식 Facade | - |
| RL 환경 | gymnasium.Env, render_mode | 응용 |
| 학습 | PPO/SAC/SHAC, 대시보드 | 응용 |

## 6. pygame식 API 설계 — "5분 안에 머릿속 모델이 잡히게"

철학: **개념 수를 줄이고, 진입 코드를 짧게, 기본값을 똑똑하게.** 처음 만나는 객체는 5~6개 이내: `World`, `Body`, `Joint`(`Robot`), `Shape`, `Viewer`, `Recorder`.

### 6.1 진입 #1 — 게임처럼 (실시간)
```python
import forge3d as f3d
world = f3d.World(gravity=(0, 0, -9.81))
ground = world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
viewer = f3d.Viewer(world, mode="realtime")
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()
```

### 6.2 진입 #2 — 시뮬레이션처럼 (고품질 오프라인 영상)
```python
import forge3d as f3d
world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="slate", roughness=0.3))
ball = world.add_sphere(radius=0.5, position=(0, 0, 4), restitution=0.8)
rec = f3d.Recorder(world, mode="hq", resolution=(1920, 1080),
                   samples=64, output="bounce.mp4")
rec.run(duration=3.0, dt=1/240, fps=60)
```
같은 `World` API, 렌더러만 교체 — **물리 코드는 한 줄도 안 바뀐다** = 추상화 성공의 증거.

### 6.3 진입 #3 — 로봇 팔 (둘 다)
```python
import forge3d as f3d
import forge3d.robot as robot
world = f3d.World()
arm = robot.load("ur5")
world.add(arm)
world.add_box(size=(0.1,0.1,0.1), position=(0.5, 0, 0.1))
viewer = f3d.Viewer(world, mode="realtime", controls="robot")  # 관절 슬라이더
viewer.run()
rec = f3d.Recorder(world, mode="hq", output="grasp.mp4")
rec.run_policy(policy, duration=5.0)
```

### 6.4 API 설계 규칙
계층적 노출(90%는 `World` 헬퍼로, 10%만 하위 객체 직접) / 똑똑한 기본값(dt·솔버·머티리얼·카메라) / 렌더러 무관 코드 / 명시적 단위·좌표계(**z-up, SI**, 문서 최상단 고정) / 친절한 에러 메시지. **진입 예제는 15줄 이내 목표.**

## 7. 렌더링 계층 상세

- **공통 추상 `Renderer` ABC**: `render(snapshot) -> Frame|None`, `set_camera(camera)`. `Camera`/`Light`/`Material`은 두 렌더러가 공유하는 장면 기술. 사용자는 `mode=` 문자열로 선택.
- **실시간(RealtimeRenderer)**: `moderngl`(OpenGL 3.3+) + `pyglet`/`glfw`. 즉시 셰이딩, 그림자맵, PBR-lite, 그리드/축, 와이어프레임 토글. 궤도 카메라·줌/팬·일시정지·스텝. 헤드리스는 `EGL` 오프스크린 캡처.
- **고품질(HQRenderer)**: 순수 Python 소프트웨어 레이트레이서(NumPy 벡터화, 선택 JAX JIT). 직접광+그림자 → AO → 반사/굴절 → MSAA(`samples=`) → PBR. PNG → `imageio`/`ffmpeg` mp4. BVH 가속 + 벡터화로 프레임당 수 초 목표, `samples`·`max_bounces`로 화질/속도 조절.
- **교체 가능성 증명**: 동일 `SceneSnapshot`을 두 렌더러에 넣어 *동일 장면이 두 화질로* 나오는 회귀 테스트.

## 8. 로봇 팔 학습 — "쉽게 조작하고, 친절하게 본다" (응용)

- **친절한 RL 환경 API**: Gymnasium 100% 준수(SB3 등과 즉시 호환). `render_mode`로 headless(학습)·human(실시간 관찰)·rgb_array(영상) 전환 — 학습 속도와 관찰을 한 코드로.
- **인터랙티브 조작**: 관절 슬라이더 패널, 목표 마커 드래그, 그리퍼 토글, 일시정지/리셋, 속도 배속, 카메라 프리셋(정면/탑/그리퍼).
- **친절한 학습 관찰**: 실시간 대시보드(보상·성공률·에피소드 길이, TensorBoard 병행), 롤아웃 미리보기, 체크포인트→영상(`rec.run_policy` 한 줄), 실패 분석 뷰.
- **알고리즘·성능(v1 계승)**: reaching → pick-and-place(weld 추상화 위). 행동 목표관절각+PD → 토크. all-JAX(JIT+vmap) + SHAC, **학습 핫루프는 렌더러 OFF**. 보상은 단계형, 항을 하나씩 추가.

## 9. 단계별 로드맵 (라이브러리 우선, ★=v2 신규/재배치)

각 단계는 **검증 기준 통과**가 다음 단계의 전제다.

| Phase | 내용 | 검증/완료 기준 | 대략 |
|-------|------|----------------|------|
| 0 | Docker/CPU, 백엔드 스위치, 패키지 골격, 테스트·로깅 | `import forge3d` 동작, `pytest` 통과 | 3~5일 |
| 1 | 수학 + 2-DOF 동역학(정확성) | 에너지 보존, 손유도=RNEA | 1~2주 |
| 2 | n-DOF 일반화(RNEA→CRBA→순동역학→ABA) | 기준엔진(PyBullet) 가속도 대조 | 2~3주 |
| 3 ★ | SceneSnapshot + 실시간 렌더러(MVP) | 떨어지는 상자를 창에서 60FPS 관찰 | 1.5~2주 |
| 4 ★ | pygame식 공개 API(Facade) + Viewer | §6.1 예제가 그대로 동작 | 1주 |
| 5 | 충돌(프리미티브) + 연성 접촉(Phase A) | 마찰 임계각·반발 거동 이론 대조 | 2~3주 |
| 6 ★ | 고품질 레이트레이서(MVP→AO/AA) + Recorder | §6.2 bounce.mp4 산출 | 2~3주 |
| 7 | 로봇 모델 로더 + 그리퍼 + 인터랙티브 조작 UI | 슬라이더로 팔 조작, 목표 드래그 | 1.5~2주 |
| 8 | Gymnasium 환경(reaching) + render_mode 3종 | headless/human/rgb_array 전환 | 1주 |
| 9 | Reaching RL 완주 + 학습 대시보드 | 도달 성공률 곡선 상승, 실시간 관찰 | 2~3주 |
| 10 | 파지 weld 추상화 + pick-and-place 완주 | 물체 집어 옮기기 성공, 영상화 | 2~4주 |
| 11 | all-JAX 성능화(JIT+vmap) + SHAC | 처리량 수십~수백배↑ | 2~3주 |
| 12 (선택) | 실접촉 마찰 파지(Phase C), GJK/EPA, 도메인 랜덤화 | 미끄러짐 견디는 파지 | 가변 |

> **순서 핵심**: 실시간 렌더러(P3)와 pygame식 API(P4)를 **접촉·RL보다 먼저** 세운다. 이후 모든 단계를 "눈으로 보면서" 디버깅한다 — 물리 버그를 숫자가 아니라 화면으로 잡는 게 압도적으로 빠르다. 고품질 렌더러(P6)는 실시간이 선 뒤 추가. RL은 reaching(P9)을 먼저 닫고 파지(P10)로, 성능화(P11)는 reaching 학습을 본 뒤.

## 10. 기술 스택

물리/수치 NumPy↔JAX(함수형 코어)·SciPy·SymPy / 실시간 렌더 `moderngl`+`pyglet`/`glfw`·`imgui`(UI) / 고품질 렌더 자체 레이트레이서(NumPy/JAX)·`imageio`+`ffmpeg` / RL 자체 PPO·SHAC(JAX) 또는 SB3(torch) / 환경 Gymnasium / 검증 기준값 PyBullet·MuJoCo(validation 전용) / 테스트·로깅 pytest·TensorBoard / 컨테이너 Docker(CPU), 헤드리스 렌더 EGL/Xvfb.

## 11. 디렉터리 구조 (라이브러리 + 응용 분리)

```
forge3d-project/
├── Dockerfile / docker-compose.yml / pyproject.toml / CLAUDE.md
├── docs/                         # ROADMAP, WORKFLOW, PROGRESS, specs/
│
├── src/forge3d/                  # ── 라이브러리 (1급 산출물) ──
│   ├── __init__.py               # 공개 API: World, Body, Viewer, Recorder ...
│   ├── backend.py                # np ↔ jnp 스위치
│   ├── math/  dynamics/  collision/  contact/  model/
│   ├── sim/                      # world, simulator, state, snapshot
│   ├── render/                   # ── 렌더링 계층 ──
│   │   ├── base.py               #   Renderer ABC, Camera, Light, Material
│   │   ├── realtime/             #   moderngl 래스터화, shadow map
│   │   ├── hq/                   #   소프트웨어 레이트레이서, BVH, AO
│   │   └── snapshot.py           #   SceneSnapshot 계약
│   ├── viewer.py  recorder.py  robot.py
│
├── examples/                     # ── 라이브러리 사용 예제(고객 입장) ──
│   ├── 01_falling_box_realtime.py
│   ├── 02_bounce_hq_video.py
│   └── 03_robot_interactive.py
│
├── apps/robot_rl/                # ── 응용: 로봇 팔 학습 ──
│   ├── envs/  training/  configs/
│   └── dashboard.py
│
├── tests/                        # 보존법칙, IK, 백엔드 일치, 렌더러 회귀
├── validation/                   # pybullet_compare, mujoco_compare (엔진 미포함)
└── assets/                       # 팔 모델, 물체, 머티리얼
```

## 12. Docker 구성 핵심 (CPU 전용)

가벼운 CPU 베이스(`python:3.11-slim` 또는 `ubuntu:24.04`+python), 물리·학습에 GPU/CUDA 불필요. JAX·PyTorch는 CPU 휠. **그래픽**은 OpenGL 가능 여부를 먼저 확인하고, 헤드리스면 `EGL`/`Xvfb` 오프스크린. 코드·체크포인트·로그·렌더 산출물은 볼륨 마운트로 보존. 멀티코어용 `XLA_FLAGS`, `OMP_NUM_THREADS` 명시.

## 13. 검증 전략

- **물리**: 에너지·운동량 보존, 해석해/기준엔진 대조, 접촉(마찰 임계각).
- **백엔드 일치**: np 결과 ≈ jnp 결과(수치 허용오차).
- **렌더러 계약**: 동일 `SceneSnapshot`이 두 렌더러에서 일관된 장면 → 회귀 테스트(실시간=빠른 미리보기, HQ=골든 이미지 비교).
- **API 사용성(독립 검증)**: `examples/`가 *라이브러리 내부를 안 건드리고* 동작 = 추상화 살아있음의 증거. 진입 예제 15줄 이내.
- **RL**: reaching 성공률 곡선, pick-and-place 성공률.

## 14. 주요 위험과 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| 고품질+순수파이썬+CPU 렌더 속도 | 높음 | "고품질=오프라인" 재정의, BVH+벡터화, `samples`로 조절 |
| 그래픽 GPU 가용성 불확실 | 중 | OpenGL(그래픽용) 허용 해석, 안 되면 EGL/Xvfb 또는 소프트 래스터라이저 |
| CPU 단독 조작 RL 학습 시간 | 최대 | all-JAX JIT+vmap, SHAC, 파지 weld 추상화 |
| 물리↔렌더 결합도 상승 | 높음 | SceneSnapshot 계약 강제, **물리 코어는 render import 금지** |
| API 비대화 | 중 | 개념 5~6개 제한, 헬퍼+기본값, 예제 15줄 규칙 |
| 마찰 파지 난이도 | 높음 | weld 우회 → 마찰은 별도 마일스톤(P12) |
| 렌더링이 학습 핫루프 오염 | 중 | `render_mode=None` 기본, 스냅샷 생성 OFF 가능 |

## 15. 라이브러리 정체성

가칭 **forge3d**. 한 줄 소개: *"순수 Python 3D 물리엔진 — 게임처럼 쉽고, 시뮬레이션처럼 아름답게."* 두 얼굴(실시간 + 고품질)을 같은 API로.

## 16. 권장 진행 순서 요약

1. 환경·골격·백엔드 스위치 (P0)
2. 동역학 **정확성** 확보 (P1~2)
3. **실시간 렌더러 + pygame식 API** — 이후 전부 "보면서" 개발 (P3~4)
4. 접촉(연성) + **고품질 렌더러/Recorder** (P5~6)
5. 로봇 모델 + **인터랙티브 조작 UI** (P7)
6. Gymnasium 환경 + **Reaching RL 완주 + 대시보드** (P8~9)
7. 파지 추상화로 **pick-and-place 완주** (P10)
8. **all-JAX 성능화 + SHAC** (P11)
9. (선택) 실접촉 마찰 파지·일반화 (P12)
10. **현대 강체 물리** — 관성 텐서·PGS·OBB 일반·캡슐 (P13)

---

## 17. PyPI 실배포 로드맵 (P14~P24) ★★ NEW

> P0~P13 이 완료된 뒤, "장난감"을 "실제 라이브러리"로 만드는 단계다.
> 기준: Pymunk·Panda3D·Godot·MuJoCo·Unity 등 성숙한 엔진들의 공통 설계 언어를 따른다.

### 게임 엔진 설계 언어 참조

| 엔진 | 핵심 구조 | forge3d가 채택할 것 |
|------|-----------|-------------------|
| **Pymunk** (2D, Python) | Space→Body→Shape/Constraint; 콜백 핸들러; MkDocs | 조인트 API 패턴, 이벤트 콜백, 문서 구조 |
| **Godot 4** | SceneTree; 시그널/이벤트; HingeJoint3D·SliderJoint3D·Generic6DOF | 물리 조인트 종류, 레이어·마스크 충돌 필터링 |
| **Unity** | Rigidbody 컴포넌트; FixedJoint·HingeJoint·SpringJoint; OnCollision* 콜백 | 충돌 이벤트 콜백 패턴, 스프링 조인트 |
| **Bullet/PyBullet** | DiscreteWorld; Generic6DOFConstraint; CCD | 구속 솔버 알고리즘, CCD swept-sphere |
| **MuJoCo** | MJCF XML; Actuator/Tendon/Sensor; 연성 접촉 | URDF full 파싱, 액추에이터 추상화 |
| **Panda3D** | SceneGraph NodePath; Task 시스템; ReadTheDocs | 문서 스타일, 예제 구조 |

### P14~P24 한눈에

| Phase | 내용 | 완료 기준 | 우선순위 |
|-------|------|-----------|---------|
| **P14** | Git·CI/CD·PyPI 배포 인프라 | `pip install forge3d` TestPyPI 성공 | ★★★ (1위) |
| **P15** | MkDocs 문서 사이트 | ReadTheDocs/GH Pages 배포 | ★★★ |
| **P16** | 조인트·구속 시스템 | Hinge/Prismatic/Ball/Spring 동작 | ★★★ |
| **P17** | 충돌 이벤트 콜백 | on_collision 핸들러 게임 루프 통합 | ★★ |
| **P18** | 씬 직렬화 (저장·불러오기·리플레이) | JSON 저장 → 재현 일치 | ★★ |
| **P19** | 충돌 레이어·마스크 필터링 | 레이어별 충돌 ON/OFF | ★★ |
| **P20** | API 강화 및 오류 메시지 | 경계 검증·친절한 에러·`__all__` | ★★ |
| **P21** | 지형 (Heightfield) | 높이맵→지형 충돌 | ★ |
| **P22** | CCD + 복합 충돌 형상 | 고속 물체 터널링 없음 | ★ |
| **P23** | 성능 (BVH 광역단계 + 아일랜드 슬리핑) | 1000 bodies 10× 향상 | ★ |
| **P24** | v1.0.0 제품 릴리즈 | PyPI 공식 배포·벤치마크·CHANGELOG | ★★★ (최종) |
