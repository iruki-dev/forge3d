# pyforge3d 라이브러리 개선 노트

> forge_racer.py 제작 과정에서 발견한 부족한 점 및 추가하면 좋을 기능 목록.
> 우선순위 순 정렬.

---

## 🔴 High Priority — 게임 제작에 직접 영향

### 1. 차량 물리 (Vehicle Physics) 부재

**현황:** 차량을 만들려면 box 차체 + 구 바퀴(weld) + 수동 힘/토크 적용으로 흉내내야 함.  
**문제:**
- 진짜 서스펜션(raycast suspension) 없음 → 요철에서 차가 튀거나 뒤집힘
- 타이어 마찰 모델 없음 → 옆미끄럼을 `apply_impulse`로 직접 감쇠해야 함
- 조향 각도를 물리적으로 표현할 방법 없음 (앞바퀴 hinge 각도 제어 불가)

**제안:**
```python
# 희망 API
car = world.add_vehicle(
    chassis_size=(2.2, 1.1, 0.55),
    mass=1200.0,
    wheels=[
        VehicleWheel(offset=(+0.9, +0.6, -0.3), radius=0.32, drive=True),
        ...
    ],
    suspension_stiffness=40000,
    suspension_damping=4000,
)
car.set_throttle(1.0)   # 0~1
car.set_brake(0.5)
car.set_steering(0.3)   # -1 ~ +1 (rad)
```

---

### 2. FollowCamera가 월드 프레임 오프셋만 지원

**현황:** `FollowCamera(body, offset=(0, -8, 4))` — offset이 항상 월드 좌표계 고정.  
**문제:** 차가 방향을 바꾸면 카메라가 차 뒤를 따라가지 않고 항상 남쪽에서 봄.  
**현재 우회:** 매 프레임 `quat_to_rot(car.orientation)` 으로 forward 방향을 계산해 수동으로 azimuth 업데이트.

**제안:**
```python
cam = f3d.FollowCamera(
    body=car,
    offset=(0, -8, 4),     # 로컬 프레임 오프셋
    frame="local",          # 새 파라미터: "world"(기존) | "local"(차 로컬)
    alpha=0.10,
)
```

---

### 3. `Viewer`의 Input이 pygame과 분리 불가

**현황:** `Input`/`Key`는 `Viewer` 내부 이벤트 루프에만 연결됨.  
**문제:** pygame을 직접 쓰는 게임(WindowRenderer 방식)에서는 `f3d.Input`을 쓸 수 없어 `pygame.key.get_pressed()`로 직접 입력 처리해야 함.

**제안:** `_InputBuilder`를 공개 API로 노출하거나, pygame 이벤트를 `InputBuilder`에 주입할 수 있는 어댑터 제공.
```python
inp_builder = f3d.InputBuilder()
for event in pygame.event.get():
    inp_builder.feed_pygame_event(event)
inp = inp_builder.build()
inp_builder.end_frame()
```

---

### 4. HUD/텍스트 렌더링이 Viewer에 없음

**현황:** `Viewer.draw()` 는 3D 씬만 렌더링. 점수, 속도, 타이머 등 텍스트 표시 불가.  
**현재 우회:** `apps/game/renderer.py`의 `WindowRenderer.render_hud()` — pygame font → OpenGL texture quad.

**제안:**
```python
# 희망 API
viewer.draw_text("Speed: 65 km/h", x=10, y=10, color=(1,1,1), size=20)
viewer.draw_text("LAP 2/3", x=640, y=20, anchor="center", size=28)
```

---

## 🟡 Medium Priority — 편의성/표현력

### 5. `world.add_box()` 에 `static=True` 옵션 없음

**현황:** 정적 박스를 추가하려면 `world._physics.add_static_box()`(내부 API)를 직접 호출해야 함.  
`world.add_box()`는 항상 동적 body를 생성.

**제안:**
```python
world.add_box(size=(...), static=True)   # add_sphere처럼 static 파라미터 추가
```

---

### 6. `add_static_box`가 `world._bodies`에 자동 등록 안 됨

**현황:** `world._physics.add_static_box()` 호출 후 `world._bodies`에 수동 등록하지 않으면 `world.bodies`, 충돌 이벤트, `world.save()` 에서 누락됨.  
**현재 우회:** 게임에서 `_add_static()` 헬퍼 함수로 수동 등록.

---

### 7. 물리 body의 마찰/반발 계수를 생성 후 변경 불가

**현황:** `restitution`, `friction`은 생성 시에만 설정 가능. 런타임에 슬라이딩 표면을 얼음으로 바꾸거나 부스트 시 마찰 변경 불가.

**제안:**
```python
body.friction     = 0.05   # 새 setter
body.restitution  = 0.8
```

---

