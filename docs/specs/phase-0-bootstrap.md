# SPEC: Phase 0 — 환경 골격 & 백엔드 스위치

> 파생: ROADMAP §9 P0. 검증 게이트: `import forge3d` 동작 + np/jnp 둘 다 `pytest` 통과.

## 1. 목표 (한 문장)
Docker(CPU 전용) 위에서 `src/forge3d`가 NumPy/JAX 양쪽 백엔드로 import·테스트되는 **최소 실행 골격**을 세운다.

## 2. 범위
- **포함**: 리포 구조(라이브러리 `src/forge3d/` + 응용 `apps/robot_rl/` + `examples/` 분리), `pyproject.toml`, Dockerfile/compose, `backend.py` 스위치, **공개 API 패키지 골격**(`__init__.py`가 import 가능), 테스트·로깅 골격, lint/type 설정, CI 또는 hook용 명령.
- **제외**: 실제 동역학·수학 구현(P1), 렌더러 실제 구현(P3/P6), API 실내용(P4), RL(P8+). 이 단계엔 빈 패키지·스텁만.

## 3. 영향 파일 / 인터페이스
- `pyproject.toml` — 의존성(numpy, jax[cpu], scipy, sympy, pytest, ruff, mypy), 패키지 메타(`src/forge3d` 패키징).
- `Dockerfile`, `docker-compose.yml` — CPU 베이스, 볼륨 마운트, `XLA_FLAGS`/`OMP_NUM_THREADS`.
- `src/forge3d/__init__.py` — 공개 API 자리표시(향후 `World/Body/Viewer/Recorder` 노출). 지금은 import만 성공하면 됨.
- `src/forge3d/backend.py` — `xp`, `jit`, `vmap`, 불변 갱신 헬퍼(`set_at(arr, idx, val)`), PRNG 키 헬퍼.
- 빈 서브패키지 골격: `math/ dynamics/ collision/ contact/ model/ sim/ render/{base,realtime,hq,snapshot}` (각 `__init__.py`만).
- `tests/test_backend.py`, `tests/test_import.py`(=`import forge3d` 스모크), `tests/conftest.py`(두 백엔드 매개변수화 fixture).
- `.claude/settings.json`(선택) — 편집 후 ruff hook, **`src/forge3d/` 내 외부 물리엔진 import 차단 hook, 물리 코어 패키지의 `render` import 차단 hook**.

## 4. 구현 작업
- [x] **T1.** 리포 디렉터리 구조 생성(ROADMAP §11) + `pyproject.toml` 의존성·도구 설정(ruff, mypy).
- [x] **T2.** `backend.py`: `ENGINE_BACKEND` 스위치, `xp/jit/vmap`, NumPy `vmap` 폴백, `set_at`·PRNG 키 추상화. — 완료 조건: 두 백엔드에서 동일 함수 호출이 동작.
- [x] **T3.** Dockerfile/compose: CPU 휠 설치, 코드·로그·체크포인트 볼륨 마운트, 스레드 환경변수. — 완료 조건: `docker compose run --rm dev pytest -q` 동작.
- [x] **T4.** `conftest.py`로 `numpy`/`jax` 매개변수화하는 `xp` fixture + `tests/test_backend.py` 스모크 테스트.
- [x] **T5.** 로깅 골격(TensorBoard writer 래퍼 스텁) + README의 실행/검증 명령.

## 5. 엣지 케이스 / 제약
- JAX는 **CPU 빌드만**(`jax[cpu]`). GPU/CUDA 의존성 금지.
- NumPy 폴백에서 `jit`은 no-op, `vmap`은 순회/`np.vectorize` 기반이어야 함.
- 컨테이너 내부에만 산출물 남기지 않기(볼륨 필수).

## 6. 검증 (게이트)
- `ENGINE_BACKEND=numpy pytest -q` 통과 **그리고** `ENGINE_BACKEND=jax pytest -q` 통과.
- `python -c "import forge3d"`가 두 백엔드에서 성공.
- `ruff check . && mypy src/` 통과.
- **통과 기준**: 위 4개 명령 모두 exit 0, 출력 첨부.

## 7. 완료 후 리뷰
- 서브에이전트: "구조가 ROADMAP §11과 일치하는가? backend 추상화가 P1에서 in-place 변형을 강제로 피하게 하는가?"
