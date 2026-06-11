# Skill: validate

forge3d의 검증 기준. "완료"를 선언하기 전에 반드시 통과해야 하는 게이트.

## 기본 3-gate (모든 변경에 적용)

```bash
python -m pytest tests/ \
  --ignore=tests/test_p9_training.py \
  --ignore=tests/test_pick_place.py \
  --ignore=tests/test_reach_env.py \
  -q --tb=short

ruff check src/ apps/ tests/ demos/
mypy src/
```

> `test_p9_training`, `test_pick_place`, `test_reach_env`는 `apps/robot_rl/`
> 모듈이 없어 항상 스킵. 이는 기존 상태로 실패가 아님.

## 물리 코드 정확성 게이트

물리 알고리즘(dynamics, collision, contact, constraints)을 수정했다면:

### 보존 법칙
```bash
python -m pytest tests/test_conservation.py -v
# 무토크·무감쇠에서 에너지 보존, 외력 없을 때 운동량 보존
```

### 해석해 대조
```bash
python -m pytest tests/test_rnea_2dof.py tests/test_crba.py tests/test_aba.py -v
# RNEA/CRBA/ABA vs SymPy 손유도 결과
```

### 기준 엔진 대조
```bash
# validation/ 폴더에서 PyBullet/MuJoCo와 허용오차 내 비교
python validation/compare_pybullet.py   # 있을 경우
```

### 백엔드 일치
```bash
ENGINE_BACKEND=numpy python -m pytest tests/test_snapshot.py -q
ENGINE_BACKEND=jax   python -m pytest tests/test_snapshot.py -q
```

## 렌더링 변경 게이트

```bash
python -m pytest tests/test_p26_deferred_render.py -q
python -m pytest tests/test_p34_wgpu.py -q
# 골든 이미지 비교: SSIM ≥ 0.98
# 동일 SceneSnapshot → 두 렌더러에서 일관된 장면
```

## API 변경 게이트

```bash
python -m pytest tests/test_api_usability.py tests/test_snapshot.py -v
# - 공개 API 5~6개 이내
# - examples/01_falling_box_realtime.py 가 내부 import 없이 15줄 이내로 실행
# - forge3d.sim.world 가 moderngl/glfw/pyglet를 import하지 않음
```

## 문서 변경 후

```bash
mkdocs build
# 오류 없이 빌드, site/ 에 새 페이지 존재 확인
```

## 현재 기준선 (2026-06-11)

| 항목 | 값 |
|------|-----|
| 통과 테스트 | 528 (robot_rl 제외) |
| ruff | 0 errors (I001 import-sort만 apps/ 일부) |
| mypy | src/ 통과 |
| 버전 | 2.1.0 |