### 8. `World.save()`가 조인트(Joint)를 직렬화하지 않음

**현황:** `world.save()` / `World.load()` 는 body 위치/속도만 저장. spring, hinge, distance joint는 저장되지 않아 로드 후 장애물이 사라짐.

**제안:** `_constraints` 리스트도 JSON에 포함.
```json
{
  "constraints": [
    {"type": "spring", "body_a": 3, "body_b": 5, "stiffness": 500, ...}
  ]
}
```

---

### 9. 레이캐스트(Raycast) API 없음

**현황:** 지면 감지(차가 공중에 떠 있는지), 시야 검사, 픽업 감지 등에 레이캐스트가 필요하지만 API 없음.  
**현재 우회:** 위치 기반 거리 체크로 대략적으로 처리.

**제안:**
```python
hit = world.raycast(origin=(0,0,5), direction=(0,0,-1), max_dist=10)
if hit:
    print(hit.body, hit.point, hit.normal, hit.distance)
```

---

### 10. Body의 angular_damping / linear_damping 속성 없음

**현황:** 각속도 감쇠를 `set_angular_velocity(omega * 0.8)` 로 매 프레임 직접 구현해야 함. 매 스텝마다 명시적 호출 필요.

**제안:**
```python
body.linear_damping  = 0.02   # 선속도 감쇠 (s^-1)
body.angular_damping = 0.10   # 각속도 감쇠
```
설정하면 `world.step()` 내부에서 자동 적용.

---

## 🟢 Low Priority — 퀄리티/편의

### 11. `FollowCamera.alpha`가 프레임률 종속

**현황:** `self._eye += alpha * (desired - self._eye)` — alpha가 per-frame 계수라 FPS가 다르면 스무딩이 달라짐.

**제안:**
```python
# 지수 이동 평균의 dt 보정
self._eye += (1 - math.exp(-alpha * dt)) * (desired - self._eye)
```
또는 `alpha` 대신 `smoothing_time` (초) 단위 파라미터.

---

### 12. `CollisionLayer.NONE = 0` 이 기본값(DEFAULT=1)과 혼동될 수 있음

**현황:** body 생성 직후 layer가 DEFAULT(0x0001). `NONE=0`으로 설정해야 충돌 비활성화 — 이름은 직관적이지만 AND 연산 결과가 0이므로 기존 레이어 mask 체크가 실패해 의도한 대로 동작함. 다만 NONE 레이어를 가진 body에 대해 엔진이 보장을 명시하지 않아 코드 이해가 어려움.

**제안:** 문서/주석에 `NONE = 0` 의 의미와 동작 보장을 명확히 명시.

---

### 13. `TriggerZone`을 `world.snapshot()`에서 시각화할 수 없음

**현황:** 트리거 존은 physics body가 아니라서 렌더러에 표시되지 않음. 개발 중 어디에 있는지 확인하기 어려움.

**제안:** debug 렌더링 옵션:
```python
viewer = f3d.Viewer(world, debug_triggers=True)  # 트리거 존을 반투명 박스로 표시
```

---

### 14. `world.ignore_collision()` 이후 이벤트 dispatch에서도 제외되어야 함

**현황:** `world.ignore_collision(a, b)` 는 physics contact는 무시하지만, 내부적으로 이미 `_dispatch_events`의 필터링 로직에도 추가됨. 그러나 충돌 핸들러를 등록하면 여전히 콜백이 발생할 수 있는지 명확하지 않음.

**제안:** 문서에 "ignore_collision은 physics contact와 event dispatch 모두 비활성화한다" 고 명시.

---

---

## forge_drive.py 제작 중 추가 발견

### 15. ⚠️ 실시간 성능 — 순수 Python 물리 루프의 한계 (Critical)

**관찰:** 809 bodies → world.step() 1회에 **2.27초** 소요. 60 FPS 게임에서 허용 한계는 16ms.  
**원인:** collision detection 이 O(n²) 또는 O(n) broad-phase이더라도 AABB pair 체크가 Python 루프로 구현됨. 동적 body가 22개뿐이어도 정적 body 수백 개와의 체크가 반복됨.

**측정:**
- 809 bodies (동적 22 + 정적 787): 2.27s/step ← **오픈 월드 게임 시도 시 발생**
- cascade_gauntlet scene3 (~10 동적 + 10 정적 = ~20 bodies): ~0.06s/step

**Body 수 목표 (60 FPS 게임):** ≤200 total (동적 ≤30)

**해결 방향:**
1. 자연 오브젝트(나무, 바위, 건물)를 모두 정적(static) body로 생성
2. `add_box(static=True)` 지원 부재 → `_physics.add_static_box()` 직접 호출 필요 (비공개 API)
3. **JAX 백엔드 전환** (`ENGINE_BACKEND=jax`) 으로 JIT 이득 기대 가능하나, 게임 루프 내 Python 분기가 많아 제한적

