# v1.1.0 새로운 기능 — 게임 제작 대비 릴리즈

v1.1.0은 **게임 제작 경험**을 대폭 개선하는 릴리즈입니다.
18개의 개선 요청을 분석해 구현 가능한 항목 15개를 완성했습니다.

---

## 어디서나 정적 바디

v1.1.0 이전에는 움직이지 않는 충돌 가능한 박스를 만들려면 내부 API를 호출해야 했습니다:

```python
# 이전 방식 — 내부 _physics 레이어 노출
world._physics.add_static_box(size=..., position=..., ...)
```

이제 모든 바디 타입이 `static=True`를 지원하며 `world.bodies`에 자동 등록됩니다:

```python
# v1.1.0 — 깔끔한 공개 API
wall  = world.add_box(size=(10, 0.5, 3), position=(0, 5, 1.5), static=True)
post  = world.add_capsule(radius=0.15, half_length=3, position=(2,0,3), static=True)
shelf = world.add_static_box(size=(4, 0.2, 0.1), position=(0, 0, 2))

print(wall.is_static)   # True
print(shelf in world.bodies)  # True
```

정적 바디는 충돌 감지 외부 루프에서 제외됩니다 — 시뮬레이션을 느리게 하지 않습니다.

---

## 런타임 물리 프로퍼티 설정자

바디 생성 후 재질 프로퍼티 변경:

```python
box = world.add_box(size=(1,1,1), position=(0,0,5), mass=1.0)

# 런타임에 모두 설정 가능
box.friction    = 0.02   # 표면을 얼음으로 만들기
box.restitution = 0.95   # 매우 탄성 있게

# 바디별 속도 감쇠 — world.step()마다 자동 적용
box.linear_damping  = 1.0   # 지수적 감쇠: 초당 63% 제거
box.angular_damping = 2.0   # 초당 86% 회전 제거
```

감쇠는 **dt 보정됨** (FPS 독립적):

```
v_next = v × exp(−linear_damping × dt)
```

---

## 높이맵 지형 렌더링

`world.add_terrain()`이 이제 그림자 캐스팅을 포함한 부드럽게 쉐이딩된 메시로 렌더링됩니다:

```python
import numpy as np

heights = (np.sin(np.linspace(0, 4*np.pi, 64))[:, None] *
           np.cos(np.linspace(0, 3*np.pi, 64))[None, :] * 3
          ).astype(np.float32)

world.add_terrain(
    heights=np.clip(heights - heights.min(), 0, 8),
    cell_size=2.0,
    origin=(-64, -64, 0),
    material=f3d.Material(color=(0.28, 0.42, 0.16), roughness=0.95),
)

viewer = f3d.Viewer(world)
while viewer.is_open:
    world.step()
    viewer.draw()   # 지형이 그림자가 있는 쉐이딩된 메시로 표시됨 ✅
```

`RealtimeRenderer` (헤드리스/Xvfb)와 `WindowRenderer` (glfw) 모두 지형 렌더링을 지원합니다.

---

## FollowCamera 로컬 프레임

차량 게임에서 카메라는 방향과 무관하게 항상 차 뒤에 위치해야 합니다:

```python
# frame="world" (기본값): 오프셋이 월드 기준으로 유지됨
cam = f3d.FollowCamera(car, offset=(0, -8, 4))
# frame="local": 오프셋이 차체와 함께 회전
cam = f3d.FollowCamera(car, offset=(-8, 0, 3), frame="local", smoothing_hz=8)

while viewer.is_open:
    world.step()
    viewer.set_camera(cam.to_snapshot(dt=viewer.dt))   # dt 보정 스무딩
    viewer.draw()
```

`smoothing_hz` 파라미터는 이전의 프레임별 `alpha`를 대체하여, 어떤 프레임 속도에서도 동일한 동작을 보장합니다.

---

## 레이캐스트 API

광선을 쏘아 맞는 첫 번째 바디를 찾습니다:

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

---

## InputBuilder — 커스텀 윈도우 브릿지

`InputBuilder`는 `on_key_down`, `on_key_up`, `on_mouse_move`, `on_mouse_down`, `on_mouse_up`, `on_scroll` 콜백을 제공하여 모든 윈도우 라이브러리가 표준 `f3d.Input` / `f3d.Key` 시스템을 구동할 수 있습니다:

