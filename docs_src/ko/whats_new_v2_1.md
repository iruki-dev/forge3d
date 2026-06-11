# v2.1.0 새로운 기능

v2.1은 API 완성도와 개발자 편의성을 전면적으로 개선합니다.
모든 변경 사항은 **완전한 하위 호환**을 유지합니다 — 기존 코드는 수정 없이 동작합니다.

---

## 버그 수정

### 지형 커스텀 재질이 렌더러에 전달되지 않던 문제

`add_terrain(material=Material(...))` 이제 ID 조회 대신 스냅샷에 재질 객체를 직접 포함합니다.

```python
world.add_terrain(
    heights=h,
    cell_size=5.0,
    material=f3d.Material(color=(0.78, 0.60, 0.32), roughness=0.92),
)
snap = world.snapshot()
terrain = snap.terrains[0]
print(terrain.material)   # Material(color=(0.78, 0.60, 0.32), ...)  ← 더 이상 None 아님
```

### Body.name이 설정 불가능하던 문제

```python
head = world.add_sphere(radius=0.21, name="head")
head.name = "player_head"   # 이제 동작함
```

### world.load()를 인스턴스 메서드로 호출 시 빈 월드 반환

`World.load(path)`는 새 `World`를 반환하는 클래스메서드입니다. 인스턴스에서 호출하면
반환값이 버려집니다. in-place 복원에는 `world.restore(path)`를 사용하세요:

```python
world.restore("checkpoint.json")
print(len(world.bodies))   # 파일에서 불러온 바디들
```

---

## 새 기능

### 개별 바디 충돌 콜백

전역 핸들러를 필터링하는 대신 바디의 충돌 이벤트에 직접 구독합니다.

```python
@player.on_collision_begin
def player_hit(other, event):
    print(f"플레이어가 {other.name}에 충돌  속도={event.relative_speed:.1f} m/s")

@player.on_collision_end
def player_left(other, event):
    print(f"플레이어가 {other.name}에서 분리됨")
```

### Material.emissive

이제 재질이 스냅샷을 통해 모든 렌더러로 전파되는 발광 강도를 가집니다.

```python
lava  = f3d.Material(color=(1.0, 0.2, 0.0), emissive=4.0)
neon  = f3d.Material(color=(0.0, 0.8, 1.0), emissive=2.5)
steel = f3d.Material(color="default", emissive=0.0)   # 기본값
```

### Transform.quaternion / Transform.matrix4

스냅샷 바디 트랜스폼에서 직접 쿼터니언과 4×4 모델 행렬에 접근합니다.

```python
snap = world.snapshot()
for body in snap.bodies:
    q = body.transform.quaternion   # [w, x, y, z]
    M = body.transform.matrix4      # (4, 4) 열 우선 모델 행렬
```

### TriggerZone 런타임 조작

```python
zone = world.add_trigger_zone(position=(0, 0, 0), size=(4, 4, 4))
zone.set_position((10, 20, 0))     # 이동
zone.set_half_extents((2, 2, 2))   # 크기 변경
zone.enabled = False               # 감지 일시 중지
```

### 공간 쿼리

```python
# 다중 히트 레이캐스트 (거리순 정렬)
hits = world.raycast_all(origin=(0, 0, 10), direction=(0, 0, -1), max_dist=20)
for hit in hits:
    print(hit.body.name, f"{hit.distance:.2f} m")

# 구 오버랩
nearby = world.overlap_sphere(center=(5, 0, 1), radius=8.0)
for body in nearby:
    body.apply_force((0, 0, 300))    # 폭발 밀치기

# 박스 오버랩
in_room = world.overlap_box(center=(0, 0, 2), half_extents=(10, 10, 3))
```

### 고정 타임스텝 누산기

```python
# 옵션 A — world.update() 누산기 (권장)
world.fixed_dt    = 1 / 120   # 물리 120 Hz
world.max_substeps = 8

while viewer.is_open:
    world.update(viewer.dt)   # 프레임 속도와 무관하게 물리 안정
    viewer.draw()

# 옵션 B — 명시적 서브스텝
world.step(dt=viewer.dt, substeps=4)   # dt/4로 4번 적분
```

### 캐릭터 컨트롤러

```python
cc = world.add_character(
    position=(0, 0, 2),
    height=1.8,
    radius=0.3,
    mass=70.0,
)

while viewer.is_open:
    inp = viewer.input
    move_x = float(inp.key_held(f3d.Key.D)) - float(inp.key_held(f3d.Key.A))
    move_y = float(inp.key_held(f3d.Key.W)) - float(inp.key_held(f3d.Key.S))
    cc.move(direction=(move_x, move_y, 0), speed=5.5, dt=viewer.dt)
    if inp.key_pressed(f3d.Key.SPACE) and cc.is_grounded:
        cc.jump(impulse=6.0)
    world.step(viewer.dt)
```

### 물리 프로파일러

```python
with world.profiler:
    world.step(dt=1/60)

p = world.profiler.last
print(f"총계: {p.total*1000:.2f} ms  접촉: {p.contacts}")

avg = world.profiler.average(n=60)   # 1초 롤링 평균
```

### JointType 열거형

```python
from forge3d import JointType

hinge = world.add_joint(
    JointType.HINGE, door, frame,   # "hinge" 문자열과 동일
    anchor_a=(-0.5, 0, 0), axis=(0, 0, 1),
    limits=(-1.5, 0.0),
)
```

### CollisionLayer.mask_for()

```python
player.collision_mask = f3d.CollisionLayer.mask_for(
    f3d.CollisionLayer.TERRAIN,
    f3d.CollisionLayer.ENEMY,
)
# → 플레이어는 TERRAIN과 ENEMY와만 충돌
```

### 그림자 품질 개선

창 있는 렌더러의 기본 그림자 맵 해상도가 512²에서 **1024²**로 상향됩니다.

```python
# 더욱 선명한 그림자
viewer = f3d.Viewer(world, title="데모", shadow_resolution=2048)
```

### 바디 형상 쿼리

```python
capsule = world.add_capsule(radius=0.3, half_length=0.9, position=(0, 0, 2))
print(capsule.shape_type)     # "capsule"
print(capsule.shape_params)   # {'radius': 0.3, 'half_length': 0.9}
R = capsule.rotation_matrix   # (3, 3) 회전 행렬
```

---

## 마이그레이션

모든 변경 사항은 하위 호환입니다. 코드를 수정할 필요 없습니다.

| 이전 패턴 | v2.1 대안 |
|-----------|-----------|
| `world2 = f3d.World(); world2.load(path)` (오류) | `world2.restore(path)` 또는 `world2 = f3d.World.load(path)` |
| 전역 콜백 + 수동 이름 필터 | `body.on_collision_begin(cb)` |
| `for _ in range(4): world.step(dt/4)` | `world.step(dt, substeps=4)` |
| `"hinge"` 문자열 리터럴 | `JointType.HINGE` (문자열도 계속 동작) |
| 커스텀 재질의 `terrain_snap.material_id` 조회 | `terrain_snap.material` (직접 객체) |