**제안 우선순위:**
```python
# (A) NumPy 물리 루프를 Numba/JAX로 이식 — collision broad-phase 핵심
# (B) 공개 API로 static=True 지원 통일 (add_box, add_capsule)
# (C) collision_layer=NONE body를 broad-phase에서 즉시 제외 (현재 미확인)
```

---

### 16. `weld` 제약이 자식 body의 **상대 회전**을 저장하지 않음

**현황:** `world.weld(child, parent)` 는 위치 오프셋만 저장. 자식은 항상 부모와 **같은 orientation**을 가짐.  
`_apply_welds` 에서: `update_body_pose(body_id, new_pos, anchor.quat)`  
**문제:** 윈드밀 날개나 기울어진 지붕 등 **각도가 다른 부품**을 weld할 수 없음. 모든 weld 부품이 부모와 동일 방향으로 정렬됨.

**제안:**
```python
# weld 시 상대 quaternion도 저장
def weld(self, body, anchor, local_offset=None, local_rotation=None):
    ...
    # _apply_welds에서:
    new_quat = quat_multiply(anchor.quat, stored_rel_quat)
    update_body_pose(body_id, new_pos, new_quat)
```

---

### 16. `add_box()` / `add_capsule()` 에 `static=True` 없음

**현황:** `add_sphere(static=True)` 는 지원하나, `add_box`와 `add_capsule`은 지원 안 함.  
**영향:** 나무 기둥(capsule)을 정적으로 만들려면 `_physics.add_static_box()`를 쓰거나, 무거운 mass + 강한 마찰로 흉내내야 함.

---

### 17. Heightfield가 SceneSnapshot에 포함되지 않음 — **렌더링 불가**

**현황:** `world.add_terrain()` 은 물리 충돌용 heightfield를 추가하지만, `snapshot()` 에는 포함되지 않아 화면에 보이지 않음.  
**영향:** 오픈 월드 게임에서 지형 시각화를 위해 수백 개의 box를 수동으로 배치해야 함. 지형 위 box 배치 + heightfield 충돌을 이중으로 구현해야 하는 불편함.

**제안:**
```python
# SceneSnapshot에 TerrainSnapshot 추가
@dataclass
class TerrainSnapshot:
    heights: np.ndarray    # (rows, cols)
    cell_size: float
    origin: np.ndarray     # (3,)
    material_id: str

@dataclass  
class SceneSnapshot:
    bodies: list[BodySnapshot]
    terrains: list[TerrainSnapshot] = field(default_factory=list)  # 새 필드
    ...
```
렌더러는 terrain을 삼각형 메시로 변환해 렌더링.

---

### 18. `add_joint("hinge", body, None)` — body_b=None 시 body_a가 정적이면 모터 동작 안 함

**현황:** 풍력 발전기 hub를 static box로 만들고 hinge motor를 적용하면 모터가 동작하지 않음 (static body는 힘에 반응하지 않음).  
**해결책:** hub를 dynamic body로 만들고, hinge 제약으로 위치를 고정하면 됨 — 하지만 직관적이지 않은 패턴.

---

## 요약 테이블

| # | 항목 | 우선순위 | 난이도 |
|---|------|----------|--------|
| 1 | 차량 물리 (Vehicle Physics) | 🔴 High | 매우 높음 |
| 2 | FollowCamera 로컬 프레임 | 🔴 High | 낮음 |
| 3 | Input ↔ pygame 분리 | 🔴 High | 중간 |
| 4 | HUD 텍스트 렌더링 | 🔴 High | 중간 |
| 5 | `add_box(static=True)` | 🟡 Med | 낮음 |
| 6 | `add_static_box` auto-register | 🟡 Med | 낮음 |
| 7 | 런타임 마찰/반발 변경 | 🟡 Med | 낮음 |
| 8 | `save()`에 조인트 포함 | 🟡 Med | 중간 |
| 9 | 레이캐스트 API | 🟡 Med | 높음 |
| 10 | linear/angular_damping | 🟡 Med | 낮음 |
| 11 | FollowCamera dt 보정 | 🟢 Low | 낮음 |
| 12 | NONE 레이어 문서 | 🟢 Low | 낮음 |
| 13 | TriggerZone 시각화 | 🟢 Low | 중간 |
| 14 | ignore_collision 동작 명시 | 🟢 Low | 낮음 |
| 15 | weld 상대 회전 저장 | 🟡 Med | 중간 |
| 16 | add_box/capsule static=True | 🟡 Med | 낮음 |
| 17 | Heightfield 렌더링 지원 | 🔴 High | 높음 |
| 18 | hinge+static body 조합 경고 | 🟢 Low | 낮음 |