```python
import forge3d as f3d

builder = f3d.InputBuilder()

while running:
    # builder.on_key_down(name) 등으로 이벤트 공급
    inp = builder.build()

    if inp.key_held(f3d.Key.W):
        car.apply_force(forward * 500)
    if inp.key_pressed(f3d.Key.R):
        world.teleport(car, start_pos)

    world.step()
    builder.end_frame()
```

!!! note "v2.1 변경사항"
    v2.1부터 `WindowRenderer`의 윈도우 백엔드가 **glfw**로 교체됐습니다.
    새 코드에서는 `f3d.Viewer`를 직접 사용하세요 — glfw 콜백이 자동으로 연결됩니다.

---

## Viewer HUD 텍스트

별도의 UI 라이브러리 없이 텍스트 오버레이 렌더링:

```python
while viewer.is_open:
    world.step()
    viewer.draw()   # 3D 씬

    viewer.draw_text(f"★ {stars}/20", x=10, y=10, size=28,
                     color=(1.0, 0.9, 0.1))
    viewer.draw_text("게임 오버", x=640, y=360,
                     size=64, anchor="center")
    viewer.draw_text("ESC로 종료", x=1270, y=10,
                     size=18, anchor="topright")
```

---

## Weld 상대 회전

`world.weld()`이 이제 자식과 부모 사이의 상대 방향을 유지합니다:

```python
hub   = world.add_box(size=(0.5,0.5,0.5), position=(0,0,5), mass=2)
blade = world.add_box(size=(0.3,6,0.2), position=(0,3,5), mass=1)

# 블레이드가 허브에서 90°로 생성됨 — weld가 이 각도를 유지
world.weld(blade, hub)          # 상대 회전 자동 계산
# 또는 명시적으로 지정:
world.weld(blade, hub, local_rotation=[0.707, 0, 0, 0.707])

# 이제 허브가 회전할 때 블레이드도 각도를 유지
world.add_joint("hinge", hub, None, axis=(1,0,0), motor_velocity=1.5)
```

---

## 조인트 직렬화

`World.save()` / `World.load()`이 이제 모든 조인트를 포함합니다:

```python
# 모든 것 저장 — 바디 AND 조인트
world.save("scene.json")

# 로드하고 계속 — 조인트 자동 복원
world2 = f3d.World.load("scene.json")
```

지원 조인트: `HingeJoint`, `SpringJoint`, `DistanceJoint`, `BallJoint`, `FixedJoint`, `PrismaticJoint`.

---

## 성능: 이중 충돌 감지 제거

v1.0.0에서 `world.step()`은 `detect_contacts()`를 두 번 호출했습니다 — 물리용 한 번, 이벤트 디스패치용 한 번. v1.1.0은 물리 스텝의 접촉을 캐시하여 이벤트에 재사용합니다:

```
이전: step() → detect_contacts() [물리] + detect_contacts() [이벤트]
이후: step() → detect_contacts() [물리] → 캐시 → 이벤트 [무료]
```

이벤트가 많은 씬에서 이벤트 디스패치 오버헤드를 ~50% 감소시킵니다.

---

## v1.0.0에서 마이그레이션

모든 변경 사항은 **하위 호환**입니다. 기존 코드는 수정 없이 실행됩니다.

| 이전 패턴 | v1.1.0 새 패턴 |
|-----------|----------------|
| `world._physics.add_static_box(...)` | `world.add_static_box(...)` 또는 `world.add_box(static=True)` |
| 매 프레임 수동 `car.set_angular_velocity(v * 0.8)` | `car.angular_damping = 1.2` 한 번만 |
| `FollowCamera(body, offset=(0,-8,4))` (월드 프레임만) | 차량 추적을 위해 `frame="local"` 추가 |
| `alpha=0.1` 프레임별 스무딩 (FPS 종속) | `smoothing_hz=6.0` (FPS 독립) |
| Viewer에서 지형 없음 | 자동 — `world.add_terrain(...)` 만 하면 됨 |
| `World.save()`가 조인트 누락 | 이제 조인트 포함 |
