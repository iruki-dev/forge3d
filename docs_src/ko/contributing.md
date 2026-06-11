# forge3d 기여 가이드

기여에 관심을 가져주셔서 감사합니다!

## 빠른 시작

```bash
git clone https://github.com/iruki-dev/forge3d
cd forge3d
pip install -e ".[dev]"
```

!!! note "패키지명 vs 임포트명"
    PyPI 배포명은 `pyforge3d`이지만, 코드에서는 `import forge3d`를 사용합니다.

## 워크플로우

1. 레포지토리를 포크하고 피처 브랜치 생성: `git checkout -b feat/my-feature`
2. 변경 사항과 해당 테스트 작성
3. 아래 체크를 모두 통과시키기
4. PR 열기 — 논리적 변경 단위당 하나의 PR

## 체크 사항 (모두 통과 필수)

```bash
ruff check . && ruff format --check .   # 린트 + 포맷
mypy src/                               # 타입 체킹
pytest tests/ -q                        # 테스트 스위트
```

## 규칙

### 물리 코드

- 모든 새 수식에는 해석해, 보존 법칙(에너지/운동량), 또는 PyBullet/MuJoCo 기준값(`validation/` 디렉터리)과 대조하는 단위 테스트가 필요합니다.
- 배열 in-place 변형 금지. `dataclasses.replace(body, vel=new_vel)` 패턴을 사용하세요.
- `ENGINE_BACKEND=numpy`와 `ENGINE_BACKEND=jax` 양쪽에서 올바르게 동작해야 합니다.

### 렌더러

- 물리 코어(`math/`, `dynamics/`, `collision/`, `contact/`, `model/`, `sim/`)는
  렌더러 코드를 **절대** 임포트하지 않습니다.
- 허용되는 유일한 다리는 `SceneSnapshot` (순수 데이터)입니다.

### 공개 API

- 새 공개 개념은 `src/forge3d/__init__.py`의 `__all__`에 항목을 추가해야 합니다.
- 새 공개 개념에는 `examples/`에 사용 예제(≤ 15줄)가 필요합니다.

### 금지 사항

- `src/forge3d/` 내 외부 물리 엔진(MuJoCo, PyBullet, Bullet 등) 사용.
  기준값 비교를 위해서만 `validation/`에서 허용됩니다.
- 물리 또는 학습 코드에 GPU/CUDA 의존성 추가.

## 코드 스타일

- 린트 및 포맷에는 [ruff](https://docs.astral.sh/ruff/) 사용 (최대 줄 길이 100).
- 모든 공개 함수에 타입 어노테이션 필수.
- 주석은 *이유*가 자명하지 않을 때만 추가.
- 간단한 getter/setter에는 docstring 불필요.

## 커밋 스타일

```
feat(collision): add sweep-and-prune broad-phase
fix(contact): clamp Baumgarte correction to avoid tunnelling
docs(readme): add App-style game loop example
test(physics): add conservation test for capsule-capsule
```

## 문의

GitHub에서 이슈를 열거나 Discussion을 시작하세요.
