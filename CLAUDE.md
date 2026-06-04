# CLAUDE.md — forge3d

> 매 세션 자동 로딩되는 파일이다. **항상 적용되는 규칙만** 둔다.
> 가끔만 필요한 절차·도메인 지식은 `docs/`(ROADMAP, SPEC)나 `.claude/skills/`로 옮긴다.
> 초안은 `/init`로 생성한 뒤 이 형식으로 다듬는다. git에 커밋해 공유한다.
> `[대괄호]`는 실제 값으로 채운다.

---

## 0. 절대 제약 — YOU MUST (이 프로젝트의 존재 이유)

- **IMPORTANT: 외부 물리엔진(MuJoCo, PyBullet, Bullet, ODE, DART, Isaac, Brax 등)을 엔진 코어에서 사용하지 않는다.** 동역학·접촉·충돌·구속·기구학은 **항상 직접 구현한 코드**가 푼다.
- 판단 기준 한 줄: **"동역학과 접촉을 누가 푸는가?" → 답은 언제나 우리 코드.** 막혔다고 외부 엔진 호출로 우회하지 않는다. 막히면 멈추고 보고한다.
- 외부 엔진(`pybullet`, `mujoco`)의 import는 **`validation/` 디렉터리에서 기준값 대조 전용으로만** 허용한다. `src/forge3d/` 안에서는 절대 금지.
- 써도 되는 패키지: NumPy, JAX, PyTorch, SciPy, SymPy, Gymnasium, optax/flax/equinox, stable-baselines3. (이들은 동역학을 *대신 풀지 않는다*.) **그래픽 출력용** `moderngl`/`pyglet`/`glfw`/`imgui`/`imageio`/`ffmpeg`도 허용 — 단, **물리·접촉 연산에는 절대 쓰지 않는다.**
- **GPU 제약 해석: "GPU 불가"는 물리·학습 연산 한정이다. 화면에 삼각형을 그리는 그래픽용 OpenGL은 허용**한다(없으면 실시간 렌더링 불가). 단 헤드리스에서 OpenGL 가속 여부가 불확실하면 가정하지 말고 EGL/Xvfb 가능성부터 확인하고 보고한다.

## 0c. 다중 언어 정책 (v2 신규) — YOU MUST

> v2(P25~)부터 적용. Python이 핵심이지만 성능 임계 경로는 다른 언어 허용.

- **Python**: 공개 API, 게임 로직, ML 연동. 모든 사용자 접점은 Python.
- **Rust (PyO3 + maturin)**: 물리 솔버 핫루프(GJK/EPA, BVH, PGS), SIMD 수학. `src/forge3d_core/` crate에만 존재. `src/forge3d/` 안에서 Rust 코드 직접 작성 금지.
- **GLSL**: 렌더링 셰이더 전용 (`src/forge3d/render/shaders/`). 물리 연산 불가.
- **C/C++ (CFFI/ctypes)**: 오디오 백엔드, imgui 바인딩 등 Rust로 불편한 C 라이브러리 바인딩에 한함. 물리 코어 금지.
- **폴백 규칙**: Rust 확장 빌드 실패 시 Python 구현으로 자동 폴백. Rust 없이도 전체 테스트 PASS 필수.
- **판단 기준**: "이 코드를 Rust로 쓰는 이유가 성능인가, 아니면 외부 엔진 의존인가?" → 성능이면 허용. 외부 물리 엔진 호출이면 금지.

## 0b. 라이브러리 ↔ 응용 분리 — YOU MUST

- 이 프로젝트는 **라이브러리(`src/forge3d/`, 1급 산출물)** 와 **응용(`apps/robot_rl/`)** 의 2층이다. 응용은 라이브러리를 **외부인처럼 import해서만** 쓴다. 응용을 짜려고 라이브러리 내부를 고쳐야 한다면 추상화가 실패한 것이니 멈추고 보고한다.
- **물리 코어(`math/ dynamics/ collision/ contact/ model/ sim/`)는 렌더러(`render/`)를 import하지 않는다.** 물리↔렌더의 유일한 연결은 `SceneSnapshot`(순수 데이터) 계약뿐이다. 물리 코드가 렌더러나 OpenGL을 알게 하지 않는다.
- **공개 API는 작게 유지**한다: 처음 만나는 개념 5~6개(`World/Body/Joint/Shape/Viewer/Recorder`) 이내, 진입 예제 15줄 이내, 똑똑한 기본값, z-up·SI 단위. 새 공개 개념을 늘리기 전에 헬퍼·기본값으로 해결되는지 먼저 본다.

## 1. 작업 방식 — 기획안(SPEC) 기반

- **전체 순서의 기준은 `docs/ROADMAP.md`(P0~P24) 및 `docs/ROADMAP_v2.md`(P25~P35)**, 개별 작업의 기준은 `docs/specs/`의 해당 Phase SPEC이다. 이 셋이 source of truth다.
- 작업 전 해당 SPEC을 읽고, **거기 정의된 범위·파일·완료 조건만** 다룬다. SPEC에 없는 변경은 하지 않는다.
- **Phase 게이트: 이전 Phase의 검증 기준을 통과하기 전에는 다음 Phase로 넘어가지 않는다.** (ROADMAP의 검증 기준 표 참조)
- 여러 파일을 건드리거나 접근이 불확실한 작업은 **먼저 plan mode**로 탐색·계획하고, SPEC과 대조해 승인받은 뒤 구현한다.
- SPEC의 task를 **순서대로, 한 번에 하나씩** 구현한다. task가 끝나면 SPEC 체크박스를 갱신하고 `docs/PROGRESS.md`에 기록한다.
- **SPEC과 현실이 어긋나면 임의로 우회하지 말고 멈추고 보고한다. 깨진 계획을 땜질하지 않는다.** 필요하면 실패 지점부터 다시 계획한다.

