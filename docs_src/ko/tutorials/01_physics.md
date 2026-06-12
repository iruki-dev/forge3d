# 튜토리얼 1 — 물리 시뮬레이션

이 튜토리얼은 forge3d의 물리 기능을 다룹니다: 중력, 강체, 충돌, 접촉.

---

## 월드 생성

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))  # z-up, SI 단위 (m, kg, s)
```

`World`는 모든 강체를 관리하고 시뮬레이션을 진행합니다.
좌표계: **z-up**, 오른손 좌표계. 단위: 미터, 킬로그램, 초.

---

## 바디 추가

```python
ground = world.add_ground()           # 정적 무한 평면 (z=0)
box  = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
ball = world.add_sphere(radius=0.5,  position=(1, 0, 5), mass=0.5)
cap  = world.add_capsule(radius=0.2, half_length=0.5, position=(-1, 0, 5))
```

모든 `add_*` 호출은 이후에 조회·수정할 수 있는 `Body` 핸들을 반환합니다.

### 바디 제거 & 스테일 핸들 주의

```python
world.remove(box)                    # 특정 바디 제거
world.clear()                        # 동적 바디 전체 제거
world.clear(keep_statics=False)      # 모든 바디 제거
```

!!! warning "remove / clear 후 핸들은 무효화됩니다"
    `world.remove(body)` 또는 `world.clear()` 이후, 기존 변수(`ball`, `box` 등)는
    **스테일(stale) 핸들**이 됩니다.  이 핸들로 `apply_impulse`, `body.position` 등을
    호출하면 `RuntimeError: Body id=N not found in world`가 발생합니다.

    **패턴: clear 후 반드시 재할당**

    ```python
    world.clear(keep_statics=False)
    ball = world.add_sphere(...)   # 새 핸들 — 이전 'ball' 변수는 이제 무효
    ```

    **패턴: `world.contains()`로 유효성 확인**

    ```python
    if world.contains(ball):
        world.apply_impulse(ball, force * dt)
    ```

---

## 시뮬레이션 스텝

```python
dt = 1.0 / 240          # 접촉에는 240 Hz 권장
for _ in range(2400):   # 10초
    world.step(dt=dt)

print(f"박스 위치: {box.position}")
print(f"박스 속도: {box.velocity}")
```

---

## 재질 — 마찰 & 반발

```python
ice_box = world.add_box(
    size=(1, 1, 1),
    position=(0, 0, 3),
    mass=1.0,
    friction=0.05,          # 매우 미끄러움
    restitution=0.0,        # 튀지 않음
)

rubber_ball = world.add_sphere(
    radius=0.5,
    position=(0, 0, 5),
    mass=0.2,
    friction=0.8,           # 점착력 강함
    restitution=0.85,       # 매우 탄성
)
```

---

## 정적 바디

질량 없는 충돌 가능한 형상 생성:

```python
# 세 가지 방법 모두 동일
wall  = world.add_box(size=(10, 0.5, 3), position=(0, 5, 1.5), static=True)
post  = world.add_capsule(radius=0.15, half_length=3, position=(2, 0, 3), static=True)
shelf = world.add_static_box(size=(4, 0.2, 0.1), position=(0, 0, 2))

print(wall.is_static)        # True
print(shelf in world.bodies) # True
```

정적 바디는 충돌 감지 외부 루프에서 제외되어 시뮬레이션을 느리게 하지 않습니다.

---

## 속도 감쇠

```python
box.linear_damping  = 1.0   # 지수적 감쇠: 초당 63% 제거
box.angular_damping = 2.0   # 초당 86% 회전 제거
```

감쇠는 **dt 보정됨** (FPS 독립적):

```
v_next = v × exp(−linear_damping × dt)
```

---

## 레이캐스트

```python
# 지면 감지 (서스펜션 시뮬레이션용)
hit = world.raycast(
    origin=car.position + np.array([0, 0, 0.5]),
    direction=(0, 0, -1),
    max_dist=2.0,
)
on_ground = hit is not None and hit.distance < 0.6

