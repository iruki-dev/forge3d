# pyforge3d 데모 프로그램

---

## 데모 (신규) — Cascade Gauntlet 종합 기능 쇼케이스

pyforge3d의 주요 기능을 한 번에 보여주는 3장면 HQ 렌더링 데모.

```bash
python demos/cascade_gauntlet.py                   # 기본 (480×320, spp=1)
python demos/cascade_gauntlet.py --hq              # 640×400, spp=2
python demos/cascade_gauntlet.py --ultra           # 800×500, spp=4
python demos/cascade_gauntlet.py --scene 1        # 특정 장면만 (1/2/3)
python demos/cascade_gauntlet.py -o my_demo.mp4   # 출력 파일명 지정
```

| 장면 | 내용 | 주요 기능 |
|------|------|-----------|
| 핀볼 아레나 | spring 범퍼, hinge 패들, 트리거존 득점 | spring/hinge joint, CollisionLayer, TriggerZone, on_collision_begin, CollisionHandler |
| 철거의 탑 | 진자 쇄도 공 + 6층 타워 붕괴 | distance joint, weld/release, capsule chain, World.save/load, is_sleeping |
| 지형 슬라이드 | heightfield 지형 위 PBR 구 슬라이드 | add_terrain, PBR Material, StateRecorder, apply_torque, teleport, on_collision_stay |

결과: `cascade_gauntlet.mp4` (약 24초, 24fps)

---

## 이전 데모 (archive/demos/ 로 이동됨)

세 가지 데모를 바로 실행할 수 있습니다.

---

## 데모 1 — 물리 엔진 대규모 쇼케이스

AABB 브로드페이즈 + 벡터화 충돌 감지로 수십~수백 개 물체의 물리 연산을 HQ 영상으로 기록합니다.

```bash
# 프로젝트 루트에서
python demos/physics_showcase.py
```

| 장면 | 내용 | 물체 수 |
|------|------|---------|
| 무지개 구 폭포 | 56개 구 (7색 × 8개), 반발계수별 튀어오르는 높이 비교 | 56 |
| 피라미드 대붕괴 | 55개 박스 5층 피라미드 + 볼링공 충돌 붕괴 | 56 |
| 혼돈의 아레나 | 벽 있는 경기장에 구 25 + 박스 25 무작위 낙하 | 50 |

```bash
python demos/physics_showcase.py --hq              # 고품질 (640×400, samples=2)
python demos/physics_showcase.py --ultra           # 최고 품질 (800×500, samples=4)
python demos/physics_showcase.py --scene 2         # 특정 장면만 (1/2/3)
python demos/physics_showcase.py --output my.mp4  # 출력 파일명 지정
```

결과: `physics_showcase.mp4` (약 21초, 24fps)

---

## 데모 2 — 강화학습 훈련 + 실시간 시각화

> **필요**: `pip install stable-baselines3`

### 실시간 3D 뷰어 (권장 ✨)

```bash
python demos/training_watch.py --live                    # 기본 (1280×720)
python demos/training_watch.py --live --steps 50000      # 빠른 데모
python demos/training_watch.py --live --width 1920 --height 1080
```

pygame 창이 열리고 로봇 팔이 학습하는 모습을 실시간으로 볼 수 있습니다.

| 조작 | 동작 |
|------|------|
| 좌클릭 드래그 | 카메라 orbit (회전) |
| 우클릭 드래그 | 카메라 pan (이동) |
| 마우스 휠 | zoom (거리) |
| `R` | 카메라 초기화 |
| `SPACE` | 일시정지 / 재개 |
| `ESC` | 학습 중단 + 종료 |

### 텍스트 모드

```bash
python demos/training_watch.py --steps 50000   # 터미널 진행 표시 (~3-5분)
python demos/training_watch.py                 # 전체 학습 (200k 스텝)
```

- 25%, 50%, 75% 단계마다 롤아웃 영상 클립을 저장합니다
- 완료 후 전체 진행을 보여주는 비교 영상을 만듭니다

```bash
# 이미 학습된 모델이 있으면 영상 생성만 (학습 생략)
python demos/training_watch.py --use-existing
```

결과: `training_output/demo_run/training_progress.mp4`

---

## 데모 3 — 인터랙티브 로봇 팔 테스트

> **필요**: `pip install stable-baselines3` + 학습된 모델

```bash
python demos/interactive_robot.py
```

학습된 모델을 불러와 터미널에서 목표 위치를 직접 지정하거나 랜덤으로 테스트합니다.

```
╔══════════════════════════════════════════════════════╗
║    forge3d — 인터랙티브 로봇 팔 테스터  🦾           ║
╠══════════════════════════════════════════════════════╣
║  명령어:                                             ║
║   Enter / n   → 새 랜덤 목표                        ║
║   x y z       → 직접 목표 지정  (예: 0.3 0.2 0.5)  ║
║   r           → 10회 성공률 측정                    ║
║   q           → 종료                                ║
╚══════════════════════════════════════════════════════╝
```

모델 없으면 자동 학습 후 시작:
```bash
python demos/interactive_robot.py --quick-train
```

각 시도마다 영상 클립이 `demo_clips/attempt_NNN.mp4`에 저장됩니다.

---

## 권장 실행 순서

```bash
# 1. 물리 엔진 동작 확인 (stable-baselines3 불필요)
python demos/physics_showcase.py

# 2. 학습 진행 관찰 (stable-baselines3 필요)
python demos/training_watch.py --steps 50000

# 3. 직접 테스트
python demos/interactive_robot.py
```