## 2. 엔진 작성 규칙 — 함수형 코어 (np ↔ jnp 호환의 전제)

- **in-place 변형 금지.** 상태는 입력 → 출력으로 전달한다. 배열은 불변으로 다룬다(JAX `arr.at[i].set(v)` 패턴, NumPy도 동일 추상화로 래핑).
- **난수는 명시적 키로 관리**한다(JAX PRNG 호환). 전역 난수 상태 사용 금지.
- 분기·루프는 가능하면 벡터화한다. JIT 대상 함수 안에서는 `jax.lax` 제어흐름을 쓴다.
- **모든 엔진 코드는 `ENGINE_BACKEND=numpy`와 `=jax`에서 동일하게 동작해야 한다.** 한쪽에서만 되는 코드를 작성하지 않는다.

## 3. 백엔드 경계

- **성능 경로(권장)는 all-JAX로 통일**: jnp 엔진 + flax/equinox 정책 + optax + 전체 루프 JIT + `vmap` 다중환경.
- **torch는 실험·프로토타입(SB3) 전용.**
- **학습 핫루프에서 JAX 환경 + torch 정책 혼합 금지** (매 스텝 host↔device 동기화로 JIT 이점 소멸). 경계 변환이 꼭 필요하면 DLPack, 단 프로토타이핑에 한함.

## 4. 검증 — YOU MUST

- **"완료/통과/동작함"이라고 말하기 전에 반드시 실제로 실행하고 증거(명령어 + 출력)를 보여준다.** 실행하지 않은 채 통과를 주장하지 않는다.
- 변경 후 순서: `[pytest]` → `[ruff check]` → `[mypy]`. 셋 다 통과해야 완료.
- 물리 코드의 정확성 게이트(해당 시 반드시 추가):
  - **보존 법칙**: 무토크·무감쇠에서 에너지 보존, 외력 없을 때 운동량 보존.
  - **해석해 대조**: 단진자/이중진자 닫힌 해, RNEA vs 손유도(SymPy).
  - **기준 엔진 대조**: `validation/`에서 동일 입력을 PyBullet/MuJoCo와 허용오차 내 비교.
  - **백엔드 일치**: 같은 입력에 대해 np 결과와 jnp 결과가 수치 허용오차 내 일치.
- 렌더링·API 게이트(해당 시):
  - **렌더러 계약**: 동일 `SceneSnapshot`이 두 렌더러에서 일관된 장면(실시간=빠른 미리보기, HQ=골든 이미지 비교) — 회귀 테스트.
  - **API 사용성**: `examples/`의 예제가 *라이브러리 내부를 안 건드리고* 동작(15줄 이내). 이게 추상화가 살아있다는 증거다.

## 5. 명령어 (Claude가 추측할 수 없는 것)

- 백엔드 스위치: `ENGINE_BACKEND=numpy` 또는 `ENGINE_BACKEND=jax` (기본 numpy).
- Rust 코어 ON/OFF: `USE_RUST_CORE=1` 또는 `USE_RUST_CORE=0` (기본 자동 감지).
- 공개 API 스모크: `python -c "import forge3d"` 가 동작해야 한다.
- 테스트(단일 우선, 성능 위해 전체 스위트 지양): `[pytest tests/test_xxx.py -q]`
- 린트/포맷: `[ruff check . && ruff format --check .]`
- 타입: `[mypy src/]`
- **Rust 빌드** (P25~): `maturin develop` (개발), `maturin build --release` (배포)
- **Rust 테스트** (P25~): `cargo test --workspace`
- **Rust 벤치** (P25~): `cargo bench --workspace`
- 컨테이너: `[docker compose run --rm dev pytest -q]`
- CPU 멀티코어: `XLA_FLAGS`, `OMP_NUM_THREADS` 등 스레드 환경변수를 명시적으로 설정.

## 6. 금지 / 사용자 확인 필수

- 확인 없이 금지: 파일·데이터 삭제, `git push --force`, 시크릿/`.env` 커밋, Docker 베이스 이미지 교체.
- 코드·체크포인트·로그는 **볼륨 마운트**로 컨테이너 밖에 보존한다. 컨테이너 내부에만 남기지 않는다.
- **물리·학습 연산에 GPU/CUDA 의존성 추가 금지**(이 환경은 CPU 전용). JAX·PyTorch는 CPU 휠만 설치. (그래픽용 OpenGL은 §0의 해석에 따라 허용 — 단 헤드리스 가용성은 확인 후 사용.)

## 7. 저장소 규칙

- 브랜치: `[phase-N/<요약>]` / 커밋: `[type(scope): 요약]` / 한 PR = 한 Phase 또는 그 하위 task 묶음.