# 시야선 체크
los = world.raycast(origin=player.position, direction=target_dir, max_dist=50)
can_see_target = los is None or los.distance > 49
```

`RayHit(body, point, normal, distance)` namedtuple 또는 `None`을 반환합니다.

전체 히트 목록은 `raycast_all()`:

```python
hits = world.raycast_all(origin=(0, 0, 10), direction=(0, 0, -1), max_dist=20)
for hit in hits:
    print(hit.body.name, f"{hit.distance:.2f} m")
```

---

## 오버랩 쿼리

```python
# 폭발 범위 내 바디 찾기
nearby = world.overlap_sphere(center=explosion_pos, radius=5.0)
for body in nearby:
    body.apply_force((0, 0, 300))   # 폭발 밀치기

# 공간 내 바디 찾기
in_room = world.overlap_box(center=(0, 0, 2), half_extents=(10, 10, 3))
```

---

## 조인트

```python
# 힌지 조인트 (문)
hinge = world.add_joint(
    "hinge", door, frame,
    anchor_a=(-0.5, 0, 0), anchor_b=(0, 0, 0),
    axis=(0, 0, 1),
    limits=(-1.5, 0.0),
    motor_velocity=1.0,
    motor_max_torque=30.0,
)

# 스프링 조인트
spring = world.add_joint(
    "spring", box, ceiling,
    stiffness=200.0, damping=10.0, rest_length=2.0,
)

# JointType enum (v2.1+)
from forge3d import JointType
hinge2 = world.add_joint(JointType.HINGE, door, frame, ...)

world.remove_joint(hinge)
```

지원 조인트: `HingeJoint`, `SpringJoint`, `DistanceJoint`, `BallJoint`, `FixedJoint`, `PrismaticJoint`.

---

## 충돌 이벤트

```python
@world.on_collision_begin
def hit(event: f3d.CollisionEvent) -> None:
    print(event.body_a.name, "->", event.body_b.name,
          f"impact={event.relative_speed:.1f} m/s")

# 개별 바디 콜백 (v2.1+)
@player.on_collision_begin
def player_hit(other, event):
    print(f"플레이어가 {other.name}에 충돌  속도={event.relative_speed:.1f} m/s")
```

---

## 트리거 존

```python
goal = world.add_trigger_zone(position=(5, 0, 0.5), size=(1, 1, 1))

@goal.on_enter
def scored(body: f3d.Body) -> None:
    print(f"골: {body.name}")

# 런타임 조작 (v2.1+)
goal.set_position((10, 0, 0.5))
goal.set_half_extents((2, 2, 2))
goal.enabled = False   # 잠시 감지 중지
```

---

## 충돌 레이어

```python
from forge3d import CollisionLayer

player.collision_layer = CollisionLayer.PLAYER
player.collision_mask  = CollisionLayer.mask_for(
    CollisionLayer.TERRAIN,
    CollisionLayer.ENEMY,
)  # 지형과 적과만 충돌

ghost.collision_layer = CollisionLayer.NONE   # 충돌 없음
```

---

## 고정 타임스텝

```python
# 옵션 A: world.update() — 벽시계 시간 누산 (권장)
world.fixed_dt    = 1 / 120
world.max_substeps = 8

while viewer.is_open:
    world.update(viewer.dt)
    viewer.draw()

# 옵션 B: 명시적 서브스텝
world.step(dt=viewer.dt, substeps=4)
```

---

## 직렬화

```python
world.save("checkpoint.json")           # 바디 + 조인트 저장
world2 = f3d.World.load("checkpoint.json")  # 새 World로 로드
world.restore("checkpoint.json")        # 현재 인스턴스 in-place 복원
```

---

## 다음: [렌더링 튜토리얼](02_rendering.md)
