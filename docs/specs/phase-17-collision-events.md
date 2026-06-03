# Phase 17 SPEC — 충돌 이벤트 콜백

> Source of truth for P17. Only changes described here are permitted.

## 목표

게임·시뮬레이션의 핵심 로직 트리거: **충돌 이벤트**를 추가한다.  
물체가 만나는 순간·접촉 중·떨어지는 순간을 콜백으로 처리할 수 있다.

### 참조
- **Unity**: `OnCollisionEnter(Collision)`, `OnCollisionStay`, `OnCollisionExit`; `OnTriggerEnter`
- **Godot**: `body_entered`, `body_exited` 시그널; `area_entered`
- **Pymunk**: `Space.add_collision_handler(typeA, typeB)` → begin/pre_solve/post_solve/separate
- **Bullet**: `btCollisionWorld::ContactResultCallback`

---

## 범위

| # | 내용 | 파일 |
|---|------|------|
| T1 | `CollisionEvent` 데이터클래스 | `src/forge3d/events.py` (신규) |
| T2 | `CollisionHandler` — body 쌍별 콜백 등록 | `src/forge3d/events.py` |
| T3 | `PhysicsWorld._dispatch_events()` — contact 쌍 비교 후 begin/stay/end 판정 | `src/forge3d/sim/world.py` |
| T4 | `World.on_collision_begin(fn)` / `on_collision_end(fn)` / `on_collision_stay(fn)` | `src/forge3d/facade.py` |
| T5 | `World.add_collision_handler(body_a, body_b, handler)` — 쌍별 세분화 | `src/forge3d/facade.py` |
| T6 | 트리거 바디 (`add_trigger_zone`) — 충돌하지 않고 이벤트만 발생 | `src/forge3d/facade.py` |
| T7 | 테스트 5종 | `tests/test_p17_events.py` (신규) |
| T8 | 예제: 점수 카운터, 발판 파괴 | `examples/06_events.py` |

---

## `CollisionEvent` 데이터클래스

```python
@dataclass
class CollisionEvent:
    body_a: Body
    body_b: Body
    contact_point: np.ndarray   # (3,) world-frame
    normal: np.ndarray          # (3,) pointing body_a → body_b
    impulse: float              # 충격량 크기 (N·s)
    relative_speed: float       # 접촉 직전 법선 방향 상대속도 (m/s)
```

---

## 이벤트 라이프사이클

```
스텝 N-1: (A, B) 충돌 없음
스텝 N:   (A, B) 충돌 시작 → on_collision_begin 호출
스텝 N+1: (A, B) 아직 충돌 → on_collision_stay 호출
스텝 N+2: (A, B) 분리     → on_collision_end 호출
```

내부 구현: `_prev_contact_pairs: set[frozenset[int]]` vs `_curr_contact_pairs` 집합 비교.

---

## 공개 API

```python
world = forge3d.World()
floor = world.add_ground()
ball  = world.add_sphere(radius=0.5, position=(0, 0, 5))

# 전체 충돌 리스너
@world.on_collision_begin
def hit(event: forge3d.CollisionEvent) -> None:
    print(f"{event.body_a.name} hit {event.body_b.name} "
          f"at speed {event.relative_speed:.1f} m/s")

# 쌍별 핸들러
handler = world.add_collision_handler(ball, floor)
handler.on_begin = lambda e: print("Ball landed!")
handler.on_stay  = lambda e: None
handler.on_end   = lambda e: print("Ball left floor")

# 트리거 존 (물리 충돌 없음, 이벤트만)
goal_zone = world.add_trigger_zone(
    position=(5, 0, 0.5), size=(1, 1, 1))

@goal_zone.on_enter
def scored(body: forge3d.Body) -> None:
    print(f"GOAL! {body.name}")
```

---

## 완료 기준 (게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `on_collision_begin` — 공이 바닥에 닿는 첫 스텝에 정확히 1회 호출 | `test_begin_fires_once` |
| G2 | `on_collision_stay` — 접촉 유지 동안 매 스텝 호출 | `test_stay_each_step` |
| G3 | `on_collision_end` — 분리 스텝에 정확히 1회 호출 | `test_end_fires_once` |
| G4 | 쌍별 핸들러 — 등록된 쌍만 해당 핸들러 호출 | `test_pair_handler_selectivity` |
| G5 | 트리거 존 — 물리 충돌 없이 `on_enter` 호출 | `test_trigger_zone` |
| G6 | pytest + ruff + mypy 통과 | — |
